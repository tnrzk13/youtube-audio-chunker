from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from youtube_audio_chunker.tagger import tag_chunks


@pytest.fixture
def chunk_paths(tmp_path):
    """Create fake MP3 files for tagging tests."""
    paths = []
    for i in range(1, 4):
        p = tmp_path / f"{i:02d}_Test-Video.mp3"
        p.write_bytes(b"\x00" * 100)
        paths.append(p)
    return paths


class TestTagChunks:
    @patch("youtube_audio_chunker.tagger.MP3")
    def test_sets_correct_id3_tags(self, mock_mp3_cls, chunk_paths):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = None
        mock_file.add_tags.side_effect = lambda: setattr(mock_file, "tags", MagicMock())

        tag_chunks(chunk_paths, title="Test Video", total_chunks=3, artist="Channel")

        assert mock_mp3_cls.call_count == 3
        assert mock_file.save.call_count == 3

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_adds_id3_header_when_missing(self, mock_mp3_cls, chunk_paths):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = None
        mock_file.add_tags.side_effect = lambda: setattr(mock_file, "tags", MagicMock())

        tag_chunks(chunk_paths[:1], title="T", total_chunks=1, artist="A")

        mock_file.add_tags.assert_called_once()

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_skips_add_tags_when_already_present(self, mock_mp3_cls, chunk_paths):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        tag_chunks(chunk_paths[:1], title="T", total_chunks=1, artist="A")

        mock_file.add_tags.assert_not_called()

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_track_number_format(self, mock_mp3_cls, chunk_paths):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        tag_chunks(chunk_paths, title="Test", total_chunks=3, artist="A")

        # Collect all tag assignments
        calls = mock_file.tags.__setitem__.call_args_list
        trck_calls = [c for c in calls if c[0][0] == "TRCK"]
        track_values = [str(c[0][1]) for c in trck_calls]
        assert "1/3" in track_values[0]
        assert "2/3" in track_values[1]
        assert "3/3" in track_values[2]

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_title_includes_part_number(self, mock_mp3_cls, chunk_paths):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        tag_chunks(chunk_paths, title="My Podcast", total_chunks=3, artist="Host")

        calls = mock_file.tags.__setitem__.call_args_list
        tit2_calls = [c for c in calls if c[0][0] == "TIT2"]
        title_values = [str(c[0][1]) for c in tit2_calls]
        assert "My Podcast - Part 01" in title_values[0]
        assert "My Podcast - Part 03" in title_values[2]

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_album_set_to_video_title(self, mock_mp3_cls, chunk_paths):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        tag_chunks(chunk_paths[:1], title="Album Name", total_chunks=1, artist="A")

        calls = mock_file.tags.__setitem__.call_args_list
        talb_calls = [c for c in calls if c[0][0] == "TALB"]
        assert "Album Name" in str(talb_calls[0][0][1])

    def test_empty_chunk_list_is_noop(self):
        tag_chunks([], title="T", total_chunks=0, artist="A")
