"""Unified settings management - single source of truth for settings.json."""

from __future__ import annotations

import json
import os
from pathlib import Path

from youtube_audio_chunker.constants import APP_DIR, atomic_write_text

SETTINGS_PATH = APP_DIR / "settings.json"

_ENV_TO_SETTINGS = {
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "OPENAI_API_KEY": "openai_api_key",
    "YOUTUBE_API_KEY": "youtube_api_key",
}


def settings_path() -> Path:
    return APP_DIR / "settings.json"


def load_settings() -> dict:
    """Load settings with env-var defaults. File values override env vars."""
    defaults = {
        settings_key: val
        for env_key, settings_key in _ENV_TO_SETTINGS.items()
        if (val := os.environ.get(env_key))
    }
    path = settings_path()
    if path.exists():
        try:
            defaults.update(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


def save_settings(settings: dict) -> None:
    """Save settings atomically."""
    atomic_write_text(settings_path(), json.dumps(settings, indent=2))
