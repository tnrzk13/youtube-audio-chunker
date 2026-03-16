import http.client
import json
import threading
from socketserver import ThreadingMixIn, TCPServer
from unittest.mock import patch

from youtube_audio_chunker.httpapi import _Handler, ALLOWED_ORIGIN


def _start_test_server():
    """Start the HTTP handler on a random port and return (server, port)."""
    class _Server(ThreadingMixIn, TCPServer):
        allow_reuse_address = True
        daemon_threads = True

    server = _Server(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server, port


class TestCorsHeaders:
    def test_allowed_origin_is_not_wildcard(self):
        assert ALLOWED_ORIGIN == "http://localhost:5173"

    def test_options_returns_allowed_origin(self):
        server, port = _start_test_server()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port)
            conn.request("OPTIONS", "/rpc")
            resp = conn.getresponse()
            assert resp.getheader("Access-Control-Allow-Origin") == ALLOWED_ORIGIN
        finally:
            server.shutdown()

    def test_post_returns_allowed_origin(self):
        server, port = _start_test_server()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/not-found")
            resp = conn.getresponse()
            assert resp.getheader("Access-Control-Allow-Origin") == ALLOWED_ORIGIN
        finally:
            server.shutdown()


def _raise_unexpected_error(params):
    raise RuntimeError("secret internal detail: /home/user/.config/keys")


class TestErrorSanitization:
    def test_generic_exception_returns_internal_server_error(self):
        server, port = _start_test_server()
        try:
            with patch.dict(
                "youtube_audio_chunker.sidecar._METHODS",
                {"test_boom": _raise_unexpected_error},
            ):
                conn = http.client.HTTPConnection("127.0.0.1", port)
                body = json.dumps({"method": "test_boom", "params": {}})
                conn.request(
                    "POST", "/rpc", body=body,
                    headers={"Content-Type": "application/json"},
                )
                resp = conn.getresponse()
                data = json.loads(resp.read())
                assert data["error"] == "Internal server error"
        finally:
            server.shutdown()
