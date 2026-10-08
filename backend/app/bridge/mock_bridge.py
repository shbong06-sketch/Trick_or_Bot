from .base import Bridge


class MockBridge(Bridge):
    def camera_info(self) -> dict:
        # 가짜 값. 실제 값은 /robot2의 camera_info에서 읽는다 [확인 필요]
        # 704×704는 팀원 기억 기준 [확인 필요]. fx/fy는 임의 값
        return {
            "w": 704, "h": 704,
            "fx": 500.0, "fy": 500.0, "cx": 352.0, "cy": 352.0,
            "frame": "mock_rgb_camera_optical_frame",
        }
