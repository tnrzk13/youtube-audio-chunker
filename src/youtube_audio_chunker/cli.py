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
    rename_show,
    list_shows,
)
from youtube_audio_chunker.pipeline import process_queue, transfer_unsynced, edit_episode, SyncOptions


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
            "show": _handle_show,
            "edit": _handle_edit,
        }
        handlers[args.command](args)
    except ChunkerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="youtube-audio-chunker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Download YouTube audio, split into chunks, and sideload to a Garmin watch.",
        epilog=(
            "typical workflow:\n"
            "  1. youtube-audio-chunker add <url>       Queue a video or playlist\n"
            "  2. youtube-audio-chunker sync             Download, chunk, and transfer to watch\n"
            "\n"
            "shortcut (add + sync in one step):\n"
            "  youtube-audio-chunker download <url>\n"
            "\n"
            "content types:\n"
            "  music       Split into 5-min chunks, stored in MUSIC/ (default)\n"
            "  podcast     Kept as a single file, stored in Podcasts/\n"
            "  audiobook   Kept as a single file, stored in Audiobooks/\n"
            "\n"
            f"library path: {LIBRARY_PATH}\n"
            f"output dir:   {OUTPUT_DIR}\n"
            "\n"
            "run 'youtube-audio-chunker <command> --help' for command-specific options"
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    _add_add_parser(subparsers)
    _add_sync_parser(subparsers)
    _add_download_parser(subparsers)
    _add_transfer_parser(subparsers)
    _add_list_parser(subparsers)
    _add_remove_parser(subparsers)
    _add_show_parser(subparsers)
    _add_edit_parser(subparsers)

    return parser


def _add_add_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "add",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Queue URLs for later processing",
        description=(
            "Add YouTube video or playlist URLs to the processing queue.\n"
            "Playlists are automatically expanded into individual videos."
        ),
        epilog=(
            "examples:\n"
            "  youtube-audio-chunker add https://youtube.com/watch?v=abc\n"
            "  youtube-audio-chunker add --type podcast URL1 URL2\n"
            "  youtube-audio-chunker add --type audiobook https://youtube.com/playlist?list=PL..."
        ),
    )
    p.add_argument("urls", nargs="+", help="YouTube video or playlist URLs")
    p.add_argument(
        "--type",
        choices=[t.value for t in ContentType],
        default=ContentType.MUSIC.value,
        help="Content type: music (chunked, MUSIC/), podcast (single, Podcasts/), "
        "audiobook (single, Audiobooks/). Default: music",
    )
    p.add_argument(
        "--show", metavar="NAME", default=None,
        help="show/series name for grouping (default: auto-detect from channel)",
    )


def _add_sync_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Download queued items, chunk, and transfer to watch",
        description=(
            "Process all queued URLs: download audio, split into chunks\n"
            "(music only), tag with ID3 metadata, and copy to Garmin watch."
        ),
        epilog=(
            "examples:\n"
            "  youtube-audio-chunker sync\n"
            "  youtube-audio-chunker sync --no-transfer\n"
            "  youtube-audio-chunker sync --chunk-duration 600 --artist 'Joe Rogan'"
        ),
    )
    p.add_argument(
        "--chunk-duration", type=int, default=None, metavar="SECONDS",
        help=f"chunk duration in seconds "
        f"(default: {DEFAULT_CHUNK_DURATION_SECONDS} for music, disabled for podcast/audiobook)",
    )
    p.add_argument("--artist", metavar="NAME", help="override artist name for ID3 tags")
    p.add_argument(
        "--keep-full", action="store_true",
        help="keep the full audio file after chunking",
    )
    p.add_argument(
        "--no-transfer", action="store_true",
        help="download and chunk but skip copying to watch",
    )


def _add_download_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "download",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Add URLs and immediately process (add + sync)",
        description=(
            "Shortcut that combines 'add' and 'sync' in one step.\n"
            "Queues the given URLs, then downloads, chunks, and transfers."
        ),
        epilog=(
            "examples:\n"
            "  youtube-audio-chunker download https://youtube.com/watch?v=abc\n"
            "  youtube-audio-chunker download --type podcast --no-transfer URL"
        ),
    )
    p.add_argument("urls", nargs="+", help="YouTube video or playlist URLs")
    p.add_argument(
        "--type",
        choices=[t.value for t in ContentType],
        default=ContentType.MUSIC.value,
        help="Content type: music (chunked, MUSIC/), podcast (single, Podcasts/), "
        "audiobook (single, Audiobooks/). Default: music",
    )
    p.add_argument(
        "--show", metavar="NAME", default=None,
        help="show/series name for grouping (default: auto-detect from channel)",
    )
    p.add_argument(
        "--chunk-duration", type=int, default=None, metavar="SECONDS",
        help=f"chunk duration in seconds "
        f"(default: {DEFAULT_CHUNK_DURATION_SECONDS} for music, disabled for podcast/audiobook)",
    )
    p.add_argument("--artist", metavar="NAME", help="override artist name for ID3 tags")
    p.add_argument(
        "--keep-full", action="store_true",
        help="keep the full audio file after chunking",
    )
    p.add_argument(
        "--no-transfer", action="store_true",
        help="download and chunk but skip copying to watch",
    )


