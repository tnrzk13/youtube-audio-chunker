"""JSON-RPC 2.0 stdio bridge for the Tauri GUI sidecar."""

from __future__ import annotations

import json
import shutil
import sys
import threading
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any

from youtube_audio_chunker.constants import APP_DIR, ContentType, OUTPUT_DIR
from youtube_audio_chunker.downloader import extract_metadata
from youtube_audio_chunker.errors import (
    ChunkerError,
    DependencyError,
    DownloadError,
    GarminError,
    SplitError,
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
    rename_show,
    save_library,
)
from youtube_audio_chunker.pipeline import (
    PipelineCallbacks,
    SyncOptions,
    edit_episode,
    process_queue,
    transfer_unsynced,
)

ERROR_CODES = {
    DependencyError: -32001,
    DownloadError: -32002,
    SplitError: -32003,
    GarminError: -32004,
}

PARSE_ERROR = -32700
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603

_cancel_event = threading.Event()
_stdout_lock = threading.Lock()

# Methods that run in a background thread so the main loop stays responsive
_ASYNC_METHODS = {"process_queue", "transfer_unsynced", "transfer_episode"}


def main() -> None:
    """Read JSON-RPC requests from stdin, dispatch, write responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            _write_error(None, PARSE_ERROR, f"Parse error: {exc}")
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
        if request_id is not None:
            _write_error(request_id, INTERNAL_ERROR, traceback.format_exc())


def _is_cancelled() -> bool:
    return _cancel_event.is_set()


# --- Cancel ---


def _handle_cancel(params: dict) -> dict:
    _cancel_event.set()
    return {"cancelled": True}


# --- Read methods ---


def _handle_get_library(params: dict) -> dict:
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
    library = load_library()
    return {"shows": list_shows(library)}


def _handle_rename_show(params: dict) -> dict:
    old_name = params["old_name"]
    new_name = params["new_name"]
    library = load_library()
    count = rename_show(library, old_name, new_name)
    save_library(library)
    return {"renamed": count}


def _handle_edit_episode(params: dict) -> dict:
    video_id = params["video_id"]
    updates = params.get("updates", {})
    result = edit_episode(video_id, updates)
    if result is None:
        raise ChunkerError(f"Episode not found: {video_id}")
    return result


# --- Mutation methods ---


def _handle_add_to_queue(params: dict) -> dict:
    urls = params.get("urls", [])
    content_type = params.get("content_type", ContentType.MUSIC.value)
    show_name = params.get("show_name")
    library = load_library()
    added = []
    skipped = []

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
            )
            if was_added:
                added.append(entry["title"])
            else:
                skipped.append(entry["title"])

    save_library(library)
    return {"added": added, "skipped": skipped}


def _handle_remove_episode(params: dict) -> dict:
    video_id = params["video_id"]
    library = load_library()

    episode_dir = OUTPUT_DIR / _find_folder_name(library, video_id)
    remove_episode(library, video_id)
    save_library(library)

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


# --- Process queue with progress ---


def _handle_process_queue(params: dict) -> dict:
    options = SyncOptions(
        chunk_duration_seconds=params.get("chunk_duration_seconds"),
        artist=params.get("artist"),
        keep_full=params.get("keep_full", False),
        no_transfer=params.get("no_transfer", False),
    )
    callbacks = PipelineCallbacks(
        on_progress=_notify_progress,
        on_confirm_removal=_request_confirm_removal,
        is_cancelled=_is_cancelled,
    )
    return process_queue(options, callbacks)


# --- Transfer single episode ---


def _handle_transfer_episode(params: dict) -> dict:
    video_id = params["video_id"]
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
    if not settings_path.exists():
        return {}
    return json.loads(settings_path.read_text())


def _handle_save_settings(params: dict) -> dict:
    settings = params.get("settings", {})
    settings_path = _settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2))
    return {"saved": True}


# --- Helpers ---


def _settings_path() -> Path:
    return APP_DIR / "settings.json"


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


def _request_confirm_removal(episodes: list[dict], deficit_bytes: int) -> bool:
    """Send a reverse JSON-RPC request to the frontend for user confirmation."""
    global _NEXT_REVERSE_ID
    with _reverse_lock:
        request_id = _NEXT_REVERSE_ID
        _NEXT_REVERSE_ID += 1

    request = {
        "jsonrpc": "2.0",
        "method": "confirm_removal",
        "params": {"episodes": episodes, "deficit_bytes": deficit_bytes},
        "id": request_id,
    }
    with _stdout_lock:
        sys.stdout.write(json.dumps(request) + "\n")
        sys.stdout.flush()

    # Read the response from stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = json.loads(line)
        except json.JSONDecodeError:
            continue

        if response.get("id") == request_id:
            return response.get("result", False)

    return False


# --- Method registry ---

_METHODS = {
    "get_library": _handle_get_library,
    "get_garmin_status": _handle_get_garmin_status,
    "list_shows": _handle_list_shows,
    "rename_show": _handle_rename_show,
    "edit_episode": _handle_edit_episode,
    "add_to_queue": _handle_add_to_queue,
    "remove_episode": _handle_remove_episode,
    "remove_from_garmin": _handle_remove_from_garmin,
    "process_queue": _handle_process_queue,
    "transfer_unsynced": _handle_transfer_unsynced,
    "transfer_episode": _handle_transfer_episode,
    "get_settings": _handle_get_settings,
    "save_settings": _handle_save_settings,
    "cancel": _handle_cancel,
}


if __name__ == "__main__":
    main()
