"""Mutagen ID3 tagging for audio chunks."""

from pathlib import Path

from mutagen.mp3 import MP3
from mutagen.id3 import TIT2, TALB, TPE1, TPE2, TRCK, TCON, TXXX

from youtube_audio_chunker.constants import ContentType


def tag_chunks(
    chunk_paths: list[Path],
    title: str,
    total_chunks: int,
    artist: str,
    album: str | None = None,
    track_offset: int = 0,
    content_type: ContentType | None = None,
) -> None:
    resolved_album = album if album is not None else title
    for i, path in enumerate(chunk_paths, start=1):
        audio = MP3(path)
        if audio.tags is None:
            audio.add_tags()
        audio.tags["TIT2"] = TIT2(encoding=3, text=f"{title} - Part {i:02d}")
        audio.tags["TALB"] = TALB(encoding=3, text=resolved_album)
        audio.tags["TPE1"] = TPE1(encoding=3, text=artist)
        if content_type in (ContentType.PODCAST, ContentType.AUDIOBOOK):
            audio.tags["TPE2"] = TPE2(encoding=3, text=resolved_album)
        track_number = track_offset + i
        track_text = str(track_number) if track_offset > 0 else f"{i}/{total_chunks}"
        audio.tags["TRCK"] = TRCK(encoding=3, text=track_text)
        audio.save()


def tag_single(
    audio_path: Path,
    title: str,
    artist: str,
    content_type: ContentType,
    album: str | None = None,
) -> None:
    resolved_album = album if album is not None else title
    audio = MP3(audio_path)
    if audio.tags is None:
        audio.add_tags()
    audio.tags["TIT2"] = TIT2(encoding=3, text=title)
    audio.tags["TALB"] = TALB(encoding=3, text=resolved_album)
    audio.tags["TPE1"] = TPE1(encoding=3, text=artist)
    if content_type in (ContentType.PODCAST, ContentType.AUDIOBOOK):
        audio.tags["TPE2"] = TPE2(encoding=3, text=resolved_album)
    if content_type == ContentType.PODCAST:
        _apply_podcast_tags(audio)
    elif content_type == ContentType.AUDIOBOOK:
        audio.tags["TCON"] = TCON(encoding=3, text="Audiobook")
    audio.save()


def retag_episode(
    episode_dir: Path,
    title: str,
    artist: str,
    album: str,
    content_type: ContentType,
    chunk_count: int,
) -> None:
    mp3_files = sorted(episode_dir.glob("*.mp3"))
    if chunk_count > 1:
        tag_chunks(mp3_files, title=title, total_chunks=chunk_count,
                   artist=artist, album=album, content_type=content_type)
    else:
        tag_single(mp3_files[0], title=title, artist=artist,
                   content_type=content_type, album=album)


def _apply_podcast_tags(audio: MP3) -> None:
    audio.tags["TCON"] = TCON(encoding=3, text="Podcast")
    audio.tags["PCST"] = TXXX(encoding=3, desc="PCST", text="1")
    audio.tags["TXXX:PODCASTDESC"] = TXXX(
        encoding=3, desc="PODCASTDESC", text=""
    )
