"""Local manifest (JSON) - tracks queue and download state."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from youtube_audio_chunker.constants import ContentType, LIBRARY_PATH


@dataclass
class QueueEntry:
    video_id: str
    url: str
    title: str
    added_at: str
    content_type: str = ContentType.MUSIC.value
    show_name: str | None = None
    artist: str | None = None


@dataclass
class DownloadedEpisode:
    video_id: str
    url: str
    title: str
    folder_name: str
    chunk_count: int
    total_size_bytes: int
    downloaded_at: str
    synced_at: str | None
    content_type: str = ContentType.MUSIC.value
    show_name: str | None = None
    artist: str | None = None


@dataclass
class Library:
    queue: list[QueueEntry]
    downloaded: list[DownloadedEpisode]


def load_library(path: Path = LIBRARY_PATH) -> Library:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return Library(queue=[], downloaded=[])

    data = json.loads(path.read_text())
    queue = [QueueEntry(**e) for e in data.get("queue", [])]
    downloaded = [DownloadedEpisode(**e) for e in data.get("downloaded", [])]
    return Library(queue=queue, downloaded=downloaded)


def save_library(library: Library, path: Path = LIBRARY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "queue": [asdict(e) for e in library.queue],
        "downloaded": [asdict(e) for e in library.downloaded],
    }
    path.write_text(json.dumps(data, indent=2))


def add_to_queue(
    library: Library,
    url: str,
    title: str,
    video_id: str,
    content_type: str = ContentType.MUSIC.value,
    show_name: str | None = None,
) -> bool:
    """Add a video to the queue. Returns True if added, False if duplicate."""
    existing_ids = {e.video_id for e in library.queue} | {
        e.video_id for e in library.downloaded
    }
    if video_id in existing_ids:
        return False

    entry = QueueEntry(
        video_id=video_id,
        url=url,
        title=title,
        added_at=datetime.now(timezone.utc).isoformat(),
        content_type=content_type,
        show_name=show_name,
    )
    library.queue.append(entry)
    return True


def move_to_downloaded(
    library: Library, queue_entry: QueueEntry, episode_info: dict
) -> Library:
    library.queue = [e for e in library.queue if e.video_id != queue_entry.video_id]
    episode = DownloadedEpisode(
        video_id=queue_entry.video_id,
        url=queue_entry.url,
        title=queue_entry.title,
        folder_name=episode_info["folder_name"],
        chunk_count=episode_info["chunk_count"],
        total_size_bytes=episode_info["total_size_bytes"],
        downloaded_at=datetime.now(timezone.utc).isoformat(),
        synced_at=None,
        content_type=queue_entry.content_type,
        show_name=queue_entry.show_name,
        artist=queue_entry.artist,
    )
    library.downloaded.append(episode)
    return library


def mark_synced(library: Library, video_id: str) -> Library:
    for episode in library.downloaded:
        if episode.video_id == video_id:
            episode.synced_at = datetime.now(timezone.utc).isoformat()
    return library


def remove_episode(library: Library, video_id: str) -> Library:
    library.queue = [e for e in library.queue if e.video_id != video_id]
    library.downloaded = [e for e in library.downloaded if e.video_id != video_id]
    return library


def rename_show(library: Library, old_name: str, new_name: str) -> int:
    """Rename a show across all queue and downloaded entries. Returns count updated."""
    count = 0
    for entry in library.queue:
        if entry.show_name == old_name:
            entry.show_name = new_name
            count += 1
    for episode in library.downloaded:
        if episode.show_name == old_name:
            episode.show_name = new_name
            count += 1
    return count


def list_shows(library: Library) -> list[dict]:
    """Return unique show names with episode counts and content types."""
    shows: dict[str, dict] = {}
    all_entries = [
        *((e.show_name, e.content_type) for e in library.queue),
        *((e.show_name, e.content_type) for e in library.downloaded),
    ]
    for show_name, content_type in all_entries:
        if show_name is None:
            continue
        if show_name not in shows:
            shows[show_name] = {
                "show_name": show_name,
                "episode_count": 0,
                "content_types": set(),
            }
        shows[show_name]["episode_count"] += 1
        shows[show_name]["content_types"].add(content_type)

    return [
        {**s, "content_types": sorted(s["content_types"])} for s in shows.values()
    ]


def update_episode(
    library: Library, video_id: str, updates: dict
) -> DownloadedEpisode | None:
    """Update fields on a downloaded episode. Returns updated episode or None."""
    allowed_fields = {"show_name", "artist", "title", "content_type"}
    for episode in library.downloaded:
        if episode.video_id == video_id:
            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(episode, field, value)
            return episode
    return None
