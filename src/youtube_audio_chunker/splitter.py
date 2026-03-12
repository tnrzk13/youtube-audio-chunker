"""ffmpeg segment wrapper for splitting audio files."""

import shutil
import subprocess
from pathlib import Path

from youtube_audio_chunker.constants import DEFAULT_CHUNK_DURATION_SECONDS
from youtube_audio_chunker.errors import DependencyError, SplitError


def split_audio(
    audio_path: Path,
    output_dir: Path,
    chunk_duration_seconds: int = DEFAULT_CHUNK_DURATION_SECONDS,
) -> list[Path]:
    _ensure_ffmpeg()
    _run_ffmpeg_segment(audio_path, output_dir, chunk_duration_seconds)
    return _collect_chunks(output_dir, audio_path.stem)


def _ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise DependencyError(
            "ffmpeg not found on PATH. Install it with your package manager."
        )


def _run_ffmpeg_segment(
    audio_path: Path, output_dir: Path, chunk_duration_seconds: int
) -> None:
    output_pattern = str(output_dir / f"%02d_{audio_path.stem}.mp3")
    cmd = [
        "ffmpeg",
        "-i", str(audio_path),
        "-f", "segment",
        "-segment_time", str(chunk_duration_seconds),
        "-segment_start_number", "1",
        "-c", "copy",
        "-map", "0:a",
        output_pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SplitError(
            f"ffmpeg failed with exit code {result.returncode}. "
            f"stderr: {result.stderr}"
        )


def _collect_chunks(output_dir: Path, stem: str) -> list[Path]:
    return sorted(output_dir.glob(f"*_{stem}.mp3"))
