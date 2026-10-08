# [기술검증]gazebo 상 auto slam 및 Nav2 기본 동작 확인

마지막 수정: 2026년 10월 6일 오후 12:39
분류: 실험
생성일: 2026년 10월 6일 오전 11:32

[auto slam (시간 상 중간 중단)](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5Dgazebo%20%EC%83%81%20auto%20slam%20%EB%B0%8F%20Nav2%20%EA%B8%B0%EB%B3%B8%20%EB%8F%99%EC%9E%91%20%ED%99%95%EC%9D%B8/Screencast_from_2026-10-06_11-26-03.webm)

auto slam (시간 상 중간 중단)

[nav_to_pose — map 좌표 (-13.0, 9.0) 이동](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5Dgazebo%20%EC%83%81%20auto%20slam%20%EB%B0%8F%20Nav2%20%EA%B8%B0%EB%B3%B8%20%EB%8F%99%EC%9E%91%20%ED%99%95%EC%9D%B8/Screencast_from_2026-10-06_11-29-30.webm)

nav_to_pose — map 좌표 (-13.0, 9.0) 이동

[nav_through_poses — go to pose 진행](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5Dgazebo%20%EC%83%81%20auto%20slam%20%EB%B0%8F%20Nav2%20%EA%B8%B0%EB%B3%B8%20%EB%8F%99%EC%9E%91%20%ED%99%95%EC%9D%B8/Screencast_from_2026-10-06_11-35-28.webm)

nav_through_poses — go to pose 진행

```python

    goal_pose.append(navigator.getPoseStamped([-3.0, 0.0], TurtleBot4Directions.EAST))
    goal_pose.append(navigator.getPoseStamped([-3.0, -3.0], TurtleBot4Directions.NORTH))
    goal_pose.append(navigator.getPoseStamped([3.0, -3.0], TurtleBot4Directions.NORTH_WEST))
    goal_pose.append(navigator.getPoseStamped([9.0, -1.0], TurtleBot4Directions.WEST))
    goal_pose.append(navigator.getPoseStamped([9.0, 1.0], TurtleBot4Directions.SOUTH))
    goal_pose.append(navigator.getPoseStamped([-1.0, 1.0], TurtleBot4Directions.EAST))
```

go_through_poses — nav_through_poses client에 

[follow_waypoints — 4개의 경유점을 지나며 이동](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5Dgazebo%20%EC%83%81%20auto%20slam%20%EB%B0%8F%20Nav2%20%EA%B8%B0%EB%B3%B8%20%EB%8F%99%EC%9E%91%20%ED%99%95%EC%9D%B8/Screencast_from_2026-10-06_11-46-27.webm)

follow_waypoints — 4개의 경유점을 지나며 이동

```
goal_pose.append(navigator.getPoseStamped([-3.3, 5.9], TurtleBot4Directions.NORTH))
goal_pose.append(navigator.getPoseStamped([2.1, 6.3], TurtleBot4Directions.EAST))
goal_pose.append(navigator.getPoseStamped([2.0, 1.0], TurtleBot4Directions.SOUTH))
goal_pose.append(navigator.getPoseStamped([-1.0, 0.0], TurtleBot4Directions.NORTH))
```

go_through_poses — nav_through_poses client에 

[create_path — 4개의 임의 점을 2D pose Estimation 사용해 way point 좌표를 추출](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5Dgazebo%20%EC%83%81%20auto%20slam%20%EB%B0%8F%20Nav2%20%EA%B8%B0%EB%B3%B8%20%EB%8F%99%EC%9E%91%20%ED%99%95%EC%9D%B8/Screencast_from_2026-10-06_11-56-03.webm)

create_path — 4개의 임의 점을 2D pose Estimation 사용해 way point 좌표를 추출

[mail_delivery — 저장되어 있는 목표 옵션 중 1, 4번 선택하여 이동](%5B%EA%B8%B0%EC%88%A0%EA%B2%80%EC%A6%9D%5Dgazebo%20%EC%83%81%20auto%20slam%20%EB%B0%8F%20Nav2%20%EA%B8%B0%EB%B3%B8%20%EB%8F%99%EC%9E%91%20%ED%99%95%EC%9D%B8/Screencast_from_2026-10-06_12-08-56.webm)

mail_delivery — 저장되어 있는 목표 옵션 중 1, 4번 선택하여 이동

[https://app.notion.com](https://app.notion.com)

go_through_poses는 경유점을 고려한 전체 path planning을 처음부터 계산

waypoint는 한 지점으로 이동 후 다음 값을 받아와서 경로 계산하고 이동하는 방식