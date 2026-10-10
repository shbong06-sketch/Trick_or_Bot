import asyncio
import logging
import time

from .bridge import Bridge

log = logging.getLogger("teleop")

# 브라우저가 보내는 키 비트마스크
W, A, S, D = 1, 2, 4, 8


class Teleop:
    """WASD 비트마스크 → cmd_vel. 키를 누르는 동안 일정 주기로 발행하고, 입력이 끊기면 정지한다."""

    def __init__(self, bridge: Bridge, cfg: dict):
        self.bridge = bridge
        self.max_lin = float(cfg["max_lin"])
        self.max_ang = float(cfg["max_ang"])
        self.period = 1.0 / float(cfg["cmd_rate_hz"])
        self.watchdog = float(cfg["watchdog_s"])
        self.mask = 0
        self.last_rx = 0.0
        self.owner = None  # 조작권을 가진 연결 하나

    def _velocity(self, mask: int) -> tuple[float, float]:
        lin = self.max_lin * ((mask & W > 0) - (mask & S > 0))
        ang = self.max_ang * ((mask & A > 0) - (mask & D > 0))
        return lin, ang

    def on_keys(self, mask: int) -> None:
        self.last_rx = time.monotonic()
        if mask != self.mask:
            self.mask = mask
            # 키 상태가 바뀌면 다음 주기를 기다리지 않고 바로 발행 (정지 포함)
            self.bridge.send_cmd(*self._velocity(mask))

    def on_heartbeat(self) -> None:
        self.last_rx = time.monotonic()

    def halt(self, reason: str) -> None:
        if self.mask:
            log.info("정지: %s", reason)
        self.mask = 0
        self.bridge.send_cmd(0.0, 0.0)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.period)
            if not self.mask:
                continue
            if time.monotonic() - self.last_rx > self.watchdog:
                self.halt(f"입력 {self.watchdog}s 끊김")
            else:
                self.bridge.send_cmd(*self._velocity(self.mask))
