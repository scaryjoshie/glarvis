# Design Decisions

Captures architectural and design decisions so future sessions don't lose context.

---

## Naming

The project is called **Minerva**. The Python package is `glarvis` (legacy name, kept for the package directory). Class names do not include "Glarvis" or "Minerva" — they use generic names (Orchestrator, TaskManager, etc.).

---

## Tool Type System

### Why three subclasses instead of flags?

Previously, a single `Tool` class used metadata inference:
```python
if tool.ttl or tool.notification != "silent":
    # async
else:
    # inline
```

Decision: BaseTool is an ABC. You MUST subclass InlineTool, AsyncTool, or SessionTool. The orchestrator routes by `isinstance()` check. This is explicit over implicit.

SessionTool extends AsyncTool rather than being a flag (`session=True`) because it has a genuinely different method contract (`on_input()`, `close()`).

AsyncTool is kept separate from SessionTool because most background tasks are fire-and-forget. Forcing `on_input()/close()` for those is unnecessary boilerplate.

### persist_in_display

Controls whether a task chip stays visible after completion:
- `AsyncTool.persist_in_display = False` — auto-hides (search results don't clutter the bar)
- `SessionTool.persist_in_display = True` — stays visible (sessions are long-lived)
- InlineTools skip TaskDisplay entirely (never enter TaskManager)

---

## TaskResult Design

```python
@dataclass
class TaskResult:
    result: Any = None
    guide: str | None = None
    board_content: str | None = None
```

- Tools suggest LLM speech via `guide`, don't dictate it
- `board_content` goes to the UI, not the LLM
- The LLM handles voice; the tool handles visual display

Previous field names (obsolete): `value` -> `result`, `display_text`/`speak_text` -> `guide`/`board_content`.

---

## UI Layout

```
+----------------------------------------------------+
| TaskDisplay (horizontal scrolling chips)            |
+---------------+--------------------+----------------+
|               |                    | Board Stream   |
|  Transcript   |   Board (main)    | (sidebar,      |
|  (left)       |                    |  always visible)|
|               |   focused post    |                |
|  + text input |   rendered as     |  hover=preview |
|  + VoiceCtrl  |   markdown/HTML   |  click=focus   |
+---------------+--------------------+----------------+
                | StatusBar (agent state, model)      |
                +-------------------------------------+
```

- **TaskDisplay**: horizontal scrolling chips. Clicking a chip with a `board_post_index` focuses that board post.
- **Transcript**: scrolling chat log with tool call args and results for debugging.
- **VoiceControls**: Discord-style — always visible, connect/disconnect toggle, mute, deafen, quick tool buttons, settings placeholder.
- **Board**: stream-based (array of posts). Main area + sidebar. Hover previews, click locks focus.
- **StatusBar**: sits in right column only, shows agent state dot + model name.

### Session state management

All session state (transcript, boardStream, tasks) clears on both connect and disconnect. The backend is fresh per WebRTC connection, so the frontend must match.

---

## Board Architecture

Board is a stream of posts, not a single content area. Each post has author, timestamp, and markdown content.

The stream sidebar is always visible. Hovering a stream item previews it in the main area; clicking locks the focus. This replaced an earlier design where the board was a single string that got overwritten.

Future interactive board: structured `actions` in TaskResult (buttons, forms), not JS injection.

---

## Tauri (Desktop App Wrapper)

### Why Tauri over browser-only?

Popup overlays need to be visible when the main app is in the background (voice assistant use case). Browser `window.open()` popups: get blocked by popup blockers, can't be always-on-top, show browser chrome, and disappear behind other windows.

### Why Tauri over Electron?

- ~5MB bundle vs ~150MB (Electron ships Chromium; Tauri uses system WebView2)
- Rust backend for native APIs (window management, system tray, etc.)
- Built-in transparent/frameless/always-on-top window APIs
- Lighter resource usage

Trade-off: smaller ecosystem, less mature tooling, WebView2 has some quirks (e.g., `transparent: true` makes everything invisible on Windows — we use solid dark backgrounds instead).

Electron is a viable fallback if we hit Tauri limitations. The frontend is standard Svelte/Vite — only the native window APIs would need swapping.

### Popup communication

Popups use **Tauri events** (`emit`/`listen` from `@tauri-apps/api/event`) instead of `window.postMessage()`. Events work across Tauri windows natively. The main window listens for `popup-action` events and relays them over WebSocket to the backend.

---

## Transport and Echo Cancellation

SmallWebRTCTransport runs audio through the browser, which provides native AEC. This solved the feedback loop from the old LocalAudioTransport (PyAudio) approach.

---

## Context Injection

BoardContextInjector appends the TaskManager snapshot to the system message before each LLM turn. The original system message is preserved; the snapshot is appended fresh each turn.

Future: expand to include ambient system state (time, active windows, system resources) using shared system utility libraries.

---

## System Prompt

Tuned for a terse voice assistant:
- Short responses (one sentence max for most things)
- Board-first for long content — don't read lists/data aloud
- Brief acknowledgment when posting to board ("it's on the board")
- Never list capabilities unprompted
- User requests override all rules
- No markdown/bullets/special characters (spoken aloud)

---

## LLM Configuration

- Anthropic Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
- Can swap to Sonnet 4.6 for more reasoning
- Cartesia Sonic-3 TTS at 1.25x speed
- Deepgram STT with default streaming
- Silero VAD: confidence=0.8, start=0.2s, stop=0.8s, min_volume=0.6

---

## Tool Results and LLM Context

Tool results ALWAYS go back to the LLM via `result_callback`. The system prompt controls whether the agent speaks about them. Never use `run_llm=False` — it breaks the agent's memory of prior tool calls. See `tool-results-and-context.md`.
