from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from youtube_audio_chunker.constants import ContentType
from youtube_audio_chunker.pipeline import process_queue, edit_episode, SyncOptions
from youtube_audio_chunker.library import Library, QueueEntry, DownloadedEpisode
from youtube_audio_chunker.downloader import DownloadResult
from youtube_audio_chunker.garmin import GarminEpisode


@pytest.fixture
def queue_entry():
    return QueueEntry(
        video_id="abc123",
        url="https://youtube.com/watch?v=abc123",
        title="Test Video",
        added_at="2026-03-01T12:00:00+00:00",
    )


@pytest.fixture
def library_with_queue(queue_entry):
    return Library(queue=[queue_entry], downloaded=[])


@pytest.fixture
def download_result(tmp_path):
    audio = tmp_path / "Test-Video.mp3"
    audio.write_bytes(b"\x00" * 1000)
    return DownloadResult(
        video_id="abc123",
        title="Test Video",
        artist="Channel",
        audio_path=audio,
        folder_name="Test-Video",
    )


@pytest.fixture
def chunk_files(tmp_path):
    output = tmp_path / "output" / "Test-Video"
    output.mkdir(parents=True)
    chunks = []
    for i in range(1, 4):
        p = output / f"{i:02d}_Test-Video.mp3"
        p.write_bytes(b"\x00" * 500)
        chunks.append(p)
    return chunks


MODULE = "youtube_audio_chunker.pipeline"


