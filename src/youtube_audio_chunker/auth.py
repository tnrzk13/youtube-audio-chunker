"""YouTube authentication - browser cookies and OAuth credential management."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from youtube_audio_chunker.constants import APP_DIR, atomic_write_text
from youtube_audio_chunker.settings import load_settings as _load_settings, save_settings as _save_settings

AUTH_FILE = "auth.json"
BROWSER_DETECT_ORDER = ("chrome", "firefox", "chromium", "edge", "brave")


def detect_browser() -> str | None:
    """Return the first browser that has YouTube cookies, or None."""
    for browser in BROWSER_DETECT_ORDER:
        if _browser_has_youtube_cookies(browser):
            return browser
    return None


def connect_cookies(browser: str | None = None) -> dict:
    """Validate and store browser cookie auth. Auto-detects browser if not specified."""
    if browser is None:
        browser = detect_browser()
        if browser is None:
            return {
                "success": False,
                "error": "No browser with YouTube cookies detected - "
                "log in to YouTube in your browser and retry",
            }

    account_info = _fetch_account_info(browser)

    settings = _load_settings()
    settings["youtube_auth_method"] = "cookies"
    settings["youtube_cookies_browser"] = browser
    if account_info["name"]:
        settings["youtube_account_name"] = account_info["name"]
    if account_info["email"]:
        settings["youtube_account_email"] = account_info["email"]
    _save_settings(settings)
    return {
        "success": True,
        "browser": browser,
        "account_name": account_info["name"],
        "account_email": account_info["email"],
    }


def get_auth_status() -> dict | None:
    """Return current auth status or None if not configured."""
    settings = _load_settings()
    method = settings.get("youtube_auth_method")
    if not method:
        return None

    if method == "cookies":
        browser = settings.get("youtube_cookies_browser", "unknown")
        account_name = settings.get("youtube_account_name")
        account_email = settings.get("youtube_account_email")
        detail = account_name if account_name else browser
        return {
            "method": "cookies",
            "detail": detail,
            "email": account_email,
            "browser": browser,
        }

    if method == "oauth":
        return {"method": "oauth", "detail": "Google OAuth"}

    return None


def disconnect() -> None:
    """Remove all YouTube auth configuration."""
    settings = _load_settings()
    settings.pop("youtube_auth_method", None)
    settings.pop("youtube_cookies_browser", None)
    settings.pop("youtube_account_name", None)
    settings.pop("youtube_account_email", None)
    _save_settings(settings)

    auth_path = APP_DIR / AUTH_FILE
    if auth_path.exists():
        auth_path.unlink()


def get_ytdlp_auth_opts() -> dict:
    """Return yt-dlp options dict for authenticated requests."""
    settings = _load_settings()
    if settings.get("youtube_auth_method") != "cookies":
        return {}

    browser = settings.get("youtube_cookies_browser")
    if not browser:
        return {}

    return {"cookiesfrombrowser": (browser,)}


# --- Private helpers ---


def _browser_has_youtube_cookies(browser: str) -> bool:
    """Check if yt-dlp can extract valid YouTube cookies from the given browser."""
    try:
        import yt_dlp

        opts = {
            "quiet": True,
            "no_warnings": True,
            "cookiesfrombrowser": (browser,),
            "extract_flat": True,
            "playlistend": 1,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                "https://www.youtube.com/feed/subscriptions", download=False
            )
        # Empty results means cookies are expired or invalid
        entries = [e for e in info.get("entries", []) if e is not None]
        return len(entries) > 0
    except Exception:
        return False


def _fetch_account_info(browser: str) -> dict:
    """Extract YouTube account name and email using browser cookies."""
    result: dict = {"name": None, "email": None}
    try:
        import re
        import urllib.request

        import yt_dlp

        opts = {
            "quiet": True,
            "no_warnings": True,
            "cookiesfrombrowser": (browser,),
            "extract_flat": True,
            "playlistend": 1,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                "https://www.youtube.com/playlist?list=LL", download=False
            )
            result["name"] = (
                info.get("channel") or info.get("uploader") or None
            )

            # Extract email from YouTube account page using the same cookies
            try:
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(ydl.cookiejar)
                )
                resp = opener.open("https://www.youtube.com/account")
                html = resp.read().decode("utf-8", errors="replace")
                emails = re.findall(
                    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", html
                )
                if emails:
                    result["email"] = emails[0]
            except Exception:
                pass
    except Exception:
        pass
    return result




def _load_auth() -> dict:
    path = APP_DIR / AUTH_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_auth(auth: dict) -> None:
    path = APP_DIR / AUTH_FILE
    atomic_write_text(path, json.dumps(auth, indent=2))
