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
import os

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema

from glarvis.tool import Intercept, Keyword, SessionTool, TaskResult


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
    "submit": "submit",
    "submit it": "submit",
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
    silent_popup_actions = True

    @property
    def hides_speech(self) -> bool:
        return not getattr(self, '_paused', False)

    def get_intercepts(self) -> list[Intercept]:
        async def _start():
            return await self.handle.execute_tool("transcribe")
        return [Keyword("transcribe", _start)]

    async def run(self, **kwargs) -> TaskResult:
        self._buffer: list[str] = []
        self._edited_text: str | None = None
        self._done = asyncio.Event()
        self._popup_open = True
        self._paused = False

        # Load persistent settings for popup
        from glarvis.settings import load_settings
        settings = load_settings()
        ts = settings.transcriber

        # Track the target window (where "send" will paste to)
        self._target_hwnd: int | None = None
        self._update_target_window()

        await self.handle.open_popup("transcriber", {
            "mode": "minimized",
            "text": "",
            "paused": False,
            "edit_prompt": ts.edit_prompt,
            "show_diff": ts.show_diff,
            "snap_to_bottom": ts.snap_to_bottom,
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
        for win in self.system.state.windows:
            if win.id == fg_id:
                if win.app == "minerva" or win.title == "Minerva":
                    return
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
            elif action == "submit":
                await self._do_submit()
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
            instruction = kwargs.get("instruction") or None
            return await self._do_edit(instruction)
        elif tool_name == "transcriber_clear":
            return await self._do_clear()
        elif tool_name == "transcriber_pause":
            return await self._do_pause()
        elif tool_name == "transcriber_resume":
            return await self._do_resume()
        elif tool_name == "transcriber_stop":
            return await self._do_stop()
        elif tool_name == "transcriber_submit":
            return await self._do_submit()
        elif tool_name == "transcriber_update_text":
            # Popup manually edited text — save back to buffer
            new_text = kwargs.get("text", "")
            if new_text:
                self._buffer = [new_text]
                self._edited_text = new_text
            return TaskResult(result="Text updated.")
        elif tool_name == "transcriber_set_prompt":
            from glarvis.settings import load_settings, save_settings
            prompt = kwargs.get("prompt", "").strip()
            if prompt:
                settings = load_settings()
                settings.transcriber.edit_prompt = prompt
                save_settings(settings)
            return TaskResult(result="Prompt saved.")
        elif tool_name == "transcriber_set_show_diff":
            from glarvis.settings import load_settings, save_settings
            show = kwargs.get("show_diff", True)
            settings = load_settings()
            settings.transcriber.show_diff = bool(show)
            save_settings(settings)
            return TaskResult(result="Show diff setting saved.")
        elif tool_name == "transcriber_set_snap":
            from glarvis.settings import load_settings, save_settings
            snap = kwargs.get("snap_to_bottom", True)
            settings = load_settings()
            settings.transcriber.snap_to_bottom = bool(snap)
            save_settings(settings)
            return TaskResult(result="Snap setting saved.")
        return TaskResult(result=None, guide=f"Unknown context tool: {tool_name}")

    # ── Actions ──────────────────────────────────────────────────────────

    async def _do_send(self) -> TaskResult:
        # Prefer edited text (right pane) over raw buffer
        text = self._edited_text if self._edited_text else " ".join(self._buffer)
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
            self._edited_text = None
            if self._popup_open:
                await self._update_popup("")
                await self.handle.broadcast({"type": "transcriber_sent"})
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

    async def _do_edit(self, instruction: str | None = None) -> TaskResult:
        """Edit transcript using the configured transcriber LLM (direct API call)."""
        text = " ".join(self._buffer)
        if not text:
            return TaskResult(result="Nothing to edit.", guide="Buffer is empty.")

        if not instruction:
            from glarvis.settings import load_settings
            instruction = load_settings().transcriber.edit_prompt

        self._paused = True
        await self._broadcast_state()
        await self._broadcast_editing(True)

        try:
            edited = await self._call_edit_llm(text, instruction)
            # Replace buffer with edited text
            self._buffer = [edited]
            self._edited_text = edited
            if self._popup_open:
                await self._update_popup(edited)
                await self._broadcast_edit_result(text, edited)
            await self._broadcast_editing(False)
            self._paused = False
            await self._broadcast_state()
            return TaskResult(result="Transcript edited.", guide="Edited.")
        except Exception as e:
            logger.error(f"[Transcriber] Edit failed: {e}")
            await self._broadcast_editing(False)
            self._paused = False
            await self._broadcast_state()
            return TaskResult(result=f"Edit failed: {e}", guide="Edit failed.")

    async def _call_edit_llm(self, text: str, instruction: str) -> str:
        """Call the configured LLM directly to edit the transcript."""
        from glarvis.settings import load_settings
        from glarvis.services.registry import _load_config

        settings = load_settings()
        ts = settings.transcriber

        # Resolve provider config
        config = _load_config()
        provider_config = config.get("llm", {}).get(ts.provider, {})

        # Resolve API key: override > env var from provider config
        api_key = ts.api_key
        if not api_key:
            env_key = provider_config.get("env_key", "")
            api_key = os.getenv(env_key, "")

        if not api_key:
            raise ValueError(f"No API key for transcriber provider '{ts.provider}'")

        base_url = provider_config.get("base_url")
        service_class = provider_config.get("service", "")
        prompt = f"Edit the following transcript according to the instruction. Return ONLY the edited text, nothing else.\n\nInstruction: {instruction}\n\nTranscript:\n{text}"

        # Use Anthropic SDK for Anthropic provider, OpenAI SDK for others
        if "anthropic" in service_class.lower() or ts.provider == "anthropic":
            import anthropic
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            client = anthropic.AsyncAnthropic(**kwargs)
            response = await asyncio.wait_for(
                client.messages.create(
                    model=ts.model,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=30,
            )
            return response.content[0].text.strip()
        else:
            # OpenAI-compatible (OpenAI, OpenRouter, etc.)
            from openai import AsyncOpenAI
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            client = AsyncOpenAI(**kwargs)
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=ts.model,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=30,
            )
            return response.choices[0].message.content.strip()

    async def _do_edit_via_llm(self):
        """Voice command handler for 'edit' — runs edit with settings prompt."""
        text = " ".join(self._buffer)
        if not text:
            return
        from glarvis.settings import load_settings
        instruction = load_settings().transcriber.edit_prompt
        return await self._do_edit(instruction)

    async def _do_submit(self) -> TaskResult:
        """Send text + press Enter in the target window."""
        result = await self._do_send()
        if result.guide == "Sent.":
            import time
            from glarvis.system.windows import send_key
            time.sleep(0.1)
            send_key(0x0D)  # VK_RETURN
            return TaskResult(result="Text submitted.", guide="Submitted.")
        return result

    async def _do_clear(self) -> TaskResult:
        self._buffer.clear()
        self._edited_text = None
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

    async def _broadcast_editing(self, editing: bool):
        """Notify popup that an LLM edit is in progress."""
        await self.handle.broadcast({
            "type": "transcriber_editing",
            "editing": editing,
        })

    async def _broadcast_edit_result(self, original: str, edited: str):
        """Send both original and edited text so popup can show a diff."""
        await self.handle.broadcast({
            "type": "transcriber_edit_result",
            "original": original,
            "edited": edited,
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
            f"Voice commands handled directly. Edit uses a separate LLM."
        )

    async def on_input(self, **kwargs) -> TaskResult:
        return TaskResult(result=None)

    async def close(self) -> None:
        self._popup_open = False
        self._done.set()
        await self.handle.close_popup()
