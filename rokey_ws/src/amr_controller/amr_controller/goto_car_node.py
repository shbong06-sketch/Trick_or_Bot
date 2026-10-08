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

# goto_car node: 웹캠(car_locator)이 보낸 car의 map 좌표 근처로 Nav2 이동한다.
# 3_1_a1_nav_clicked_points.py 기반 (튜터님 Robot_TB4_nav_to_pose 순서: 도크 위에서 initial pose 설정 → undock).
#
# 흐름: 도크 확인 → initial pose → Nav2 대기 → /webcam/car_point 대기 → undock
#       → car 앞 approach_dist 지점으로 이동 (car를 바라보는 방향)
#       → 도착하면 arrived_near_car publish (이후 탐색·접근은 AMR 카메라 쪽 node 담당)
# 이동 중 car_point가 replan_dist 넘게 바뀌면 목표를 갱신한다.
# 그래서 startToPose(도착까지 대기) 대신 goToPose + isTaskComplete 반복을 쓴다 (튜터님 Robot_SC_nav_to_pose 방식).
#
# namespace는 코드에 넣지 않고 실행할 때 붙인다:
#   ros2 run amr_controller goto_car --ros-args -r __ns:=/robot1
# parameter (--ros-args -p 이름:=값)
#   initial_pose   [x, y, yaw_deg]  도크 위 로봇의 map 좌표·방향 (기본 [0.0, 0.0, 0.0])
#   approach_dist  0.5   car 중심에서 이만큼 앞에서 멈춤(m)
#   replan_dist    0.5   이동 중 car 좌표가 이만큼 바뀌면 목표 갱신(m)
#   max_retries    2     이동 실패 시 같은 목표로 다시 시도하는 횟수
#   car_topic      /webcam/car_point

import math

import rclpy
from rclpy.signals import SignalHandlerOptions
from geometry_msgs.msg import PointStamped, PoseWithCovarianceStamped
from nav2_simple_commander.robot_navigator import TaskResult
from rclpy.executors import ExternalShutdownException
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Navigator

LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)


class GotoCar(TurtleBot4Navigator):
    def __init__(self):
        super().__init__()
        self.initial = list(self.declare_parameter('initial_pose', [0.0, 0.0, 0.0]).value)
        self.approach_dist = self.declare_parameter('approach_dist', 0.5).value
        self.replan_dist = self.declare_parameter('replan_dist', 0.5).value
        self.max_retries = self.declare_parameter('max_retries', 2).value
        car_topic = self.declare_parameter('car_topic', '/webcam/car_point').value

        self.car = None            # 웹캠이 보낸 최신 car (x, y)
        self.robot = None          # amcl_pose 로 받은 로봇 (x, y)
        self.create_subscription(PointStamped, car_topic, self._carCallback, LATCHED)
        # amcl_pose는 transient_local로 publish됨 (BasicNavigator와 같은 QoS)
        self.create_subscription(PoseWithCovarianceStamped, 'amcl_pose', self._robotCallback, LATCHED)
        self.arrived_pub = self.create_publisher(PointStamped, 'arrived_near_car', LATCHED)
        self.car_topic = car_topic

    def _carCallback(self, msg):
        self.car = (msg.point.x, msg.point.y)

    def _robotCallback(self, msg):
        self.robot = (msg.pose.pose.position.x, msg.pose.pose.position.y)

    def goalFor(self, car):
        """로봇에서 car 쪽으로, car 중심 approach_dist 앞의 위치와 car를 바라보는 방향(도)."""
        rx, ry = self.robot or self.initial[:2]
        dx, dy = car[0] - rx, car[1] - ry
        d = math.hypot(dx, dy)
        yaw = math.degrees(math.atan2(dy, dx))
        if d <= self.approach_dist:          # 이미 충분히 가까움: 제자리에서 방향만 돌림
            return [rx, ry], yaw
        k = (d - self.approach_dist) / d
        return [rx + dx * k, ry + dy * k], yaw

    def waitForCar(self, far_from=None):
        """car_point를 받을 때까지 (far_from이 있으면 그 점에서 replan_dist 넘게 바뀔 때까지) 대기."""
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.car is not None and (far_from is None or math.dist(self.car, far_from) > self.replan_dist):
                return


def run(navigator):
    # Start on dock
    if not navigator.getDockedStatus():
        navigator.info('Docking before intialising pose')
        navigator.dock()

    # Set initial pose
    x, y, yaw = navigator.initial
    initial_pose = navigator.getPoseStamped([x, y], yaw)
    navigator.setInitialPose(initial_pose)

    # Wait for Nav2
    navigator.waitUntilNav2Active()

    # Wait for webcam
    navigator.info(f'웹캠 car 좌표 대기 중: {navigator.car_topic}')
    navigator.waitForCar()
    navigator.info(f'car 좌표 수신: x={navigator.car[0]:.2f} y={navigator.car[1]:.2f}')

    # Undock
    navigator.undock()

    # Go to the car
    retries = 0
    while rclpy.ok():
        target = navigator.car
        position, yaw = navigator.goalFor(target)
        navigator.info(f'goal x={position[0]:.2f} y={position[1]:.2f} yaw={yaw:.0f}° '
                       f'(car x={target[0]:.2f} y={target[1]:.2f})')
        if not navigator.goToPose(navigator.getPoseStamped(position, yaw)):
            result = TaskResult.FAILED
        else:
            replanned = False
            i = 0
            while not navigator.isTaskComplete():
                i += 1
                feedback = navigator.getFeedback()
                if feedback and i % 20 == 0:
                    navigator.info(f'남은 거리 {feedback.distance_remaining:.2f} m')
                if math.dist(navigator.car, target) > navigator.replan_dist:
                    navigator.info('car가 움직임 → 목표 갱신')
                    replanned = True
                    break
            if replanned:
                retries = 0
                continue
            result = navigator.getResult()

        if result == TaskResult.SUCCEEDED:
            msg = PointStamped()
            msg.header.frame_id = 'map'
            msg.header.stamp = navigator.get_clock().now().to_msg()
            msg.point.x, msg.point.y = target
            navigator.arrived_pub.publish(msg)
            navigator.info('car 근처 도착 → arrived_near_car publish (이후 탐색·접근은 AMR 카메라 쪽). '
                           'Ctrl+C로 종료')
            # 바로 끝내면 나중에 켜진 node가 arrived_near_car를 못 받으므로 살려 둔다
            rclpy.spin(navigator)
            return

        retries += 1
        if retries <= navigator.max_retries:
            navigator.warn(f'이동 실패 ({result}) → 다시 시도 {retries}/{navigator.max_retries}')
            continue
        navigator.error('이동 실패: 새 car 좌표를 기다림 (car가 벽·장애물 근처인지 확인)')
        navigator.waitForCar(far_from=target)
        retries = 0


def main():
    # Ctrl+C를 rclpy가 아닌 여기서 받는다: 종료 전에 Nav2 이동 목표를 취소하기 위함
    # (취소하지 않으면 node가 꺼져도 로봇은 마지막 목표로 계속 주행한다)
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    navigator = GotoCar()
    try:
        run(navigator)
    except (KeyboardInterrupt, ExternalShutdownException):
        if navigator.result_future and not navigator.result_future.done():
            navigator.info('Ctrl+C → Nav2 이동 취소')
            navigator.cancelTask()
    finally:
        navigator.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
