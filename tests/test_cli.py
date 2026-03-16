import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from youtube_audio_chunker.cli import main, build_parser, _find_episode_by_title
from youtube_audio_chunker.library import Library, QueueEntry, DownloadedEpisode
from youtube_audio_chunker.garmin import GarminEpisode


@pytest.fixture
def parser():
    return build_parser()


class TestBuildParser:
    def test_add_subcommand(self, parser):
        args = parser.parse_args(["add", "https://youtube.com/watch?v=abc"])
        assert args.command == "add"
        assert args.urls == ["https://youtube.com/watch?v=abc"]

    def test_add_multiple_urls(self, parser):
        args = parser.parse_args(["add", "url1", "url2", "url3"])
        assert len(args.urls) == 3

    def test_add_show_flag(self, parser):
        args = parser.parse_args(["add", "--show", "My Show", "url1"])
        assert args.show == "My Show"

    def test_add_show_flag_defaults_to_none(self, parser):
        args = parser.parse_args(["add", "url1"])
        assert args.show is None

    def test_sync_defaults(self, parser):
        args = parser.parse_args(["sync"])
        assert args.command == "sync"
        assert args.chunk_duration is None
        assert args.no_transfer is False

    def test_sync_with_options(self, parser):
        args = parser.parse_args([
            "sync", "--chunk-duration", "600",
            "--artist", "Host Name",
            "--keep-full", "--no-transfer",
        ])
        assert args.chunk_duration == 600
        assert args.artist == "Host Name"
        assert args.keep_full is True
        assert args.no_transfer is True

    def test_download_show_flag(self, parser):
        args = parser.parse_args(["download", "--show", "My Show", "url1"])
        assert args.show == "My Show"

    def test_download_show_flag_defaults_to_none(self, parser):
        args = parser.parse_args(["download", "url1"])
        assert args.show is None

    def test_list_no_flags(self, parser):
        args = parser.parse_args(["list"])
        assert args.command == "list"
        assert args.queued is False
        assert args.local is False
        assert args.watch is False

    def test_list_with_flags(self, parser):
        args = parser.parse_args(["list", "--queued"])
        assert args.queued is True

    def test_remove_subcommand(self, parser):
        args = parser.parse_args(["remove", "My Episode Title"])
        assert args.command == "remove"
        assert args.title == "My Episode Title"

    def test_remove_with_watch_flag(self, parser):
        args = parser.parse_args(["remove", "Title", "--watch"])
        assert args.watch is True


MODULE = "youtube_audio_chunker.cli"


class TestAddCommand:
    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.extract_metadata")
    @patch(f"{MODULE}.load_library")
    def test_adds_urls_to_queue(self, mock_load, mock_meta, mock_save):
        mock_load.return_value = Library(queue=[], downloaded=[])
        mock_meta.return_value = [{"id": "abc", "title": "Test"}]

        with patch("sys.argv", ["yac", "add", "https://youtube.com/watch?v=abc"]):
            main()

        mock_meta.assert_called_once()
        mock_save.assert_called_once()

    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.extract_metadata")
    @patch(f"{MODULE}.load_library")
    def test_expands_playlist(self, mock_load, mock_meta, mock_save):
        mock_load.return_value = Library(queue=[], downloaded=[])
        mock_meta.return_value = [
            {"id": "v1", "title": "Video 1"},
            {"id": "v2", "title": "Video 2"},
        ]

        with patch("sys.argv", ["yac", "add", "https://youtube.com/playlist?list=PL1"]):
            main()

        saved_lib = mock_save.call_args[0][0]
        assert len(saved_lib.queue) == 2


class TestSyncCommand:
    @patch(f"{MODULE}.process_queue")
    def test_calls_process_queue(self, mock_process):
        with patch("sys.argv", ["yac", "sync", "--no-transfer"]):
            main()

        mock_process.assert_called_once()
        opts = mock_process.call_args[0][0]
        assert opts.no_transfer is True
        assert opts.chunk_duration_seconds is None


class TestListCommand:
    @patch(f"{MODULE}.list_garmin_episodes")
    @patch(f"{MODULE}.find_garmin_mount")
    @patch(f"{MODULE}.load_library")
    def test_list_all_sections(self, mock_load, mock_find, mock_list, capsys):
        mock_load.return_value = Library(
            queue=[
                QueueEntry(video_id="q1", url="u1", title="Queued One", added_at="t"),
            ],
            downloaded=[
                DownloadedEpisode(
                    video_id="d1", url="u2", title="Downloaded One",
                    folder_name="Downloaded-One", chunk_count=3,
                    total_size_bytes=5000, downloaded_at="t", synced_at=None,
                ),
            ],
        )
        mock_find.return_value = None

        with patch("sys.argv", ["yac", "list"]):
            main()

        output = capsys.readouterr().out
        assert "Queued One" in output
        assert "Downloaded One" in output


