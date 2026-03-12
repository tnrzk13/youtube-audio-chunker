from enum import Enum
from pathlib import Path

DEFAULT_CHUNK_DURATION_SECONDS = 300
DEFAULT_AUDIO_BITRATE = "128k"
DEFAULT_AUDIO_FORMAT = "mp3"

APP_DIR = Path.home() / ".youtube-audio-chunker"
LIBRARY_PATH = APP_DIR / "library.json"
OUTPUT_DIR = APP_DIR / "output"

GARMIN_MARKER_DIR = "GARMIN"

FAT32_ILLEGAL_CHARS = r'\/:*?"<>|'


class ContentType(str, Enum):
    MUSIC = "music"
    PODCAST = "podcast"
    AUDIOBOOK = "audiobook"


GARMIN_DIRS = {
    ContentType.MUSIC: "Music",
    ContentType.PODCAST: "Podcasts",
    ContentType.AUDIOBOOK: "Audiobooks",
}
