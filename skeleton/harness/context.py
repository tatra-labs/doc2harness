"""The conversation, its token totals and its compaction. Sections 2.2, 2.6 and 4."""


class Conversation:
    """The message list sent to the model, plus the running token totals."""

    def __init__(self, system, prompt):
        raise NotImplementedError

    def add_assistant(self, content, tool_calls):
        """Append the assistant message for one response. Section 2.2."""
        raise NotImplementedError

    def add_tool(self, call_id, content):
        """Append the tool message for one executed call. Section 2.2."""
        raise NotImplementedError

    def count_usage(self, usage):
        """Accumulate one response's usage into the totals. Section 2.6."""
        raise NotImplementedError

    def compact(self, limit):
        """Drop old messages until the budget fits; return how many went. Section 4."""
        raise NotImplementedError
