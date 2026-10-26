"""The agent loop. Sections 2.4, 2.5, 2.6 and 3."""

import os
import sys

from .context import Conversation
from .model import ModelError, post
from .schema import SYSTEM_PROMPT, TOOLS
from .tools import ToolError, call, check_args


def _out(text):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _tokens(conversation):
    _out(
        "tokens: prompt=%d completion=%d"
        % (conversation.prompt_tokens, conversation.completion_tokens)
    )


def run(options, log):
    workdir = os.path.realpath(options["workdir"])
    conversation = Conversation(
        SYSTEM_PROMPT.format(workdir=workdir), options["prompt"]
    )
    for turn in range(1, options["max_turns"] + 1):
        if turn > 1:
            dropped = conversation.compact(options["context_limit"])
            if dropped:
                _out("compact: dropped %d messages" % dropped)
        body = {
            "model": options["model_name"],
            "turn": turn,
            "messages": conversation.messages,
            "tools": TOOLS,
            "max_turns": options["max_turns"],
        }
        log.request(turn, len(conversation.messages))
        try:
            response = post(options["model_url"], body, options["retries"])
        except ModelError as exc:
            sys.stderr.write("model error: %s\n" % exc)
            log.end("model_error", 3)
            return 3

        calls = response.get("tool_calls") or []
        if not isinstance(calls, list):
            calls = []
        log.response(turn, len(calls))
        conversation.count_usage(response.get("usage"))

        content = response.get("content")
        if isinstance(content, str) and content:
            _out("assistant: " + content)
        conversation.add_assistant(content, calls or None)

        if not calls:
            _out("done: " + (content if isinstance(content, str) else ""))
            _tokens(conversation)
            log.end("text", 0)
            return 0

        for one in calls:
            if not isinstance(one, dict):
                one = {}
            name = one.get("name")
            _out("tool: %s" % name)
            if name == "finish":
                try:
                    arguments = check_args("finish", one.get("arguments"))
                except ToolError as exc:
                    _failed(conversation, log, turn, name, one, exc)
                    continue
                code = 0 if arguments["success"] else 1
                _out("done: " + arguments["summary"])
                _tokens(conversation)
                log.end("finish", code)
                return code
            try:
                result = call(name, one.get("arguments"), workdir)
            except ToolError as exc:
                _failed(conversation, log, turn, name, one, exc)
                continue
            log.tool(turn, name, True)
            conversation.add_tool(one.get("id"), result)

    sys.stderr.write("max turns exceeded\n")
    _tokens(conversation)
    log.end("max_turns", 1)
    return 1


def _failed(conversation, log, turn, name, one, exc):
    """A tool call failed: report it, feed it back, and carry on. Section 3."""
    _out("error: %s" % exc)
    log.tool(turn, name, False)
    conversation.add_tool(one.get("id"), "ERROR: %s" % exc)
