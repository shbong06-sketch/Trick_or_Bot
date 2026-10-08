# Robot_TB4_follow_waypoints

> 원본: https://indecisive-freedom-6e8.notion.site/3a48e215779c80e8bed6e8fdf02ab5e8  
> 최종 수정: 2026-07-30 16:11 / 변환: 2026-10-08 15:51

### 학습 목표

- 단일 목적지로 이동하는 `Nav2`의 핵심 사용법 익힌다.

### 핵심 개념

### 코드 구현

#### **목표 지점 좌표 찾기:**

- localization 실행

  ```bash
  ros2 launch turtlebot4_navigation localization.launch.py namespace:=/robot<n> map:=$HOME/<map_directory>/<map_name>.yaml
  ```

- rivz 실행

  ```bash
  ros2 launch turtlebot4_viz view_robot.launch.py namespace:=/robot<n>
  ```

- RViz 상단에서 "Publish Point" 버튼 선택

  - 마우스 커서가 십자 모양으로 바뀜

  - 지도 위 원하는 위치를 클릭

- 새로운 좌표가 `/clicked_point` 토픽으로 발행됨

  ```bash
  ros2 topic echo /robot<n>/clicked_point
  ```

  ```bash
  mi@mi:~$ ros2 topic echo /robot<n>/clicked_point
  header:
    stamp:
      sec: 280
      nanosec: 407000000
    frame_id: map
  point:
    x: -1.491623992919922
    y: -2.1892388038635254
    z: 0.002471923828125
  ---
  ```

#### **follow_waypoints.py:**

```python
#!/usr/bin/env python3

import rclpy
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator

# ======================
# 초기 설정 (파일 안에서 직접 정의)
# ======================
INITIAL_POSE_POSITION = [0.01, 0.01]
INITIAL_POSE_DIRECTION = TurtleBot4Directions.NORTH

GOAL_POSES = [
    ([-0.02, -1.39], TurtleBot4Directions.NORTH),
    ([-2.77, -1.29], TurtleBot4Directions.SOUTH),
    ([-0.29, -0.22], TurtleBot4Directions.EAST),
]
# ======================

def main():
    rclpy.init()
    navigator = TurtleBot4Navigator()

    if not navigator.getDockedStatus():
        navigator.info('Docking before initializing pose')
        navigator.dock()

    initial_pose = navigator.getPoseStamped(INITIAL_POSE_POSITION, INITIAL_POSE_DIRECTION)
    navigator.setInitialPose(initial_pose)

    navigator.waitUntilNav2Active()

    navigator.undock()

    goal_pose_msgs = [navigator.getPoseStamped(position, direction) for position, direction in GOAL_POSES]
    navigator.startFollowWaypoints(goal_pose_msgs)

    navigator.dock()

    rclpy.shutdown()

if __name__ == '__main__':
    main()

```

### 빌드 및 실행

- 빌드

  ```bash
  cd ~/rokey_ws
  colcon build --packages-select rokey_pjt
  source install/setup.bash
  ```

- localization 실행

  ```bash
  ros2 launch turtlebot4_navigation localization.launch.py namespace:=/robot<n> map:=$HOME/<map_directory>/<map_name>.yaml
  ```

- rviz 실행

  ```bash
  ros2 launch turtlebot4_viz view_navigation.launch.py namespace:=/robot<n>
  ```

- nav2 실행

  ```bash
  ros2 launch turtlebot4_navigation nav2.launch.py namespace:=/robot<n>
  ```

- navigation node 실행

  ```bash
  ros2 run rokey_pjt follow_waypoints --ros-args -r __ns:=/robot<n>
  ```
