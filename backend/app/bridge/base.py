from abc import ABC, abstractmethod


class Bridge(ABC):
    """게임 서버가 로봇 정보에 접근하는 유일한 통로. ROS와 mock이 같은 인터페이스를 따른다."""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    @abstractmethod
    def camera_info(self) -> dict:
        """펌킨 1인칭 카메라 내부 파라미터: {w, h, fx, fy, cx, cy, frame}"""
