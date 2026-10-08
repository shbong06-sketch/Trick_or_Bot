from .base import Bridge


def create_bridge(mock: bool) -> Bridge:
    if mock:
        from .mock_bridge import MockBridge
        return MockBridge()
    # ROS 브리지는 다음 단계에서 구현한다
    raise NotImplementedError("ROS 브리지는 아직 없다. MOCK=1로 실행할 것")
