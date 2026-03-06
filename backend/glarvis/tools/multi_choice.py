"""Multi-choice selector — first SessionTool using context + popups.

Opens a popup with numbered options. The user picks by voice ("two") or by
clicking in the popup. The LLM naturally maps speech to select_option(number=2).
Supports an "other" option for custom input via voice or popup text field.
"""

from __future__ import annotations

import asyncio

from pipecat.adapters.schemas.function_schema import FunctionSchema

from glarvis.tool import SessionTool, TaskResult


class MultiChoiceSession(SessionTool):
    name = "show_choices"
    description = "Show a popup with numbered options for the user to pick from."
    parameters = {
        "options": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of options to choose from",
        },
        "prompt": {
            "type": "string",
            "description": "Question or prompt for the user",
        },
    }
    required = ["options"]
    persist_in_display = False
    cancel_on_interruption = False
    notification = "silent"  # LLM handles the response, not a raw TTS notification

    async def run(self, options=None, prompt="", **kwargs) -> TaskResult:
        self._options = options or []
        self._result: TaskResult | None = None
        self._done = asyncio.Event()

        await self.handle.open_popup("multi_choice", {
            "prompt": prompt,
            "options": self._options,
        })

        # Block until a choice is made or dismissed
        await self._done.wait()
        return self._result or TaskResult(result=None, guide="Dismissed")

    def get_context_tools(self) -> list[FunctionSchema]:
        return [
            FunctionSchema(
                name="select_option",
                description="Select a displayed option by number (1-based).",
                properties={"number": {"type": "integer", "description": "Option number to select"}},
                required=["number"],
            ),
            FunctionSchema(
                name="select_other",
                description="Select a custom option not in the displayed list. Use when the user wants something different from the numbered options.",
                properties={"text": {"type": "string", "description": "The custom option text"}},
                required=["text"],
            ),
            FunctionSchema(
                name="dismiss",
                description="Close the choices without selecting.",
                properties={},
                required=[],
            ),
        ]

    async def handle_context_call(self, tool_name: str, **kwargs) -> TaskResult:
        if tool_name == "select_option":
            n = kwargs.get("number", 0)
            if 1 <= n <= len(self._options):
                choice = self._options[n - 1]
                await self.handle.close_popup()
                self._result = TaskResult(result=choice, guide=f"User selected: {choice}")
                self._done.set()
                return self._result
            return TaskResult(result=None, guide=f"Invalid number. Pick 1-{len(self._options)}.")
        elif tool_name == "select_other":
            text = kwargs.get("text", "")
            if not text:
                return TaskResult(result=None, guide="Provide text for the custom option.")
            await self.handle.close_popup()
            self._result = TaskResult(result=text, guide=f"User selected custom option: {text}")
            self._done.set()
            return self._result
        elif tool_name == "dismiss":
            await self.handle.close_popup()
            self._result = TaskResult(result=None, guide="User dismissed the choices.")
            self._done.set()
            return self._result
        return TaskResult(result=None, guide=f"Unknown context tool: {tool_name}")

    async def on_input(self, **kwargs) -> TaskResult:
        return TaskResult(result=None, guide="Pick a number, say something else, or say dismiss.")

    async def close(self) -> None:
        await self.handle.close_popup()
        self._done.set()
