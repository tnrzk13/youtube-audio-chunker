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
    remove_episodes,
    rename_show,
    list_shows,
    update_episode,
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


class TestRemoveEpisodes:
    def test_removes_mix_of_queue_and_downloaded(self):
        q1 = QueueEntry(video_id="q1", url="u1", title="Q1", added_at="t")
        q2 = QueueEntry(video_id="q2", url="u2", title="Q2", added_at="t")
        d1 = DownloadedEpisode(
            video_id="d1", url="u3", title="D1", folder_name="D1",
            chunk_count=1, total_size_bytes=100,
            downloaded_at="t", synced_at=None,
        )
        d2 = DownloadedEpisode(
            video_id="d2", url="u4", title="D2", folder_name="D2",
            chunk_count=1, total_size_bytes=100,
            downloaded_at="t", synced_at=None,
        )
        lib = Library(queue=[q1, q2], downloaded=[d1, d2])

        remove_episodes(lib, {"q1", "d2"})

        assert [e.video_id for e in lib.queue] == ["q2"]
        assert [e.video_id for e in lib.downloaded] == ["d1"]

    def test_noop_for_unknown_ids(self, empty_library):
        remove_episodes(empty_library, {"unknown1", "unknown2"})
        assert len(empty_library.queue) == 0
        assert len(empty_library.downloaded) == 0

    def test_empty_set_removes_nothing(self, queue_entry, downloaded_episode):
        lib = Library(queue=[queue_entry], downloaded=[downloaded_episode])
        remove_episodes(lib, set())
        assert len(lib.queue) == 1
        assert len(lib.downloaded) == 1


class TestBackwardCompatibility:
    def test_load_library_without_show_name_or_artist(self, library_path):
        """Old library.json files without show_name/artist fields still load."""
        data = {
            "queue": [
                {
                    "video_id": "old1",
                    "url": "https://www.youtube.com/watch?v=old1",
                    "title": "Old Queue Entry",
                    "added_at": "2026-01-01T00:00:00+00:00",
                    "content_type": "music",
                }
            ],
            "downloaded": [
                {
                    "video_id": "old2",
                    "url": "https://www.youtube.com/watch?v=old2",
                    "title": "Old Downloaded",
                    "folder_name": "Old-Downloaded",
                    "chunk_count": 3,
                    "total_size_bytes": 5000,
                    "downloaded_at": "2026-01-01T00:05:00+00:00",
                    "synced_at": None,
                    "content_type": "music",
                }
            ],
        }
        library_path.write_text(json.dumps(data))

        lib = load_library(library_path)
        assert lib.queue[0].show_name is None
        assert lib.queue[0].artist is None
        assert lib.downloaded[0].show_name is None
        assert lib.downloaded[0].artist is None


class TestRenameShow:
    def test_renames_matching_entries_in_queue_and_downloaded(self):
        q1 = QueueEntry(
            video_id="q1", url="u1", title="Ep 1", added_at="t",
            show_name="Old Show",
        )
        q2 = QueueEntry(
            video_id="q2", url="u2", title="Ep 2", added_at="t",
            show_name="Other Show",
        )
        d1 = DownloadedEpisode(
            video_id="d1", url="u3", title="Ep 3", folder_name="Ep-3",
            chunk_count=2, total_size_bytes=1000,
            downloaded_at="t", synced_at=None, show_name="Old Show",
        )
        lib = Library(queue=[q1, q2], downloaded=[d1])

        count = rename_show(lib, "Old Show", "New Show")

        assert count == 2
        assert lib.queue[0].show_name == "New Show"
        assert lib.queue[1].show_name == "Other Show"
        assert lib.downloaded[0].show_name == "New Show"

    def test_returns_zero_when_no_matches(self, empty_library):
        count = rename_show(empty_library, "Nonexistent", "New Name")
        assert count == 0


