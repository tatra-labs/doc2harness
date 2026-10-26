# The HARNESS-1 contract

A *harness* is the program around a language model that turns a prompt into changes on disk: it
assembles requests, exposes tools, executes them, loops, logs, and exits with a status. This document
is the complete specification of one such harness, **HARNESS-1**. It consolidates behaviour that is
common across current coding-agent harnesses — tool results fed back as messages, workspace path
containment, command deny lists, todo tracking, context compaction, transport retries, transcript
logging, token accounting, and distinct exit codes for task failure versus transport failure.

Build it. Every statement below that says **must** is checked by a test case. Nothing else is checked:
wording of tool descriptions, module layout, code style, comments and performance are free.

Read the whole document before writing code. Several requirements are *cross-cutting* — retries,
logging, token accounting, path containment and compaction each touch more than one part of the loop —
and they are where the test cases concentrate.

---

## 1. Entry point

The root of your harness must contain `harness.json`:

```json
{"run": ["python", "-m", "harness"]}
```

`run` is the argument vector that starts the harness. The grader appends the run arguments below to it
and executes it with the harness root as the working directory. Any language is fine as long as
`harness.json` names a command that works on the grading machine.

### 1.1 Arguments

| argument | required | default | meaning |
|---|---|---|---|
| `--prompt TEXT` | yes, unless `--prompt-file` | — | the user's task |
| `--prompt-file PATH` | no | — | read the task from a file, decoded as UTF-8 |
| `--workdir DIR` | yes | — | the only directory the harness may touch |
| `--model-url URL` | yes | — | base URL of the model server |
| `--model-name NAME` | no | `mock-1` | sent as the `model` field |
| `--max-turns N` | no | `10` | hard cap on requests sent to the model |
| `--context-limit N` | no | `100000` | compaction threshold, in characters |
| `--retries N` | no | `3` | retry attempts after a failed request |
| `--log PATH` | no | — | write a JSON-lines transcript |

Arguments are given as two tokens (`--max-turns 4`); `--max-turns=4` need not be supported.

### 1.2 Usage errors

The harness **must** write a line beginning with `usage: ` to **stderr** and **must** exit `2`, without
sending any request, when:

* `--workdir`, `--model-url`, or both prompt options are missing;
* both `--prompt` and `--prompt-file` are given;
* `--prompt-file` names a file that does not exist;
* `--workdir` names a directory that does not exist;
* an unknown `--flag` is given;
* a flag that takes a value is given without one;
* `--max-turns`, `--context-limit` or `--retries` is given a value that is not a non-negative integer.

## 2. The model protocol

One turn is one `POST` to `<model-url>` + `/v1/chat` with header `content-type: application/json` and a
UTF-8 JSON body. The harness **must** send exactly these five keys:

```json
{
  "model": "mock-1",
  "turn": 1,
  "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "add a test"}],
  "tools": [{"name": "edit_file", "description": "...", "parameters": {...}}],
  "max_turns": 10
}
```

* `model` is the `--model-name` value, `max_turns` the `--max-turns` value.
* `turn` counts requests from `1`.
* No other top-level keys **must** be present.

### 2.1 The system prompt

`messages[0]` **must** be `{"role": "system", "content": ...}` where the content is exactly these three
lines joined by `\n`, with no trailing newline:

```
You are a coding agent. You are working in the directory {workdir}.
Use the provided tools to complete the user's task.
Call finish when the task is done or cannot be done.
```

`{workdir}` is replaced by the workspace path resolved to an absolute real path (symbolic links
resolved, as `os.path.realpath` and `realpath(1)` do). The system message **must** appear exactly once,
at index 0, in every request.

### 2.2 The conversation

`messages[1]` **must** be `{"role": "user", "content": <the prompt>}`. After that the harness appends,
in order:

* one assistant message per response received, `{"role": "assistant", "content": <content>}`, with
  `"tool_calls": [...]` added only when the response carried tool calls. The `id`, `name` and
  `arguments` of each call **must** be echoed back unchanged. `content` **must** be echoed unchanged,
  including when it is `null`.
* one message per tool call executed, in call order,
  `{"role": "tool", "tool_call_id": <the call's id>, "content": <result>}`.

Every request after the first therefore carries the whole conversation so far. Key order within a
message object is not checked.

### 2.3 The tool list

`tools` **must** be present in every request and **must** list exactly these seven tools, sorted by
name, each an object with the keys `name`, `description` and `parameters`:

