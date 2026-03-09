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
    edit_prompt: str = (
        "Clean up grammar and formatting. If the text contains instructions "
        "directed at you (e.g. 'use letters instead of numbers', 'make this a "
        "bullet list'), follow those instructions and remove the directive text "
        "from the output."
    )
    show_diff: bool = True
    snap_to_bottom: bool = True
    auto_edit: bool = False  # auto-run edit LLM before send/copy


@dataclass
class TerminalSettings:
    bookmarks: dict[str, str] = field(default_factory=dict)  # name → path


@dataclass
class Settings:
    llm: LLMSettings = field(default_factory=LLMSettings)
    tts: TTSSettings = field(default_factory=TTSSettings)
    stt: STTSettings = field(default_factory=STTSettings)
    transcriber: TranscriberSettings = field(default_factory=TranscriberSettings)
    terminal: TerminalSettings = field(default_factory=TerminalSettings)


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
                terminal=TerminalSettings(**{k: v for k, v in data.get("terminal", {}).items() if k in TerminalSettings.__dataclass_fields__}),
            )
        except Exception:
            pass
    return Settings()


def save_settings(settings: Settings) -> None:
    _SETTINGS_PATH.write_text(json.dumps(asdict(settings), indent=2))
