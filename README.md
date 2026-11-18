# scout_mini_cdt_ws

ROS 2 workspace for the Scout Mini CDT platform.

The Scout base driver, messages and robot descriptions are provided by the
`src/scout_ros2` Git submodule from
[ori-systems/scout_ros2](https://github.com/ori-systems/scout_ros2)

The [AgileX UGV SDK](https://github.com/agilexrobotics/ugv_sdk) at `src/ugv_sdk`
is included directly in this repository, with the CAN lifecycle fixes and its
existing googletest dependency. Its upstream revisions and local modifications
are recorded in [UPSTREAM.md](src/ugv_sdk/UPSTREAM.md).

The [Velodyne drivers](https://github.com/ros-drivers/velodyne) at
`src/velodyne` remain a submodule, alongside `src/scout_ros2`. Both submodules
are pinned to specific commits.

## Clone the workspace

```bash
git clone --recurse-submodules https://github.com/ori-systems/scout_mini_cdt_ws.git
cd scout_mini_cdt_ws
```

For an existing clone, initialise all submodules with:

```bash
git submodule update --init --recursive
```

## Update the Scout dependency

Fetch the latest commit from the Scout submodule, then record the new
submodule version in this workspace:

```bash
git submodule update --remote -- src/scout_ros2
git add src/scout_ros2
git commit -m "Update Scout submodule"
```

Rebuild the affected ROS packages after changing the submodule version.

## Docker deployment on the Pi

Docker owns the runtime stack. Build the ROS packages inside the container.

```bash
cd ~/cdt_ws
cp docker/.env.example docker/.env
```

Stop and disable the old host startup services so they do not compete with
the container:

```bash
sudo systemctl disable --now scout-mini.service rmw-zenohd.service
```

```bash
docker compose --env-file docker/.env -f docker/docker-compose.yml run --rm --no-deps --pull never scout_mini_base build
docker compose --env-file docker/.env -f docker/docker-compose.yml up -d --no-build --pull never
```

Compose launches the Scout Mini base under `/scout_mini`, the selected robot
description and joint states, VLP-16 packet and point-cloud nodes, D455 colour
and depth streams at 640 x 480 / 15 fps, a Zenoh router on TCP 7448 and Foxglove
on TCP 8765. It restarts the container unless explicitly stopped. No velocity
commands are sent by bringup.

Inspect or stop the deployment with:

```bash
docker compose --env-file docker/.env -f docker/docker-compose.yml logs -f
docker compose --env-file docker/.env -f docker/docker-compose.yml down
```

## Foxglove

Connect the PC to the Scout LAN/Wi-Fi, open Foxglove, choose a Foxglove
WebSocket connection and enter `ws://192.168.1.2:8765`.

Useful topics:
| Topic | Display |
| --- | --- |
| `/scout_mini/odom` | Odometry / raw messages |
| `/robot_description` | Scout robot model in a 3D panel, fixed frame `odom` |
| `/velodyne_points` | Full point cloud at the sensor rate, fixed frame `velodyne` |
| `/camera/d455/color/image_raw/compressed` | JPEG colour image for Wi-Fi / Foxglove, quality 70 |
| `/camera/d455/color/image_raw` | Full colour image, preferably viewed over Ethernet |
| `/camera/d455/depth/image_rect_raw` | Depth image |

The bridge serves the robot model's `package://` mesh resources. Velodyne
packets and point clouds are provided at full resolution and sensor rate,
without preview decimation or throttling. The standard `compressed_image_transport`
plugin provides JPEG at the camera's 640 x 480 / 15 fps profile; select the
`/compressed` topic in Foxglove's Image panel. Raw camera images and point clouds
consume significant Wi-Fi bandwidth; subscribe only to streams being used.

The VLP-16 at `192.168.1.201` sends its UDP data directly to the Pi's reserved
address `192.168.1.2`, ports 2368/8308.

## Automatic CAN recovery on the Pi

The host watchdog checks heartbeats on `can0`. After five seconds without a heartbeat it
stops the Docker stack, resets CAN at 500 kbit/s, and starts the stack again.
If a link reset fails, it power cycles the Pi 5's shared USB supply before
retrying. This also briefly disconnects the D455. Old SDK velocity commands
are discarded by restarting the container.

Install on the Pi from the workspace root. The host needs `uhubctl` **2.6.0 or
newer**, which includes Pi 5 support;[upstream installation instructions](https://github.com/mvp/uhubctl#compiling)
if a suitable package is unavailable.

```bash
sudo install -D -m 0644 docker/can-watchdog.py /usr/local/lib/scout-mini/can-watchdog.py
sudo install -m 0644 docker/scout-can-watchdog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now scout-can-watchdog.service
```

The watchdog allows 20 seconds for container startup, restarts an exited base
process, and respects an explicitly stopped or removed container. If one full
recovery attempt still receives no chassis heartbeat, it resumes the camera
and LiDAR and waits for CAN traffic to return before restarting the base again.
It avoids repeatedly power cycling USB while the chassis is switched off, and
refuses shared USB power cycling if a USB storage device is connected.

```bash
journalctl -u scout-can-watchdog.service -f
sudo systemctl stop scout-can-watchdog.service   # suspend recovery for maintenance
sudo systemctl start scout-can-watchdog.service
```

This recovers communication failures; persistent CAN wiring, termination,
power, or adapter firmware faults still need fixing.


## Scout and CDT payload description

The default boot stack loads a single combined Scout Mini Omni and CDT
payload model from `src/payload_urdf`. `scout_bringup` accepts `payload:=false` to select the base model alone.