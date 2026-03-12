import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from youtube_audio_chunker.cli import main, build_parser
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
