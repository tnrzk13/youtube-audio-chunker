from pathlib import Path
from unittest.mock import patch, MagicMock, ANY

import pytest

from youtube_audio_chunker.constants import sanitize_filename
from youtube_audio_chunker.downloader import (
    _build_results,
    _build_search_result,
    _find_audio_file,
    download_audio,
    extract_metadata,
    list_channel_videos,
    list_feed,
    list_user_playlists,
    list_playlist_videos,
    RESULTS_PAGE_SIZE,
    search_youtube,
    DownloadResult,
)
from youtube_audio_chunker.errors import DownloadError


@pytest.fixture
def output_dir(tmp_path):
    d = tmp_path / "downloads"
    d.mkdir()
    return d


class TestSanitizeFilename:
    def test_strips_fat32_illegal_chars(self):
        assert sanitize_filename('a/b\\c:d*e?"f<g>h|i') == "abcdefghi"

    def test_replaces_spaces_with_hyphens(self):
        assert sanitize_filename("hello world test") == "hello-world-test"

    def test_collapses_multiple_hyphens(self):
        assert sanitize_filename("a - b -- c") == "a-b-c"

    def test_strips_leading_trailing_hyphens(self):
        assert sanitize_filename(" -hello- ") == "hello"

    def test_preserves_normal_chars(self):
        assert sanitize_filename("My-Podcast_Episode01") == "My-Podcast_Episode01"

    def test_strips_fullwidth_equivalents_from_ytdlp(self):
        """yt-dlp replaces FAT32 illegal chars with fullwidth Unicode equivalents."""
        assert sanitize_filename("Game Theory #12： The Law") == "Game-Theory-#12-The-Law"
        assert sanitize_filename("What＊Is＊This？") == "WhatIsThis"


class TestExtractMetadata:
    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_extracts_single_video(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "id": "abc123",
            "title": "Test Video",
            "_type": "video",
        }

        results = extract_metadata("https://youtube.com/watch?v=abc123")

        assert len(results) == 1
        assert results[0]["id"] == "abc123"
        assert results[0]["title"] == "Test Video"

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_expands_playlist(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "_type": "playlist",
            "entries": [
                {"id": "v1", "title": "Video 1"},
                {"id": "v2", "title": "Video 2"},
            ],
        }

        results = extract_metadata("https://youtube.com/playlist?list=PL123")

        assert len(results) == 2
        assert results[0]["id"] == "v1"
        assert results[1]["id"] == "v2"


class TestDownloadAudio:
    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_returns_download_result(self, mock_ydl_cls, output_dir):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "id": "abc123",
            "title": "Test Video",
            "uploader": "Channel Name",
        }
        # Simulate the downloaded file (new id-prefixed pattern)
        expected_file = output_dir / "abc123_Test-Video.mp3"
        expected_file.write_bytes(b"\x00" * 100)

        results = download_audio(
            "https://youtube.com/watch?v=abc123", output_dir
        )

        assert len(results) == 1
        assert results[0].video_id == "abc123"
        assert results[0].title == "Test Video"
        assert results[0].artist == "Channel Name"

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_raises_download_error_on_failure(self, mock_ydl_cls, output_dir):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = Exception("Network error")

        with pytest.raises(DownloadError, match="Network error"):
            download_audio("https://youtube.com/watch?v=fail", output_dir)

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_configures_mp3_128k_output(self, mock_ydl_cls, output_dir):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "id": "x",
            "title": "T",
            "uploader": "U",
        }
        (output_dir / "x_T.mp3").write_bytes(b"\x00")

        download_audio("https://youtube.com/watch?v=x", output_dir)

        opts = mock_ydl_cls.call_args[0][0]
        assert opts["postprocessors"][0]["preferredcodec"] == "mp3"
        assert opts["postprocessors"][0]["preferredquality"] == "128"


