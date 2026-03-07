"""Config-driven service registry for LLM, TTS, and STT providers."""

from __future__ import annotations

import importlib
import os
import shutil
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "services.yaml"
_EXAMPLE_PATH = Path(__file__).resolve().parent.parent.parent / "services.example.yaml"

_config: dict | None = None


def _load_config() -> dict:
    global _config
    if _config is not None:
        return _config

    if not _CONFIG_PATH.exists():
        if _EXAMPLE_PATH.exists():
            shutil.copy(_EXAMPLE_PATH, _CONFIG_PATH)
            logger.info(f"[Services] Created services.yaml from example")
        else:
            _config = {"llm": {}, "tts": {}, "stt": {}}
            return _config

    with open(_CONFIG_PATH) as f:
        _config = yaml.safe_load(f) or {}

    # Ensure top-level keys exist
    for key in ("llm", "tts", "stt"):
        _config.setdefault(key, {})

    return _config


def _save_config(config: dict):
    """Write config back to services.yaml."""
    global _config
    _config = config
    with open(_CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def reload_config():
    """Force reload config from disk."""
    global _config
    _config = None
    _load_config()


def _mask_key(key: str) -> str:
    """Return abbreviated key for safe display (e.g. 'sk-a...F7x2')."""
    if not key:
        return ""
    if len(key) <= 8:
        return "\u2022" * len(key)
    return key[:4] + "\u2022\u2022\u2022" + key[-4:]


def _import_class(service_path: str):
    module_path, class_name = service_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# ── Creation helpers ──────────────────────────────────────────────────────────

def create_llm(provider_id: str, model: str, api_key_override: str = ""):
    """Create a Pipecat LLM service from config."""
    config = _load_config()
    provider = config["llm"].get(provider_id)
    if not provider:
        raise ValueError(f"Unknown LLM provider: {provider_id}")

    api_key = api_key_override or os.getenv(provider["env_key"], "")
    if not api_key:
        raise ValueError(
            f"No API key for {provider['name']} (set {provider['env_key']} in .env or provide in settings)"
        )

    ServiceClass = _import_class(provider["service"])
    kwargs: dict[str, Any] = {"api_key": api_key, "model": model}
    if provider.get("base_url"):
        kwargs["base_url"] = provider["base_url"]

    logger.info(f"[Services] Creating LLM: {provider['name']} / {model}")
    return ServiceClass(**kwargs)


def create_tts(provider_id: str, voice_id: str = "", api_key_override: str = ""):
    """Create a Pipecat TTS service from config."""
    config = _load_config()
    provider = config["tts"].get(provider_id)
    if not provider:
        raise ValueError(f"Unknown TTS provider: {provider_id}")

    api_key = api_key_override or os.getenv(provider["env_key"], "")
    if not api_key:
        raise ValueError(
            f"No API key for {provider['name']} (set {provider['env_key']} in .env)"
        )

    # Use first voice as default if none specified
    voices = provider.get("voices", [])
    if not voice_id and voices:
        voice_id = voices[0]["id"]

    ServiceClass = _import_class(provider["service"])
    kwargs: dict[str, Any] = {"api_key": api_key, "voice_id": voice_id}

    # Some services need an aiohttp session (e.g. Inworld)
    import inspect
    sig = inspect.signature(ServiceClass.__init__)
    if "aiohttp_session" in sig.parameters:
        import aiohttp
        kwargs["aiohttp_session"] = aiohttp.ClientSession()

    # Apply extra params (speed, etc.)
    params = provider.get("params", {})
    if params:
        # Try to use InputParams if the service supports it
        if hasattr(ServiceClass, "InputParams"):
            from pipecat.services.cartesia.tts import GenerationConfig
            input_params = {}
            if "speed" in params:
                input_params["generation_config"] = GenerationConfig(speed=params["speed"])
            if input_params:
                kwargs["params"] = ServiceClass.InputParams(**input_params)

    logger.info(f"[Services] Creating TTS: {provider['name']} / {voice_id}")
    return ServiceClass(**kwargs)


def create_stt(provider_id: str, model: str = "", api_key_override: str = ""):
    """Create a Pipecat STT service from config."""
    config = _load_config()
    provider = config["stt"].get(provider_id)
    if not provider:
        raise ValueError(f"Unknown STT provider: {provider_id}")

    api_key = api_key_override or os.getenv(provider["env_key"], "")
    if not api_key:
        raise ValueError(
            f"No API key for {provider['name']} (set {provider['env_key']} in .env)"
        )

    ServiceClass = _import_class(provider["service"])
    kwargs: dict[str, Any] = {"api_key": api_key}
    if model:
        kwargs["model"] = model

    logger.info(f"[Services] Creating STT: {provider['name']} / {model or 'default'}")
    return ServiceClass(**kwargs)


# ── CRUD for services.yaml ───────────────────────────────────────────────────

def add_service_item(service_type: str, provider_id: str, item) -> bool:
    """Add a model (str) or voice ({id, name}) to a provider."""
    config = _load_config()
    provider = config.get(service_type, {}).get(provider_id)
    if not provider:
        return False
    if service_type == "tts":
        voices = provider.setdefault("voices", [])
        voices.append(item)
    else:
        models = provider.setdefault("models", [])
        if item not in models:
            models.append(item)
    _save_config(config)
    return True


def remove_service_item(service_type: str, provider_id: str, item_id: str) -> bool:
    """Remove a model or voice from a provider."""
    config = _load_config()
    provider = config.get(service_type, {}).get(provider_id)
    if not provider:
        return False
    if service_type == "tts":
        voices = provider.get("voices", [])
        provider["voices"] = [v for v in voices if v.get("id") != item_id]
    else:
        models = provider.get("models", [])
        provider["models"] = [m for m in models if m != item_id]
    _save_config(config)
    return True


def edit_service_voice(provider_id: str, voice_id: str, updates: dict) -> bool:
    """Edit a TTS voice's name or id."""
    config = _load_config()
    provider = config.get("tts", {}).get(provider_id)
    if not provider:
        return False
    for voice in provider.get("voices", []):
        if voice.get("id") == voice_id:
            if "name" in updates:
                voice["name"] = updates["name"]
            if "id" in updates:
                voice["id"] = updates["id"]
            _save_config(config)
            return True
    return False


def set_provider_speed(provider_id: str, speed: float | None) -> bool:
    """Set or clear TTS speed for a provider."""
    config = _load_config()
    provider = config.get("tts", {}).get(provider_id)
    if not provider:
        return False
    if speed is None:
        # Remove speed
        params = provider.get("params", {})
        params.pop("speed", None)
        if not params:
            provider.pop("params", None)
    else:
        params = provider.setdefault("params", {})
        params["speed"] = round(speed, 2)
    _save_config(config)
    return True


# ── Status for frontend ──────────────────────────────────────────────────────

def get_status() -> dict:
    """Return all service info with key availability for the frontend settings modal."""
    config = _load_config()
    result = {}

    for service_type in ("llm", "tts", "stt"):
        providers = []
        for pid, pdata in config[service_type].items():
            env_key_val = os.getenv(pdata.get("env_key", ""), "")
            entry = {
                "id": pid,
                "name": pdata.get("name", pid),
                "has_key": bool(env_key_val),
                "key_hint": _mask_key(env_key_val),
            }
            if service_type == "llm":
                models = pdata.get("models", [])
                entry["models"] = models
                entry["default_model"] = models[0] if models else ""
            elif service_type == "tts":
                entry["voices"] = pdata.get("voices", [])
                entry["default_voice"] = entry["voices"][0]["id"] if entry["voices"] else ""
                entry["speed"] = pdata.get("params", {}).get("speed")
            elif service_type == "stt":
                models = pdata.get("models", [])
                entry["models"] = models
                entry["default_model"] = models[0] if models else ""
            providers.append(entry)
        result[service_type] = providers

    return result
