"""The JSON-lines transcript. Section 6."""

import json
import os


class Logbook:
    """Writes the transcript, or nothing at all when --log was not given."""

    def __init__(self, path):
        self.path = path

    def _append(self, event):
        if self.path is None:
            return
        parent = os.path.dirname(os.path.abspath(self.path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self.path, "ab") as fh:
            fh.write((json.dumps(event) + "\n").encode("utf-8"))

    def request(self, turn, messages):
        self._append({"event": "request", "turn": turn, "messages": messages})

    def response(self, turn, tool_calls):
        self._append({"event": "response", "turn": turn, "tool_calls": tool_calls})

    def tool(self, turn, name, ok):
        self._append({"event": "tool", "turn": turn, "name": name, "ok": ok})

    def end(self, reason, code):
        self._append({"event": "end", "reason": reason, "exit": code})
