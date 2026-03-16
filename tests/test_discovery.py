import json
import time
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import pytest

from youtube_audio_chunker.discovery import (
    search_youtube_api,
    load_cache,
    save_cache,
    get_cached_results,
    cache_results,
    parse_iso8601_duration,
    CACHE_TTL_SECONDS,
)


@pytest.fixture
def cache_path(tmp_app_dir):
    return tmp_app_dir / "discovery_cache.json"


@pytest.fixture
def youtube_api_response():
    return {
        "items": [
            {
                "id": {"videoId": "vid1"},
                "snippet": {
                    "title": "Great Video",
                    "channelTitle": "Cool Channel",
                    "channelId": "UC123",
                },
            },
            {
                "id": {"videoId": "vid2"},
                "snippet": {
                    "title": "Another Video",
                    "channelTitle": "Another Channel",
                    "channelId": "UC456",
                },
            },
        ],
        "nextPageToken": "NEXT_TOKEN",
    }


def _make_mock_urlopen(search_resp, videos_resp=None):
    """Create a mock urlopen that returns search_resp first, then videos_resp."""
    if videos_resp is None:
        videos_resp = {"items": []}
    responses = iter([search_resp, videos_resp])

    def mock_urlopen(url, timeout=None):
        mock = MagicMock()
        mock.read.return_value = json.dumps(next(responses)).encode()
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    return mock_urlopen


class TestSearchYoutubeApi:
    def test_maps_api_response_to_results(self, youtube_api_response):
        mock_urlopen = _make_mock_urlopen(youtube_api_response)

        with patch("youtube_audio_chunker.discovery.urllib.request.urlopen", side_effect=mock_urlopen) as patched:
            result = search_youtube_api("test query", "API_KEY")

        assert len(result["results"]) == 2
        assert result["results"][0]["video_id"] == "vid1"
        assert result["results"][0]["title"] == "Great Video"
        assert result["results"][0]["channel"] == "Cool Channel"
        assert result["results"][0]["url"] == "https://www.youtube.com/watch?v=vid1"
        assert result["results"][0]["channel_url"] == "https://www.youtube.com/channel/UC123"
        assert result["next_page_token"] == "NEXT_TOKEN"

        # Verify first call is the search URL
        search_url = patched.call_args_list[0][0][0]
        assert "q=test+query" in search_url
        assert "key=API_KEY" in search_url
        assert "type=video" in search_url

    def test_passes_page_token(self, youtube_api_response):
        mock_urlopen = _make_mock_urlopen(youtube_api_response)

        with patch("youtube_audio_chunker.discovery.urllib.request.urlopen", side_effect=mock_urlopen) as patched:
            search_youtube_api("query", "KEY", page_token="TOKEN123")

        search_url = patched.call_args_list[0][0][0]
        assert "pageToken=TOKEN123" in search_url

    def test_handles_missing_next_page_token(self):
        mock_urlopen = _make_mock_urlopen({"items": []})

        with patch("youtube_audio_chunker.discovery.urllib.request.urlopen", side_effect=mock_urlopen):
            result = search_youtube_api("query", "KEY")

        assert result["results"] == []
        assert result["next_page_token"] is None


class TestParseIso8601Duration:
    def test_hours_minutes_seconds(self):
        assert parse_iso8601_duration("PT1H23M45S") == 5025

    def test_minutes_seconds(self):
        assert parse_iso8601_duration("PT4M33S") == 273

    def test_minutes_only(self):
        assert parse_iso8601_duration("PT10M") == 600

    def test_seconds_only(self):
        assert parse_iso8601_duration("PT30S") == 30

    def test_hours_only(self):
        assert parse_iso8601_duration("PT2H") == 7200

    def test_hours_and_seconds(self):
        assert parse_iso8601_duration("PT1H5S") == 3605

    def test_empty_returns_zero(self):
        assert parse_iso8601_duration("") == 0

    def test_invalid_returns_zero(self):
        assert parse_iso8601_duration("not a duration") == 0


