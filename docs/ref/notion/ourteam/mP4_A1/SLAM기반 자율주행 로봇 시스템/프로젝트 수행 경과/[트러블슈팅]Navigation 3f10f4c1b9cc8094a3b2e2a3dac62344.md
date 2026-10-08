# [트러블슈팅]Navigation

마지막 수정: 2026년 10월 7일 오전 9:35
분류: 트러블슈팅
분야: ROS2
생성일: 2026년 10월 7일 오전 8:29
작성 상태: 작성 중

```jsx
[controller_server-1] [WARN] [1791329326.393827533] [robot1.controller_server.rclcpp]: failed to send response to /robot1/controller_server/change_state (timeout): client will not receive response, at ./src/rmw_response.cpp:153, at ./src/rcl/service.c:400
[controller_server-1] [INFO] [1791329328.415557553] [robot1.local_costmap.local_costmap]: StaticLayer: Resizing static layer to 161 X 338 at 0.050000 m/pix
```

```jsx
echo $ROS_SUPER_CLIENT
# 결과가 True

export ROS_SUPER_CLINET=False
ros-restart # daemon stop && start
```