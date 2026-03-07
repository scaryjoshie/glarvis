"""Pipeline construction — builds the Pipecat voice pipeline and registers tools."""

from __future__ import annotations

import os
from typing import Any, Callable, Coroutine

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
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
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

from glarvis.context_injector import BoardContextInjector
from glarvis.input_interceptor import InputInterceptor
from glarvis.mute_gate import MuteGate
from glarvis.orchestrator import Orchestrator
from glarvis.response_capture import ResponseCapture
from glarvis.system import SystemMonitor
from glarvis.task_manager import TaskManager
from glarvis.tools.core import CloseBoard, DebugContext, EnterSession, ExitSession, ListTools, Mute
from glarvis.tools.general import (
    FocusWindow, GetTime, ListDirectory, OpenProgram,
    ReadFile, SearchFiles, SearchPrograms, WriteBoard,
)
from glarvis.tools.multi_choice import MultiChoiceSession
from glarvis.transcript_capture import TranscriptCapture


SYSTEM_PROMPT = """\
You are Minerva, a deeply intelligent desktop voice assistant. Think efficient coworker, not chatbot.

Rules:
- Keep responses SHORT. One sentence max for most things. "Yep", "got it", "on it" are fine responses.
- If the user is just chatting, chat back briefly. Don't over-explain or monologue.
- Never list your capabilities or offer help unprompted. The user knows what you can do.
- NEVER read lists aloud. Not windows, not files, not programs, not options. Post to board or use multi_choice instead.
- Short answers (a sentence or less) can be spoken. Anything longer goes on the board.
- If you post to the board in response to the user, let them know briefly — "it's on the board", "take a look", etc.
- If the user explicitly asks you to read or explain something, speak it fully.
- No markdown, bullets, or special characters. This is spoken aloud.
- You have live System State showing open windows, focused window, clipboard, and time. Use it — don't say you can't see what's open.

Tools:
- You can call multiple tools in one turn and chain them. Don't say you can only do one thing at a time.
- Some tools start sessions. While a session is active, extra context tools appear in your tool list (listed in the system state below). USE them — they are real tools you can call, not suggestions.
- CRITICAL: When a session is active (like show_choices), the user's responses go through its context tools. If show_choices is active and the user says a number or name, call select_option — NOT focus_window or any other tool. The context tool handles it.
- If the user wants something not in the listed options, use select_other with their request.
- After a selection is made, continue with whatever task prompted the choice. Don't stop.

Disambiguation — ALWAYS use show_choices when there are multiple options:
- Multiple windows match (e.g. two Notepad instances) → show_choices with the window titles
- Multiple programs match a search → show_choices with the program names
- Any time the user needs to pick from a list → show_choices, never read options aloud

Common workflows (call these tools in sequence):
- "Open X" / "Go to X": Check the window list first. If exactly one match, focus_window(id). If multiple matches, show_choices. If not open, search_programs("X") → open_program(exact_name).
- "Show me file X": read_file(path) posts to board.
"""


class PipelineSession:
    """Holds all state for a single voice pipeline session."""

    def __init__(self):
        self.task: PipelineTask | None = None
        self.orchestrator: Orchestrator | None = None
        self.mute_gate: MuteGate | None = None
        self.system_monitor: SystemMonitor | None = None

    async def teardown(self):
        """Clean up all resources."""
        if self.system_monitor:
            self.system_monitor.stop()
        if self.task:
            await self.task.cancel()
        self.task = None
        self.orchestrator = None
        self.mute_gate = None
        self.system_monitor = None


def build_session(
    transport: SmallWebRTCTransport,
    broadcast: Callable[[dict], Coroutine],
) -> PipelineSession:
    """Build a complete pipeline session with all tools and processors."""
    session = PipelineSession()

    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))

    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id=os.getenv("CARTESIA_VOICE_ID", "87748186-23bb-4158-a1eb-332911b0b708"),
        params=CartesiaTTSService.InputParams(
            generation_config=GenerationConfig(speed=1.25)
        ),
    )

    llm = AnthropicLLMService(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model="claude-sonnet-4-6",
    )

    # Orchestrator with temporary context (rebuilt after tool registration)
    task_manager = TaskManager()
    temp_context = LLMContext(messages=[{"role": "system", "content": SYSTEM_PROMPT}])
    orchestrator = Orchestrator(task_manager, llm, temp_context, pipeline_task=None)

    # Mute gate and system monitor
    mute_gate = MuteGate(broadcast=broadcast)
    system_monitor = SystemMonitor(interval=2.0)
    system_monitor.start()

    # Register all tools
    for tool in [
        GetTime(), ListDirectory(), SearchFiles(), WriteBoard(), CloseBoard(),
        MultiChoiceSession(), Mute(mute_gate),
        FocusWindow(system_monitor), SearchPrograms(system_monitor),
        OpenProgram(system_monitor), ReadFile(),
    ]:
        orchestrator.register(tool)
    orchestrator.register(ListTools(orchestrator))
    orchestrator.register(DebugContext(orchestrator))
    orchestrator.register(EnterSession(orchestrator))
    orchestrator.register(ExitSession(orchestrator))

    # Rebuild context with tools schema
    context = LLMContext(
        messages=[{"role": "system", "content": SYSTEM_PROMPT}],
        tools=orchestrator.get_tools_schema(),
    )
    orchestrator.context = context
    orchestrator._original_system_message = SYSTEM_PROMPT
    orchestrator.set_broadcast(broadcast)
    orchestrator.system_monitor = system_monitor

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

    pipeline = Pipeline([
        transport.input(),
        stt,
        mute_gate,
        TranscriptCapture(orchestrator),
        InputInterceptor(orchestrator),
        user_aggregator,
        BoardContextInjector(orchestrator),
        llm,
        ResponseCapture(orchestrator),
        tts,
        transport.output(),
        assistant_aggregator,
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    orchestrator.pipeline_task = task

    session.task = task
    session.orchestrator = orchestrator
    session.mute_gate = mute_gate
    session.system_monitor = system_monitor

    return session