class TestSearchFetchesDuration:
    def test_search_populates_duration_from_videos_api(self):
        search_resp = {
            "items": [
                {
                    "id": {"videoId": "vid1"},
                    "snippet": {"title": "V1", "channelTitle": "C1", "channelId": "UC1"},
                },
                {
                    "id": {"videoId": "vid2"},
                    "snippet": {"title": "V2", "channelTitle": "C2", "channelId": "UC2"},
                },
            ],
            "nextPageToken": None,
        }
        videos_resp = {
            "items": [
                {"id": "vid1", "contentDetails": {"duration": "PT10M30S"}},
                {"id": "vid2", "contentDetails": {"duration": "PT1H5M"}},
            ],
        }

        call_count = 0

        def mock_urlopen(url, timeout=None):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.read.return_value = json.dumps(search_resp).encode()
            else:
                mock.read.return_value = json.dumps(videos_resp).encode()
            mock.__enter__ = lambda s: s
            mock.__exit__ = MagicMock(return_value=False)
            return mock

        with patch("youtube_audio_chunker.discovery.urllib.request.urlopen", side_effect=mock_urlopen):
            result = search_youtube_api("test", "KEY")

        assert result["results"][0]["duration_seconds"] == 630
        assert result["results"][1]["duration_seconds"] == 3900

    def test_search_handles_missing_video_details(self):
        search_resp = {
            "items": [
                {
                    "id": {"videoId": "vid1"},
                    "snippet": {"title": "V1", "channelTitle": "C1", "channelId": "UC1"},
                },
            ],
        }
        videos_resp = {"items": []}

        call_count = 0

        def mock_urlopen(url, timeout=None):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.read.return_value = json.dumps(search_resp).encode()
            else:
                mock.read.return_value = json.dumps(videos_resp).encode()
            mock.__enter__ = lambda s: s
            mock.__exit__ = MagicMock(return_value=False)
            return mock

        with patch("youtube_audio_chunker.discovery.urllib.request.urlopen", side_effect=mock_urlopen):
            result = search_youtube_api("test", "KEY")

        assert result["results"][0]["duration_seconds"] == 0


class TestCache:
    def test_load_empty_cache(self, cache_path):
        cache = load_cache(cache_path)
        assert cache == {}

    def test_save_and_load_roundtrip(self, cache_path):
        data = {
            "topic-1": {
                "results": [{"video_id": "v1", "title": "Test"}],
                "fetched_at": "2026-03-01T00:00:00+00:00",
                "next_page_token": None,
            }
        }
        save_cache(data, cache_path)
        loaded = load_cache(cache_path)
        assert loaded["topic-1"]["results"][0]["video_id"] == "v1"

    def test_get_cached_results_fresh(self, cache_path):
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "topic-1": {
                "results": [{"video_id": "v1"}],
                "fetched_at": now,
                "next_page_token": "abc",
            }
        }
        save_cache(data, cache_path)

        result = get_cached_results("topic-1", cache_path)
        assert result is not None
        assert result["results"][0]["video_id"] == "v1"

    def test_get_cached_results_stale(self, cache_path):
        old_time = "2020-01-01T00:00:00+00:00"
        data = {
            "topic-1": {
                "results": [{"video_id": "v1"}],
                "fetched_at": old_time,
                "next_page_token": None,
            }
        }
        save_cache(data, cache_path)

        result = get_cached_results("topic-1", cache_path)
        assert result is None

    def test_get_cached_results_missing_topic(self, cache_path):
        save_cache({}, cache_path)
        result = get_cached_results("nonexistent", cache_path)
        assert result is None

    def test_cache_results_writes(self, cache_path):
        save_cache({}, cache_path)
        results = [{"video_id": "v1", "title": "Cached"}]
        cache_results("topic-1", results, "next_tok", cache_path)

        loaded = load_cache(cache_path)
        assert "topic-1" in loaded
        assert loaded["topic-1"]["results"][0]["title"] == "Cached"
        assert loaded["topic-1"]["next_page_token"] == "next_tok"