class TestRemoveCommand:
    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.load_library")
    def test_removes_by_title(self, mock_load, mock_save):
        mock_load.return_value = Library(
            queue=[],
            downloaded=[
                DownloadedEpisode(
                    video_id="d1", url="u", title="Episode to Remove",
                    folder_name="Episode-to-Remove", chunk_count=3,
                    total_size_bytes=5000, downloaded_at="t", synced_at=None,
                ),
            ],
        )

        with patch("sys.argv", ["yac", "remove", "Episode to Remove"]):
            main()

        saved_lib = mock_save.call_args[0][0]
        assert len(saved_lib.downloaded) == 0


class TestFindEpisodeByTitle:
    def test_case_insensitive_match_downloaded(self):
        library = Library(
            queue=[],
            downloaded=[
                DownloadedEpisode(
                    video_id="d1", url="u", title="My Episode",
                    folder_name="My-Episode", chunk_count=3,
                    total_size_bytes=5000, downloaded_at="t", synced_at=None,
                ),
            ],
        )

        video_id, folder = _find_episode_by_title(library, "my episode")

        assert video_id == "d1"
        assert folder == "My-Episode"

    def test_case_insensitive_match_queued(self):
        library = Library(
            queue=[
                QueueEntry(video_id="q1", url="u", title="My Episode", added_at="t"),
            ],
            downloaded=[],
        )

        video_id, folder = _find_episode_by_title(library, "MY EPISODE")

        assert video_id == "q1"
        assert folder is None

    def test_whitespace_stripped_match(self):
        library = Library(
            queue=[],
            downloaded=[
                DownloadedEpisode(
                    video_id="d1", url="u", title="My Episode",
                    folder_name="My-Episode", chunk_count=3,
                    total_size_bytes=5000, downloaded_at="t", synced_at=None,
                ),
            ],
        )

        video_id, folder = _find_episode_by_title(library, "  My Episode  ")

        assert video_id == "d1"
        assert folder == "My-Episode"

    def test_returns_none_when_not_found(self):
        library = Library(queue=[], downloaded=[])

        video_id, folder = _find_episode_by_title(library, "Nonexistent")

        assert video_id is None
        assert folder is None


class TestShowCommand:
    def test_show_list_parses(self, parser):
        args = parser.parse_args(["show", "list"])
        assert args.command == "show"
        assert args.show_action == "list"

    def test_show_rename_parses(self, parser):
        args = parser.parse_args(["show", "rename", "Old Name", "New Name"])
        assert args.command == "show"
        assert args.show_action == "rename"
        assert args.old_name == "Old Name"
        assert args.new_name == "New Name"

    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.list_shows")
    @patch(f"{MODULE}.load_library")
    def test_show_list_displays_shows(self, mock_load, mock_list_shows, mock_save, capsys):
        mock_load.return_value = Library(queue=[], downloaded=[])
        mock_list_shows.return_value = [
            {"show_name": "My Podcast", "episode_count": 5, "content_types": ["podcast"]},
            {"show_name": "Music Mix", "episode_count": 3, "content_types": ["music"]},
        ]

        with patch("sys.argv", ["yac", "show", "list"]):
            main()

        output = capsys.readouterr().out
        assert "My Podcast" in output
        assert "5" in output
        assert "Music Mix" in output
        assert "3" in output

    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.rename_show")
    @patch(f"{MODULE}.load_library")
    def test_show_rename_calls_rename_show(self, mock_load, mock_rename, mock_save, capsys):
        mock_load.return_value = Library(queue=[], downloaded=[])
        mock_rename.return_value = 3

        with patch("sys.argv", ["yac", "show", "rename", "Old Name", "New Name"]):
            main()

        mock_rename.assert_called_once()
        call_args = mock_rename.call_args
        assert call_args[0][1] == "Old Name"
        assert call_args[0][2] == "New Name"
        mock_save.assert_called_once()

        output = capsys.readouterr().out
        assert "3" in output


