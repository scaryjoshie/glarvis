# Speech Monitoring Protocol — Design Doc

## Current System (as of 2026-03)

Speech flows through `InputInterceptor`, which checks `orchestrator.get_speech_monitors()`.

### Tool attributes
- `monitors_speech = True` — tool receives all STT via `on_speech(text)`
- `hides_speech = True/property` — when True, STT is NOT forwarded to intercepts or LLM

### Flow
1. STT produces text
2. `InputInterceptor` calls `orchestrator.get_speech_monitors()`
3. For each monitor: call `tool.on_speech(text)`
4. If ANY monitor has `hides_speech == True`: skip intercept chain + LLM forwarding
5. Otherwise: run intercept chain (global keywords, context intercepts), then LLM

### Current limitation
- Only one speech monitor at a time (no priority/ordering)
- `hides_speech` is binary — can't partially filter (e.g. "hide all except commands")
- Transcriber solved partial filtering by checking commands internally in `on_speech()`

## Future Design: Speech as First-Class Protocol

### Goals
- Multiple concurrent monitors with explicit priority
- Granular control: consume vs observe vs transform
- Clean separation of "I want to see speech" from "I want to block others from seeing it"

### Sketch

```python
class SpeechParticipant(Protocol):
    """Any tool/system that participates in the speech pipeline."""
    priority: int  # Lower = earlier in chain (0 = first)

    async def process_speech(self, text: str, ctx: SpeechContext) -> SpeechAction:
        """Process speech and return an action."""
        ...

class SpeechAction(Enum):
    PASS = "pass"        # Let speech continue to next participant
    CONSUME = "consume"  # I handled it, stop propagation
    TRANSFORM = "transform"  # Modified text, continue with new version

class SpeechContext:
    original_text: str
    current_text: str  # May be transformed by earlier participants
    source: str  # "stt", "typed", etc.
```

### Priority chain example
1. **Mute gate** (priority 0) — blocks everything when muted
2. **Active session commands** (priority 10) — "pause", "resume", "stop"
3. **Transcriber capture** (priority 20) — captures speech, CONSUME when active
4. **Global keywords** (priority 30) — "transcribe", "mute", "switch"
5. **Context intercepts** (priority 40) — session-specific (number words, etc.)
6. **LLM** (priority 100) — final destination

### Benefits
- Transcriber at priority 20 can CONSUME speech (hiding from LLM) but session commands at priority 10 still work
- Multiple tools can observe without blocking
- Transform allows speech preprocessing (e.g. number word → digit conversion)

### Not building yet
This is a future consideration. Current system works for the transcriber use case with the `hides_speech` property approach. Build this when we need multiple concurrent speech-aware tools.
