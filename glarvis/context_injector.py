"""Frame processor that injects Board state into the LLM context
before each turn. Sits in the pipeline right before the LLM."""

from pipecat.frames.frames import Frame, LLMRunFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class BoardContextInjector(FrameProcessor):
    """Intercepts LLMRunFrame and updates the system message with Board state."""

    def __init__(self, orchestrator):
        super().__init__()
        self._orchestrator = orchestrator

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMRunFrame):
            self._orchestrator.inject_board_context()

        # Always pass the frame through
        await self.push_frame(frame, direction)
