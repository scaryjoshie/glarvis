# File Map

## Entry point
- `backend/server.py` — FastAPI server, WebRTC signaling, WebSocket, REST API for settings/services

## Pipeline
- `backend/glarvis/pipeline.py` — PipelineSession class, `build_session()` factory that wires up all services and tools

## Core modules (`backend/glarvis/`)
- `tool.py` — BaseTool ABC, InlineTool, AsyncTool, SessionTool, TaskResult, ToolHandle
- `task_manager.py` — TaskManager state manager, TaskState, Notification
- `orchestrator.py` — Orchestrator wiring tools ↔ Pipecat ↔ TaskManager ↔ UI, session context, popup routing, input interception
- `prompt.py` — BASE_PROMPT and `build_system_message()` for context injection
- `settings.py` — Persistent LLM/TTS/STT settings (settings.json)

## Frame processors (`backend/glarvis/`)
- `context_injector.py` — BoardContextInjector: refreshes tools + system message before each LLM turn
- `transcript_capture.py` — TranscriptCapture: broadcasts user speech to UI transcript
- `response_capture.py` — ResponseCapture: captures LLM text output for UI transcript
- `input_interceptor.py` — InputInterceptor: lets active sessions claim user input before the LLM
- `mute_gate.py` — MuteGate: drops voice transcriptions when soft-muted, passes "unmute" keyword

## Services (`backend/glarvis/services/`)
- `registry.py` — Config-driven service creation (LLM/TTS/STT), YAML config CRUD, provider status
- `__init__.py` — Re-exports `create_llm`, `create_tts`, `create_stt`, etc.

## System (`backend/glarvis/system/`)
- `monitor.py` — SystemMonitor: background polling loop, WindowInfo, SystemState, ProgramInfo, stable window IDs
- `windows.py` — Windows-specific APIs: window enumeration (pywin32), clipboard, focus, program launch (Get-StartApps)

## Tools (`backend/glarvis/tools/`)
- `core.py` — Mute, CloseBoard, EnterSession, ExitSession, ListTools, DebugContext
- `general.py` — GetTime, WriteBoard, ListDirectory, SearchFiles, ReadFile, FocusWindow, SearchPrograms, OpenProgram
- `multi_choice.py` — MultiChoiceSession (SessionTool: popup with numbered options, voice/click selection)

## Frontend (`web/src/`)
- `App.svelte` — Main layout (TaskDisplay top, transcript left, board+statusbar right)
- `lib/components/Board.svelte` — Board display (main area + stream sidebar, hover preview)
- `lib/components/Transcript.svelte` — Chat log + text input + VoiceControls
- `lib/components/TaskDisplay.svelte` — Horizontal scrolling task chips with board linking
- `lib/components/StatusBar.svelte` — Agent state dot + model name
- `lib/components/VoiceControls.svelte` — Discord-style: connect/disconnect, mute, deafen, quick tools, settings
- `lib/components/SettingsModal.svelte` — Full settings modal for LLM/TTS/STT provider configuration
- `lib/stores/connection.js` — WebRTC/WebSocket state, mute/deafen, boardStream, transcript, tasks, popup management, settings
- `lib/popups/MultiChoice.svelte` — Multi-choice popup UI (Tauri event emitting, keyboard shortcuts)
- `lib/popups/BoardNotify.svelte` — Board notification overlay when main window is unfocused

## Popup system (`web/`)
- `popup.html` — Minimal HTML shell for popup windows (dark background)
- `src/popup.js` — Popup entry point: reads hash data, mounts Svelte component

## Tauri (`web/src-tauri/`)
- `tauri.conf.json` — App config (window size, dev URL, build commands)
- `capabilities/default.json` — Permissions (window creation, events, webview)
- `src/lib.rs`, `src/main.rs`, `Cargo.toml` — Rust backend (generated, minimal)

## Config
- `backend/.env` — API keys (loaded via dotenv)
- `backend/settings.json` — Persistent user settings (LLM model, TTS voice, etc.)
- `backend/services.yaml` — Provider registry (models, voices, API class paths, env key names)
- `backend/services.example.yaml` — Template for services.yaml (copied on first run)
- `web/vite.config.js` — Vite dev server, proxies to FastAPI on port 8000, multi-page build (main + popup)
- `web/package.json` — Node deps including `@tauri-apps/api` and `@tauri-apps/cli`

## Docs (`docs/`)
- `architecture.md` — Pipeline overview, services, server structure
- `design-decisions.md` — Architectural decisions and rationale
- `tool-system.md` — Tool types, TaskResult, writing new tools
- `board-and-orchestrator.md` — TaskManager, Orchestrator, context injection
- `tool-results-and-context.md` — Why results always go through result_callback
- `tool-context-and-popups.md` — Session context, ToolHandle, popups, SystemMonitor, AppSessionTool design
- `file-map.md` — This file
- `todo.md` — Current work items

## Archive
- `archive/` — Old main.py (headless LocalAudioTransport mode, no longer used)
