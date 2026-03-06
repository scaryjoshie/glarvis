# Design Decisions

This document captures all architectural and design decisions made during development.
It exists so that future agents or compacted sessions don't lose critical context.

---

## Naming Conventions

| Name | What it is | Status |
|------|-----------|--------|
| **BaseTool** | Abstract base class for all tools (ABC, cannot instantiate) | Exists in `glarvis/tool.py` |
| **InlineTool** | Runs directly in LLM turn, returns result immediately | Exists in `glarvis/tool.py` |
| **AsyncTool** | Spawns on TaskManager, completes in background | Exists in `glarvis/tool.py` |
| **SessionTool** | Long-lived, accepts subsequent input via on_input() | Exists in `glarvis/tool.py` |
| **TaskManager** | Backend task lifecycle (spawn, track, complete, notify) | Exists in `glarvis/task_manager.py` |
| **Board** | Rich display surface for the UI (markdown, diagrams, content) | Not yet built |
| **TaskDisplay** | UI component showing live task status (top bar) | Frontend exists but needs work |
| **Orchestrator** | Wires tools, TaskManager, and Pipecat pipeline together | Exists in `glarvis/orchestrator.py` |

- Do NOT put "Glarvis" in class/function names — the name hasn't been decided yet.
- The project folder `glarvis/` is fine, just not class names.
- `BoardContextInjector` is fine since "Board" is a real component name.

---

## Tool Type System

### Why three subclasses instead of flags or metadata inference?

Previously, the system had a single `Tool` class. Inline vs async was inferred from metadata:
```python
if tool.ttl or tool.notification != "silent":
    # async
else:
    # inline
```

Decision: BaseTool is an ABC. You MUST subclass InlineTool, AsyncTool, or SessionTool. The orchestrator routes by isinstance() check. This was also preferred over a `session=True` flag because SessionTool has a genuinely different method contract (on_input, close).

The user also asked: "should we not have async tools then? Should async just be session tools with no extra ways to call?" We decided to keep AsyncTool separate because most background tasks are fire-and-forget (search, download, build) and forcing tool authors to implement on_input()/close() for those is unnecessary boilerplate. An AsyncTool is essentially a SessionTool that can't receive additional input — the distinction is worth keeping for ergonomics.

### InlineTool
- Runs directly in the LLM turn, blocks until complete
- Does NOT appear in TaskDisplay (default: silent notification, no display)
- No persistence — fire and forget
- Each call creates a fresh run(), no state carries over
- Good for: get_time, read_file, quick lookups
- Default notification: "silent", default display: "none"

