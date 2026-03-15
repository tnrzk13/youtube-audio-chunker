from pathlib import Path
from unittest.mock import patch, MagicMock, ANY

import pytest

from youtube_audio_chunker.constants import sanitize_filename
from youtube_audio_chunker.downloader import (
    _build_results,
    download_audio,
    extract_metadata,
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
        # Simulate the downloaded file
        expected_file = output_dir / "Test-Video.mp3"
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
        (output_dir / "T.mp3").write_bytes(b"\x00")

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
        (output_dir / "Test.mp3").write_bytes(b"\x00")
        info = {"id": "v1", "title": "Test", "uploader": "Uploader", "channel": "The Channel"}

        results = _build_results(info, output_dir)

        assert results[0].channel == "The Channel"

    def test_build_results_falls_back_to_uploader(self, output_dir):
        (output_dir / "Test.mp3").write_bytes(b"\x00")
        info = {"id": "v1", "title": "Test", "uploader": "The Uploader"}

        results = _build_results(info, output_dir)

        assert results[0].channel == "The Uploader"

    def test_build_results_falls_back_to_unknown(self, output_dir):
        (output_dir / "Test.mp3").write_bytes(b"\x00")
        info = {"id": "v1", "title": "Test"}

        results = _build_results(info, output_dir)

        assert results[0].channel == "Unknown"
