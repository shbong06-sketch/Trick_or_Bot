# TrickOrBot 구현 지침 v2
# [공통 구현 원칙]
# - 아래 내용은 구현할 기능의 설명이며, 현재 기능이 구현되어 있다는 뜻은 아니다.
# - ROS 2 Jazzy와 현재 패키지 구조를 기준으로 최소한의 구현을 작성한다.
# - docs/interfaces.md와 관련 .msg/.srv 파일을 확인하고 공통 규격을 따른다.
# - 필수 규격이나 게임 규칙이 미정이면 필요한 결정 사항을 먼저 명시한다.
# - 미정인 값을 실제 장비에서 확인한 값처럼 사용하지 않는다.
# - 기존 ROS/Nav2 기능과 공통 모듈을 재사용하고 같은 기능을 중복 구현하지 않는다.
# - 요청하지 않은 패키지, 외부 서버, DB, 플러그인 구조는 추가하지 않는다.
# - 단순한 기능을 불필요한 클래스 계층이나 여러 보조 파일로 나누지 않는다.
# - 필요한 입력 검사와 안전 처리는 구현하되 자동 복구 기능을 임의로 확대하지 않는다.
# - 이 파일의 완료 기준을 만족하면 추가 기능 구현을 멈춘다.
#
# [역할]
# 웹에서 들어온 펌킨 이동 요청을 게임 조작 모드에 맞게 전달하는 ROS 노드.
# [입출력]
# 입력: 웹에서 변환한 이동 요청, 게임 상태, 조작 모드.
# 출력: velocity_gate로 전달할 펌킨 이동 요청.
# [구현]
# 게임 진행 상태에서 플레이어 조작을 허용하고 중단·종료 시 요청을 중지한다.
# 운영자 복구 모드는 합의된 방식으로만 허용한다.
# 입력 수신 시각을 관리해 오래된 명령을 새 명령처럼 반복 전달하지 않는다.
# [실패 처리]
# 웹 입력이 끊기거나 유효하지 않으면 이전 이동 요청을 유지하지 않는다.
# [범위]
# 키보드 해석을 백엔드와 중복 구현하지 않는다.
# 최종 안전 상한·명령 선택은 velocity_gate가 담당하며 cmd_vel을 직접 우회 발행하지 않는다.
# [완료 기준]
# 조작 허용·중단·입력 단절에 따라 이동 요청이 올바르게 전환된다.
#
# [구현 메모]
# - 운영자 복구 모드는 아직 합의되지 않아 구현하지 않았다. 지금은 플레이어 조작만 다룬다.

import math
import time

from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from tob_interfaces.msg import GameState

# docs/interfaces.md 10.1 상태 메시지 권장 QoS
STATE_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                       durability=DurabilityPolicy.VOLATILE,
                       history=HistoryPolicy.KEEP_LAST, depth=1)


def _finite(t) -> bool:
    return all(math.isfinite(v) for v in (t.linear.x, t.linear.y, t.linear.z,
                                          t.angular.x, t.angular.y, t.angular.z))


class PumpkinController(Node):
    """웹 이동 요청을 게임이 RUNNING일 때만 velocity_gate로 넘긴다."""

    def __init__(self):
        super().__init__('pumpkin_controller')
        self._state_timeout = float(self.declare_parameter('game_state_timeout_s', 1.0).value)
        self._request_max_age = Duration(
            seconds=float(self.declare_parameter('request_max_age_s', 0.5).value))
        check_hz = float(self.declare_parameter('check_rate_hz', 10.0).value)

        self._phase: int | None = None
        self._state_rx: float | None = None     # 마지막 GameState 수신 시각 (단조 시계)
        self._allowed = False
        self._allowed_since: Time | None = None  # 이 시각 이전에 만든 요청은 넘기지 않는다
        self._block_reason = '게임 상태 미수신'

        self._pub = self.create_publisher(TwistStamped, '/tob/pumpkin/cmd_manual', 10)
        self.create_subscription(TwistStamped, '/tob/pumpkin/cmd_request', self._on_request, 10)
        self.create_subscription(GameState, '/tob/game/state', self._on_state, STATE_QOS)
        # GameState가 끊긴 것은 콜백으로 알 수 없으므로 주기적으로 확인한다.
        # game_manager와 같이 /clock이 멈춰도 검사하도록 STEADY_TIME 타이머를 쓴다
        self.create_timer(1.0 / check_hz, self._update_allowed,
                          clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.get_logger().info('대기: 게임 상태 미수신')

    def _on_state(self, msg: GameState) -> None:
        self._phase = msg.phase
        self._state_rx = time.monotonic()
        self._update_allowed()

    def _current_block_reason(self) -> str | None:
        if self._state_rx is None:
            return '게임 상태 미수신'
        if time.monotonic() - self._state_rx > self._state_timeout:
            return '게임 상태 만료'
        if self._phase != GameState.RUNNING:
            return f'게임 진행 중 아님 (phase={self._phase})'
        return None

    def _update_allowed(self) -> None:
        reason = self._current_block_reason()
        allowed = reason is None
        if allowed and not self._allowed:
            # 진행 전·일시정지 중에 만든 오래된 요청은 재개 후에도 실행하지 않는다
            self._allowed_since = self.get_clock().now()
            self.get_logger().info('조작 허용')
        elif not allowed and (self._allowed or reason != self._block_reason):
            if self._allowed:
                self._publish_stop()
            self.get_logger().info(f'조작 중지: {reason}')
            self._block_reason = reason
        self._allowed = allowed

    def _on_request(self, msg: TwistStamped) -> None:
        if not self._allowed:
            return
        if not _finite(msg.twist):
            self.get_logger().warn('유한값이 아닌 이동 요청을 버림')
            self._publish_stop()
            return
        stamp = Time.from_msg(msg.header.stamp, clock_type=self.get_clock().clock_type)
        if stamp < self._allowed_since:
            return
        if self.get_clock().now() - stamp > self._request_max_age:
            self.get_logger().warn('오래된 이동 요청을 버림', throttle_duration_sec=1.0)
            return
        self._pub.publish(msg)

    def _publish_stop(self) -> None:
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        self._pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = PumpkinController()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