| name | `parameters.properties` keys | `parameters.required` |
|---|---|---|
| `edit_file` | `path`, `old`, `new` | `path`, `old`, `new` |
| `finish` | `success`, `summary` | `success`, `summary` |
| `list_dir` | `path` | `path` |
| `read_file` | `path` | `path` |
| `run_command` | `command` | `command` |
| `todo_write` | `items` | `items` |
| `write_file` | `path`, `content` | `path`, `content` |

`parameters.type` **must** be `"object"`. `required` **must** be in the order given above.
`description` is free text and is not checked.

### 2.4 Responses

A successful response is HTTP `200` with a JSON object:

```json
{"content": "looking now", "tool_calls": [{"id": "c1", "name": "read_file", "arguments": {"path": "a.txt"}}],
 "usage": {"prompt_tokens": 12, "completion_tokens": 4}}
```

`content` may be a string or `null`. `tool_calls` and `usage` may be absent; an absent or partial
`usage` counts as zero for the missing fields.

For each response the harness **must**, in this order:

1. if `content` is a non-empty string, write `assistant: <content>` to stdout;
2. for each tool call in order: write `tool: <name>` to stdout, then execute it as in section 3.

### 2.5 Ending the loop

* A response with **no** tool calls ends the loop: the harness **must** write `done: <content>` to
  stdout (empty after the space if `content` is `null` or empty) and exit `0`.
* A `finish` tool call ends the loop: the harness **must** write `done: <summary>` to stdout and exit
  `0` when `success` is `true`, `1` when it is `false`. Tool calls that follow `finish` in the same
  response **must not** be executed, and no further request **must** be sent.
* Reaching `--max-turns` requests without either of the above: the harness **must** write
  `max turns exceeded` to stderr and exit `1`.

### 2.6 Token accounting

Immediately before exiting with code `0` or `1`, and as the **last** line it writes to stdout, the
harness **must** write

```
tokens: prompt=<P> completion=<C>
```

where `P` and `C` are the sums of `usage.prompt_tokens` and `usage.completion_tokens` over every
successful response of the run. No `tokens:` line **must** be written when exiting `2` or `3`.

## 3. The tools

Each tool returns a result string. On success the harness **must** append it unchanged as the tool
message content. On failure the harness **must** append `ERROR: <message>` as the tool message content,
**must** write `error: <message>` to stdout, and **must** carry on with the next tool call or turn: a
failing tool never ends the run.

These failures are shared by all tools and are checked before any tool-specific behaviour:

| condition | message |
|---|---|
| the name is not one of the seven | `unknown tool: <name>` |
| a required argument is absent | `missing argument: <name>` |
| a required argument has the wrong JSON type | `bad argument: <name>` |

Expected types are string for `path`, `old`, `new`, `content`, `command`, `summary`; boolean for
`success`; array for `items`.

### 3.1 Path containment

`path` arguments are relative to the workspace. Before using one, the harness **must** reject it with
`path outside workdir: <path>` when it is an absolute path, or when joining it to the workspace and
resolving the result (as `os.path.realpath` does, without requiring the file to exist) lands outside the
resolved workspace path. `a/../b` is inside; `../b` and `/etc/passwd` are not.

### 3.2 `read_file(path)`

Returns the file's bytes decoded as UTF-8. Failures: `no such file: <path>` when it does not exist,
`not a file: <path>` when it is a directory.

### 3.3 `write_file(path, content)`

Writes `content` as UTF-8, creating parent directories, truncating an existing file. Returns
`wrote <N> bytes to <path>`, where `N` is the length of the UTF-8 encoding.

### 3.4 `edit_file(path, old, new)`

Replaces the single occurrence of `old` with `new`. Returns `replaced old with new in <path>`.
Failures: `no such file: <path>`; `old string not found in <path>`; and
`old string is not unique in <path>: <N> occurrences` when `old` occurs `N > 1` times, counted as
non-overlapping occurrences. The file **must not** change when the edit fails.

### 3.5 `list_dir(path)`

Returns the directory's entries sorted by name, one per line, each directory suffixed with `/`, with no
trailing newline; an empty directory returns the empty string. Failures: `no such directory: <path>`
when it does not exist, `not a directory: <path>` when it is a file.

### 3.6 `run_command(command)`

Runs `command` through the platform shell with the workspace as the working directory and returns

```
exit=<code>
<output>
```

— that is, `exit=<code>`, a newline, then the command's stdout and stderr interleaved as produced,
decoded as UTF-8 with undecodable bytes replaced. The command **must** be denied, before it runs, with
`command denied: <command>` when its first whitespace-separated token (after leading whitespace is
stripped) is one of

