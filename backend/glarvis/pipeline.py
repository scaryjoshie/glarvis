"""Pipeline construction — builds the Pipecat voice pipeline and registers tools."""

from __future__ import annotations

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
from glarvis.services import create_llm, create_tts, create_stt
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

from glarvis.context_injector import BoardContextInjector
from glarvis.input_interceptor import InputInterceptor
from glarvis.mute_gate import MuteGate
from glarvis.orchestrator import Orchestrator
from glarvis.prompt import BASE_PROMPT
from glarvis.response_capture import ResponseCapture
from glarvis.system import SystemMonitor
from glarvis.task_manager import TaskManager
from glarvis.tools.core import CloseBoard, DebugContext, EnterSession, ExitSession, ListTools, Mute, OpenSettings, Restart, Shutdown
from glarvis.tools.general import (
    FocusWindow, GetTime, ListDirectory, OpenProgram,
    ReadFile, SearchFiles, SearchPrograms, SwitchWindow, WriteBoard,
)
from glarvis.settings import load_settings
from glarvis.tools.multi_choice import MultiChoiceSession
from glarvis.tools.transcriber import TranscriberSession
from glarvis.transcript_capture import TranscriptCapture


class PipelineSession:
    """Holds all state for a single voice pipeline session."""

    def __init__(self):
        self.task: PipelineTask | None = None
        self.orchestrator: Orchestrator | None = None
        self.mute_gate: MuteGate | None = None
        self.system_monitor: SystemMonitor | None = None
        self.model_display: str = ""

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
    settings = load_settings()
    session = PipelineSession()
    session.model_display = settings.llm.display_name

    stt = create_stt(settings.stt.provider, settings.stt.model, settings.stt.api_key)
    tts = create_tts(settings.tts.provider, settings.tts.voice_id, settings.tts.api_key)
    llm = create_llm(settings.llm.provider, settings.llm.model, settings.llm.api_key)

    # Orchestrator and Context
    task_manager = TaskManager()
    context = LLMContext(messages=[{"role": "system", "content": BASE_PROMPT}])
    
    # Mute gate and system monitor
    mute_gate = MuteGate(broadcast=broadcast)
    system_monitor = SystemMonitor()
    system_monitor.start()

    orchestrator = Orchestrator(
        task_manager, llm, context,
        broadcast=broadcast, system_monitor=system_monitor
    )
    system_monitor.on_focus_change = orchestrator.on_focus_change

    # Register all tools
    for tool in [
        GetTime(), ListDirectory(), SearchFiles(), WriteBoard(), CloseBoard(),
        MultiChoiceSession(), TranscriberSession(), Mute(mute_gate), OpenSettings(),
        SwitchWindow(), FocusWindow(), SearchPrograms(), OpenProgram(), ReadFile(),
    ]:
        orchestrator.register(tool)
    orchestrator.register(Shutdown())
    orchestrator.register(Restart())
    orchestrator.register(ListTools(orchestrator))
    orchestrator.register(DebugContext(orchestrator))
    orchestrator.register(EnterSession(orchestrator))
    orchestrator.register(ExitSession(orchestrator))

    # Rebuild context with gathered tools schema
    context.set_tools(orchestrator.get_tools_schema())

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

    orchestrator.set_pipeline_task(task)

    session.task = task
    session.orchestrator = orchestrator
    session.mute_gate = mute_gate
    session.system_monitor = system_monitor

    return session
