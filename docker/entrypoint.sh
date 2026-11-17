#!/bin/bash
set -eo pipefail

source "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
cd "${WORKSPACE:-/home/ori/cdt_ws}"

case "${1:-launch}" in
  build)
    shift
    export CMAKE_BUILD_PARALLEL_LEVEL="${BUILD_JOBS:-2}"
    export MAKEFLAGS="-j${BUILD_JOBS:-2}"
    exec colcon build --packages-up-to scout_bringup --executor sequential \
      --cmake-args -DBUILD_TESTING=OFF "$@"
    ;;
  launch)
    if (( $# > 0 )); then shift; fi
    if [[ ! -f install/setup.bash ]]; then
      echo 'Workspace is not built. Run the Compose service with command: build' >&2
      exit 1
    fi
    source install/setup.bash
    exec ros2 launch scout_bringup bringup.launch.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
