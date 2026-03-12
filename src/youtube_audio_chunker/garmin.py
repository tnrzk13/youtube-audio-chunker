"""Garmin watch detection and file operations."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from youtube_audio_chunker.constants import (
    ContentType,
    GARMIN_DIRS,
    GARMIN_MARKER_DIR,
)
from youtube_audio_chunker.errors import GarminError


@dataclass
class GarminEpisode:
    folder_name: str
    total_size_bytes: int
    modified_at: float
    location: str = ""


def find_garmin_mount() -> Path | None:
    candidates = _get_removable_mountpoints()
    candidates.extend(_get_mtp_mountpoints())
    for mp in candidates:
        garmin_root = _find_garmin_root(mp)
        if garmin_root is not None:
            return garmin_root
    return None


def _find_garmin_root(mountpoint: Path) -> Path | None:
    """Check mountpoint and one level of subdirs for the GARMIN marker."""
    if (mountpoint / GARMIN_MARKER_DIR).is_dir():
        return mountpoint
    for child in _safe_iterdir(mountpoint):
        if child.is_dir() and (child / GARMIN_MARKER_DIR).is_dir():
            return child
    return None


def _safe_iterdir(path: Path) -> list[Path]:
    try:
        return list(path.iterdir())
    except OSError:
        return []


def copy_to_garmin(
    source_dir: Path,
    garmin_mount: Path,
    content_type: ContentType = ContentType.MUSIC,
) -> Path:
    target_dir = garmin_mount / GARMIN_DIRS[content_type]
    target_dir.mkdir(exist_ok=True)

    source_size = _dir_size_bytes(source_dir)
    available = get_available_space_bytes(garmin_mount)
    if source_size > available:
        raise GarminError(
            f"Not enough space on Garmin. Need {source_size} bytes, "
            f"have {available} bytes. Try removing old episodes first."
        )

    files = list(source_dir.glob("*.mp3"))
    is_single_file = len(files) == 1

    if is_single_file:
        dest = target_dir / files[0].name
        shutil.copy2(files[0], dest)
    else:
        dest = target_dir / source_dir.name
        shutil.copytree(source_dir, dest)

    return dest


def remove_from_garmin(folder_name: str, garmin_mount: Path) -> None:
    for garmin_dir in GARMIN_DIRS.values():
        parent = garmin_mount / garmin_dir
        # Check for a subfolder match
        target = parent / folder_name
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
            return
        # Check for a single-file match (folder_name.mp3)
        target_file = parent / f"{folder_name}.mp3"
        if target_file.exists():
            target_file.unlink()
            return

    searched = ", ".join(GARMIN_DIRS.values())
    raise GarminError(
        f"Episode '{folder_name}' not found on Garmin. Searched: {searched}."
    )


def list_garmin_episodes(garmin_mount: Path) -> list[GarminEpisode]:
    episodes = []
    for content_type, garmin_dir in GARMIN_DIRS.items():
        parent = garmin_mount / garmin_dir
        if not parent.exists():
            continue
        for entry in parent.iterdir():
            if entry.is_dir():
                episodes.append(
                    GarminEpisode(
                        folder_name=entry.name,
                        total_size_bytes=_dir_size_bytes(entry),
                        modified_at=entry.stat().st_mtime,
                        location=garmin_dir,
                    )
                )
            elif entry.suffix == ".mp3":
                episodes.append(
                    GarminEpisode(
                        folder_name=entry.stem,
                        total_size_bytes=entry.stat().st_size,
                        modified_at=entry.stat().st_mtime,
                        location=garmin_dir,
                    )
                )
    return episodes


def get_available_space_bytes(garmin_mount: Path) -> int:
    return shutil.disk_usage(garmin_mount).free


def _get_mtp_mountpoints() -> list[Path]:
    """Find GVFS MTP mounts (Linux only)."""
    gvfs_dir = Path(f"/run/user/{os.getuid()}/gvfs")
    if not gvfs_dir.is_dir():
        return []
    return [p for p in gvfs_dir.iterdir() if p.is_dir() and "mtp" in p.name]


def _get_removable_mountpoints() -> list[Path]:
    system = platform.system()
    if system == "Darwin":
        return _get_removable_mountpoints_macos()
    return _get_removable_mountpoints_linux()


def _get_removable_mountpoints_linux() -> list[Path]:
    result = subprocess.run(
        ["lsblk", "-J", "-o", "NAME,RM,MOUNTPOINTS"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    data = json.loads(result.stdout)
    mountpoints: list[Path] = []
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


def _get_removable_mountpoints_macos() -> list[Path]:
    volumes = Path("/Volumes")
    if not volumes.is_dir():
        return []

    mountpoints = []
    for entry in volumes.iterdir():
        if not entry.is_dir() or entry.name == "Macintosh HD":
            continue
        if _is_removable_macos(entry):
            mountpoints.append(entry)
    return mountpoints


def _is_removable_macos(volume: Path) -> bool:
    result = subprocess.run(
        ["diskutil", "info", str(volume)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        if "Removable Media" in line and "Yes" in line:
            return True
    return False


def _dir_size_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
