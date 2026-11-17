#!/usr/bin/env python3
"""Recover the Scout's SocketCAN adapter and Docker stack on the Pi host."""

import json
import logging
import os
from pathlib import Path
import select
import signal
import socket
import struct
import subprocess
import threading
import time


LOG = logging.getLogger("scout-can-watchdog")
STOP = threading.Event()
INTERFACE = os.environ.get("CAN_INTERFACE", "can0")
CONTAINER = os.environ.get("CONTAINER_NAME", "scout_mini_base")
TIMEOUT = float(os.environ.get("CAN_TIMEOUT", "5"))
STARTUP_GRACE = float(os.environ.get("STARTUP_GRACE", "20"))
USB_POWER_CYCLE = os.environ.get("USB_POWER_CYCLE", "0") == "1"


def run(*args, timeout=30):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def container_state():
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{json .}}", CONTAINER],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode:
        return None
    info = json.loads(result.stdout)
    state = info["State"]
    if not state["Running"] or state["Paused"] or state["Restarting"]:
        return None
    return info["Id"], state["StartedAt"]


class Heartbeat:
    """Read real AGX V2 chassis status, rather than the SDK's cached ROS state."""

    def __init__(self):
        self.sock = None
        self.ifindex = None
        self.last_seen = None

    def close(self):
        if self.sock is not None:
            self.sock.close()
        self.sock = None
        self.ifindex = None
        self.last_seen = None

    def poll(self, duration=1):
        try:
            index = socket.if_nametoindex(INTERFACE)
            if index != self.ifindex:
                self.close()
                self.sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
                # Standard, non-RTR chassis-status frames only. Command traffic
                # and CAN error notifications must never count as healthy RX.
                # CAN_ERR_FLAG must not be in this mask: Linux interprets that
                # as an error-frame registration instead of a data-frame filter.
                mask = 0x7FF | socket.CAN_EFF_FLAG | socket.CAN_RTR_FLAG
                self.sock.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER,
                                     struct.pack("=II", 0x211, mask))
                self.sock.bind((INTERFACE,))
                self.sock.setblocking(False)
                self.ifindex = index
            deadline = time.monotonic() + duration
            received = False
            while not STOP.is_set() and time.monotonic() < deadline:
                ready, _, _ = select.select([self.sock], [], [],
                                            min(0.2, max(0, deadline - time.monotonic())))
                if ready:
                    # Drain the queue so old buffered frames cannot mask a loss.
                    while True:
                        try:
                            frame = self.sock.recv(16)
                        except BlockingIOError:
                            break
                        if len(frame) == 16 and frame[4] == 8:
                            self.last_seen = time.monotonic()
                            received = True
            return received
        except OSError:
            self.close()
            STOP.wait(duration)
            return False

    def wait_for_frames(self, timeout=5):
        self.close()
        deadline = time.monotonic() + timeout
        # Require status on two separate polls after resetting/re-enumeration.
        consecutive = 0
        while not STOP.is_set() and time.monotonic() < deadline:
            consecutive = consecutive + 1 if self.poll(0.5) else 0
            if consecutive >= 2:
                return True
        return False


def reset_can():
    run("ip", "link", "set", "dev", INTERFACE, "down")
    run("ip", "link", "set", "dev", INTERFACE, "type", "can",
        "bitrate", "500000")
    run("ip", "link", "set", "dev", INTERFACE, "up")


