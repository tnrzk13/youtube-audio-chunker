"""Build the Python sidecar into a standalone binary using PyInstaller.

Usage:
    python build/build_sidecar.py

Output goes to gui/src-tauri/binaries/ with the Tauri sidecar naming
convention: youtube-audio-chunker-sidecar-{target_triple}
"""

import platform
import subprocess
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SIDECAR_ENTRY = PROJECT_ROOT / "src" / "youtube_audio_chunker" / "sidecar.py"
TAURI_BINARIES_DIR = PROJECT_ROOT / "gui" / "src-tauri" / "binaries"
DIST_DIR = PROJECT_ROOT / "build" / "dist"
WORK_DIR = PROJECT_ROOT / "build" / "work"


def get_target_triple() -> str:
    machine = platform.machine().lower()
    system = platform.system().lower()

    arch_map = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}
    arch = arch_map.get(machine, machine)

    if system == "linux":
        return f"{arch}-unknown-linux-gnu"
    elif system == "darwin":
        return f"{arch}-apple-darwin"
    else:
        print(f"Unsupported platform: {system}", file=sys.stderr)
        sys.exit(1)


def build_sidecar():
    target_triple = get_target_triple()
    binary_name = f"youtube-audio-chunker-sidecar-{target_triple}"

    print(f"Building sidecar for {target_triple}...")

    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--name", "youtube-audio-chunker-sidecar",
            "--distpath", str(DIST_DIR),
            "--workpath", str(WORK_DIR),
            "--specpath", str(WORK_DIR),
            "--clean",
            str(SIDECAR_ENTRY),
        ],
        check=True,
    )

    TAURI_BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    source = DIST_DIR / "youtube-audio-chunker-sidecar"
    dest = TAURI_BINARIES_DIR / binary_name

    shutil.copy2(source, dest)
    dest.chmod(0o755)

    print(f"Sidecar binary: {dest}")


if __name__ == "__main__":
    build_sidecar()
