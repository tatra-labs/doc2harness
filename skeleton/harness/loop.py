"""The agent loop. Sections 2.4, 2.5, 2.6 and 3."""


def run(options, log):
    """Drive the conversation until it ends, and return the process exit code.

    `options` carries prompt, workdir, model_url, model_name, max_turns, context_limit
    and retries. `log` is a Logbook. Sections 2.4 and 2.5 fix what is written to stdout,
    in what order, and which exit code each ending produces.
    """
    raise NotImplementedError
