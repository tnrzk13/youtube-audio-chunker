from unittest.mock import patch, MagicMock

from youtube_audio_chunker.garmin import GarminEpisode
from youtube_audio_chunker.sidecar import _handle_get_garmin_status

SIDECAR_MODULE = "youtube_audio_chunker.sidecar"


class TestHandleGetGarminStatus:
    @patch(f"{SIDECAR_MODULE}.get_total_space_bytes", return_value=8_000_000_000)
    @patch(f"{SIDECAR_MODULE}.get_available_space_bytes", return_value=3_500_000_000)
    @patch(f"{SIDECAR_MODULE}.list_garmin_episodes")
    @patch(f"{SIDECAR_MODULE}.find_garmin_mount")
    def test_connected_includes_total_bytes(
        self, mock_mount, mock_list, mock_available, mock_total, tmp_path
    ):
        mock_mount.return_value = tmp_path
        mock_list.return_value = [
            GarminEpisode(
                folder_name="My-Podcast",
                total_size_bytes=500_000_000,
                modified_at=1000.0,
                location="Music",
            )
        ]

        result = _handle_get_garmin_status({})

        assert result["connected"] is True
        assert result["available_bytes"] == 3_500_000_000
        assert result["total_bytes"] == 8_000_000_000
        assert len(result["episodes"]) == 1
        assert result["episodes"][0]["folder_name"] == "My-Podcast"

    @patch(f"{SIDECAR_MODULE}.find_garmin_mount", return_value=None)
    def test_disconnected_includes_total_bytes(self, mock_mount):
        result = _handle_get_garmin_status({})

        assert result["connected"] is False
        assert result["available_bytes"] == 0
        assert result["total_bytes"] == 0
        assert result["episodes"] == []

    @patch(f"{SIDECAR_MODULE}.get_total_space_bytes", return_value=8_000_000_000)
    @patch(f"{SIDECAR_MODULE}.get_available_space_bytes", return_value=8_000_000_000)
    @patch(f"{SIDECAR_MODULE}.list_garmin_episodes", return_value=[])
    @patch(f"{SIDECAR_MODULE}.find_garmin_mount")
    def test_empty_watch_total_equals_available(
        self, mock_mount, mock_list, mock_available, mock_total, tmp_path
    ):
        mock_mount.return_value = tmp_path

        result = _handle_get_garmin_status({})

        assert result["total_bytes"] == 8_000_000_000
        assert result["available_bytes"] == 8_000_000_000
        assert result["episodes"] == []
