import asyncio
import os
import sys

from dotenv import load_dotenv
from loguru import logger

from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
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
from glarvis.orchestrator import Orchestrator
from glarvis.tools.examples import GetTime, ListDirectory, SearchFiles

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

SYSTEM_PROMPT = """\
You are Glarvis, a friendly and sharp voice assistant. You speak naturally \
and conversationally, like a knowledgeable friend — not a corporate chatbot. \
Keep responses concise since they'll be spoken aloud. Avoid bullet points, \
markdown, or special characters. Be warm but not sycophantic. If you don't \
know something, just say so.

When you use tools, follow these guidelines:
- If a tool says results display on the board, don't read the results aloud. \
Just confirm you started the action or give a brief summary.
- You can call tools while speaking. For example, say "sure, looking that up" \
and call the tool in the same response.
- Check the Board State section (if present) to see active tasks and results. \
If a notification says the user was already notified, you don't need to repeat it."""


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
        voice_id=os.getenv("CARTESIA_VOICE_ID", "dc30854e-e398-4579-9dc8-16f6cb2c19b9"),
    )

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
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
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

    # Kick off with a greeting
    context.add_message(
        {"role": "system", "content": "Greet the user briefly. Introduce yourself as Glarvis."}
    )
    await task.queue_frames([LLMRunFrame()])

    runner = PipelineRunner(handle_sigint=False if sys.platform == "win32" else True)
    await runner.run(task)


if __name__ == "__main__":
    asyncio.run(main())