### AsyncTool
- Spawns on TaskManager as asyncio task
- DOES appear in TaskDisplay
- Stays in TaskDisplay after completion (doesn't immediately vanish — user may want to revisit)
- LLM gets a placeholder result ("Task task_1 started"), real result arrives via snapshot on next turn
- Has lifecycle hooks: on_start(), on_progress(), on_complete(), on_expire()
- Has TTL support (optional timeout)
- Has task_display_status() for custom TaskDisplay rendering
- Good for: search_codebase, downloads, builds, anything that takes time
- Default notification: "notify", default display: "board"

### SessionTool (extends AsyncTool)
- Long-lived interactive tool, stays alive after initial run()
- Subsequent LLM calls to the same tool route to on_input() instead of spawning new task
- Orchestrator checks isinstance(tool, SessionTool) — if active task exists, routes to on_input()
- Has close() method for cleanup when cancelled/dismissed
- No TTL by default (sessions don't expire)
- Good for: Claude Code, browser automation, anything maintaining state across interactions
- on_input() is abstract — must be implemented

### Orchestrator routing logic:
```python
if isinstance(tool, SessionTool) and tool_has_active_task:
    route to on_input()
elif isinstance(tool, AsyncTool):
    spawn on TaskManager
else:  # InlineTool
    run inline
```

---

## TaskResult

```python
@dataclass
class TaskResult:
    result: Any = None           # raw data for LLM context
    guide: str | None = None     # natural language hint for the LLM
    board_content: str | None = None  # rich markdown for Board stream
```

- `result`: raw data that goes into LLM context via result_callback. The LLM sees this.
- `guide`: a natural language suggestion for what the LLM might say. NOT a script — the LLM can rephrase, expand, or ignore it. Allows reasoning over tool output without forcing the LLM to interpret raw data every time.
- `board_content`: rich markdown that goes directly to the Board stream in the UI. The LLM does NOT see this. Used for tables, code, file listings, etc.

Previous field names (now obsolete): `value` → `result`, `display_text` and `speak_text` → replaced by `guide` and `board_content`.

---

## UI Layout

```
┌──────────────────────────────────────────────────────┐
│ TaskDisplay (top bar)                                │
│ ┌──────┐ ┌──────────┐ ┌─────────┐                   │
│ │ icon │ │  icon     │ │  icon   │  ← task chips     │
│ └──────┘ └──────────┘ └─────────┘                    │
├───────────────┬──────────────────────┬───────────────┤
│               │                      │ Board Stream  │
│  Transcript   │   Board (main)       │ (right sidebar│
│  (left)       │                      │  chronological│
│               │   expanded task      │  feed)        │
│  scrolling    │   detail, or content │               │
│  conversation │   user/LLM asked to  │  click item   │
│  log          │   display            │  to maximize  │
│               │                      │  in main area │
├───────────────┴──────────────────────┴───────────────┤
│ StatusBar (bottom)                                    │
│ ◉ listening   Claude Haiku 4.5        ~~~ voice viz  │
└──────────────────────────────────────────────────────┘
```

- **TaskDisplay (top)**: compact task chips/icons. Shows async/session tasks. Inline tasks do NOT show here.
  - Hover → expand to show details (progress log, elapsed, tool-specific info)
  - Click → enter task context (agent gets context hint like "[User focused on task_3: search_files]")
  - Click also expands task detail in the main Board area
  - Tasks don't vanish immediately after completion — they linger so user can revisit
- **Transcript (left)**: scrolling conversation log. User speech, agent responses, tool call indicators.
- **Board (center/main)**: rich content area. Shows whatever was last clicked/focused. Ephemeral — shows expanded task detail or content posted by tools/LLM.
- **Board Stream (right sidebar)**: chronological feed of items posted to the board. Auto-saves. Click an item to maximize it in the main Board area. Items have author (tool name) and timestamp.
- **StatusBar (bottom)**: mic state, model name, voice visualization.

### Board content model
- Items flow into the stream chronologically
- Each item has: author (tool name or LLM), timestamp, markdown content
- Clicking an item shows it in the main Board area
- Board items auto-save to the stream
- The main area is ephemeral — just shows the currently focused item

### TaskDisplay behavior
- Inline tasks skip TaskDisplay entirely
- Async tasks appear when spawned, stay after completion (fade/collapse eventually but don't disappear)
- Progress updates (post_progress) update the task chip/icon
- Completion can optionally write to the Board stream (via board_content in TaskResult)
- Notifications can pop up even when Board stream item exists

---

## Tool Output and the LLM

Tools should NOT dictate exactly what the agent says. Instead:
- `result` provides raw data the LLM can reason over
- `guide` provides a natural language suggestion the LLM can use, rephrase, or ignore
- This allows the LLM to reason: "the user asked X, the tool found Y, but given context Z, I should say W"
- The LLM handles the voice side; the tool handles the visual side (board_content)

---

## Async Tools and LLM Context

Async tool results reach the LLM through the task state snapshot injected into the system message before each turn. The snapshot includes:
- Running tasks with progress
- Recent completions with results
- Pending notifications

This means the LLM sees async results on the NEXT user turn (when the user speaks and triggers a new LLMRunFrame). There is currently no mechanism for a task to proactively trigger an LLM turn — this is a future enhancement if needed.

Tool results ALWAYS go back to the LLM via result_callback (see docs/tool-results-and-context.md). Never use run_llm=False.

---

## Processes vs Tools

We discussed tracking external processes (VS Code, Claude Code instances, browsers) in the TaskDisplay. The decision:
- This is NOT about tools spawning processes
- It's about DISCOVERY: a background scanner detects what's running and surfaces it in TaskDisplay
- Clicking a discovered process could activate a tool/context for interacting with it
- The TaskManager would track both internally-spawned tasks AND externally-discovered processes
- This adds complexity and we DO NOT build it yet — add it later as its own module

---

## Echo Cancellation

- LocalAudioTransport (PyAudio) has NO echo cancellation
- Pipecat's answer: AEC is a client/transport concern
- WebRTC transports (SmallWebRTCTransport, DailyTransport) get browser-native AEC for free
- We switched to SmallWebRTCTransport to solve this
- Pipecat's audio filters (Krisp, AIC, noisereduce, etc.) are noise reduction, NOT echo cancellation

---

## Context Injection

Currently: BoardContextInjector intercepts LLMRunFrame and appends task state snapshot to the system message.

Future plan: expand context injection to include ambient system state:
```
[System Context]
  Time: 2:34 PM, Thursday March 6
  Active windows: VS Code (main.py), Chrome (3 tabs), Terminal
  System: 8.2 GB RAM free, CPU 12%
```

This would use system utility libraries that tools also import:
```
glarvis/
  system/
    windows.py    # list_windows(), focus_window(), etc.
    processes.py  # list_processes(), open_program(), etc.
    time.py       # current_time(), timers, etc.
    clipboard.py  # get/set clipboard
```

Tools import these libraries. The context injector also imports them for ambient state. This way the agent knows basic system info without making tool calls.

---

## Tool-Defined Board Views

Each tool can define how it renders on the Board when expanded:
- Default: render board_content as markdown (sufficient for almost everything)
- Override board_view() for custom rendering (future: live graphs, terminal output, etc.)
- We do NOT build custom rendering infrastructure now — markdown is enough
- The hook exists so future tools can customize without changing the framework

---

## LLM Configuration

- Currently using Anthropic Claude Haiku 4.5 (model: claude-haiku-4-5-20251001)
- Can swap to Sonnet 4.6 (claude-sonnet-4-6-20250514) for more reasoning
- OpenAI-compatible (Cerebras gpt-oss-120b) also available — commented out in code
- Cartesia Sonic-3 TTS, speed 1.25x
- Deepgram STT
- Silero VAD: confidence=0.8, start=0.2s, stop=0.8s, min_volume=0.6

---

## System Prompt Design

The system prompt is tuned for a terse voice assistant:
- First person, friendly but concise
- Answers questions directly but briefly
- Doesn't explain actions unless asked
- User requests override all rules
- No markdown, bullets, or special characters (spoken aloud)
- Empty responses are fine (silence is ok)

Key lesson learned: don't say "never explain" — say "don't explain unprompted, but give details when asked."
