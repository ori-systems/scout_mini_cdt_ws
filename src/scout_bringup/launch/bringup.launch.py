import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import (
    FrontendLaunchDescriptionSource,
    PythonLaunchDescriptionSource,
)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


ASSET_ALLOWLIST = (
    r"['^(?:package://|file:///opt/ros/jazzy/share/)(?:[-A-Za-z0-9_%]+/)*"
    r"[-A-Za-z0-9_%]+[.](?:dae|fbx|glb|gltf|jpeg|jpg|mtl|obj|png|stl|tif|tiff|urdf|webp|xacro)$']"
)


def share(pkg, *path):
    return os.path.join(get_package_share_directory(pkg), *path)


def generate_launch_description():
    # Toggles: ros2 launch robot_bringup bringup.launch.py realsense:=false
    toggles = ["zenoh_router", "foxglove", "scout_base", "scout_description", "velodyne", "realsense"]
    args = [DeclareLaunchArgument(t, default_value="true") for t in toggles]

    zenoh_router = Node(
        package="rmw_zenoh_cpp",
        executable="rmw_zenohd",
        output="screen",
        condition=IfCondition(LaunchConfiguration("zenoh_router")),
    )

    foxglove = IncludeLaunchDescription(
    FrontendLaunchDescriptionSource(share("foxglove_bridge", "launch", "foxglove_bridge_launch.xml")),
    launch_arguments={"asset_uri_allowlist": ASSET_ALLOWLIST}.items(),
    condition=IfCondition(LaunchConfiguration("foxglove")),
)

    scout_base = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(share("scout_base", "launch", "scout_mini_omni_base.launch.py")),
        condition=IfCondition(LaunchConfiguration("scout_base")),
    )

    scout_description = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(share("scout_description", "launch", "scout_base_description.launch.py")),
        condition=IfCondition(LaunchConfiguration("scout_description")),
    )

    velodyne_driver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(share("velodyne_driver", "launch", "velodyne_driver_node-VLP16-launch.py")),
        condition=IfCondition(LaunchConfiguration("velodyne")),
    )

    velodyne_transform = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(share("velodyne_pointcloud", "launch", "velodyne_transform_node-VLP16-launch.py")),
        condition=IfCondition(LaunchConfiguration("velodyne")),
    )

    realsense = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(share("realsense2_camera", "launch", "rs_launch.py")),
        condition=IfCondition(LaunchConfiguration("realsense")),
    )

    # Give the zenoh router a moment to come up before nodes connect to it
    everything_else = TimerAction(
        period=2.0,
        actions=[foxglove, scout_base, scout_description, velodyne_driver, velodyne_transform, realsense],
    )

    return LaunchDescription(args + [zenoh_router, everything_else])