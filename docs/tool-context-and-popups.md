# Tool Context, Popups, and System Monitor

Design document for interconnected systems: session context (dynamic tool injection), popup windows, system monitor, and app sessions.

---

## 1. Session Context

### Problem

When a SessionTool is active, the agent often needs temporary capabilities. A multi-choice selector needs "select option N" and "close". A notepad session needs "save" and "copy to clipboard". These tools only make sense while the session's context is active.

### Core concept: session alive ≠ context active

Sessions have three states:
- **Dormant** — session exists, has state, but its context tools are NOT in the LLM prompt. Shows as a chip in TaskDisplay.
- **Active context** — session's context tools are injected into the LLM prompt. The agent "knows about" this session.
- **Closed** — done, cleaned up, removed.

Most sessions are dormant most of the time. Context is entered/exited explicitly.

### Context activation triggers

| Trigger | How |
|---------|-----|
| User clicks task chip | UI → backend |
| Agent calls `enter_session(id)` | Tool call |
| Window focus (AppSessionTool only) | SystemMonitor auto-detection |

### Context deactivation triggers

| Trigger | How |
|---------|-----|
| User clicks chip again / different chip | UI → backend |
| Agent calls `exit_session(id)` | Tool call |
| Window loses focus (AppSessionTool only) | SystemMonitor auto-detection |
| Session closes | Automatic |

### Design

SessionTool gets context-related methods:

```python
class SessionTool(AsyncTool):
    def get_context_tools(self) -> list[FunctionSchema]:
        """Tools available while this session's context is active.
        Override to inject temporary tools. Can vary based on state."""
        return []

    async def handle_context_call(self, tool_name: str, **kwargs) -> TaskResult:
        """Handle a call to one of this session's context tools."""
        ...
```

Context tools are **additive** — they stack on top of the base tool set. The user can still ask the time while in a notepad session.

### Orchestrator changes

The orchestrator tracks which session(s) have active context. On each LLM turn:
1. Collect context tools from all active-context sessions
2. Update `LLMContext.tools` with base tools + context tools
3. Route context tool calls to the owning session's `handle_context_call()`

Since Pipecat allows updating `LLMContext.tools` at runtime (the LLM reads it fresh each turn), no pipeline rebuild is needed.

### Built-in tools for context management

```python
enter_session(id: int)   # activate a session's context
exit_session(id: int)    # deactivate a session's context
```

These are always available as base tools. The agent uses them to switch context programmatically.

---

## 2. ToolHandle (scoped API for tools)

### Problem

SessionTools need to interact with the UI (open popups, post to board) without coupling to the orchestrator directly.

### Design

A small interface given to tools at registration:

```python
class ToolHandle:
    """Scoped API for tool-to-system communication. Set by orchestrator."""

    async def open_popup(self, popup_type: str, data: dict) -> None:
        """Tell frontend to open a popup window."""
        ...

    async def close_popup(self) -> None:
        """Tell frontend to close this tool's popup."""
        ...

    async def post_to_board(self, content: str) -> int:
        """Post markdown to the board. Returns post index."""
        ...
```

Set on BaseTool at registration:

```python
class BaseTool(ABC):
    handle: ToolHandle | None = None  # set by orchestrator on register
    system: SystemMonitor | None = None  # set by orchestrator on register
```

Tools use `self.handle.open_popup(...)` instead of reaching into the orchestrator.

---

## 3. Popup Windows (Tauri Native Overlays)

### Problem

Tools need to show UI outside the main app: multi-choice selectors, transcriber overlays, etc. These must be visible when the main app is in the background (e.g., user is working in another app and interacting by voice).

Browser `window.open()` popups were rejected: blocked by popup blockers, can't stay always-on-top, look ugly with browser chrome, and disappear behind other windows.

### Design

Popups are **Tauri native windows** via `WebviewWindow` from `@tauri-apps/api/webviewWindow`. Each popup:
- Is a separate native window (frameless, always-on-top, centered, skip-taskbar)
- Renders a Svelte component from `popup.html` (multi-page Vite build)
- Communicates with the main window via **Tauri events** (`emit`/`listen` from `@tauri-apps/api/event`)
- Main window relays actions over the existing WebSocket to the backend
- Auto-closes itself after sending an action

### Message flow

```
Backend                     Main window                  Popup window (Tauri)
   │                             │                            │
   ├─ ws: popup_open ───────────►│                            │
   │                             ├─ new WebviewWindow() ─────►│ renders Svelte
   │                             │                            │
   │                             │◄── emit('popup-action') ───┤ user clicks/keys
   │◄── ws: popup_action ────────┤                            │ self.close()
   │                             │                            │
   ├─ ws: popup_close ──────────►│                            │
   │                             ├─ win.close() ─────────────►│
```

### Window properties

```javascript
new WebviewWindow(label, {
  url: 'popup.html#<encoded-data>',
  decorations: false,     // no title bar
  alwaysOnTop: true,      // visible over other apps
  center: true,           // centered on screen
  resizable: false,
  skipTaskbar: true,      // no taskbar entry
  width: 420, height: 360,
  transparent: false,     // WebView2 transparency is broken on Windows
});
```

### Popup types

- `multi_choice` — numbered options, select by number key/click/voice

### Frontend structure

