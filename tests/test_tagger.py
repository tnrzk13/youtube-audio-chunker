from pathlib import Path
from unittest.mock import patch, MagicMock

from youtube_audio_chunker.constants import ContentType
from youtube_audio_chunker.tagger import tag_single, retag_episode


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
    def test_podcast_sets_tpe2_to_show_name(self, mock_mp3_cls, tmp_path):
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
        tpe2_calls = [c for c in calls if c[0][0] == "TPE2"]
        assert len(tpe2_calls) == 1
        assert "My Podcast" in str(tpe2_calls[0][0][1])

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_audiobook_sets_tpe2_to_show_name(self, mock_mp3_cls, tmp_path):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        audio_path = tmp_path / "chapter.mp3"
        audio_path.write_bytes(b"\x00" * 100)

        tag_single(
            audio_path, title="Chapter 1", artist="Author",
            content_type=ContentType.AUDIOBOOK, album="My Book",
        )

        calls = mock_file.tags.__setitem__.call_args_list
        tpe2_calls = [c for c in calls if c[0][0] == "TPE2"]
        assert len(tpe2_calls) == 1
        assert "My Book" in str(tpe2_calls[0][0][1])

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_music_does_not_set_tpe2(self, mock_mp3_cls, tmp_path):
        mock_file = MagicMock()
        mock_mp3_cls.return_value = mock_file
        mock_file.tags = MagicMock()

        audio_path = tmp_path / "song.mp3"
        audio_path.write_bytes(b"\x00" * 100)

        tag_single(
            audio_path, title="Song", artist="Band",
            content_type=ContentType.MUSIC,
        )

        calls = mock_file.tags.__setitem__.call_args_list
        tpe2_calls = [c for c in calls if c[0][0] == "TPE2"]
        assert len(tpe2_calls) == 0

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
    def test_retag_multi_file_episode(self, mock_mp3_cls, tmp_path):
        """retag_episode calls tag_single on each mp3 in the directory."""
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
        )

        assert mock_mp3_cls.call_count == 3
        assert mock_file.save.call_count == 3

        calls = mock_file.tags.__setitem__.call_args_list
        talb_calls = [c for c in calls if c[0][0] == "TALB"]
        for talb_call in talb_calls:
            assert "The Show" in str(talb_call[0][1])
        # tag_single does not add "Part XX" to titles
        tit2_calls = [c for c in calls if c[0][0] == "TIT2"]
        for tit2_call in tit2_calls:
            assert "Part" not in str(tit2_call[0][1])

    @patch("youtube_audio_chunker.tagger.MP3")
    def test_retag_single_file_episode(self, mock_mp3_cls, tmp_path):
        """retag_episode re-tags a single file using tag_single."""
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
        )

        assert mock_mp3_cls.call_count == 1
        assert mock_file.save.call_count == 1

        calls = mock_file.tags.__setitem__.call_args_list
        talb_calls = [c for c in calls if c[0][0] == "TALB"]
        assert "The Show" in str(talb_calls[0][0][1])
        # Single file uses tag_single logic - no "Part XX" in title
        tit2_calls = [c for c in calls if c[0][0] == "TIT2"]
        assert "Part" not in str(tit2_calls[0][0][1])
