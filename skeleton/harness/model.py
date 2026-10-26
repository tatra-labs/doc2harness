"""The model transport. Section 5."""


class ModelError(Exception):
    """No attempt produced a usable response. The message is what stderr reports."""


def post(url, body, retries):
    """POST `body` to `url`/v1/chat and return the decoded JSON object.

    Retries what section 5 says to retry, reports each retry on stderr, and raises
    ModelError("status <code>") or ModelError("bad response") when it gives up.
    """
    raise NotImplementedError
