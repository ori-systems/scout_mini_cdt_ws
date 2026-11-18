import os
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import (
    FrontendLaunchDescriptionSource,
    PythonLaunchDescriptionSource,
)
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node, PushRosNamespace, SetParametersFromFile


ASSET_ALLOWLIST = (
    r"['^(?:package://|file:///opt/ros/jazzy/share/)(?:[-A-Za-z0-9_%]+/)*"
    r"[-A-Za-z0-9_%]+[.](?:dae|fbx|glb|gltf|jpeg|jpg|mtl|obj|png|stl|tif|tiff|urdf|webp|xacro)$']"
)


def share(pkg, *path):
    return os.path.join(get_package_share_directory(pkg), *path)


def parameters(package, filename, node_name):
    with open(share(package, "config", filename), encoding="utf-8") as stream:
        return yaml.safe_load(stream)[node_name]["ros__parameters"]


def generate_launch_description():
    # Toggles: ros2 launch scout_bringup bringup.launch.py realsense:=false
    toggles = ["zenoh_router", "foxglove", "scout_base", "scout_description", "velodyne", "realsense"]
    args = [DeclareLaunchArgument(t, default_value="true") for t in toggles]
    args += [
        DeclareLaunchArgument("port_name", default_value="can0"),
        DeclareLaunchArgument("is_omni_wheel", default_value="true"),
        DeclareLaunchArgument("scout_namespace", default_value="scout_mini"),
        DeclareLaunchArgument("model", default_value="scout_mini/scout_mini_omni.xacro"),
        DeclareLaunchArgument("payload", default_value="true"),
        DeclareLaunchArgument("velodyne_ip", default_value="192.168.1.201"),
        DeclareLaunchArgument("velodyne_frame", default_value="velodyne"),
        DeclareLaunchArgument("realsense_serial", default_value="''"),
        DeclareLaunchArgument("camera_profile", default_value="640x480x15"),
        DeclareLaunchArgument("foxglove_port", default_value="8765"),
    ]

    zenoh_router = Node(
        package="rmw_zenoh_cpp",
        executable="rmw_zenohd",
        output="screen",
        condition=IfCondition(LaunchConfiguration("zenoh_router")),
    )

    foxglove = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(share("foxglove_bridge", "launch", "foxglove_bridge_launch.xml")),
        launch_arguments={
            "asset_uri_allowlist": ASSET_ALLOWLIST,
            "address": "0.0.0.0",
            "port": LaunchConfiguration("foxglove_port"),
            "max_qos_depth": "2",
            "message_backlog_size": "16",
        }.items(),
        condition=IfCondition(LaunchConfiguration("foxglove")),
    )

    scout_base = GroupAction(
        condition=IfCondition(LaunchConfiguration("scout_base")),
        actions=[
            PushRosNamespace(LaunchConfiguration("scout_namespace")),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(share("scout_base", "launch", "scout_base.launch.py")),
                launch_arguments={
                    "port_name": LaunchConfiguration("port_name"),
                    "is_scout_mini": "true",
                    "is_omni_wheel": LaunchConfiguration("is_omni_wheel"),
                }.items(),
            ),
        ],
    )

    scout_description = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(share("payload_urdf", "launch", "description.launch.py")),
        launch_arguments={
            "scout_model": LaunchConfiguration("model"),
            "payload": LaunchConfiguration("payload"),
            "lidar_frame": LaunchConfiguration("velodyne_frame"),
            # Live camera TFs are calibrated by the driver; use nominal frames
            # only when the camera driver is disabled for an offline preview.
            "nominal_camera_frames": PythonExpression([
                "'", LaunchConfiguration("realsense"), "'.lower() in ('false', '0')",
            ]),
        }.items(),
        condition=IfCondition(LaunchConfiguration("scout_description")),
    )

    driver_parameters = parameters("velodyne_driver", "VLP16-velodyne_driver_node-params.yaml", "velodyne_driver_node")
    velodyne_driver = Node(
        package="velodyne_driver", executable="velodyne_driver_node", name="velodyne_driver_node",
        output="screen", condition=IfCondition(LaunchConfiguration("velodyne")),
        parameters=[driver_parameters, {
            "device_ip": LaunchConfiguration("velodyne_ip"),
            "frame_id": LaunchConfiguration("velodyne_frame"),
        }],
    )

    transform_parameters = parameters("velodyne_pointcloud", "VLP16-velodyne_transform_node-params.yaml", "velodyne_transform_node")
    transform_parameters["calibration"] = share("velodyne_pointcloud", "params", "VLP16db.yaml")
    velodyne_transform = Node(
        package="velodyne_pointcloud", executable="velodyne_transform_node", name="velodyne_transform_node",
        output="screen", parameters=[transform_parameters, {
            "frame_id": LaunchConfiguration("velodyne_frame"),
        }],
        condition=IfCondition(LaunchConfiguration("velodyne")),
    )

    realsense = GroupAction(
        condition=IfCondition(LaunchConfiguration("realsense")),
        actions=[
            # The driver's image_transport publisher provides JPEG on demand.
            SetParametersFromFile(share("scout_bringup", "config", "realsense.yaml")),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(share("realsense2_camera", "launch", "rs_launch.py")),
                launch_arguments={
                    "device_type": "D455",
                    "camera_name": "d455",
                    "camera_namespace": "camera",
                    "serial_no": LaunchConfiguration("realsense_serial"),
                    "rgb_camera.color_profile": LaunchConfiguration("camera_profile"),
                    "depth_module.depth_profile": LaunchConfiguration("camera_profile"),
                }.items(),
            ),
        ],
    )

    # Give the zenoh router a moment to come up before nodes connect to it
    everything_else = TimerAction(
        period=2.0,
        actions=[foxglove, scout_base, scout_description, velodyne_driver, velodyne_transform, realsense],
    )

    return LaunchDescription(args + [zenoh_router, everything_else])
