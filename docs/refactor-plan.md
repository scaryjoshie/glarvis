# Refactor Plan: Intercept System + ToolHandle + System Access

## Summary

Three related changes that simplify how tools interface with the system:

1. **Intercept system** — unified input interception (global + context scoped)
2. **ToolHandle consolidation** — single concrete class in its own file, no abstract/subclass split
3. **System monitor as live reference** — set once at registration, no per-turn stamping

## 1. Intercept System

### Intercept Types

Defined in `tool.py`:

```python
@dataclass
class Keyword:
    word: str
    handler: Callable  # async () -> TaskResult | None

@dataclass
class Function:
    handler: Callable  # async (text: str) -> TaskResult | None

Intercept = Keyword | Function
```

- **Keyword**: exact match after cleaning, O(1) dict lookup. Handler takes no args (it knows what keyword triggered it).
- **Function**: receives cleaned text, does custom matching. Returns `TaskResult` to intercept, `None` to pass through.

### Registration Points

```python
class BaseTool:
    def get_intercepts(self) -> list[Intercept]:
        """Global intercepts. Called once at register() time. Always active."""
        return []

class SessionTool:
    def get_context_intercepts(self) -> list[Intercept]:
        """Context intercepts. Registered at enter_context(), removed at exit_context()."""
        return []
```

### Orchestrator Registry

```python
# On orchestrator
_global_keywords: dict[str, Keyword]     # cleaned word → Keyword
_global_functions: list[Function]
_context_keywords: dict[str, Keyword]     # cleaned word → Keyword
_context_functions: list[Function]
_context_intercepts: dict[str, list]      # task_id → intercepts (for cleanup)
```

- `register(tool)` → `tool.get_intercepts()` → populates global layer
- `enter_context(task_id)` → `tool.get_context_intercepts()` → populates context layer
- `exit_context(task_id)` → removes that task's context intercepts

### Dispatch Pipeline

`InputInterceptor` calls `orchestrator.try_intercept(text)` on every transcription frame:

```
1. Clean text (strip, lowercase, remove trailing punctuation)
2. Global keyword lookup (O(1)) → call handler if hit
3. Context keyword lookup (O(1)) → call handler if hit
4. Global functions (sequential) → call each until non-None
5. Context functions (sequential) → call each until non-None
6. Not intercepted → frame flows to LLM
```

Handler returns `TaskResult` → intercepted, frame consumed. Returns `None` → pass-through, try next.

After a context intercept, orchestrator broadcasts transcript and checks `is_done` for auto-exit.

### Tool Examples

**SwitchWindow (global keyword):**
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

**MultiChoiceSession (context keywords + function):**
```python
class MultiChoiceSession(SessionTool):
    def get_context_intercepts(self):
        return [
            Keyword("dismiss", self._on_dismiss),
            Keyword("cancel", self._on_dismiss),
            Keyword("nevermind", self._on_dismiss),
            Keyword("never mind", self._on_dismiss),
            Function(self._match_number),
        ]

    async def _on_dismiss(self):
        return await self.handle_context_call("dismiss")

    async def _match_number(self, text):
        n = _NUMBER_WORDS.get(text)
        if hasattr(self, "_full_options") and n is not None and 1 <= n <= len(self._full_options):
            return await self.handle_context_call("select_option", number=n)
        return None
```

---

## 2. ToolHandle Consolidation

### Current (two class defs)
- `ToolHandle` abstract class in `tool.py` (defines interface)
- `_OrchestratorToolHandle` concrete subclass in `orchestrator.py` (implements it)

### New (one concrete class)

Create `backend/glarvis/handle.py`:

