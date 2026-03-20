"""JSON-RPC 2.0 stdio bridge for the Tauri GUI sidecar."""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from youtube_audio_chunker.auth import (
    connect_cookies,
    detect_browser,
    disconnect as auth_disconnect,
    get_auth_status,
)
from youtube_audio_chunker.constants import APP_DIR, ContentType, OUTPUT_DIR
from youtube_audio_chunker.downloader import (
    extract_metadata,
    list_channel_videos,
    list_feed,
    list_playlist_videos,
    list_user_playlists,
    search_youtube,
)
from youtube_audio_chunker.errors import (
    ChunkerError,
    DependencyError,
    DownloadError,
    GarminError,
)
from youtube_audio_chunker.garmin import (
    copy_to_garmin,
    dir_size_bytes,
    find_garmin_mount,
    get_available_space_bytes,
    get_total_space_bytes,
    list_garmin_episodes,
    remove_from_garmin,
)
from youtube_audio_chunker.library import (
    add_to_queue,
    list_shows,
    load_library,
    mark_synced,
    remove_episode,
    remove_episodes,
    rename_show,
    save_library,
)
from youtube_audio_chunker.pipeline import (
    PipelineCallbacks,
    SyncOptions,
    edit_episode,
    edit_queue_entry,
    process_queue,
    resync_episode,
    transfer_unsynced,
)
from youtube_audio_chunker.topics import (
    add_topic,
    delete_topic,
    dismiss_video,
    get_excluded_video_ids,
    load_topics,
    record_video_history,
    save_topics,
    update_topic,
)
from youtube_audio_chunker.discovery import (
    cache_results,
    get_cached_results,
    search_youtube_api,
)
from youtube_audio_chunker.settings import (
    _ENV_TO_SETTINGS,
    load_settings as _load_settings,
    save_settings,
    settings_path as _settings_path,
)
from youtube_audio_chunker.topic_extractor import extract_topics_from_titles

ERROR_CODES = {
    DependencyError: -32001,
    DownloadError: -32002,
    GarminError: -32004,
}

PARSE_ERROR = -32700

log = logging.getLogger(__name__)
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603

_cancel_event = threading.Event()
_stdout_lock = threading.Lock()
_library_lock = threading.Lock()
_topics_lock = threading.Lock()

# Methods that run in a background thread so the main loop stays responsive
_ASYNC_METHODS = {
    "process_queue", "transfer_unsynced", "transfer_episode", "resync_episode",
    "list_subscriptions", "list_home_feed", "list_liked_videos",
    "list_playlists", "list_playlist_videos",
    "connect_cookies", "detect_browser",
    "extract_topics", "search_topic",
}


