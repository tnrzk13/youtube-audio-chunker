class ChunkerError(Exception):
    """Base exception for youtube-audio-chunker."""


class DependencyError(ChunkerError):
    """A required external tool is missing or broken."""


class DownloadError(ChunkerError):
    """Audio download failed."""


class GarminError(ChunkerError):
    """Garmin watch detection or file operation failed."""
