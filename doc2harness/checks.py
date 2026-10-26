"""The assertion engine: compare the four observable channels against a case's expectations.

Every leaf comparison is one named check. A case passes only when all of its checks pass, which is
the score the paper reports; the per-check numbers are there to show *where* a harness went wrong.
"""

import json

MISSING = object()


def _fill(value, places):
    """Substitute {workdir}, {model_url} and friends anywhere inside an expectation."""
    if isinstance(value, str):
        for key, filling in places.items():
            value = value.replace("{%s}" % key, filling)
        return value
    if isinstance(value, list):
        return [_fill(item, places) for item in value]
    if isinstance(value, dict):
        return {key: _fill(item, places) for key, item in value.items()}
    return value


def _lines(text):
    text = text.replace("\r\n", "\n")
    return [line for line in text.split("\n") if line != ""]


class Report:
    def __init__(self):
        self.checks = []

    def add(self, name, ok, detail=""):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def equal(self, name, want, got):
        self.add(name, want == got, "" if want == got else "want %r, got %r" % (want, got))

    @property
    def passed(self):
        return all(check["ok"] for check in self.checks)

    @property
    def failures(self):
        return [check for check in self.checks if not check["ok"]]


def evaluate(case, observed):
    """Score one observed run against one case. Returns a Report."""
    report = Report()
    expect = _fill(case.get("expect", {}), observed["places"])
    if observed["timeout"]:
        report.add("timeout", False, "the harness did not exit within the time limit")
        return report

    for key, want in expect.items():
        handler = _HANDLERS.get(key)
        if handler is None:
            report.add("unknown-expectation:" + key, False, "no such check")
            continue
        handler(report, want, observed)
    return report


# --- the channels ----------------------------------------------------------------------------


def _exit_code(report, want, observed):
    report.equal("exit_code", want, observed["exit_code"])


def _stdout(report, want, observed):
    report.equal("stdout", list(want), _lines(observed["stdout"]))


def _stdout_has(report, want, observed):
    got = _lines(observed["stdout"])
    for index, line in enumerate(want):
        report.add(
            "stdout_has[%d]" % index,
            line in got,
            "" if line in got else "missing line %r; stdout was %r" % (line, got),
        )


def _stdout_lacks(report, want, observed):
    got = _lines(observed["stdout"])
    for index, line in enumerate(want):
        report.add("stdout_lacks[%d]" % index, line not in got, "unwanted line %r" % line)


def _stdout_prefix(report, want, observed):
    got = _lines(observed["stdout"])
    for index, prefix in enumerate(want):
        hit = any(line.startswith(prefix) for line in got)
        report.add(
            "stdout_prefix[%d]" % index,
            hit,
            "" if hit else "no line starts with %r; stdout was %r" % (prefix, got),
        )


def _stdout_last(report, want, observed):
    got = _lines(observed["stdout"])
    last = got[-1] if got else None
    report.equal("stdout_last", want, last)


def _stderr_has(report, want, observed):
    for index, piece in enumerate(want):
        hit = piece in observed["stderr"]
        report.add(
            "stderr_has[%d]" % index,
            hit,
            "" if hit else "missing %r; stderr was %r" % (piece, observed["stderr"]),
        )


def _stderr_lacks(report, want, observed):
    for index, piece in enumerate(want):
        report.add(
            "stderr_lacks[%d]" % index,
            piece not in observed["stderr"],
            "unwanted %r in stderr" % piece,
        )


def _files(report, want, observed):
    for path, content in want.items():
        got = observed["files"].get(path, MISSING)
        if content is None:
            report.add(
                "files[%s]" % path,
                got is MISSING,
                "" if got is MISSING else "file exists with %r" % got,
            )
        else:
            report.equal("files[%s]" % path, content, None if got is MISSING else got)


def _file_has(report, want, observed):
    for path, pieces in want.items():
        got = observed["files"].get(path)
        for index, piece in enumerate(pieces):
            hit = got is not None and piece in got
            report.add(
                "file_has[%s][%d]" % (path, index),
                hit,
                "" if hit else "missing %r in %r" % (piece, got),
            )


def _only_files(report, want, observed):
    report.equal("only_files", sorted(want), sorted(observed["files"]))


def _outside_clean(report, want, observed):
    if not want:
        return
    report.equal("outside_clean", [], observed["outside"])


def _request_count(report, want, observed):
    report.equal("request_count", want, len(observed["requests"]))


def _misroutes(report, want, observed):
    report.equal("misroutes", want, len(observed["misroutes"]))


def _content_type(report, want, observed):
    seen = observed["content_types"]
    ok = bool(seen) and all(
        (value or "").split(";")[0].strip() == want for value in seen
    )
    report.add("content_type", ok, "" if ok else "content types were %r" % seen)


# --- the request channel ---------------------------------------------------------------------


def _requests(report, want, observed):
    for spec in want:
        index = spec["index"]
        label = "requests[%d]" % index
        if index >= len(observed["requests"]):
            report.add(label, False, "only %d requests arrived" % len(observed["requests"]))
            continue
        body = observed["requests"][index]
        if not isinstance(body, dict):
            report.add(label, False, "request body was not a JSON object")
            continue
        _one_request(report, label, spec, body)


