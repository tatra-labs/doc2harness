"""The seven tools. Section 3."""


class ToolError(Exception):
    """A tool failed. The message is what goes back to the model."""


def check_args(name, arguments):
    """Raise ToolError for an unknown tool or a bad argument. Section 3.

    Returns the arguments to use when they are acceptable.
    """
    raise NotImplementedError


def call(name, arguments, workdir):
    """Run one checked tool call and return its result string, or raise ToolError.

    `finish` is not dispatched here; the loop handles it. Sections 3.2 to 3.7.
    """
    raise NotImplementedError
