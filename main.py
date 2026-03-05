import asyncio
import os
import sys

from dotenv import load_dotenv
from loguru import logger

from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams

from glarvis.board import Board
from glarvis.context_injector import BoardContextInjector
from glarvis.gate import SpeechGate
from glarvis.orchestrator import Orchestrator
from glarvis.tools.examples import GetTime, ListDirectory, SearchFiles

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

SYSTEM_PROMPT = """\
You are Glarvis, a terse voice assistant. Think efficient coworker, not chatbot.

Rules:
- Answer questions directly but briefly. If asked "can you hear me", say "yep!" not "got it".
- For actions and commands, keep it short: "on it", "done", "sure".
- Don't explain what you did or summarize actions unprompted.
- But if the user asks for details, give the details they ask for. User requests override these rules.
- No markdown, bullets, or special characters. This is spoken aloud.
- Tool calls can have no speech. Silence is fine.
- Board results speak for themselves. Don't read them out.
- Ignore speech not directed at you. Empty response, no tool calls."""


async def main():
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        )
    )

    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))

    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id=os.getenv("CARTESIA_VOICE_ID", "87748186-23bb-4158-a1eb-332911b0b708"),
    )
    # 694f9389-aac1-45b6-b726-9d9369183238 Sarah
    # 8d8ce8c9-44a4-46c4-b10f-9a927b99a853 Connie
    # 146485fd-8736-41c7-88a8-7cdd0da34d84 Tim
    # 71a7ad14-091c-4e8e-a314-022ece01c121 Charlotte
    # 7ea5e9c2-b719-4dc3-b870-5ba5f14d31d8 Janvi
    # f8f5f1b2-f02d-4d8e-a40d-fd850a487b3d Kiara
    # 87bc56aa-ab01-4baa-9071-77d497064686 Jordan
    # f114a467-c40a-4db8-964d-aaba89cd08fa Miles
    # daf747c6-6bc2-4083-bd59-aa94dce23f5d Yasmin
    # 87748186-23bb-4158-a1eb-332911b0b708 Za wizard
    # 6d287143-8db3-434a-959c-df147192da27 Stacy
    # 56b87df1-594d-4135-992c-1112bb504c59 Lexi
    # 7d7d769c-5ab1-4dd5-bb17-ec8d4b69d03d Eleanor
    # f80e7298-93f5-46d0-86f2-b8f29cfc88bd Claudia
    # 98c87826-dba2-44f4-b123-4c7e3c8a2647 Madison
    # 02fe5732-a072-4767-83e3-a91d41d274ca Madison best friend


    llm = OpenAILLMService(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL") or None,
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
    )

    # Set up tools
    board = Board()
    tools = [GetTime(), ListDirectory(), SearchFiles()]
    tools_schema = ToolsSchema(standard_tools=[t.to_function_schema() for t in tools])

    context = LLMContext(
        messages=[{"role": "system", "content": SYSTEM_PROMPT}],
        tools=tools_schema,
    )

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

    # Orchestrator needs a reference to the pipeline task for notification delivery.
    # We create it with a None task first, then set it after pipeline construction.
    orchestrator = Orchestrator(board, llm, context, pipeline_task=None)
    for tool in tools:
        orchestrator.register(tool)

    injector = BoardContextInjector(orchestrator)
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            injector,
            llm,
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

    # Now give the orchestrator its pipeline task reference
    orchestrator.pipeline_task = task

    logger.info("Glarvis is listening. Say 'Glarvis' to activate.")

    runner = PipelineRunner(handle_sigint=False if sys.platform == "win32" else True)
    await runner.run(task)


if __name__ == "__main__":
    asyncio.run(main())
