ARG ROS_DISTRO=jazzy

FROM ros:${ROS_DISTRO}-ros-base-noble

ENV DEBIAN_FRONTEND=noninteractive
# ENV ROS_DISTRO=jazzy
# ENV WS=/ros2_ws

# Install rmw_zenoh
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ros-${ROS_DISTRO}-rmw-zenoh-cpp \
    ros-${ROS_DISTRO}-foxglove-bridge \
    ros-${ROS_DISTRO}-compressed-image-transport \
 && rm -rf /var/lib/apt/lists/*

# Install udev and librealsense2
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    udev \
    usbutils \
    ros-${ROS_DISTRO}-librealsense2* \
    ros-${ROS_DISTRO}-realsense2-* \
 && rm -rf /var/lib/apt/lists/*

# Install dependencies with rosdep
RUN --mount=type=bind,source=src,target=src \
    apt-get update \
 && rosdep update \
 && rosdep install --from-paths src --ignore-src -r -y --skip-keys catkin \
 && rm -rf /var/lib/apt/lists/*
    
# Source the ROS setup file
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> ~/.bashrc

ARG WORKSPACE
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

# Add vscode user with same UID and GID as your host system
# (copied from https://code.visualstudio.com/remote/advancedcontainers/add-nonroot-user#_creating-a-nonroot-user)
RUN (userdel -r ubuntu || true) \
    && groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo ${USERNAME} ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

# Switch from root to user
USER ${USERNAME}
WORKDIR ${WORKSPACE}
