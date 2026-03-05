# TaskManager and Orchestrator

## TaskManager (`glarvis/task_manager.py`)

The TaskManager is the central state manager for async tasks. It tracks active tasks, maintains completion history, and queues notifications.

### State model

```
TaskState:
    id: str                  # "task_1", "task_2", ...
    tool: Tool               # reference to the tool instance
    status: pending | running | completed | failed | expired
    started_at: float
    completed_at: float | None
    result: TaskResult | None
    progress: str | None     # latest progress message
    _task: asyncio.Task      # the actual coroutine
```

### Key methods

- `spawn(tool, kwargs)` — creates an asyncio task, tracks it, enforces TTL
- `post_progress(task_id, update)` — tools call this mid-execution to report progress
- `snapshot()` — renders current state as text for LLM context injection. Returns None if empty (saves tokens).
- `drain_notifications()` — pops all pending notifications (called by orchestrator)

### Completion routing

When a task completes, `_handle_completion()` routes the result based on tool metadata:
- `display="board"` or `"both"` — prints to terminal (future: sends to Board display in UI)
- `notification="notify"` or `"interrupt"` — queues a Notification, calls `on_notification` callback
- `notification="silent"` — no notification

After routing, the task moves from `active` to `history` (capped at 20 entries).

### Notification

```
Notification:
    task_id: str
    message: str           # from TaskResult.speak_text or default "{tool.name} has completed"
    level: "notify" | "interrupt"
```

## Orchestrator (`glarvis/orchestrator.py`)

The Orchestrator wires tools into Pipecat. It sits between the tool system and the pipeline.

### Responsibilities

1. **Register tools** — creates a Pipecat function handler per tool, registers with `llm.register_function()`
2. **Execute tools** — decides inline vs TaskManager spawn based on tool metadata
3. **Inject context** — updates system message with task state before each LLM turn
4. **Deliver notifications** — pushes TTSSpeakFrame into pipeline when TaskManager notifications fire

### Registration flow

```
orchestrator.register(tool)
  -> creates _handler(params) closure
  -> calls llm.register_function(tool.name, _handler)
  -> _handler routes to _execute_tool() then result_callback()
```

### Context injection

`inject_task_context()` is called by `BoardContextInjector` (a FrameProcessor) before each LLM turn. It appends the TaskManager's snapshot to the system message so the LLM knows about active/completed tasks.

The original system message is preserved; the snapshot is appended fresh each turn.

### Notification delivery

When the TaskManager fires `on_notification`, the orchestrator creates a `TTSSpeakFrame` and queues it on the `PipelineTask`. This causes the TTS to speak the notification. Currently there's no distinction between "notify" (queue) and "interrupt" (preempt) — both push immediately.

## BoardContextInjector (`glarvis/context_injector.py`)

A thin FrameProcessor that:
1. Logs STT output when it sees a `TranscriptionFrame`
2. Calls `orchestrator.inject_task_context()` when it sees an `LLMRunFrame`
3. Passes all frames through unchanged

Sits in the pipeline between UserAggregator and LLM.

## SpeechGate (`glarvis/gate.py`)

Built but NOT currently in the pipeline. A wake-word gate that:
- In LISTENING mode: swallows transcriptions unless they contain a wake word
- In ACTIVE mode: passes everything through for 30s, then reverts
- Wake words: configurable, defaults include common mishearings
- Strips the wake word from the transcription before passing through

Would go between STT and UserAggregator if enabled.
