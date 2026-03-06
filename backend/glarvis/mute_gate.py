"""MuteGate — drops voice transcription frames when muted.

Sits after STT in the pipeline. When muted, only the 'unmute' keyword
gets through. Text input (user_id='user') always passes."""

from loguru import logger
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class MuteGate(FrameProcessor):
    def __init__(self, broadcast=None):
        super().__init__()
        self.muted = False       # soft mute (server-side gate, mic still on)
        self.hard_muted = False   # hard mute (client-side, mic track disabled)
        self._broadcast = broadcast  # async fn to notify frontend

    async def set_muted(self, muted: bool):
        self.muted = muted
        logger.info(f"[MuteGate] {'Muted' if muted else 'Unmuted'}")
        if self._broadcast:
            await self._broadcast({"type": "mute_state", "muted": muted})

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if self.muted and isinstance(frame, TranscriptionFrame):
            # Text input always passes through
            if frame.user_id in ("user", "popup"):
                await self.push_frame(frame, direction)
                return

            # Check for unmute keyword in voice
            if "unmute" in frame.text.strip().lower():
                await self.set_muted(False)
                await self.push_frame(
                    TranscriptionFrame(text="unmute", user_id=frame.user_id, timestamp=frame.timestamp),
                    direction,
                )
                return

            # Drop voice frames when muted
            return

        await self.push_frame(frame, direction)