```python
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from glarvis.tool import TaskResult

class ToolHandle:
    """Single interface for tool-to-system communication.
    Created by orchestrator at registration time."""

    def __init__(self, orchestrator: Any, tool_name: str):
        self._orch = orchestrator
        self._name = tool_name

    @property
    def system(self):
        """Live SystemMonitor reference."""
        return self._orch.system_monitor

    async def post_to_board(self, content: str, author: str | None = None) -> int:
        return await self._orch.broadcast_board_post(author or self._name, content)

    async def open_popup(self, popup_type: str, data: dict) -> None:
        await self._orch._broadcast_msg({
            "type": "popup_open", "popup_type": popup_type,
            "tool_name": self._name, "data": data,
        })

    async def close_popup(self) -> None:
        await self._orch._broadcast_msg({
            "type": "popup_close", "tool_name": self._name,
        })

    async def close_named_popup(self, name: str) -> None:
        await self._orch._broadcast_msg({
            "type": "popup_close", "tool_name": name,
        })

    async def execute_tool(self, tool_name: str, **kwargs) -> TaskResult:
        return await self._orch.execute_tool(tool_name, kwargs)
```

### Changes to other files

**`tool.py`:**
- Remove the `ToolHandle` abstract class entirely
- Import `ToolHandle` from `handle.py` under `TYPE_CHECKING` for type hints
- Remove `BaseTool.system` attribute (access via `self.handle.system` instead, or keep as convenience property)

**`orchestrator.py`:**
- Remove `_OrchestratorToolHandle` class
- Import `ToolHandle` from `handle.py`
- `register()` does `tool.handle = ToolHandle(self, tool.name)`

### System access through handle

Tools access system monitor via `self.handle.system`:
```python
self.handle.system.state.windows          # live window list
self.handle.system.state.foreground_id    # focused window
self.handle.system.focus_window(id)       # actions
self.handle.system.search_programs("foo") # actions
```

**Optional convenience**: keep `self.system` on BaseTool as a property:
```python
@property
def system(self):
    return self.handle.system if self.handle else None
```

This way tools write `self.system.state.windows` (short) but it's backed by the handle. Can add this later if the longer form feels verbose.

---

## 3. System Monitor — Live Reference

### Current
- `prepare_for_turn()` loops over all tools and stamps `tool.system = sys_state` every LLM turn
- `sys_state` is `system_monitor.state` — the same object every time (mutated in place by monitor's `_update()` loop)
- Redundant: re-assigning the same reference repeatedly

### New
- Set `tool.system` (or `tool.handle.system`) once at registration
- `SystemMonitor.state` is mutated in place every 2s by `_update()` — always live
- Remove the state distribution loop from `prepare_for_turn()`
- `prepare_for_turn()` still reads `system_monitor.state` for `build_system_message()` (that's fine, it's reading the live state)

---

## Files Changed

| File | Changes |
|---|---|
| `backend/glarvis/handle.py` | **NEW** — concrete `ToolHandle` class |
| `backend/glarvis/tool.py` | Remove abstract `ToolHandle`, add `Keyword`/`Function`/`Intercept`, add `get_intercepts()`, `get_context_intercepts()`, remove `shortcuts`, remove `intercept()` |
| `backend/glarvis/orchestrator.py` | Remove `_OrchestratorToolHandle`, use `ToolHandle` from handle.py, intercept registry + dispatch, remove state stamping loop |
| `backend/glarvis/tools/general.py` | `SwitchWindow.get_intercepts()`, remove `__init__(monitor)` from FocusWindow/SearchPrograms/OpenProgram, use `self.system` or `self.handle.system` |
| `backend/glarvis/tools/multi_choice.py` | `get_context_intercepts()` replaces `intercept()` |
| `backend/glarvis/tools/core.py` | DebugContext shows intercept registry state |
| `backend/glarvis/pipeline.py` | Remove `system_monitor` args from tool constructors |
| `backend/glarvis/input_interceptor.py` | No changes (calls `orchestrator.try_intercept()` which is updated) |

---

## Implementation Status

The intercept system and system monitor changes are **already implemented** in the current working tree. What remains:

- [ ] Create `handle.py` with concrete `ToolHandle`
- [ ] Remove abstract `ToolHandle` from `tool.py`
- [ ] Remove `_OrchestratorToolHandle` from `orchestrator.py`
- [ ] Update `orchestrator.register()` to use new `ToolHandle`
- [ ] Decide on `self.system` convenience property vs `self.handle.system` only
