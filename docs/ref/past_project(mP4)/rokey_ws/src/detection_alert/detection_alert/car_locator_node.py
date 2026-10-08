"""car_locator node: 웹캠 검출 bbox → car의 map 좌표.

webcam_detector의 /webcam/detections(JSON)를 받아, '내 차' bbox의 아래쪽 가운데(바퀴가 바닥에 닿는 점)를
원본 영상 pixel로 되돌린 뒤(bbox + crop_offset) homography로 map (x, y)로 바꾼다.
내 차 = detections의 my_id(track ID)와 같은 검출. my_id가 없는 옛 메시지는 confidence 최고 car.

subscribe
  /webcam/detections        std_msgs/String (webcam_detector)
publish
  /webcam/car_point_raw     geometry_msgs/PointStamped (frame map)  car가 보이는 매 프레임. RViz 확인용
  /webcam/car_point         geometry_msgs/PointStamped (frame map)  AMR(goto_car)에 보내는 목표
      - car 알림(car_alert)이 켜진 동안 보냄: 처음 위치 / 이동 확정 시(move_judge.MoveJudge) /
        이동 중 마지막으로 보낸 위치에서 resend_dist 넘게 더 갔을 때
      - car가 멈추면 멈춘 위치(stop_sec 동안의 평균)를 한 번 더 보냄 (stop_tol 넘게 차이 날 때)
      - 이동 판단은 시간 기준(처리 주기와 무관): 기준 위치에서 최근 avg_sec 평균이 resend_dist 이상 벗어난
        상태가 hold_sec 이상 계속될 때만 이동. 그보다 짧은 튐은 노이즈로 무시
      - require_stop:=true 이면 car가 stop_sec 동안 stop_tol 안에 머물렀을 때만 보냄
      - QoS transient_local: goto_car를 나중에 켜도 마지막 좌표를 바로 받음

parameter (--ros-args -p 이름:=값)
  homography     보정 파일 경로 (기본: src/detection_alert/config/homography.yaml)
  target_class   car
  require_stop   false
  stop_sec       1.0   멈춤 판단 시간(초)
  stop_tol       0.05  멈춤 판단 허용 이동(m)
  resend_dist    0.3   이만큼 움직이면 이동으로 보고 car_point를 다시 보냄(m)
  avg_sec        0.5   이동 판단에 쓰는 최근 평균 구간(초)
  hold_sec       0.2   이동 판단이 이 시간(초) 이상 계속돼야 이동으로 확정

사용법:
  ros2 run detection_alert car_locator [--ros-args -p require_stop:=true]
"""
import json
import math

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from detection_alert import homography as hg
from detection_alert.move_judge import MoveJudge

LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)


