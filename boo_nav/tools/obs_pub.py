#!/usr/bin/env python3
"""가짜 TargetObservation 발행기: 펌킨이 지도 (x, y)에 보인다고 알린다.

사용: python3 boo_nav/tools/obs_pub.py 2.0 1.0        # (2.0, 1.0)에 계속 보임
      python3 boo_nav/tools/obs_pub.py --none         # 보이지 않음(detected=false)
Ctrl+C로 끝낸다. 실제 탐지·위치 계산 노드가 준비되기 전에 Boo 추격을 시험하는 용도.
"""
import argparse

import rclpy
from rclpy.executors import ExternalShutdownException
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from tob_interfaces.msg import TargetObservation


class ObsPub(Node):
    def __init__(self, pos):
        super().__init__('fake_obs_pub')
        self.pos = pos
        self.pub = self.create_publisher(
            TargetObservation, '/tob/target/observation',
            QoSProfile(depth=1, reliability=QoSReliabilityPolicy.RELIABLE))
        self.create_timer(0.1, self.tick)

    def tick(self):
        msg = TargetObservation()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.source = 'boo_camera'
        if self.pos is not None:
            msg.detected = True
            msg.map_valid = True
            msg.confidence = 0.9
            msg.target_position = PointStamped()
            msg.target_position.header.frame_id = 'map'
            msg.target_position.header.stamp = msg.header.stamp
            msg.target_position.point.x, msg.target_position.point.y = self.pos
        self.pub.publish(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('x', nargs='?', type=float)
    ap.add_argument('y', nargs='?', type=float)
    ap.add_argument('--none', action='store_true')
    ap.add_argument('--sim-time', action='store_true', help='시뮬레이션 시간 사용')
    args = ap.parse_args()
    pos = None if args.none or args.x is None else (args.x, args.y)
    rclpy.init(args=['--ros-args', '-p', f'use_sim_time:={str(args.sim_time).lower()}'])
    node = ObsPub(pos)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
