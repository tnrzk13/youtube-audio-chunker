from dataclasses import asdict
from unittest.mock import patch, MagicMock

from youtube_audio_chunker.garmin import GarminEpisode
from youtube_audio_chunker.library import (
    DownloadedEpisode,
    Library,
    QueueEntry,
)
from youtube_audio_chunker.sidecar import (
    _handle_add_to_queue,
    _handle_edit_episode,
    _handle_edit_queue_entry,
    _handle_get_garmin_status,
    _handle_list_channel_videos,
    _handle_list_shows,
    _handle_rename_show,
    _handle_resync_episode,
    _handle_search_youtube,
)

SIDECAR_MODULE = "youtube_audio_chunker.sidecar"


class TestHandleGetGarminStatus:
    @patch(f"{SIDECAR_MODULE}.get_total_space_bytes", return_value=8_000_000_000)
    @patch(f"{SIDECAR_MODULE}.get_available_space_bytes", return_value=3_500_000_000)
    @patch(f"{SIDECAR_MODULE}.list_garmin_episodes")
    @patch(f"{SIDECAR_MODULE}.find_garmin_mount")
    def test_connected_includes_total_bytes(
        self, mock_mount, mock_list, mock_available, mock_total, tmp_path
    ):
        mock_mount.return_value = tmp_path
        mock_list.return_value = [
            GarminEpisode(
                folder_name="My-Podcast",
                total_size_bytes=500_000_000,
                modified_at=1000.0,
                location="Music",
            )
        ]

        result = _handle_get_garmin_status({})

        assert result["connected"] is True
        assert result["available_bytes"] == 3_500_000_000
        assert result["total_bytes"] == 8_000_000_000
        assert len(result["episodes"]) == 1
        assert result["episodes"][0]["folder_name"] == "My-Podcast"

    @patch(f"{SIDECAR_MODULE}.find_garmin_mount", return_value=None)
    def test_disconnected_includes_total_bytes(self, mock_mount):
        result = _handle_get_garmin_status({})

        assert result["connected"] is False
        assert result["available_bytes"] == 0
        assert result["total_bytes"] == 0
        assert result["episodes"] == []

    @patch(f"{SIDECAR_MODULE}.get_total_space_bytes", return_value=8_000_000_000)
    @patch(f"{SIDECAR_MODULE}.get_available_space_bytes", return_value=8_000_000_000)
    @patch(f"{SIDECAR_MODULE}.list_garmin_episodes", return_value=[])
    @patch(f"{SIDECAR_MODULE}.find_garmin_mount")
    def test_empty_watch_total_equals_available(
        self, mock_mount, mock_list, mock_available, mock_total, tmp_path
    ):
        mock_mount.return_value = tmp_path

        result = _handle_get_garmin_status({})

        assert result["total_bytes"] == 8_000_000_000
        assert result["available_bytes"] == 8_000_000_000
        assert result["episodes"] == []


class TestHandleListShows:
    @patch(f"{SIDECAR_MODULE}.load_library")
    def test_returns_show_groupings(self, mock_load):
        library = Library(
            queue=[
                QueueEntry(
                    video_id="q1", url="u1", title="Ep 1",
                    added_at="2024-01-01", show_name="My Show",
                ),
            ],
            downloaded=[
                DownloadedEpisode(
                    video_id="d1", url="u2", title="Ep 2",
                    folder_name="ep-2", chunk_count=3,
                    total_size_bytes=1000, downloaded_at="2024-01-01",
                    synced_at=None, show_name="My Show",
                ),
                DownloadedEpisode(
                    video_id="d2", url="u3", title="Ep 3",
                    folder_name="ep-3", chunk_count=5,
                    total_size_bytes=2000, downloaded_at="2024-01-02",
                    synced_at=None, show_name="Other Show",
                ),
            ],
        )
        mock_load.return_value = library

        result = _handle_list_shows({})

        shows = result["shows"]
        assert len(shows) == 2
        show_names = {s["show_name"] for s in shows}
        assert show_names == {"My Show", "Other Show"}
        my_show = next(s for s in shows if s["show_name"] == "My Show")
        assert my_show["episode_count"] == 2


class TestHandleRenameShow:
    @patch(f"{SIDECAR_MODULE}.save_library")
    @patch(f"{SIDECAR_MODULE}.load_library")
    def test_renames_and_returns_count(self, mock_load, mock_save):
        library = Library(
            queue=[],
            downloaded=[
                DownloadedEpisode(
                    video_id="d1", url="u1", title="Ep 1",
                    folder_name="ep-1", chunk_count=3,
                    total_size_bytes=1000, downloaded_at="2024-01-01",
                    synced_at=None, show_name="Old Name",
                ),
                DownloadedEpisode(
                    video_id="d2", url="u2", title="Ep 2",
                    folder_name="ep-2", chunk_count=5,
                    total_size_bytes=2000, downloaded_at="2024-01-02",
                    synced_at=None, show_name="Old Name",
                ),
            ],
        )
        mock_load.return_value = library

        result = _handle_rename_show({"old_name": "Old Name", "new_name": "New Name"})

        assert result == {"renamed": 2}
        mock_save.assert_called_once_with(library)
        assert library.downloaded[0].show_name == "New Name"
        assert library.downloaded[1].show_name == "New Name"


