"""FastAPI server — serves WebRTC signaling, WebSocket for UI updates,
and runs the Pipecat voice pipeline."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from loguru import logger

from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.cartesia.tts import CartesiaTTSService, GenerationConfig
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

from glarvis.context_injector import BoardContextInjector
from glarvis.orchestrator import Orchestrator
from glarvis.response_capture import ResponseCapture
from glarvis.task_manager import TaskManager
from glarvis.tools.examples import DebugContext, EnterSession, ExitSession, GetTime, ListDirectory, ListTools, SearchFiles, WriteBoard
from glarvis.transcript_capture import TranscriptCapture

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

SYSTEM_PROMPT = """\
You are Minerva, a deeply intelligent desktop voice assistant. Think efficient coworker, not chatbot.

Rules:
- Keep responses SHORT. One sentence max for most things. "Yep", "got it", "on it" are fine responses.
- If the user is just chatting, chat back briefly. Don't over-explain or monologue.
- Never list your capabilities or offer help unprompted. The user knows what you can do.
- Short answers (a sentence or less) can be spoken. Anything longer goes on the board.
- Don't read out lists, file contents, or structured data — post to the board instead.
- If you post to the board in response to the user, let them know briefly — "it's on the board", "take a look", etc. If nothing was asked, you don't need to announce it.
- If the user explicitly asks you to read or explain something, speak it fully.
- You can call multiple tools in sequence. Don't tell the user you can only do one thing at a time.
- No markdown, bullets, or special characters. This is spoken aloud.
"""

# SYSTEM_PROMPT = """\ # OLD
# You are Glarvis, a deeply intelligent desktop voice assistant. Think efficient coworker, not chatbot.

# Rules:
# - Talk in the first person to sound natural. Be friendly, but concise. 
# - Answer questions directly but briefly. If asked "can you hear me", say "yep!" not "got it".
# - For actions and commands, keep it short: "on it", "ok, done", "sure, let me do that".
# - Try not to explain what you did or summarize your actions, unless the user asks for it.
# - But if the user asks for details, give the details they ask for. User requests override these rules.
# - No markdown, bullets, or special characters. This is spoken aloud.
# """
# # - It is ok for tool calls to have no speech, if no speech is necessary. Silence is fine.
# # - Board results speak for themselves. Don't read them out, unleess the user specifies otherwise.
# # - Ignore speech not directed at you. Empty response, no tool calls.
# # """

app = FastAPI()
request_handler = SmallWebRTCRequestHandler()

# ── WebSocket connections for UI updates ──────────────────────────────────────

ws_clients: set[WebSocket] = set()
active_pipeline_task: PipelineTask | None = None
active_orchestrator: Orchestrator | None = None


async def broadcast(msg: dict):
    """Send a message to all connected WebSocket clients."""
    data = json.dumps(msg)
    disconnected = set()
    for client in ws_clients:
        try:
            await client.send_text(data)
        except Exception:
            disconnected.add(client)
    for client in disconnected:
        ws_clients.discard(client)


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
                if msg.get("type") == "user_text" and msg.get("text", "").strip():
                    await _inject_user_text(msg["text"].strip())
                elif msg.get("type") == "context_toggle" and msg.get("task_id"):
                    _handle_context_toggle(msg["task_id"])
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_clients.discard(websocket)
        logger.info(f"[WS] Client disconnected ({len(ws_clients)} total)")


def _handle_context_toggle(task_id: str):
    """Toggle session context when user clicks a session chip."""
    if not active_orchestrator:
        logger.warning("[Server] No active orchestrator for context toggle")
        return
    active_orchestrator.toggle_context(task_id)


async def _inject_user_text(text: str):
    """Inject typed text into the pipeline as if the user spoke it."""
    from pipecat.frames.frames import TranscriptionFrame

    if not active_pipeline_task:
        logger.warning("[Server] No active pipeline to inject text into")
        return

    logger.info(f'[Server] Injecting user text: "{text}"')
    frame = TranscriptionFrame(text=text, user_id="user", timestamp=str(time.time()))
    await active_pipeline_task.queue_frame(frame)


# ── WebRTC signaling ─────────────────────────────────────────────────────────

@app.post("/webrtc/offer")
async def webrtc_offer(request: dict):
    req = SmallWebRTCRequest.from_dict(request)
    answer = await request_handler.handle_web_request(req, on_new_connection)
    return answer


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
        if c.get("candidate")  # filter empty end-of-candidates signals
    ]
    patch = SmallWebRTCPatchRequest(pc_id=request["pc_id"], candidates=candidates)
    await request_handler.handle_patch_request(patch)
    return {"ok": True}


async def on_new_connection(webrtc_connection: SmallWebRTCConnection):
    """Called when a new WebRTC peer connects. Sets up and runs the pipeline in the background."""
    logger.info("[Server] New WebRTC connection, building pipeline...")

    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_passthrough=True,
        ),
    )

    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))

    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id=os.getenv("CARTESIA_VOICE_ID", "87748186-23bb-4158-a1eb-332911b0b708"),
        params=CartesiaTTSService.InputParams(
            generation_config=GenerationConfig(
                speed=1.25,
            )
        ),
    )

    llm = AnthropicLLMService(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model="claude-haiku-4-5-20251001",
    )

    # Set up tools and orchestrator
    task_manager = TaskManager()

    # Build orchestrator first so ListTools can reference it
    # We need a temporary context to construct the orchestrator, then rebuild with tools
    temp_context = LLMContext(messages=[{"role": "system", "content": SYSTEM_PROMPT}])
    orchestrator = Orchestrator(task_manager, llm, temp_context, pipeline_task=None)

    # Register all tools
    for tool in [GetTime(), ListDirectory(), SearchFiles(), WriteBoard()]:
        orchestrator.register(tool)
    orchestrator.register(ListTools(orchestrator))
    orchestrator.register(DebugContext(orchestrator))
    orchestrator.register(EnterSession(orchestrator))
    orchestrator.register(ExitSession(orchestrator))

    # Now build the real context with tools schema
    context = LLMContext(
        messages=[{"role": "system", "content": SYSTEM_PROMPT}],
        tools=orchestrator.get_tools_schema(),
    )
    orchestrator.context = context
    orchestrator._original_system_message = SYSTEM_PROMPT

    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(
                    confidence=0.8,
                    start_secs=0.2,
                    stop_secs=0.8,
                    min_volume=0.6,
                )
            ),
        ),
    )

    # Wire up UI broadcasting
    orchestrator.set_broadcast(broadcast)

    transcript_capture = TranscriptCapture(orchestrator)
    injector = BoardContextInjector(orchestrator)
    response_capture = ResponseCapture(orchestrator)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            transcript_capture,
            user_aggregator,
            injector,
            llm,
            response_capture,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    orchestrator.pipeline_task = task

    global active_pipeline_task, active_orchestrator
    active_pipeline_task = task
    active_orchestrator = orchestrator

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("[Server] Client connected to WebRTC")
        # Post available tools to the board on connect
        await orchestrator.broadcast_welcome()

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        global active_pipeline_task, active_orchestrator
        logger.info("[Server] Client disconnected from WebRTC")
        active_pipeline_task = None
        active_orchestrator = None
        await task.cancel()

    # Run pipeline in background so the HTTP response returns immediately
    runner = PipelineRunner(handle_sigint=False)
    asyncio.create_task(runner.run(task))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
