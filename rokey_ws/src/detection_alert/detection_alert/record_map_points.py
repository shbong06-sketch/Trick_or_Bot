"""보정점의 map 좌표를 기록한다. 두 가지 방법 중 하나를 쓴다.

1) 로봇 위치 (기본): 바닥 X 테이프 위에 로봇을 세우고 Enter
   teleop으로 로봇 중심을 X 테이프 위에 맞춘 뒤 Enter → 그 순간의 로봇 위치(map→base_link TF)를 저장.
   (로봇을 손으로 들어 옮기면 odom이 모르므로 위치가 틀어진다. 반드시 주행해서 옮길 것)
   amcl_pose 대신 TF를 쓰는 이유:
     amcl_pose는 로봇이 일정 거리(약 0.25m) 움직일 때만 갱신되어, 멈춘 위치와 최대 그만큼 어긋날 수 있다.
     TF map→base_link는 마지막 AMCL 보정 + 그 뒤 odom 이동까지 반영한 현재 위치다.

2) RViz 클릭 (--clicked): 로봇 없이, 맵에 보이는 벽 모서리 등을 RViz Publish Point로 클릭
   클릭할 때마다 /clicked_point 좌표를 저장. 웹캠 화면에서도 같은 점(벽과 바닥이 만나는 꼭짓점)을 찾을 수 있어야 한다.

사용법:
  ros2 run detection_alert record_map_points [--ns /robot1] [--out <yaml>]
  ros2 run detection_alert record_map_points --clicked [--topic /clicked_point] [--out <yaml>]
  (로봇 위치) Enter: 기록 / (공통) u + Enter: 마지막 점 취소 / q + Enter: 끝
결과: map_points.yaml (calib_homography --points 로 넘긴다)
"""
import argparse
import math
import threading
from pathlib import Path

import rclpy
import yaml
from geometry_msgs.msg import PointStamped
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener

from detection_alert.homography import config_dir


class PoseReader(Node):
    def __init__(self, ns):
        ns = '/' + ns.strip('/') if ns.strip('/') else ''
        # TurtleBot4는 tf를 /<ns>/tf 로 publish → 이 node의 /tf 구독만 remap
        super().__init__('record_map_points', cli_args=[
            '--ros-args', '-r', f'/tf:={ns}/tf', '-r', f'/tf_static:={ns}/tf_static'])
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)

    def current(self):
        """(x, y, yaw_deg) 또는 None."""
        try:
            t = self.buffer.lookup_transform('map', 'base_link', Time())
        except Exception as e:
            self.get_logger().warn(f'map→base_link TF 없음: {e}')
            return None
        q = t.transform.rotation
        yaw = math.degrees(math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z)))
        return t.transform.translation.x, t.transform.translation.y, yaw


class ClickReader(Node):
    """RViz Publish Point(/clicked_point)를 받을 때마다 점을 추가한다."""

    def __init__(self, topic, points, on_change):
        super().__init__('record_map_points')
        self.points = points
        self.on_change = on_change
        self.lock = threading.Lock()
        self.create_subscription(PointStamped, topic, self.on_click, 10)

    def on_click(self, msg):
        if msg.header.frame_id not in ('map', '/map'):
            print(f'  ⚠️ frame이 {msg.header.frame_id}: RViz Fixed Frame을 map으로 할 것 (무시함)', flush=True)
            return
        with self.lock:
            self.points.append((msg.point.x, msg.point.y))
            self.on_change(f'  ✅ {len(self.points)}번: x={msg.point.x:.3f} y={msg.point.y:.3f} → 저장됨')


def spin(node):
    try:
        rclpy.spin(node)
    except ExternalShutdownException:  # Ctrl+C
        pass


def save(path, points, how):
    body = yaml.safe_dump({'map_points': [[round(x, 4), round(y, 4)] for x, y in points]},
                          default_flow_style=None)
    Path(path).write_text(f'# 보정점의 map 좌표 ({how}). 순서 = calib_homography에서 클릭할 순서\n' + body)


def main():
    parser = argparse.ArgumentParser(description='보정점의 map 좌표를 로봇 위치(TF) 또는 RViz 클릭으로 기록')
    parser.add_argument('--clicked', action='store_true', help='로봇 대신 RViz Publish Point 클릭을 기록')
    parser.add_argument('--topic', default='/clicked_point', help='--clicked 일 때 받을 topic')
    parser.add_argument('--ns', default='/robot1', help='로봇 namespace (로봇 위치 방식)')
    parser.add_argument('--out', default=str(config_dir() / 'map_points.yaml'), help='저장할 yaml')
    args, ros_args = parser.parse_known_args()

    rclpy.init(args=ros_args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    points = []
    how = 'RViz 클릭' if args.clicked else '로봇 중심 위치'

    def changed(msg):
        save(args.out, points, how)
        print(msg, flush=True)

    if args.clicked:
        node = ClickReader(args.topic, points, changed)
    else:
        node = PoseReader(args.ns)
    spinner = threading.Thread(target=spin, args=(node,), daemon=True)
    spinner.start()

    print(f'저장 위치: {args.out}')
    if args.clicked:
        print(f'RViz 상단 Publish Point → 맵 위 보정점을 순서대로 클릭 ({args.topic})')
    try:
        while True:
            if args.clicked:
                cmd = input('\n(클릭은 RViz에서) u: 마지막 점 취소, q: 끝 > ').strip().lower()
            else:
                cmd = input(f'\n로봇을 X {len(points) + 1}번 위에 맞추고 Enter (u: 취소, q: 끝) > ').strip().lower()
            if cmd == 'q':
                break
            if cmd == 'u':
                if points:
                    changed(f'  {len(points)}번 취소: {points.pop()}')
                continue
            if args.clicked:
                continue
            pose = node.current()
            if pose is None:
                print('  ❌ 위치를 못 읽음: localization이 켜져 있고 --ns가 맞는지 확인')
                continue
            x, y, yaw = pose
            points.append((x, y))
            changed(f'  ✅ {len(points)}번: x={x:.3f} y={y:.3f} (yaw {yaw:.0f}°) → 저장됨')
    except (KeyboardInterrupt, EOFError):
        pass
    print(f'\n총 {len(points)}개 저장: {args.out}')
    if len(points) < 6:
        print('⚠️  6개 이상 권장 (적으면 잘못 찍은 점을 잡기 어려움)')
    # spin 스레드를 먼저 멈춘 뒤 node를 정리 (반대로 하면 종료 때 abort)
    rclpy.try_shutdown()
    spinner.join(timeout=2.0)
    node.destroy_node()


if __name__ == '__main__':
    main()
