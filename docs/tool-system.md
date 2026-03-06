# Tool System

## Overview

Tools are the primary way the agent interacts with the system. Each tool subclasses one of three types defined in `backend/glarvis/tool.py`:

- **InlineTool** — runs directly in the LLM turn, returns result immediately
- **AsyncTool** — spawns on TaskManager as a background task
- **SessionTool** — long-lived interactive tool that accepts subsequent input

The orchestrator routes by `isinstance()` check, not metadata inference.

## Tool types

### BaseTool (ABC)

Abstract base class. Cannot be instantiated directly. Declares the interface:

```python
class BaseTool(ABC):
    name: str              # function name the LLM calls
    description: str       # what the LLM sees in the schema
    parameters: dict       # JSON Schema properties
    required: list[str]    # required parameter names
    cancel_on_interruption: bool = True

    async def run(self, **kwargs) -> TaskResult  # override this
    def to_function_schema() -> FunctionSchema   # auto-generates Pipecat schema
```

### InlineTool

- Runs directly in the LLM turn, blocks until complete
- Does NOT appear in TaskDisplay, never enters TaskManager
- Good for: get_time, read_file, write_board, quick lookups
- Default: notification="silent", display="none"

### AsyncTool

- Spawns on TaskManager as an asyncio task
- Appears in TaskDisplay as a chip while running
- `persist_in_display = False` — auto-hides from TaskDisplay on completion
- LLM gets a placeholder result ("Task task_1 started"), real result arrives via snapshot on next turn
- Has TTL support (optional timeout)
- Has `task_display_status()` for custom chip text
- Good for: search_codebase, downloads, builds
- Default: notification="notify", display="board"

### SessionTool (extends AsyncTool)

- Long-lived interactive tool, stays alive after initial `run()`
- Subsequent LLM calls route to `on_input()` instead of spawning new task
- Has `close()` method for cleanup
- `persist_in_display = True` — stays visible in TaskDisplay
- No TTL by default
- Good for: Claude Code, browser automation, stateful interactions
- **Note**: `on_input()` routing is not yet wired in the orchestrator

## TaskResult

```python
@dataclass
class TaskResult:
    result: Any = None           # raw data for LLM context
    guide: str | None = None     # natural language hint for the LLM
    board_content: str | None = None  # rich markdown for Board display
```

- `result`: goes to LLM via result_callback. The LLM sees this.
- `guide`: suggestion for what the LLM might say. Not a script — LLM can rephrase or ignore.
- `board_content`: markdown posted to the Board stream. The LLM does NOT see this.

## Current tools (`backend/glarvis/tools/examples.py`)

| Tool | Type | Description |
|------|------|-------------|
| GetTime | InlineTool | Returns current date and time |
| ListDirectory | InlineTool | Lists files, posts to board |
| SearchFiles | AsyncTool | Searches files by pattern, posts to board |
| WriteBoard | InlineTool | Posts arbitrary markdown to the board |
| ListTools | InlineTool | Lists all registered tools on the board |
| DebugContext | InlineTool | Dumps full LLM context, messages, and task state to board |

## Writing a new tool

1. Subclass `InlineTool`, `AsyncTool`, or `SessionTool`
2. Set `name`, `description`, `parameters`, `required`
3. Implement `async def run(self, **kwargs) -> TaskResult`
4. Register in `server.py`: `orchestrator.register(MyTool())`

Tools that need a reference to the orchestrator (like ListTools, DebugContext) take it as a constructor arg.

## Result routing

Tool results ALWAYS go back to the LLM via `result_callback`. The system prompt controls whether the agent speaks about them. See `tool-results-and-context.md` for details.
