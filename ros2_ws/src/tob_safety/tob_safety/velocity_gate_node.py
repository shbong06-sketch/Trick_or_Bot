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
# 각 로봇에서 이동 요청의 권한·신선도·속도 상한을 검사하는 ROS 노드.
# [입출력]
# 입력: 수동·자동 요청, 조작 모드, 이동 허가, 정지 요청.
# 출력: Collision Monitor의 입력으로 보낼 속도 명령.
# [구현]
# 현재 모드에서 선택된 명령만 통과시킨다.
# 명령과 이동 허가가 각각 만료되는지 로봇 로컬에서 검사한다.
# 유효한 허가·명령이 없거나 정지 상태이면 0 속도를 출력한다.
# [실패 처리]
# 유한값이 아닌 속도나 만료된 요청을 거부한다.
# 재연결됐다는 이유만으로 이전 이동 명령을 다시 실행하지 않는다.
# [범위]
# 카메라 탐지·Nav2 경로 계산·라이다 충돌 판정을 중복 구현하지 않는다.
# 안전 처리 이후에 다른 발행자가 cmd_vel을 덮어쓰지 않도록 실행 구성을 맞춘다.
# [완료 기준]
# 명령 단절·허가 단절·모드 변경·정지 요청에서 이전 속도가 유지되지 않는다.
#
# [구현 메모]
# - 입력 토픽은 robot_id로 정한다: /tob/<robot_id>/cmd_manual, cmd_auto, control_mode, safety
# - control_mode(std_msgs/String): manual | auto | stop. 발행자가 아직 없으면 default_mode를 쓴다.
# - Collision Monitor 설정 전까지는 output_topic을 로봇 cmd_vel에 바로 연결한다.

import math
import time

from geometry_msgs.msg import Twist, TwistStamped
import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from std_msgs.msg import String
from tob_interfaces.msg import SafetyState

MODES = ('manual', 'auto', 'stop')

# docs/interfaces.md 10.1 상태 메시지 권장 QoS
STATE_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                       durability=DurabilityPolicy.VOLATILE,
                       history=HistoryPolicy.KEEP_LAST, depth=1)
# 모드는 늦게 뜬 게이트도 현재 값을 받아야 한다
MODE_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                      durability=DurabilityPolicy.TRANSIENT_LOCAL,
                      history=HistoryPolicy.KEEP_LAST, depth=1)


def _finite(t) -> bool:
    return all(math.isfinite(v) for v in (t.linear.x, t.linear.y, t.linear.z,
                                          t.angular.x, t.angular.y, t.angular.z))


def _clamp(v: float, limit: float) -> float:
    return max(-limit, min(limit, v))