```
rm  rmdir  sudo  shutdown  reboot  mkfs  dd  chmod  chown
```

or when the command contains the substring `rm -rf` anywhere.

### 3.7 `todo_write(items)`

`items` is an array of objects with a string `text` and a boolean `done`. The harness **must** write
`<workdir>/.harness/todo.json` containing the array as JSON with two-space indentation and a trailing
newline (`json.dumps(items, indent=2) + "\n"`), creating `.harness/` if needed, and return
`todo: <N> items (<M> done)` with `N` the number of items and `M` how many have `done` true.
An item that is not an object, or lacks `text` or `done`, fails the call with `bad argument: items`,
and the file **must not** be written. `.harness/` **must not** be created by any other part of the
harness.

### 3.8 `finish(success, summary)`

Ends the run as described in section 2.5. It produces no tool message and no `tool` transcript
event, and `tool: finish` is still written to stdout. If its arguments fail the checks at the top of
section 3 it is an ordinary tool failure and the run continues.

## 4. Compaction

Before sending every request *after the first*, the harness **must** measure the conversation as

```
budget = sum(len(json.dumps(m, sort_keys=True)) for m in messages[1:])
```

and, while `budget > --context-limit` and more than four messages remain after the system message,
drop the oldest message after the system message and measure again. When at least one message has been
dropped the harness **must** then also drop the new oldest message if its role is `tool`, insert
`{"role": "user", "content": "[compacted: dropped <N> messages]"}` at index 1 with `N` the total number
dropped, and write `compact: dropped <N> messages` to stdout. The inserted message is an ordinary part
of the conversation from then on and counts towards later budgets.

## 5. Transport failures

A request *attempt* fails when the connection fails or the response status is not `200`. The harness
**must** retry an attempt that failed with status `429`, with a status of `500` or above, or with a
connection error, up to `--retries` further attempts. Before each retry it **must** write

```
retry: attempt <k> after status <code>
```

to **stderr**, where `k` counts the attempt about to be made, from `2`, and `<code>` is the status just
seen, or `0` for a connection error. Retries carry the identical body and do not increment `turn`.

The harness **must not** retry any other status, and **must not** retry a `200` whose body is not a JSON
object.

When no attempt succeeds, the harness **must** write `model error: status <code>` to stderr — `<code>`
being the last status seen, or `0` for a connection error — and exit `3`. For a `200` with an
unparseable or non-object body it **must** write `model error: bad response` and exit `3`.

## 6. The transcript

With `--log PATH` the harness **must** append one JSON object per line to `PATH`, creating the file and
its parent directories if needed, in the order the events happen, with exactly these keys in this
order and no others:

| event | object |
|---|---|
| a request is about to be sent (once per turn, not per attempt) | `{"event": "request", "turn": <n>, "messages": <count>}` |
| a response was received | `{"event": "response", "turn": <n>, "tool_calls": <count>}` |
| a tool call finished | `{"event": "tool", "turn": <n>, "name": <name>, "ok": <bool>}` |
| the run is about to exit | `{"event": "end", "reason": <reason>, "exit": <code>}` |

`messages` is the number of messages in the request body. `ok` is `false` for the failures of section 3.
`reason` is `"finish"`, `"text"`, `"max_turns"`, `"model_error"` or `"usage"`. Lines are compact JSON
(`json.dumps`'s default separators) and the file ends with a newline. An `end` event **must** be written
for every exit, including usage errors, when `--log` is given.

## 7. Exit codes

| code | when |
|---|---|
| `0` | the loop ended on a text-only response, or on `finish` with `success` true |
| `1` | `finish` with `success` false, or `--max-turns` reached |
| `2` | a usage error from section 1.2 |
| `3` | a transport failure from section 5 |

## 8. How the harness is graded

Each case runs the harness once, as its own process, with a fresh empty workspace and a fresh model
server that answers from a fixed script and records what it was sent. Nothing else is running, no
other request reaches the server, and the same case always produces the same four channels.

Two conveniences, so that nothing turns on the platform:

* captured stdout and stderr have `
` folded to `
` before anything is compared, so writing
  text lines the ordinary way is safe on Windows;
* `run_command` output is only ever checked for the substrings a command is expected to produce,
  never for an exact shell transcript.

Everything else is compared exactly, including every byte the harness writes to a file.

## 9. Where the harness must not go

The harness **must not** write, outside `--workdir`, anything but the `--log` file. It **must not**
read the environment for configuration, and **must not** require network access other than
`--model-url`.
