"""The JSON-lines transcript. Section 6."""


class Logbook:
    """Writes the transcript, or nothing at all when --log was not given."""

    def __init__(self, path):
        raise NotImplementedError

    def request(self, turn, messages):
        raise NotImplementedError

    def response(self, turn, tool_calls):
        raise NotImplementedError

    def tool(self, turn, name, ok):
        raise NotImplementedError

    def end(self, reason, code):
        raise NotImplementedError
