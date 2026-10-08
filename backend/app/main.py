from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .bridge import create_bridge
from .levels import load_level
from .settings import MOCK, STATIC_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bridge = create_bridge(MOCK)
    app.state.bridge.start()
    yield
    app.state.bridge.stop()


app = FastAPI(title="Trick-or-Bot game server", lifespan=lifespan)


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
