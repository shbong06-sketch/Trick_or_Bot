from .base import Bridge


def create_bridge(mock: bool, level: dict) -> Bridge:
    if mock:
        from .mock_bridge import MockBridge
        return MockBridge(level)
    from .ros_bridge import RosBridge
    return RosBridge()
