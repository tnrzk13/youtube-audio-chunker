"""Orchestrator - coordinates download, split, tag, and transfer."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from youtube_audio_chunker.constants import (
    ContentType,
    DEFAULT_CHUNK_DURATION_SECONDS,
    LIBRARY_PATH,
    OUTPUT_DIR,
)
from youtube_audio_chunker.downloader import download_audio, DownloadResult
from youtube_audio_chunker.garmin import (
    dir_size_bytes,
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
    update_episode,
    DownloadedEpisode,
    Library,
    QueueEntry,
)
from youtube_audio_chunker.splitter import split_audio
from youtube_audio_chunker.tagger import tag_chunks, tag_single, retag_episode


@dataclass
class SyncOptions:
    library_path: Path = LIBRARY_PATH
    output_dir: Path = OUTPUT_DIR
    chunk_duration_seconds: int | None = None
    artist: str | None = None
    keep_full: bool = False
    no_transfer: bool = False


@dataclass
class PipelineCallbacks:
    on_progress: Callable[[str, str, str, int], None] | None = None
    on_confirm_removal: Callable[[list, int], bool] | None = None
    is_cancelled: Callable[[], bool] | None = None


def process_queue(
    options: SyncOptions, callbacks: PipelineCallbacks | None = None,
) -> dict:
    cb = callbacks or PipelineCallbacks()
    library = load_library(options.library_path)
    if not library.queue:
        _progress(cb, "info", "", "Nothing in queue.", 0)
        return {"processed": 0, "transferred": 0}

    processed = _download_and_chunk_all(library, options, cb)
    if not processed:
        return {"processed": 0, "transferred": 0}

    if options.no_transfer:
        _progress(cb, "info", "", "Skipping transfer (--no-transfer).", 0)
        return {"processed": len(processed), "transferred": 0}

    transferred = _transfer_to_garmin(library, processed, options, cb)
    return {"processed": len(processed), "transferred": transferred}


def transfer_unsynced(
    library_path: Path = LIBRARY_PATH,
    callbacks: PipelineCallbacks | None = None,
) -> dict:
    """Transfer all local episodes not currently on the watch."""
    cb = callbacks or PipelineCallbacks()
    library = load_library(library_path)

    garmin_mount = find_garmin_mount()
    if garmin_mount is None:
        _progress(cb, "info", "", "No Garmin watch detected.", 0)
        return {"transferred": 0}

    garmin_episodes = list_garmin_episodes(garmin_mount)
    on_watch = {ep.folder_name for ep in garmin_episodes}
    not_on_watch = [
        ep for ep in library.downloaded
        if ep.folder_name not in on_watch
    ]

    if not not_on_watch:
        _progress(cb, "info", "", "No unsynced episodes to transfer.", 0)
        return {"transferred": 0}

    transferred = 0
    for ep in not_on_watch:
        if _cancelled(cb):
            break
        if _transfer_local_episode(library, ep, garmin_mount, cb):
            transferred += 1

    save_library(library, library_path)
    return {"transferred": transferred}


def edit_episode(
    video_id: str,
    updates: dict,
    library_path: Path = LIBRARY_PATH,
    output_dir: Path = OUTPUT_DIR,
) -> dict | None:
    """Update metadata on a downloaded episode and re-tag files on disk."""
    library = load_library(library_path)
    ep = update_episode(library, video_id, updates)
    if ep is None:
        return None

    episode_dir = output_dir / ep.folder_name
    if episode_dir.exists():
        retag_episode(
            episode_dir,
            title=ep.title,
            artist=ep.artist or "",
            album=ep.show_name or ep.title,
            content_type=ContentType(ep.content_type),
            chunk_count=ep.chunk_count,
        )

    save_library(library, library_path)
    return asdict(ep)


def select_episodes_for_removal(episodes, deficit_bytes):
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


# --- Internal helpers ---


def _compute_episode_index(
    library: Library, show_name: str | None, content_type: ContentType,
) -> int:
    """Count existing downloaded music episodes with the same show_name."""
    if content_type != ContentType.MUSIC or show_name is None:
        return 0
    return sum(
        1 for ep in library.downloaded
        if ep.show_name == show_name and ep.content_type == ContentType.MUSIC.value
    )


def _progress(cb: PipelineCallbacks, *args) -> None:
    if cb.on_progress:
        cb.on_progress(*args)
    else:
        # CLI fallback: print the message
        print(args[2])


def _cancelled(cb: PipelineCallbacks) -> bool:
    if cb.is_cancelled:
        return cb.is_cancelled()
    return False


def _download_and_chunk_all(
    library: Library, options: SyncOptions, cb: PipelineCallbacks,
) -> list[tuple[DownloadResult, Path, ContentType]]:
    processed = []
    queue_snapshot = list(library.queue)
    total = len(queue_snapshot)

    for i, entry in enumerate(queue_snapshot):
        if _cancelled(cb):
            _progress(cb, "cancelled", "", "Processing cancelled", 0)
            break

        # Sidecar reloads library to check if entry was removed mid-processing
        if cb.is_cancelled is not None:
            library_fresh = load_library(options.library_path)
            still_queued = any(e.video_id == entry.video_id for e in library_fresh.queue)
            if not still_queued:
                continue

        result = _process_single_entry(entry, library, options, cb)
        if result:
            dl, episode_dir = result
            content_type = ContentType(entry.content_type)
            processed.append((dl, episode_dir, content_type))

        step_pct = int((i + 1) / total * 100)
        _progress(
            cb, "process", entry.video_id,
            f"Processed {i + 1}/{total}", step_pct,
        )

        if _cancelled(cb):
            _progress(cb, "cancelled", "", "Processing cancelled", 0)
            break

    return processed


def _process_single_entry(
    entry: QueueEntry, library: Library, options: SyncOptions,
    cb: PipelineCallbacks,
) -> tuple[DownloadResult, Path] | None:
    _progress(cb, "download", entry.video_id, f"Downloading: {entry.title}", 0)

    if _cancelled(cb):
        _progress(cb, "cancelled", "", "Processing cancelled", 0)
        return None

    results = download_audio(entry.url, options.output_dir)
    if not results:
        return None

    if _cancelled(cb):
        _progress(cb, "cancelled", "", "Processing cancelled", 0)
        return None

    dl = results[0]
    _progress(cb, "download", entry.video_id, f"Downloaded: {dl.title}", 100)

    entry.show_name = entry.show_name or dl.channel
    entry.artist = entry.artist or options.artist or dl.artist

    content_type = ContentType(entry.content_type)
    show_name = entry.show_name
    episode_index = _compute_episode_index(library, show_name, content_type)
    episode_dir = _prepare_episode(
        dl, content_type, options, cb,
        show_name=show_name, episode_index=episode_index,
    )
    _update_library_after_processing(library, entry, dl, episode_dir, options)
    return (dl, episode_dir)


def _should_chunk(content_type: ContentType, options: SyncOptions) -> bool:
    if options.chunk_duration_seconds is not None:
        return True
    return content_type == ContentType.MUSIC


def _prepare_episode(
    dl: DownloadResult, content_type: ContentType, options: SyncOptions,
    cb: PipelineCallbacks,
    show_name: str | None = None, episode_index: int = 0,
) -> Path:
    episode_dir = options.output_dir / dl.folder_name
    episode_dir.mkdir(parents=True, exist_ok=True)
    artist = options.artist or dl.artist
    album = show_name

    if _should_chunk(content_type, options):
        chunk_duration = (
            options.chunk_duration_seconds or DEFAULT_CHUNK_DURATION_SECONDS
        )
        _progress(cb, "split", dl.video_id, f"Splitting: {dl.title}", 0)
        chunks = split_audio(dl.audio_path, episode_dir, chunk_duration)
        _progress(cb, "tag", dl.video_id, f"Tagging {len(chunks)} chunks", 0)
        track_offset = episode_index * 100
        tag_chunks(
            chunks, title=dl.title, total_chunks=len(chunks), artist=artist,
            album=album, track_offset=track_offset,
        )
        if not options.keep_full:
            dl.audio_path.unlink(missing_ok=True)
    else:
        dest = episode_dir / dl.audio_path.name
        dl.audio_path.rename(dest)
        _progress(cb, "tag", dl.video_id, f"Tagging: {dl.title}", 0)
        tag_single(
            dest, title=dl.title, artist=artist,
            content_type=content_type, album=album,
        )

    return episode_dir


def _update_library_after_processing(
    library: Library, entry: QueueEntry, dl: DownloadResult, episode_dir: Path,
    options: SyncOptions,
) -> None:
    total_size = dir_size_bytes(episode_dir)
    chunk_count = len(list(episode_dir.glob("*.mp3")))
    episode_info = {
        "folder_name": dl.folder_name,
        "chunk_count": chunk_count,
        "total_size_bytes": total_size,
    }
    move_to_downloaded(library, entry, episode_info)
    save_library(library, options.library_path)


def _transfer_to_garmin(
    library: Library,
    processed: list[tuple[DownloadResult, Path, ContentType]],
    options: SyncOptions,
    cb: PipelineCallbacks,
) -> int:
    garmin_mount = find_garmin_mount()
    if garmin_mount is None:
        _progress(cb, "info", "", "No Garmin watch detected. Episodes saved locally.", 0)
        return 0

    transferred = 0
    for dl, episode_dir, content_type in processed:
        if _cancelled(cb):
            break
        if _transfer_single_episode(
            library, dl, episode_dir, content_type, garmin_mount, options, cb,
        ):
            transferred += 1

    save_library(library, options.library_path)
    return transferred


def _transfer_single_episode(
    library: Library,
    dl: DownloadResult,
    episode_dir: Path,
    content_type: ContentType,
    garmin_mount: Path,
    options: SyncOptions,
    cb: PipelineCallbacks,
) -> bool:
    needed_bytes = dir_size_bytes(episode_dir)
    available = get_available_space_bytes(garmin_mount)

    if needed_bytes > available:
        freed = _try_free_space(needed_bytes, available, garmin_mount, cb)
        if not freed:
            _progress(
                cb, "skip", dl.video_id,
                f"Skipping transfer of '{dl.title}' - not enough space.", 0,
            )
            return False

    _progress(cb, "transfer", dl.video_id, f"Transferring: {dl.title}", 0)
    copy_to_garmin(episode_dir, garmin_mount, content_type)
    mark_synced(library, dl.video_id)
    _progress(cb, "transfer", dl.video_id, f"Synced: {dl.title}", 100)
    return True


def _try_free_space(
    needed_bytes: int, available_bytes: int, garmin_mount: Path,
    cb: PipelineCallbacks,
) -> bool:
    deficit = needed_bytes - available_bytes
    episodes = list_garmin_episodes(garmin_mount)
    episodes.sort(key=lambda e: e.modified_at)

    to_remove = select_episodes_for_removal(episodes, deficit)
    if not to_remove:
        return False

    if cb.on_confirm_removal:
        approved = cb.on_confirm_removal(
            [asdict(e) for e in to_remove], deficit,
        )
    else:
        _print_removal_plan(to_remove, deficit)
        approved = _confirm_removal()

    if not approved:
        return False

    for ep in to_remove:
        remove_from_garmin(ep.folder_name, garmin_mount)
        _progress(cb, "info", "", f"  Removed: {ep.folder_name}", 0)

    return True


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


def _transfer_local_episode(
    library: Library, ep: DownloadedEpisode, garmin_mount: Path,
    cb: PipelineCallbacks,
) -> bool:
    episode_dir = OUTPUT_DIR / ep.folder_name
    if not episode_dir.exists():
        _progress(cb, "skip", ep.video_id, f"Skipping '{ep.title}' - local files not found.", 0)
        return False

    content_type = ContentType(ep.content_type)
    needed_bytes = dir_size_bytes(episode_dir)
    available = get_available_space_bytes(garmin_mount)

    if needed_bytes > available:
        freed = _try_free_space(needed_bytes, available, garmin_mount, cb)
        if not freed:
            _progress(
                cb, "skip", ep.video_id,
                f"Skipping transfer of '{ep.title}' - not enough space.", 0,
            )
            return False

    _progress(cb, "transfer", ep.video_id, f"Transferring: {ep.title}", 0)
    copy_to_garmin(episode_dir, garmin_mount, content_type)
    mark_synced(library, ep.video_id)
    _progress(cb, "transfer", ep.video_id, f"Synced: {ep.title}", 100)
    return True