class VelocityGate(Node):
    """선택된 모드의 신선한 명령만 속도 상한을 적용해 통과시키고, 막히면 0 속도를 한 번 보낸다."""

    def __init__(self):
        super().__init__('velocity_gate')
        p = self.declare_parameter
        self._robot_id = p('robot_id', 'pumpkin').value
        output_topic = p('output_topic', '').value
        self._stamped = bool(p('output_stamped', False).value)
        self._frame = p('output_frame', 'base_link').value
        self._max_lin = float(p('max_lin', 0.0).value)
        self._max_ang = float(p('max_ang', 0.0).value)
        self._cmd_timeout = float(p('cmd_timeout_s', 0.5).value)
        self._require_safety = bool(p('require_safety_state', True).value)
        self._safety_max_age = float(p('safety_max_age_s', 0.5).value)
        self._mode = p('default_mode', 'manual').value
        check_hz = float(p('check_rate_hz', 20.0).value)
        if not output_topic:
            raise ValueError('output_topic 파라미터가 비어 있음 (safety.yaml 확인)')
        if self._max_lin <= 0.0 or self._max_ang <= 0.0:
            raise ValueError('max_lin·max_ang 파라미터가 설정되지 않음 (safety.yaml 확인)')
        if self._mode not in MODES:
            raise ValueError(f'default_mode={self._mode} 는 {MODES} 중 하나여야 함')

        # 수신 시각은 단조 시계로 잰다 (/clock이 멈춰도 만료 검사를 계속한다)
        self._mode_since = time.monotonic()  # 모드 전환 전에 받은 명령은 쓰지 않는다
        self._cmd: dict[str, tuple[Twist, float] | None] = {'manual': None, 'auto': None}
        self._safety: tuple[SafetyState, float] | None = None
        self._passing = False           # 마지막으로 0이 아닌 명령을 내보냈는지
        self._reason = ''

        ns = f'/tob/{self._robot_id}'
        msg_type = TwistStamped if self._stamped else Twist
        self._pub = self.create_publisher(msg_type, output_topic, 10)
        self.create_subscription(TwistStamped, f'{ns}/cmd_manual',
                                 lambda m: self._on_cmd('manual', m), 10)
        self.create_subscription(TwistStamped, f'{ns}/cmd_auto',
                                 lambda m: self._on_cmd('auto', m), 10)
        self.create_subscription(String, f'{ns}/control_mode', self._on_mode, MODE_QOS)
        self.create_subscription(SafetyState, f'{ns}/safety', self._on_safety, STATE_QOS)
        self.create_timer(1.0 / check_hz, lambda: self._evaluate(None),
                          clock=Clock(clock_type=ClockType.STEADY_TIME))

        self.get_logger().info(
            f'{ns}/cmd_{{manual,auto}} → {self._pub.topic_name} '
            f"({'TwistStamped' if self._stamped else 'Twist'}), mode={self._mode}, "
            f'상한 {self._max_lin} m/s · {self._max_ang} rad/s')
        if not self._require_safety:
            self.get_logger().warn('require_safety_state=false: SafetyState 없이 이동을 허용함 '
                                   '(safety_supervisor 구현 전 임시 설정)')

    # ---- 입력 ----
    def _on_cmd(self, source: str, msg: TwistStamped) -> None:
        if not _finite(msg.twist):
            self.get_logger().warn(f'{source}: 유한값이 아닌 속도를 거부함')
            self._cmd[source] = None
        else:
            self._cmd[source] = (msg.twist, time.monotonic())
        if source == self._mode:
            self._evaluate(self._cmd[source])

    def _on_mode(self, msg: String) -> None:
        mode = msg.data if msg.data in MODES else 'stop'
        if mode != msg.data:
            self.get_logger().warn(f'알 수 없는 모드 "{msg.data}" → stop')
        if mode == self._mode:
            return
        self.get_logger().info(f'모드 {self._mode} → {mode}')
        self._mode, self._mode_since = mode, time.monotonic()
        self._evaluate(None)

    def _on_safety(self, msg: SafetyState) -> None:
        if msg.robot_id == self._robot_id:
            self._safety = (msg, time.monotonic())
            self._evaluate(None)

    # ---- 판단 ----
    def _block_reason(self) -> str | None:
        now = time.monotonic()
        if self._mode == 'stop':
            return '정지 모드'
        entry = self._cmd[self._mode]
        if entry is None:
            return f'{self._mode} 명령 없음'
        _, rx = entry
        if rx < self._mode_since:
            return '모드 전환 전 명령'
        if now - rx > self._cmd_timeout:
            return f'{self._mode} 명령 만료'
        if self._require_safety:
            if self._safety is None:
                return '안전 상태 미수신'
            safety, safety_rx = self._safety
            max_age = min(float(safety.valid_for_s), self._safety_max_age)
            ros_now = self.get_clock().now()
            stamp = Time.from_msg(safety.header.stamp, clock_type=ros_now.clock_type)
            # 발행 시각(ROS 시계)과 실제 수신 중단(단조 시계)을 모두 검사한다 (docs/interfaces.md 5.5)
            if now - safety_rx > max_age or (ros_now - stamp).nanoseconds * 1e-9 > max_age:
                return '안전 상태 만료'
            if not safety.motion_allowed:
                return f'이동 금지: {safety.reason}'
        return None

    def _evaluate(self, fresh) -> None:
        """선택 모드의 방금 받은 명령(fresh)을 검사해 통과시킨다. None이면 상태만 다시 검사."""
        reason = self._block_reason()
        if reason is None:
            if fresh is not None:
                twist, _ = fresh
                self._publish(_clamp(twist.linear.x, self._max_lin),
                              _clamp(twist.angular.z, self._max_ang))
            if self._reason:
                self.get_logger().info('명령 통과')
                self._reason = ''
            return
        if self._passing:
            self._publish(0.0, 0.0)
        if reason != self._reason:
            self.get_logger().info(f'차단: {reason}')
            self._reason = reason

    def _publish(self, lin: float, ang: float) -> None:
        if self._stamped:
            msg = TwistStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self._frame
            twist = msg.twist
        else:
            msg = twist = Twist()
        twist.linear.x = lin
        twist.angular.z = ang
        self._pub.publish(msg)
        self._passing = bool(lin or ang)


def main(args=None):
    rclpy.init(args=args)
    node = VelocityGate()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
