"""Publish one combined Scout/payload description and its joint transforms."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    description = ParameterValue(Command([
        FindExecutable(name="xacro"), " ",
        PathJoinSubstitution([FindPackageShare("payload_urdf"), "urdf", "scout_with_payload.urdf.xacro"]),
        " scout_model:=", LaunchConfiguration("scout_model"),
        " payload:=", LaunchConfiguration("payload"),
        " lidar_frame:=", LaunchConfiguration("lidar_frame"),
        " nominal_camera_frames:=", LaunchConfiguration("nominal_camera_frames"),
    ]), value_type=str)
    return LaunchDescription([
        DeclareLaunchArgument("scout_model", default_value="scout_mini/scout_mini_omni.xacro"),
        DeclareLaunchArgument("payload", default_value="true"),
        DeclareLaunchArgument("lidar_frame", default_value="velodyne"),
        DeclareLaunchArgument("nominal_camera_frames", default_value="false"),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("publish_joint_states", default_value="true"),
        Node(
            package="robot_state_publisher", executable="robot_state_publisher",
            name="robot_state_publisher", output="screen",
            parameters=[{"robot_description": description,
                         "use_sim_time": LaunchConfiguration("use_sim_time")}],
        ),
        Node(
            package="joint_state_publisher", executable="joint_state_publisher",
            name="joint_state_publisher", output="screen",
            condition=IfCondition(LaunchConfiguration("publish_joint_states")),
            parameters=[{"robot_description": description,
                         "use_sim_time": LaunchConfiguration("use_sim_time")}],
        ),
    ])
