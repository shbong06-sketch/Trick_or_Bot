# Creating Custom ROS2 Interface

> 원본: https://indecisive-freedom-6e8.notion.site/3908e215779c824ea0dc81f0c729a25f  
> 최종 수정: 2026-07-24 17:42 / 변환: 2026-10-08 14:05

| 속성 | 값 |
|---|---|
| 상태 | 완료 |
| 환경 | ubuntu22.04,humble,ubuntu24.04,jazzy |
| 순서 | 1-0-3 |

> 💡 **모든 작업은** **`rokey_venv`** **안에서 실행**해야 합니다.
>
> 터미널에 **(rokey_venv)** 가 없을 경우, **반드시** 아래 커맨드를 실행해 venv 환경을 활성화하세요.
>
> ```python
> source ~/venvs/rokey_venv/bin/activate
> ```

- reference

  🔗 embed: <https://docs.ros.org/en/humble/Tutorials.html>

- example service interface creation

```bash
cd ~/Documents/ros2_ws/src
ros2 pkg create my_interfaces --build-type ament_cmake
cd my_interfaces
mkdir srv
echo -e "int64 a\nint64 b\n---\nint64 sum" > srv/AddTwoInts.srv
```

```bash

# Replace package.xml
<?xml version="1.0"?>
<package format="3">
  <name>my_interfaces</name>
  <version>0.0.0</version>
  <description>Test interfaces</description>
  <maintainer email="kimandreas@hotmail.com">rokey-kim</maintainer>
  <license>Apache 2.0</license>

  <buildtool_depend>ament_cmake</buildtool_depend>
  <build_depend>rosidl_default_generators</build_depend>
  <exec_depend>rosidl_default_runtime</exec_depend>
  <member_of_group>rosidl_interface_packages</member_of_group>

  <export>
    <build_type>ament_cmake</build_type>
    <!-- <member_of_group>rosidl_interface_packages</member_of_group> -->
  </export>
</package>
```

```bash
# Replace CMakeLists.txt

cmake_minimum_required(VERSION 3.8)
project(my_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/AddTwoInts.srv"
)

ament_package()
```

```bash

# Rebuild
cd ~/Documents/ros2_ws
rm -rf build/ install/ log/
colcon build --packages-select my_interfaces
source install/setup.bash

sudo apt install tree
tree ~/Documents/ros2_ws/src/my_interfaces/
cat ~/Documents/ros2_ws/src/my_interfaces/package.xml
cat ~/Documents/ros2_ws/src/my_interfaces/CMakeLists.txt

ros2 interface list
ros2 interface show my_interfaces/srv/AddTwoInts 

```

```bash
#add below line to package.xml in the package that uses this interface
 <exec_depend>my_interfaces</exec_depend>
```
