from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from youtube_audio_chunker.pipeline import process_queue, SyncOptions
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
