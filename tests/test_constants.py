import os
from unittest.mock import patch

import pytest

from youtube_audio_chunker.constants import atomic_write_text


class TestAtomicWriteText:
    def test_writes_content_correctly(self, tmp_path):
        path = tmp_path / "test.json"
        atomic_write_text(path, '{"key": "value"}')
        assert path.read_text() == '{"key": "value"}'

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "file.json"
        atomic_write_text(path, "hello")
        assert path.read_text() == "hello"

    def test_original_file_preserved_on_failure(self, tmp_path):
        path = tmp_path / "data.json"
        path.write_text("original content")

        with patch("youtube_audio_chunker.constants.os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                atomic_write_text(path, "new content")

        assert path.read_text() == "original content"

    def test_temp_file_cleaned_up_on_failure(self, tmp_path):
        path = tmp_path / "data.json"

        with patch("youtube_audio_chunker.constants.os.replace", side_effect=OSError("fail")):
            with pytest.raises(OSError):
                atomic_write_text(path, "content")

        remaining = list(tmp_path.glob("*.tmp"))
        assert remaining == []

    def test_overwrites_existing_file(self, tmp_path):
        path = tmp_path / "data.json"
        path.write_text("old")
        atomic_write_text(path, "new")
        assert path.read_text() == "new"