```
web/
  popup.html                  # minimal HTML shell (dark bg, loads popup.js)
  src/popup.js                # reads hash data, mounts correct Svelte component
  src/lib/popups/
    MultiChoice.svelte        # multi-choice popup UI + Tauri event emitting
```

### Tauri permissions required

```json
// web/src-tauri/capabilities/default.json
{
  "windows": ["main", "popup_*"],
  "permissions": [
    "core:window:allow-create", "core:window:allow-close",
    "core:webview:allow-create-webview-window", "core:event:default"
  ]
}
```

---

## 4. Multi-Choice Selector

First concrete use of session context + popups.

### Flow

```
1. Agent calls show_choices(options=["A", "B", "C"], prompt="Which one?")
2. show_choices is a SessionTool:
   a. Opens popup window via self.handle.open_popup()
   b. Injects context tools: select_option(number), dismiss()
   c. Returns TaskResult(result="Choices shown", guide="Pick a number")
3. User says "two"
4. LLM calls select_option(number=2) → routed to handle_context_call()
5. Session resolves choice, closes popup, ends session
6. Context tools removed
```

### Why no special voice detection

The LLM naturally maps "two" / "the second one" / "option two" to `select_option(number=2)`. "Nevermind" / "close" maps to `dismiss()`. Freeform input that isn't a number is just normal conversation — the session handles it via `on_input()`.

### Implementation

See `backend/glarvis/tools/multi_choice.py`. Key design choices:

- `run()` blocks on `asyncio.Event` — keeps the session alive in TaskManager until a choice is made or dismissed
- `cancel_on_interruption = False` — user interruption shouldn't kill the popup
- `persist_in_display = False` — transient, auto-hides after completion
- Popup auto-closes itself after emitting an action (no dangling windows)
- Two convergent paths: voice ("two" → LLM → `select_option(2)`) and click (popup → Tauri event → WS → `handle_popup_action` → `handle_context_call`)

---

## 5. System Monitor

### Problem

Tools and context injection need live system state. Each tool querying independently is wasteful.

### Design

```python
class SystemMonitor:
    """Live system state. Updated by a background loop."""

    time: datetime              # property, not cached
    active_windows: list[WindowInfo]
    foreground_window: WindowInfo | None
    clipboard_text: str

    async def start(self): ...  # begin background loop
    async def stop(self): ...   # stop updates
```

```python
class WindowInfo:
    id: int              # stable integer, e.g. 0, 1, 2
    title: str           # "server.py - Visual Studio Code"
    process_name: str    # "code.exe"
    is_foreground: bool
```

### Window IDs

Integer IDs for reliable LLM references. No spelling/capitalization issues:

```
[Active Windows]
0: Notepad — untitled.txt
1: VS Code — server.py
2: Chrome — GitHub (3 tabs)
```

Agent calls `focus_window(id=1)` instead of guessing the title string.

### Wiring

- Orchestrator owns the SystemMonitor, starts it on pipeline creation
- On `register(tool)`: sets `tool.system = self.system_monitor`
- Context injection reads from SystemMonitor for ambient state in system message
- BaseTool gets `system: SystemMonitor | None = None`

### Update rates

- Time: property (`datetime.now()`), not polled
- Active windows: every 2-3 seconds
- Clipboard: every 1 second
- System resources: every 5-10 seconds (if needed)

---

## 6. AppSessionTool (future — not building now)

A specialization of SessionTool for window-bound interactions.

### Concept

```python
class AppSessionTool(SessionTool):
    """Session that auto-activates context when its app is in the foreground."""

    def matches_window(self, window: WindowInfo) -> bool:
        """Does this window belong to this tool's app?"""
        ...

    @property
    def is_focused(self) -> bool:
        return self.system and self.matches_window(self.system.foreground_window)
```

- Context auto-activates when the matched window gains focus
- Context deactivates when it loses focus
- Capabilities can vary based on focus (`get_context_tools()` checks `self.is_focused`)
- For UI automation: typing, clicking, scrolling (only when focused)

### Distinction from SessionTool

- **SessionTool**: API-level interaction, always available when context is active. E.g., managing a Claude agent via SDK.
- **AppSessionTool**: UI-level interaction, focus-dependent. E.g., typing in a terminal, clicking buttons.

Same app might have both: a SessionTool for API control and an AppSessionTool for live terminal interaction. These are genuinely different concerns — one manages the agent, the other interacts with the terminal window.

### Multiple windows

When an app has multiple windows (e.g., two VS Code instances), the agent can see all windows in SystemMonitor context and use multi-choice to disambiguate before entering a session. Tool descriptions can instruct this: "use show_choices first if there are multiple matching windows."

---

## 7. Build Order

1. **Session context system** — `get_context_tools()`, `handle_context_call()`, dynamic LLMContext.tools in orchestrator, `enter_session`/`exit_session` tools, task chip click → enter context
2. **ToolHandle** — scoped API for tools (popup, board access)
3. **Popup infrastructure** — WebSocket message types, `window.open()`, `postMessage` relay
4. **Multi-choice selector** — first SessionTool using context + popups
5. **SystemMonitor** — background loop, BaseTool integration, context injection, window IDs
6. **Real tools** — open_program, focus_window, list_processes (using SystemMonitor)
7. **AppSessionTool** — focus-driven context activation (when needed)

Steps 1-4 are tightly coupled. Step 5 is independent. Steps 6-7 depend on 5.