class TestProcessQueue:
    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.tag_chunks")
    @patch(f"{MODULE}.split_audio")
    @patch(f"{MODULE}.download_audio")
    @patch(f"{MODULE}.load_library")
    def test_processes_queued_entries(
        self, mock_load, mock_download, mock_split, mock_tag, mock_save,
        library_with_queue, download_result, chunk_files, tmp_path,
    ):
        mock_load.return_value = library_with_queue
        mock_download.return_value = [download_result]
        mock_split.return_value = chunk_files

        opts = SyncOptions(
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
            no_transfer=True,
        )
        process_queue(opts)

        mock_download.assert_called_once()
        mock_split.assert_called_once()
        mock_tag.assert_called_once()

    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.tag_chunks")
    @patch(f"{MODULE}.split_audio")
    @patch(f"{MODULE}.download_audio")
    @patch(f"{MODULE}.load_library")
    def test_moves_entry_to_downloaded_after_processing(
        self, mock_load, mock_download, mock_split, mock_tag, mock_save,
        library_with_queue, download_result, chunk_files, tmp_path,
    ):
        mock_load.return_value = library_with_queue
        mock_download.return_value = [download_result]
        mock_split.return_value = chunk_files

        opts = SyncOptions(
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
            no_transfer=True,
        )
        process_queue(opts)

        # save_library should have been called with the entry moved to downloaded
        saved_lib = mock_save.call_args[0][0]
        assert len(saved_lib.queue) == 0
        assert len(saved_lib.downloaded) == 1

    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.load_library")
    def test_skips_when_queue_empty(self, mock_load, mock_save, tmp_path):
        mock_load.return_value = Library(queue=[], downloaded=[])

        opts = SyncOptions(
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
            no_transfer=True,
        )
        process_queue(opts)

        # Nothing to save if nothing changed
        mock_save.assert_not_called()

    @patch(f"{MODULE}.copy_to_garmin")
    @patch(f"{MODULE}.find_garmin_mount")
    @patch(f"{MODULE}.get_available_space_bytes")
    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.tag_chunks")
    @patch(f"{MODULE}.split_audio")
    @patch(f"{MODULE}.download_audio")
    @patch(f"{MODULE}.load_library")
    def test_transfers_to_garmin_when_requested(
        self, mock_load, mock_download, mock_split, mock_tag,
        mock_save, mock_space, mock_find, mock_copy,
        library_with_queue, download_result, chunk_files, tmp_path,
    ):
        mock_load.return_value = library_with_queue
        mock_download.return_value = [download_result]
        mock_split.return_value = chunk_files
        mock_find.return_value = tmp_path / "garmin"
        mock_space.return_value = 1_000_000_000
        mock_copy.return_value = tmp_path / "garmin" / "MUSIC" / "Test-Video"

        opts = SyncOptions(
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
            no_transfer=False,
        )
        process_queue(opts)

        mock_find.assert_called_once()
        mock_copy.assert_called_once()

    @patch(f"{MODULE}.find_garmin_mount")
    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.tag_chunks")
    @patch(f"{MODULE}.split_audio")
    @patch(f"{MODULE}.download_audio")
    @patch(f"{MODULE}.load_library")
    def test_skips_transfer_when_garmin_not_found(
        self, mock_load, mock_download, mock_split, mock_tag,
        mock_save, mock_find,
        library_with_queue, download_result, chunk_files, tmp_path,
    ):
        mock_load.return_value = library_with_queue
        mock_download.return_value = [download_result]
        mock_split.return_value = chunk_files
        mock_find.return_value = None

        opts = SyncOptions(
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
            no_transfer=False,
        )
        # Should not raise, just skip transfer
        process_queue(opts)

    @patch(f"{MODULE}.remove_from_garmin")
    @patch(f"{MODULE}.copy_to_garmin")
    @patch(f"{MODULE}.list_garmin_episodes")
    @patch(f"{MODULE}.get_available_space_bytes")
    @patch(f"{MODULE}.find_garmin_mount")
    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.tag_chunks")
    @patch(f"{MODULE}.split_audio")
    @patch(f"{MODULE}.download_audio")
    @patch(f"{MODULE}.load_library")
    def test_auto_cleanup_prompts_user(
        self, mock_load, mock_download, mock_split, mock_tag,
        mock_save, mock_find, mock_space, mock_list, mock_copy,
        mock_remove,
        library_with_queue, download_result, chunk_files, tmp_path,
    ):
        mock_load.return_value = library_with_queue
        mock_download.return_value = [download_result]
        mock_split.return_value = chunk_files
        garmin_mount = tmp_path / "garmin"
        mock_find.return_value = garmin_mount
        # First call: not enough space. After removal: enough space.
        mock_space.side_effect = [100, 1_000_000_000]
        mock_list.return_value = [
            GarminEpisode(
                folder_name="Old-Episode",
                total_size_bytes=50_000,
                modified_at=1000.0,
            )
        ]
        mock_copy.return_value = garmin_mount / "MUSIC" / "Test-Video"

        opts = SyncOptions(
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
            no_transfer=False,
        )

        with patch("builtins.input", return_value="y"):
            process_queue(opts)

        mock_remove.assert_called_once_with("Old-Episode", garmin_mount)
        mock_copy.assert_called_once()

    @patch(f"{MODULE}.copy_to_garmin")
    @patch(f"{MODULE}.list_garmin_episodes")
    @patch(f"{MODULE}.get_available_space_bytes")
    @patch(f"{MODULE}.find_garmin_mount")
    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.tag_chunks")
    @patch(f"{MODULE}.split_audio")
    @patch(f"{MODULE}.download_audio")
    @patch(f"{MODULE}.load_library")
    def test_auto_cleanup_skips_transfer_when_declined(
        self, mock_load, mock_download, mock_split, mock_tag,
        mock_save, mock_find, mock_space, mock_list, mock_copy,
        library_with_queue, download_result, chunk_files, tmp_path,
    ):
        mock_load.return_value = library_with_queue
        mock_download.return_value = [download_result]
        mock_split.return_value = chunk_files
        mock_find.return_value = tmp_path / "garmin"
        mock_space.return_value = 100  # Always too small
        mock_list.return_value = [
            GarminEpisode(folder_name="Ep", total_size_bytes=50, modified_at=1.0)
        ]

        opts = SyncOptions(
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
            no_transfer=False,
        )

        with patch("builtins.input", return_value="n"):
            process_queue(opts)

        mock_copy.assert_not_called()


