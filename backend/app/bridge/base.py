from abc import ABC, abstractmethod
from typing import Protocol

from ..protocol import Pose7


class VideoSink(Protocol):
    def want_frame(self) -> bool: ...
    def push(self, stamp: float, pose: Pose7 | None, jpeg: bytes) -> None: ...


class Bridge(ABC):
    """게임 서버가 로봇 정보에 접근하는 유일한 통로. ROS와 mock이 같은 인터페이스를 따른다."""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    @abstractmethod
    def camera_info(self) -> dict:
        """펌킨 1인칭 카메라 내부 파라미터: {w, h, fx, fy, cx, cy, frame}"""

    @abstractmethod
    def send_cmd(self, lin: float, ang: float) -> None:
        """펌킨 속도 명령 (m/s, rad/s). 호출한 쪽이 주기·워치독을 책임진다."""

    def pumpkin_pose(self) -> tuple[float, float, float] | None:
        """map 프레임 펌킨 위치 (x, y, yaw). 아직 모르면 None."""
        return None

    def boo_pose(self) -> tuple[float, float, float] | None:
        """map 프레임 부우 위치 (x, y, yaw). 아직 모르면 None."""
        return None

    @abstractmethod
    def set_video_sink(self, sink: VideoSink) -> None:
        """펌킨 카메라 JPEG를 받을 곳. start() 전에 호출한다."""
