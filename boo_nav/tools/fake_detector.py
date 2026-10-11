#!/usr/bin/env python3
"""가짜 펌킨 탐지기: 펌킨(로봇2)의 위치를 따라가며 Boo의 카메라가 볼 수 있을 때만 관측을 발행한다.

[역할]
실제 탐지·위치 계산 노드(tob_perception, tob_localization)가 준비되기 전에 Boo 추격을 시험한다.
탐지 담당 팀원의 설명(2026-10-11)에 맞춰, 사이에 시야를 막는 장애물이 없으면 지도 끝에서도 보인다고 본다.
[입출력]
입력: /robot1/amcl_pose(Boo 위치), /robot2/amcl_pose(펌킨 위치). 펌킨은 teleop이나 pumpkin_scenario.py로 움직인다.
출력: /tob/target/observation (TargetObservation, source=boo_camera, 10 Hz).
[보이는 조건(모두 만족)]
 ① 거리: 기본은 제한 없음. --range <m>을 주면 그 거리까지만 본다(0이면 제한 없음).
 ② 시야각: 펌킨이 Boo 정면 수평 --hfov도(기본 69°, OAK-D RGB 수평 화각) 안에 있다.
 ③ 가림: 두 로봇 사이를 지도(holloween_boo)의 벽이 가리지 않는다.
[출력 값]
보이면 detected=true, map_valid=true, confidence=--conf(기본 0.7, 탐지 담당 팀원이 말한 값),
펌킨의 지도 위치, 거리. 안 보이면 detected=false, map_valid=false.
[범위]
카메라 영상·YOLO·좌표 변환을 흉내 내지 않는다. 위치는 AMCL 값 그대로이고 잡음을 넣지 않는다.
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
    """지도(pgm+yaml)에서 두 점 사이를 벽이 가리는지 검사한다.

    지도 그림에서 검은 칸(밝기 50 미만)을 벽으로 본다. 지도 밖도 막힌 것으로 본다.
    """

    def __init__(self, yaml_path):
        meta = yaml.safe_load(open(yaml_path, encoding='utf-8'))
        img = Image.open(yaml_path.rsplit('/', 1)[0] + '/' + meta['image'])
        self.occ = np.array(img) < 50          # 검은 칸 = 벽
        self.res = float(meta['resolution'])
        self.ox, self.oy = float(meta['origin'][0]), float(meta['origin'][1])
        self.h = self.occ.shape[0]

    def blocked(self, a, b):
        """지도 좌표 a에서 b까지 직선이 벽을 지나면 True. 직선을 지도 한 칸의 절반 간격으로 따라가며 검사한다."""
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
    """쿼터니언 q의 바라보는 방향(yaw, 라디안)."""
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


class FakeDetector(Node):
    """Boo·펌킨 위치로 "보이는지"를 판단해 10 Hz로 관측을 발행하는 노드."""

    def __init__(self, args):
        super().__init__('fake_detector')
        self.args = args
        self.grid = Grid(args.map)
        self.boo = None        # Boo의 최신 지도 위치(AMCL). 아직 못 받았으면 None
        self.pumpkin = None    # 펌킨의 최신 지도 위치(AMCL)
        self.create_subscription(PoseWithCovarianceStamped, '/robot1/amcl_pose',
                                 lambda m: setattr(self, 'boo', m.pose.pose), POSE_QOS)
        self.create_subscription(PoseWithCovarianceStamped, '/robot2/amcl_pose',
                                 lambda m: setattr(self, 'pumpkin', m.pose.pose), POSE_QOS)
        self.pub = self.create_publisher(TargetObservation, '/tob/target/observation', OBS_QOS)
        self.create_timer(0.1, self.tick)
        self.last = None       # 마지막으로 로그에 남긴 사유(바뀔 때만 로그를 남기기 위함)

    def visible(self):
        """(보이는지, Boo–펌킨 거리[m], 사유 문구)를 돌려준다. 위치를 아직 모르면 거리는 nan."""
        if self.boo is None or self.pumpkin is None:
            return False, float('nan'), '위치 없음'
        b, p = self.boo.position, self.pumpkin.position
        dx, dy = p.x - b.x, p.y - b.y
        dist = math.hypot(dx, dy)
        if self.args.range > 0 and dist > self.args.range:   # --range 0이면 거리 제한 없음
            return False, dist, '거리 초과'
        # 펌킨 방향과 Boo 정면 방향의 차이(-180~180도로 정리한 절댓값)
        off = math.degrees(abs(math.atan2(math.sin(math.atan2(dy, dx) - yaw_of(self.boo.orientation)),
                                          math.cos(math.atan2(dy, dx) - yaw_of(self.boo.orientation)))))
        if off > self.args.hfov / 2:
            return False, dist, '시야각 밖'
        if self.grid.blocked((b.x, b.y), (p.x, p.y)):
            return False, dist, '벽에 가림'
        return True, dist, '보임'

    def tick(self):
        """0.1초마다 보이는지 판단해 관측을 발행하고, 사유가 바뀌면 로그를 남긴다."""
        seen, dist, why = self.visible()
        msg = TargetObservation()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.source = 'boo_camera'
        if seen:
            msg.detected = True
            msg.map_valid = True
            msg.confidence = self.args.conf
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
    ap.add_argument('--range', type=float, default=0.0,
                    help='탐지 거리 상한[m]. 0이면 제한 없음(기본, 탐지 담당 팀원 설명에 따름)')
    ap.add_argument('--conf', type=float, default=0.7, help='보일 때 발행할 신뢰도(기본 0.7)')
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
