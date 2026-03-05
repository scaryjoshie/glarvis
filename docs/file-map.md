# File Map

## Entry point
- `main.py` — Pipeline construction, service config, system prompt, tool registration

## Core modules (`glarvis/`)
- `tool.py` — `Tool` base class, `TaskResult` dataclass, type aliases (NotificationLevel, DisplayMode)
- `task_manager.py` — `TaskManager` state manager, `TaskState`, `Notification`
- `orchestrator.py` — `Orchestrator` wiring tools <-> Pipecat <-> TaskManager
- `context_injector.py` — `BoardContextInjector` frame processor (injects task state before LLM turns)
- `gate.py` — `SpeechGate` wake-word processor (built, not in pipeline)

## Tools (`glarvis/tools/`)
- `examples.py` — GetTime, ListDirectory, SearchFiles demo tools

## Config
- `.env` — API keys (Anthropic, Deepgram, Cartesia, Cerebras), voice ID
- `pyproject.toml` — Dependencies managed with uv

## Docs (`docs/`)
- `architecture.md` — Pipeline overview, services, known limitations
- `tool-system.md` — Tool base class, inline vs async, writing new tools
- `board-and-orchestrator.md` — TaskManager state, orchestrator, context injection, notifications
- `tool-results-and-context.md` — Why results always go through result_callback
- `file-map.md` — This file

## Naming conventions
- **TaskManager** — backend task lifecycle (spawn, track, complete, notify)
- **Board** — rich display surface for the UI (markdown, diagrams, content) [not yet built]
- **TaskDisplay** — UI component showing live task status [not yet built]
- **Orchestrator** — wires tools, TaskManager, and Pipecat pipeline together
- **Tool** — base class for all tools (LLM-facing schema + system-facing behavior)