def power_cycle_usb():
    version = run("uhubctl", "--version").strip().split(".")
    if tuple(int(v) for v in version[:2]) < (2, 6):
        raise RuntimeError("Pi 5 USB power recovery requires uhubctl >= 2.6.0")
    model = Path("/proc/device-tree/model").read_text().rstrip("\0")
    if not model.startswith("Raspberry Pi 5"):
        raise RuntimeError("USB power recovery is configured for Raspberry Pi 5 only")
    usb = Path("/sys/bus/usb/devices")
    # Cutting the Pi 5's shared USB power must not disconnect mounted storage.
    if any(p.read_text().strip() == "08" for p in usb.glob("*:*/bInterfaceClass")):
        raise RuntimeError("USB storage is attached; refusing to cut shared USB power")
    hubs = sorted(
        p.name[3:] for p in usb.glob("usb*")
        if p.resolve().parent.name.startswith("xhci-hcd.")
        and (p / "idVendor").read_text().strip() == "1d6b"
    )
    if len(hubs) != 4:
        raise RuntimeError(f"Expected four onboard Pi 5 USB root hubs, found {hubs}")
    LOG.warning("Power cycling shared USB supply; D455 will reconnect too (hubs %s)", hubs)
    try:
        for hub in hubs:
            output = run("uhubctl", "--nosysfs", "--exact", "--location", hub,
                         "--action", "off", timeout=10)
            LOG.debug("USB hub %s off: %s", hub, output.strip())
        STOP.wait(5)
    finally:
        # Restore every hub even if an off command fails or the service stops.
        errors = []
        for hub in hubs:
            try:
                output = run("uhubctl", "--nosysfs", "--exact", "--location", hub,
                             "--action", "on", timeout=10)
                LOG.debug("USB hub %s on: %s", hub, output.strip())
            except (RuntimeError, subprocess.TimeoutExpired) as error:
                errors.append(str(error))
        if errors:
            raise RuntimeError("Could not restore USB power: " + "; ".join(errors))
    deadline = time.monotonic() + 15
    while not STOP.is_set() and time.monotonic() < deadline:
        if Path(f"/sys/class/net/{INTERFACE}").exists():
            # Let udev/networkd finish initial setup before changing CAN state.
            run("udevadm", "settle", "--timeout=10", timeout=15)
            STOP.wait(2)
            if STOP.is_set():
                return
            reset_can()
            return
        STOP.wait(0.5)
    raise RuntimeError(f"{INTERFACE} did not reappear after USB power cycle")


def restart_stack(container_id):
    # Restarting creates a fresh SDK instance; previous velocity commands are
    # discarded. The watchdog itself never sends motor commands.
    run("docker", "stop", "--time", "5", container_id, timeout=20)
    if not STOP.is_set():
        run("docker", "start", container_id)


def recover(container_id, heartbeat):
    LOG.warning("No chassis heartbeat for %.1fs; stopping stack and resetting %s",
                TIMEOUT, INTERFACE)
    run("docker", "stop", "--time", "5", container_id, timeout=20)
    recovered = False
    try:
        try:
            reset_can()
            recovered = heartbeat.wait_for_frames()
        except RuntimeError as error:
            LOG.warning("CAN link reset failed: %s", error)
        if not recovered and USB_POWER_CYCLE and not STOP.is_set():
            power_cycle_usb()
            recovered = heartbeat.wait_for_frames()
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        LOG.error("Recovery failed: %s", error)
    finally:
        if not STOP.is_set():
            # Keep camera/LiDAR available even if the chassis is powered off.
            run("docker", "start", container_id)
    if recovered:
        LOG.info("Fresh CAN heartbeats restored; stack restarted")
    else:
        LOG.error("Still no CAN heartbeat; payloads restarted. Waiting for chassis RX "
                  "before restarting the base again (no repeated USB power cycles).")
    return recovered


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: STOP.set())
    LOG.info("Monitoring %s chassis heartbeat; timeout %.1fs; USB power recovery %s",
             INTERFACE, TIMEOUT, USB_POWER_CYCLE)
    heartbeat = Heartbeat()
    previous = None
    started = 0
    last_frame_at = 0
    check_process_at = 0
    waiting_for_chassis = False
    try:
        while not STOP.is_set():
            state = container_state()
            if state is None:
                # Respect docker compose stop/down and Docker maintenance.
                previous = None
                heartbeat.close()
                STOP.wait(1)
                continue
            if state != previous:
                previous = state
                started = time.monotonic()
                last_frame_at = started
                heartbeat.close()
            received = heartbeat.poll()
            now = time.monotonic()
            if received:
                last_frame_at = now
            if waiting_for_chassis:
                if received:
                    LOG.info("Chassis heartbeat returned; restarting stack to reconnect base")
                    restart_stack(state[0])
                    waiting_for_chassis = False
                continue
            if now - started < STARTUP_GRACE:
                continue
            if now - last_frame_at > TIMEOUT:
                waiting_for_chassis = not recover(state[0], heartbeat)
                previous = None
                continue
            if now >= check_process_at:
                check_process_at = now + 10
                try:
                    processes = run("docker", "top", state[0], "-eo", "pid,comm")
                except (RuntimeError, subprocess.TimeoutExpired) as error:
                    LOG.warning("Could not check base process: %s", error)
                    continue
                if "scout_base_node" not in {p.split()[-1] for p in processes.splitlines() if p.split()}:
                    LOG.warning("CAN is healthy but base process exited; restarting stack")
                    restart_stack(state[0])
    finally:
        heartbeat.close()


if __name__ == "__main__":
    main()
