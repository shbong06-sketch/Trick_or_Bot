"""Level 1 게임의 명령, 입력 검사, ROS 시간과 최종 결과를 관리한다."""

from dataclasses import dataclass
import math
from pathlib import Path
import time
from uuid import uuid4

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from geometry_msgs.msg import PoseStamped
from rcl_interfaces.msg import ParameterDescriptor
import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from tob_game.level_loader import LevelConfigError, load_level
from tob_game.round_logger import RoundLogger
from tob_game.rules import break_capture, evaluate, Observation, RoundState
from tob_interfaces.msg import GameEvent, GameState, SafetyState, TargetObservation
from tob_interfaces.srv import GameCommand


def stamp_ns(stamp):
    """원본 ROS 시각을 정수 나노초로 읽는다."""
    return stamp.sec * 1_000_000_000 + stamp.nanosec


@dataclass
class Sample:
    """원본 메시지와 별도의 단조 수신 시각."""

    message: object
    received_s: float


def state_qos(depth=1):
    """인터페이스 문서의 상태·이벤트 QoS를 만든다."""
    return QoSProfile(depth=depth, reliability=ReliabilityPolicy.RELIABLE,
                      durability=DurabilityPolicy.VOLATILE,
                      history=HistoryPolicy.KEEP_LAST)


