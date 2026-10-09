import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .bridge import create_bridge
from .game import Game
from .levels import load_level, pack_occ
from .settings import MOCK, ROBOT, STATIC_DIR
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
    yield
    game_task.cancel()
    teleop_task.cancel()
    teleop.halt("서버 종료")
    bridge.stop()


app = FastAPI(title="Trick-or-Bot game server", lifespan=lifespan)
app.include_router(ws_game_router)
app.include_router(video_router)


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
        "mock": MOCK,
    }


@app.post("/api/game/start")
async def start_game():
    """회차 시작 (운영자용). 플레이어 화면에서는 Enter로 시작한다."""
    await app.state.game.start()
    return {"state": app.state.game.state}


@app.post("/api/game/reset")
async def reset_game():
    """시작 전 상태로 되돌린다. 로봇 복귀는 이후 단계."""
    await app.state.game.reset()
    return {"state": app.state.game.state}


# API 라우트 뒤에 마운트해야 /api가 가려지지 않는다
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
