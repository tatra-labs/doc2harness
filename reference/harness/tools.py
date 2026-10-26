"""The seven tools. Section 3."""

import json
import os
import subprocess

from .policy import Denied, command_denied, contain
from .schema import ARG_TYPES, REQUIRED


class ToolError(Exception):
    """A tool failed; the message goes back to the model. Section 3."""


def _read(path):
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8")


def _write(path, text):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8"))


def check_args(name, arguments):
    """Raise ToolError for an unknown tool or bad arguments. Section 3."""
    if name not in REQUIRED:
        raise ToolError("unknown tool: " + str(name))
    if not isinstance(arguments, dict):
        arguments = {}
    for key in REQUIRED[name]:
        if key not in arguments:
            raise ToolError("missing argument: " + key)
        if not isinstance(arguments[key], ARG_TYPES[key]):
            raise ToolError("bad argument: " + key)
    return arguments


def call(name, arguments, workdir):
    """Run a checked tool call and return its result string."""
    arguments = check_args(name, arguments)
    try:
        return _dispatch[name](arguments, workdir)
    except Denied as exc:
        raise ToolError(str(exc)) from None


def _read_file(args, workdir):
    path = args["path"]
    full = contain(workdir, path)
    if not os.path.exists(full):
        raise ToolError("no such file: " + path)
    if os.path.isdir(full):
        raise ToolError("not a file: " + path)
    return _read(full)


def _write_file(args, workdir):
    path, content = args["path"], args["content"]
    _write(contain(workdir, path), content)
    return "wrote %d bytes to %s" % (len(content.encode("utf-8")), path)


def _edit_file(args, workdir):
    path, old, new = args["path"], args["old"], args["new"]
    full = contain(workdir, path)
    if not os.path.isfile(full):
        raise ToolError("no such file: " + path)
    text = _read(full)
    found = text.count(old)
    if found == 0:
        raise ToolError("old string not found in " + path)
    if found > 1:
        raise ToolError(
            "old string is not unique in %s: %d occurrences" % (path, found)
        )
    _write(full, text.replace(old, new, 1))
    return "replaced old with new in " + path


def _list_dir(args, workdir):
    path = args["path"]
    full = contain(workdir, path)
    if not os.path.exists(full):
        raise ToolError("no such directory: " + path)
    if not os.path.isdir(full):
        raise ToolError("not a directory: " + path)
    lines = []
    for entry in sorted(os.listdir(full)):
        suffix = "/" if os.path.isdir(os.path.join(full, entry)) else ""
        lines.append(entry + suffix)
    return "\n".join(lines)


def _run_command(args, workdir):
    command = args["command"]
    if command_denied(command):
        raise ToolError("command denied: " + command)
    done = subprocess.run(
        command,
        shell=True,
        cwd=os.path.realpath(workdir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = done.stdout.decode("utf-8", "replace")
    return "exit=%d\n%s" % (done.returncode, output)


def _todo_write(args, workdir):
    items = args["items"]
    for item in items:
        if not isinstance(item, dict) or "text" not in item or "done" not in item:
            raise ToolError("bad argument: items")
        if not isinstance(item["text"], str) or not isinstance(item["done"], bool):
            raise ToolError("bad argument: items")
    target = contain(workdir, os.path.join(".harness", "todo.json"))
    _write(target, json.dumps(items, indent=2) + "\n")
    done = sum(1 for item in items if item["done"])
    return "todo: %d items (%d done)" % (len(items), done)


_dispatch = {
    "read_file": _read_file,
    "write_file": _write_file,
    "edit_file": _edit_file,
    "list_dir": _list_dir,
    "run_command": _run_command,
    "todo_write": _todo_write,
}
