"""FastAPI server — WebRTC signaling, WebSocket for UI updates."""

import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from loguru import logger
from pipecat.frames.frames import TranscriptionFrame
from pipecat.pipeline.runner import PipelineRunner
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

from glarvis.pipeline import PipelineSession, build_session

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

app = FastAPI()
request_handler = SmallWebRTCRequestHandler()

# ── Session state ─────────────────────────────────────────────────────────────

ws_clients: set[WebSocket] = set()
session: PipelineSession | None = None


async def broadcast(msg: dict):
    data = json.dumps(msg)
    disconnected = set()
    for client in ws_clients:
        try:
            await client.send_text(data)
        except Exception:
            disconnected.add(client)
    for client in disconnected:
        ws_clients.discard(client)


@app.on_event("shutdown")
async def shutdown():
    global session
    logger.info("[Server] Shutting down...")
    if session:
        await session.teardown()
        session = None


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_clients.add(websocket)
    logger.info(f"[WS] Client connected ({len(ws_clients)} total)")
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                await _handle_ws_message(msg)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_clients.discard(websocket)
        logger.info(f"[WS] Client disconnected ({len(ws_clients)} total)")


async def _handle_ws_message(msg: dict):
    msg_type = msg.get("type")
    if msg_type == "user_text" and msg.get("text", "").strip():
        await _inject_user_text(msg["text"].strip())
    elif msg_type == "context_toggle" and msg.get("task_id"):
        if session and session.orchestrator:
            session.orchestrator.toggle_context(msg["task_id"])
    elif msg_type == "soft_unmute":
        if session and session.mute_gate and session.mute_gate.muted:
            await session.mute_gate.set_muted(False)
    elif msg_type == "hard_mute":
        if session and session.mute_gate:
            session.mute_gate.hard_muted = msg.get("muted", False)
    elif msg_type == "popup_action":
        if session and session.orchestrator:
            await session.orchestrator.handle_popup_action(
                msg.get("tool_name", ""), msg.get("action", ""), msg.get("data", {}),
            )


async def _inject_user_text(text: str):
    if not session or not session.task:
        return
    logger.info(f'[Server] Injecting user text: "{text}"')
    frame = TranscriptionFrame(text=text, user_id="user", timestamp=str(time.time()))
    await session.task.queue_frame(frame)


# ── WebRTC signaling ─────────────────────────────────────────────────────────

@app.post("/webrtc/offer")
async def webrtc_offer(request: dict):
    req = SmallWebRTCRequest.from_dict(request)
    return await request_handler.handle_web_request(req, on_new_connection)


@app.post("/webrtc/ice")
async def webrtc_ice(request: dict):
    from pipecat.transports.smallwebrtc.request_handler import (
        IceCandidate,
        SmallWebRTCPatchRequest,
    )
    candidates = [
        IceCandidate(
            candidate=c["candidate"],
            sdp_mid=c["sdpMid"],
            sdp_mline_index=c["sdpMLineIndex"],
        )
        for c in request.get("candidates", [])
        if c.get("candidate")
    ]
    patch = SmallWebRTCPatchRequest(pc_id=request["pc_id"], candidates=candidates)
    await request_handler.handle_patch_request(patch)
    return {"ok": True}


async def on_new_connection(webrtc_connection: SmallWebRTCConnection):
    global session

    # Tear down previous session
    if session:
        logger.info("[Server] Cancelling previous pipeline before new connection")
        await session.teardown()
        session = None

    logger.info("[Server] New WebRTC connection, building pipeline...")

    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_passthrough=True,
        ),
    )

    session = build_session(transport, broadcast)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("[Server] Client connected to WebRTC")
        await session.orchestrator.broadcast_welcome()

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        global session
        logger.info("[Server] Client disconnected from WebRTC")
        if session:
            await session.teardown()
            session = None

    runner = PipelineRunner(handle_sigint=False)
    asyncio.create_task(runner.run(session.task))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
