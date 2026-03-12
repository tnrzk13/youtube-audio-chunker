# youtube-audio-chunker

Download YouTube audio, split into navigable chunks, and sideload to Garmin watches.

Built for the Garmin Forerunner 245 Music (and similar watches that play MP3s from a `MUSIC/` folder via USB).

## Prerequisites

- Python 3.11+
- [ffmpeg](https://ffmpeg.org/) (system package)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (installed as dependency)

## Installation

```bash
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

## Usage

### Add videos to the queue

```bash
youtube-audio-chunker add "https://www.youtube.com/watch?v=VIDEO_ID"
youtube-audio-chunker add "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

Playlists are expanded to individual entries. Duplicates are skipped.

### Process queue and sync to watch

```bash
# Process and transfer to Garmin
youtube-audio-chunker sync

# Process only (no watch needed)
youtube-audio-chunker sync --no-transfer

# Custom chunk duration (10 minutes)
youtube-audio-chunker sync --chunk-duration 600

# Override artist tag
youtube-audio-chunker sync --artist "Podcast Host"
```

When the watch is low on storage, `sync` will list the oldest episodes and ask before removing them.

### List episodes

```bash
youtube-audio-chunker list            # Show all sections
youtube-audio-chunker list --queued   # URLs waiting to be processed
youtube-audio-chunker list --local    # Downloaded and chunked locally
youtube-audio-chunker list --watch    # On the Garmin watch
```

### Remove episodes

```bash
youtube-audio-chunker remove "Episode Title"          # Remove from local storage
youtube-audio-chunker remove "Episode Title" --watch   # Remove from watch only
```

## How it works

1. **Download** - yt-dlp extracts audio as 128kbps MP3
2. **Split** - ffmpeg segments into 5-minute chunks (lossless, no re-encoding)
3. **Tag** - ID3v2 tags set per chunk (title, album, artist, track number) so they play in order
4. **Transfer** - copies to `MUSIC/` folder on the mounted Garmin

Files are stored in `~/.youtube-audio-chunker/`.

## Running tests

```bash
pytest tests/
```
