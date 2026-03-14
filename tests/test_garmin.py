import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from youtube_audio_chunker.garmin import (
    find_garmin_mount,
    copy_to_garmin,
    remove_from_garmin,
    list_garmin_episodes,
    get_available_space_bytes,
    get_total_space_bytes,
    GarminEpisode,
)
from youtube_audio_chunker.errors import GarminError

MODULE = "youtube_audio_chunker.garmin"


@pytest.fixture
def fake_garmin(tmp_path):
    """Create a fake Garmin mount point with GARMIN/ marker and Music/ dir."""
    garmin_dir = tmp_path / "GARMIN"
    garmin_dir.mkdir()
    music_dir = tmp_path / "Music"
    music_dir.mkdir()
    return tmp_path


@pytest.fixture
def garmin_with_episodes(fake_garmin):
    """Garmin mount with two existing episode folders."""
    music = fake_garmin / "Music"
    ep1 = music / "Old-Podcast"
    ep1.mkdir()
    (ep1 / "01_Old-Podcast.mp3").write_bytes(b"\x00" * 5000)
    (ep1 / "02_Old-Podcast.mp3").write_bytes(b"\x00" * 5000)

    ep2 = music / "Recent-Podcast"
    ep2.mkdir()
    (ep2 / "01_Recent-Podcast.mp3").write_bytes(b"\x00" * 8000)
    return fake_garmin


def _no_mtp(monkeypatch):
    """Ensure MTP detection returns nothing during tests."""
    monkeypatch.setattr(f"{MODULE}._get_mtp_mountpoints", lambda: [])


class TestFindGarminMount:
    @patch(f"{MODULE}.subprocess.run")
    def test_finds_garmin_by_lsblk_and_marker(self, mock_run, fake_garmin, monkeypatch):
        _no_mtp(monkeypatch)
        lsblk_output = {
            "blockdevices": [
                {
                    "name": "sda",
                    "rm": True,
                    "mountpoints": [str(fake_garmin)],
                }
            ]
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(lsblk_output)
        )

        result = find_garmin_mount()
        assert result == fake_garmin

    @patch(f"{MODULE}.subprocess.run")
    def test_finds_garmin_via_mtp(self, mock_run, tmp_path, monkeypatch):
        # MTP mount with Internal Storage/GARMIN marker
        internal = tmp_path / "Internal Storage"
        internal.mkdir()
        (internal / "GARMIN").mkdir()
        (internal / "Music").mkdir()

        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps({"blockdevices": []})
        )
        monkeypatch.setattr(f"{MODULE}._get_mtp_mountpoints", lambda: [tmp_path])

        result = find_garmin_mount()
        assert result == internal

    @patch(f"{MODULE}.subprocess.run")
    def test_returns_none_when_no_removable_devices(self, mock_run, monkeypatch):
        _no_mtp(monkeypatch)
        lsblk_output = {"blockdevices": []}
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(lsblk_output)
        )

        result = find_garmin_mount()
        assert result is None

    @patch(f"{MODULE}.subprocess.run")
    def test_returns_none_when_no_garmin_marker(self, mock_run, tmp_path, monkeypatch):
        _no_mtp(monkeypatch)
        # Removable but no GARMIN/ directory
        lsblk_output = {
            "blockdevices": [
                {"name": "sda", "rm": True, "mountpoints": [str(tmp_path)]}
            ]
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(lsblk_output)
        )

        result = find_garmin_mount()
        assert result is None

    @patch(f"{MODULE}.subprocess.run")
    def test_skips_null_mountpoints(self, mock_run, monkeypatch):
        _no_mtp(monkeypatch)
        lsblk_output = {
            "blockdevices": [
                {"name": "sda", "rm": True, "mountpoints": [None]}
            ]
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(lsblk_output)
        )

        result = find_garmin_mount()
        assert result is None


