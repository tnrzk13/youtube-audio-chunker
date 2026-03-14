#!/usr/bin/env bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[ok]${NC}    $1"; }
info() { echo -e "${BLUE}[info]${NC}  $1"; }
warn() { echo -e "${YELLOW}[warn]${NC}  $1"; }
err()  { echo -e "${RED}[error]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CMD=""

# ── OS detection ──────────────────────────────────────────────────────────────

OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    err "Unsupported OS: $OSTYPE"
    exit 1
fi

# ── Helpers ───────────────────────────────────────────────────────────────────

confirm() {
    read -r -p "$1 [y/N] " response
    [[ "$response" =~ ^[Yy]$ ]]
}

apt_install() {
    if confirm "Install $* via apt?"; then
        sudo apt-get install -y "$@"
    else
        err "Skipped required packages: $*"
        exit 1
    fi
}

brew_install() {
    if ! command -v brew &>/dev/null; then
        warn "Homebrew not found."
        if confirm "Install Homebrew?"; then
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        else
            err "Homebrew is required on macOS. Install it from https://brew.sh"
            exit 1
        fi
    fi
    if confirm "Install $* via brew?"; then
        brew install "$@"
    else
        err "Skipped required packages: $*"
        exit 1
    fi
}

# ── Python 3.11+ ─────────────────────────────────────────────────────────────

check_python() {
    echo "Checking Python..."
    for cmd in python3.13 python3.12 python3.11 python3; do
        if command -v "$cmd" &>/dev/null; then
            version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            major=$(echo "$version" | cut -d. -f1)
            minor=$(echo "$version" | cut -d. -f2)
            if [[ "$major" -ge 3 && "$minor" -ge 11 ]]; then
                PYTHON_CMD="$cmd"
                ok "Python $version ($cmd)"
                return
            fi
        fi
    done

    warn "Python 3.11+ not found."
    if [[ "$OS" == "linux" ]]; then
        apt_install python3.11 python3.11-venv python3-pip
        PYTHON_CMD="python3.11"
    else
        brew_install python@3.11
        PYTHON_CMD="python3.11"
    fi
}

# ── ffmpeg ────────────────────────────────────────────────────────────────────

check_ffmpeg() {
    echo "Checking ffmpeg..."
    if command -v ffmpeg &>/dev/null; then
        ok "ffmpeg $(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')"
        return
    fi

    warn "ffmpeg not found."
    if [[ "$OS" == "linux" ]]; then
        apt_install ffmpeg
    else
        brew_install ffmpeg
    fi
}

# ── Node.js / npm ─────────────────────────────────────────────────────────────

check_node() {
    echo "Checking Node.js..."
    if command -v node &>/dev/null; then
        version=$(node --version)
        major=$(echo "$version" | tr -d 'v' | cut -d. -f1)
        if [[ "$major" -ge 18 ]]; then
            ok "Node.js $version"
            return
        fi
        warn "Node.js $version found but 18+ is required."
    else
        warn "Node.js not found."
    fi

    if [[ "$OS" == "linux" ]]; then
        if confirm "Install Node.js 20 via NodeSource?"; then
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt-get install -y nodejs
            ok "Node.js installed"
        else
            err "Node.js 18+ is required."
            exit 1
        fi
    else
        brew_install node
    fi
}

# ── Rust ──────────────────────────────────────────────────────────────────────

check_rust() {
    echo "Checking Rust..."
    if command -v cargo &>/dev/null; then
        ok "Rust $(rustc --version | awk '{print $2}')"
        return
    fi

    warn "Rust not found."
    if confirm "Install Rust via rustup?"; then
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        if [[ -f "$HOME/.cargo/env" ]]; then
            # shellcheck source=/dev/null
            source "$HOME/.cargo/env"
        fi
        ok "Rust installed"
    else
        err "Rust is required to build the desktop app."
        exit 1
    fi
}

# ── Tauri system libs (Linux only) ────────────────────────────────────────────

check_tauri_linux_deps() {
    echo "Checking Tauri system libraries..."
    TAURI_DEPS=(
        libwebkit2gtk-4.1-dev
        build-essential
        curl
        wget
        file
        libxdo-dev
        libssl-dev
        libayatana-appindicator3-dev
        librsvg2-dev
    )

    missing=()
    for pkg in "${TAURI_DEPS[@]}"; do
        if ! dpkg -s "$pkg" &>/dev/null; then
            missing+=("$pkg")
        fi
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        ok "Tauri system libraries"
        return
    fi

    warn "Missing: ${missing[*]}"
    apt_install "${missing[@]}"
    ok "Tauri system libraries installed"
}

# ── Xcode CLI tools (macOS only) ──────────────────────────────────────────────

check_xcode_tools() {
    echo "Checking Xcode Command Line Tools..."
    if xcode-select -p &>/dev/null; then
        ok "Xcode Command Line Tools"
        return
    fi

    warn "Xcode Command Line Tools not found."
    if confirm "Install Xcode Command Line Tools?"; then
        xcode-select --install
        info "Follow the prompt to complete installation, then re-run this script."
        exit 0
    else
        err "Xcode Command Line Tools are required on macOS."
        exit 1
    fi
}

# ── Install project dependencies ──────────────────────────────────────────────

install_python_package() {
    echo "Installing Python package..."
    cd "$SCRIPT_DIR"
    "$PYTHON_CMD" -m pip install -e . --quiet
    ok "Python package installed"
}

install_npm_deps() {
    echo "Installing npm dependencies..."
    cd "$SCRIPT_DIR/gui"
    npm install --silent
    ok "npm dependencies installed"
}

# ── Main ──────────────────────────────────────────────────────────────────────

echo ""
echo "Setting up youtube-audio-chunker on $OS"
echo "──────────────────────────────────────────"
echo ""

check_python
check_ffmpeg
check_node
check_rust

if [[ "$OS" == "linux" ]]; then
    check_tauri_linux_deps
elif [[ "$OS" == "macos" ]]; then
    check_xcode_tools
fi

echo ""
info "Installing project dependencies..."
echo ""

install_python_package
install_npm_deps

echo ""
echo "──────────────────────────────────────────"
ok "Setup complete!"
echo ""
echo "Build the desktop app:"
echo "    cd gui && npm run tauri build"
echo ""
echo "Or run in development mode:"
echo "    cd gui && npx tauri dev"
echo ""
