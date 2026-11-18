cmake_minimum_required(VERSION 3.8)
project(payload_urdf)

find_package(ament_cmake REQUIRED)
install(DIRECTORY meshes urdf launch DESTINATION share/${PROJECT_NAME})
ament_package()
