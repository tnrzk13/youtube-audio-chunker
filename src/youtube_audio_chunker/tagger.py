"""Mutagen ID3 tagging for audio chunks."""

from pathlib import Path

from mutagen.mp3 import MP3
from mutagen.id3 import TIT2, TALB, TPE1, TRCK


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
