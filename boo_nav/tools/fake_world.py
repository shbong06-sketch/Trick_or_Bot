#!/usr/bin/env python3
"""boo_controller_node 모의 시험: 가짜 Nav2 서버 + 시나리오 발행 + BooState 검사.

Gazebo 없이 컨트롤러의 상태 전환·목표 전송·취소를 확인한다.
먼저 다른 터미널에서 컨트롤러를 띄운다(네임스페이스 robot1):
  ros2 run tob_control boo_controller_node --ros-args -r __ns:=/robot1 \
    --params-file <control.yaml> -p suspicion_fill_s:=1.0 -p lost_timeout_s:=0.8
그다음 이 스크립트를 실행한다. 모든 검사가 통과하면 종료 코드 0.
"""
import math
import sys
import time

import rclpy
from geometry_msgs.msg import PointStamped, PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from tob_interfaces.msg import BooState, GameState, SafetyState, TargetObservation

QOS = QoSProfile(depth=1, reliability=QoSReliabilityPolicy.RELIABLE)
NAMES = {0: 'IDLE', 1: 'PATROL', 2: 'SUSPECT', 3: 'CHASE', 4: 'SEARCH'}


class FakeWorld(Node):
    def __init__(self):
        super().__init__('fake_world')
        cb = ReentrantCallbackGroup()
        self.pos = [0.0, 0.0]
        self.speed = 1.0                      # 가짜 로봇 속도 [m/s]
        self.goals = []                       # (시각, x, y, 결과)
        self.cancel_count = 0
        self.server = ActionServer(
            self, NavigateToPose, '/robot1/navigate_to_pose', self._execute,
            goal_callback=lambda g: GoalResponse.ACCEPT,
            cancel_callback=self._on_cancel, callback_group=cb)
        self.game_pub = self.create_publisher(GameState, '/tob/game/state', QOS)
        self.safe_pub = self.create_publisher(SafetyState, '/tob/boo/safety', QOS)
        self.obs_pub = self.create_publisher(TargetObservation, '/tob/target/observation', QOS)
        self.create_subscription(BooState, '/tob/boo/state', self._on_boo, QOS)
        self.boo = None
        self.history = []
        self.phase = GameState.RUNNING
        self.safe = True
        self.seen_at = None                   # None이면 관측 없음
        self.source = 'boo_camera'
        self.create_timer(0.1, self._publish)

    def _on_cancel(self, _goal):
        self.cancel_count += 1
        return CancelResponse.ACCEPT

    def _execute(self, handle):
        tx = handle.request.pose.pose.position.x
        ty = handle.request.pose.pose.position.y
        t0 = time.time()
        result = NavigateToPose.Result()
        while True:
            if handle.is_cancel_requested:
                handle.canceled()
                self.goals.append((t0, tx, ty, 'CANCELED'))
                return result
            dx, dy = tx - self.pos[0], ty - self.pos[1]
            dist = math.hypot(dx, dy)
            if dist < 0.1:
                handle.succeed()
                self.goals.append((t0, tx, ty, 'SUCCEEDED'))
                return result
            step = min(dist, self.speed * 0.1)
            self.pos[0] += dx / dist * step
            self.pos[1] += dy / dist * step
            fb = NavigateToPose.Feedback()
            fb.distance_remaining = float(dist)
            fb.current_pose = PoseStamped()
            fb.current_pose.pose.position.x, fb.current_pose.pose.position.y = self.pos
            handle.publish_feedback(fb)
            time.sleep(0.1)

    def _publish(self):
        now = self.get_clock().now().to_msg()
        game = GameState()
        game.phase = self.phase
        game.round_id = 'test'
        self.game_pub.publish(game)
        safe = SafetyState()
        safe.header.stamp = now
        safe.robot_id = 'boo'
        safe.motion_allowed = self.safe
        safe.valid_for_s = 1.0
        self.safe_pub.publish(safe)
        obs = TargetObservation()
        obs.header.stamp = now
        obs.source = self.source
        if self.seen_at is not None:
            obs.detected = True
            obs.map_valid = True
            obs.target_position = PointStamped()
            obs.target_position.header.frame_id = 'map'
            obs.target_position.point.x, obs.target_position.point.y = self.seen_at
        self.obs_pub.publish(obs)

    def _on_boo(self, msg):
        if self.boo is None or msg.behavior != self.boo.behavior:
            self.history.append((time.time(), NAMES[msg.behavior], msg.reason))
        self.boo = msg


