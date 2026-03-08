"""Persistent settings — stored in settings.json next to server.py."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"


@dataclass
class LLMSettings:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key: str = ""  # if empty, falls back to env var

    @property
    def display_name(self) -> str:
        model = self.model
        if "/" in model:
            model = model.split("/", 1)[1]
        return model


@dataclass
class TTSSettings:
    provider: str = "cartesia"
    voice_id: str = "87748186-23bb-4158-a1eb-332911b0b708"
    api_key: str = ""


@dataclass
class STTSettings:
    provider: str = "deepgram"
    model: str = ""
    api_key: str = ""


@dataclass
class TranscriberSettings:
    provider: str = "anthropic"
    model: str = "claude-haiku-4-5-20251001"
    api_key: str = ""  # if empty, falls back to env var
    edit_prompt: str = "clean up grammar and formatting"
    show_diff: bool = True


@dataclass
class Settings:
    llm: LLMSettings = field(default_factory=LLMSettings)
    tts: TTSSettings = field(default_factory=TTSSettings)
    stt: STTSettings = field(default_factory=STTSettings)
    transcriber: TranscriberSettings = field(default_factory=TranscriberSettings)


def load_settings() -> Settings:
    if _SETTINGS_PATH.exists():
        try:
            data = json.loads(_SETTINGS_PATH.read_text())
            llm_data = data.get("llm", {})
            tts_data = data.get("tts", {})
            stt_data = data.get("stt", {})
            transcriber_data = data.get("transcriber", {})
            return Settings(
                llm=LLMSettings(**{k: v for k, v in llm_data.items() if k in LLMSettings.__dataclass_fields__}),
                tts=TTSSettings(**{k: v for k, v in tts_data.items() if k in TTSSettings.__dataclass_fields__}),
                stt=STTSettings(**{k: v for k, v in stt_data.items() if k in STTSettings.__dataclass_fields__}),
                transcriber=TranscriberSettings(**{k: v for k, v in transcriber_data.items() if k in TranscriberSettings.__dataclass_fields__}),
            )
        except Exception:
            pass
    return Settings()


def save_settings(settings: Settings) -> None:
    _SETTINGS_PATH.write_text(json.dumps(asdict(settings), indent=2))
