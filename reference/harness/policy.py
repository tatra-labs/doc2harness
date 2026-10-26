"""Path containment and the command deny list. Sections 3.1 and 3.6."""

import os

DENIED_COMMANDS = frozenset(
    ["rm", "rmdir", "sudo", "shutdown", "reboot", "mkfs", "dd", "chmod", "chown"]
)


class Denied(Exception):
    """A tool argument the harness refuses to act on."""


def contain(workdir, path):
    """Resolve `path` inside `workdir`, or raise Denied. Section 3.1."""
    if os.path.isabs(path):
        raise Denied("path outside workdir: " + path)
    root = os.path.realpath(workdir)
    full = os.path.realpath(os.path.join(root, path))
    if full != root and not full.startswith(root + os.sep):
        raise Denied("path outside workdir: " + path)
    return full


def command_denied(command):
    """True when `command` must not run. Section 3.6."""
    tokens = command.lstrip().split()
    if tokens and tokens[0] in DENIED_COMMANDS:
        return True
    return "rm -rf" in command
