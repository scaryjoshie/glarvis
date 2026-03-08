"""Multi-choice selector — first SessionTool using context + popups.

Opens a popup with numbered options. The user picks by voice ("two") or by
clicking in the popup. The LLM naturally maps speech to select_option(number=2).
Supports an "other" option for custom input via voice or popup text field.
"""

from __future__ import annotations

import asyncio

from pipecat.adapters.schemas.function_schema import FunctionSchema

from glarvis.tool import Function, Intercept, Keyword, SessionTool, TaskResult


_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
    "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
}


class MultiChoiceSession(SessionTool):
    name = "show_choices"
    description = "Show a popup with numbered options for the user to pick from."
    parameters = {
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to display to the user"},
                    "action": {
                        "type": "object",
                        "description": "Optional shortcut action to execute immediately when chosen.",
                        "properties": {
                            "tool": {"type": "string", "description": "Name of the tool to execute"},
                            "args": {"type": "object", "description": "Arguments for the tool"}
                        },
                        "required": ["tool"]
                    }
                },
                "required": ["text"]
            },
            "description": "List of options to choose from. Can be simple strings or objects with an action.",
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
        # Standardize options internally, but pass simple strings to popup
        self._full_options = []
        for opt in (options or []):
            if isinstance(opt, dict):
                self._full_options.append({
                    "text": str(opt.get("text", "")),
                    "action": opt.get("action"),
                    "icon": opt.get("icon"),
                })
            else:
                self._full_options.append({"text": str(opt), "action": None, "icon": None})

        self._result: TaskResult | None = None
        self._done = asyncio.Event()

        popup_options = []
        for opt in self._full_options:
            entry = {"text": opt["text"]}
            if opt["icon"]:
                entry["icon"] = opt["icon"]
            popup_options.append(entry)

        await self.handle.open_popup("multi_choice", {
            "prompt": prompt,
            "options": popup_options,
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
            if 1 <= n <= len(self._full_options):
                choice = self._full_options[n - 1]
                await self.handle.close_popup()
                
                action = choice.get("action")
                if action and isinstance(action, dict) and "tool" in action:
                    # Execute shortcut action immediately
                    args = action.get("args", {})
                    action_result = await self.handle.execute_tool(action["tool"], **args)
                    self._result = TaskResult(
                        result=f"User selected '{choice['text']}' and action '{action['tool']}' was triggered.\nResult: {action_result.result}",
                        guide=f"Executed shortcut: {action['tool']}"
                    )
                else:
                    self._result = TaskResult(result=choice["text"], guide=f"User selected: {choice['text']}")
                    
                self._done.set()
                return self._result
            return TaskResult(result=None, guide=f"Invalid number. Pick 1-{len(self._full_options)}.")
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

    @property
    def is_done(self) -> bool:
        return self._done.is_set()

    def get_context_intercepts(self) -> list[Intercept]:
        return [
            Keyword("dismiss", self._on_dismiss),
            Keyword("cancel", self._on_dismiss),
            Keyword("nevermind", self._on_dismiss),
            Keyword("never mind", self._on_dismiss),
            Function(self._match_number),
        ]

    async def _on_dismiss(self) -> TaskResult:
        return await self.handle_context_call("dismiss")

    async def _match_number(self, text: str) -> TaskResult | None:
        n = _NUMBER_WORDS.get(text)
        if hasattr(self, "_full_options") and n is not None and 1 <= n <= len(self._full_options):
            return await self.handle_context_call("select_option", number=n)
        return None

    async def on_input(self, **kwargs) -> TaskResult:
        return TaskResult(result=None, guide="Pick a number, say something else, or say dismiss.")

    async def close(self) -> None:
        await self.handle.close_popup()
        self._done.set()
