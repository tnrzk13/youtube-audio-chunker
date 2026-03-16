"""YouTube Data API v3 search and result caching for topic discovery."""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from youtube_audio_chunker.constants import APP_DIR, atomic_write_text

CACHE_PATH = APP_DIR / "discovery_cache.json"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours

_SEARCH_API = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_API = "https://www.googleapis.com/youtube/v3/videos"


def search_youtube_api(
    query: str,
    api_key: str,
    page_token: str | None = None,
) -> dict:
    params = {
        "q": query,
        "type": "video",
        "part": "snippet",
        "maxResults": "10",
        "videoDuration": "medium",
        "order": "relevance",
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token

    url = f"{_SEARCH_API}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())

    results = [_map_search_item(item) for item in data.get("items", [])]
    _hydrate_durations(results, api_key)
    return {
        "results": results,
        "next_page_token": data.get("nextPageToken"),
    }


def _map_search_item(item: dict) -> dict:
    snippet = item.get("snippet", {})
    video_id = item.get("id", {}).get("videoId", "")
    channel_id = snippet.get("channelId", "")
    return {
        "video_id": video_id,
        "title": snippet.get("title", ""),
        "channel": snippet.get("channelTitle", ""),
        "duration_seconds": 0,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "channel_url": f"https://www.youtube.com/channel/{channel_id}",
    }


def _hydrate_durations(results: list[dict], api_key: str) -> None:
    """Fetch durations from the Videos API and populate results in-place."""
    video_ids = [r["video_id"] for r in results if r["video_id"]]
    if not video_ids:
        return

    params = {
        "id": ",".join(video_ids),
        "part": "contentDetails",
        "key": api_key,
    }
    url = f"{_VIDEOS_API}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())

    duration_by_id = {}
    for item in data.get("items", []):
        raw = item.get("contentDetails", {}).get("duration", "")
        duration_by_id[item["id"]] = parse_iso8601_duration(raw)

    for result in results:
        result["duration_seconds"] = duration_by_id.get(result["video_id"], 0)


def parse_iso8601_duration(raw: str) -> int:
    """Parse an ISO 8601 duration like 'PT1H23M45S' into total seconds."""
    import re

    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", raw)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


# --- Cache management ---


def load_cache(path: Path = CACHE_PATH) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_cache(cache: dict, path: Path = CACHE_PATH) -> None:
    atomic_write_text(path, json.dumps(cache, indent=2))


def get_cached_results(topic_id: str, path: Path = CACHE_PATH) -> dict | None:
    cache = load_cache(path)
    entry = cache.get(topic_id)
    if entry is None:
        return None

    fetched_at = datetime.fromisoformat(entry["fetched_at"])
    age_seconds = (datetime.now(timezone.utc) - fetched_at).total_seconds()
    if age_seconds > CACHE_TTL_SECONDS:
        return None

    return entry


def cache_results(
    topic_id: str,
    results: list[dict],
    next_page_token: str | None,
    path: Path = CACHE_PATH,
) -> None:
    cache = load_cache(path)
    cache[topic_id] = {
        "results": results,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "next_page_token": next_page_token,
    }
    save_cache(cache, path)
