# Vendored UGV SDK

This directory is tracked directly in `scout_mini_cdt_ws`, including the
existing googletest dependency. Neither directory is a Git submodule.

Upstream sources:

- UGV SDK: https://github.com/agilexrobotics/ugv_sdk
  at `f2704eacdc90357078cd93ec60aae08bb4baab35`.
- GoogleTest: https://github.com/google/googletest
  at `b796f7d44681514f58a683a3a71ff17c94edb0c1` (v1.13.0).

Local modifications, 2026-11-17:

- `include/ugv_sdk/utilities/protocol_detector.hpp` and
  `src/utilities/protocol_detector.cpp`: initialize detection flags and stop
  the CAN receiver before destroying or reconnecting the protocol detector.
  This prevents callbacks from writing to a detector after its lifetime ends.
- `include/ugv_sdk/details/async_port/async_can.hpp` and
  `src/async_port/async_can.cpp`: initialize the file descriptor, close it through
  its Asio owner, drain cancelled callbacks, and avoid joining the I/O thread
  from its own receive-error callback.

These changes address SDK lifetime and cleanup bugs. They do not establish the
cause of recurring CAN bus error states.

The upstream license files and copyright notices are retained: `LICENSE`
(Apache-2.0) and `test/googletest/LICENSE` (GoogleTest BSD license).
