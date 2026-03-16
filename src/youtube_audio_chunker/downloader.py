"""yt-dlp wrapper for downloading YouTube audio."""

from __future__ import annotations

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from youtube_audio_chunker.constants import (
    DEFAULT_AUDIO_BITRATE,
    DEFAULT_AUDIO_FORMAT,
    sanitize_filename,
)
from youtube_audio_chunker.errors import DownloadError


@dataclass
class DownloadResult:
    video_id: str
    title: str
    artist: str
    audio_path: Path
    folder_name: str
    channel: str = "Unknown"


RESULTS_PAGE_SIZE = 10


def search_youtube(query: str, offset: int = 0) -> list[dict]:
    """Search YouTube and return a page of results starting at offset."""
    total_needed = offset + RESULTS_PAGE_SIZE
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{total_needed}:{query}", download=False)
    entries = [e for e in info.get("entries", []) if e is not None]
    return [_build_search_result(e) for e in entries[offset:]]


def _build_search_result(entry: dict) -> dict:
    channel_url = (
        entry.get("channel_url")
        or entry.get("uploader_url")
        or _channel_url_from_id(entry.get("channel_id"))
    )
    return {
        "video_id": entry.get("id", ""),
        "title": entry.get("title", ""),
        "channel": entry.get("channel") or entry.get("uploader") or "Unknown",
        "duration_seconds": entry.get("duration") or 0,
        "url": entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id', '')}",
        "channel_url": channel_url or "",
    }


def _enrich_missing_channels(results: list[dict]) -> None:
    """Fill in channel names for results missing them, via YouTube oEmbed."""
    to_enrich = [r for r in results if r["channel"] == "Unknown" and r["video_id"]]
    if not to_enrich:
        return

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(_fetch_oembed_channel, r["video_id"]): r
            for r in to_enrich
        }
        for future in as_completed(futures):
            result_dict = futures[future]
            oembed = future.result()
            if oembed:
                result_dict["channel"] = oembed["name"]
                if not result_dict["channel_url"] and oembed.get("url"):
                    result_dict["channel_url"] = oembed["url"]


def _fetch_oembed_channel(video_id: str) -> dict | None:
    """Fetch channel name and URL from YouTube oEmbed API."""
    try:
        url = (
            f"https://www.youtube.com/oembed"
            f"?url=https://www.youtube.com/watch?v={video_id}&format=json"
        )
        resp = urllib.request.urlopen(url, timeout=5)
        data = json.loads(resp.read())
        return {
            "name": data.get("author_name", "Unknown"),
            "url": data.get("author_url", ""),
        }
    except Exception:
        return None


def _channel_url_from_id(channel_id: str | None) -> str | None:
    if not channel_id:
        return None
    return f"https://www.youtube.com/channel/{channel_id}/videos"


def list_channel_videos(channel_url: str, offset: int = 0) -> dict:
    """List videos from a YouTube channel, paginated by offset."""
    url = channel_url.rstrip("/")
    if not url.endswith("/videos"):
        url += "/videos"

    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playliststart": offset + 1,
        "playlistend": offset + RESULTS_PAGE_SIZE,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    channel_name = info.get("channel") or info.get("uploader") or "Unknown"
    videos = [
        {
            "video_id": e.get("id", ""),
            "title": e.get("title", ""),
            "duration_seconds": e.get("duration") or 0,
            "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id', '')}",
        }
        for e in info.get("entries", [])
        if e is not None
    ]
    return {"channel_name": channel_name, "videos": videos}


def list_feed(feed_url: str, auth_opts: dict, offset: int = 0) -> list[dict]:
    """List videos from a YouTube feed (subscriptions, liked, etc.) with auth."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playliststart": offset + 1,
        "playlistend": offset + RESULTS_PAGE_SIZE,
        **auth_opts,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(feed_url, download=False)
    entries = [e for e in info.get("entries", []) if e is not None]
    results = [_build_search_result(e) for e in entries]
    _enrich_missing_channels(results)
    return results


def list_user_playlists(auth_opts: dict) -> list[dict]:
    """List the authenticated user's playlists."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        **auth_opts,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(
            "https://www.youtube.com/feed/library", download=False
        )
    return [
        _build_playlist_result(e)
        for e in info.get("entries", [])
        if e is not None
    ]


def list_playlist_videos(
    playlist_id: str, auth_opts: dict, offset: int = 0
) -> list[dict]:
    """List videos in a specific playlist."""
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playliststart": offset + 1,
        "playlistend": offset + RESULTS_PAGE_SIZE,
        **auth_opts,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = [e for e in info.get("entries", []) if e is not None]
    return [_build_search_result(e) for e in entries]


def _build_playlist_result(entry: dict) -> dict:
    return {
        "playlist_id": entry.get("id", ""),
        "title": entry.get("title", ""),
        "video_count": entry.get("playlist_count") or 0,
    }


def extract_metadata(url: str) -> list[dict]:
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info.get("_type") == "playlist":
        return [
            {"id": e["id"], "title": e["title"], "duration": e.get("duration") or 0}
            for e in info.get("entries", [])
            if e is not None
        ]
    return [{"id": info["id"], "title": info["title"], "duration": info.get("duration") or 0}]


def download_audio(url: str, output_dir: Path) -> list[DownloadResult]:
    opts = _build_ydl_opts(output_dir)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:
        raise DownloadError(
            f"Download failed for {url} because {exc}. "
            "Try checking the URL or your network connection."
        ) from exc

    return _build_results(info, output_dir)


def _build_ydl_opts(output_dir: Path) -> dict:
    return {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "%(id)s_%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": DEFAULT_AUDIO_FORMAT,
                "preferredquality": DEFAULT_AUDIO_BITRATE.rstrip("k"),
            }
        ],
    }


def _build_results(info: dict, output_dir: Path) -> list[DownloadResult]:
    entries = info.get("entries", [info]) if info.get("_type") == "playlist" else [info]
    results = []
    for entry in entries:
        if entry is None:
            continue
        title = entry.get("title", "Unknown")
        video_id = entry.get("id", "")
        folder_name = sanitize_filename(title)
        audio_path = _find_audio_file(output_dir, title, video_id=video_id)
        channel = entry.get("channel") or entry.get("uploader") or "Unknown"
        results.append(
            DownloadResult(
                video_id=video_id,
                title=title,
                artist=entry.get("uploader", "Unknown"),
                audio_path=audio_path,
                folder_name=folder_name,
                channel=channel,
            )
        )
    return results


def _find_audio_file(
    output_dir: Path, title: str, video_id: str = ""
) -> Path:
    audio_extensions = ("mp3", "m4a", "opus", "webm")

    # Priority 1: match by video_id prefix (e.g. "abc123_Title.mp3")
    if video_id:
        for ext in audio_extensions:
            for c in output_dir.glob(f"*.{ext}"):
                if c.stem.startswith(f"{video_id}_"):
                    return c

    # Priority 2: match by sanitized title (backward compat with legacy files)
    sanitized = sanitize_filename(title)
    for ext in audio_extensions:
        for c in output_dir.glob(f"*.{ext}"):
            if sanitize_filename(c.stem) == sanitized:
                return c

    raise DownloadError(
        f"Downloaded file not found for '{title}' in {output_dir}. "
        "Try checking if ffmpeg postprocessing completed."
    )
