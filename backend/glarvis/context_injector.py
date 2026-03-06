"""Frame processor that prepares context before each LLM turn.
Sits in the pipeline right before the LLM."""

from pipecat.frames.frames import Frame, LLMRunFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class BoardContextInjector(FrameProcessor):
    """Intercepts LLMRunFrame and refreshes tools + system message."""

    def __init__(self, orchestrator):
        super().__init__()
        self._orchestrator = orchestrator

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMRunFrame):
            self._orchestrator.prepare_for_turn()

        await self.push_frame(frame, direction)
