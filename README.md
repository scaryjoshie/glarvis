# Glarvis/Minerva

Desktop voice assistant. Sees your windows, clipboard, and focus, and can switch tabs, paste text, launch programs, and run sessions in your terminal.

## What you can do

- Dictate hands-free with voice commands ("send", "copy", "edit", "submit")
- LLM-clean dictated text with a side-by-side diff before pasting
- Switch windows, focus apps, and launch programs by voice
- Bookmark terminal directories and `cd` into them by saying their name
- Start a Claude Code session in your terminal by saying "cli"
- Pick from numbered popups by voice — they stay on top of your other apps
- Mute, unmute, and deafen by voice
- Hot-swap between 10+ LLM providers and several TTS / STT engines
- Type instead of speaking when you don't want to talk

```
Browser → WebRTC → STT → MuteGate → Interceptor → VAD → ContextInjector
       → LLM → ResponseCapture → TTSGate → TTS → Browser
```

## Stack

- **Pipeline:** Pipecat, Silero VAD, WebRTC transport (browser handles AEC).
- **Providers:** YAML-driven registry. LLM — Anthropic, OpenAI, OpenRouter, Gemini, Cerebras, Grok, DeepSeek, Together, Groq, Inception. TTS — Cartesia, ElevenLabs, Deepgram, OpenAI, Inworld. STT — Deepgram, OpenAI, Groq, Speechmatics.
- **Frontend:** Svelte 5 + Vite, wrapped in Tauri. Native frameless popups via `WebviewWindow`, multi-page build sharing one `popup.html` shell.
- **System:** `pywin32` + `Get-StartApps`. Windows-only; `system/` is split so other platforms drop in as a single file.

## Tools

Three classes, dispatched by `isinstance`:

- `InlineTool` — runs in the LLM turn.
- `AsyncTool` — spawns on a `TaskManager`, results re-enter the system prompt next turn.
- `SessionTool` — long-lived, can inject context tools into the LLM schema while active. `AppSessionTool` auto-activates when its window gains focus.

Tools talk to the system through a small `ToolHandle` (`open_popup`, `post_to_board`, `execute_tool`, `pick_directory`, `inject_llm_message`).

## Pipeline pieces

- **MuteGate** — drops voice frames; passes typed text and the literal word "unmute".
- **TTSGate** — drops `TTSSpeakFrame`s before TTS runs (deafen without paying).
- **InputInterceptor** — speech monitors (sessions can own the STT stream) plus a keyword/function intercept chain that runs before the LLM.
- **BoardContextInjector** — every turn, rebuilds the LLM's tool list and re-renders the system message with the current task snapshot, active session info, and live system state.
- **SystemMonitor** — 0.5 s loop. Visible windows with stable integer IDs, foreground hwnd, clipboard, time, installed apps. Window icons via `WM_GETICON` / `ExtractIconEx`, cached as base64 PNG.

## Sessions

- **MultiChoice** — popup with numbered options. Voice ("two"), click, or LLM tool call all converge through `select_option`. Options can carry an `{tool, args}` shortcut that chains automatically.
- **Transcriber** — dictation pill that snaps to the bottom of the screen. Live transcript, voice commands ("send", "copy", "edit", "submit"). "edit" expands to a side-by-side diff and runs a separately-configured LLM. "send" focuses the prior window and pastes.
- **Terminal** — bound to Windows Terminal. "left"/"right" send `Ctrl+(Shift+)Tab`. Number words 1–6 map to tab shortcuts. "bookmark" opens a native directory picker; "bookmarks" opens a multi-choice that `cd`s into the chosen path.

## Frontend

- Animated canvas orb with state colors (idle / listening / thinking / speaking).
- Task chips (click to toggle a session's LLM context).
- Board stream (markdown via `marked` + `dompurify`, hover preview).
- Command palette (Ctrl+K), system context overlay (Ctrl+Shift+S), Discord-style voice controls.

## Layout

```
backend/
  server.py                  # FastAPI, WebRTC signaling, WebSocket
  glarvis/
    pipeline.py              # build_session()
    orchestrator.py          # routing, context, intercepts, popups
    tool.py                  # tool base classes
    task_manager.py
    handle.py
    prompt.py                # system message builder
    context_injector.py
    input_interceptor.py
    mute_gate.py / tts_gate.py
    services/registry.py     # YAML provider registry
    system/                  # monitor + win32 backend
    tools/                   # core, general, multi_choice, transcriber, terminal
  services.example.yaml
web/
  src/                       # App, components, popups, stores
  src-tauri/                 # Tauri shell
  popup.html
start.sh
```

## Running

```bash
cp backend/.env.example backend/.env
cp backend/services.example.yaml backend/services.yaml
./start.sh
```

Backend on `:8000`, Tauri dev shell alongside. Vite proxies `/webrtc`, `/api`, `/ws`.

## Built with

Backend
- [Pipecat](https://github.com/pipecat-ai/pipecat) — voice/AI frame pipeline
- [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) — server and WebSocket
- [aiortc](https://github.com/aiortc/aiortc) — WebRTC transport
- [Silero VAD](https://github.com/snakers4/silero-vad) — voice activity detection
- [pywin32](https://github.com/mhammond/pywin32) — window enumeration, clipboard, `SendInput`
- [Pillow](https://python-pillow.org/) — HICON → PNG conversion
- [loguru](https://github.com/Delgan/loguru), [PyYAML](https://pyyaml.org/), [python-dotenv](https://github.com/theskumar/python-dotenv)
- [uv](https://github.com/astral-sh/uv) — Python package manager / lockfile
- SDKs: [anthropic](https://github.com/anthropics/anthropic-sdk-python), [openai](https://github.com/openai/openai-python), [google-genai](https://github.com/googleapis/python-genai)

Frontend
- [Svelte 5](https://svelte.dev/) + [Vite](https://vitejs.dev/)
- [Tauri 2](https://tauri.app/) — desktop shell, native popup windows
- [@tauri-apps/plugin-dialog](https://github.com/tauri-apps/plugins-workspace/tree/v2/plugins/dialog) — native directory picker
- [marked](https://marked.js.org/) + [DOMPurify](https://github.com/cure53/DOMPurify) — board markdown
- [diff](https://github.com/kpdecker/jsdiff) — transcriber edit view

Model / service providers
- LLM: [Anthropic](https://www.anthropic.com/), [OpenAI](https://platform.openai.com/), [OpenRouter](https://openrouter.ai/), [Google Gemini](https://ai.google.dev/), [Cerebras](https://www.cerebras.ai/), [xAI Grok](https://x.ai/), [DeepSeek](https://www.deepseek.com/), [Together](https://www.together.ai/), [Groq](https://groq.com/), [Inception](https://www.inceptionlabs.ai/)
- TTS: [Cartesia](https://cartesia.ai/), [ElevenLabs](https://elevenlabs.io/), [Deepgram](https://deepgram.com/), [OpenAI](https://platform.openai.com/docs/guides/text-to-speech), [Inworld](https://inworld.ai/)
- STT: [Deepgram](https://deepgram.com/), [OpenAI](https://platform.openai.com/docs/guides/speech-to-text), [Groq](https://groq.com/), [Speechmatics](https://www.speechmatics.com/)
