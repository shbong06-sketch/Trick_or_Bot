from abc import ABC, abstractmethod
from typing import Protocol

from ..protocol import Pose7


class VideoSink(Protocol):
    def want_frame(self) -> bool: ...
    def push(self, stamp: float, pose: Pose7 | None, jpeg: bytes) -> None: ...


class Bridge(ABC):
    """게임 서버가 로봇 정보에 접근하는 유일한 통로. ROS와 mock이 같은 인터페이스를 따른다."""

    # True면 게임 판정은 ROS game_manager가 하고, 서버는 game_state()를 화면에 옮기기만 한다
    remote_game = False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    @abstractmethod
    def camera_info(self) -> dict:
        """펌킨 1인칭 카메라 내부 파라미터: {w, h, fx, fy, cx, cy, frame}"""

    @abstractmethod
    def send_cmd(self, lin: float, ang: float) -> None:
        """펌킨 이동 요청 (m/s, rad/s). 호출한 쪽이 주기·워치독을 책임진다.

        ROS에서는 pumpkin_controller(게임 진행 확인) → velocity_gate(안전 상한)를 거쳐 cmd_vel이 된다.
        """

    async def request_start(self, level: int) -> tuple[bool, str]:
        """게임 관리자에게 회차 시작을 요청한다. (수락 여부, 거절 사유). mock은 항상 수락."""
        return True, ""

    async def request_reset(self, round_id: str) -> tuple[bool, str]:
        """게임 관리자에게 회차 초기화를 요청한다. (수락 여부, 거절 사유). mock은 항상 수락."""
        return True, ""

    def game_state(self) -> dict | None:
        """game_manager의 마지막 GameState (remote_game일 때만). 아직 못 받았으면 None."""
        return None

    def reset_pumpkin(self) -> None:
        """펌킨을 시작 위치로 되돌린다. mock만 가능하고 실물 로봇은 아무것도 하지 않는다."""

    def pumpkin_pose(self) -> tuple[float, float, float] | None:
        """map 프레임 펌킨 위치 (x, y, yaw). 아직 모르면 None."""
        return None

    def boo_pose(self) -> tuple[float, float, float] | None:
        """map 프레임 부우 위치 (x, y, yaw). 아직 모르면 None."""
        return None

    @abstractmethod
    def set_video_sink(self, sink: VideoSink) -> None:
        """펌킨 카메라 JPEG를 받을 곳. start() 전에 호출한다."""