class CarLocator(Node):
    def __init__(self):
        super().__init__('car_locator')
        path = self.declare_parameter('homography', str(hg.default_path())).value
        self.target = self.declare_parameter('target_class', 'car').value
        self.require_stop = self.declare_parameter('require_stop', False).value
        self.stop_sec = self.declare_parameter('stop_sec', 1.0).value
        self.stop_tol = self.declare_parameter('stop_tol', 0.05).value
        self.resend_dist = self.declare_parameter('resend_dist', 0.3).value
        avg_sec = self.declare_parameter('avg_sec', 0.5).value
        hold_sec = self.declare_parameter('hold_sec', 0.2).value

        cal = hg.load(path)
        self.H = cal['H']
        self.cal_w, self.cal_h = cal['image_size']
        # 보정점들이 둘러싼 영역. 이 밖은 외삽이라 오차가 커질 수 있음
        self.hull = cv2.convexHull(np.array(cal['pixel_points'], np.float32))
        res = cal.get('residual_m') or [0.0]
        self.get_logger().info(
            f"homography: {path} ({cal.get('created', '?')}, 점 {len(cal['pixel_points'])}개, "
            f"잔차 최대 {max(res):.3f} m)")

        self.create_subscription(String, '/webcam/detections', self.on_detections, 10)
        self.raw_pub = self.create_publisher(PointStamped, '/webcam/car_point_raw', 10)
        self.point_pub = self.create_publisher(PointStamped, '/webcam/car_point', LATCHED)

        self.judge = MoveJudge(self.stop_sec, self.stop_tol, avg_sec, self.resend_dist, hold_sec)
        self.sent = None         # 마지막으로 보낸 (x, y)
        self.was_stopped = False
        self.n_sent = 0
        self.last = None         # 상태 log용 (x, y, inside, stopped)
        self.create_timer(2.0, self.log_status)
        self.get_logger().info(
            f'target={self.target}, require_stop={self.require_stop}, '
            f'stop={self.stop_sec}s/{self.stop_tol}m, move={self.resend_dist}m '
            f'(최근 {avg_sec}s 평균, {hold_sec}s 이상)')

    def to_map(self, d, msg):
        """검출 1개의 아래쪽 가운데 pixel → map (x, y), 보정 영역 안인지 여부."""
        x1, y1, x2, y2 = d['bbox']
        ox, oy = msg.get('crop_offset', [0, 0])
        u, v = (x1 + x2) / 2 + ox, y2 + oy  # bbox는 crop한 정사각형 기준 (webcam_detector가 640→crop 크기로 되돌려 보냄)
        # 보정 영상과 검출 영상의 원본 해상도가 다르면 비율로 맞춤
        sw, sh = msg.get('src_w', self.cal_w), msg.get('src_h', self.cal_h)
        u, v = u * self.cal_w / sw, v * self.cal_h / sh
        inside = cv2.pointPolygonTest(self.hull, (float(u), float(v)), False) >= 0
        x, y = hg.pixel_to_map(self.H, u, v)
        return float(x), float(y), inside

    def make_point(self, x, y, stamp):
        p = PointStamped()
        p.header.frame_id = 'map'
        p.header.stamp = stamp
        p.point.x, p.point.y = x, y
        return p

    def pick_car(self, data):
        """내 차 검출 1개. my_id와 같은 track ID를 우선, 없으면 mine인 것 중 confidence 최고."""
        cars = [d for d in data['detections'] if d['class'] == self.target and d.get('mine', True)]
        my_id = data.get('my_id')
        same = [d for d in cars if my_id is not None and d.get('track_id') == my_id]
        return (same or cars or [None])[0]

    def on_detections(self, msg):
        data = json.loads(msg.data)
        if not data.get('car_alert'):
            self.judge.reset()
            self.last = None
            self.was_stopped = False
            return
        car = self.pick_car(data)
        if car is None:  # 알림은 켜져 있고 이번 프레임만 못 봄 (순간 미검출): 기록을 지우지 않고 넘어감
            return
        x, y, inside = self.to_map(car, data)
        now = self.get_clock().now()
        stamp = now.to_msg()
        self.raw_pub.publish(self.make_point(x, y, stamp))

        self.judge.update(now.nanoseconds / 1e9, x, y)
        stopped, moving, pos = self.judge.stopped, self.judge.moving, self.judge.pos
        self.last = (x, y, inside, stopped)
        just_stopped = stopped and not self.was_stopped
        self.was_stopped = stopped

        if self.require_stop and not stopped:
            return
        if self.sent is None:
            send = True                                              # 처음 위치
        elif moving:                                                 # 이동 확정 후 resend_dist 넘게 더 감
            send = math.dist(self.sent, pos) >= self.resend_dist
        else:                                                        # 멈춤: 멈춘 위치가 마지막 전송과 다르면
            send = just_stopped and math.dist(self.sent, pos) > self.stop_tol
        if send:
            gx, gy = pos if (stopped or moving) else (x, y)
            self.point_pub.publish(self.make_point(gx, gy, stamp))
            self.n_sent += 1
            self.get_logger().warn(
                f"📍 car_point #{self.n_sent}: x={gx:.2f} y={gy:.2f} "
                f"({'멈춤' if stopped else '이동 중' if moving else '처음'}{'' if inside else ', ⚠️ 보정 영역 밖'})")
            self.sent = (gx, gy)

    def log_status(self):
        if self.last is None:
            self.get_logger().info(f'car 없음 (보낸 car_point {self.n_sent}개)')
        else:
            x, y, inside, stopped = self.last
            self.get_logger().info(
                f"car x={x:.2f} y={y:.2f} {'멈춤' if stopped else '이동 중'}"
                f"{'' if inside else ' ⚠️ 보정 영역 밖'} (보낸 car_point {self.n_sent}개)")


def main():
    rclpy.init()
    try:
        node = CarLocator()
    except FileNotFoundError as e:
        print(f'❌ 보정 파일 없음: {e.filename}\n   먼저 calib_homography로 보정할 것 (guidance_6)')
        rclpy.shutdown()
        return
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