def wait_until(node, cond, timeout, label):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if cond():
            print(f'  [OK] {label} ({time.time() - t0:.1f}s)')
            return True
        time.sleep(0.05)
    print(f'  [FAIL] {label}: {timeout}s 안에 만족하지 않음 (BooState={node.boo and NAMES[node.boo.behavior]})')
    return False


def main():
    rclpy.init()
    node = FakeWorld()
    ex = MultiThreadedExecutor(num_threads=4)
    ex.add_node(node)
    import threading
    threading.Thread(target=ex.spin, daemon=True).start()
    ok = True
    behavior = lambda: node.boo is not None and NAMES[node.boo.behavior]  # noqa: E731

    print('1) 게임 진행 + 안전 허용 → 순찰 시작')
    ok &= wait_until(node, lambda: behavior() == 'PATROL' and node.boo.goal_active, 8, 'PATROL, 목표 전송')
    ok &= wait_until(node, lambda: len([g for g in node.goals if g[3] == 'SUCCEEDED']) >= 2, 15,
                     '순찰 지점 2곳 도착')

    print('2) 펌킨 관측 → 의심 → 추격')
    node.seen_at = (1.0, 1.0)
    ok &= wait_until(node, lambda: behavior() == 'SUSPECT', 3, 'SUSPECT')
    ok &= wait_until(node, lambda: behavior() == 'CHASE', 5, 'CHASE (게이지 가득)')
    node.seen_at = (2.0, 1.5)
    ok &= wait_until(node, lambda: any(abs(g[1] - 2.0) < 0.3 and abs(g[2] - 1.5) < 0.3 for g in node.goals)
                     or node.boo.goal_active, 4, '움직인 목표로 교체/추격')

    print('3) 정지 거리 안에서 멈추기')
    ok &= wait_until(node, lambda: node.boo.target_visible and
                     math.hypot(node.pos[0] - 2.0, node.pos[1] - 1.5) < 0.6, 10, '목표 가까이 도착')
    time.sleep(1.0)
    ok &= wait_until(node, lambda: not node.boo.goal_active, 3, '정지 거리 안에서 목표 취소')

    print('4) 멀리서 관측을 놓침 → 마지막 위치로 수색 → 순찰 복귀')
    node.seen_at = (3.0, -1.0)
    ok &= wait_until(node, lambda: node.boo.goal_active and node.boo.target_visible, 3, '먼 목표로 추격')
    time.sleep(0.6)
    node.seen_at = None
    ok &= wait_until(node, lambda: behavior() == 'SEARCH', 4, 'SEARCH')
    ok &= wait_until(node, lambda: behavior() == 'PATROL', 20, 'PATROL 복귀')
    ok &= wait_until(node, lambda: node.boo.last_seen_valid, 1, '마지막 관측 위치 기억')

    print('5) 게임 일시정지 → 즉시 IDLE, 목표 취소')
    node.phase = GameState.PAUSED
    ok &= wait_until(node, lambda: behavior() == 'IDLE', 3, 'IDLE')
    ok &= wait_until(node, lambda: not node.boo.goal_active, 3, '목표 없음')
    node.phase = GameState.RUNNING
    ok &= wait_until(node, lambda: behavior() == 'PATROL', 5, '재개 후 PATROL')

    print('6) 안전 상태 불허 → IDLE')
    node.safe = False
    ok &= wait_until(node, lambda: behavior() == 'IDLE', 3, '안전 불허로 IDLE')
    node.safe = True
    ok &= wait_until(node, lambda: behavior() == 'PATROL', 5, '허용 복귀 후 PATROL')

    print('7) 허용하지 않은 출처(webcam)의 관측은 무시')
    node.source = 'webcam'
    node.seen_at = (1.0, 1.0)
    time.sleep(2.0)
    ok &= behavior() == 'PATROL'
    print(f'  [{"OK" if behavior() == "PATROL" else "FAIL"}] 출처 불일치 관측에 반응하지 않음 (BooState={behavior()})')
    node.source = 'boo_camera'
    node.seen_at = None

    print('\n상태 전환 기록:')
    t0 = node.history[0][0] if node.history else 0
    for t, name, why in node.history:
        print(f'  +{t - t0:5.1f}s {name:8s} {why}')
    print('Nav2 목표 기록(결과):', [(round(g[1], 1), round(g[2], 1), g[3]) for g in node.goals])
    print('\n결과:', '통과' if ok else '실패')
    rclpy.shutdown()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
