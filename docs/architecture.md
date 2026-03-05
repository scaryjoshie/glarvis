# Architecture Overview

## Pipeline

The voice agent is a Pipecat pipeline with local audio I/O:

```
Mic (PyAudio) → STT (Deepgram) → UserAggregator+VAD → ContextInjector → LLM (Claude) → TTS (Cartesia) → Speaker (PyAudio) → AssistantAggregator
```

### Frame flow

1. `LocalAudioTransport.input()` captures mic audio via PyAudio
2. `DeepgramSTTService` transcribes streaming audio to text
3. `UserAggregator` + `SileroVAD` bundles transcription into an `LLMRunFrame` when the user stops talking (stop_secs=0.8, confidence=0.8)
4. `BoardContextInjector` intercepts `LLMRunFrame`, logs STT output, appends board snapshot to system message
5. `AnthropicLLMService` (Haiku 4.5) generates text response and/or tool calls
6. `CartesiaTTSService` (Sonic-3, speed 1.25x) converts text to audio
7. `LocalAudioTransport.output()` plays audio through speakers
8. `AssistantAggregator` records the assistant's response back into context

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
| LLM | Anthropic (Claude Haiku 4.5) | OpenAI-compatible also available via Cerebras |
| TTS | Cartesia Sonic-3 | speed=1.25x, voice configurable via CARTESIA_VOICE_ID |
| VAD | Silero | confidence=0.8, start=0.2s, stop=0.8s, min_volume=0.6 |

All API keys are in `.env`. The LLM can be swapped between Anthropic and OpenAI-compatible (Cerebras) by changing the service class in main.py.

## Known limitations

- **No echo cancellation** with LocalAudioTransport. Speaker audio bleeds into mic. Fix: switch to WebRTC transport (SmallWebRTCTransport/DailyTransport) which has browser-native AEC. For now, use headphones.
- **VAD sensitivity**: confidence=0.8 and min_volume=0.6 are tuned to reduce self-interruption but aren't perfect with speakers.
