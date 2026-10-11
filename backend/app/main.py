import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .bridge import create_bridge
from .game import Game
from .levels import list_levels, load_level, pack_occ
from .records import Records
from .settings import BACKEND_DIR, MOCK, ROBOT, STATIC_DIR
from .teleop import Teleop
from .video import VideoHub
from .video import router as video_router
from .ws_game import router as ws_game_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    level = load_level(1)
    bridge = create_bridge(MOCK, level)
    video = VideoHub(asyncio.get_running_loop(), level["video_fps"])
    bridge.set_video_sink(video)
    bridge.start()
    teleop = Teleop(bridge, ROBOT["pumpkin"])
    teleop_task = asyncio.create_task(teleop.run())
    game = Game(level, bridge)
    game.on_end = lambda: teleop.halt("회차 종료")
    game_task = asyncio.create_task(game.run())
    app.state.bridge, app.state.teleop, app.state.video, app.state.game = bridge, teleop, video, game
    app.state.records = Records()
    yield
    app.state.records.close()
    game_task.cancel()
    teleop_task.cancel()
    teleop.halt("서버 종료")
    bridge.stop()


app = FastAPI(title="Trick-or-Bot game server", lifespan=lifespan)
app.include_router(ws_game_router)
app.include_router(video_router)


@app.get("/api/levels")
def get_levels():
    """설정이 준비된 레벨 목록. 레벨 선택 화면이 시작 가능 여부를 표시하는 데 쓴다."""
    return list_levels()


@app.get("/api/session")
def get_session(lv: int = 1):
    """게임 시작 시 한 번만 받는 정적 데이터: 레벨 설정 + 맵 메타 + 카메라 내부 파라미터."""
    try:
        cfg = load_level(lv)
    except FileNotFoundError:
        raise HTTPException(404, f"level {lv} 없음")
    return {
        "lv": cfg["lv"],
        "name": cfg["name"],
        "time": cfg["time_limit_s"],
        "pickR": cfg["pick_radius_m"],
        "candies": cfg["candies"],
        "gate": {**cfg["gate"], "front": cfg["gate_front_m"], "zoneR": cfg["gate_zone_r"],
                 "dwell": cfg["gate_dwell_s"], "enterR": cfg["gate_enter_r"]},
        # 점유 격자는 비트로 묶어 여기서 한 번만 보낸다 (브라우저 가림 처리용)
        "map": {**{k: v for k, v in cfg["map"].items() if k != "occ"}, "occ": pack_occ(cfg["map"]["occ"])},
        "cam": app.state.bridge.camera_info(),
        "net": {"fps": cfg["video_fps"]},
        "hud": {"hearts": cfg.get("hearts", 3), "heartbeatR": cfg.get("heartbeat_radius_m", 2.0),
                "cctv": len(cfg.get("cctv") or [])},
        "mock": MOCK,
    }


@app.post("/api/game/start")
async def start_game():
    """회차 시작 (운영자용). 플레이어 화면에서는 Enter로 시작한다."""
    if (err := await app.state.game.start()) is not None:
        raise HTTPException(409, err)
    return {"state": app.state.game.state}


@app.post("/api/game/reset")
async def reset_game():
    """시작 전 상태로 되돌린다. 로봇 복귀는 이후 단계."""
    if (err := await app.state.game.reset()) is not None:
        raise HTTPException(409, err)
    return {"state": app.state.game.state}


class RecordIn(BaseModel):
    nickname: str = Field(min_length=1, max_length=12)


@app.post("/api/records")
def save_record(body: RecordIn):
    """방금 클리어한 회차를 닉네임과 함께 저장한다. 기록 시간은 서버가 판정한 값만 쓴다."""
    clear = app.state.game.last_clear
    if clear is None or app.state.game.state != "clear":
        raise HTTPException(409, "저장할 클리어 기록이 없습니다")
    if clear["saved"]:
        raise HTTPException(409, "이미 저장한 기록입니다")
    nickname = body.nickname.strip()
    if not nickname:
        raise HTTPException(422, "닉네임을 입력하세요")
    rid = app.state.records.add(clear["lv"], nickname, clear["time"])
    clear["saved"] = True
    return {"id": rid, "lv": clear["lv"], "time": clear["time"]}


class HudPreview(BaseModel):
    sg: float | None = None     # 의심 게이지 0~1
    bs: str | None = None       # 부우 상태
    cc: int | None = None       # CCTV 감지 0/1
    hit: bool = False           # 피격 1회


@app.post("/api/debug/hud")
async def debug_hud(body: HudPreview):
    """mock 전용: 부우 판단 로직이 붙기 전에 HUD(하트·추적·의심·CCTV) 화면을 미리 보기 위한 값 주입."""
    if not MOCK:
        raise HTTPException(403, "mock 모드에서만 쓸 수 있습니다")
    game = app.state.game
    await game.set_hud(**{k: v for k, v in body.model_dump().items() if k != "hit" and v is not None})
    if body.hit:
        await game.hit()
    return game.hud


@app.get("/api/leaderboard")
def leaderboard(lv: int = 1, limit: int = 10):
    return {"lv": lv, "records": app.state.records.top(lv, max(1, min(limit, 100)))}


# API 라우트 뒤에 마운트해야 /api가 가려지지 않는다
# /proto = 백엔드 단독 시험용 화면, / = React 앱 빌드 결과 (frontend/dist, 없으면 시험용 화면)
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
app.mount("/proto", StaticFiles(directory=STATIC_DIR, html=True), name="proto")
app.mount("/", StaticFiles(directory=FRONTEND_DIST if FRONTEND_DIST.is_dir() else STATIC_DIR, html=True), name="web")
