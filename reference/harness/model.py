"""The model transport, with the retry rules of section 5."""

import json
import sys
import urllib.error
import urllib.request


class ModelError(Exception):
    """No attempt produced a usable response. Section 5."""


def _retryable(status):
    return status == 0 or status == 429 or status >= 500


def post(url, body, retries):
    """POST `body` to `url`/v1/chat, retrying per section 5. Returns the JSON object."""
    target = url.rstrip("/") + "/v1/chat"
    payload = json.dumps(body).encode("utf-8")
    attempt = 1
    while True:
        status, raw = 0, None
        try:
            request = urllib.request.Request(
                target, data=payload, headers={"content-type": "application/json"}
            )
            with urllib.request.urlopen(request) as response:
                status = response.status
                raw = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.read()
        except urllib.error.URLError:
            status = 0
        except OSError:
            status = 0
        if status == 200:
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise ModelError("bad response") from None
            if not isinstance(parsed, dict):
                raise ModelError("bad response")
            return parsed
        if _retryable(status) and attempt <= retries:
            attempt += 1
            sys.stderr.write("retry: attempt %d after status %d\n" % (attempt, status))
            sys.stderr.flush()
            continue
        raise ModelError("status %d" % status)
