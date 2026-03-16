import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from youtube_audio_chunker.auth import (
    AUTH_FILE,
    BROWSER_DETECT_ORDER,
    connect_cookies,
    detect_browser,
    disconnect,
    get_auth_status,
    get_ytdlp_auth_opts,
)

AUTH_MODULE = "youtube_audio_chunker.auth"


@pytest.fixture
def app_dir(tmp_path):
    """Redirect APP_DIR to a temp directory for isolation."""
    with patch(f"{AUTH_MODULE}.APP_DIR", tmp_path):
        yield tmp_path


def _write_settings(app_dir: Path, data: dict) -> None:
    (app_dir / "settings.json").write_text(json.dumps(data))


def _read_settings(app_dir: Path) -> dict:
    return json.loads((app_dir / "settings.json").read_text())


def _write_auth(app_dir: Path, data: dict) -> None:
    (app_dir / AUTH_FILE).write_text(json.dumps(data))


class TestDetectBrowser:
    def test_returns_first_browser_with_cookies(self, app_dir):
        with patch(f"{AUTH_MODULE}._browser_has_youtube_cookies") as mock_check:
            mock_check.side_effect = lambda b: b == "firefox"

            result = detect_browser()

            assert result == "firefox"

    def test_returns_none_when_no_browser_has_cookies(self, app_dir):
        with patch(f"{AUTH_MODULE}._browser_has_youtube_cookies", return_value=False):
            result = detect_browser()

            assert result is None

    def test_tries_browsers_in_order(self, app_dir):
        tried = []
        with patch(f"{AUTH_MODULE}._browser_has_youtube_cookies") as mock_check:
            def track(browser):
                tried.append(browser)
                return False
            mock_check.side_effect = track

            detect_browser()

            assert tried == list(BROWSER_DETECT_ORDER)


class TestConnectCookies:
    @patch(f"{AUTH_MODULE}._fetch_account_info", return_value={"name": "Test User", "email": "test@gmail.com"})
    def test_auto_detects_browser_and_saves_settings(self, mock_fetch, app_dir):
        with patch(f"{AUTH_MODULE}.detect_browser", return_value="chrome"):
            result = connect_cookies()

            assert result["success"] is True
            assert result["browser"] == "chrome"
            assert result["account_name"] == "Test User"
            assert result["account_email"] == "test@gmail.com"
            settings = _read_settings(app_dir)
            assert settings["youtube_auth_method"] == "cookies"
            assert settings["youtube_cookies_browser"] == "chrome"
            assert settings["youtube_account_name"] == "Test User"
            assert settings["youtube_account_email"] == "test@gmail.com"

    @patch(f"{AUTH_MODULE}._fetch_account_info", return_value={"name": None, "email": None})
    def test_uses_specified_browser(self, mock_fetch, app_dir):
        result = connect_cookies(browser="firefox")

        assert result["success"] is True
        assert result["browser"] == "firefox"
        settings = _read_settings(app_dir)
        assert settings["youtube_cookies_browser"] == "firefox"

    def test_fails_when_no_browser_detected(self, app_dir):
        with patch(f"{AUTH_MODULE}.detect_browser", return_value=None):
            result = connect_cookies()

            assert result["success"] is False
            assert "No browser" in result["error"]

    @patch(f"{AUTH_MODULE}._fetch_account_info", return_value={"name": None, "email": None})
    def test_preserves_existing_settings(self, mock_fetch, app_dir):
        _write_settings(app_dir, {"default_content_type": "music", "chunk_duration_seconds": 300})

        connect_cookies(browser="chrome")

        settings = _read_settings(app_dir)
        assert settings["default_content_type"] == "music"
        assert settings["chunk_duration_seconds"] == 300
        assert settings["youtube_auth_method"] == "cookies"


class TestGetAuthStatus:
    def test_returns_none_when_no_settings(self, app_dir):
        assert get_auth_status() is None

    def test_returns_none_when_no_auth_method(self, app_dir):
        _write_settings(app_dir, {"default_content_type": "podcast"})

        assert get_auth_status() is None

    def test_returns_cookies_status_with_account_info(self, app_dir):
        _write_settings(app_dir, {
            "youtube_auth_method": "cookies",
            "youtube_cookies_browser": "chrome",
            "youtube_account_name": "Tony Kwok",
            "youtube_account_email": "tony@gmail.com",
        })

        result = get_auth_status()

        assert result["method"] == "cookies"
        assert result["detail"] == "Tony Kwok"
        assert result["email"] == "tony@gmail.com"
        assert result["browser"] == "chrome"

    def test_returns_cookies_status_falls_back_to_browser(self, app_dir):
        _write_settings(app_dir, {
            "youtube_auth_method": "cookies",
            "youtube_cookies_browser": "chrome",
        })

        result = get_auth_status()

        assert result["method"] == "cookies"
        assert result["detail"] == "chrome"
        assert result["email"] is None
        assert result["browser"] == "chrome"

    def test_returns_oauth_status(self, app_dir):
        _write_settings(app_dir, {"youtube_auth_method": "oauth"})
        _write_auth(app_dir, {
            "youtube_oauth_client_id": "my-id",
            "youtube_oauth_client_secret": "my-secret",
            "youtube_oauth_refresh_token": "my-token",
        })

        result = get_auth_status()

        assert result["method"] == "oauth"
        assert result["detail"] == "Google OAuth"


class TestDisconnect:
    def test_clears_auth_fields_from_settings(self, app_dir):
        _write_settings(app_dir, {
            "youtube_auth_method": "cookies",
            "youtube_cookies_browser": "chrome",
            "youtube_account_name": "Test User",
            "default_content_type": "podcast",
        })

        disconnect()

        settings = _read_settings(app_dir)
        assert "youtube_auth_method" not in settings
        assert "youtube_cookies_browser" not in settings
        assert "youtube_account_name" not in settings
        assert settings["default_content_type"] == "podcast"

    def test_removes_auth_json(self, app_dir):
        _write_settings(app_dir, {"youtube_auth_method": "oauth"})
        auth_path = app_dir / AUTH_FILE
        _write_auth(app_dir, {"youtube_oauth_refresh_token": "tok"})
        assert auth_path.exists()

        disconnect()

        assert not auth_path.exists()

    def test_noop_when_no_settings(self, app_dir):
        disconnect()  # Should not raise


class TestGetYtdlpAuthOpts:
    def test_returns_cookies_opts(self, app_dir):
        _write_settings(app_dir, {
            "youtube_auth_method": "cookies",
            "youtube_cookies_browser": "chrome",
        })

        opts = get_ytdlp_auth_opts()

        assert opts == {"cookiesfrombrowser": ("chrome",)}

    def test_returns_empty_when_no_auth(self, app_dir):
        assert get_ytdlp_auth_opts() == {}

    def test_returns_empty_for_oauth(self, app_dir):
        _write_settings(app_dir, {"youtube_auth_method": "oauth"})

        assert get_ytdlp_auth_opts() == {}