class TestListShows:
    def test_returns_grouped_shows(self):
        d1 = DownloadedEpisode(
            video_id="a", url="u", title="Ep 1", folder_name="f",
            chunk_count=1, total_size_bytes=100,
            downloaded_at="t", synced_at=None,
            content_type="podcast", show_name="My Podcast",
        )
        d2 = DownloadedEpisode(
            video_id="b", url="u", title="Ep 2", folder_name="f",
            chunk_count=1, total_size_bytes=100,
            downloaded_at="t", synced_at=None,
            content_type="podcast", show_name="My Podcast",
        )
        d3 = DownloadedEpisode(
            video_id="c", url="u", title="Song", folder_name="f",
            chunk_count=1, total_size_bytes=100,
            downloaded_at="t", synced_at=None,
            content_type="music", show_name="My Album",
        )
        q1 = QueueEntry(
            video_id="d", url="u", title="Ep 3", added_at="t",
            content_type="podcast", show_name="My Podcast",
        )
        lib = Library(queue=[q1], downloaded=[d1, d2, d3])

        shows = list_shows(lib)

        shows_by_name = {s["show_name"]: s for s in shows}
        assert len(shows_by_name) == 2
        assert shows_by_name["My Podcast"]["episode_count"] == 3
        assert "podcast" in shows_by_name["My Podcast"]["content_types"]
        assert shows_by_name["My Album"]["episode_count"] == 1
        assert "music" in shows_by_name["My Album"]["content_types"]

    def test_excludes_entries_without_show_name(self):
        d1 = DownloadedEpisode(
            video_id="a", url="u", title="Ungrouped", folder_name="f",
            chunk_count=1, total_size_bytes=100,
            downloaded_at="t", synced_at=None,
        )
        lib = Library(queue=[], downloaded=[d1])

        shows = list_shows(lib)
        assert shows == []

    def test_aggregates_mixed_content_types(self):
        d1 = DownloadedEpisode(
            video_id="a", url="u", title="Ep 1", folder_name="f",
            chunk_count=1, total_size_bytes=100,
            downloaded_at="t", synced_at=None,
            content_type="podcast", show_name="Mixed Show",
        )
        d2 = DownloadedEpisode(
            video_id="b", url="u", title="Ep 2", folder_name="f",
            chunk_count=1, total_size_bytes=100,
            downloaded_at="t", synced_at=None,
            content_type="music", show_name="Mixed Show",
        )
        lib = Library(queue=[], downloaded=[d1, d2])

        shows = list_shows(lib)
        assert len(shows) == 1
        assert sorted(shows[0]["content_types"]) == ["music", "podcast"]


class TestUpdateEpisode:
    def test_updates_specified_fields(self):
        episode = DownloadedEpisode(
            video_id="abc", url="u", title="Original Title", folder_name="f",
            chunk_count=1, total_size_bytes=100,
            downloaded_at="t", synced_at=None,
        )
        lib = Library(queue=[], downloaded=[episode])

        result = update_episode(lib, "abc", {
            "show_name": "My Show",
            "artist": "Some Artist",
            "title": "New Title",
        })

        assert result is not None
        assert result.show_name == "My Show"
        assert result.artist == "Some Artist"
        assert result.title == "New Title"
        # Unchanged fields preserved
        assert result.video_id == "abc"
        assert result.folder_name == "f"

    def test_leaves_unspecified_fields_unchanged(self):
        episode = DownloadedEpisode(
            video_id="abc", url="u", title="Original", folder_name="f",
            chunk_count=1, total_size_bytes=100,
            downloaded_at="t", synced_at=None,
            content_type="podcast", show_name="Old Show",
        )
        lib = Library(queue=[], downloaded=[episode])

        result = update_episode(lib, "abc", {"artist": "New Artist"})

        assert result is not None
        assert result.artist == "New Artist"
        assert result.show_name == "Old Show"
        assert result.title == "Original"
        assert result.content_type == "podcast"

    def test_returns_none_for_unknown_video_id(self, empty_library):
        result = update_episode(empty_library, "nonexistent", {"title": "X"})
        assert result is None


class TestAddToQueueWithShowName:
    def test_passes_show_name_through(self, empty_library):
        add_to_queue(
            empty_library,
            url="https://www.youtube.com/watch?v=xyz",
            title="Episode 1",
            video_id="xyz",
            show_name="My Podcast",
        )
        assert empty_library.queue[0].show_name == "My Podcast"

    def test_show_name_defaults_to_none(self, empty_library):
        add_to_queue(
            empty_library,
            url="https://www.youtube.com/watch?v=xyz",
            title="Episode 1",
            video_id="xyz",
        )
        assert empty_library.queue[0].show_name is None


class TestMoveToDownloadedCarriesShowFields:
    def test_carries_show_name_and_artist(self):
        entry = QueueEntry(
            video_id="q1", url="u1", title="Ep 1", added_at="t",
            show_name="My Show", artist="The Artist",
        )
        lib = Library(queue=[entry], downloaded=[])
        episode_info = {
            "folder_name": "Ep-1",
            "chunk_count": 3,
            "total_size_bytes": 5000,
        }

        lib = move_to_downloaded(lib, entry, episode_info)

        assert lib.downloaded[0].show_name == "My Show"
        assert lib.downloaded[0].artist == "The Artist"
