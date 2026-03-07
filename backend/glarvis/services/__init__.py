"""Service registry — unified config-driven creation of LLM, TTS, and STT services."""

from glarvis.services.registry import (
    create_llm,
    create_tts,
    create_stt,
    get_status,
    add_service_item,
    remove_service_item,
    edit_service_voice,
    set_provider_speed,
)
