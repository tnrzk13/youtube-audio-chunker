# youtube-audio-chunker

## Run (from project root)

- `npm run dev:tauri` - full stack dev (HTTP API + Tauri native with Python sidecar)
- `npm run dev` - browser-only preview, no Tauri IPC / Watch access
- `npm run build` - builds the `.deb`, prints a paste-runnable `sudo apt install` hint
- `npm run gui:install` - installs `gui/` deps

`gui/`'s `dev` script exists because Tauri invokes it via `beforeDevCommand` - keep it.
