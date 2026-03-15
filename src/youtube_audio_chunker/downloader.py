"""yt-dlp wrapper for downloading YouTube audio."""

from __future__ import annotations

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


def extract_metadata(url: str) -> list[dict]:
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info.get("_type") == "playlist":
        return [
            {"id": e["id"], "title": e["title"]}
            for e in info.get("entries", [])
            if e is not None
        ]
    return [{"id": info["id"], "title": info["title"]}]


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
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
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
        folder_name = sanitize_filename(title)
        audio_path = _find_audio_file(output_dir, title)
        channel = entry.get("channel") or entry.get("uploader") or "Unknown"
        results.append(
            DownloadResult(
                video_id=entry.get("id", ""),
                title=title,
                artist=entry.get("uploader", "Unknown"),
                audio_path=audio_path,
                folder_name=folder_name,
                channel=channel,
            )
        )
    return results


def _find_audio_file(output_dir: Path, title: str) -> Path:
    sanitized = sanitize_filename(title)
    for ext in ("mp3", "m4a", "opus", "webm"):
        candidates = list(output_dir.glob(f"*.{ext}"))
        for c in candidates:
            if sanitize_filename(c.stem) == sanitized:
                return c
    # Fallback: return first mp3
    mp3s = list(output_dir.glob("*.mp3"))
    if mp3s:
        return mp3s[0]
    raise DownloadError(
        f"Downloaded file not found for '{title}' in {output_dir}. "
        "Try checking if ffmpeg postprocessing completed."
    )
