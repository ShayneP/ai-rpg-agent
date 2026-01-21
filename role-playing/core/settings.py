"""
Minimal settings layer to centralize provider/model/voice defaults.

Uses environment variables when present; stays lightweight to avoid extra deps.
"""

from dataclasses import dataclass
from functools import lru_cache
import os
from typing import List


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_list(key: str) -> List[str]:
    raw = os.getenv(key)
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    llm_model: str
    stt_provider: str
    tts_model: str
    narrator_voice: str
    combat_voice: str
    available_voices: List[str]
    # RPG API settings
    rpg_api_base_url: str
    rpg_api_timeout: float


@lru_cache()
def get_settings() -> Settings:
    return Settings(
        llm_model=_env("DA_LLM_MODEL", "openai/gpt-4.1"),
        stt_provider=_env("DA_STT_PROVIDER", "deepgram/nova-3-general"),
        tts_model=_env("DA_TTS_MODEL", "inworld-tts-1.5-max"),
        narrator_voice=_env("DA_NARRATOR_VOICE", "Hades"),
        combat_voice=_env("DA_COMBAT_VOICE", "Hades"),
        available_voices=_env_list("DA_AVAILABLE_VOICES"),
        # RPG API - defaults to localhost for development
        rpg_api_base_url=_env("RPG_API_URL", "http://localhost:8000"),
        rpg_api_timeout=float(_env("RPG_API_TIMEOUT", "30.0")),
    )


settings = get_settings()