class TestShowNameFlow:
    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.tag_chunks")
    @patch(f"{MODULE}.split_audio")
    @patch(f"{MODULE}.download_audio")
    @patch(f"{MODULE}.load_library")
    def test_show_name_flows_from_download_to_library(
        self, mock_load, mock_download, mock_split, mock_tag, mock_save,
        tmp_path,
    ):
        entry = QueueEntry(
            video_id="abc123",
            url="https://youtube.com/watch?v=abc123",
            title="Test Video",
            added_at="2026-03-01T12:00:00+00:00",
        )
        library = Library(queue=[entry], downloaded=[])
        mock_load.return_value = library

        audio = tmp_path / "Test-Video.mp3"
        audio.write_bytes(b"\x00" * 1000)
        dl = DownloadResult(
            video_id="abc123", title="Test Video", artist="Channel",
            audio_path=audio, folder_name="Test-Video", channel="The Channel",
        )
        mock_download.return_value = [dl]

        output = tmp_path / "output" / "Test-Video"
        output.mkdir(parents=True)
        chunks = [output / f"{i:02d}_Test-Video.mp3" for i in range(1, 4)]
        for c in chunks:
            c.write_bytes(b"\x00" * 500)
        mock_split.return_value = chunks

        opts = SyncOptions(
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
            no_transfer=True,
        )
        process_queue(opts)

        saved_lib = mock_save.call_args[0][0]
        ep = saved_lib.downloaded[0]
        assert ep.show_name == "The Channel"
        assert ep.artist == "Channel"

    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.tag_chunks")
    @patch(f"{MODULE}.split_audio")
    @patch(f"{MODULE}.download_audio")
    @patch(f"{MODULE}.load_library")
    def test_queue_entry_show_name_takes_precedence(
        self, mock_load, mock_download, mock_split, mock_tag, mock_save,
        tmp_path,
    ):
        entry = QueueEntry(
            video_id="abc123",
            url="https://youtube.com/watch?v=abc123",
            title="Test Video",
            added_at="2026-03-01T12:00:00+00:00",
            show_name="My Custom Show",
        )
        library = Library(queue=[entry], downloaded=[])
        mock_load.return_value = library

        audio = tmp_path / "Test-Video.mp3"
        audio.write_bytes(b"\x00" * 1000)
        dl = DownloadResult(
            video_id="abc123", title="Test Video", artist="Channel",
            audio_path=audio, folder_name="Test-Video", channel="The Channel",
        )
        mock_download.return_value = [dl]

        output = tmp_path / "output" / "Test-Video"
        output.mkdir(parents=True)
        chunks = [output / f"{i:02d}_Test-Video.mp3" for i in range(1, 4)]
        for c in chunks:
            c.write_bytes(b"\x00" * 500)
        mock_split.return_value = chunks

        opts = SyncOptions(
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
            no_transfer=True,
        )
        process_queue(opts)

        saved_lib = mock_save.call_args[0][0]
        ep = saved_lib.downloaded[0]
        assert ep.show_name == "My Custom Show"

    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.tag_chunks")
    @patch(f"{MODULE}.split_audio")
    @patch(f"{MODULE}.download_audio")
    @patch(f"{MODULE}.load_library")
    def test_tag_chunks_receives_album_and_track_offset(
        self, mock_load, mock_download, mock_split, mock_tag, mock_save,
        tmp_path,
    ):
        """Music episodes with a show_name should pass album and track_offset to tagger."""
        # Existing downloaded music episode with same show
        existing_ep = DownloadedEpisode(
            video_id="prev", url="u", title="Previous",
            folder_name="Previous", chunk_count=5,
            total_size_bytes=5000, downloaded_at="t", synced_at=None,
            content_type="music", show_name="The Channel",
        )
        entry = QueueEntry(
            video_id="abc123",
            url="https://youtube.com/watch?v=abc123",
            title="Test Video",
            added_at="2026-03-01T12:00:00+00:00",
        )
        library = Library(queue=[entry], downloaded=[existing_ep])
        mock_load.return_value = library

        audio = tmp_path / "Test-Video.mp3"
        audio.write_bytes(b"\x00" * 1000)
        dl = DownloadResult(
            video_id="abc123", title="Test Video", artist="Channel",
            audio_path=audio, folder_name="Test-Video", channel="The Channel",
        )
        mock_download.return_value = [dl]

        output = tmp_path / "output" / "Test-Video"
        output.mkdir(parents=True)
        chunks = [output / f"{i:02d}_Test-Video.mp3" for i in range(1, 4)]
        for c in chunks:
            c.write_bytes(b"\x00" * 500)
        mock_split.return_value = chunks

        opts = SyncOptions(
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
            no_transfer=True,
        )
        process_queue(opts)

        tag_call = mock_tag.call_args
        assert tag_call.kwargs.get("album") == "The Channel"
        assert tag_call.kwargs.get("track_offset") == 100


