"""Captures user transcriptions and broadcasts them to the UI.
Sits before the user aggregator so it sees TranscriptionFrames."""

from loguru import logger

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class TranscriptCapture(FrameProcessor):
    """Captures final transcriptions and sends them to the UI transcript."""

    def __init__(self, orchestrator):
        super().__init__()
        self._orchestrator = orchestrator

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if text:
                # Check if any active session hides speech (e.g. transcriber)
                monitors = self._orchestrator.get_speech_monitors()
                hidden = any(hides for _, hides in monitors)
                if not hidden:
                    logger.info(f'[STT] User said: "{text}"')
                    await self._orchestrator.broadcast_transcript("user", text)

        await self.push_frame(frame, direction)
