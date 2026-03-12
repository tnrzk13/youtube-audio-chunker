"""Garmin watch detection and file operations."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from youtube_audio_chunker.constants import GARMIN_MUSIC_DIR, GARMIN_MARKER_DIR
from youtube_audio_chunker.errors import GarminError


@dataclass
class GarminEpisode:
    folder_name: str
    total_size_bytes: int
    modified_at: float


def find_garmin_mount() -> Path | None:
    mountpoints = _get_removable_mountpoints()
    for mp in mountpoints:
        if (mp / GARMIN_MARKER_DIR).is_dir():
            return mp
    return None


def copy_to_garmin(source_dir: Path, garmin_mount: Path) -> Path:
    music_dir = garmin_mount / GARMIN_MUSIC_DIR
    music_dir.mkdir(exist_ok=True)
    dest = music_dir / source_dir.name

    source_size = _dir_size_bytes(source_dir)
    available = get_available_space_bytes(garmin_mount)
    if source_size > available:
        raise GarminError(
            f"Not enough space on Garmin. Need {source_size} bytes, "
            f"have {available} bytes. Try removing old episodes first."
        )

    shutil.copytree(source_dir, dest)
    return dest


def remove_from_garmin(folder_name: str, garmin_mount: Path) -> None:
    target = garmin_mount / GARMIN_MUSIC_DIR / folder_name
    if not target.exists():
        raise GarminError(
            f"Episode '{folder_name}' not found on Garmin at {target}."
        )
    shutil.rmtree(target)


def list_garmin_episodes(garmin_mount: Path) -> list[GarminEpisode]:
    music_dir = garmin_mount / GARMIN_MUSIC_DIR
    if not music_dir.exists():
        return []

    episodes = []
    for folder in music_dir.iterdir():
        if not folder.is_dir():
            continue
        episodes.append(
            GarminEpisode(
                folder_name=folder.name,
                total_size_bytes=_dir_size_bytes(folder),
                modified_at=folder.stat().st_mtime,
            )
        )
    return episodes


def get_available_space_bytes(garmin_mount: Path) -> int:
    return shutil.disk_usage(garmin_mount).free


def _get_removable_mountpoints() -> list[Path]:
    result = subprocess.run(
        ["lsblk", "-J", "-o", "NAME,RM,MOUNTPOINTS"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    data = json.loads(result.stdout)
    mountpoints = []
    for device in data.get("blockdevices", []):
        _collect_mountpoints(device, mountpoints)
    return mountpoints


def _collect_mountpoints(device: dict, result: list[Path]) -> None:
    if device.get("rm"):
        for mp in device.get("mountpoints", []):
            if mp is not None:
                path = Path(mp)
                if path.is_dir():
                    result.append(path)
    for child in device.get("children", []):
        _collect_mountpoints(child, result)


def _dir_size_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
