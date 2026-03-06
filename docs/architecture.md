# Architecture Overview

## Pipeline

The voice agent runs as a Pipecat pipeline served over WebRTC via FastAPI:

```
Browser (WebRTC) -> STT (Deepgram) -> TranscriptCapture -> UserAggregator+VAD -> BoardContextInjector -> LLM (Claude) -> ResponseCapture -> TTS (Cartesia) -> Browser (WebRTC) -> AssistantAggregator
```

### Frame flow

1. `SmallWebRTCTransport.input()` receives audio from browser via WebRTC (browser handles echo cancellation)
2. `DeepgramSTTService` transcribes streaming audio to text
3. `TranscriptCapture` broadcasts user speech to the UI transcript via WebSocket
4. `UserAggregator` + `SileroVAD` bundles transcription into an `LLMRunFrame` when the user stops talking
5. `BoardContextInjector` intercepts `LLMRunFrame`, injects task state snapshot into system message
6. `AnthropicLLMService` (Haiku 4.5) generates text response and/or tool calls
7. `ResponseCapture` broadcasts assistant speech to the UI transcript via WebSocket
8. `CartesiaTTSService` (Sonic-3, speed 1.25x) converts text to audio
9. `SmallWebRTCTransport.output()` sends audio back to browser
10. `AssistantAggregator` records the assistant's response back into context

### Text input path

Typed text from the web UI is sent over WebSocket as `{type: "user_text", text}`. The server injects it as a `TranscriptionFrame` via `pipeline_task.queue_frame()`, entering the same pipeline path as speech.

### Key Pipecat concepts

- **Frames**: typed data units flowing through the pipeline (TranscriptionFrame, LLMRunFrame, TTSSpeakFrame, etc.)
- **FrameProcessor**: a pipeline node that receives, transforms, and pushes frames
- **LLMContext**: shared conversation state (messages + tools) that the aggregators and LLM read/write
- **Pipeline**: ordered list of processors; frames flow left-to-right (downstream) by default
- **PipelineTask**: wraps a pipeline, provides `queue_frame()` for injecting frames from outside

## Services

| Service | Provider | Config |
|---------|----------|--------|
| STT | Deepgram | Default streaming |
| LLM | Anthropic (Claude Haiku 4.5) | claude-haiku-4-5-20251001 |
| TTS | Cartesia Sonic-3 | speed=1.25x, voice configurable via CARTESIA_VOICE_ID |
| VAD | Silero | confidence=0.8, start=0.2s, stop=0.8s, min_volume=0.6 |
| Transport | SmallWebRTCTransport | Browser-native AEC, signaling via FastAPI |

All API keys are in `backend/.env`.

## Server (`backend/server.py`)

FastAPI serves three concerns:
1. **WebRTC signaling** — `/webrtc/offer` and `/webrtc/ice` endpoints for peer connection
2. **WebSocket** — `/ws` for UI updates (server->client) and text input (client->server)
3. **Pipeline lifecycle** — `on_new_connection()` builds and runs the pipeline per WebRTC peer

A `broadcast()` function sends JSON messages to all connected WebSocket clients. The orchestrator uses this to push transcript entries, board posts, and task updates to the UI.

## Echo Cancellation

SmallWebRTCTransport runs audio through the browser, which provides native acoustic echo cancellation (AEC). This solved the feedback loop that existed with the old LocalAudioTransport (PyAudio) approach. No headphones required.