class TestHandleEditEpisode:
    @patch(f"{SIDECAR_MODULE}.edit_episode")
    def test_passes_through_to_pipeline(self, mock_edit):
        mock_edit.return_value = {
            "video_id": "abc",
            "title": "My Title",
            "show_name": "New Show",
        }

        result = _handle_edit_episode({
            "video_id": "abc",
            "updates": {"show_name": "New Show"},
        })

        mock_edit.assert_called_once_with("abc", {"show_name": "New Show"})
        assert result["video_id"] == "abc"
        assert result["show_name"] == "New Show"

    @patch(f"{SIDECAR_MODULE}.edit_episode", return_value=None)
    def test_raises_on_not_found(self, mock_edit):
        import pytest

        with pytest.raises(Exception, match="Episode not found: xyz"):
            _handle_edit_episode({"video_id": "xyz", "updates": {}})


class TestHandleResyncEpisode:
    @patch(f"{SIDECAR_MODULE}.resync_episode")
    def test_passes_through_to_pipeline(self, mock_resync):
        mock_resync.return_value = {"video_id": "abc", "title": "My Episode"}

        result = _handle_resync_episode({"video_id": "abc"})

        mock_resync.assert_called_once_with("abc")
        assert result["video_id"] == "abc"

    @patch(f"{SIDECAR_MODULE}.resync_episode", return_value=None)
    def test_raises_on_not_found(self, mock_resync):
        import pytest

        with pytest.raises(Exception, match="Episode not found: xyz"):
            _handle_resync_episode({"video_id": "xyz"})


class TestHandleEditQueueEntry:
    @patch(f"{SIDECAR_MODULE}.edit_queue_entry")
    def test_passes_through_to_pipeline(self, mock_edit):
        mock_edit.return_value = {
            "video_id": "abc",
            "title": "My Title",
            "show_name": "New Show",
        }

        result = _handle_edit_queue_entry({
            "video_id": "abc",
            "updates": {"show_name": "New Show"},
        })

        mock_edit.assert_called_once_with("abc", {"show_name": "New Show"})
        assert result["show_name"] == "New Show"

    @patch(f"{SIDECAR_MODULE}.edit_queue_entry", return_value=None)
    def test_raises_on_not_found(self, mock_edit):
        import pytest

        with pytest.raises(Exception, match="Queue entry not found: xyz"):
            _handle_edit_queue_entry({"video_id": "xyz", "updates": {}})


class TestHandleSearchYoutube:
    @patch(f"{SIDECAR_MODULE}.search_youtube")
    def test_returns_results(self, mock_search):
        mock_search.return_value = [
            {
                "video_id": "abc",
                "title": "Test",
                "channel": "Ch",
                "duration_seconds": 120,
                "url": "https://www.youtube.com/watch?v=abc",
                "channel_url": "https://www.youtube.com/@Ch",
            }
        ]

        result = _handle_search_youtube({"query": "test"})

        assert len(result["results"]) == 1
        assert result["results"][0]["video_id"] == "abc"
        mock_search.assert_called_once_with("test", offset=0)

    def test_returns_empty_for_blank_query(self):
        result = _handle_search_youtube({"query": "  "})

        assert result == {"results": []}

    def test_returns_empty_for_missing_query(self):
        result = _handle_search_youtube({})

        assert result == {"results": []}


class TestHandleListChannelVideos:
    @patch(f"{SIDECAR_MODULE}.list_channel_videos")
    def test_returns_channel_videos(self, mock_list):
        mock_list.return_value = {
            "channel_name": "Lofi Girl",
            "videos": [
                {
                    "video_id": "v1",
                    "title": "Lofi Radio",
                    "duration_seconds": 12250,
                    "url": "https://www.youtube.com/watch?v=v1",
                },
            ],
        }

        result = _handle_list_channel_videos({
            "channel_url": "https://www.youtube.com/@LofiGirl"
        })

        assert result["channel_name"] == "Lofi Girl"
        assert len(result["videos"]) == 1
        mock_list.assert_called_once_with("https://www.youtube.com/@LofiGirl", offset=0)

    def test_raises_for_blank_channel_url(self):
        import pytest

        with pytest.raises(ValueError, match="channel_url is required"):
            _handle_list_channel_videos({"channel_url": "  "})

    def test_raises_for_missing_channel_url(self):
        import pytest

        with pytest.raises(ValueError, match="channel_url is required"):
            _handle_list_channel_videos({})


class TestHandleAddToQueueWithShowName:
    @patch(f"{SIDECAR_MODULE}.save_library")
    @patch(f"{SIDECAR_MODULE}.extract_metadata")
    @patch(f"{SIDECAR_MODULE}.load_library")
    def test_passes_show_name_to_add_to_queue(
        self, mock_load, mock_extract, mock_save
    ):
        library = Library(queue=[], downloaded=[])
        mock_load.return_value = library
        mock_extract.return_value = [{"title": "Video 1", "id": "vid1"}]

        result = _handle_add_to_queue({
            "urls": ["https://youtube.com/watch?v=vid1"],
            "show_name": "My Podcast",
        })

        assert result["added"] == ["Video 1"]
        assert library.queue[0].show_name == "My Podcast"

    @patch(f"{SIDECAR_MODULE}.save_library")
    @patch(f"{SIDECAR_MODULE}.extract_metadata")
    @patch(f"{SIDECAR_MODULE}.load_library")
    def test_omits_show_name_when_not_provided(
        self, mock_load, mock_extract, mock_save
    ):
        library = Library(queue=[], downloaded=[])
        mock_load.return_value = library
        mock_extract.return_value = [{"title": "Video 1", "id": "vid1"}]

        result = _handle_add_to_queue({
            "urls": ["https://youtube.com/watch?v=vid1"],
        })

        assert result["added"] == ["Video 1"]
        assert library.queue[0].show_name is None
