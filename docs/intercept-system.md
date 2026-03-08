# Intercept System

## Overview

Intercepts let tools catch voice input **before it reaches the LLM**. Two scopes, two matching styles, one pipeline.

## System State Access

Tools get a reference to `SystemMonitor` once at registration via `tool.system`. This is the live monitor — always current, no refresh needed.

```python
self.system.state.windows          # live window list
self.system.state.foreground_id    # currently focused window
self.system.focus_window(id)       # actions
self.system.search_programs("foo") # actions
```

Set once at `orchestrator.register()`, never re-stamped. Tools that currently take `monitor` as a constructor arg (FocusWindow, SearchPrograms, OpenProgram) won't need to — it's on BaseTool.

## Scopes

**Global** — always active, registered when the tool is registered with the orchestrator.
- Example: "switch" → `SwitchWindow.run()`

**Context** — active only when a session has entered context, cleaned up on exit.
- Example: "two" → `MultiChoiceSession._on_number()` (only while a multi-choice is active)

## Matching Styles

**Keyword** — exact string match after cleaning. O(1) dict lookup.
```python
Keyword("switch", self.run)
Keyword("dismiss", self._on_dismiss)
```

**Function** — callable that receives cleaned text, returns `TaskResult` or `None` (pass-through). Run sequentially.
```python
Function(self._match_number)  # parses "two", "second", etc.
```

Handler signatures:
- Keyword: `() -> TaskResult | None` (no args — you know what keyword triggered it)
- Function: `(text: str) -> TaskResult | None` (receives cleaned text for custom matching)

Return `TaskResult` → intercepted, frame consumed. Return `None` → pass-through, next interceptor tries.

## Registration

Tools declare intercepts at two points:

```python
class SwitchWindow(InlineTool):
    def get_intercepts(self):
        """Called once at orchestrator.register() time. Always active."""
        return [Keyword("switch", self.run)]

class MultiChoiceSession(SessionTool):
    def get_context_intercepts(self):
        """Called at enter_context(). Removed at exit_context()."""
        return [
            Keyword("dismiss", self._on_dismiss),
            Keyword("cancel", self._on_dismiss),
            Function(self._match_number),
        ]
```

The orchestrator collects these into a single registry:
- `register(tool)` → calls `tool.get_intercepts()` → adds to global layer
- `enter_context(task_id)` → calls `tool.get_context_intercepts()` → adds to context layer
- `exit_context(task_id)` → removes that session's context intercepts

## Dispatch Pipeline

On every voice transcription, `InputInterceptor` calls `orchestrator.try_intercept(text)`:

```
1. Clean text                     ← strip, lowercase, remove trailing punctuation
2. Keyword lookup (global dict)   ← O(1)
3. Keyword lookup (context dict)  ← O(1)
4. Global functions (sequential)  ← each returns TaskResult | None
5. Context functions (sequential) ← each returns TaskResult | None
6. Not intercepted                ← frame flows to LLM
```

At steps 2–5, if a handler returns `TaskResult`, input is intercepted. If it returns `None`, the pipeline continues to the next step.

## Information Flow

```
Voice → STT → MuteGate → TranscriptCapture → InputInterceptor
                                                     │
                                          try_intercept(text)
                                                     │
                                          ┌──────────┴──────────┐
                                          │  clean text          │
                                          │  keyword lookup (G)  │
                                          │  keyword lookup (C)  │
                                          │  functions (G)       │
                                          │  functions (C)       │
                                          └──────────┬──────────┘
                                                     │
                                     ┌───────────────┴───────────────┐
                                     │                               │
                              TaskResult returned              None (pass)
                              Frame consumed                   Frame → LLM
```

## Object Ownership

| Object | Lives on | Set by | Used by |
|---|---|---|---|
| `SystemMonitor` | `tool.system` | `orchestrator.register()` (once, by reference) | `tool.run()`, intercept handlers, actions |
| `tool.handle` | Each `BaseTool` | `orchestrator.register()` | `execute_tool`, `broadcast`, etc. |
| Global intercepts | Orchestrator registry | `register()` via `get_intercepts()` | `try_intercept()` |
| Context intercepts | Orchestrator registry | `enter/exit_context()` via `get_context_intercepts()` | `try_intercept()` |
| `_active_contexts` | Orchestrator | `enter/exit_context()` | `_rebuild_tools()`, context intercepts |
| `TaskManager` | Orchestrator | Tool results | `prepare_for_turn()` for snapshot |

## Examples

### Simple global shortcut
```python
class SwitchWindow(InlineTool):
    name = "switch_window"

    def get_intercepts(self):
        return [Keyword("switch", self.run)]

    async def run(self, **kwargs):
        options = [
            {"text": f"{w.title} ({w.app})", "action": {"tool": "focus_window", "args": {"id": w.id}}}
            for w in self.system.state.windows
        ]
        return await self.handle.execute_tool("show_choices", options=options, prompt="Switch to:")
```

### Lambda shortcut (no dedicated tool)
```python
# Registered by any tool that wants a quick global trigger
def get_intercepts(self):
    return [
        Keyword("mute", lambda: self.handle.execute_tool("mute")),
    ]
```

### Session with context intercepts
```python
class MultiChoiceSession(SessionTool):
    def get_context_intercepts(self):
        keywords = [
            Keyword("dismiss", self._on_dismiss),
            Keyword("cancel", self._on_dismiss),
            Keyword("nevermind", self._on_dismiss),
        ]
        return keywords + [Function(self._match_number)]

    async def _on_dismiss(self):
        return await self.handle_context_call("dismiss")

    async def _match_number(self, text):
        cleaned = text.strip().lower().rstrip(".!?,")
        n = _NUMBER_WORDS.get(cleaned)
        if n and 1 <= n <= len(self._options):
            return await self.handle_context_call("select_option", number=n)
        return None  # pass-through
```
