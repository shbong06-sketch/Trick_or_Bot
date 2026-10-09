import asyncio
import json
import logging
import math
import time

from .bridge import Bridge

log = logging.getLogger("game")

CHECK_PERIOD = 0.1  # 10 Hz. 획득 판정 → 화면 사라짐 0.5 s 예산에서 판정 지연이 최대 0.1 s


class Game:
    """회차 상태. 사탕 획득·탈출문·시간 초과는 서버만 판정하고, 결과를 모든 화면에 이벤트로 보낸다.

    상태: ready(시작 전) → run(진행 중) → clear(탈출 성공) | over(시간 초과)
    탈출문: 잠김 → (사탕을 다 모은 뒤 문 앞 구역에서 dwell_s 머무름) → 열림 → (문 지점 도착) → clear
    """

    def __init__(self, level: dict, bridge: Bridge):
        self.bridge = bridge
        self.lv = int(level["lv"])
        self.duration = float(level["time_limit_s"])
        self.radius = float(level["pick_radius_m"])
        self.candies = {c["id"]: (float(c["x"]), float(c["y"])) for c in level["candies"]}
        g = level["gate"]
        self.gate = (float(g["x"]), float(g["y"]))
        yaw = float(g.get("yaw", 0.0))
        front = float(level["gate_front_m"])
        self.gate_front = (self.gate[0] + front * math.cos(yaw), self.gate[1] + front * math.sin(yaw))
        self.zone_r = float(level["gate_zone_r"])
        self.dwell_s = float(level["gate_dwell_s"])
        self.enter_r = float(level["gate_enter_r"])

        self.clients: set = set()              # /ws/game 연결들
        self.on_end = None                     # clear·over 때 호출 (로봇 정지)
        self._reset_round()
        self.state = "ready"
        self.reason: str | None = None
        self.last_clear: dict | None = None    # 마지막 클리어 {lv, time, saved}. 닉네임 저장에 쓴다

    def _reset_round(self) -> None:
        self.collected: dict[str, float] = {}  # id → 판정 시각 (서버 time.time())
        self.t0: float | None = None           # 시작 시각
        self.t_end: float | None = None        # clear·over 시각
        self.dwell_from: float | None = None   # 문 앞 구역에 들어온 시각 (머무는 중일 때만)
        self.opened_at: float | None = None    # 문이 열린 시각

    # ---- 보내는 메시지 ----
    async def broadcast(self, msg: str) -> None:
        for ws in list(self.clients):
            try:
                await ws.send_text(msg)
            except Exception:
                self.clients.discard(ws)

    def collected_msg(self) -> str:
        return json.dumps({"t": "cds", "ids": list(self.collected)})

    def state_msg(self) -> str:
        # 남은 시간은 보내지 않는다. 시작 시각과 길이만 주면 브라우저가 카운트다운한다
        msg = {"t": "st", "s": self.state, "dur": self.duration}
        if self.t0 is not None:
            msg["t0"] = round(self.t0, 3)
        if self.t_end is not None:
            msg["el"] = round(self.t_end - self.t0, 2)  # 걸린 시간 (클리어 기록)
        if self.reason:
            msg["r"] = self.reason
        return json.dumps(msg)

    def gate_msg(self) -> str:
        # 문 상태가 바뀔 때만 보낸다. dw = 문 앞 구역에 들어온 시각 (머무는 진행률은 브라우저가 계산)
        return json.dumps({"t": "gt", "op": round(self.opened_at, 3) if self.opened_at else None,
                           "dw": round(self.dwell_from, 3) if self.dwell_from else None, "need": self.dwell_s})

    # ---- 상태 변경 ----
    async def _set_state(self, state: str, reason: str | None = None) -> None:
        self.state, self.reason = state, reason
        if state in ("clear", "over"):
            self.t_end = time.time()
            if state == "clear":
                self.last_clear = {"lv": self.lv, "time": round(self.t_end - self.t0, 2), "saved": False}
            if self.on_end:
                self.on_end()
        log.info("상태 %s%s", state, f" ({reason})" if reason else "")
        await self.broadcast(self.state_msg())

    async def start(self) -> None:
        if self.state == "run":
            return
        self._reset_round()
        self.t0 = time.time()
        await self.broadcast(self.collected_msg())
        await self.broadcast(self.gate_msg())
        await self._set_state("run")

    async def reset(self) -> None:
        self._reset_round()
        await self.broadcast(self.collected_msg())
        await self.broadcast(self.gate_msg())
        await self._set_state("ready")

    # ---- 판정 루프 ----
    async def run(self) -> None:
        while True:
            await asyncio.sleep(CHECK_PERIOD)
            if self.state != "run":
                continue
            now = time.time()
            if now >= self.t0 + self.duration:
                await self._set_state("over", "timeout")
                continue
            pose = self.bridge.pumpkin_pose()
            if pose is None:
                continue
            x, y, _ = pose
            await self._check_candies(x, y, now)
            if len(self.collected) == len(self.candies):
                await self._check_gate(x, y, now)

    async def _check_candies(self, x: float, y: float, now: float) -> None:
        for cid, (cx, cy) in self.candies.items():
            if cid in self.collected:
                continue
            d = math.hypot(x - cx, y - cy)
            if d <= self.radius:
                self.collected[cid] = now
                log.info("획득 %s (거리 %.2f m, %d/%d) 판정 시각 %.3f",
                         cid, d, len(self.collected), len(self.candies), now)
                await self.broadcast(json.dumps(
                    {"t": "cd", "id": cid, "n": len(self.collected), "ts": round(now, 4)}))

    async def _check_gate(self, x: float, y: float, now: float) -> None:
        if self.opened_at is None:
            inside = math.hypot(x - self.gate_front[0], y - self.gate_front[1]) <= self.zone_r
            if inside and self.dwell_from is None:
                self.dwell_from = now
                log.info("탈출문 앞 구역 진입")
                await self.broadcast(self.gate_msg())
            elif not inside and self.dwell_from is not None:
                self.dwell_from = None  # 구역을 벗어나면 처음부터 다시
                log.info("탈출문 앞 구역 이탈 (머무름 초기화)")
                await self.broadcast(self.gate_msg())
            elif inside and now - self.dwell_from >= self.dwell_s:
                self.opened_at, self.dwell_from = now, None
                log.info("탈출문 열림")
                await self.broadcast(self.gate_msg())
        elif math.hypot(x - self.gate[0], y - self.gate[1]) <= self.enter_r:
            await self._set_state("clear")
