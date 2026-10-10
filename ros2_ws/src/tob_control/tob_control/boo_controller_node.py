"""Boo 이동 전체 관리 노드: 관측·게임·안전 상태 → FSM → Nav2 목표.

[입출력]
입력: /tob/target/observation(TargetObservation), /tob/game/state(GameState),
      /tob/boo/safety(SafetyState).
출력: /tob/boo/state(BooState), Nav2 NavigateToPose 목표(노드 네임스페이스 기준).
[규칙]
- detected와 map_valid가 모두 참이고, 허용한 출처이며, 만료되지 않은 관측만 추격에 쓴다.
- 펌킨의 실제 위치(/tob/pumpkin/pose)는 구독하지 않는다. 추격 정보는 관측뿐이다.
- 게임이 RUNNING이 아니거나 이동이 허용되지 않으면 진행 중인 목표를 취소하고 IDLE로 둔다.
- 같은 목표를 매 주기 다시 보내지 않는다(목표가 goal_update_dist_m 이상 움직였을 때만 교체).
- 이동 실패·취소는 도착으로 취급하지 않는다(FSM에 실패/취소로 전달).
[범위]
게임 승패 판정, 경로 계획, 최종 안전 속도 처리는 하지 않는다.
"""

import math
from typing import Optional, Tuple

import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from tob_interfaces.msg import BooState, GameState, SafetyState, TargetObservation

from tob_control.boo_fsm import Behavior, BooFsm, CmdKind, FsmConfig, Point
from tob_control.nav2_client import Nav2Client, Nav2State

