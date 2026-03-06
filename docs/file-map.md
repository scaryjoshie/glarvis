# File Map

## Entry point
- `backend/server.py` — FastAPI server, WebRTC signaling, WebSocket, pipeline setup, system prompt

## Core modules (`backend/glarvis/`)
- `tool.py` — BaseTool ABC, InlineTool, AsyncTool, SessionTool, TaskResult dataclass
- `task_manager.py` — TaskManager state manager, TaskState, Notification
- `orchestrator.py` — Orchestrator wiring tools <-> Pipecat <-> TaskManager <-> UI
- `context_injector.py` — BoardContextInjector frame processor (injects task state before LLM turns)
- `transcript_capture.py` — TranscriptCapture frame processor (broadcasts user speech to UI)
- `response_capture.py` — ResponseCapture frame processor (broadcasts assistant speech to UI)

## Tools (`backend/glarvis/tools/`)
- `examples.py` — GetTime, SearchFiles, ListDirectory, WriteBoard, ListTools, DebugContext, EnterSession, ExitSession
- `multi_choice.py` — MultiChoiceSession (SessionTool: popup with numbered options, voice/click selection)

## Frontend (`web/src/`)
- `App.svelte` — Main layout (TaskDisplay top, transcript left, board+statusbar right)
- `lib/components/Board.svelte` — Board display (main area + stream sidebar, hover preview)
- `lib/components/Transcript.svelte` — Chat log + text input + VoiceControls
- `lib/components/TaskDisplay.svelte` — Horizontal scrolling task chips with board linking
- `lib/components/StatusBar.svelte` — Agent state dot + model name
- `lib/components/VoiceControls.svelte` — Discord-style: connect/disconnect, mute, deafen, quick tools, settings
- `lib/popups/MultiChoice.svelte` — Multi-choice popup UI (Tauri event emitting, keyboard shortcuts)
- `lib/stores/connection.js` — WebRTC/WebSocket state, mute/deafen, boardStream, transcript, tasks, Tauri popup management

## Popup system (`web/`)
- `popup.html` — Minimal HTML shell for popup windows (dark background)
- `src/popup.js` — Popup entry point: reads hash data, mounts Svelte component

## Tauri (`web/src-tauri/`)
- `tauri.conf.json` — App config (window size, dev URL, build commands)
- `capabilities/default.json` — Permissions (window creation, events, webview)
- `src/lib.rs`, `src/main.rs`, `Cargo.toml` — Rust backend (generated, minimal)

## Config
- `backend/.env` — API keys (Anthropic, Deepgram, Cartesia), voice ID
- `backend/pyproject.toml` — Python dependencies (managed with uv)
- `web/vite.config.js` — Vite dev server, proxies to FastAPI on port 8000, multi-page build (main + popup)
- `web/package.json` — Node deps including `@tauri-apps/api` and `@tauri-apps/cli`

## Docs (`docs/`)
- `architecture.md` — Pipeline overview, services, server structure
- `design-decisions.md` — Architectural decisions and rationale
- `tool-system.md` — Tool types, TaskResult, writing new tools
- `board-and-orchestrator.md` — TaskManager, Orchestrator, context injection
- `tool-results-and-context.md` — Why results always go through result_callback
- `file-map.md` — This file
- `todo.md` — Current work items

## Archive
- `archive/` — Old main.py (headless LocalAudioTransport mode, no longer used)
