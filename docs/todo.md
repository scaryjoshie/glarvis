# TODO

## Next Up

### Agent Memory
- Persist key facts across sessions (user preferences, past decisions)
- Injection via system message or separate context

### Frontend Polish
- Settings panel UX refinements
- Styling polish and theming
- Transcriber popup (future popup type)

### Claude Code Bridge
- SessionTool wrapping Claude Code SDK
- AppSessionTool for terminal interaction (depends on AppSessionTool design)

### AppSessionTool (future)
- Focus-driven context activation via SystemMonitor
- `matches_window()` to detect which app
- Auto-enter context on foreground, auto-exit on background
- Capabilities vary by focus state (UI automation only when focused)
- See `tool-context-and-popups.md` for full spec

## Done

- SystemMonitor — background polling loop, WindowInfo with stable integer IDs, clipboard, foreground tracking, installed programs via Get-StartApps
- Real tools — `focus_window`, `search_programs`, `open_program`, `read_file` (all using SystemMonitor)
- Service registry — YAML-driven config for LLM/TTS/STT providers, dynamic class importing, CRUD API, settings modal
- Settings system — persistent settings.json, REST API, WebSocket sync, full frontend modal
- Mute system — soft mute (server-side gate, "unmute" keyword passthrough), hard mute (client-side mic toggle), dual UI states
- Input interception — `InputInterceptor` frame processor lets sessions claim voice input before the LLM
- Board notification popups — `BoardNotify.svelte` overlay when main window is unfocused
- Pipeline refactor — `PipelineSession` class, `build_session()` factory (code moved from server.py to pipeline.py)
- Popup infrastructure — Tauri native overlay windows (frameless, always-on-top, centered), WebSocket message types, Tauri events for popup→main communication, multi-page Vite build
- Multi-choice selector — `MultiChoiceSession` SessionTool, voice and click paths, popup auto-close, intercept for number words
- Tauri migration — native desktop app wrapper (WebView2 on Windows), enables native overlay popups
- Session context system — `get_context_tools`, `handle_context_call`, dynamic `LLMContext.tools`, `enter/exit_session` tools, chip click → context toggle, `on_input` routing, auto-enter/exit context
- ToolHandle — scoped API: `post_to_board`, `open_popup`, `close_popup`
- Tool type system — `BaseTool` ABC → `InlineTool`/`AsyncTool`/`SessionTool`, orchestrator routes by `isinstance()`
- TaskResult with `result`/`guide`/`board_content`/`notify`
- Board stream (array of posts with sidebar, hover preview)
- TaskDisplay (horizontal scrolling chips, board linking, clear button, session context toggle with purple highlight)
- `persist_in_display` (AsyncTool=False, SessionTool=True)
- Text input alongside voice (TranscriptionFrame injection)
- Discord-style voice controls (mute, deafen, connect/disconnect, quick tools, volume sliders)
- WriteBoard, ListTools, DebugContext, EnterSession, ExitSession tools
- Tool call args + results in transcript
- Welcome board post on connect
- Session state clear on connect/disconnect
- Backend moved to `backend/` subfolder
- SmallWebRTCTransport (browser AEC)