STATE_QOS = QoSProfile(depth=1, reliability=QoSReliabilityPolicy.RELIABLE)


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class BooControllerNode(Node):
    """Boo의 FSM 결정을 Nav2 목표로 실행하고 BooState를 발행한다."""

    def __init__(self) -> None:
        super().__init__('boo_controller')
        self._declare_params()
        p = self.get_parameter
        self._period = p('control_period_s').value
        self._obs_timeout = p('obs_timeout_s').value
        self._game_timeout = p('game_timeout_s').value
        self._sources = list(p('accepted_sources').value)
        self._update_dist = p('goal_update_dist_m').value
        self._min_interval = p('goal_min_interval_s').value
        self._standoff = p('chase_standoff_m').value
        self._need_game = p('require_game_state').value
        self._need_safety = p('require_safety').value
        self._frame = p('frame_id').value

        xy = list(p('patrol_points_xy').value)
        points = [(xy[i], xy[i + 1]) for i in range(0, len(xy) - 1, 2)]
        cfg = FsmConfig(
            suspicion_fill_s=p('suspicion_fill_s').value,
            suspicion_decay_s=p('suspicion_decay_s').value,
            lost_timeout_s=p('lost_timeout_s').value,
            search_hold_s=p('search_hold_s').value,
            search_timeout_s=p('search_timeout_s').value,
            max_goal_failures=p('max_goal_failures').value,
            failure_hold_s=p('failure_hold_s').value,
            suspect_hold=p('suspect_hold').value)
        self._fsm = BooFsm(cfg, points)
        self._nav = Nav2Client(self, p('nav2_action').value, self._frame, self._on_nav_result)

        self._obs: Optional[TargetObservation] = None
        self._obs_rx = None
        self._game: Optional[GameState] = None
        self._game_rx = None
        self._safety: Optional[SafetyState] = None
        self._safety_rx = None

        self._last_target: Optional[Point] = None   # 마지막으로 Nav2에 보낸 목표
        self._last_send = None
        self._last_fail = False                      # 마지막 목표가 실패·거절·서버없음으로 끝남
        self._hold: Optional[Point] = None           # 추격 정지 거리 안이라 멈춘 목표
        self._prev_behavior = Behavior.IDLE
        self._last_tick = self.get_clock().now()

        self.create_subscription(TargetObservation, '/tob/target/observation',
                                 self._on_obs, STATE_QOS)
        self.create_subscription(GameState, '/tob/game/state', self._on_game, STATE_QOS)
        self.create_subscription(SafetyState, '/tob/boo/safety', self._on_safety, STATE_QOS)
        self._state_pub = self.create_publisher(BooState, '/tob/boo/state', STATE_QOS)
        self.create_timer(self._period, self._tick)
        self.get_logger().info(
            f'boo_controller 시작: 순찰 지점 {len(points)}개, 게임 상태 필요={self._need_game}, '
            f'안전 상태 필요={self._need_safety}')

    # ---- 파라미터 ----
    def _declare_params(self) -> None:
        defaults = {
            'control_period_s': 0.1,
            'obs_timeout_s': 0.5,
            'game_timeout_s': 2.0,
            'accepted_sources': ['boo_camera'],
            'goal_update_dist_m': 0.2,
            'goal_min_interval_s': 0.5,
            'chase_standoff_m': 0.45,
            'require_game_state': True,
            'require_safety': True,
            'frame_id': 'map',
            'nav2_action': 'navigate_to_pose',
            'patrol_points_xy': [0.0, 0.0],
            'suspicion_fill_s': 3.0,
            'suspicion_decay_s': 3.0,
            'lost_timeout_s': 1.0,
            'search_hold_s': 0.0,
            'search_timeout_s': 15.0,
            'max_goal_failures': 3,
            'failure_hold_s': 5.0,
            'suspect_hold': True,
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value)

    # ---- 구독 콜백 ----
    def _on_obs(self, msg: TargetObservation) -> None:
        self._obs, self._obs_rx = msg, self.get_clock().now()

    def _on_game(self, msg: GameState) -> None:
        self._game, self._game_rx = msg, self.get_clock().now()

    def _on_safety(self, msg: SafetyState) -> None:
        self._safety, self._safety_rx = msg, self.get_clock().now()

    # ---- 유효성 ----
    def _age_s(self, rx_time, header_stamp=None) -> float:
        """수신 경과 시간과 메시지 원본 시각 경과 중 큰 값."""
        now = self.get_clock().now()
        age = (now - rx_time).nanoseconds / 1e9
        if header_stamp is not None and (header_stamp.sec or header_stamp.nanosec):
            stamp_age = (now - rclpy.time.Time.from_msg(header_stamp)).nanoseconds / 1e9
            age = max(age, stamp_age)
        return age

    def _seen_point(self) -> Optional[Point]:
        """유효한 직접 관측이면 지도 좌표, 아니면 None."""
        obs = self._obs
        if obs is None or not (obs.detected and obs.map_valid):
            return None
        if obs.source not in self._sources:
            return None
        frame = obs.target_position.header.frame_id
        if frame and frame != self._frame:
            return None
        x, y = obs.target_position.point.x, obs.target_position.point.y
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        if self._age_s(self._obs_rx, obs.header.stamp) > self._obs_timeout:
            return None
        return (x, y)

    def _game_running(self) -> bool:
        if not self._need_game:
            return True
        if self._game is None or self._age_s(self._game_rx) > self._game_timeout:
            return False
        return self._game.phase == GameState.RUNNING

    def _motion_allowed(self) -> bool:
        if not self._need_safety:
            return True
        msg = self._safety
        if msg is None or not msg.motion_allowed:
            return False
        return self._age_s(self._safety_rx, msg.header.stamp) <= msg.valid_for_s

    # ---- 주기 처리 ----
    def _tick(self) -> None:
        now = self.get_clock().now()
        dt = (now - self._last_tick).nanoseconds / 1e9
        self._last_tick = now
        enabled = self._game_running() and self._motion_allowed()
        self._fsm.set_enabled(enabled)
        if not enabled:
            self._cancel_goal(reason='이동 금지')
        seen = self._seen_point() if enabled else None

        cmd = self._fsm.step(dt, seen)
        if cmd.kind == CmdKind.STOP:
            self._cancel_goal(reason=cmd.reason)
        elif cmd.kind == CmdKind.GOTO and cmd.target is not None:
            self._maybe_send(cmd.target)
        self._check_standoff()

        if self._fsm.behavior != self._prev_behavior:
            self.get_logger().info(
                f'상태 {self._prev_behavior.name} → {self._fsm.behavior.name}: {self._fsm.reason}')
            self._prev_behavior = self._fsm.behavior
        self._publish_state(seen is not None)

    def _maybe_send(self, target: Point) -> None:
        if not self._nav.server_ready():
            return   # 서버가 준비되지 않은 상태를 이동 가능으로 취급하지 않는다(실패로도 세지 않는다)
        now = self.get_clock().now()
        moved = self._last_target is None or _dist(target, self._last_target) >= self._update_dist
        if self._hold is not None:
            if _dist(target, self._hold) < self._update_dist:
                if self._fsm.behavior == Behavior.SEARCH:
                    # 정지 거리 안에서 멈춘 자리가 곧 수색 지점이므로 도착으로 본다
                    self._hold = None
                    self._fsm.on_nav_result(success=True)
                return
            self._hold = None
        interval_ok = (self._last_send is None or
                       (now - self._last_send).nanoseconds / 1e9 >= self._min_interval)
        retry = self._last_fail and not self._nav.busy
        if not interval_ok or not (moved or retry):
            return
        self._last_fail = False
        self._last_target = target
        self._last_send = now
        self._nav.send_goal(target[0], target[1], self._goal_yaw(target))

    def _goal_yaw(self, target: Point) -> float:
        """현재 위치(Nav2 feedback)에서 목표를 바라보는 방향. 위치를 모르면 0."""
        pose = self._nav.current_pose
        if pose is None:
            return 0.0
        return math.atan2(target[1] - pose.pose.position.y, target[0] - pose.pose.position.x)

    def _check_standoff(self) -> None:
        """추격 중 경로상 남은 거리가 정지 거리 안이면 목표를 취소하고 그 자리에서 기다린다."""
        remaining = self._nav.remaining_m
        if (self._fsm.behavior == Behavior.CHASE and self._nav.busy and remaining is not None
                and remaining <= self._standoff and self._last_target is not None):
            self._hold = self._last_target
            self._nav.cancel()

    def _cancel_goal(self, reason: str) -> None:
        if self._nav.busy:
            self.get_logger().info(f'Nav2 목표 취소: {reason}')
            self._nav.cancel()
        self._last_target = None
        self._hold = None

    def _on_nav_result(self, token: int, state: Nav2State) -> None:
        self.get_logger().info(f'Nav2 목표 {token} 결과: {state.value}')
        if state == Nav2State.SUCCEEDED:
            self._last_fail = False
            self._fsm.on_nav_result(success=True)
        elif state == Nav2State.CANCELED:
            self._fsm.on_nav_result(success=False, canceled=True)
        else:
            self._last_fail = True
            self._fsm.on_nav_result(success=False)

    # ---- 발행 ----
    def _publish_state(self, visible: bool) -> None:
        msg = BooState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame
        if self._game is not None:
            msg.round_id = self._game.round_id
        msg.behavior = int(self._fsm.behavior)
        msg.target_visible = visible
        msg.suspicion = float(self._fsm.suspicion)
        msg.goal_active = self._nav.busy
        seen: Optional[Tuple[float, float]] = self._fsm.last_seen
        msg.last_seen_valid = seen is not None
        if seen is not None:
            point = PointStamped()
            point.header.frame_id = self._frame
            if self._obs is not None:
                point.header.stamp = self._obs.header.stamp
            point.point.x, point.point.y = seen
            msg.last_seen_target = point
        msg.reason = self._fsm.reason
        self._state_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = BooControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
