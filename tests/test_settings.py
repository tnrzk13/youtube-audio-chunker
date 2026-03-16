import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from youtube_audio_chunker.settings import (
    SETTINGS_PATH,
    load_settings,
    save_settings,
    settings_path,
)

SETTINGS_MODULE = "youtube_audio_chunker.settings"


@pytest.fixture
def app_dir(tmp_path):
    with patch(f"{SETTINGS_MODULE}.APP_DIR", tmp_path):
        yield tmp_path


class TestSettingsPath:
    def test_returns_settings_json_in_app_dir(self, app_dir):
        result = settings_path()
        assert result == app_dir / "settings.json"


class TestLoadSettings:
    def test_returns_empty_dict_when_no_file(self, app_dir):
        result = load_settings()
        assert result == {}

    def test_loads_saved_settings(self, app_dir):
        data = {"youtube_api_key": "abc123", "topic_provider": "openai"}
        (app_dir / "settings.json").write_text(json.dumps(data))

        result = load_settings()

        assert result["youtube_api_key"] == "abc123"
        assert result["topic_provider"] == "openai"

    def test_env_vars_provide_defaults(self, app_dir):
        with patch.dict(os.environ, {"YOUTUBE_API_KEY": "env-key"}, clear=False):
            result = load_settings()

        assert result["youtube_api_key"] == "env-key"

    def test_file_settings_override_env_vars(self, app_dir):
        (app_dir / "settings.json").write_text(
            json.dumps({"youtube_api_key": "file-key"})
        )

        with patch.dict(os.environ, {"YOUTUBE_API_KEY": "env-key"}, clear=False):
            result = load_settings()

        assert result["youtube_api_key"] == "file-key"

    def test_env_var_not_set_for_missing_keys(self, app_dir):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("YOUTUBE_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)

            result = load_settings()

        assert "youtube_api_key" not in result
        assert "anthropic_api_key" not in result
        assert "openai_api_key" not in result

    def test_handles_corrupt_json(self, app_dir):
        (app_dir / "settings.json").write_text("not valid json{{{")

        result = load_settings()

        assert result == {}

    def test_all_env_vars_mapped(self, app_dir):
        env = {
            "ANTHROPIC_API_KEY": "ant-key",
            "OPENAI_API_KEY": "oai-key",
            "YOUTUBE_API_KEY": "yt-key",
        }
        with patch.dict(os.environ, env, clear=False):
            result = load_settings()

        assert result["anthropic_api_key"] == "ant-key"
        assert result["openai_api_key"] == "oai-key"
        assert result["youtube_api_key"] == "yt-key"


class TestSaveSettings:
    def test_roundtrip(self, app_dir):
        data = {"youtube_api_key": "my-key", "topic_provider": "anthropic"}
        save_settings(data)

        result = load_settings()

        assert result["youtube_api_key"] == "my-key"
        assert result["topic_provider"] == "anthropic"

    def test_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "deep" / "nested"
        with patch(f"{SETTINGS_MODULE}.APP_DIR", nested):
            save_settings({"key": "val"})

        assert (nested / "settings.json").exists()

    def test_uses_atomic_write(self, app_dir):
        with patch(f"{SETTINGS_MODULE}.atomic_write_text") as mock_write:
            save_settings({"key": "val"})

        mock_write.assert_called_once()
        call_path = mock_write.call_args[0][0]
        assert call_path == app_dir / "settings.json"
