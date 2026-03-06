"""Speech gate — filters out transcriptions that aren't addressed to Glarvis.

Sits between STT and the user aggregator. Passes through transcriptions that
contain the wake word, or all transcriptions if the agent is in "active" mode
(i.e., already in a conversation). Goes back to listening mode after a period
of inactivity."""

import asyncio
import time

from loguru import logger

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

WAKE_WORDS = ["glarvis", "jarvis", "clarice", "gladys"]  # common mishearings
ACTIVE_TIMEOUT = 30.0  # seconds of silence before going back to listening mode


class SpeechGate(FrameProcessor):
    """Only passes transcriptions to the pipeline when the user is addressing Glarvis.

    Two modes:
    - LISTENING: only passes through if wake word is detected, then switches to ACTIVE
    - ACTIVE: passes everything through, reverts to LISTENING after inactivity
    """

    def __init__(self, wake_words: list[str] | None = None, active_timeout: float = ACTIVE_TIMEOUT):
        super().__init__()
        self._wake_words = [w.lower() for w in (wake_words or WAKE_WORDS)]
        self._active_timeout = active_timeout
        self._active = False
        self._last_speech_time = 0.0
        self._timeout_task: asyncio.Task | None = None

    def _has_wake_word(self, text: str) -> bool:
        text_lower = text.lower()
        return any(w in text_lower for w in self._wake_words)

    def _strip_wake_word(self, text: str) -> str:
        """Remove the wake word from the transcription."""
        text_lower = text.lower()
        for w in self._wake_words:
            idx = text_lower.find(w)
            if idx != -1:
                # Remove wake word and clean up
                stripped = text[:idx] + text[idx + len(w):]
                return stripped.strip().strip(",").strip()
        return text

    def _activate(self):
        if not self._active:
            logger.info("[Gate] Activated — listening for commands")
        self._active = True
        self._last_speech_time = time.time()

        # Reset timeout
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
        self._timeout_task = asyncio.create_task(self._deactivate_after_timeout())

    async def _deactivate_after_timeout(self):
        await asyncio.sleep(self._active_timeout)
        if time.time() - self._last_speech_time >= self._active_timeout:
            self._active = False
            logger.info("[Gate] Deactivated — waiting for wake word")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if not text:
                await self.push_frame(frame, direction)
                return

            if self._active:
                # Already in conversation — pass everything through
                self._last_speech_time = time.time()
                await self.push_frame(frame, direction)

            elif self._has_wake_word(text):
                # Wake word detected — activate and pass through (minus wake word)
                self._activate()
                stripped = self._strip_wake_word(text)
                if stripped:
                    # There's content after the wake word, pass it through
                    frame = TranscriptionFrame(
                        text=stripped,
                        user_id=frame.user_id,
                        timestamp=frame.timestamp,
                        language=frame.language,
                    )
                    await self.push_frame(frame, direction)
                # If only wake word and nothing else, we just activate
                # and wait for the next utterance
            else:
                # Not active, no wake word — swallow it
                logger.debug(f"[Gate] Ignored (no wake word): {text[:50]}")
        else:
            # Non-transcription frames always pass through
            await self.push_frame(frame, direction)
