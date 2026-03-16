"""Lightweight HTTP server for browser dev mode - wraps the same handlers as the sidecar."""

from __future__ import annotations

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn, TCPServer
from typing import Any

from youtube_audio_chunker.errors import ChunkerError
from youtube_audio_chunker.sidecar import _METHODS, _cancel_event

DEFAULT_PORT = 8765

_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()


def _broadcast_progress(
    progress_type: str, video_id: str, message: str, percent: int
) -> None:
    event_data = json.dumps({
        "type": progress_type,
        "video_id": video_id,
        "message": message,
        "percent": percent,
    })
    with _sse_lock:
        for q in _sse_clients:
            q.put(event_data)


class _Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self._send_cors_headers(204)
        self.end_headers()

    def do_POST(self):
        if self.path != "/rpc":
            self._send_json(404, {"error": "Not found"})
            return

        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        method = request.get("method", "")
        params = request.get("params", {})

        handler = _METHODS.get(method)
        if handler is None:
            self._send_json(404, {"error": f"Unknown method: {method}"})
            return

        try:
            result = handler(params)
            self._send_json(200, {"result": result})
        except ChunkerError as exc:
            self._send_json(500, {"error": str(exc)})
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def do_GET(self):
        if self.path != "/events":
            self._send_json(404, {"error": "Not found"})
            return

        self._send_cors_headers(200, "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        client_queue: queue.Queue = queue.Queue()
        with _sse_lock:
            _sse_clients.append(client_queue)

        try:
            while True:
                data = client_queue.get()
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _sse_lock:
                _sse_clients.remove(client_queue)

    def _send_cors_headers(self, code: int, content_type: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, code: int, data: Any) -> None:
        self._send_cors_headers(code)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        pass  # Suppress default request logging


def main(port: int = DEFAULT_PORT) -> None:
    # Wire progress notifications to SSE broadcast
    from youtube_audio_chunker import pipeline
    from youtube_audio_chunker.pipeline import PipelineCallbacks

    _original_handle_process_queue = _METHODS["process_queue"]
    _original_handle_transfer_unsynced = _METHODS["transfer_unsynced"]

    def _handle_process_queue_with_sse(params: dict) -> dict:
        from youtube_audio_chunker.pipeline import SyncOptions
        options = SyncOptions(
            chunk_duration_seconds=params.get("chunk_duration_seconds"),
            artist=params.get("artist"),
            keep_full=params.get("keep_full", False),
            no_transfer=params.get("no_transfer", False),
        )
        callbacks = PipelineCallbacks(
            on_progress=_broadcast_progress,
            is_cancelled=lambda: _cancel_event.is_set(),
        )
        return pipeline.process_queue(options, callbacks)

    def _handle_transfer_unsynced_with_sse(params: dict) -> dict:
        callbacks = PipelineCallbacks(
            on_progress=_broadcast_progress,
            is_cancelled=lambda: _cancel_event.is_set(),
        )
        return pipeline.transfer_unsynced(callbacks=callbacks)

    _METHODS["process_queue"] = _handle_process_queue_with_sse
    _METHODS["transfer_unsynced"] = _handle_transfer_unsynced_with_sse

    class _ThreadingHTTPServer(ThreadingMixIn, TCPServer):
        allow_reuse_address = True
        daemon_threads = True

    server = _ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    print(f"HTTP API listening on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        # Restore originals
        _METHODS["process_queue"] = _original_handle_process_queue
        _METHODS["transfer_unsynced"] = _original_handle_transfer_unsynced


def _run_with_reload(port: int = DEFAULT_PORT) -> None:
    """Re-exec this process whenever a .py file in src/ changes."""
    import os
    import signal
    import subprocess
    import sys

    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    src_dir = os.path.join(os.path.dirname(__file__), os.pardir)
    child: subprocess.Popen | None = None

    def start_child() -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-m", "youtube_audio_chunker.httpapi", "--port", str(port)],
        )

    class _ReloadHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if event.src_path.endswith(".py"):
                nonlocal child
                print(f"\n  Reloading (changed: {os.path.basename(event.src_path)})")
                if child:
                    child.terminate()
                    child.wait()
                child = start_child()

    child = start_child()
    observer = Observer()
    observer.schedule(_ReloadHandler(), src_dir, recursive=True)
    observer.start()
    print(f"  Auto-reload watching {os.path.abspath(src_dir)}")

    try:
        child.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if child:
            child.terminate()
            child.wait()
        observer.stop()
        observer.join()


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    port = DEFAULT_PORT
    reload = False
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        elif args[i] == "--reload":
            reload = True
            i += 1
        else:
            i += 1

    if reload:
        _run_with_reload(port)
    else:
        main(port)
