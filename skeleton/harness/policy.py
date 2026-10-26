"""Path containment and the command deny list. Sections 3.1 and 3.6."""


class Denied(Exception):
    """A tool argument the harness refuses to act on."""


def contain(workdir, path):
    """Resolve `path` inside `workdir`, or raise Denied with the section 3.1 message.

    Returns the absolute path to use. `path` is always workspace-relative.
    """
    raise NotImplementedError


def command_denied(command):
    """True when `command` must not run at all. Section 3.6."""
    raise NotImplementedError
