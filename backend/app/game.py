import asyncio
import logging
import math
import time

from .bridge import Bridge

log = logging.getLogger("game")

CHECK_PERIOD = 0.1  # 10 Hz. 획득 판정 → 화면 사라짐 0.5 s 예산에서 판정 지연이 최대 0.1 s


class Game:
    """회차 상태. 사탕 획득은 서버만 판정하고, 결과를 연결된 모든 화면에 이벤트로 보낸다."""

    def __init__(self, level: dict, bridge: Bridge):
        self.bridge = bridge
        self.radius = float(level["pick_radius_m"])
        self.candies = {c["id"]: (float(c["x"]), float(c["y"])) for c in level["candies"]}
        self.collected: dict[str, float] = {}  # id → 판정 시각 (서버 time.time())
        self.clients: set = set()              # /ws/game 연결들

    async def broadcast(self, msg: str) -> None:
        for ws in list(self.clients):
            try:
                await ws.send_text(msg)
            except Exception:
                self.clients.discard(ws)

    def collected_msg(self) -> str:
        return '{"t":"cds","ids":[%s]}' % ",".join(f'"{i}"' for i in self.collected)

    async def reset(self) -> None:
        self.collected.clear()
        log.info("회차 초기화: 사탕 %d개", len(self.candies))
        await self.broadcast(self.collected_msg())

    async def run(self) -> None:
        while True:
            await asyncio.sleep(CHECK_PERIOD)
            pose = self.bridge.pumpkin_pose()
            if pose is None:
                continue
            x, y, _ = pose
            for cid, (cx, cy) in self.candies.items():
                if cid in self.collected:
                    continue
                d = math.hypot(x - cx, y - cy)
                if d <= self.radius:
                    ts = time.time()
                    self.collected[cid] = ts
                    log.info("획득 %s (거리 %.2f m, %d/%d) 판정 시각 %.3f",
                             cid, d, len(self.collected), len(self.candies), ts)
                    await self.broadcast('{"t":"cd","id":"%s","n":%d,"ts":%.4f}' % (cid, len(self.collected), ts))
