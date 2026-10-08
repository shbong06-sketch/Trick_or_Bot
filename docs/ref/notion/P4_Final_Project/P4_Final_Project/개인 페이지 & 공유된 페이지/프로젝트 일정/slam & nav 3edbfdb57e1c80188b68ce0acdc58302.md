# slam & nav

날짜: 2026년 10월 2일

1. 언도킹
2. teleop
    
    ```jsx
    ros2 run teleop_twist_keyboard teleop_twist_keyboard \
      --ros-args -p stamped:=true -r /cmd_vel:=/robot2/cmd_vel
    ```
    
3. slam
    
    ```jsx
    ros2 launch turtlebot4_navigation slam.launch.py namespace:=/robot2
    ```
    
4. rviz
    
    ```jsx
    ros2 launch turtlebot4_viz view_robot.launch.py namespace:=/robot2
    ```
    

# 2) 맵 저장

```jsx
ros2 run nav2_map_server map_saver_cli -f arena_map \
  --ros-args -p map_subscribe_transient_local:=true -r map:=/robot2/map
```

맵 확인

![image.png](slam%20&%20nav/image.png)

```jsx
eog ~/turtlebot4_ws/arena_map.pgm
```

# 3) 이후 실행 시: 저장된 맵으로 localization + Nav2

```jsx
ros2 launch turtlebot4_navigation localization.launch.py namespace:=/robot2 map:=$HOME/minicar_ws/arena_map.yaml
ros2 launch turtlebot4_navigation nav2.launch.py namespace:=/robot2
ros2 launch turtlebot4_viz view_robot.launch.py namespace:=/robot2
```

![image.png](slam%20&%20nav/image%201.png)

- Reliability Policy: `Reliable`
- Durability Policy: `Transient Local`
- 그래도 안켜질 때
    
    ```jsx
    ros2 lifecycle set /robot2/map_server deactivate
    ros2 lifecycle set /robot2/map_server activate
    ```
    
    unconfigured라면 아래 순서대로 진행
    
    ### 1. 전부 종료 후 정리
    
    모든 터미널(localization, nav2, RViz)을 `Ctrl+C`로 끄고 아래를 실행하세요.
    
    ```bash
    pkill -f amcl; pkill -f map_server; pkill -f nav2; pkill -f rviz2ros2 daemon stop && ros2 daemon startros2 node list    # /robot2 아래 nav2 관련 노드가 남아 있지 않아야 함
    ```
    
    ### 2. localization을 먼저 단독으로 실행하고 로그 보기
    
    ```bash
    ros2 launch turtlebot4_navigation localization.launch.py namespace:=/robot2 map:=$HOME/minicar_ws/arena_map.yaml
    ```
    
    ### 3. 상태 확인
    
    ```bash
    ros2 lifecycle get /robot2/map_serverros2 lifecycle get /robot2/amcl
    ```
    
- nav goal 안먹을 때
    
    ```jsx
    ros2 lifecycle get /robot2/bt_navigator
    ros2 lifecycle get /robot2/controller_server
    ros2 lifecycle get /robot2/planner_server
    ```