class TestEditEpisode:
    @patch(f"{MODULE}.retag_episode")
    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.load_library")
    def test_updates_library_and_retags(
        self, mock_load, mock_save, mock_retag, tmp_path,
    ):
        ep = DownloadedEpisode(
            video_id="abc123", url="u", title="Old Title",
            folder_name="Old-Title", chunk_count=3,
            total_size_bytes=5000, downloaded_at="t", synced_at=None,
            content_type="music", show_name="Old Show",
        )
        library = Library(queue=[], downloaded=[ep])
        mock_load.return_value = library

        episode_dir = tmp_path / "output" / "Old-Title"
        episode_dir.mkdir(parents=True)
        for i in range(1, 4):
            (episode_dir / f"{i:02d}_Old-Title.mp3").write_bytes(b"\x00" * 100)

        result = edit_episode(
            "abc123",
            {"show_name": "New Show", "title": "New Title"},
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
        )

        assert result["show_name"] == "New Show"
        assert result["title"] == "New Title"
        mock_save.assert_called_once()
        mock_retag.assert_called_once()

    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.load_library")
    def test_returns_none_for_unknown_video(self, mock_load, mock_save, tmp_path):
        library = Library(queue=[], downloaded=[])
        mock_load.return_value = library

        result = edit_episode(
            "unknown",
            {"show_name": "X"},
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
        )

        assert result is None
        mock_save.assert_not_called()


