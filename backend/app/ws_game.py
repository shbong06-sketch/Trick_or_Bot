import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
log = logging.getLogger("game")

POSE_PERIOD = 0.2  # 5 Hz


def _short(pose):
    return [round(pose[0], 2), round(pose[1], 2), round(pose[2], 2)]


async def _send_pose(ws: WebSocket, bridge) -> None:
    """두 로봇 위치를 한 메시지로 5 Hz. a = 펌킨, b = 부우 (모르면 키 생략)."""
    while True:
        msg = {"t": "p"}
        if (a := bridge.pumpkin_pose()) is not None:
            msg["a"] = _short(a)
        if (b := bridge.boo_pose()) is not None:
            msg["b"] = _short(b)
        if len(msg) > 1:
            await ws.send_text(json.dumps(msg, separators=(",", ":")))
        await asyncio.sleep(POSE_PERIOD)


async def _notify(ws: WebSocket, text: str) -> None:
    try:
        await ws.send_text(text)
    except Exception:
        pass  # 이미 끊긴 연결


@router.websocket("/ws/game")
async def ws_game(ws: WebSocket):
    await ws.accept()
    teleop = ws.app.state.teleop
    game = ws.app.state.game
    game.clients.add(ws)
    await ws.send_text(game.state_msg())      # 늦게 들어온 화면도 진행 상태·시작 시각을 안다
    await ws.send_text(game.collected_msg())  # 이미 먹은 사탕은 안 그린다
    await ws.send_text(game.gate_msg())       # 탈출문이 이미 열렸는지
    pose_task = asyncio.create_task(_send_pose(ws, ws.app.state.bridge))
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            t = msg.get("t")
            if t == "k" and msg.get("b") and ws is not teleop.owner:
                # 조작권은 실제로 키를 누른 탭이 가져간다. 이전 탭은 정지시키고 보기 전용으로 알린다
                prev, teleop.owner = teleop.owner, ws
                if prev is not None:
                    teleop.halt("다른 탭이 조작권을 가져감")
                    await _notify(prev, '{"t":"busy"}')
                await ws.send_text('{"t":"own"}')
            if t == "k" and game.state in ("clear", "over"):
                t = "k-ignored"  # 회차가 끝나면 다음 시작 전까지 로봇을 움직이지 않는다
            if ws is teleop.owner:
                if t == "k":
                    teleop.on_keys(int(msg.get("b", 0)) & 0xF)
                elif t == "h":
                    teleop.on_heartbeat()
            if t == "start":
                # 시작한 탭이 조작권도 가져간다
                if ws is not teleop.owner:
                    prev, teleop.owner = teleop.owner, ws
                    if prev is not None:
                        teleop.halt("다른 탭이 조작권을 가져감")
                        await _notify(prev, '{"t":"busy"}')
                    await ws.send_text('{"t":"own"}')
                await game.start()
            if t == "cdlog":
                # 브라우저가 보고한 측정값 (서버 시계 기준으로 환산된 ms)
                log.info("측정 %s: 판정→수신 %.0f ms, 판정→화면에서 사라짐 %.0f ms",
                         msg.get("id"), float(msg.get("rx", -1)), float(msg.get("gone", -1)))
            if t in ("k", "k-ignored", "h", "ping"):
                # 왕복 지연 측정용: c는 클라이언트 시각을 그대로 돌려준다.
                # st(서버 시각, s)로 브라우저가 서버와의 시계 차이를 추정해 영상 지연을 계산한다
                await ws.send_text(json.dumps(
                    {"t": "a", "s": msg.get("s"), "c": msg.get("c"), "st": round(time.time(), 4)}))
    except (WebSocketDisconnect, json.JSONDecodeError, ValueError, AttributeError):
        pass
    finally:
        pose_task.cancel()
        game.clients.discard(ws)
        if ws is teleop.owner:
            teleop.owner = None
            teleop.halt("WebSocket 끊김")