def _one_request(report, label, spec, body):
    messages = body.get("messages")
    if not isinstance(messages, list):
        messages = []
    tools = body.get("tools")
    if not isinstance(tools, list):
        tools = []

    if "keys" in spec:
        report.equal(label + ".keys", sorted(spec["keys"]), sorted(body))
    for key, value in spec.get("field", {}).items():
        report.equal("%s.%s" % (label, key), value, body.get(key, None))
    if "system" in spec:
        first = messages[0] if messages else {}
        report.equal(label + ".system.role", "system", first.get("role"))
        report.equal(label + ".system.content", spec["system"], first.get("content"))
    if "message_count" in spec:
        report.equal(label + ".message_count", spec["message_count"], len(messages))
    if "tool_names" in spec:
        names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
        report.equal(label + ".tool_names", list(spec["tool_names"]), names)
    if "tools_sorted" in spec and spec["tools_sorted"]:
        names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
        report.equal(label + ".tools_sorted", sorted(names), names)
    for name, required in spec.get("tool_required", {}).items():
        tool = _by_name(tools, name)
        got = (tool.get("parameters") or {}).get("required") if tool else None
        report.equal("%s.tool[%s].required" % (label, name), list(required), got)
    for name, properties in spec.get("tool_properties", {}).items():
        tool = _by_name(tools, name)
        found = (tool.get("parameters") or {}).get("properties") if tool else None
        got = sorted(found) if isinstance(found, dict) else None
        report.equal("%s.tool[%s].properties" % (label, name), sorted(properties), got)
    for matcher in spec.get("messages", []):
        _one_message(report, label, matcher, messages)


def _by_name(tools, name):
    for tool in tools:
        if isinstance(tool, dict) and tool.get("name") == name:
            return tool
    return None


def _one_message(report, label, matcher, messages):
    at = matcher["at"]
    where = "%s.messages[%d]" % (label, at)
    try:
        message = messages[at]
    except IndexError:
        report.add(where, False, "only %d messages in the request" % len(messages))
        return
    if not isinstance(message, dict):
        report.add(where, False, "message was not a JSON object")
        return
    for key in ("role", "content", "tool_call_id"):
        if key in matcher:
            report.equal("%s.%s" % (where, key), matcher[key], message.get(key, None))
    if "content_has" in matcher:
        got = message.get("content")
        for index, piece in enumerate(matcher["content_has"]):
            hit = isinstance(got, str) and piece in got
            report.add(
                "%s.content_has[%d]" % (where, index),
                hit,
                "" if hit else "missing %r in %r" % (piece, got),
            )
    if "tool_calls" in matcher:
        report.equal(where + ".tool_calls", matcher["tool_calls"], message.get("tool_calls", None))
    if "no_tool_calls" in matcher and matcher["no_tool_calls"]:
        report.add(
            where + ".no_tool_calls",
            "tool_calls" not in message,
            "the key must be absent when the response carried no tool calls",
        )


# --- the transcript --------------------------------------------------------------------------


def _log_lines(observed):
    if observed["log"] is None:
        return None
    parsed = []
    for line in observed["log"].split("\n"):
        if not line.strip():
            continue
        try:
            parsed.append(json.loads(line))
        except ValueError:
            parsed.append({"_unparseable": line})
    return parsed


def _log(report, want, observed):
    got = _log_lines(observed)
    report.equal("log", list(want), got)


def _log_has(report, want, observed):
    got = _log_lines(observed) or []
    for index, event in enumerate(want):
        report.add(
            "log_has[%d]" % index,
            event in got,
            "missing event %r; transcript was %r" % (event, got),
        )


def _log_order(report, want, observed):
    """The listed events must appear in this relative order."""
    got = _log_lines(observed) or []
    position = -1
    for index, event in enumerate(want):
        found = None
        for offset in range(position + 1, len(got)):
            if got[offset] == event:
                found = offset
                break
        report.add(
            "log_order[%d]" % index,
            found is not None,
            "" if found is not None else "no %r after position %d in %r" % (event, position, got),
        )
        if found is None:
            return
        position = found


def _log_keys(report, want, observed):
    """Every transcript line must carry exactly the keys its event type declares."""
    got = _log_lines(observed) or []
    report.add("log_keys.written", bool(got), "no transcript was written")
    for index, event in enumerate(got):
        kind = event.get("event")
        if kind not in want:
            report.add("log_keys[%d]" % index, False, "unexpected event %r" % event)
            continue
        report.equal("log_keys[%d]" % index, list(want[kind]), list(event))


def _no_log(report, want, observed):
    if not want:
        return
    report.add(
        "no_log",
        observed["log"] is None,
        "a transcript was written without --log: %r" % observed["log"],
    )


_HANDLERS = {
    "exit_code": _exit_code,
    "stdout": _stdout,
    "stdout_has": _stdout_has,
    "stdout_lacks": _stdout_lacks,
    "stdout_prefix": _stdout_prefix,
    "stdout_last": _stdout_last,
    "stderr_has": _stderr_has,
    "stderr_lacks": _stderr_lacks,
    "files": _files,
    "file_has": _file_has,
    "only_files": _only_files,
    "outside_clean": _outside_clean,
    "request_count": _request_count,
    "misroutes": _misroutes,
    "content_type": _content_type,
    "requests": _requests,
    "log": _log,
    "log_has": _log_has,
    "log_order": _log_order,
    "log_keys": _log_keys,
    "no_log": _no_log,
}
