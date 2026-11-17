# scout_mini_cdt_ws

ROS 2 workspace for the Scout Mini CDT platform.

The Scout base driver, messages and robot descriptions are provided by the
`src/scout_ros2` Git submodule from
[ori-systems/scout_ros2](https://github.com/ori-systems/scout_ros2)

## Clone the workspace

```bash
git clone --recurse-submodules https://github.com/ori-systems/scout_mini_cdt_ws.git
cd scout_mini_cdt_ws
```

For an existing clone, initialise the Scout submodule with:

```bash
git submodule update --init --recursive -- src/scout_ros2
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
