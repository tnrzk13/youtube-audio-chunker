import pytest
from pathlib import Path


@pytest.fixture
def tmp_app_dir(tmp_path):
    """Provides a temporary app directory mimicking ~/.youtube-audio-chunker/."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return tmp_path
