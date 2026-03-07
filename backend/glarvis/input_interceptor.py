"""Intercepts user transcriptions before the LLM when active sessions
can handle them directly (e.g., number words during multi-choice).

Sits after TranscriptCapture, before UserAggregator in the pipeline.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from loguru import logger
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

if TYPE_CHECKING:
    from glarvis.orchestrator import Orchestrator
    from pipecat.pipeline.task import PipelineTask


class InputInterceptor(FrameProcessor):
    """Checks if active session contexts want to claim user input.

    If a session's intercept() returns a result, the transcription frame
    is consumed (not forwarded to the LLM). The result is injected back
    as a user message so the LLM knows what happened and can follow up.
    """

    def __init__(self, orchestrator: Orchestrator):
        super().__init__()
        self._orchestrator = orchestrator
        self._pipeline_task: PipelineTask | None = None

    def set_pipeline_task(self, task: PipelineTask):
        self._pipeline_task = task

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            result = await self._orchestrator.try_intercept(frame.text)
            if result is not None:
                logger.info(f"[InputInterceptor] Consumed: {frame.text!r}")
                # Inject the result as a user message so the LLM can follow up
                if result.guide and self._pipeline_task:
                    injected = TranscriptionFrame(
                        text=f"[{result.guide}]",
                        user_id="intercepted",
                        timestamp=str(time.time()),
                    )
                    await self._pipeline_task.queue_frame(injected)
                return  # consume the original frame

        await self.push_frame(frame, direction)
