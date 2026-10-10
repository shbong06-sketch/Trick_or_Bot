"""Nav2 NavigateToPose 목표 전송·취소·결과 확인.

[역할]
Nav2 목표 하나를 보내고, 진행 중 거리와 최종 결과를 호출자에게 알린다.
[구현]
- 액션 클라이언트 하나(NavigateToPose)만 쓴다. 콜백에서 서버 응답을 기다리지 않는다.
- 목표마다 번호(token)를 붙여, 교체된 이전 목표의 늦은 결과가 새 목표 결과와 섞이지 않게 한다.
- 수락 전에 취소를 요청하면 수락 직후에 취소한다.
[범위]
자동 서버 재시작, 무한 재시도, 자체 경로 계획은 하지 않는다.
"""

import math
from enum import Enum
from typing import Callable, Optional

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node


class Nav2State(str, Enum):
    """목표 하나의 진행 상태."""

    IDLE = 'IDLE'              # 보낸 목표 없음
    PENDING = 'PENDING'        # 전송했고 서버 응답 대기
    ACTIVE = 'ACTIVE'          # 수락되어 주행 중
    SUCCEEDED = 'SUCCEEDED'    # 도착
    FAILED = 'FAILED'          # Nav2가 중단(ABORTED)
    CANCELED = 'CANCELED'      # 우리가 취소했거나 Nav2가 취소
    REJECTED = 'REJECTED'      # 서버가 목표를 거절
    NO_SERVER = 'NO_SERVER'    # 서버가 준비되지 않아 보내지 못함


_FINAL = (Nav2State.SUCCEEDED, Nav2State.FAILED, Nav2State.CANCELED,
          Nav2State.REJECTED, Nav2State.NO_SERVER)


class Nav2Client:
    """NavigateToPose 목표를 하나씩 관리하는 작은 클라이언트."""

    def __init__(self, node: Node, action_name: str = 'navigate_to_pose',
                 frame_id: str = 'map',
                 on_result: Optional[Callable[[int, Nav2State], None]] = None):
        """node 네임스페이스 기준의 action_name으로 클라이언트를 만든다.

        on_result(token, state)는 목표가 끝났을 때(최종 상태) 한 번 불린다.
        """
        self._node = node
        self._frame_id = frame_id
        self._on_result = on_result
        self._client = ActionClient(node, NavigateToPose, action_name)
        self._token = 0
        self._state = Nav2State.IDLE
        self._handle = None
        self._cancel_requested = False
        self._remaining_m: Optional[float] = None
        self._current_pose: Optional[PoseStamped] = None

    # ---- 읽기 전용 상태 ----
    @property
    def state(self) -> Nav2State:
        return self._state

    @property
    def token(self) -> int:
        """가장 최근에 보낸 목표의 번호."""
        return self._token

    @property
    def busy(self) -> bool:
        """목표가 전송 중이거나 주행 중이면 True."""
        return self._state in (Nav2State.PENDING, Nav2State.ACTIVE)

    @property
    def remaining_m(self) -> Optional[float]:
        """Nav2 feedback의 남은 경로 길이[m]. 목표가 끝나면 None."""
        return self._remaining_m

    @property
    def current_pose(self) -> Optional[PoseStamped]:
        """Nav2 feedback의 현재 로봇 자세. 아직 없으면 None."""
        return self._current_pose

    def server_ready(self) -> bool:
        return self._client.server_is_ready()

    # ---- 목표 전송·취소 ----
    def send_goal(self, x: float, y: float, yaw: float = 0.0) -> int:
        """새 목표를 보낸다. 진행 중인 목표가 있으면 교체하고, 새 목표 번호를 돌려준다.

        서버가 없으면 NO_SERVER로 바로 끝낸다(기다리지 않는다).
        """
        self._release_old_goal()
        self._token += 1
        token = self._token
        self._remaining_m = None
        self._cancel_requested = False
        if not self._client.server_is_ready():
            self._finish(token, Nav2State.NO_SERVER)
            return token
        goal = NavigateToPose.Goal()
        goal.pose = self._make_pose(x, y, yaw)
        self._state = Nav2State.PENDING
        future = self._client.send_goal_async(
            goal, feedback_callback=lambda msg, t=token: self._on_feedback(t, msg))
        future.add_done_callback(lambda f, t=token: self._on_response(t, f))
        return token

    def cancel(self) -> None:
        """진행 중인 목표를 취소한다. 목표가 없으면 아무것도 하지 않는다."""
        if self._state == Nav2State.PENDING:
            self._cancel_requested = True   # 수락되면 바로 취소
        elif self._state == Nav2State.ACTIVE and self._handle is not None:
            self._cancel_requested = True
            self._handle.cancel_goal_async()

    # ---- 내부 ----
    def _release_old_goal(self) -> None:
        """교체되는 이전 목표를 최선으로 취소하고 결과 수신 대상에서 뺀다."""
        if self._handle is not None and self._state == Nav2State.ACTIVE:
            self._handle.cancel_goal_async()
        self._handle = None
        if self.busy:
            self._state = Nav2State.IDLE   # 이전 목표의 늦은 결과는 token으로 걸러진다

    def _make_pose(self, x: float, y: float, yaw: float) -> PoseStamped:
        pose = PoseStamped()
        pose.header.frame_id = self._frame_id
        pose.header.stamp = self._node.get_clock().now().to_msg()
        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose.pose.orientation.w = math.cos(yaw / 2.0)
        return pose

    def _on_response(self, token: int, future) -> None:
        if token != self._token:
            # 이미 교체된 목표: 수락됐다면 취소만 한다.
            handle = future.result()
            if handle is not None and handle.accepted:
                handle.cancel_goal_async()
            return
        handle = future.result()
        if handle is None or not handle.accepted:
            self._finish(token, Nav2State.REJECTED)
            return
        self._handle = handle
        self._state = Nav2State.ACTIVE
        if self._cancel_requested:
            handle.cancel_goal_async()
        handle.get_result_async().add_done_callback(
            lambda f, t=token: self._on_done(t, f))

    def _on_feedback(self, token: int, msg) -> None:
        if token != self._token:
            return
        feedback = msg.feedback
        self._remaining_m = float(feedback.distance_remaining)
        self._current_pose = feedback.current_pose

    def _on_done(self, token: int, future) -> None:
        if token != self._token:
            return
        status = future.result().status
        if status == GoalStatus.STATUS_SUCCEEDED:
            state = Nav2State.SUCCEEDED
        elif status == GoalStatus.STATUS_CANCELED:
            state = Nav2State.CANCELED
        else:
            state = Nav2State.FAILED
        self._finish(token, state)

    def _finish(self, token: int, state: Nav2State) -> None:
        self._state = state
        self._handle = None
        self._remaining_m = None
        if self._on_result is not None:
            self._on_result(token, state)


def is_final(state: Nav2State) -> bool:
    """목표가 끝난 상태(성공·실패·취소·거절·서버 없음)인지."""
    return state in _FINAL
