from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from youtube_audio_chunker.constants import ContentType
from youtube_audio_chunker.tagger import tag_chunks, tag_single, retag_episode


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

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_album_param_overrides_title_for_talb(self, mock_mp3_cls, chunk_paths):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        tag_chunks(
            chunk_paths, title="Episode 1", total_chunks=3, artist="Host",
            album="My Show",
        )

        calls = mock_file.tags.__setitem__.call_args_list
        talb_calls = [c for c in calls if c[0][0] == "TALB"]
        for talb_call in talb_calls:
            assert "My Show" in str(talb_call[0][1])

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_album_none_falls_back_to_title(self, mock_mp3_cls, chunk_paths):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        tag_chunks(
            chunk_paths[:1], title="Solo Title", total_chunks=1, artist="A",
            album=None,
        )

        calls = mock_file.tags.__setitem__.call_args_list
        talb_calls = [c for c in calls if c[0][0] == "TALB"]
        assert "Solo Title" in str(talb_calls[0][0][1])

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_track_offset_produces_offset_track_numbers(self, mock_mp3_cls, chunk_paths):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        tag_chunks(
            chunk_paths, title="Ep", total_chunks=3, artist="A",
            track_offset=200,
        )

        calls = mock_file.tags.__setitem__.call_args_list
        trck_calls = [c for c in calls if c[0][0] == "TRCK"]
        track_values = [str(c[0][1]) for c in trck_calls]
        assert "201" in track_values[0]
        assert "202" in track_values[1]
        assert "203" in track_values[2]
        # No "/total" denominator when offset is used
        for val in track_values:
            assert "/" not in val


class TestTagSingle:
    @patch("youtube_audio_chunker.tagger.MP3")
    def test_album_param_overrides_title_for_talb(self, mock_mp3_cls, tmp_path):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        audio_path = tmp_path / "episode.mp3"
        audio_path.write_bytes(b"\x00" * 100)

        tag_single(
            audio_path, title="Episode 5", artist="Host",
            content_type=ContentType.PODCAST, album="My Podcast",
        )

        calls = mock_file.tags.__setitem__.call_args_list
        talb_calls = [c for c in calls if c[0][0] == "TALB"]
        assert "My Podcast" in str(talb_calls[0][0][1])

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_album_none_falls_back_to_title(self, mock_mp3_cls, tmp_path):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        audio_path = tmp_path / "episode.mp3"
        audio_path.write_bytes(b"\x00" * 100)

        tag_single(
            audio_path, title="Standalone", artist="A",
            content_type=ContentType.MUSIC,
        )

        calls = mock_file.tags.__setitem__.call_args_list
        talb_calls = [c for c in calls if c[0][0] == "TALB"]
        assert "Standalone" in str(talb_calls[0][0][1])

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_audiobook_sets_genre_to_audiobook(self, mock_mp3_cls, tmp_path):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        audio_path = tmp_path / "chapter.mp3"
        audio_path.write_bytes(b"\x00" * 100)

        tag_single(
            audio_path, title="Chapter 1", artist="Author",
            content_type=ContentType.AUDIOBOOK,
        )

        calls = mock_file.tags.__setitem__.call_args_list
        tcon_calls = [c for c in calls if c[0][0] == "TCON"]
        assert len(tcon_calls) == 1
        assert "Audiobook" in str(tcon_calls[0][0][1])


class TestRetagEpisode:
    @patch("youtube_audio_chunker.tagger.MP3")
    def test_retag_chunked_episode(self, mock_mp3_cls, tmp_path):
        """retag_episode re-tags multiple chunk files when chunk_count > 1."""
        episode_dir = tmp_path / "episode"
        episode_dir.mkdir()
        for i in range(1, 4):
            (episode_dir / f"{i:02d}_Episode-Title.mp3").write_bytes(b"\x00" * 100)

        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        retag_episode(
            episode_dir=episode_dir,
            title="Episode Title",
            artist="Host",
            album="The Show",
            content_type=ContentType.PODCAST,
            chunk_count=3,
        )

        assert mock_mp3_cls.call_count == 3
        assert mock_file.save.call_count == 3

        calls = mock_file.tags.__setitem__.call_args_list
        talb_calls = [c for c in calls if c[0][0] == "TALB"]
        for talb_call in talb_calls:
            assert "The Show" in str(talb_call[0][1])

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_retag_single_file_episode(self, mock_mp3_cls, tmp_path):
        """retag_episode re-tags a single file when chunk_count == 1."""
        episode_dir = tmp_path / "episode"
        episode_dir.mkdir()
        (episode_dir / "Episode-Title.mp3").write_bytes(b"\x00" * 100)

        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        retag_episode(
            episode_dir=episode_dir,
            title="Episode Title",
            artist="Host",
            album="The Show",
            content_type=ContentType.PODCAST,
            chunk_count=1,
        )

        assert mock_mp3_cls.call_count == 1
        assert mock_file.save.call_count == 1

        calls = mock_file.tags.__setitem__.call_args_list
        talb_calls = [c for c in calls if c[0][0] == "TALB"]
        assert "The Show" in str(talb_calls[0][0][1])
        # Single file should use tag_single logic - no "Part XX" in title
        tit2_calls = [c for c in calls if c[0][0] == "TIT2"]
        assert "Part" not in str(tit2_calls[0][0][1])
