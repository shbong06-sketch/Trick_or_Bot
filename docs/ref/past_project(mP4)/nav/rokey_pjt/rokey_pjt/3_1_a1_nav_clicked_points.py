#!/usr/bin/env python3

# Copyright 2022 Clearpath Robotics, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @author Roni Kreinin (rkreinin@clearpathrobotics.com)

# 3_1_a_nav_to_pose.py 기반. RViz Publish Point로 찍은 좌표들을 차례로 startToPose 한다.
# 순서는 튜터님 Robot_TB4_nav_to_pose 예제를 따른다 (도크 위에서 initial pose 설정 → undock).
# namespace는 코드에 넣지 않고 실행할 때 붙인다:
#   ros2 run rokey_pjt nav_clicked_points --ros-args -r __ns:=/robot1

import rclpy

from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator

# ======================
# 초기 설정 (파일 안에서 직접 정의)
# ======================
# 도크 위 로봇의 map 좌표 (SLAM을 도크에서 시작했으면 원점 근처)
INITIAL_POSE_POSITION = [0.0, 0.0]
INITIAL_POSE_DIRECTION = TurtleBot4Directions.NORTH

# ros2 topic echo /robot1/clicked_point 로 얻은 좌표 (x, y). z는 쓰지 않음
# 방향: NORTH=map +x, WEST=+y, SOUTH=-x, EAST=-y
GOAL_POSES = [
    ([-2.1353, -0.8995], TurtleBot4Directions.WEST),
    ([-1.9712, 0.1873], TurtleBot4Directions.NORTH_EAST),
    ([-1.1610, -1.1866], TurtleBot4Directions.NORTH_EAST),
]
# ======================


def main():
    rclpy.init()

    navigator = TurtleBot4Navigator()

    # Start on dock
    if not navigator.getDockedStatus():
        navigator.info('Docking before intialising pose')
        navigator.dock()

    # Set initial pose
    initial_pose = navigator.getPoseStamped(INITIAL_POSE_POSITION, INITIAL_POSE_DIRECTION)
    navigator.setInitialPose(initial_pose)

    # Wait for Nav2
    navigator.waitUntilNav2Active()

    # Undock
    navigator.undock()

    # Go to each goal pose
    for i, (position, direction) in enumerate(GOAL_POSES):
        navigator.info(f'[{i + 1}/{len(GOAL_POSES)}] goal {position}')
        goal_pose = navigator.getPoseStamped(position, direction)
        navigator.startToPose(goal_pose)

    rclpy.shutdown()


if __name__ == '__main__':
    main()
