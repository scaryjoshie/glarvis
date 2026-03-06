# TaskManager, Orchestrator, and Board

## TaskManager (`backend/glarvis/task_manager.py`)

Manages the lifecycle of async/session tasks.

### TaskState

```python
@dataclass
class TaskState:
    id: str                    # "task_1", "task_2", ...
    tool: AsyncTool            # reference to the tool instance
    status: str                # pending | running | completed | failed | expired
    started_at: float
    completed_at: float | None
    result: TaskResult | None
    progress: str | None       # latest progress message
    board_post_index: int | None  # links to a board post in the UI
    _task: asyncio.Task        # the actual coroutine
```

### Key methods

- `spawn(tool, kwargs)` — creates an asyncio task, tracks it, enforces TTL
- `post_progress(task_id, update)` — tools call this mid-execution to report progress
- `snapshot()` — renders current state as text for LLM context injection (returns None if empty)
- `to_ui_list()` — serializes tasks for the frontend, filtering by `persist_in_display`

### Callbacks

- `on_notification(notif)` — fired when a task completes with notify/interrupt level
- `on_change()` — fired on any task state change (broadcasts to UI)
- `on_board_post(task_id, author, content)` — fired when an async task posts to the board

### Completion routing

When a task completes, `_handle_completion()`:
1. Routes `board_content` to the board via `on_board_post`
2. Queues a `Notification` if notification level is "notify" or "interrupt"
3. Moves the task from `active` to `history` (capped at 20)

### Task visibility

- `persist_in_display = False` (AsyncTool default): task chip removed from UI after completion
- `persist_in_display = True` (SessionTool default): task chip stays visible
- InlineTools never enter TaskManager at all

## Orchestrator (`backend/glarvis/orchestrator.py`)

Wires tools, TaskManager, Pipecat pipeline, and UI together.

### Responsibilities

1. **Register tools** — creates Pipecat function handlers, registers with LLM
2. **Execute tools** — routes by isinstance(): InlineTool runs inline, AsyncTool/SessionTool spawns on TaskManager
3. **Inject context** — updates system message with task state snapshot before each LLM turn
4. **Deliver notifications** — pushes TTSSpeakFrame into pipeline for spoken notifications
5. **Broadcast to UI** — sends transcript entries, board posts, and task updates via WebSocket

### Execution routing

```python
if isinstance(tool, SessionTool):
    # TODO: check for active session, route to on_input()
    task_id = await task_manager.spawn(tool, kwargs)
elif isinstance(tool, AsyncTool):
    task_id = await task_manager.spawn(tool, kwargs)
else:  # InlineTool
    result = await tool.run(**kwargs)
    if result.board_content:
        await broadcast_board_post(tool.name, result.board_content)
```

### UI broadcasting

The orchestrator holds a `broadcast` function (set by server.py) for pushing to WebSocket clients:

- `broadcast_transcript(role, text, entry_type, tool, tool_args, tool_result)` — transcript entries
- `broadcast_board_post(author, content)` — board posts (returns post index for linking)
- `broadcast_welcome()` — posts available tools listing on connect
- Task updates are broadcast via `on_change` callback from TaskManager

### Board post linking

The orchestrator tracks a `_board_post_index` counter. When a board post is created, the index is stored on the corresponding `TaskState.board_post_index`. The frontend uses this to link task chips to board items (clicking a chip focuses the linked board post).

## BoardContextInjector (`backend/glarvis/context_injector.py`)

A FrameProcessor that intercepts `LLMRunFrame` and calls `orchestrator.inject_task_context()` to append the task state snapshot to the system message before each LLM turn.

## Board (frontend)

The board is a stream of markdown posts displayed in the right panel of the UI.

### Data model

Each board post has: `author` (tool name or "minerva"), `timestamp`, `content` (markdown).

Posts are stored in `boardStream` (Svelte writable array). `boardFocused` tracks which post is shown in the main area.

### UI layout

- **Main area**: renders the focused post as HTML (via marked.js)
- **Stream sidebar**: chronological list of posts, click to focus, hover to preview
- Always visible, shows "No posts yet" when empty

### Welcome post

On WebRTC client connect, the orchestrator posts a welcome message listing all registered tools with their types (instant/background/session).
