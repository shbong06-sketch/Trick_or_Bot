#!/usr/bin/env python3
"""Boo 행동 상태와 두 로봇 위치를 벽시계 시각과 함께 CSV로 기록한다(영상 자막·지도 그림용).

[입출력] 입력: /tob/boo/state, /robot1/amcl_pose(Boo), /robot2/amcl_pose(Pumpkin).
         출력: 인자로 받은 CSV 파일 (time_unix, behavior, reason, boo_x, boo_y, pum_x, pum_y, gap_m), 10 Hz.
[사용] python3 boo_nav/tools/state_logger.py <csv 경로> [--seconds N]
"""
import argparse
import csv
import math
import time

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from tob_interfaces.msg import BooState

NAMES = {0: 'IDLE', 1: 'PATROL', 2: 'SUSPECT', 3: 'CHASE', 4: 'SEARCH'}


class StateLogger(Node):
    """Boo 행동 상태와 두 로봇 위치를 모아 10 Hz로 CSV에 한 줄씩 쓰는 노드. 시뮬레이션 시계를 쓴다."""

    def __init__(self, path: str):
        super().__init__('state_logger', parameter_overrides=[
            rclpy.parameter.Parameter('use_sim_time', value=True)])
        self.boo = self.pum = None   # 두 로봇의 최신 (x, y). 둘 다 받기 전에는 줄을 쓰지 않는다
        self.state = ('', '')        # (행동 이름, 사유)
        self.file = open(path, 'w', newline='')
        self.csv = csv.writer(self.file)
        self.csv.writerow(['time_unix', 'behavior', 'reason', 'boo_x', 'boo_y', 'pum_x', 'pum_y', 'gap_m'])
        self.create_subscription(BooState, '/tob/boo/state', self._on_state,
                                 QoSProfile(depth=1, reliability=QoSReliabilityPolicy.RELIABLE))
        self.create_subscription(PoseWithCovarianceStamped, '/robot1/amcl_pose', self._on_boo, 10)
        self.create_subscription(PoseWithCovarianceStamped, '/robot2/amcl_pose', self._on_pum, 10)
        self.create_timer(0.1, self._tick)

    # 아래 세 콜백은 최신 값만 저장하고, 기록은 _tick이 한다.
    def _on_state(self, m):
        self.state = (NAMES.get(m.behavior, str(m.behavior)), m.reason)

    def _on_boo(self, m):
        self.boo = (m.pose.pose.position.x, m.pose.pose.position.y)

    def _on_pum(self, m):
        self.pum = (m.pose.pose.position.x, m.pose.pose.position.y)

    def _tick(self):
        """0.1초마다 CSV 한 줄(시각, 행동, 사유, 두 로봇 위치, 사이 거리)을 쓰고 즉시 저장한다."""
        if self.boo is None or self.pum is None:
            return
        gap = math.hypot(self.boo[0] - self.pum[0], self.boo[1] - self.pum[1])
        self.csv.writerow([f'{time.time():.3f}', self.state[0], self.state[1],
                           f'{self.boo[0]:.3f}', f'{self.boo[1]:.3f}',
                           f'{self.pum[0]:.3f}', f'{self.pum[1]:.3f}', f'{gap:.3f}'])
        self.file.flush()


def main():
    """인자: CSV 경로, --seconds(0이면 Ctrl+C까지 기록)."""
    ap = argparse.ArgumentParser()
    ap.add_argument('csv')
    ap.add_argument('--seconds', type=float, default=0.0)
    a = ap.parse_args()
    rclpy.init()
    node = StateLogger(a.csv)
    end = time.time() + a.seconds if a.seconds else None
    try:
        while rclpy.ok() and (end is None or time.time() < end):
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
