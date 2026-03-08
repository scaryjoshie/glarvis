"""Intercepts user transcriptions before the LLM.

Two mechanisms:
1. Speech monitors — sessions with monitors_speech=True get on_speech() calls.
   If any monitor has hides_speech=True, the LLM doesn't see the speech.
2. Intercept chain — keyword/function pattern matching for specific phrases.

Sits after TranscriptCapture, before UserAggregator in the pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

if TYPE_CHECKING:
    from glarvis.orchestrator import Orchestrator


class InputInterceptor(FrameProcessor):
    """Routes STT output to speech monitors and/or intercept handlers.

    Speech monitors get on_speech() for every transcription. If any monitor
    hides speech, the frame and subsequent VAD stop are suppressed.

    Intercepts run after monitors (only if speech isn't hidden).
    """

    def __init__(self, orchestrator: Orchestrator):
        super().__init__()
        self._orchestrator = orchestrator
        self._suppress_stop = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, UserStartedSpeakingFrame):
            self._suppress_stop = False
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            # System-injected and typed text frames bypass speech monitors and intercepts
            if frame.user_id in ("system", "popup", "text"):
                await self.push_frame(frame, direction)
                return

            # 1. Speech monitors (real user speech only)
            monitors = self._orchestrator.get_speech_monitors()
            hidden = False
            for tool, hides in monitors:
                await tool.on_speech(frame.text)
                if hides:
                    hidden = True

            if hidden:
                self._suppress_stop = True
                return

            # 2. Intercept chain (keywords, functions)
            result = await self._orchestrator.try_intercept(frame.text)
            if result is not None:
                logger.info(f"[InputInterceptor] Intercepted: {frame.text!r} → {result.guide!r}")
                if result.guide:
                    frame.text = f"[{result.guide}]"
                    await self.push_frame(frame, direction)
                else:
                    self._suppress_stop = True
                return

        if isinstance(frame, UserStoppedSpeakingFrame) and self._suppress_stop:
            logger.debug("[InputInterceptor] Suppressed stop frame")
            self._suppress_stop = False
            return

        await self.push_frame(frame, direction)
