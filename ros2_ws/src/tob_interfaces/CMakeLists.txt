cmake_minimum_required(VERSION 3.8)
project(tob_interfaces)

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# 메시지와 서비스의 사용 코드를 생성한다.
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/GameState.msg"
  "msg/GameEvent.msg"
  "msg/BooState.msg"
  "msg/TargetObservation.msg"
  "msg/SafetyState.msg"
  "srv/GameCommand.srv"
  DEPENDENCIES builtin_interfaces std_msgs geometry_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
