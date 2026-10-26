"""The controls: one deliberately wrong harness per rule.

`null` does nothing at all and must fail every case — that is the positive control the
paper asks for, the thing that proves no case can be passed vacuously. The others are the
reference harness with exactly one rule broken, and each must fail only the cases about
that rule. Their measured scores are the table in the README.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "reference")))


def break_no_retry():
    """Section 5: never retry anything."""
    from harness import model

    model._retryable = lambda status: False


def break_no_tokens():
    """Section 2.6: never report the token totals."""
    from harness import loop

    loop._tokens = lambda conversation: None


def break_fatal_tool_error():
    """Section 3: let a tool failure end the run."""
    from harness import loop

    def fatal(conversation, log, turn, name, one, exc):
        sys.stderr.write("tool failed: %s\n" % exc)
        raise SystemExit(1)

    loop._failed = fatal


def break_silent_tool_error():
    """Section 3: report a tool failure but do not tell the model about it."""
    from harness import loop

    def silent(conversation, log, turn, name, one, exc):
        print("error: %s" % exc)
        log.tool(turn, name, False)

    loop._failed = silent


def break_open_paths():
    """Section 3.1: let a path argument point anywhere."""
    from harness import tools

    tools.contain = lambda workdir, path: os.path.join(
        os.path.realpath(workdir), path.lstrip("/\\")
    )


def break_unsorted_tools():
    """Section 2.3: send the tool list in the wrong order."""
    from harness import loop, schema

    loop.TOOLS = list(reversed(schema.TOOLS))


def break_no_compaction():
    """Section 4: never compact."""
    from harness import context

    context.Conversation.compact = lambda self, limit: 0


def break_tool_results_as_user():
    """Section 2.2: send tool results as user messages."""
    from harness import context

    def as_user(self, call_id, content):
        self.messages.append({"role": "user", "content": content})

    context.Conversation.add_tool = as_user


def break_no_tool_events():
    """Section 6: leave the tool events out of the transcript."""
    from harness import logbook

    logbook.Logbook.tool = lambda self, turn, name, ok: None


def break_lenient_arguments():
    """Section 3: accept whatever arguments arrive."""
    from harness import loop, tools

    lenient = lambda name, arguments: (
        arguments if isinstance(arguments, dict) else {}
    )
    tools.check_args = lenient
    loop.check_args = lenient


BREAKS = {
    "no_retry": break_no_retry,
    "no_tokens": break_no_tokens,
    "fatal_tool_error": break_fatal_tool_error,
    "silent_tool_error": break_silent_tool_error,
    "open_paths": break_open_paths,
    "unsorted_tools": break_unsorted_tools,
    "no_compaction": break_no_compaction,
    "tool_results_as_user": break_tool_results_as_user,
    "no_tool_events": break_no_tool_events,
    "lenient_arguments": break_lenient_arguments,
}


def main():
    which, argv = sys.argv[1], sys.argv[2:]
    if which == "null":
        return 0
    BREAKS[which]()
    from harness.cli import main as harness_main

    return harness_main(argv)


if __name__ == "__main__":
    sys.exit(main())
