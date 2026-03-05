# Tool System

## Overview

Tools are the primary way the agent interacts with the system. Each tool is a Python class that subclasses `Tool` (in `glarvis/tool.py`) and declares two layers of metadata:

1. **LLM-facing** — what the model sees: name, description, parameters, required
2. **System-facing** — what the orchestrator uses: notification level, display mode, TTL, hooks

The LLM never sees the system-facing metadata. It just calls tools by name. The orchestrator reads the metadata to decide how to execute the tool and route its results.

## Tool base class (`glarvis/tool.py`)

```python
class Tool:
    # LLM-facing
    name: str              # function name the LLM calls
    description: str       # what the LLM sees in the schema
    parameters: dict       # JSON Schema properties
    required: list[str]    # required parameter names

    # System-facing
    notification: "silent" | "notify" | "interrupt"  # how to alert the user
    display: "board" | "speak" | "both" | "none"     # where to show results
    ttl: int | None        # max seconds before expiry, None = no limit
    cancel_on_interruption: bool  # cancel if user interrupts

    async def run(self, **kwargs) -> TaskResult  # override this
```

### TaskResult

Every tool returns a `TaskResult`:
- `value` — the raw result (goes to LLM context via result_callback)
- `display_text` — what to show on the board/terminal
- `speak_text` — what to say aloud (only for notify/interrupt tools)

### Lifecycle hooks

Override these in subclasses for custom behavior:
- `on_start()` — called when execution begins
- `on_progress(update)` — called by the tool itself to report progress
- `on_complete(result)` — called after run() succeeds
- `on_expire()` — called if TTL is exceeded

### Pipecat integration

`to_function_schema()` converts the tool to Pipecat's `FunctionSchema` format for registration with the LLM service.

## Inline vs async execution

The orchestrator decides execution mode implicitly from the tool's metadata:

```python
if tool.ttl or tool.notification != "silent":
    # Async — spawn on the Board, return placeholder to LLM
    await board.spawn(tool, kwargs)
else:
    # Inline — run directly, return result to LLM immediately
    await tool.run(**kwargs)
```

**Inline tools** (silent + no TTL): execute in the handler, result goes straight to LLM. Good for fast lookups (get_time, simple queries).

**Async tools** (has TTL or non-silent notification): spawned on the Board as asyncio tasks. The LLM gets a "task started" placeholder. The Board manages lifecycle, TTL enforcement, and completion routing.

## Example tools (`glarvis/tools/examples.py`)

| Tool | Notification | Display | TTL | Execution |
|------|-------------|---------|-----|-----------|
| GetTime | silent | none | - | inline |
| ListDirectory | silent | board | - | inline |
| SearchFiles | notify | board | 15s | async (Board) |

## Writing a new tool

1. Create a class that subclasses `Tool`
2. Set the LLM-facing fields (name, description, parameters, required)
3. Set the system-facing fields (notification, display, ttl)
4. Implement `async def run(self, **kwargs) -> TaskResult`
5. Register it in main.py: add to the `tools` list

The orchestrator and board handle everything else — schema registration, execution routing, result delivery, and context management.

## Important: result_callback

Tool results ALWAYS go back to the LLM via `result_callback`. See `docs/tool-results-and-context.md` for why. Never use `run_llm=False` — let the system prompt control verbosity.
