"""FastAPI server — WebRTC signaling, WebSocket for UI updates."""

import asyncio
import json
import sys
import time
from contextlib import asynccontextmanager
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
from glarvis.services import (
    get_status as get_service_status,
    add_service_item,
    remove_service_item,
    edit_service_voice,
    set_provider_speed,
)
from glarvis.settings import LLMSettings, TTSSettings, STTSettings, Settings, load_settings, save_settings

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Shutdown
    global session
    logger.info("[Server] Shutting down...")
    if session:
        await session.teardown()
        session = None


app = FastAPI(lifespan=lifespan)
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


# ── REST endpoints ────────────────────────────────────────────────────────────

def _settings_payload(settings: Settings) -> dict:
    status = get_service_status()
    return {
        "llm": {
            "provider": settings.llm.provider,
            "model": settings.llm.model,
            "has_override": bool(settings.llm.api_key),
        },
        "tts": {
            "provider": settings.tts.provider,
            "voice_id": settings.tts.voice_id,
            "has_override": bool(settings.tts.api_key),
        },
        "stt": {
            "provider": settings.stt.provider,
            "model": settings.stt.model,
            "has_override": bool(settings.stt.api_key),
        },
        "services": status,
    }


@app.get("/api/settings")
async def get_settings(reload: bool = False):
    if reload:
        from glarvis.services.registry import reload_config
        reload_config()
    settings = load_settings()
    return _settings_payload(settings)


@app.post("/api/services/add")
async def api_add_item(body: dict):
    ok = add_service_item(body["service_type"], body["provider"], body["item"])
    return {"ok": ok, "services": get_service_status()}


@app.post("/api/services/remove")
async def api_remove_item(body: dict):
    ok = remove_service_item(body["service_type"], body["provider"], body["item_id"])
    return {"ok": ok, "services": get_service_status()}


@app.post("/api/services/edit-voice")
async def api_edit_voice(body: dict):
    ok = edit_service_voice(body["provider"], body["voice_id"], body.get("updates", {}))
    return {"ok": ok, "services": get_service_status()}


@app.post("/api/services/speed")
async def api_set_speed(body: dict):
    speed = body.get("speed")
    ok = set_provider_speed(body["provider"], float(speed) if speed is not None else None)
    return {"ok": ok, "services": get_service_status()}


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
    elif msg_type == "get_settings":
        settings = load_settings()
        payload = _settings_payload(settings)
        payload["type"] = "settings"
        await broadcast(payload)
    elif msg_type == "save_settings":
        existing = load_settings()
        llm_data = msg.get("llm", {})
        tts_data = msg.get("tts", {})
        stt_data = msg.get("stt", {})
        # api_key: null/absent = keep existing, "" = clear, "sk-..." = set new
        llm_key = llm_data.get("api_key")
        tts_key = tts_data.get("api_key")
        stt_key = stt_data.get("api_key")
        settings = Settings(
            llm=LLMSettings(
                provider=llm_data.get("provider", "anthropic"),
                model=llm_data.get("model", "claude-sonnet-4-6"),
                api_key=existing.llm.api_key if llm_key is None else llm_key,
            ),
            tts=TTSSettings(
                provider=tts_data.get("provider", "cartesia"),
                voice_id=tts_data.get("voice_id", ""),
                api_key=existing.tts.api_key if tts_key is None else tts_key,
            ),
            stt=STTSettings(
                provider=stt_data.get("provider", "deepgram"),
                model=stt_data.get("model", ""),
                api_key=existing.stt.api_key if stt_key is None else stt_key,
            ),
        )
        save_settings(settings)
        logger.info(f"[Server] Settings saved: LLM={settings.llm.provider}/{settings.llm.model} TTS={settings.tts.provider} STT={settings.stt.provider}")
        await broadcast({"type": "settings_saved", "model_display": settings.llm.display_name})


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


session_lock = asyncio.Lock()
runner_task: asyncio.Task | None = None

async def on_new_connection(webrtc_connection: SmallWebRTCConnection):
    global session, runner_task

    async with session_lock:
        # Tear down previous session
        if session:
            logger.info("[Server] Cancelling previous pipeline before new connection")
            await session.teardown()
            session = None
        if runner_task and not runner_task.done():
            runner_task.cancel()
            runner_task = None

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

    # Capture reference so disconnect handler only tears down its own session
    this_session = session

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("[Server] Client connected to WebRTC")
        if session is this_session:
            await broadcast({"type": "model_info", "model_display": this_session.model_display})
            await this_session.orchestrator.broadcast_welcome()

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        global session
        logger.info("[Server] Client disconnected from WebRTC")
        if session is this_session:
            await session.teardown()
            session = None

    runner = PipelineRunner(handle_sigint=False)
    runner_task = asyncio.create_task(runner.run(session.task))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
