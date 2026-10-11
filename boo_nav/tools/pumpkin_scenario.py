#!/usr/bin/env python3
"""펌킨(로봇2)을 지정한 지점으로 걸어가게 하고, Boo와의 실제 거리와 Boo 행동 상태를 시간순으로 기록한다.

한 프로세스로 처리한다(ros2 CLI를 여러 번 띄우면 DDS 참가자가 늘어 연결이 불안정해진다).
사용: python3 boo_nav/tools/pumpkin_scenario.py -3.0 -0.2 --sim-time   # (-3.0, -0.2)까지 걸어가 멈춤
기록하는 값: 상태가 바뀌는 순간(SUSPECT=탐지 순간, CHASE, SEARCH, PATROL)의 Boo–펌킨 실제 거리,
             그리고 끝날 때(Ctrl+C 또는 --seconds) 마지막 거리. Boo·펌킨 위치는 각각 AMCL 값이다.
"""
import argparse
import math
import time

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, TwistStamped
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from tob_interfaces.msg import BooState

POSE_QOS = QoSProfile(depth=1, reliability=QoSReliabilityPolicy.RELIABLE,
                      durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
STATE_QOS = QoSProfile(depth=1, reliability=QoSReliabilityPolicy.RELIABLE)
NAMES = {0: 'IDLE', 1: 'PATROL', 2: 'SUSPECT', 3: 'CHASE', 4: 'SEARCH'}


def yaw_of(q):
    """쿼터니언 q의 바라보는 방향(yaw, 라디안)."""
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


class Scenario(Node):
    """펌킨을 목표 지점으로 몰고 가며 Boo 상태 변화와 두 로봇 사이 거리를 로그로 남기는 노드."""

    def __init__(self, goal, seconds):
        super().__init__('pumpkin_scenario')
        self.goal, self.seconds = goal, seconds
        self.boo = self.pumpkin = None    # 두 로봇의 최신 지도 위치(AMCL)
        self.behavior = None              # Boo의 현재 행동 번호 (바뀐 순간을 잡기 위함)
        self.t0 = time.time()             # 시나리오 시작 시각(로그의 + 경과 초 기준)
        self.create_subscription(PoseWithCovarianceStamped, '/robot1/amcl_pose',
                                 lambda m: setattr(self, 'boo', m.pose.pose), POSE_QOS)
        self.create_subscription(PoseWithCovarianceStamped, '/robot2/amcl_pose',
                                 lambda m: setattr(self, 'pumpkin', m.pose.pose), POSE_QOS)
        self.create_subscription(BooState, '/tob/boo/state', self.on_state, STATE_QOS)
        self.pub = self.create_publisher(TwistStamped, '/robot2/cmd_vel', 10)
        self.create_timer(0.1, self.tick)
        self.create_timer(5.0, self.report)

    def dist(self):
        """Boo–펌킨 실제 거리[m] (AMCL 위치 기준). 위치를 모르면 nan."""
        if self.boo is None or self.pumpkin is None:
            return float('nan')
        return math.hypot(self.boo.position.x - self.pumpkin.position.x,
                          self.boo.position.y - self.pumpkin.position.y)

    def log(self, text):
        """시나리오 시작 후 경과 초와 함께 로그를 남긴다."""
        self.get_logger().info(f'+{time.time() - self.t0:5.1f}s {text}')

    def on_state(self, msg):
        """Boo 행동이 바뀐 순간(SUSPECT는 탐지 순간)에 두 로봇 위치와 실제 거리를 기록한다."""
        if msg.behavior != self.behavior:
            self.behavior = msg.behavior
            if self.boo and self.pumpkin:
                self.log(f'{NAMES[msg.behavior]:8s} 시작 | Boo=({self.boo.position.x:.2f},{self.boo.position.y:.2f}) '
                         f'펌킨=({self.pumpkin.position.x:.2f},{self.pumpkin.position.y:.2f}) '
                         f'실제 거리={self.dist():.2f} m | {msg.reason}')

    def report(self):
        """5초마다 현재 거리와 Boo 상태를 기록한다."""
        if self.boo and self.pumpkin:
            self.log(f'  거리 {self.dist():.2f} m (상태 {NAMES.get(self.behavior, "?")})')

    def tick(self):
        """0.1초마다 펌킨 속도를 정한다: 목표 방향으로 돌고(최대 0.6 rad/s), 거의 정면이면 0.15 m/s로 전진, 0.15 m 안이면 정지."""
        if time.time() - self.t0 > self.seconds:
            self.log(f'종료: 마지막 실제 거리 {self.dist():.2f} m (상태 {NAMES.get(self.behavior, "?")})')
            raise ExternalShutdownException
        cmd = TwistStamped()
        cmd.header.frame_id = 'base_link'
        if self.pumpkin is not None:
            p = self.pumpkin.position
            dx, dy = self.goal[0] - p.x, self.goal[1] - p.y
            if math.hypot(dx, dy) > 0.15:
                err = math.atan2(math.sin(math.atan2(dy, dx) - yaw_of(self.pumpkin.orientation)),
                                 math.cos(math.atan2(dy, dx) - yaw_of(self.pumpkin.orientation)))
                cmd.twist.angular.z = max(-0.6, min(0.6, 1.2 * err))
                cmd.twist.linear.x = 0.15 if abs(err) < 0.5 else 0.0
        self.pub.publish(cmd)


def main():
    """인자: 펌킨 목표 x y, --seconds(기본 150초 뒤 종료), --sim-time(시뮬레이션 시계 사용)."""
    ap = argparse.ArgumentParser()
    ap.add_argument('x', type=float)
    ap.add_argument('y', type=float)
    ap.add_argument('--seconds', type=float, default=150.0)
    ap.add_argument('--sim-time', action='store_true')
    a = ap.parse_args()
    rclpy.init(args=['--ros-args', '-p', f'use_sim_time:={str(a.sim_time).lower()}'])
    node = Scenario((a.x, a.y), a.seconds)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