class TestChannelExtraction:
    def test_download_result_has_channel_field(self):
        result = DownloadResult(
            video_id="v1",
            title="T",
            artist="A",
            audio_path=Path("/tmp/t.mp3"),
            folder_name="T",
            channel="My Channel",
        )
        assert result.channel == "My Channel"

    def test_download_result_channel_defaults_to_unknown(self):
        result = DownloadResult(
            video_id="v1",
            title="T",
            artist="A",
            audio_path=Path("/tmp/t.mp3"),
            folder_name="T",
        )
        assert result.channel == "Unknown"

    def test_build_results_extracts_channel_from_info(self, output_dir):
        (output_dir / "v1_Test.mp3").write_bytes(b"\x00")
        info = {"id": "v1", "title": "Test", "uploader": "Uploader", "channel": "The Channel"}

        results = _build_results(info, output_dir)

        assert results[0].channel == "The Channel"

    def test_build_results_falls_back_to_uploader(self, output_dir):
        (output_dir / "v1_Test.mp3").write_bytes(b"\x00")
        info = {"id": "v1", "title": "Test", "uploader": "The Uploader"}

        results = _build_results(info, output_dir)

        assert results[0].channel == "The Uploader"

    def test_build_results_falls_back_to_unknown(self, output_dir):
        (output_dir / "v1_Test.mp3").write_bytes(b"\x00")
        info = {"id": "v1", "title": "Test"}

        results = _build_results(info, output_dir)

        assert results[0].channel == "Unknown"


