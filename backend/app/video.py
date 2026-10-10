import asyncio
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .protocol import Pose7, pack_video_frame

router = APIRouter()


class VideoHub:
    """카메라 스레드에서 받은 JPEG를 fps로 솎아 내고, 클라이언트마다 최신 프레임 1장만 들고 있다."""

    def __init__(self, loop: asyncio.AbstractEventLoop, fps: float):
        self.loop = loop
        self.min_gap = 0.9 / fps  # 카메라와 목표 fps가 같을 때 지터로 프레임이 빠지지 않게 여유를 둔다
        self.last = 0.0
        self.seq = 0
        self.clients: set["_Slot"] = set()

    def want_frame(self) -> bool:
        """카메라 콜백이 TF 조회 전에 먼저 묻는다. 버릴 프레임이면 조회 비용도 아낀다."""
        return bool(self.clients) and time.monotonic() - self.last >= self.min_gap

    def push(self, stamp: float, pose: Pose7 | None, jpeg: bytes) -> None:
        """카메라 스레드에서 호출. JPEG는 디코딩하지 않고 헤더만 붙인다."""
        self.last = time.monotonic()
        self.seq += 1
        frame = pack_video_frame(self.seq, stamp, pose, jpeg)
        self.loop.call_soon_threadsafe(self._fan_out, frame)

    def _fan_out(self, frame: bytes) -> None:
        for slot in self.clients:
            slot.frame = frame  # 아직 못 보낸 프레임은 덮어쓴다 (큐 길이 1)
            slot.ready.set()


class _Slot:
    def __init__(self):
        self.frame: bytes | None = None
        self.ready = asyncio.Event()


@router.websocket("/ws/video")
async def ws_video(ws: WebSocket):
    await ws.accept()
    hub: VideoHub = ws.app.state.video
    slot = _Slot()
    hub.clients.add(slot)

    async def sender():
        while True:
            await slot.ready.wait()
            slot.ready.clear()
            frame, slot.frame = slot.frame, None
            if frame:
                await ws.send_bytes(frame)

    task = asyncio.create_task(sender())
    try:
        # 클라이언트는 보내지 않는다. 끊김 감지용
        while (await ws.receive())["type"] != "websocket.disconnect":
            pass
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(slot)
        task.cancel()
