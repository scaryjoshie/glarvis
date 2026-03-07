# Architecture Overview

## Pipeline

The voice agent runs as a Pipecat pipeline served over WebRTC via FastAPI:

```
Browser (WebRTC) → STT → MuteGate → TranscriptCapture → InputInterceptor → UserAggregator+VAD → BoardContextInjector → LLM → ResponseCapture → TTS → Browser (WebRTC) → AssistantAggregator
```

### Frame flow

1. `SmallWebRTCTransport.input()` receives audio from browser via WebRTC (browser handles echo cancellation)
2. STT service (configurable) transcribes streaming audio to text
3. `MuteGate` drops voice frames when soft-muted, passes "unmute" keyword and text input
4. `TranscriptCapture` broadcasts user speech to the UI transcript via WebSocket
5. `InputInterceptor` checks if active session contexts want to claim the input (e.g., number words during multi-choice)
6. `UserAggregator` + `SileroVAD` bundles transcription into an `LLMContextFrame` when the user stops talking
7. `BoardContextInjector` calls `orchestrator.prepare_for_turn()` — rebuilds tools, distributes system state, injects task/system snapshots into system message
8. LLM service (configurable) generates text response and/or tool calls
9. `ResponseCapture` broadcasts assistant speech to the UI transcript via WebSocket
10. TTS service (configurable) converts text to audio
11. `SmallWebRTCTransport.output()` sends audio back to browser
12. `AssistantAggregator` records the assistant's response back into context

### Text input path

Typed text from the web UI is sent over WebSocket as `{type: "user_text", text}`. The server injects it as a `TranscriptionFrame` via `pipeline_task.queue_frame()`, entering the same pipeline path as speech.

### Key Pipecat concepts

- **Frames**: typed data units flowing through the pipeline (TranscriptionFrame, LLMContextFrame, TTSSpeakFrame, etc.)
- **FrameProcessor**: a pipeline node that receives, transforms, and pushes frames
- **LLMContext**: shared conversation state (messages + tools) that the aggregators and LLM read/write
- **Pipeline**: ordered list of processors; frames flow left-to-right (downstream) by default
- **PipelineTask**: wraps a pipeline, provides `queue_frame()` for injecting frames from outside

## Services

Services are configured via `backend/services.yaml` and created by the registry (`backend/glarvis/services/registry.py`). Provider selection is stored in `backend/settings.json`.

| Service | Default Provider | Config |
|---------|-----------------|--------|
| STT | Deepgram | Default streaming |
| LLM | Anthropic (Claude Sonnet 4.6) | Configurable model |
| TTS | Cartesia Sonic-3 | Speed configurable, voice selectable |
| VAD | Silero | confidence=0.8, start=0.2s, stop=0.8s, min_volume=0.6 |
| Transport | SmallWebRTCTransport | Browser-native AEC, signaling via FastAPI |

All API keys are in `backend/.env`. Override keys can be set per-session in `backend/settings.json`.

## Server (`backend/server.py`)

FastAPI serves four concerns:
1. **WebRTC signaling** — `/webrtc/offer` and `/webrtc/ice` endpoints for peer connection
2. **WebSocket** — `/ws` for UI updates (server→client) and text input / settings / popup actions (client→server)
3. **REST API** — `/api/settings`, `/api/services/*` for reading/writing service configuration
4. **Pipeline lifecycle** — `on_new_connection()` builds and runs the pipeline per WebRTC peer via `build_session()`

A `broadcast()` function sends JSON messages to all connected WebSocket clients. The orchestrator uses this to push transcript entries, board posts, task updates, and popup commands to the UI.

## Pipeline Session (`backend/glarvis/pipeline.py`)

`PipelineSession` encapsulates all state for a single voice pipeline session:
- `task` — the PipelineTask
- `orchestrator` — the Orchestrator instance
- `mute_gate` — the MuteGate processor
- `system_monitor` — the SystemMonitor instance

`build_session()` is a factory that creates and wires everything together: services, tools, frame processors, and the pipeline.

## Echo Cancellation

SmallWebRTCTransport runs audio through the browser, which provides native acoustic echo cancellation (AEC). This solved the feedback loop that existed with the old LocalAudioTransport (PyAudio) approach. No headphones required.
