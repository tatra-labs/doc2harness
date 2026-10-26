"""The scripted mock model of stage 2.

The mock makes a run deterministic: it answers the harness from a fixed script and records every
request body it received, which is one of the four observable channels.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Returned once the script is spent. It carries no tool calls, so a correct harness stops.
EXHAUSTED = {"content": "script exhausted"}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):  # keep the grader's output clean
        pass

    def do_POST(self):  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        model = self.server.model
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            body = {"_unparseable": raw.decode("utf-8", "replace")}
        with model.lock:
            if self.path != "/v1/chat":
                model.misroutes.append(self.path)
                self._send(404, b"")
                return
            model.requests.append(body)
            model.content_types.append(self.headers.get("content-type"))
            step = model.next_step()
        status, payload = _render(step)
        self._send(status, payload)

    def do_GET(self):  # noqa: N802
        with self.server.model.lock:
            self.server.model.misroutes.append("GET " + self.path)
        self._send(404, b"")

    def _send(self, status, payload):
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)


def _render(step):
    """Turn one script entry into an HTTP status and body."""
    if "raw" in step:
        return step.get("status", 200), step["raw"].encode("utf-8")
    status = step.get("status", 200)
    if status != 200:
        return status, b""
    body = {key: value for key, value in step.items() if key != "status"}
    return 200, json.dumps(body).encode("utf-8")


class MockModel:
    """A model server that replays `script`, one entry per request attempt."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.content_types = []
        self.misroutes = []
        self.lock = threading.Lock()
        self._served = 0
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.model = self
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def next_step(self):
        if self._served < len(self.script):
            step = self.script[self._served]
        else:
            step = EXHAUSTED
        self._served += 1
        return step

    @property
    def url(self):
        host, port = self._server.server_address[:2]
        return "http://%s:%d" % (host, port)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
        return False
