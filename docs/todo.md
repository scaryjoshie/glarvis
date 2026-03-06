# TODO

## Next Up (build order)

### 3. Popup infrastructure
- WebSocket message types: `popup_open`, `popup_close`, `popup_action`
- `window.open()` wrapper in frontend
- `postMessage` relay from popup → main app → WebSocket
- Minimal popup HTML shell + Svelte rendering
- Frontend: `web/src/lib/popups/`

### 4. Multi-choice selector
- First SessionTool using context + popups
- `show_choices(options, prompt)` → opens popup, injects select_option/dismiss
- LLM naturally maps "two" → `select_option(number=2)`
- `persist_in_display = False` (transient)

### 5. SystemMonitor
- Background update loop for live system state
- `WindowInfo` with stable integer IDs (no spelling issues for LLM)
- Set on `BaseTool.system` by orchestrator
- Context injection reads from it for ambient state in system message
- Tracks: active windows, foreground window, clipboard, time

### 6. Real tools (using SystemMonitor)
- `open_program` (InlineTool) — launches a program
- `focus_window(id)` (InlineTool) — brings window to front by ID
- `read_file` (InlineTool) — reads file, posts to board
- `search_codebase` (AsyncTool) — searches files, posts to board
- `list_processes` (InlineTool) — lists running processes
- Tool descriptions instruct agent to use multi-choice for disambiguation

### 7. AppSessionTool (future)
- Focus-driven context activation via SystemMonitor
- `matches_window()` to detect which app
- Auto-enter context on foreground, auto-exit on background
- Capabilities vary by focus state (UI automation only when focused)
- See design doc for full spec

### Other
- Claude Code bridge (SessionTool for SDK, AppSessionTool for terminal)
- Agent memory (persist key facts across sessions)
- Frontend: settings panel, styling polish
- Transcriber popup (future popup type)

## Done

- Session context system (get_context_tools, handle_context_call, dynamic LLMContext.tools, enter/exit_session tools, chip click → context toggle, on_input routing, auto-enter/exit context)
- ToolHandle (scoped API: post_to_board, open_popup, close_popup — subclass pattern with _OrchestratorToolHandle)
- Tool type system (BaseTool ABC → InlineTool/AsyncTool/SessionTool)
- Orchestrator routes by isinstance() check
- TaskResult with result/guide/board_content
- Board stream (array of posts with sidebar, hover preview)
- TaskDisplay (horizontal scrolling chips, board linking, clear button, session context toggle with purple highlight)
- `persist_in_display` (AsyncTool=False, SessionTool=True)
- Text input alongside voice (TranscriptionFrame injection)
- Discord-style voice controls (mute, deafen, connect/disconnect, quick tools)
- WriteBoard, ListTools, DebugContext, EnterSession, ExitSession tools
- Tool call args + results in transcript
- Welcome board post on connect
- Session state clear on connect/disconnect
- Backend moved to `backend/` subfolder
- SmallWebRTCTransport (browser AEC)
