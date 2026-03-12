"""CLI entry point - argparse with subcommands."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from youtube_audio_chunker.constants import (
    ContentType,
    DEFAULT_CHUNK_DURATION_SECONDS,
    GARMIN_DIRS,
    LIBRARY_PATH,
    OUTPUT_DIR,
)
from youtube_audio_chunker.downloader import extract_metadata
from youtube_audio_chunker.errors import ChunkerError
from youtube_audio_chunker.garmin import (
    find_garmin_mount,
    list_garmin_episodes,
    remove_from_garmin,
)
from youtube_audio_chunker.library import (
    load_library,
    save_library,
    add_to_queue,
    remove_episode,
)
from youtube_audio_chunker.pipeline import process_queue, transfer_unsynced, SyncOptions


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "command") or args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        handlers = {
            "add": _handle_add,
            "sync": _handle_sync,
            "download": _handle_download,
            "transfer": _handle_transfer,
            "list": _handle_list,
            "remove": _handle_remove,
        }
        handlers[args.command](args)
    except ChunkerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="youtube-audio-chunker",
        description="Download YouTube audio, split into chunks, sideload to Garmin",
    )
    subparsers = parser.add_subparsers(dest="command")

    _add_add_parser(subparsers)
    _add_sync_parser(subparsers)
    _add_download_parser(subparsers)
    _add_transfer_parser(subparsers)
    _add_list_parser(subparsers)
    _add_remove_parser(subparsers)

    return parser


def _add_add_parser(subparsers) -> None:
    p = subparsers.add_parser("add", help="Add URLs to processing queue")
    p.add_argument("urls", nargs="+", help="YouTube video or playlist URLs")
    p.add_argument(
        "--type",
        choices=[t.value for t in ContentType],
        default=ContentType.MUSIC.value,
        help="Content type: music (chunked, MUSIC/), podcast (single, Podcasts/), "
        "audiobook (single, Audio books/). Default: music",
    )


def _add_sync_parser(subparsers) -> None:
    p = subparsers.add_parser("sync", help="Process queue, chunk, transfer to watch")
    p.add_argument(
        "--chunk-duration", type=int, default=None,
        help=f"Force chunking at this duration in seconds "
        f"(default: {DEFAULT_CHUNK_DURATION_SECONDS} for music, disabled for podcast/audiobook)",
    )
    p.add_argument("--artist", help="Override artist name for ID3 tags")
    p.add_argument(
        "--keep-full", action="store_true",
        help="Keep full audio file after chunking",
    )
    p.add_argument(
        "--no-transfer", action="store_true",
        help="Process but don't copy to watch",
    )


def _add_download_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "download", help="Add URLs and immediately download (add + sync in one step)",
    )
    p.add_argument("urls", nargs="+", help="YouTube video or playlist URLs")
    p.add_argument(
        "--type",
        choices=[t.value for t in ContentType],
        default=ContentType.MUSIC.value,
        help="Content type: music (chunked, MUSIC/), podcast (single, Podcasts/), "
        "audiobook (single, Audio books/). Default: music",
    )
    p.add_argument(
        "--chunk-duration", type=int, default=None,
        help=f"Force chunking at this duration in seconds "
        f"(default: {DEFAULT_CHUNK_DURATION_SECONDS} for music, disabled for podcast/audiobook)",
    )
    p.add_argument("--artist", help="Override artist name for ID3 tags")
    p.add_argument(
        "--keep-full", action="store_true",
        help="Keep full audio file after chunking",
    )
    p.add_argument(
        "--no-transfer", action="store_true",
        help="Process but don't copy to watch",
    )


def _add_transfer_parser(subparsers) -> None:
    subparsers.add_parser(
        "transfer", help="Transfer unsynced local episodes to Garmin watch",
    )


def _add_list_parser(subparsers) -> None:
    p = subparsers.add_parser("list", help="Show episodes by location")
    p.add_argument("--queued", action="store_true", help="Show queued URLs only")
    p.add_argument("--local", action="store_true", help="Show local episodes only")
    p.add_argument("--watch", action="store_true", help="Show watch episodes only")


def _add_remove_parser(subparsers) -> None:
    p = subparsers.add_parser("remove", help="Remove episode by title")
    p.add_argument("title", help="Episode title to remove")
    p.add_argument("--watch", action="store_true", help="Remove from Garmin only")


def _handle_add(args) -> None:
    library = load_library()
    content_type = args.type
    for url in args.urls:
        entries = extract_metadata(url)
        for entry in entries:
            added = add_to_queue(
                library,
                url=url,
                title=entry["title"],
                video_id=entry["id"],
                content_type=content_type,
            )
            if added:
                print(f"Added ({content_type}): {entry['title']}")
            else:
                print(f"Skipped (already exists): {entry['title']}")
    save_library(library)


def _handle_download(args) -> None:
    _handle_add(args)
    _handle_sync(args)


def _handle_transfer(_args) -> None:
    transfer_unsynced()


def _handle_sync(args) -> None:
    opts = SyncOptions(
        chunk_duration_seconds=args.chunk_duration,
        artist=args.artist,
        keep_full=args.keep_full,
        no_transfer=args.no_transfer,
    )
    process_queue(opts)


def _handle_list(args) -> None:
    show_all = not (args.queued or args.local or args.watch)
    library = load_library()

    if show_all or args.queued:
        _print_queued(library)
    if show_all or args.local:
        _print_local(library)
    if show_all or args.watch:
        _print_watch()


def _print_queued(library) -> None:
    print("=== Queued ===")
    if not library.queue:
        print("  (empty)")
    for entry in library.queue:
        print(f"  {entry.title}")
    print()


def _print_local(library) -> None:
    print("=== Local ===")
    if not library.downloaded:
        print("  (empty)")
    for ep in library.downloaded:
        size_mb = ep.total_size_bytes / 1_000_000
        synced = "synced" if ep.synced_at else "not synced"
        content_type = getattr(ep, "content_type", "music")
        if ep.chunk_count == 1:
            print(f"  {ep.title} ({content_type}, {size_mb:.1f} MB, {synced})")
        else:
            print(f"  {ep.title} ({content_type}, {ep.chunk_count} chunks, {size_mb:.1f} MB, {synced})")
    print()


def _print_watch() -> None:
    print("=== Watch ===")
    garmin = find_garmin_mount()
    if garmin is None:
        print("  (no Garmin detected)")
        print()
        return
    episodes = list_garmin_episodes(garmin)
    if not episodes:
        print("  (empty)")
    for ep in episodes:
        size_mb = ep.total_size_bytes / 1_000_000
        location = ep.location or "MUSIC"
        print(f"  {ep.folder_name} ({location}, {size_mb:.1f} MB)")
    print()


def _handle_remove(args) -> None:
    if args.watch:
        _remove_from_watch(args.title)
    else:
        _remove_from_local(args.title)


def _remove_from_watch(title: str) -> None:
    garmin = find_garmin_mount()
    if garmin is None:
        print("No Garmin watch detected.", file=sys.stderr)
        sys.exit(1)
    remove_from_garmin(title, garmin)
    print(f"Removed from watch: {title}")


def _remove_from_local(title: str) -> None:
    library = load_library()
    video_id, folder_name = _find_episode_by_title(library, title)
    if video_id is None:
        print(f"Episode '{title}' not found.", file=sys.stderr)
        sys.exit(1)

    remove_episode(library, video_id)

    if folder_name:
        episode_dir = OUTPUT_DIR / folder_name
        if episode_dir.exists():
            shutil.rmtree(episode_dir)

    save_library(library)
    print(f"Removed: {title}")


def _find_episode_by_title(library, title: str) -> tuple[str | None, str | None]:
    """Returns (video_id, folder_name) or (None, None) if not found."""
    for ep in library.downloaded:
        if ep.title == title:
            return ep.video_id, ep.folder_name
    for entry in library.queue:
        if entry.title == title:
            return entry.video_id, None
    return None, None
