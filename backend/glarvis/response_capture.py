"""Captures LLM text output and broadcasts it to the UI transcript."""

from pipecat.frames.frames import Frame, LLMFullResponseStartFrame, LLMFullResponseEndFrame, LLMTextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class ResponseCapture(FrameProcessor):
    """Sits after the LLM to capture full responses for the transcript.

    Accumulates LLMTextFrames between LLMFullResponseStartFrame and
    LLMFullResponseEndFrame, then broadcasts the complete response."""

    def __init__(self, orchestrator):
        super().__init__()
        self._orchestrator = orchestrator
        self._buffer = []
        self._capturing = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._capturing = True
            self._buffer.clear()
        elif isinstance(frame, LLMFullResponseEndFrame):
            if self._buffer:
                text = "".join(self._buffer).strip()
                if text:
                    await self._orchestrator.broadcast_transcript("assistant", text)
            self._buffer.clear()
            self._capturing = False
        elif isinstance(frame, LLMTextFrame) and self._capturing:
            self._buffer.append(frame.text)

        await self.push_frame(frame, direction)
