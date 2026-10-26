"""The conversation and its compaction. Sections 2.2, 2.6 and 4."""

import json


class Conversation:
    def __init__(self, system, prompt):
        self.messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def add_assistant(self, content, tool_calls):
        message = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        self.messages.append(message)

    def add_tool(self, call_id, content):
        self.messages.append(
            {"role": "tool", "tool_call_id": call_id, "content": content}
        )

    def count_usage(self, usage):
        """Accumulate one response's usage. Section 2.6."""
        if not isinstance(usage, dict):
            return
        for key, attribute in (
            ("prompt_tokens", "prompt_tokens"),
            ("completion_tokens", "completion_tokens"),
        ):
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                setattr(self, attribute, getattr(self, attribute) + value)

    def _budget(self):
        return sum(len(json.dumps(m, sort_keys=True)) for m in self.messages[1:])

    def compact(self, limit):
        """Drop old messages until the budget fits. Returns how many went. Section 4."""
        dropped = 0
        while self._budget() > limit and len(self.messages) - 1 > 4:
            del self.messages[1]
            dropped += 1
        if not dropped:
            return 0
        if len(self.messages) > 1 and self.messages[1]["role"] == "tool":
            del self.messages[1]
            dropped += 1
        self.messages.insert(
            1,
            {"role": "user", "content": "[compacted: dropped %d messages]" % dropped},
        )
        return dropped
