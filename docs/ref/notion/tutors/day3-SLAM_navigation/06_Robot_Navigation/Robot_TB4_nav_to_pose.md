# Robot_TB4_nav_to_pose

> 원본: https://indecisive-freedom-6e8.notion.site/3a48e215779c80198cc3c8f979bae14f  
> 최종 수정: 2026-07-30 16:11 / 변환: 2026-10-08 15:51

### 학습 목표

- 단일 목적지로 이동하는 `Nav2`의 핵심 사용법 익힌다.

### 핵심 개념

- **`TurtleBot4Navigator`** **클래스 사용**

  - 내비게이션 기능을 간결하게 사용할 수 있도록 래핑된 클래스

  - 도킹, 포즈 설정, 목표 이동, 상태 체크 등을 메서드로 제공

- **도킹 상태 확인 및 초기 포즈 설정**

  - 시작 시 도킹되어 있는지 확인하고, 도킹 상태를 기준으로 초기 위치 설정

- **목표 위치로 자율주행**

  - 목표 좌표를 설정하고 `startToPose()`로 이동 명령 실행

- **기본 좌표계 이해**

  - `TurtleBot4Directions`: NORTH, EAST, SOUTH, WEST 등 방향 정의

  ```
      NORTH = 0
      NORTH_WEST = 45
      WEST = 90
      SOUTH_WEST = 135
      SOUTH = 180
      SOUTH_EAST = 225
      EAST = 270
      NORTH_EAST = 315
  ```

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
  mi@mi:~$ ros2 topic echo /robot4/clicked_point
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

#### **nav_to_pose.py:**

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
    ([-0.87, -1.21], TurtleBot4Directions.NORTH),
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

    goal_pose = navigator.getPoseStamped(*GOAL_POSES[0])
    navigator.startToPose(goal_pose)
    navigator.goToPose

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
  ros2 run rokey_pjt nav_to_pose --ros-args -r __ns:=/robot<n>
  ```

### 요약 정리

|  |  |
|---|---|
| 항목 | 설명 |
| 도킹 여부 확인 | `getDockedStatus()` |
| 도킹 수행 | `dock()` |
| 초기 포즈 설정 | `setInitialPose()` |
| 목표 위치 지정 | `getPoseStamped([x, y], 방향)` |
| 이동 명령 | `startToPose(goal_pose)` |
| 방향 정의 | `TurtleBot4Directions.NORTH`, `EAST`, ... |
