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

- ToolHandle consolidation — single concrete `ToolHandle` in `handle.py`, removed abstract class from `tool.py` and `_OrchestratorToolHandle` from `orchestrator.py`, `BaseTool.system` is now a convenience property via handle
- Intercept system — `Keyword`/`Function` types in `tool.py`, global + context scoped registry in orchestrator, `try_intercept()` dispatch pipeline, `get_intercepts()` on BaseTool, `get_context_intercepts()` on SessionTool
- Window icons — `get_hwnd_icon()` (WM_GETICON, works for UWP/ApplicationFrameHost), `get_exe_icon()` fallback, cached by exe path in SystemMonitor, passed as `_icons` side channel (never in LLM context)
- SwitchWindow tool — global "switch" keyword intercept, shows multi-choice with app icons
- Mute keyword intercept — "mute"/"mute me" bypass LLM entirely
- Auto-dismiss transient sessions — `persist_in_display=False` sessions dismissed when LLM calls base tools directly
- Silent spawn for transient sessions — no LLM narration for pickers like show_choices
- `get_context_info()` on SessionTool — injects session state into system message each turn
- `_`-prefixed kwargs convention — side-channel data stripped from transcript broadcast
- Ghost window filtering — `_NOISE_APPS` set (systemsettings) in windows.py
- Shutdown/Restart tools — kill project processes by PID (Tauri app, node/vite), restart via detached `.restart.bat` + `start.sh`
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