def _load_dotenv() -> None:
    """Load .env file from common locations into os.environ (no dependency)."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[2] / ".env",  # project root
    ]
    for path in candidates:
        if path.is_file():
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if not os.environ.get(key):
                    os.environ[key] = value
            break


def main() -> None:
    """Read JSON-RPC requests from stdin, dispatch, write responses to stdout."""
    global _confirm_result
    _load_dotenv()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            _write_error(None, PARSE_ERROR, f"Parse error: {exc}")
            continue

        # Check if this is a confirmation response for a pending reverse request
        if (
            _confirm_request_id is not None
            and request.get("id") == _confirm_request_id
            and "result" in request
        ):
            _confirm_result = request["result"]
            _confirm_event.set()
            continue

        _dispatch(request)


def _dispatch(request: dict) -> None:
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    handler = _METHODS.get(method)
    if handler is None:
        if request_id is not None:
            _write_error(request_id, METHOD_NOT_FOUND, f"Unknown method: {method}")
        return

    if method in _ASYNC_METHODS:
        _cancel_event.clear()
        thread = threading.Thread(
            target=_run_handler, args=(handler, params, request_id)
        )
        thread.daemon = True
        thread.start()
    else:
        _run_handler(handler, params, request_id)


def _run_handler(handler, params: dict, request_id: Any) -> None:
    try:
        result = handler(params)
        if request_id is not None:
            _write_result(request_id, result)
    except ChunkerError as exc:
        code = ERROR_CODES.get(type(exc), INTERNAL_ERROR)
        if request_id is not None:
            _write_error(request_id, code, str(exc))
    except Exception:
        log.exception("Unhandled error in handler")
        if request_id is not None:
            _write_error(request_id, INTERNAL_ERROR, "Internal error")


def _is_cancelled() -> bool:
    return _cancel_event.is_set()


# --- Cancel ---


def _handle_cancel(params: dict) -> dict:
    _cancel_event.set()
    return {"cancelled": True}


# --- Read methods ---


def _handle_get_library(params: dict) -> dict:
    with _library_lock:
        library = load_library()
        return {
            "queue": [asdict(e) for e in library.queue],
            "downloaded": [asdict(e) for e in library.downloaded],
        }


def _handle_get_garmin_status(params: dict) -> dict:
    mount = find_garmin_mount()
    if mount is None:
        return {"connected": False, "episodes": [], "available_bytes": 0, "total_bytes": 0}

    episodes = list_garmin_episodes(mount)
    available = get_available_space_bytes(mount)
    total = get_total_space_bytes(mount)
    return {
        "connected": True,
        "episodes": [asdict(e) for e in episodes],
        "available_bytes": available,
        "total_bytes": total,
    }


def _handle_list_shows(params: dict) -> dict:
    with _library_lock:
        library = load_library()
        return {"shows": list_shows(library)}


def _handle_rename_show(params: dict) -> dict:
    old_name = params["old_name"]
    new_name = params["new_name"]
    with _library_lock:
        library = load_library()
        count = rename_show(library, old_name, new_name)
        save_library(library)
    return {"renamed": count}


def _handle_edit_episode(params: dict) -> dict:
    video_id = params["video_id"]
    updates = params.get("updates", {})
    with _library_lock:
        result = edit_episode(video_id, updates)
    if result is None:
        raise ChunkerError(f"Episode not found: {video_id}")
    return result


def _handle_resync_episode(params: dict) -> dict:
    video_id = params["video_id"]
    with _library_lock:
        result = resync_episode(video_id)
    if result is None:
        raise ChunkerError(f"Episode not found: {video_id}")
    return result


def _handle_edit_queue_entry(params: dict) -> dict:
    video_id = params["video_id"]
    updates = params.get("updates", {})
    with _library_lock:
        result = edit_queue_entry(video_id, updates)
    if result is None:
        raise ChunkerError(f"Queue entry not found: {video_id}")
    return result


# --- Search methods ---


def _handle_search_youtube(params: dict) -> dict:
    query = params.get("query", "")
    if not query.strip():
        return {"results": []}
    offset = params.get("offset", 0)
    return {"results": search_youtube(query, offset=offset)}


def _handle_list_channel_videos(params: dict) -> dict:
    channel_url = params.get("channel_url", "")
    if not channel_url.strip():
        raise ValueError("channel_url is required")
    offset = params.get("offset", 0)
    return list_channel_videos(channel_url, offset=offset)


# --- Mutation methods ---


def _handle_add_to_queue(params: dict) -> dict:
    urls = params.get("urls", [])
    content_type = params.get("content_type", ContentType.MUSIC.value)
    show_name = params.get("show_name")
    added = []
    added_ids = []
    skipped = []

    with _library_lock:
        library = load_library()
        for url in urls:
            entries = extract_metadata(url)
            for entry in entries:
                was_added = add_to_queue(
                    library,
                    url=url,
                    title=entry["title"],
                    video_id=entry["id"],
                    content_type=content_type,
                    show_name=show_name,
                    duration_seconds=entry.get("duration", 0),
                )
                if was_added:
                    added.append(entry["title"])
                    added_ids.append(entry["id"])
                else:
                    skipped.append(entry["title"])
        save_library(library)

    # Topic operations acquire their own lock
    if added_ids:
        _record_history_for_ids(added_ids)
        _maybe_auto_extract_topics(library)

    return {"added": added, "skipped": skipped}


def _handle_remove_episode(params: dict) -> dict:
    video_id = params["video_id"]
    with _library_lock:
        library = load_library()
        episode_dir = OUTPUT_DIR / _find_folder_name(library, video_id)
        remove_episode(library, video_id)
        save_library(library)

    _record_history_for_ids([video_id])

    if episode_dir.exists():
        shutil.rmtree(episode_dir)

    return {"removed": video_id}


def _handle_remove_from_garmin(params: dict) -> dict:
    folder_name = params["folder_name"]
    mount = find_garmin_mount()
    if mount is None:
        raise GarminError("No Garmin watch detected.")
    remove_from_garmin(folder_name, mount)
    return {"removed": folder_name}


def _handle_remove_episodes(params: dict) -> dict:
    video_ids = params["video_ids"]
    with _library_lock:
        library = load_library()
        folder_names = [
            ep.folder_name
            for ep in library.downloaded
            if ep.video_id in set(video_ids)
        ]
        remove_episodes(library, set(video_ids))
        save_library(library)

    _record_history_for_ids(video_ids)

    failed = []
    for folder_name in folder_names:
        episode_dir = OUTPUT_DIR / folder_name
        if episode_dir.exists():
            try:
                shutil.rmtree(episode_dir)
            except OSError as exc:
                failed.append({"folder_name": folder_name, "error": str(exc)})

    return {"removed": video_ids, "failed": failed}


def _handle_remove_from_garmin_batch(params: dict) -> dict:
    folder_names = params["folder_names"]
    mount = find_garmin_mount()
    if mount is None:
        raise GarminError("No Garmin watch detected.")

    removed = []
    failed = []
    for name in folder_names:
        try:
            remove_from_garmin(name, mount)
            removed.append(name)
        except Exception as exc:
            failed.append({"folder_name": name, "error": str(exc)})

    return {"removed": removed, "failed": failed}


# --- Process queue with progress ---


def _handle_process_queue(params: dict) -> dict:
    options = SyncOptions(
        artist=params.get("artist"),
        no_transfer=params.get("no_transfer", False),
    )
    callbacks = PipelineCallbacks(
        on_progress=_notify_progress,
        on_confirm_removal=_request_confirm_removal,
        is_cancelled=_is_cancelled,
    )
    with _library_lock:
        return process_queue(options, callbacks)


# --- Transfer single episode ---


def _handle_transfer_episode(params: dict) -> dict:
    video_id = params["video_id"]
    with _library_lock:
        library = load_library()
        ep = next((e for e in library.downloaded if e.video_id == video_id), None)
        if ep is None:
            raise ChunkerError(f"Episode not found: {video_id}")

        garmin_mount = find_garmin_mount()
        if garmin_mount is None:
            raise GarminError("No Garmin watch detected.")

        episode_dir = OUTPUT_DIR / ep.folder_name
        if not episode_dir.exists():
            raise ChunkerError(f"Files not found: {ep.title}")

        content_type = ContentType(ep.content_type)
        needed = dir_size_bytes(episode_dir)
        available = get_available_space_bytes(garmin_mount)

        if needed > available:
            raise GarminError(
                f"Not enough space on watch. Need {needed // 1_000_000} MB, "
                f"have {available // 1_000_000} MB free."
            )

        _notify_progress("transfer", ep.video_id, f"Transferring: {ep.title}", 0)
        copy_to_garmin(episode_dir, garmin_mount, content_type)
        mark_synced(library, ep.video_id)
        save_library(library)
        _notify_progress("transfer", ep.video_id, f"Synced: {ep.title}", 100)

    return {"transferred": video_id}


# --- Transfer unsynced ---


def _handle_transfer_unsynced(params: dict) -> dict:
    callbacks = PipelineCallbacks(
        on_progress=_notify_progress,
        on_confirm_removal=_request_confirm_removal,
        is_cancelled=_is_cancelled,
    )
    return transfer_unsynced(callbacks=callbacks)


# --- Settings ---


def _handle_get_settings(params: dict) -> dict:
    settings_path = _settings_path()
    saved = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    env_keys = [
        settings_key
        for env_key, settings_key in _ENV_TO_SETTINGS.items()
        if os.environ.get(env_key) and settings_key not in saved
    ]
    merged = _load_settings()
    merged["_env_keys"] = env_keys
    return merged


def _handle_save_settings(params: dict) -> dict:
    settings = params.get("settings", {})
    save_settings(settings)
    return {"saved": True}


# --- Helpers ---


def _find_folder_name(library: Any, video_id: str) -> str:
    for ep in library.downloaded:
        if ep.video_id == video_id:
            return ep.folder_name
    for entry in library.queue:
        if entry.video_id == video_id:
            return ""
    return ""


# --- JSON-RPC I/O ---


def _write_result(request_id: int | str, result: Any) -> None:
    response = {"jsonrpc": "2.0", "result": result, "id": request_id}
    with _stdout_lock:
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


def _write_error(request_id: int | str | None, code: int, message: str) -> None:
    response = {
        "jsonrpc": "2.0",
        "error": {"code": code, "message": message},
        "id": request_id,
    }
    with _stdout_lock:
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


def _notify_progress(
    progress_type: str, video_id: str, message: str, percent: int
) -> None:
    """Send a JSON-RPC notification (no id = no response expected)."""
    notification = {
        "jsonrpc": "2.0",
        "method": "progress",
        "params": {
            "type": progress_type,
            "video_id": video_id,
            "message": message,
            "percent": percent,
        },
    }
    with _stdout_lock:
        sys.stdout.write(json.dumps(notification) + "\n")
        sys.stdout.flush()


_NEXT_REVERSE_ID = 1000
_reverse_lock = threading.Lock()
_confirm_event = threading.Event()
_confirm_result: bool = False
_confirm_request_id: int | None = None


def _request_confirm_removal(episodes: list[dict], deficit_bytes: int) -> bool:
    """Send a reverse JSON-RPC request and wait for main loop to relay the response."""
    global _NEXT_REVERSE_ID, _confirm_result, _confirm_request_id
    with _reverse_lock:
        request_id = _NEXT_REVERSE_ID
        _NEXT_REVERSE_ID += 1

    _confirm_event.clear()
    _confirm_request_id = request_id

    request = {
        "jsonrpc": "2.0",
        "method": "confirm_removal",
        "params": {"episodes": episodes, "deficit_bytes": deficit_bytes},
        "id": request_id,
    }
    with _stdout_lock:
        sys.stdout.write(json.dumps(request) + "\n")
        sys.stdout.flush()

    # Wait for main() to signal the response (5 min timeout)
    _confirm_event.wait(timeout=300)
    _confirm_request_id = None
    return _confirm_result


# --- Feed methods ---


def _get_auth_opts() -> dict:
    from youtube_audio_chunker.auth import get_ytdlp_auth_opts
    return get_ytdlp_auth_opts()


def _handle_list_subscriptions(params: dict) -> dict:
    offset = params.get("offset", 0)
    auth_opts = _get_auth_opts()
    results = list_feed("https://www.youtube.com/feed/subscriptions", auth_opts, offset=offset)
    return {"results": results}


def _handle_list_home_feed(params: dict) -> dict:
    offset = params.get("offset", 0)
    auth_opts = _get_auth_opts()
    results = list_feed("https://www.youtube.com/feed/recommended", auth_opts, offset=offset)
    return {"results": results}


def _handle_list_liked_videos(params: dict) -> dict:
    offset = params.get("offset", 0)
    auth_opts = _get_auth_opts()
    results = list_feed("https://www.youtube.com/playlist?list=LL", auth_opts, offset=offset)
    return {"results": results}


def _handle_list_playlists(params: dict) -> dict:
    auth_opts = _get_auth_opts()
    playlists = list_user_playlists(auth_opts)
    return {"playlists": playlists}


def _handle_list_playlist_videos(params: dict) -> dict:
    playlist_id = params.get("playlist_id", "")
    if not playlist_id.strip():
        raise ValueError("playlist_id is required")
    offset = params.get("offset", 0)
    auth_opts = _get_auth_opts()
    results = list_playlist_videos(playlist_id, auth_opts, offset=offset)
    return {"results": results}


# --- Auth methods ---


def _handle_detect_browser(params: dict) -> dict:
    browser = detect_browser()
    if browser is None:
        return {"browser": None}
    return {"browser": browser}


def _handle_connect_cookies(params: dict) -> dict:
    browser = params.get("browser")
    return connect_cookies(browser=browser)


def _handle_get_auth_status(params: dict) -> dict:
    status = get_auth_status()
    if status is None:
        return {"method": None, "detail": None}
    return status


def _handle_disconnect_auth(params: dict) -> dict:
    auth_disconnect()
    return {"disconnected": True}


# --- Discovery / Topics ---


def _handle_get_topics(params: dict) -> dict:
    with _topics_lock:
        store = load_topics()
        return {"topics": [asdict(t) for t in store.topics]}


def _handle_create_topic(params: dict) -> dict:
    name = params["name"]
    search_query = params["search_query"]
    with _topics_lock:
        store = load_topics()
        add_topic(store, name, search_query, source_video_ids=[])
        save_topics(store)
        return {"topics": [asdict(t) for t in store.topics]}


def _handle_update_topic(params: dict) -> dict:
    topic_id = params["topic_id"]
    with _topics_lock:
        store = load_topics()
        result = update_topic(
            store, topic_id,
            name=params.get("name"),
            search_query=params.get("search_query"),
        )
        if result is None:
            raise ChunkerError(f"Topic not found: {topic_id}")
        save_topics(store)
        return asdict(result)


def _handle_delete_topic(params: dict) -> dict:
    topic_id = params["topic_id"]
    with _topics_lock:
        store = load_topics()
        delete_topic(store, topic_id)
        save_topics(store)
    return {"deleted": topic_id}


def _handle_dismiss_video(params: dict) -> dict:
    video_id = params["video_id"]
    with _topics_lock:
        store = load_topics()
        dismiss_video(store, video_id)
        save_topics(store)
    return {"dismissed": video_id}


def _handle_search_topic(params: dict) -> dict:
    topic_id = params["topic_id"]
    page_token = params.get("page_token")

    settings = _load_settings()
    api_key = settings.get("youtube_api_key", "")
    if not api_key:
        raise ChunkerError("YouTube API key not configured. Set it in Settings.")

    with _topics_lock:
        store = load_topics()
        topic = next((t for t in store.topics if t.id == topic_id), None)
        if topic is None:
            raise ChunkerError(f"Topic not found: {topic_id}")
        search_query = topic.search_query

    # Use cache if fresh and no specific page requested
    if not page_token:
        cached = get_cached_results(topic_id)
        if cached is not None:
            with _topics_lock:
                store = load_topics()
            library = load_library()
            excluded = get_excluded_video_ids(store, library)
            filtered = [r for r in cached["results"] if r["video_id"] not in excluded]
            return {"results": filtered, "next_page_token": cached.get("next_page_token")}

    result = search_youtube_api(search_query, api_key, page_token=page_token)

    # Cache the raw results
    cache_results(topic_id, result["results"], result["next_page_token"])

    # Filter out excluded videos
    with _topics_lock:
        store = load_topics()
    library = load_library()
    excluded = get_excluded_video_ids(store, library)
    filtered = [r for r in result["results"] if r["video_id"] not in excluded]

    return {"results": filtered, "next_page_token": result["next_page_token"]}


def _handle_extract_topics(params: dict) -> dict:
    settings = _load_settings()
    provider, api_key, model = _resolve_topic_provider(settings)
    if not api_key:
        raise ChunkerError("No API key configured for topic extraction. Set one in Settings.")

    library = load_library()
    titles = [e.title for e in library.queue] + [e.title for e in library.downloaded]
    if not titles:
        return {"topics": [], "new_count": 0}

    extracted = extract_topics_from_titles(titles, api_key, provider=provider, model=model)

    with _topics_lock:
        store = load_topics()
        existing_names = {t.name.lower() for t in store.topics}
        new_count = 0
        video_ids = [e.video_id for e in library.queue] + [e.video_id for e in library.downloaded]

        for topic_data in extracted:
            if topic_data["name"].lower() not in existing_names:
                add_topic(store, topic_data["name"], topic_data["search_query"], video_ids)
                existing_names.add(topic_data["name"].lower())
                new_count += 1

        save_topics(store)
        return {"topics": [asdict(t) for t in store.topics], "new_count": new_count}


def _record_history_for_ids(video_ids: list[str]) -> None:
    with _topics_lock:
        store = load_topics()
        record_video_history(store, video_ids)
        save_topics(store)


def _resolve_topic_provider(settings: dict) -> tuple[str, str, str | None]:
    """Return (provider, api_key, model) based on settings."""
    provider = settings.get("topic_provider", "")
    model = settings.get("topic_model") or None
    if provider == "openai" and settings.get("openai_api_key"):
        return "openai", settings["openai_api_key"], model
    if provider == "anthropic" and settings.get("anthropic_api_key"):
        return "anthropic", settings["anthropic_api_key"], model
    # Fallback: use whichever key is available
    if settings.get("anthropic_api_key"):
        return "anthropic", settings["anthropic_api_key"], model
    if settings.get("openai_api_key"):
        return "openai", settings["openai_api_key"], model
    return "anthropic", "", model


def _maybe_auto_extract_topics(library) -> None:
    """Spawn background topic extraction if an API key is configured."""
    settings = _load_settings()
    provider, api_key, model = _resolve_topic_provider(settings)
    if not api_key:
        return

    titles = [e.title for e in library.queue] + [e.title for e in library.downloaded]
    if not titles:
        return

    def _run():
        try:
            extracted = extract_topics_from_titles(titles, api_key, provider=provider, model=model)
            with _topics_lock:
                store = load_topics()
                existing_names = {t.name.lower() for t in store.topics}
                video_ids = [e.video_id for e in library.queue] + [
                    e.video_id for e in library.downloaded
                ]
                for topic_data in extracted:
                    if topic_data["name"].lower() not in existing_names:
                        add_topic(store, topic_data["name"], topic_data["search_query"], video_ids)
                        existing_names.add(topic_data["name"].lower())
                save_topics(store)
        except Exception:
            logging.getLogger(__name__).exception("Auto topic extraction failed")

    thread = threading.Thread(target=_run)
    thread.daemon = True
    thread.start()




# --- Method registry ---

_METHODS = {
    "get_library": _handle_get_library,
    "get_garmin_status": _handle_get_garmin_status,
    "list_shows": _handle_list_shows,
    "rename_show": _handle_rename_show,
    "edit_episode": _handle_edit_episode,
    "resync_episode": _handle_resync_episode,
    "edit_queue_entry": _handle_edit_queue_entry,
    "search_youtube": _handle_search_youtube,
    "list_channel_videos": _handle_list_channel_videos,
    "add_to_queue": _handle_add_to_queue,
    "remove_episode": _handle_remove_episode,
    "remove_episodes": _handle_remove_episodes,
    "remove_from_garmin": _handle_remove_from_garmin,
    "remove_from_garmin_batch": _handle_remove_from_garmin_batch,
    "process_queue": _handle_process_queue,
    "transfer_unsynced": _handle_transfer_unsynced,
    "transfer_episode": _handle_transfer_episode,
    "get_settings": _handle_get_settings,
    "save_settings": _handle_save_settings,
    "cancel": _handle_cancel,
    "list_subscriptions": _handle_list_subscriptions,
    "list_home_feed": _handle_list_home_feed,
    "list_liked_videos": _handle_list_liked_videos,
    "list_playlists": _handle_list_playlists,
    "list_playlist_videos": _handle_list_playlist_videos,
    "detect_browser": _handle_detect_browser,
    "connect_cookies": _handle_connect_cookies,
    "get_auth_status": _handle_get_auth_status,
    "disconnect_auth": _handle_disconnect_auth,
    "get_topics": _handle_get_topics,
    "create_topic": _handle_create_topic,
    "update_topic": _handle_update_topic,
    "delete_topic": _handle_delete_topic,
    "dismiss_video": _handle_dismiss_video,
    "search_topic": _handle_search_topic,
    "extract_topics": _handle_extract_topics,
}


if __name__ == "__main__":
    main()
