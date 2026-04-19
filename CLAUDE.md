# youtube-audio-chunker

## Dev server

Run `cd gui && npm run tauri dev`. `npm run dev` alone is browser-only (no Tauri IPC, no Python sidecar, no Watch access). Keep the `dev` script - tauri invokes it via `beforeDevCommand`.
