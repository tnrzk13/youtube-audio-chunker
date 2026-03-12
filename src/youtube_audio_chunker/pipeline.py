"""Orchestrator - coordinates download, split, tag, and transfer."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from youtube_audio_chunker.constants import (
    DEFAULT_CHUNK_DURATION_SECONDS,
    LIBRARY_PATH,
    OUTPUT_DIR,
)
from youtube_audio_chunker.downloader import download_audio, DownloadResult
from youtube_audio_chunker.garmin import (
    find_garmin_mount,
    copy_to_garmin,
    remove_from_garmin,
    list_garmin_episodes,
    get_available_space_bytes,
)
from youtube_audio_chunker.library import (
    load_library,
    save_library,
    move_to_downloaded,
    mark_synced,
    Library,
    QueueEntry,
)
from youtube_audio_chunker.splitter import split_audio
from youtube_audio_chunker.tagger import tag_chunks


@dataclass
class SyncOptions:
    library_path: Path = LIBRARY_PATH
    output_dir: Path = OUTPUT_DIR
    chunk_duration_seconds: int = DEFAULT_CHUNK_DURATION_SECONDS
    artist: str | None = None
    keep_full: bool = False
    no_transfer: bool = False


def process_queue(options: SyncOptions) -> None:
    library = load_library(options.library_path)
    if not library.queue:
        print("Nothing in queue.")
        return

    processed = _download_and_chunk_all(library, options)
    if not processed:
        return

    save_library(library, options.library_path)

    if options.no_transfer:
        print("Skipping transfer (--no-transfer).")
        return

    _transfer_to_garmin(library, processed, options)


def _download_and_chunk_all(
    library: Library, options: SyncOptions
) -> list[tuple[DownloadResult, Path]]:
    processed = []
    for entry in list(library.queue):
        result = _process_single_entry(entry, library, options)
        if result:
            processed.append(result)
    return processed


def _process_single_entry(
    entry: QueueEntry, library: Library, options: SyncOptions
) -> tuple[DownloadResult, Path] | None:
    print(f"Downloading: {entry.title}")
    results = download_audio(entry.url, options.output_dir)
    if not results:
        return None

    dl = results[0]
    episode_dir = _chunk_and_tag(dl, options)
    _update_library_after_processing(library, entry, dl, episode_dir)
    return (dl, episode_dir)


def _chunk_and_tag(dl: DownloadResult, options: SyncOptions) -> Path:
    episode_dir = options.output_dir / dl.folder_name
    episode_dir.mkdir(parents=True, exist_ok=True)

    print(f"Splitting: {dl.title}")
    chunks = split_audio(dl.audio_path, episode_dir, options.chunk_duration_seconds)

    artist = options.artist or dl.artist
    print(f"Tagging {len(chunks)} chunks")
    tag_chunks(chunks, title=dl.title, total_chunks=len(chunks), artist=artist)

    if not options.keep_full:
        dl.audio_path.unlink(missing_ok=True)

    return episode_dir


def _update_library_after_processing(
    library: Library, entry: QueueEntry, dl: DownloadResult, episode_dir: Path
) -> None:
    total_size = sum(f.stat().st_size for f in episode_dir.rglob("*") if f.is_file())
    chunk_count = len(list(episode_dir.glob("*.mp3")))
    episode_info = {
        "folder_name": dl.folder_name,
        "chunk_count": chunk_count,
        "total_size_bytes": total_size,
    }
    move_to_downloaded(library, entry, episode_info)


def _transfer_to_garmin(
    library: Library,
    processed: list[tuple[DownloadResult, Path]],
    options: SyncOptions,
) -> None:
    garmin_mount = find_garmin_mount()
    if garmin_mount is None:
        print("No Garmin watch detected. Episodes saved locally.")
        return

    for dl, episode_dir in processed:
        _transfer_single_episode(library, dl, episode_dir, garmin_mount, options)

    save_library(library, options.library_path)


def _transfer_single_episode(
    library: Library,
    dl: DownloadResult,
    episode_dir: Path,
    garmin_mount: Path,
    options: SyncOptions,
) -> None:
    needed_bytes = sum(f.stat().st_size for f in episode_dir.rglob("*") if f.is_file())
    available = get_available_space_bytes(garmin_mount)

    if needed_bytes > available:
        freed = _try_free_space(needed_bytes, available, garmin_mount)
        if not freed:
            print(f"Skipping transfer of '{dl.title}' - not enough space.")
            return

    print(f"Transferring: {dl.title}")
    copy_to_garmin(episode_dir, garmin_mount)
    mark_synced(library, dl.video_id)
    print(f"Synced: {dl.title}")


def _try_free_space(
    needed_bytes: int, available_bytes: int, garmin_mount: Path
) -> bool:
    deficit = needed_bytes - available_bytes
    episodes = list_garmin_episodes(garmin_mount)
    episodes.sort(key=lambda e: e.modified_at)

    to_remove = _select_episodes_for_removal(episodes, deficit)
    if not to_remove:
        return False

    _print_removal_plan(to_remove, deficit)
    if not _confirm_removal():
        return False

    for ep in to_remove:
        remove_from_garmin(ep.folder_name, garmin_mount)
        print(f"  Removed: {ep.folder_name}")

    return True


def _select_episodes_for_removal(episodes, deficit_bytes):
    to_remove = []
    freed = 0
    for ep in episodes:
        to_remove.append(ep)
        freed += ep.total_size_bytes
        if freed >= deficit_bytes:
            break
    if freed < deficit_bytes:
        return []
    return to_remove


def _print_removal_plan(episodes, deficit_bytes):
    total_free = sum(e.total_size_bytes for e in episodes)
    print(f"\nNeed to free {deficit_bytes:,} bytes. These episodes would be removed:")
    for ep in episodes:
        size_mb = ep.total_size_bytes / 1_000_000
        print(f"  - {ep.folder_name} ({size_mb:.1f} MB)")
    print()


def _confirm_removal() -> bool:
    try:
        answer = input("Remove these episodes to make room? [y/N] ")
        return answer.strip().lower() == "y"
    except (EOFError, KeyboardInterrupt):
        return False
