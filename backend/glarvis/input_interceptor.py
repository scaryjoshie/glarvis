"""Intercepts user transcriptions before the LLM when active sessions
can handle them directly (e.g., number words during multi-choice).

Sits after TranscriptCapture, before UserAggregator in the pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

if TYPE_CHECKING:
    from glarvis.orchestrator import Orchestrator


class InputInterceptor(FrameProcessor):
    """Checks if active session contexts want to claim user input.

    If a session's intercept() returns a result, the frame's text is
    replaced with the result guide and pushed downstream normally.
    The natural VAD stop event that follows speech triggers the LLM turn.
    """

    def __init__(self, orchestrator: Orchestrator):
        super().__init__()
        self._orchestrator = orchestrator

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            result = await self._orchestrator.try_intercept(frame.text)
            if result is not None:
                logger.info(f"[InputInterceptor] Intercepted: {frame.text!r} → {result.guide!r}")
                if result.guide:
                    # Replace the text and let it flow through naturally
                    frame.text = f"[{result.guide}]"
                    await self.push_frame(frame, direction)
                return  # either pushed modified frame or consumed silently

        await self.push_frame(frame, direction)
