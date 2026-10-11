import asyncio
import json
import logging
import math
import time

from .bridge import Bridge

log = logging.getLogger("game")

CHECK_PERIOD = 0.1  # 10 Hz. 획득 판정 → 화면 사라짐 0.5 s 예산에서 판정 지연이 최대 0.1 s
T0_TOLERANCE_S = 0.5  # GameState 경과시간으로 다시 계산한 시작 시각이 이만큼 어긋나면 화면에 다시 보낸다

# tob_interfaces/msg/GameState.msg phase → 화면 상태. 웹에는 일시정지 화면이 없어 PAUSED는 run으로 보인다
PHASE_TO_WEB = {0: "ready", 1: "run", 2: "run", 3: "clear", 4: "over"}
# game_manager(tob_game/rules.py) 실패 사유 → 화면이 구분하는 사유
REASON_TO_WEB = {"하트 소진": "caught", "제한시간 초과": "timeout"}


class Game:
    """회차 상태. 사탕 획득·탈출문·시간 초과는 서버만 판정하고, 결과를 모든 화면에 이벤트로 보낸다.

    상태: ready(시작 전) → run(진행 중) → clear(탈출 성공) | over(시간 초과)
    탈출문: 잠김 → (사탕을 다 모은 뒤 문 앞 구역에서 dwell_s 머무름) → 열림 → (문 지점 도착) → clear

    bridge.remote_game(ROS)이면 판정은 game_manager가 하고, 여기서는 GameState를 같은 화면 메시지로 옮긴다.
    이때 탈출문은 사탕을 다 모으면 바로 열린다 (game_manager에는 문 앞 대기 규칙이 없다).
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
        self.max_hearts = int(level.get("hearts", 3))

        self.clients: set = set()              # /ws/game 연결들
        self.on_end = None                     # clear·over 때 호출 (로봇 정지)
        self._starting = False                 # game_manager START 응답을 기다리는 중
        self.round_id = ""                     # game_manager 회차 ID (remote_game일 때만)
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
        # HUD: 하트·부우 상태·의심 게이지·CCTV 감지. 부우 판단 로직이 set_hud()/hit()로 채운다 (지금은 mock 미리보기만)
        self.hud = {"hp": self.max_hearts, "bs": "patrol", "sg": 0.0, "cc": 0}

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

    def hud_msg(self) -> str:
        return json.dumps({"t": "hud", **self.hud, "max": self.max_hearts}, separators=(",", ":"))

    async def set_hud(self, **changes) -> None:
        """바뀐 값이 있을 때만 보낸다. bs = patrol|suspect|chase|search|return, sg = 의심 0~1, cc = CCTV 감지 0/1"""
        if "sg" in changes:
            changes["sg"] = round(min(1.0, max(0.0, float(changes["sg"]))), 2)
        changed = {k: v for k, v in changes.items() if k in self.hud and self.hud[k] != v}
        if changed:
            self.hud.update(changed)
            await self.broadcast(self.hud_msg())

    async def hit(self) -> None:
        """부우에게 맞음: 하트 1개 감소. 0이 되면 게임오버 (체포 판정 기준은 아직 미정)"""
        if self.state != "run" or self.hud["hp"] <= 0:
            return
        self.hud["hp"] -= 1
        log.info("피격: 하트 %d/%d", self.hud["hp"], self.max_hearts)
        await self.broadcast(json.dumps({"t": "hit", "hp": self.hud["hp"]}))
        await self.broadcast(self.hud_msg())
        if self.hud["hp"] == 0:
            await self._set_state("over", "caught")

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

    async def start(self) -> str | None:
        """회차 시작. game_manager가 START를 거절하면 시작하지 않고 사유를 돌려준다."""
        if self.state == "run" or self._starting:
            return None
        self._starting = True
        try:
            accepted, message = await self.bridge.request_start(self.lv)
        finally:
            self._starting = False
        if not accepted:
            log.warning("시작 거절: %s", message)
            return message or "게임 관리자가 시작을 거절했습니다"
        if self.bridge.remote_game:
            return None  # 화면 상태는 다음 GameState로 바뀐다
        self.bridge.reset_pumpkin()
        self._reset_round()
        self.t0 = time.time()
        await self.broadcast(self.collected_msg())
        await self.broadcast(self.gate_msg())
        await self.broadcast(self.hud_msg())
        await self._set_state("run")

    async def reset(self) -> str | None:
        """시작 전 상태로. game_manager가 RESET을 거절하면 사유를 돌려준다."""
        if self.bridge.remote_game:
            accepted, message = await self.bridge.request_reset(self.round_id)
            if not accepted:
                log.warning("초기화 거절: %s", message)
                return message or "게임 관리자가 초기화를 거절했습니다"
            return None  # 화면 상태는 다음 GameState로 바뀐다
        self.bridge.reset_pumpkin()
        self._reset_round()
        await self.broadcast(self.collected_msg())
        await self.broadcast(self.gate_msg())
        await self.broadcast(self.hud_msg())
        await self._set_state("ready")
        return None

    # ---- 판정 루프 ----
    async def run(self) -> None:
        while True:
            await asyncio.sleep(CHECK_PERIOD)
            if self.bridge.remote_game:
                if (gs := self.bridge.game_state()) is not None:
                    await self._sync(gs)
                continue
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

    async def _sync(self, gs: dict) -> None:
        """game_manager의 GameState를 기존 화면 메시지(st·cds·cd·gt·hud·hit)로 옮긴다. 바뀐 것만 보낸다."""
        now = time.time()
        if gs["round_id"] != self.round_id:
            # 새 회차 또는 초기화: 이전 회차의 사탕·하트·문 표시를 지운다
            self.round_id = gs["round_id"]
            self._reset_round()
            await self.broadcast(self.collected_msg())
            await self.broadcast(self.gate_msg())
            await self.broadcast(self.hud_msg())
        for cid in gs["collected"]:
            if cid not in self.collected:
                self.collected[cid] = now
                log.info("획득 %s (game_manager, %d/%d)", cid, len(self.collected), gs["candy_total"])
                await self.broadcast(json.dumps(
                    {"t": "cd", "id": cid, "n": len(self.collected), "ts": round(now, 4)}))
        if gs["max_hp"] and (gs["max_hp"] != self.max_hearts or gs["hp"] != self.hud["hp"]):
            if gs["hp"] < self.hud["hp"]:
                log.info("피격 (game_manager): 하트 %d/%d", gs["hp"], gs["max_hp"])
                await self.broadcast(json.dumps({"t": "hit", "hp": gs["hp"]}))
            self.max_hearts, self.hud["hp"] = gs["max_hp"], gs["hp"]
            await self.broadcast(self.hud_msg())
        if gs["exit_enabled"] and self.opened_at is None:
            self.opened_at = now
            await self.broadcast(self.gate_msg())

        state = PHASE_TO_WEB.get(gs["phase"], "ready")
        if gs["elapsed_s"] + gs["remaining_s"] > 0:
            self.duration = round(gs["elapsed_s"] + gs["remaining_s"], 2)
        # 브라우저는 시작 시각 t0으로 카운트다운한다. 경과시간에서 거꾸로 계산하고 어긋날 때만 다시 보낸다
        t0 = now - gs["elapsed_s"] if state != "ready" else None
        t0_moved = t0 is not None and (self.t0 is None or abs(self.t0 - t0) > T0_TOLERANCE_S)
        if state != self.state:
            self.t0 = t0
            await self._set_state(state, REASON_TO_WEB.get(gs["reason"], gs["reason"]) or None)
        elif state == "run" and t0_moved:
            self.t0 = t0
            await self.broadcast(self.state_msg())

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