class TestResyncEpisode:
    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.mark_synced")
    @patch(f"{MODULE}.copy_to_garmin")
    @patch(f"{MODULE}.remove_from_garmin")
    @patch(f"{MODULE}.find_garmin_mount")
    @patch(f"{MODULE}.load_library")
    def test_removes_old_and_recopies(
        self, mock_load, mock_find, mock_remove, mock_copy, mock_mark,
        mock_save, tmp_path,
    ):
        ep = DownloadedEpisode(
            video_id="abc123", url="u", title="My Episode",
            folder_name="My-Episode", chunk_count=3,
            total_size_bytes=5000, downloaded_at="t",
            synced_at="2026-03-01T12:00:00+00:00",
            content_type="music", show_name="My Show",
        )
        library = Library(queue=[], downloaded=[ep])
        mock_load.return_value = library

        garmin_mount = tmp_path / "garmin"
        garmin_mount.mkdir()
        mock_find.return_value = garmin_mount

        episode_dir = tmp_path / "output" / "My-Episode"
        episode_dir.mkdir(parents=True)
        (episode_dir / "01_My-Episode.mp3").write_bytes(b"\x00" * 100)

        from youtube_audio_chunker.pipeline import resync_episode
        result = resync_episode(
            "abc123",
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
        )

        mock_remove.assert_called_once_with("My-Episode", garmin_mount)
        mock_copy.assert_called_once_with(
            episode_dir, garmin_mount, ContentType.MUSIC,
        )
        mock_mark.assert_called_once()
        mock_save.assert_called_once()
        assert result["video_id"] == "abc123"

    @patch(f"{MODULE}.find_garmin_mount", return_value=None)
    @patch(f"{MODULE}.load_library")
    def test_raises_when_garmin_not_connected(
        self, mock_load, mock_find, tmp_path,
    ):
        ep = DownloadedEpisode(
            video_id="abc123", url="u", title="My Episode",
            folder_name="My-Episode", chunk_count=3,
            total_size_bytes=5000, downloaded_at="t",
            synced_at="2026-03-01T12:00:00+00:00",
            content_type="music",
        )
        library = Library(queue=[], downloaded=[ep])
        mock_load.return_value = library

        from youtube_audio_chunker.pipeline import resync_episode
        from youtube_audio_chunker.errors import GarminError

        with pytest.raises(GarminError, match="No Garmin watch detected"):
            resync_episode(
                "abc123",
                library_path=tmp_path / "library.json",
                output_dir=tmp_path / "output",
            )

    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.mark_synced")
    @patch(f"{MODULE}.copy_to_garmin")
    @patch(f"{MODULE}.remove_from_garmin")
    @patch(f"{MODULE}.find_garmin_mount")
    @patch(f"{MODULE}.load_library")
    def test_handles_content_type_change(
        self, mock_load, mock_find, mock_remove, mock_copy, mock_mark,
        mock_save, tmp_path,
    ):
        """After editing content_type from podcast to music, resync should
        remove from old folder (Podcasts/) and copy to new (Music/)."""
        ep = DownloadedEpisode(
            video_id="abc123", url="u", title="My Episode",
            folder_name="My-Episode", chunk_count=1,
            total_size_bytes=5000, downloaded_at="t",
            synced_at="2026-03-01T12:00:00+00:00",
            content_type="music",  # already edited to music
        )
        library = Library(queue=[], downloaded=[ep])
        mock_load.return_value = library

        garmin_mount = tmp_path / "garmin"
        garmin_mount.mkdir()
        mock_find.return_value = garmin_mount

        episode_dir = tmp_path / "output" / "My-Episode"
        episode_dir.mkdir(parents=True)
        (episode_dir / "My-Episode.mp3").write_bytes(b"\x00" * 100)

        from youtube_audio_chunker.pipeline import resync_episode
        resync_episode(
            "abc123",
            library_path=tmp_path / "library.json",
            output_dir=tmp_path / "output",
        )

        # remove_from_garmin searches all dirs, so it finds old location
        mock_remove.assert_called_once_with("My-Episode", garmin_mount)
        # copy uses the current content_type
        mock_copy.assert_called_once_with(
            episode_dir, garmin_mount, ContentType.MUSIC,
        )


class TestEditQueueEntry:
    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.load_library")
    def test_updates_queue_entry_fields(self, mock_load, mock_save, tmp_path):
        entry = QueueEntry(
            video_id="abc123",
            url="https://youtube.com/watch?v=abc123",
            title="Original Title",
            added_at="2026-03-01T12:00:00+00:00",
            content_type="music",
            show_name="Old Show",
        )
        library = Library(queue=[entry], downloaded=[])
        mock_load.return_value = library

        from youtube_audio_chunker.pipeline import edit_queue_entry
        result = edit_queue_entry(
            "abc123",
            {"show_name": "New Show", "title": "New Title", "content_type": "podcast"},
            library_path=tmp_path / "library.json",
        )

        assert result["show_name"] == "New Show"
        assert result["title"] == "New Title"
        assert result["content_type"] == "podcast"
        mock_save.assert_called_once()

    @patch(f"{MODULE}.save_library")
    @patch(f"{MODULE}.load_library")
    def test_returns_none_for_unknown_video(self, mock_load, mock_save, tmp_path):
        library = Library(queue=[], downloaded=[])
        mock_load.return_value = library

        from youtube_audio_chunker.pipeline import edit_queue_entry
        result = edit_queue_entry(
            "unknown",
            {"show_name": "X"},
            library_path=tmp_path / "library.json",
        )

        assert result is None
        mock_save.assert_not_called()
