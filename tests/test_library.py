import json
from datetime import datetime, timezone

import pytest

from youtube_audio_chunker.library import (
    Library,
    QueueEntry,
    DownloadedEpisode,
    load_library,
    save_library,
    add_to_queue,
    move_to_downloaded,
    mark_synced,
    remove_episode,
)


@pytest.fixture
def library_path(tmp_app_dir):
    return tmp_app_dir / "library.json"


@pytest.fixture
def empty_library():
    return Library(queue=[], downloaded=[])


@pytest.fixture
def queue_entry():
    return QueueEntry(
        video_id="abc123",
        url="https://www.youtube.com/watch?v=abc123",
        title="Test Video",
        added_at="2026-03-01T12:00:00+00:00",
    )


@pytest.fixture
def downloaded_episode():
    return DownloadedEpisode(
        video_id="abc123",
        url="https://www.youtube.com/watch?v=abc123",
        title="Test Video",
        folder_name="Test-Video",
        chunk_count=5,
        total_size_bytes=10_000_000,
        downloaded_at="2026-03-01T12:05:00+00:00",
        synced_at=None,
    )


class TestLoadLibrary:
    def test_returns_empty_library_when_file_missing(self, library_path):
        lib = load_library(library_path)
        assert lib.queue == []
        assert lib.downloaded == []

    def test_loads_existing_library(self, library_path, queue_entry):
        data = {
            "queue": [
                {
                    "video_id": queue_entry.video_id,
                    "url": queue_entry.url,
                    "title": queue_entry.title,
                    "added_at": queue_entry.added_at,
                }
            ],
            "downloaded": [],
        }
        library_path.write_text(json.dumps(data))

        lib = load_library(library_path)
        assert len(lib.queue) == 1
        assert lib.queue[0].video_id == "abc123"
        assert lib.queue[0].title == "Test Video"

    def test_creates_parent_dirs_on_load(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "library.json"
        lib = load_library(nested)
        assert lib.queue == []
        assert nested.parent.exists()


class TestSaveLibrary:
    def test_roundtrip(self, library_path, queue_entry, downloaded_episode):
        lib = Library(queue=[queue_entry], downloaded=[downloaded_episode])
        save_library(lib, library_path)

        loaded = load_library(library_path)
        assert len(loaded.queue) == 1
        assert loaded.queue[0].video_id == queue_entry.video_id
        assert len(loaded.downloaded) == 1
        assert loaded.downloaded[0].folder_name == "Test-Video"

    def test_creates_parent_dirs_on_save(self, tmp_path, empty_library):
        nested = tmp_path / "a" / "b" / "library.json"
        save_library(empty_library, nested)
        assert nested.exists()


class TestAddToQueue:
    def test_adds_entry(self, empty_library):
        result = add_to_queue(
            empty_library,
            url="https://www.youtube.com/watch?v=xyz",
            title="New Video",
            video_id="xyz",
        )
        assert result is True
        assert len(empty_library.queue) == 1
        assert empty_library.queue[0].video_id == "xyz"
        assert empty_library.queue[0].title == "New Video"

    def test_deduplicates_by_video_id(self, empty_library):
        assert add_to_queue(empty_library, url="u1", title="V1", video_id="dup") is True
        assert add_to_queue(empty_library, url="u2", title="V1 again", video_id="dup") is False
        assert len(empty_library.queue) == 1

    def test_deduplicates_against_downloaded(self, downloaded_episode):
        lib = Library(queue=[], downloaded=[downloaded_episode])
        result = add_to_queue(
            lib,
            url=downloaded_episode.url,
            title=downloaded_episode.title,
            video_id=downloaded_episode.video_id,
        )
        assert result is False
        assert len(lib.queue) == 0

    def test_sets_added_at_timestamp(self, empty_library):
        add_to_queue(empty_library, url="u", title="T", video_id="v")
        ts = datetime.fromisoformat(empty_library.queue[0].added_at)
        assert ts.tzinfo is not None


class TestMoveToDownloaded:
    def test_moves_from_queue_to_downloaded(self, queue_entry):
        lib = Library(queue=[queue_entry], downloaded=[])
        episode_info = {
            "folder_name": "Test-Video",
            "chunk_count": 5,
            "total_size_bytes": 10_000_000,
        }
        lib = move_to_downloaded(lib, queue_entry, episode_info)
        assert len(lib.queue) == 0
        assert len(lib.downloaded) == 1
        assert lib.downloaded[0].folder_name == "Test-Video"
        assert lib.downloaded[0].chunk_count == 5

    def test_preserves_other_queue_entries(self):
        entry1 = QueueEntry(video_id="a", url="u1", title="T1", added_at="t")
        entry2 = QueueEntry(video_id="b", url="u2", title="T2", added_at="t")
        lib = Library(queue=[entry1, entry2], downloaded=[])
        episode_info = {"folder_name": "T1", "chunk_count": 3, "total_size_bytes": 5000}
        lib = move_to_downloaded(lib, entry1, episode_info)
        assert len(lib.queue) == 1
        assert lib.queue[0].video_id == "b"


class TestMarkSynced:
    def test_sets_synced_at(self, downloaded_episode):
        lib = Library(queue=[], downloaded=[downloaded_episode])
        lib = mark_synced(lib, "abc123")
        assert lib.downloaded[0].synced_at is not None
        ts = datetime.fromisoformat(lib.downloaded[0].synced_at)
        assert ts.tzinfo is not None

    def test_noop_for_unknown_video_id(self, downloaded_episode):
        lib = Library(queue=[], downloaded=[downloaded_episode])
        lib = mark_synced(lib, "unknown")
        assert lib.downloaded[0].synced_at is None


class TestRemoveEpisode:
    def test_removes_downloaded_episode(self, downloaded_episode):
        lib = Library(queue=[], downloaded=[downloaded_episode])
        lib = remove_episode(lib, "abc123")
        assert len(lib.downloaded) == 0

    def test_removes_queued_entry(self, queue_entry):
        lib = Library(queue=[queue_entry], downloaded=[])
        lib = remove_episode(lib, "abc123")
        assert len(lib.queue) == 0

    def test_noop_for_unknown_video_id(self, empty_library):
        lib = remove_episode(empty_library, "unknown")
        assert len(lib.queue) == 0
        assert len(lib.downloaded) == 0
