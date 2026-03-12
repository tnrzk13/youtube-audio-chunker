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
    GarminEpisode,
)
from youtube_audio_chunker.errors import GarminError


@pytest.fixture
def fake_garmin(tmp_path):
    """Create a fake Garmin mount point with GARMIN/ marker and MUSIC/ dir."""
    garmin_dir = tmp_path / "GARMIN"
    garmin_dir.mkdir()
    music_dir = tmp_path / "MUSIC"
    music_dir.mkdir()
    return tmp_path


@pytest.fixture
def garmin_with_episodes(fake_garmin):
    """Garmin mount with two existing episode folders."""
    music = fake_garmin / "MUSIC"
    ep1 = music / "Old-Podcast"
    ep1.mkdir()
    (ep1 / "01_Old-Podcast.mp3").write_bytes(b"\x00" * 5000)
    (ep1 / "02_Old-Podcast.mp3").write_bytes(b"\x00" * 5000)

    ep2 = music / "Recent-Podcast"
    ep2.mkdir()
    (ep2 / "01_Recent-Podcast.mp3").write_bytes(b"\x00" * 8000)
    return fake_garmin


class TestFindGarminMount:
    @patch("youtube_audio_chunker.garmin.subprocess.run")
    def test_finds_garmin_by_lsblk_and_marker(self, mock_run, fake_garmin):
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

    @patch("youtube_audio_chunker.garmin.subprocess.run")
    def test_returns_none_when_no_removable_devices(self, mock_run):
        lsblk_output = {"blockdevices": []}
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(lsblk_output)
        )

        result = find_garmin_mount()
        assert result is None

    @patch("youtube_audio_chunker.garmin.subprocess.run")
    def test_returns_none_when_no_garmin_marker(self, mock_run, tmp_path):
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

    @patch("youtube_audio_chunker.garmin.subprocess.run")
    def test_skips_null_mountpoints(self, mock_run):
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

        dest = fake_garmin / "MUSIC" / "My-Podcast"
        assert dest.exists()
        assert len(list(dest.iterdir())) == 2
        assert result == dest

    def test_raises_error_when_insufficient_space(self, fake_garmin, tmp_path):
        source = tmp_path / "src" / "Huge-File"
        source.mkdir(parents=True)
        (source / "chunk.mp3").write_bytes(b"\x00" * 100)

        with patch(
            "youtube_audio_chunker.garmin.get_available_space_bytes", return_value=0
        ):
            with pytest.raises(GarminError, match="space"):
                copy_to_garmin(source, fake_garmin)

    def test_creates_music_dir_if_missing(self, tmp_path):
        garmin_mount = tmp_path / "garmin"
        garmin_mount.mkdir()
        (garmin_mount / "GARMIN").mkdir()
        # No MUSIC dir yet

        source = tmp_path / "src" / "Ep"
        source.mkdir(parents=True)
        (source / "01.mp3").write_bytes(b"\x00" * 10)

        with patch(
            "youtube_audio_chunker.garmin.get_available_space_bytes",
            return_value=1_000_000,
        ):
            result = copy_to_garmin(source, garmin_mount)

        assert (garmin_mount / "MUSIC" / "Ep").exists()


class TestRemoveFromGarmin:
    def test_removes_episode_folder(self, garmin_with_episodes):
        remove_from_garmin("Old-Podcast", garmin_with_episodes)
        assert not (garmin_with_episodes / "MUSIC" / "Old-Podcast").exists()

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
    @patch("youtube_audio_chunker.garmin.shutil.disk_usage")
    def test_returns_free_space(self, mock_usage, fake_garmin):
        mock_usage.return_value = MagicMock(free=500_000_000)
        result = get_available_space_bytes(fake_garmin)
        assert result == 500_000_000
