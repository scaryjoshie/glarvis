"""Transcriber — voice dictation session with live popup.

Opens a popup that shows transcribed speech in real time. Two modes:
- Minimized: small pill bar + one-line fading transcript
- Maximized: full scrollable text area

Actions: send (paste to target window), copy, edit (LLM rewrite), stop.
Uses monitors_speech + hides_speech to take ownership of the STT stream.
Tracks the target window (last focused non-popup window) for send.
"""

from __future__ import annotations

import asyncio

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema

from glarvis.tool import SessionTool, TaskResult


# Voice commands — exact match only (after strip + lower)
_COMMANDS: dict[str, str] = {
    "send": "send",
    "send it": "send",
    "paste": "send",
    "paste it": "send",
    "copy": "copy",
    "copy it": "copy",
    "copy that": "copy",
    "clear": "clear",
    "clear all": "clear",
    "stop": "stop",
    "stop transcribing": "stop",
    "cancel": "stop",
    "done": "stop",
    "pause": "pause",
    "resume": "resume",
    "unpause": "resume",
    "edit": "edit",
    "edit this": "edit",
    "clean this up": "edit",
    "fix this": "edit",
}


class TranscriberSession(SessionTool):
    name = "transcribe"
    description = "Start voice dictation. Opens a live transcript popup where speech is captured as text."
    parameters = {}
    required = []
    persist_in_display = True
    cancel_on_interruption = False
    auto_enter_context = True
    monitors_speech = True
    hides_speech = True

    async def run(self, **kwargs) -> TaskResult:
        self._buffer: list[str] = []
        self._done = asyncio.Event()
        self._popup_open = True
        self._paused = False

        # Track the target window (where "send" will paste to)
        self._target_hwnd: int | None = None
        self._update_target_window()

        await self.handle.open_popup("transcriber", {
            "mode": "minimized",
            "text": "",
            "paused": False,
        })

        # Block until session ends
        await self._done.wait()

        return TaskResult(
            result="Transcriber stopped.",
            guide="Done.",
        )

    # ── Target window tracking ───────────────────────────────────────────

    def _update_target_window(self):
        """Save the currently focused window as the paste target."""
        if not self.system:
            return
        fg_id = self.system.state.foreground_id
        if fg_id is None:
            return
        # Find the hwnd for this stable ID
        for win in self.system.state.windows:
            if win.id == fg_id:
                self._target_hwnd = win.hwnd
                logger.debug(f"[Transcriber] Target window: {win.title} (hwnd={win.hwnd})")
                return

    def _maybe_update_target(self):
        """Update target window if the foreground is a real app (not our popup)."""
        if not self.system:
            return
        fg_id = self.system.state.foreground_id
        if fg_id is None:
            return
        for win in self.system.state.windows:
            if win.id == fg_id:
                # Skip if it's our own popup (Minerva title, or very small window)
                if win.app == "minerva" or win.title == "Minerva":
                    return
                if win.hwnd != self._target_hwnd:
                    self._target_hwnd = win.hwnd
                    logger.debug(f"[Transcriber] Target updated: {win.title}")
                return

    def _focus_target(self) -> bool:
        """Focus the target window before pasting. Returns True if successful."""
        if not self._target_hwnd:
            return False
        from glarvis.system.windows import focus_window
        return focus_window(self._target_hwnd)

    # ── Speech ownership ─────────────────────────────────────────────────

    async def on_speech(self, text: str) -> None:
        """Receive all STT output. Check for commands first, then buffer."""
        cleaned = text.strip().lower().rstrip(".!?,")
        if not cleaned:
            return

        # Update target if user is focused on a real window (not the popup)
        self._maybe_update_target()

        # Commands always work, even when paused
        action = _COMMANDS.get(cleaned)
        if action:
            logger.info(f"[Transcriber] Voice command: {cleaned!r} → {action}")
            if action == "send":
                await self._do_send()
            elif action == "copy":
                await self._do_copy()
            elif action == "clear":
                await self._do_clear()
            elif action == "stop":
                await self._do_stop()
            elif action == "pause":
                await self._do_pause()
            elif action == "resume":
                await self._do_resume()
            elif action == "edit":
                await self._do_edit_via_llm()
            return

        # Don't buffer when paused
        if self._paused:
            return

        # Not a command — add to buffer
        self._buffer.append(text.strip())
        if self._popup_open:
            await self._update_popup(" ".join(self._buffer))

    # ── Context tools (LLM can also trigger these) ───────────────────────

    def get_context_tools(self) -> list[FunctionSchema]:
        return [
            FunctionSchema(
                name="transcriber_send",
                description="Paste the transcribed text into the target application window.",
                properties={},
                required=[],
            ),
            FunctionSchema(
                name="transcriber_copy",
                description="Copy the transcribed text to the clipboard.",
                properties={},
                required=[],
            ),
            FunctionSchema(
                name="transcriber_edit",
                description="Ask the LLM to clean up / rewrite the transcribed text. Provide an instruction.",
                properties={
                    "instruction": {
                        "type": "string",
                        "description": "How to edit the text (e.g. 'fix grammar', 'make formal', 'summarize')",
                    },
                },
                required=[],
            ),
            FunctionSchema(
                name="transcriber_clear",
                description="Clear the transcribed text buffer.",
                properties={},
                required=[],
            ),
            FunctionSchema(
                name="transcriber_stop",
                description="Stop transcribing and close the popup.",
                properties={},
                required=[],
            ),
        ]

    async def handle_context_call(self, tool_name: str, **kwargs) -> TaskResult:
        if tool_name == "transcriber_send":
            return await self._do_send()
        elif tool_name == "transcriber_copy":
            return await self._do_copy()
        elif tool_name == "transcriber_edit":
            instruction = kwargs.get("instruction", "clean up grammar and formatting")
            return await self._do_edit(instruction)
        elif tool_name == "transcriber_clear":
            return await self._do_clear()
        elif tool_name == "transcriber_pause":
            return await self._do_pause()
        elif tool_name == "transcriber_resume":
            return await self._do_resume()
        elif tool_name == "transcriber_stop":
            return await self._do_stop()
        return TaskResult(result=None, guide=f"Unknown context tool: {tool_name}")

    # ── Actions ──────────────────────────────────────────────────────────

    async def _do_send(self) -> TaskResult:
        text = " ".join(self._buffer)
        if not text:
            return TaskResult(result="Nothing to send.", guide="Buffer is empty.")

        import time
        from glarvis.system.windows import paste_text

        # Focus the target window first, then paste
        if self._target_hwnd:
            self._focus_target()
            time.sleep(0.15)  # let the window come to foreground

        success = paste_text(text)
        if success:
            self._buffer.clear()
            if self._popup_open:
                await self._update_popup("")
            return TaskResult(result="Text pasted.", guide="Sent.")
        return TaskResult(result="Failed to paste text.", guide="Paste failed.")

    async def _do_copy(self) -> TaskResult:
        text = " ".join(self._buffer)
        if not text:
            return TaskResult(result="Nothing to copy.", guide="Buffer is empty.")

        from glarvis.system.windows import set_clipboard_text
        success = set_clipboard_text(text)
        if success:
            return TaskResult(result="Copied to clipboard.", guide="Copied.")
        return TaskResult(result="Failed to copy.", guide="Copy failed.")

    async def _do_edit(self, instruction: str) -> TaskResult:
        text = " ".join(self._buffer)
        if not text:
            return TaskResult(result="Nothing to edit.", guide="Buffer is empty.")

        return TaskResult(
            result=f"Current transcript:\n{text}\n\nInstruction: {instruction}\n\nRewrite the transcript according to the instruction. Post the result to the board showing original and edited versions.",
            guide="Editing transcript.",
        )

    async def _do_edit_via_llm(self):
        """Pause capture and nudge the LLM to call transcriber_edit."""
        text = " ".join(self._buffer)
        if not text:
            return
        self._paused = True
        await self._broadcast_state()
        # Inject a message that triggers the LLM — it will see the context tools
        # and the transcript in get_context_info(), then call transcriber_edit
        await self.handle.inject_llm_message(
            f"[User wants to edit the transcript. Call transcriber_edit to clean it up.]"
        )

    async def _do_clear(self) -> TaskResult:
        self._buffer.clear()
        if self._popup_open:
            await self._update_popup("")
        return TaskResult(result="Cleared.", guide="Cleared.")

    async def _do_pause(self) -> TaskResult:
        self._paused = True
        await self._broadcast_state()
        return TaskResult(result="Paused.", guide="Paused.")

    async def _do_resume(self) -> TaskResult:
        self._paused = False
        # Update target window on resume (user may have switched apps)
        self._update_target_window()
        await self._broadcast_state()
        return TaskResult(result="Resumed.", guide="Resumed.")

    async def _do_stop(self) -> TaskResult:
        self._popup_open = False
        self._done.set()
        await self.handle.close_popup()
        return TaskResult(result="Transcriber stopped.", guide="Stopped.")

    # ── Popup communication ──────────────────────────────────────────────

    async def _update_popup(self, text: str):
        """Send updated text to the popup."""
        await self.handle.broadcast({
            "type": "transcriber_update",
            "text": text,
        })

    async def _broadcast_state(self):
        """Send pause/resume state to the popup."""
        await self.handle.broadcast({
            "type": "transcriber_state",
            "paused": self._paused,
        })

    # ── SessionTool protocol ─────────────────────────────────────────────

    @property
    def is_done(self) -> bool:
        return self._done.is_set()

    def get_context_info(self) -> str | None:
        text = " ".join(self._buffer) if hasattr(self, "_buffer") else ""
        word_count = len(text.split()) if text else 0
        paused = " (PAUSED)" if getattr(self, "_paused", False) else ""
        return (
            f"Transcriber is active{paused} ({word_count} words captured). "
            f"Voice commands handled directly. LLM can call transcriber_edit to rewrite."
        )

    async def on_input(self, **kwargs) -> TaskResult:
        return TaskResult(result=None)

    async def close(self) -> None:
        self._popup_open = False
        self._done.set()
        await self.handle.close_popup()