class TestCopyToGarmin:
    def test_copies_episode_folder(self, fake_garmin, tmp_path):
        source = tmp_path / "src" / "My-Podcast"
        source.mkdir(parents=True)
        (source / "01_My-Podcast.mp3").write_bytes(b"\x00" * 100)
        (source / "02_My-Podcast.mp3").write_bytes(b"\x00" * 100)

        result = copy_to_garmin(source, fake_garmin)

        dest = fake_garmin / "Music" / "My-Podcast"
        assert dest.exists()
        assert len(list(dest.iterdir())) == 2
        assert result == dest

    def test_single_file_uses_folder_name(self, fake_garmin, tmp_path):
        """Single-file episode should use the source dir name on watch,
        not the original mp3 filename, so folder_name cross-reference works."""
        source = tmp_path / "src" / "My-Cool-Title"
        source.mkdir(parents=True)
        # yt-dlp often creates filenames with spaces, while the episode
        # folder uses the sanitized name (spaces -> dashes)
        (source / "My Cool Title.mp3").write_bytes(b"\x00" * 100)

        copy_to_garmin(source, fake_garmin)

        assert (fake_garmin / "Music" / "My-Cool-Title.mp3").exists()
        assert not (fake_garmin / "Music" / "My Cool Title.mp3").exists()

    def test_single_file_roundtrip_folder_name(self, fake_garmin, tmp_path):
        """After copying a single-file episode, list_garmin_episodes should
        return a folder_name matching the source directory name."""
        source = tmp_path / "src" / "My-Cool-Title"
        source.mkdir(parents=True)
        (source / "My Cool Title.mp3").write_bytes(b"\x00" * 100)

        copy_to_garmin(source, fake_garmin)
        episodes = list_garmin_episodes(fake_garmin)

        names = {e.folder_name for e in episodes}
        assert "My-Cool-Title" in names

    def test_raises_error_when_insufficient_space(self, fake_garmin, tmp_path):
        source = tmp_path / "src" / "Huge-File"
        source.mkdir(parents=True)
        (source / "chunk.mp3").write_bytes(b"\x00" * 100)

        with patch(
            f"{MODULE}.get_available_space_bytes", return_value=0
        ):
            with pytest.raises(GarminError, match="space"):
                copy_to_garmin(source, fake_garmin)

    def test_creates_music_dir_if_missing(self, tmp_path):
        garmin_mount = tmp_path / "garmin"
        garmin_mount.mkdir()
        (garmin_mount / "GARMIN").mkdir()
        # No Music dir yet

        source = tmp_path / "src" / "Ep"
        source.mkdir(parents=True)
        (source / "01.mp3").write_bytes(b"\x00" * 10)

        with patch(
            f"{MODULE}.get_available_space_bytes",
            return_value=1_000_000,
        ):
            copy_to_garmin(source, garmin_mount)

        # Single file uses folder name, not original filename
        assert (garmin_mount / "Music" / "Ep.mp3").exists()


class TestRemoveFromGarmin:
    def test_removes_episode_folder(self, garmin_with_episodes):
        remove_from_garmin("Old-Podcast", garmin_with_episodes)
        assert not (garmin_with_episodes / "Music" / "Old-Podcast").exists()

    def test_raises_error_for_missing_folder(self, fake_garmin):
        with pytest.raises(GarminError, match="not found"):
            remove_from_garmin("Nonexistent", fake_garmin)


class TestListGarminEpisodes:
    def test_lists_episodes_with_size(self, garmin_with_episodes):
        episodes = list_garmin_episodes(garmin_with_episodes)
        assert len(episodes) == 2
        names = {e.folder_name for e in episodes}
        assert "Old-Podcast" in names
        assert "Recent-Podcast" in names

    def test_calculates_total_size(self, garmin_with_episodes):
        episodes = list_garmin_episodes(garmin_with_episodes)
        old = next(e for e in episodes if e.folder_name == "Old-Podcast")
        assert old.total_size_bytes == 10000

    def test_returns_empty_list_when_no_episodes(self, fake_garmin):
        episodes = list_garmin_episodes(fake_garmin)
        assert episodes == []


class TestGetAvailableSpaceBytes:
    @patch(f"{MODULE}.shutil.disk_usage")
    def test_returns_free_space(self, mock_usage, fake_garmin):
        mock_usage.return_value = MagicMock(free=500_000_000)
        result = get_available_space_bytes(fake_garmin)
        assert result == 500_000_000


class TestGetTotalSpaceBytes:
    @patch(f"{MODULE}.shutil.disk_usage")
    def test_returns_total_space(self, mock_usage, fake_garmin):
        mock_usage.return_value = MagicMock(total=8_000_000_000)
        result = get_total_space_bytes(fake_garmin)
        assert result == 8_000_000_000
