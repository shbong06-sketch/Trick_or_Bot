#!/usr/bin/env python3
"""가짜 펌킨 탐지기: 시뮬레이션에서 펌킨(로봇2)의 실제 위치를 따라가며 Boo의 카메라가 볼 수 있을 때만 관측을 발행한다.

실제 탐지·위치 계산 노드(tob_perception, tob_localization)가 준비되기 전에 Boo 추격을 시험하는 용도다.
발행: /tob/target/observation (TargetObservation, source=boo_camera)
- 보일 조건(모두 만족): ① Boo와 펌킨 사이 거리 ≤ --range (기본 2.5 m, SRD SR-009 탐지 요구 범위의 상한)
  ② 펌킨이 Boo 정면 시야각 안(기본 수평 69°, OAK-D RGB 수평 화각) ③ 두 로봇 사이를 지도의 벽이 가리지 않음
- 보이면 detected=true, map_valid=true, 펌킨의 지도 위치(AMCL), 거리. 안 보이면 detected=false, map_valid=false.
- 위치는 /robot1/amcl_pose(Boo)와 /robot2/amcl_pose(펌킨)를 쓴다. 펌킨은 teleop으로 움직인다(가이던스 참고).
"""
import argparse
import math

import numpy as np
import rclpy
import yaml
from geometry_msgs.msg import PointStamped, PoseWithCovarianceStamped
from PIL import Image
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from tob_interfaces.msg import TargetObservation

POSE_QOS = QoSProfile(depth=1, reliability=QoSReliabilityPolicy.RELIABLE,
                      durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
OBS_QOS = QoSProfile(depth=1, reliability=QoSReliabilityPolicy.RELIABLE)


class Grid:
    """지도(pgm+yaml)에서 두 점 사이를 벽이 가리는지 검사한다."""

    def __init__(self, yaml_path):
        meta = yaml.safe_load(open(yaml_path, encoding='utf-8'))
        img = Image.open(yaml_path.rsplit('/', 1)[0] + '/' + meta['image'])
        self.occ = np.array(img) < 50          # 검은 칸 = 벽
        self.res = float(meta['resolution'])
        self.ox, self.oy = float(meta['origin'][0]), float(meta['origin'][1])
        self.h = self.occ.shape[0]

    def blocked(self, a, b):
        n = max(int(math.hypot(b[0] - a[0], b[1] - a[1]) / (self.res / 2)), 1)
        for i in range(n + 1):
            x = a[0] + (b[0] - a[0]) * i / n
            y = a[1] + (b[1] - a[1]) * i / n
            col = int((x - self.ox) / self.res)
            row = self.h - 1 - int((y - self.oy) / self.res)
            if not (0 <= col < self.occ.shape[1] and 0 <= row < self.h) or self.occ[row, col]:
                return True
        return False


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


class FakeDetector(Node):
    def __init__(self, args):
        super().__init__('fake_detector')
        self.args = args
        self.grid = Grid(args.map)
        self.boo = None
        self.pumpkin = None
        self.create_subscription(PoseWithCovarianceStamped, '/robot1/amcl_pose',
                                 lambda m: setattr(self, 'boo', m.pose.pose), POSE_QOS)
        self.create_subscription(PoseWithCovarianceStamped, '/robot2/amcl_pose',
                                 lambda m: setattr(self, 'pumpkin', m.pose.pose), POSE_QOS)
        self.pub = self.create_publisher(TargetObservation, '/tob/target/observation', OBS_QOS)
        self.create_timer(0.1, self.tick)
        self.last = None

    def visible(self):
        """(보이는지, 거리, 사유)"""
        if self.boo is None or self.pumpkin is None:
            return False, float('nan'), '위치 없음'
        b, p = self.boo.position, self.pumpkin.position
        dx, dy = p.x - b.x, p.y - b.y
        dist = math.hypot(dx, dy)
        if dist > self.args.range:
            return False, dist, '거리 초과'
        off = math.degrees(abs(math.atan2(math.sin(math.atan2(dy, dx) - yaw_of(self.boo.orientation)),
                                          math.cos(math.atan2(dy, dx) - yaw_of(self.boo.orientation)))))
        if off > self.args.hfov / 2:
            return False, dist, '시야각 밖'
        if self.grid.blocked((b.x, b.y), (p.x, p.y)):
            return False, dist, '벽에 가림'
        return True, dist, '보임'

    def tick(self):
        seen, dist, why = self.visible()
        msg = TargetObservation()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.source = 'boo_camera'
        if seen:
            msg.detected = True
            msg.map_valid = True
            msg.confidence = 0.9
            msg.distance_m = float(dist)
            msg.target_position = PointStamped()
            msg.target_position.header = msg.header
            msg.target_position.point.x = self.pumpkin.position.x
            msg.target_position.point.y = self.pumpkin.position.y
        self.pub.publish(msg)
        if why != self.last:
            self.get_logger().info(f'{why} (거리 {dist:.2f} m)')
            self.last = why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--range', type=float, default=2.5, help='탐지 거리 상한[m]')
    ap.add_argument('--hfov', type=float, default=69.0, help='카메라 수평 화각[deg]')
    ap.add_argument('--map', default='/home/mu-01/Trick_or_Bot/backend/maps/holloween_boo.yaml')
    ap.add_argument('--sim-time', action='store_true')
    args = ap.parse_args()
    rclpy.init(args=['--ros-args', '-p', f'use_sim_time:={str(args.sim_time).lower()}'])
    node = FakeDetector(args)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
