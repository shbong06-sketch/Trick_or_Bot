"""웹캠 car 좌표(car_locator) 오차 측정: RViz에서 car 위치를 클릭한 좌표와 비교한다.

RViz Publish Point로 car 중심을 클릭할 때마다
  - 직전 window초 동안의 /webcam/car_point_raw 평균(웹캠 추정값)과
  - 클릭 좌표(/clicked_point, 기준값)
의 차이를 CSV에 한 줄씩 기록한다. 끝(q 또는 Ctrl+C)에 요약을 출력한다.

요약 항목
  오차 평균·최대·RMSE   : 웹캠 추정 위치와 클릭 위치의 거리(m)
  bias (dx, dy 평균)    : 오차가 한쪽으로 쏠린 정도. car_locator는 bbox 아래쪽 가운데(카메라 쪽 바퀴 끝)를 쓰므로
                          car 중심을 클릭하면 카메라 쪽으로 일정하게 쏠릴 수 있다
  bias 뺀 오차 평균      : 쏠림을 보정했을 때 남는 오차

사용법:
  ros2 run detection_alert eval_car_point --out <csv> [--window 1.0]
  u + Enter: 마지막 기록 취소 / q + Enter: 끝
"""
import argparse
import csv
import math
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

FIELDS = ['no', 'time', 'click_x', 'click_y', 'est_x', 'est_y', 'dx', 'dy', 'err_m', 'n_samples', 'est_std_m']


class EvalNode(Node):
    def __init__(self, window, est_topic, click_topic, on_row):
        super().__init__('eval_car_point')
        self.window = window
        self.on_row = on_row
        self.samples = deque()   # (수신 시각, x, y)
        self.lock = threading.Lock()
        self.create_subscription(PointStamped, est_topic, self.on_est, 10)
        self.create_subscription(PointStamped, click_topic, self.on_click, 10)
        self.last_warn = 0.0

    def on_est(self, msg):
        now = time.monotonic()
        with self.lock:
            self.samples.append((now, msg.point.x, msg.point.y))
            while self.samples and now - self.samples[0][0] > 10.0:
                self.samples.popleft()

    def on_click(self, msg):
        if msg.header.frame_id not in ('map', '/map'):
            print(f'  ⚠️ frame이 {msg.header.frame_id}: RViz Fixed Frame을 map으로 할 것 (무시함)', flush=True)
            return
        now = time.monotonic()
        with self.lock:
            recent = np.array([[x, y] for t, x, y in self.samples if now - t <= self.window])
        if len(recent) == 0:
            print(f'  ❌ 최근 {self.window}초 동안 웹캠 car 추정값 없음: car가 검출 영역(화면 가운데) 안에 있고 '
                  f'car_locator가 켜져 있는지 확인 (무시함)', flush=True)
            return
        est = recent.mean(0)
        std = float(np.linalg.norm(recent - est, axis=1).mean())
        self.on_row(msg.point.x, msg.point.y, float(est[0]), float(est[1]), len(recent), std)


def spin(node):
    try:
        rclpy.spin(node)
    except ExternalShutdownException:  # Ctrl+C
        pass


def summary(rows):
    if not rows:
        return '기록 없음'
    d = np.array([[r['dx'], r['dy']] for r in rows])
    e = np.linalg.norm(d, axis=1)
    bias = d.mean(0)
    e_nb = np.linalg.norm(d - bias, axis=1)
    return (f'측정 {len(rows)}회\n'
            f'  오차 평균 {e.mean():.3f} m / 최대 {e.max():.3f} m / RMSE {math.sqrt((e ** 2).mean()):.3f} m\n'
            f'  bias (dx, dy 평균) = ({bias[0]:+.3f}, {bias[1]:+.3f}) m, 크기 {np.linalg.norm(bias):.3f} m\n'
            f'  bias 뺀 오차 평균 {e_nb.mean():.3f} m / 최대 {e_nb.max():.3f} m')


def main():
    parser = argparse.ArgumentParser(description='웹캠 car 좌표와 RViz 클릭 좌표의 오차 측정')
    parser.add_argument('--out', default=f'eval_car_point_{datetime.now():%y%m%d_%H%M%S}.csv', help='저장할 csv')
    parser.add_argument('--window', type=float, default=1.0, help='클릭 직전 몇 초의 웹캠 추정값을 평균할지')
    parser.add_argument('--est-topic', default='/webcam/car_point_raw')
    parser.add_argument('--click-topic', default='/clicked_point')
    args, ros_args = parser.parse_known_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    def write():
        with out.open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)

    def on_row(cx, cy, ex, ey, n, std):
        dx, dy = ex - cx, ey - cy
        rows.append({'no': len(rows) + 1, 'time': datetime.now().strftime('%H:%M:%S'),
                     'click_x': round(cx, 4), 'click_y': round(cy, 4),
                     'est_x': round(ex, 4), 'est_y': round(ey, 4),
                     'dx': round(dx, 4), 'dy': round(dy, 4), 'err_m': round(math.hypot(dx, dy), 4),
                     'n_samples': n, 'est_std_m': round(std, 4)})
        write()
        r = rows[-1]
        print(f"  ✅ {r['no']}번: 클릭 ({cx:.2f}, {cy:.2f})  웹캠 ({ex:.2f}, {ey:.2f})  "
              f"오차 {r['err_m']:.3f} m (dx {dx:+.3f}, dy {dy:+.3f}, 웹캠 흔들림 {std:.3f} m, {n}개 평균)", flush=True)

    rclpy.init(args=ros_args)
    node = EvalNode(args.window, args.est_topic, args.click_topic, on_row)
    spinner = threading.Thread(target=spin, args=(node,), daemon=True)
    spinner.start()
    print(f'저장 위치: {out.resolve()}\n'
          f'car를 놓고 1~2초 기다린 뒤 RViz Publish Point로 car 중심을 클릭 ({args.click_topic})')
    try:
        while True:
            cmd = input('\n(클릭은 RViz에서) u: 마지막 기록 취소, q: 끝 > ').strip().lower()
            if cmd == 'q':
                break
            if cmd == 'u' and rows:
                print(f"  {rows.pop()['no']}번 취소", flush=True)
                write()
    except (KeyboardInterrupt, EOFError):
        pass
    print('\n' + summary(rows))
    print(f'csv: {out.resolve()}')
    # spin 스레드를 먼저 멈춘 뒤 node를 정리 (반대로 하면 종료 때 abort)
    rclpy.try_shutdown()
    spinner.join(timeout=2.0)
    node.destroy_node()


if __name__ == '__main__':
    main()
