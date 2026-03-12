"""Mutagen ID3 tagging for audio chunks."""

from pathlib import Path

from mutagen.mp3 import MP3
from mutagen.id3 import TIT2, TALB, TPE1, TRCK, TCON, TXXX

from youtube_audio_chunker.constants import ContentType


def tag_chunks(
    chunk_paths: list[Path], title: str, total_chunks: int, artist: str
) -> None:
    for i, path in enumerate(chunk_paths, start=1):
        audio = MP3(path)
        if audio.tags is None:
            audio.add_tags()
        audio.tags["TIT2"] = TIT2(encoding=3, text=f"{title} - Part {i:02d}")
        audio.tags["TALB"] = TALB(encoding=3, text=title)
        audio.tags["TPE1"] = TPE1(encoding=3, text=artist)
        audio.tags["TRCK"] = TRCK(encoding=3, text=f"{i}/{total_chunks}")
        audio.save()


def tag_single(
    audio_path: Path,
    title: str,
    artist: str,
    content_type: ContentType,
) -> None:
    audio = MP3(audio_path)
    if audio.tags is None:
        audio.add_tags()
    audio.tags["TIT2"] = TIT2(encoding=3, text=title)
    audio.tags["TALB"] = TALB(encoding=3, text=title)
    audio.tags["TPE1"] = TPE1(encoding=3, text=artist)
    if content_type == ContentType.PODCAST:
        _apply_podcast_tags(audio)
    audio.save()


def _apply_podcast_tags(audio: MP3) -> None:
    audio.tags["TCON"] = TCON(encoding=3, text="Podcast")
    audio.tags["PCST"] = TXXX(encoding=3, desc="PCST", text="1")
    audio.tags["TXXX:PODCASTDESC"] = TXXX(
        encoding=3, desc="PODCASTDESC", text=""
    )
