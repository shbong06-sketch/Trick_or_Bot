import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .bridge import create_bridge
from .levels import load_level
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
    app.state.bridge, app.state.teleop, app.state.video = bridge, teleop, video
    yield
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
        "map": cfg["map"],
        "cam": app.state.bridge.camera_info(),
        "net": {"fps": cfg["video_fps"]},
        "mock": MOCK,
    }


# API 라우트 뒤에 마운트해야 /api가 가려지지 않는다
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