class TestEditCommand:
    def test_edit_parses_video_id(self, parser):
        args = parser.parse_args(["edit", "abc123"])
        assert args.command == "edit"
        assert args.video_id == "abc123"

    def test_edit_parses_show_flag(self, parser):
        args = parser.parse_args(["edit", "abc123", "--show", "New Show"])
        assert args.show == "New Show"

    def test_edit_parses_artist_flag(self, parser):
        args = parser.parse_args(["edit", "abc123", "--artist", "New Artist"])
        assert args.artist == "New Artist"

    def test_edit_parses_title_flag(self, parser):
        args = parser.parse_args(["edit", "abc123", "--title", "New Title"])
        assert args.title == "New Title"

    def test_edit_parses_type_flag(self, parser):
        args = parser.parse_args(["edit", "abc123", "--type", "podcast"])
        assert args.type == "podcast"

    def test_edit_all_flags_combined(self, parser):
        args = parser.parse_args([
            "edit", "abc123",
            "--show", "My Show",
            "--artist", "My Artist",
            "--title", "My Title",
            "--type", "audiobook",
        ])
        assert args.show == "My Show"
        assert args.artist == "My Artist"
        assert args.title == "My Title"
        assert args.type == "audiobook"

    def test_edit_flags_default_to_none(self, parser):
        args = parser.parse_args(["edit", "abc123"])
        assert args.show is None
        assert args.artist is None
        assert args.title is None
        assert args.type is None

    @patch(f"{MODULE}.edit_episode")
    def test_edit_calls_edit_episode(self, mock_edit, capsys):
        mock_edit.return_value = {
            "video_id": "abc123", "title": "New Title",
            "show_name": "New Show", "artist": "New Artist",
        }

        with patch("sys.argv", ["yac", "edit", "abc123", "--show", "New Show", "--title", "New Title"]):
            main()

        mock_edit.assert_called_once()
        call_args = mock_edit.call_args
        assert call_args[0][0] == "abc123"
        updates = call_args[0][1]
        assert updates["show_name"] == "New Show"
        assert updates["title"] == "New Title"
        assert "artist" not in updates

    @patch(f"{MODULE}.edit_episode")
    def test_edit_episode_not_found(self, mock_edit, capsys):
        mock_edit.return_value = None

        with patch("sys.argv", ["yac", "edit", "unknown"]):
            with pytest.raises(SystemExit):
                main()

        output = capsys.readouterr().err
        assert "not found" in output.lower()


class TestAddCommandWithShow:
    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.extract_metadata")
    @patch(f"{MODULE}.load_library")
    def test_passes_show_name_to_add_to_queue(self, mock_load, mock_meta, mock_save):
        mock_load.return_value = Library(queue=[], downloaded=[])
        mock_meta.return_value = [{"id": "abc", "title": "Test"}]

        with patch("sys.argv", ["yac", "add", "--show", "My Show", "https://youtube.com/watch?v=abc"]):
            main()

        saved_lib = mock_save.call_args[0][0]
        assert len(saved_lib.queue) == 1
        assert saved_lib.queue[0].show_name == "My Show"

    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.extract_metadata")
    @patch(f"{MODULE}.load_library")
    def test_show_name_none_when_not_provided(self, mock_load, mock_meta, mock_save):
        mock_load.return_value = Library(queue=[], downloaded=[])
        mock_meta.return_value = [{"id": "abc", "title": "Test"}]

        with patch("sys.argv", ["yac", "add", "https://youtube.com/watch?v=abc"]):
            main()

        saved_lib = mock_save.call_args[0][0]
        assert saved_lib.queue[0].show_name is None


class TestListCommandWithShowName:
    @patch(f"{MODULE}.list_garmin_episodes")
    @patch(f"{MODULE}.find_garmin_mount")
    @patch(f"{MODULE}.load_library")
    def test_displays_show_name_for_queued(self, mock_load, mock_find, mock_list, capsys):
        mock_load.return_value = Library(
            queue=[
                QueueEntry(video_id="q1", url="u1", title="Queued One", added_at="t",
                           show_name="My Podcast"),
            ],
            downloaded=[],
        )
        mock_find.return_value = None

        with patch("sys.argv", ["yac", "list"]):
            main()

        output = capsys.readouterr().out
        assert "Queued One" in output
        assert "My Podcast" in output

    @patch(f"{MODULE}.list_garmin_episodes")
    @patch(f"{MODULE}.find_garmin_mount")
    @patch(f"{MODULE}.load_library")
    def test_displays_show_name_for_downloaded(self, mock_load, mock_find, mock_list, capsys):
        mock_load.return_value = Library(
            queue=[],
            downloaded=[
                DownloadedEpisode(
                    video_id="d1", url="u2", title="Downloaded One",
                    folder_name="Downloaded-One", chunk_count=3,
                    total_size_bytes=5_000_000, downloaded_at="t", synced_at="t2",
                    show_name="My Show",
                ),
            ],
        )
        mock_find.return_value = None

        with patch("sys.argv", ["yac", "list"]):
            main()

        output = capsys.readouterr().out
        assert "Downloaded One" in output
        assert "My Show" in output

    @patch(f"{MODULE}.list_garmin_episodes")
    @patch(f"{MODULE}.find_garmin_mount")
    @patch(f"{MODULE}.load_library")
    def test_omits_show_name_when_none(self, mock_load, mock_find, mock_list, capsys):
        mock_load.return_value = Library(
            queue=[
                QueueEntry(video_id="q1", url="u1", title="Queued One", added_at="t"),
            ],
            downloaded=[
                DownloadedEpisode(
                    video_id="d1", url="u2", title="Downloaded One",
                    folder_name="Downloaded-One", chunk_count=3,
                    total_size_bytes=5_000_000, downloaded_at="t", synced_at=None,
                ),
            ],
        )
        mock_find.return_value = None

        with patch("sys.argv", ["yac", "list"]):
            main()

        output = capsys.readouterr().out
        # Show name should not appear when it's None
        assert "None" not in output