class GameManagerNode(Node):
    """이동 제어 없이 게임 상태와 사건만 발행하는 노드."""

    def __init__(self, **kwargs):
        """운영 설정과 ROS 연결을 준비한다. 레벨 검증은 START에서 수행한다."""
        super().__init__('game_manager', **kwargs)
        share = Path(get_package_share_directory('tob_game'))
        self._config_file = share / 'config' / 'game_manager.yaml'
        defaults = {
            'level_path': 'levels/level1.yaml',
            'result_log_path': '~/.local/state/tob_game/rounds.jsonl',
            'tick_period_s': 0.05,
            'state_period_s': 0.1,
            'pose_timeout_s': 0.5,
            'observation_timeout_s': 0.5,
            'receive_timeout_s': 0.5,
            'future_tolerance_s': 0.05,
            'observation_position_skew_s': 0.2,
            'safety_max_valid_for_s': 1.0,
            'max_clock_step_s': 1.0,
            'observation_sources': ['boo_camera'],
            'observation_frame_ids': ['camera_optical_frame'],
        }
        self.settings = {}
        for name, default in defaults.items():
            value = self.declare_parameter(
                name, default, ParameterDescriptor(read_only=True)).value
            if isinstance(default, float):
                if not math.isfinite(value) or value <= 0:
                    raise ValueError(f'ROS 파라미터 {name}: 유한한 양수가 필요합니다')
            elif isinstance(default, list):
                if not value or any(not isinstance(v, str) or not v.strip() for v in value):
                    raise ValueError(f'ROS 파라미터 {name}: 빈 항목 없는 문자열 목록이 필요합니다')
            elif not value.strip():
                raise ValueError(f'ROS 파라미터 {name}: 빈 경로는 사용할 수 없습니다')
            self.settings[name] = value
        if self.settings['tick_period_s'] > self.settings['max_clock_step_s']:
            raise ValueError('tick_period_s는 max_clock_step_s 이하여야 합니다')
        self._round_logger = RoundLogger(
            self.settings['result_log_path'], (get_package_prefix('tob_game'), share))
        self.phase = GameState.READY
        self.round_id = ''
        self.level = None
        self.round = RoundState(hp=0)
        self._active_ns = 0
        self._last_game_ns = self._ros_ns()
        self._clock_seen_ns = self._last_game_ns
        self._samples = {}
        self._watermarks = {}
        self._observation_after_ns = self._last_game_ns
        self._resume_received_s = self._steady_s()
        self._finished = False
        self._state_pub = self.create_publisher(GameState, '/tob/game/state', state_qos())
        self._event_pub = self.create_publisher(GameEvent, '/tob/game/event', state_qos(10))
        for robot in ('pumpkin', 'boo'):
            self.create_subscription(
                PoseStamped, f'/tob/{robot}/pose',
                lambda msg, key=f'{robot}_pose': self._receive(key, msg), state_qos())
            self.create_subscription(
                SafetyState, f'/tob/{robot}/safety',
                lambda msg, key=f'{robot}_safety': self._receive(key, msg), state_qos())
        self.create_subscription(TargetObservation, '/tob/target/observation',
                                 lambda msg: self._receive('observation', msg), state_qos())
        self.create_service(GameCommand, '/tob/game/command', self._command)
        # /clock이 멈춰도 상태 발행과 수신 중단 검사를 계속한다.
        self._steady_clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.create_timer(self.settings['tick_period_s'], self._tick, clock=self._steady_clock)
        self.create_timer(self.settings['state_period_s'], self._publish_state,
                          clock=self._steady_clock)
        self._publish_state()
        self.get_logger().info('게임 관리자 준비: 운영 시간 설정은 실측 전 초기값입니다')

    def _ros_ns(self):
        return self.get_clock().now().nanoseconds

    def _steady_s(self):
        return time.monotonic()

    def _check_clock(self, now):
        delta = (now - self._clock_seen_ns) / 1e9
        self._clock_seen_ns = now
        if delta < 0 or delta > self.settings['max_clock_step_s']:
            # 비정상 구간은 누적하지 않고 새 시간축에서 새 입력을 기다린다.
            self._last_game_ns = now
            self._samples.clear()
            self._watermarks.clear()
            self._observation_after_ns = now
            break_capture(self.round)
            self.round.observation_floor = 0
            self.round.awaiting_observation = False
            self.get_logger().warning('ROS 시계 불연속: 해당 구간 제외, 입력과 잡힘 누적 초기화')

    def _fresh_stamp(self, stamp, now, timeout):
        original = stamp_ns(stamp)
        age = (now - original) / 1e9
        return (original > 0 and 0 <= stamp.nanosec < 1_000_000_000
                and -self.settings['future_tolerance_s'] <= age <= timeout)

    def _fresh_sample(self, sample, now, received, timeout):
        return (sample is not None
                and 0 <= received - sample.received_s <= self.settings['receive_timeout_s']
                and self._fresh_stamp(sample.message.header.stamp, now, timeout))

    def _pose(self, robot, level, now, received):
        sample = self._samples.get(f'{robot}_pose')
        if not self._fresh_sample(sample, now, received, self.settings['pose_timeout_s']):
            return None
        msg = sample.message
        p = msg.pose.position
        if (not msg.header.frame_id or msg.header.frame_id != level['frame_id']
                or not all(math.isfinite(v) for v in (p.x, p.y, p.z))):
            return None
        return p.x, p.y

    def _safety_error(self, robot, now, received):
        sample = self._samples.get(f'{robot}_safety')
        if sample is None:
            return f'{robot}: 안전 상태를 받지 못했습니다'
        msg = sample.message
        if msg.robot_id != robot:
            return f'{robot}: SafetyState.robot_id가 일치하지 않습니다'
        if (not math.isfinite(msg.valid_for_s)
                or not 0 < msg.valid_for_s <= self.settings['safety_max_valid_for_s']):
            return f'{robot}: valid_for_s가 유한한 양수 또는 허용 상한 조건을 위반했습니다'
        if not self._fresh_sample(sample, now, received, msg.valid_for_s):
            return f'{robot}: 안전 상태의 원본 시각 또는 수신 시간이 만료되었습니다'
        if received - sample.received_s > msg.valid_for_s:
            return f'{robot}: 안전 허가 수신 유효기간이 만료되었습니다'
        if not msg.motion_allowed:
            return f'{robot}: 이동이 허용되지 않았습니다 ({msg.reason})'
        return ''

    def _observation(self, now, received):
        sample = self._samples.get('observation')
        if not self.level or not self._fresh_sample(
                sample, now, received, self.settings['observation_timeout_s']):
            return None
        msg = sample.message
        point = msg.target_position
        if (stamp_ns(msg.header.stamp) <= self._observation_after_ns
                or stamp_ns(point.header.stamp) <= self._observation_after_ns
                or msg.source not in self.settings['observation_sources']
                or msg.header.frame_id not in self.settings['observation_frame_ids']
                or not msg.detected or not msg.map_valid
                or point.header.frame_id != self.level['frame_id']
                or not self._fresh_stamp(point.header.stamp, now, self.settings['pose_timeout_s'])
                or abs(stamp_ns(msg.header.stamp) - stamp_ns(point.header.stamp)) / 1e9
                > self.settings['observation_position_skew_s']
                or not all(math.isfinite(v) for v in (point.point.x, point.point.y, point.point.z))
                or not math.isfinite(msg.distance_m) or msg.distance_m < 0):
            return None
        return Observation(stamp_ns(msg.header.stamp), msg.distance_m)

    def _receive(self, key, msg):
        now, received = self._ros_ns(), self._steady_s()
        self._check_clock(now)
        self._expire_resume_wait(now, received)
        original = stamp_ns(msg.header.stamp)
        if original > 0 and original <= self._watermarks.get(key, 0):
            return  # 역순·중복은 수신 시각과 최신성을 연장하지 않는다.
        if not self._fresh_stamp(msg.header.stamp, now, float('inf')):
            self._samples.pop(key, None)
            if key == 'observation' and self.phase == GameState.RUNNING:
                self.round.awaiting_observation = False
                break_capture(self.round)
            return
        if key == 'observation' and self.phase == GameState.RUNNING:
            if not self.round.awaiting_observation and self._observation(now, received) is None:
                break_capture(self.round)
        self._watermarks[key] = original
        self._samples[key] = Sample(msg, received)
        if key == 'observation' and self.phase == GameState.RUNNING:
            # 타이머 사이에 무효 → 유효 관측이 와도 연속성을 잃은 사실을 보존한다.
            if original > self._observation_after_ns:
                self.round.awaiting_observation = False
                observation = self._observation(now, received)
                if (observation is None or observation.distance_m
                        > self.level['rules']['capture']['distance_m']):
                    break_capture(self.round)

    def _readiness_error(self, level, now, received):
        if now <= 0:
            return 'ROS 시계가 아직 유효하지 않습니다'
        for robot in ('pumpkin', 'boo'):
            if self._pose(robot, level, now, received) is None:
                return f'{robot}: 위치의 좌표계·좌표·원본 시각·수신 최신성을 확인하세요'
            error = self._safety_error(robot, now, received)
            if error:
                return error
        return ''

    def _advance_time(self, now):
        self._active_ns += max(0, now - self._last_game_ns)
        self._last_game_ns = now
        self.round.elapsed_s = self._active_ns / 1e9

    def _new_observations_only(self, now, preserve_hold=False):
        self._samples.pop('observation', None)
        self._observation_after_ns = now
        self._resume_received_s = self._steady_s()
        break_capture(self.round, preserve_hold=preserve_hold)
        self.round.awaiting_observation = preserve_hold

    def _expire_resume_wait(self, now, received):
        if (self.phase == GameState.RUNNING and self.round.awaiting_observation
                and ((now - self._observation_after_ns) / 1e9
                     > self.settings['observation_timeout_s']
                     or received - self._resume_received_s > self.settings['receive_timeout_s'])):
            self.round.awaiting_observation = False
            break_capture(self.round)

    def _command(self, request, response):
        command = request.command
        error = ''
        candidate = None
        if command not in (request.START, request.PAUSE, request.RESUME, request.RESET):
            error = f'지원하지 않는 명령입니다: {command}'
        elif command == request.START:
            if self.phase not in (GameState.READY, GameState.CLEARED, GameState.FAILED):
                error = 'START는 READY·CLEARED·FAILED에서만 허용됩니다'
            elif request.round_id:
                error = 'START의 round_id는 새 회차 요청이므로 비워야 합니다'
            elif request.level != 1:
                error = f'지원하지 않는 레벨입니다: {request.level}'
            else:
                try:
                    candidate = load_level(self.settings['level_path'], self._config_file)
                except LevelConfigError as exc:
                    error = str(exc)
        elif request.round_id != self.round_id:
            error = '현재 round_id와 일치하지 않습니다'
        elif command == request.PAUSE and self.phase != GameState.RUNNING:
            error = 'PAUSE는 RUNNING에서만 허용됩니다'
        elif command == request.RESUME and self.phase != GameState.PAUSED:
            error = 'RESUME은 PAUSED에서만 허용됩니다'
        now, received = self._ros_ns(), self._steady_s()
        if not error and command in (request.START, request.RESUME):
            # 거절은 회차를 변경하지 않는다. 시계 불연속은 주기 콜백이 처리한다.
            delta = (now - self._clock_seen_ns) / 1e9
            if delta < 0 or delta > self.settings['max_clock_step_s']:
                error = 'ROS 시계 불연속 이후 새 입력을 기다려야 합니다'
            else:
                error = self._readiness_error(candidate or self.level, now, received)
        if not error:
            self._check_clock(now)
            if command == request.START:
                self.level = candidate
                self.round = RoundState(hp=candidate['rules']['initial_hp'])
                self.round_id = str(uuid4())
                self._active_ns = 0
                self._last_game_ns = now
                self._finished = False
                self._new_observations_only(now)
                self.phase = GameState.RUNNING
            elif command == request.PAUSE:
                self._advance_time(now)
                self.phase = GameState.PAUSED
                break_capture(self.round, preserve_hold=True)
            elif command == request.RESUME:
                self._last_game_ns = now
                self._new_observations_only(now, preserve_hold=True)
                self.phase = GameState.RUNNING
            else:
                self.phase = GameState.READY
                self.round_id = ''
                self.level = None
                self.round = RoundState(hp=0)
                self._active_ns = 0
                self._last_game_ns = now
                self._finished = False
                self._new_observations_only(now)
        response.accepted = not bool(error)
        response.message = error or '명령을 수락했습니다. 실제 로봇 정지 완료를 뜻하지 않습니다'
        response.round_id = self.round_id
        response.phase = self.phase
        self._publish_state()
        return response

    def _tick(self):
        now, received = self._ros_ns(), self._steady_s()
        self._check_clock(now)
        if self.phase != GameState.RUNNING:
            return
        self._expire_resume_wait(now, received)
        self._advance_time(now)
        events = evaluate(self.level, self.round, self.round.elapsed_s,
                          self._pose('pumpkin', self.level, now, received),
                          self._observation(now, received))
        if self.round.outcome:
            self.phase = getattr(GameState, self.round.outcome)
        for event in events:
            msg = GameEvent()
            msg.stamp = self.get_clock().now().to_msg()
            msg.round_id, msg.level = self.round_id, self.level['level']
            msg.event_type = getattr(GameEvent, event.kind)
            msg.hp, msg.candy_id = event.hp, event.candy_id
            msg.elapsed_s, msg.reason = self.round.elapsed_s, event.reason
            self._event_pub.publish(msg)
        if events:
            self._publish_state()
        if self.round.outcome and not self._finished:
            self._finished = True
            try:
                self._round_logger.write({
                    'round_id': self.round_id, 'level': self.level['level'],
                    'ended_at_ros_ns': now, 'phase': self.round.outcome,
                    'reason': self.round.reason, 'elapsed_s': self.round.elapsed_s,
                    'hp': self.round.hp, 'collected_candy_ids': list(self.round.collected),
                })
            except OSError as exc:
                self.get_logger().error(str(exc))

    def _publish_state(self):
        msg = GameState()
        msg.stamp = self.get_clock().now().to_msg()
        msg.round_id, msg.phase = self.round_id, self.phase
        msg.level = self.level['level'] if self.level else 0
        msg.elapsed_s, msg.hp = self.round.elapsed_s, self.round.hp
        if self.level:
            msg.max_hp = self.level['rules']['initial_hp']
            msg.remaining_s = max(0.0, self.level['rules']['time_limit_s'] - self.round.elapsed_s)
            msg.candy_total = len(self.level['layout']['candies'])
            msg.exit_enabled = len(self.round.collected) == msg.candy_total
        msg.collected_candy_ids = list(self.round.collected)
        msg.reason = self.round.reason
        self._state_pub.publish(msg)


def main(args=None):
    """게임 관리자 하나만 실행한다."""
    rclpy.init(args=args)
    node = None
    try:
        node = GameManagerNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()
