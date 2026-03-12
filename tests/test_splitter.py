import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from youtube_audio_chunker.splitter import split_audio
from youtube_audio_chunker.errors import DependencyError, SplitError
from youtube_audio_chunker.constants import DEFAULT_CHUNK_DURATION_SECONDS


@pytest.fixture
def fake_audio(tmp_path):
    audio = tmp_path / "input.mp3"
    audio.write_bytes(b"\x00" * 1000)
    return audio


@pytest.fixture
def output_dir(tmp_path):
    d = tmp_path / "chunks"
    d.mkdir()
    return d


class TestSplitAudio:
    @patch("youtube_audio_chunker.splitter.shutil.which", return_value=None)
    def test_raises_dependency_error_when_ffmpeg_missing(self, _mock, fake_audio, output_dir):
        with pytest.raises(DependencyError, match="ffmpeg"):
            split_audio(fake_audio, output_dir)

    @patch("youtube_audio_chunker.splitter.subprocess.run")
    @patch("youtube_audio_chunker.splitter.shutil.which", return_value="/usr/bin/ffmpeg")
    def test_calls_ffmpeg_with_correct_args(self, _which, mock_run, fake_audio, output_dir):
        mock_run.return_value = MagicMock(returncode=0)
        # Pre-create output files that ffmpeg would produce
        (output_dir / "01_input.mp3").write_bytes(b"\x00")
        (output_dir / "02_input.mp3").write_bytes(b"\x00")

        split_audio(fake_audio, output_dir, chunk_duration_seconds=300)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd[0]
        assert "-segment_time" in cmd
        assert "300" in cmd
        assert "-c" in cmd
        assert "copy" in cmd

    @patch("youtube_audio_chunker.splitter.subprocess.run")
    @patch("youtube_audio_chunker.splitter.shutil.which", return_value="/usr/bin/ffmpeg")
    def test_returns_sorted_chunk_paths(self, _which, mock_run, fake_audio, output_dir):
        mock_run.return_value = MagicMock(returncode=0)
        # Simulate ffmpeg output files
        (output_dir / "02_input.mp3").write_bytes(b"\x00")
        (output_dir / "01_input.mp3").write_bytes(b"\x00")
        (output_dir / "03_input.mp3").write_bytes(b"\x00")

        result = split_audio(fake_audio, output_dir)

        assert len(result) == 3
        assert result[0].name == "01_input.mp3"
        assert result[1].name == "02_input.mp3"
        assert result[2].name == "03_input.mp3"

    @patch("youtube_audio_chunker.splitter.subprocess.run")
    @patch("youtube_audio_chunker.splitter.shutil.which", return_value="/usr/bin/ffmpeg")
    def test_raises_split_error_on_ffmpeg_failure(self, _which, mock_run, fake_audio, output_dir):
        mock_run.return_value = MagicMock(returncode=1, stderr="encode error")

        with pytest.raises(SplitError, match="ffmpeg"):
            split_audio(fake_audio, output_dir)

    @patch("youtube_audio_chunker.splitter.subprocess.run")
    @patch("youtube_audio_chunker.splitter.shutil.which", return_value="/usr/bin/ffmpeg")
    def test_uses_default_chunk_duration(self, _which, mock_run, fake_audio, output_dir):
        mock_run.return_value = MagicMock(returncode=0)
        (output_dir / "01_input.mp3").write_bytes(b"\x00")

        split_audio(fake_audio, output_dir)

        cmd = mock_run.call_args[0][0]
        idx = cmd.index("-segment_time")
        assert cmd[idx + 1] == str(DEFAULT_CHUNK_DURATION_SECONDS)

    @patch("youtube_audio_chunker.splitter.subprocess.run")
    @patch("youtube_audio_chunker.splitter.shutil.which", return_value="/usr/bin/ffmpeg")
    def test_uses_segment_start_number_1(self, _which, mock_run, fake_audio, output_dir):
        mock_run.return_value = MagicMock(returncode=0)
        (output_dir / "01_input.mp3").write_bytes(b"\x00")

        split_audio(fake_audio, output_dir)

        cmd = mock_run.call_args[0][0]
        idx = cmd.index("-segment_start_number")
        assert cmd[idx + 1] == "1"
