"""Frame processor that prepares context before each LLM turn.
Sits in the pipeline right before the LLM."""

from loguru import logger
from pipecat.frames.frames import Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# Pipecat 0.0.104 uses LLMContextFrame, older versions used LLMRunFrame
try:
    from pipecat.frames.frames import LLMContextFrame as _TriggerFrame
except ImportError:
    from pipecat.frames.frames import LLMRunFrame as _TriggerFrame


class BoardContextInjector(FrameProcessor):
    """Intercepts the LLM context frame and refreshes tools + system message."""

    def __init__(self, orchestrator):
        super().__init__()
        self._orchestrator = orchestrator

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, _TriggerFrame):
            try:
                self._orchestrator.prepare_for_turn()
            except Exception as e:
                logger.error(f"[BoardContextInjector] prepare_for_turn failed: {e}")

        await self.push_frame(frame, direction)