def _add_transfer_parser(subparsers) -> None:
    subparsers.add_parser(
        "transfer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Copy unsynced local episodes to Garmin watch",
        description=(
            "Transfer any locally downloaded episodes that haven't been\n"
            "copied to the Garmin watch yet. The watch must be connected via MTP."
        ),
    )


def _add_list_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Show episodes by location",
        description=(
            "Display episodes grouped by location: queued, local, and watch.\n"
            "Shows all sections by default, or filter to a specific one."
        ),
        epilog=(
            "examples:\n"
            "  youtube-audio-chunker list\n"
            "  youtube-audio-chunker list --watch\n"
            "  youtube-audio-chunker list --queued --local"
        ),
    )
    p.add_argument("--queued", action="store_true", help="show only queued (not yet downloaded) URLs")
    p.add_argument("--local", action="store_true", help="show only locally downloaded episodes")
    p.add_argument("--watch", action="store_true", help="show only episodes on the Garmin watch")


def _add_show_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "show",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Manage shows/series",
        description="List or rename shows (series groupings).",
        epilog=(
            "examples:\n"
            "  youtube-audio-chunker show list\n"
            "  youtube-audio-chunker show rename 'Old Name' 'New Name'"
        ),
    )
    show_sub = p.add_subparsers(dest="show_action")

    show_sub.add_parser("list", help="list shows with episode counts")

    rename_p = show_sub.add_parser("rename", help="rename a show")
    rename_p.add_argument("old_name", help="current show name")
    rename_p.add_argument("new_name", help="new show name")


def _add_edit_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "edit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Edit episode metadata",
        description="Update metadata on a downloaded episode and re-tag files on disk.",
        epilog=(
            "examples:\n"
            '  youtube-audio-chunker edit abc123 --show "New Show"\n'
            '  youtube-audio-chunker edit abc123 --artist "New Artist" --title "New Title"\n'
            "  youtube-audio-chunker edit abc123 --type podcast"
        ),
    )
    p.add_argument("video_id", help="video ID of the episode to edit")
    p.add_argument("--show", metavar="NAME", default=None, help="set show/series name")
    p.add_argument("--artist", metavar="NAME", default=None, help="set artist name")
    p.add_argument("--title", metavar="TITLE", default=None, help="set episode title")
    p.add_argument(
        "--type",
        choices=[t.value for t in ContentType],
        default=None,
        help="set content type",
    )


def _add_remove_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "remove",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Remove an episode by title",
        description=(
            "Remove an episode from the local library (queue + files) or\n"
            "from the Garmin watch only (with --watch)."
        ),
        epilog=(
            "examples:\n"
            "  youtube-audio-chunker remove 'My Episode Title'\n"
            "  youtube-audio-chunker remove --watch 'My Episode Title'"
        ),
    )
    p.add_argument("title", help="episode title (use quotes if it contains spaces)")
    p.add_argument("--watch", action="store_true", help="remove from Garmin watch only (keep local copy)")


def _handle_add(args) -> None:
    library = load_library()
    content_type = args.type
    show_name = getattr(args, "show", None)
    for url in args.urls:
        entries = extract_metadata(url)
        for entry in entries:
            added = add_to_queue(
                library,
                url=url,
                title=entry["title"],
                video_id=entry["id"],
                content_type=content_type,
                show_name=show_name,
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
        if entry.show_name:
            print(f"  {entry.title} ({entry.show_name})")
        else:
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
        parts = [content_type]
        if ep.show_name:
            parts.insert(0, ep.show_name)
        if ep.chunk_count > 1:
            parts.append(f"{ep.chunk_count} chunks")
        parts.append(f"{size_mb:.1f} MB")
        parts.append(synced)
        detail = ", ".join(parts)
        print(f"  {ep.title} ({detail})")
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
    normalized = title.strip().lower()
    for ep in library.downloaded:
        if ep.title.strip().lower() == normalized:
            return ep.video_id, ep.folder_name
    for entry in library.queue:
        if entry.title.strip().lower() == normalized:
            return entry.video_id, None
    return None, None


def _handle_show(args) -> None:
    if not hasattr(args, "show_action") or args.show_action is None:
        print("Usage: youtube-audio-chunker show {list,rename}", file=sys.stderr)
        sys.exit(1)

    library = load_library()
    if args.show_action == "list":
        _show_list(library)
    elif args.show_action == "rename":
        _show_rename(library, args.old_name, args.new_name)


def _show_list(library) -> None:
    shows = list_shows(library)
    if not shows:
        print("No shows found.")
        return
    for show in shows:
        types = ", ".join(show["content_types"])
        print(f"  {show['show_name']} ({show['episode_count']} episodes, {types})")


def _show_rename(library, old_name: str, new_name: str) -> None:
    count = rename_show(library, old_name, new_name)
    save_library(library)
    print(f"Renamed '{old_name}' to '{new_name}' ({count} episodes updated)")


def _handle_edit(args) -> None:
    updates = _collect_edit_updates(args)
    result = edit_episode(args.video_id, updates)
    if result is None:
        print(f"Episode '{args.video_id}' not found.", file=sys.stderr)
        sys.exit(1)
    print(f"Updated: {result['title']}")


def _collect_edit_updates(args) -> dict:
    updates = {}
    if args.show is not None:
        updates["show_name"] = args.show
    if args.artist is not None:
        updates["artist"] = args.artist
    if args.title is not None:
        updates["title"] = args.title
    if args.type is not None:
        updates["content_type"] = args.type
    return updates
