"""TTSGate — drops TTS frames when deafened.

Sits before TTS in the pipeline. When deafened, TTSSpeakFrame and
TTSStartedFrame are dropped so the TTS service is never called,
saving API costs. The LLM still runs normally."""

from loguru import logger
from pipecat.frames.frames import Frame, TTSSpeakFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class TTSGate(FrameProcessor):
    def __init__(self, broadcast=None):
        super().__init__()
        self.deafened = False
        self._broadcast = broadcast

    async def set_deafened(self, deafened: bool):
        self.deafened = deafened
        logger.info(f"[TTSGate] {'Deafened' if deafened else 'Undeafened'}")
        if self._broadcast:
            await self._broadcast({"type": "deafen_state", "deafened": deafened})

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if self.deafened and isinstance(frame, TTSSpeakFrame):
            return  # drop — TTS service never sees it

        await self.push_frame(frame, direction)
