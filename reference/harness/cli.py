"""Argument handling. Sections 1.1 and 1.2."""

import os
import sys

from . import loop
from .logbook import Logbook

VALUE_FLAGS = (
    "--prompt",
    "--prompt-file",
    "--workdir",
    "--model-url",
    "--model-name",
    "--max-turns",
    "--context-limit",
    "--retries",
    "--log",
)

INTEGER_FLAGS = {"--max-turns": 10, "--context-limit": 100000, "--retries": 3}


def _parse(argv):
    """Split argv into a flag table, or a usage message. Section 1.1."""
    given = {}
    index = 0
    while index < len(argv):
        token = argv[index]
        if token not in VALUE_FLAGS:
            return given, "usage: unknown argument %s" % token
        if index + 1 >= len(argv):
            return given, "usage: %s needs a value" % token
        given[token] = argv[index + 1]
        index += 2
    return given, None


def _validate(given):
    """Return a usage message, or None. Section 1.2."""
    for flag in ("--workdir", "--model-url"):
        if flag not in given:
            return "usage: %s is required" % flag
    has_prompt = "--prompt" in given
    has_file = "--prompt-file" in given
    if has_prompt and has_file:
        return "usage: --prompt and --prompt-file are mutually exclusive"
    if not has_prompt and not has_file:
        return "usage: --prompt or --prompt-file is required"
    if has_file and not os.path.isfile(given["--prompt-file"]):
        return "usage: no such prompt file: %s" % given["--prompt-file"]
    if not os.path.isdir(given["--workdir"]):
        return "usage: no such directory: %s" % given["--workdir"]
    for flag in INTEGER_FLAGS:
        if flag in given and not given[flag].isdigit():
            return "usage: %s needs a non-negative integer" % flag
    return None


def main(argv):
    given, error = _parse(argv)
    log = Logbook(given.get("--log"))
    if error is None:
        error = _validate(given)
    if error is not None:
        sys.stderr.write(error + "\n")
        log.end("usage", 2)
        return 2

    if "--prompt" in given:
        prompt = given["--prompt"]
    else:
        with open(given["--prompt-file"], "rb") as fh:
            prompt = fh.read().decode("utf-8")

    options = {
        "prompt": prompt,
        "workdir": given["--workdir"],
        "model_url": given["--model-url"],
        "model_name": given.get("--model-name", "mock-1"),
    }
    for flag, default in INTEGER_FLAGS.items():
        key = flag[2:].replace("-", "_")
        options[key] = int(given[flag]) if flag in given else default
    return loop.run(options, log)