class TestSearchYoutube:
    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_returns_results_with_expected_fields(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "entries": [
                {
                    "id": "abc123",
                    "title": "Test Video",
                    "channel": "Test Channel",
                    "duration": 204,
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "channel_url": "https://www.youtube.com/@TestChannel",
                },
            ],
        }

        results = search_youtube("test query")

        assert len(results) == 1
        assert results[0]["video_id"] == "abc123"
        assert results[0]["title"] == "Test Video"
        assert results[0]["channel"] == "Test Channel"
        assert results[0]["duration_seconds"] == 204
        assert results[0]["url"] == "https://www.youtube.com/watch?v=abc123"
        assert results[0]["channel_url"] == "https://www.youtube.com/@TestChannel"
        mock_ydl.extract_info.assert_called_once_with(
            f"ytsearch{RESULTS_PAGE_SIZE}:test query", download=False
        )

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_offset_skips_earlier_results(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        entries = [{"id": f"v{i}", "title": f"Video {i}", "duration": 60} for i in range(15)]
        mock_ydl.extract_info.return_value = {"entries": entries}

        results = search_youtube("test", offset=10)

        assert len(results) == 5
        assert results[0]["video_id"] == "v10"
        mock_ydl.extract_info.assert_called_once_with(
            f"ytsearch{10 + RESULTS_PAGE_SIZE}:test", download=False
        )

    def test_build_search_result_falls_back_to_uploader(self):
        entry = {
            "id": "v1",
            "title": "T",
            "uploader": "The Uploader",
            "duration": 60,
        }

        result = _build_search_result(entry)

        assert result["channel"] == "The Uploader"

    def test_build_search_result_constructs_channel_url_from_id(self):
        entry = {
            "id": "v1",
            "title": "T",
            "channel": "Ch",
            "channel_id": "UC123",
            "duration": 60,
        }

        result = _build_search_result(entry)

        assert result["channel_url"] == "https://www.youtube.com/channel/UC123/videos"

    def test_build_search_result_prefers_channel_url_over_id(self):
        entry = {
            "id": "v1",
            "title": "T",
            "channel": "Ch",
            "channel_url": "https://www.youtube.com/@Existing",
            "channel_id": "UC123",
            "duration": 60,
        }

        result = _build_search_result(entry)

        assert result["channel_url"] == "https://www.youtube.com/@Existing"

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_returns_empty_list_when_no_entries(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"entries": []}

        results = search_youtube("nothing here")

        assert results == []


class TestListChannelVideos:
    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_returns_channel_videos(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "channel": "Lofi Girl",
            "entries": [
                {
                    "id": "v1",
                    "title": "Lofi Radio",
                    "duration": 12250,
                    "url": "https://www.youtube.com/watch?v=v1",
                },
                {
                    "id": "v2",
                    "title": "Jazz Cafe",
                    "duration": 6322,
                    "url": "https://www.youtube.com/watch?v=v2",
                },
            ],
        }

        result = list_channel_videos("https://www.youtube.com/@LofiGirl")

        assert result["channel_name"] == "Lofi Girl"
        assert len(result["videos"]) == 2
        assert result["videos"][0]["video_id"] == "v1"
        assert result["videos"][0]["title"] == "Lofi Radio"
        assert result["videos"][0]["duration_seconds"] == 12250
        assert result["videos"][1]["video_id"] == "v2"

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_appends_videos_to_channel_url(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"channel": "Ch", "entries": []}

        list_channel_videos("https://www.youtube.com/@Test")

        mock_ydl.extract_info.assert_called_once_with(
            "https://www.youtube.com/@Test/videos", download=False
        )

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_does_not_double_append_videos(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"channel": "Ch", "entries": []}

        list_channel_videos("https://www.youtube.com/@Test/videos")

        mock_ydl.extract_info.assert_called_once_with(
            "https://www.youtube.com/@Test/videos", download=False
        )

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_paginates_with_playliststart_and_playlistend(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"channel": "Ch", "entries": []}

        list_channel_videos("https://www.youtube.com/@Test", offset=10)

        opts = mock_ydl_cls.call_args[0][0]
        assert opts["playliststart"] == 11
        assert opts["playlistend"] == 10 + RESULTS_PAGE_SIZE

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_returns_empty_for_no_videos(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"channel": "Empty", "entries": []}

        result = list_channel_videos("https://www.youtube.com/@Empty")

        assert result["channel_name"] == "Empty"
        assert result["videos"] == []


class TestListFeed:
    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_returns_search_results_from_feed(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "entries": [
                {
                    "id": "v1",
                    "title": "Video 1",
                    "channel": "Channel A",
                    "duration": 300,
                    "url": "https://www.youtube.com/watch?v=v1",
                    "channel_url": "https://www.youtube.com/@ChannelA",
                },
                {
                    "id": "v2",
                    "title": "Video 2",
                    "channel": "Channel B",
                    "duration": 600,
                    "url": "https://www.youtube.com/watch?v=v2",
                    "channel_url": "https://www.youtube.com/@ChannelB",
                },
            ],
        }

        results = list_feed(":ytfeed:subscriptions", auth_opts={}, offset=0)

        assert len(results) == 2
        assert results[0]["video_id"] == "v1"
        assert results[0]["title"] == "Video 1"
        assert results[0]["channel"] == "Channel A"
        assert results[1]["video_id"] == "v2"

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_passes_auth_opts(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"entries": []}

        list_feed(":ytfeed:subscriptions", auth_opts={"cookiesfrombrowser": ("chrome",)}, offset=0)

        opts = mock_ydl_cls.call_args[0][0]
        assert opts["cookiesfrombrowser"] == ("chrome",)

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_paginates_with_playliststart_and_playlistend(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"entries": []}

        list_feed(":ytfeed:liked", auth_opts={}, offset=10)

        opts = mock_ydl_cls.call_args[0][0]
        assert opts["playliststart"] == 11
        assert opts["playlistend"] == 10 + RESULTS_PAGE_SIZE

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_returns_empty_for_no_entries(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"entries": []}

        results = list_feed(":ytfeed:subscriptions", auth_opts={}, offset=0)

        assert results == []

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_skips_none_entries(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "entries": [
                None,
                {"id": "v1", "title": "Good", "duration": 60},
            ],
        }

        results = list_feed(":ytfeed:subscriptions", auth_opts={}, offset=0)

        assert len(results) == 1
        assert results[0]["video_id"] == "v1"


class TestListUserPlaylists:
    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_returns_playlists(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "entries": [
                {
                    "id": "PLabc",
                    "title": "My Playlist",
                    "playlist_count": 12,
                    "thumbnails": [{"url": "http://img.com/1.jpg"}],
                },
                {
                    "id": "PLdef",
                    "title": "Another Playlist",
                    "playlist_count": 5,
                },
            ],
        }

        result = list_user_playlists(auth_opts={"cookiesfrombrowser": ("chrome",)})

        assert len(result) == 2
        assert result[0]["playlist_id"] == "PLabc"
        assert result[0]["title"] == "My Playlist"
        assert result[0]["video_count"] == 12
        assert result[1]["playlist_id"] == "PLdef"
        assert result[1]["video_count"] == 5

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_returns_empty_for_no_playlists(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"entries": []}

        result = list_user_playlists(auth_opts={})

        assert result == []


class TestListPlaylistVideos:
    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_returns_videos_from_playlist(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "entries": [
                {
                    "id": "v1",
                    "title": "First",
                    "channel": "Ch",
                    "duration": 120,
                    "url": "https://www.youtube.com/watch?v=v1",
                    "channel_url": "https://www.youtube.com/@Ch",
                },
            ],
        }

        results = list_playlist_videos("PLabc", auth_opts={}, offset=0)

        assert len(results) == 1
        assert results[0]["video_id"] == "v1"
        assert results[0]["title"] == "First"

    @patch("youtube_audio_chunker.downloader.yt_dlp.YoutubeDL")
    def test_constructs_playlist_url(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"entries": []}

        list_playlist_videos("PLabc123", auth_opts={}, offset=0)

        mock_ydl.extract_info.assert_called_once_with(
            "https://www.youtube.com/playlist?list=PLabc123", download=False
        )


class TestFindAudioFile:
    def test_matches_by_video_id_prefix(self, output_dir):
        (output_dir / "abc123_Test-Video.mp3").write_bytes(b"\x00")

        result = _find_audio_file(output_dir, "Test Video", video_id="abc123")

        assert result.name == "abc123_Test-Video.mp3"

    def test_falls_back_to_title_match_when_id_missing(self, output_dir):
        """Legacy files without video_id prefix still match by title."""
        (output_dir / "Test-Video.mp3").write_bytes(b"\x00")

        result = _find_audio_file(output_dir, "Test Video", video_id="abc123")

        assert result.name == "Test-Video.mp3"

    def test_falls_back_to_title_match_when_id_empty(self, output_dir):
        (output_dir / "Test-Video.mp3").write_bytes(b"\x00")

        result = _find_audio_file(output_dir, "Test Video", video_id="")

        assert result.name == "Test-Video.mp3"

    def test_prefers_id_match_over_title_match(self, output_dir):
        """When both id-prefixed and title-only files exist, prefer the id match."""
        (output_dir / "abc123_Test-Video.mp3").write_bytes(b"\x00")
        (output_dir / "Test-Video.mp3").write_bytes(b"\x00")

        result = _find_audio_file(output_dir, "Test Video", video_id="abc123")

        assert result.name == "abc123_Test-Video.mp3"

    def test_raises_when_no_match(self, output_dir):
        """No blind fallback - raises DownloadError when nothing matches."""
        (output_dir / "totally-different.mp3").write_bytes(b"\x00")

        with pytest.raises(DownloadError, match="not found"):
            _find_audio_file(output_dir, "My Title", video_id="xyz789")

    def test_stale_mp3_not_picked_up(self, output_dir):
        """A stale mp3 from a previous download must not be returned."""
        (output_dir / "old-episode.mp3").write_bytes(b"\x00")

        with pytest.raises(DownloadError):
            _find_audio_file(output_dir, "New Episode", video_id="new123")

    def test_matches_non_mp3_extension(self, output_dir):
        (output_dir / "abc123_Test-Video.m4a").write_bytes(b"\x00")

        result = _find_audio_file(output_dir, "Test Video", video_id="abc123")

        assert result.name == "abc123_Test-Video.m4a"

    def test_title_match_without_video_id_param(self, output_dir):
        """Backward compat: calling without video_id still works via title match."""
        (output_dir / "Test-Video.mp3").write_bytes(b"\x00")

        result = _find_audio_file(output_dir, "Test Video")

        assert result.name == "Test-Video.mp3"
