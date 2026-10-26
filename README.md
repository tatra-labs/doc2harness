<h1 align="center">doc2harness</h1>

<p align="center">
  <a href="https://github.com/tatra-labs/doc2harness/actions/workflows/tests.yml"><img src="https://github.com/tatra-labs/doc2harness/actions/workflows/tests.yml/badge.svg" alt="tests"></a>
  <a href="https://arxiv.org/abs/2610.20344"><img src="https://img.shields.io/badge/arXiv-2610.20344-b31b1b.svg" alt="arXiv"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/dependencies-none-success.svg" alt="no dependencies">
</p>

<p align="center"><b>Can your coding agent build the thing it runs inside?</b><br>
Hand it a specification, let it write an agent harness, then grade the harness by running it
against a scripted model. Deterministic, offline, no API key.</p>

Every agent benchmark fixes the harness — the tools, the loop, the state, the retries — and measures
the model inside it. [*Doc2Harness*](https://arxiv.org/abs/2610.20344) (Ge, Liu, Gao et al.,
October 2026) turns that around and asks the model to **build the harness**, then drives the frozen
result end to end with a scripted mock model and scores four observable channels. Across nineteen
frontier models the best scored 53.05% and the weakest 27.44%, and failures clustered not on single
functions but on *how cross-cutting behaviour was split across modules*. No code was released.

**doc2harness** is an open, dependency-free implementation of that idea: a specification to build
from, a scripted model server, 110 test cases over the four channels, and the controls that prove the
cases mean something.

## The scoreboard

Every number below is produced by this repository on this repository — `python scripts/controls_table.py`
reproduces the table.

| harness | cases passed | checks passed | categories with a failure |
|---|---:|---:|---|
| `reference` — a complete implementation | **110/110** | 383/383 | none |
| `null` — does nothing at all | **0/110** | 120/310 | all ten |
| `fatal_tool_error` — a failing tool ends the run | 83/110 | 309/375 | commands, loop, paths, tools, transcript |
| `no_tokens` — never reports token totals | 91/110 | 364/383 | compaction, loop, tokens |
| `tool_results_as_user` — tool results sent as user messages | 101/110 | 361/383 | commands, compaction, protocol, tools |
| `silent_tool_error` — tool failure never reaches the model | 101/110 | 366/378 | commands, paths, tools |
| `no_retry` — never retries a 500 | 103/110 | 363/383 | tokens, transcript, transport |
| `lenient_arguments` — accepts any tool arguments | 104/110 | 368/383 | commands, tools |
| `open_paths` — no workspace containment | 105/110 | 376/383 | paths |
| `no_tool_events` — transcript misses tool events | 106/110 | 377/381 | transcript |
| `no_compaction` — never compacts the conversation | 108/110 | 375/383 | compaction |
| `unsorted_tools` — tool list in the wrong order | 108/110 | 380/383 | protocol |

The first two rows are the benchmark's integrity. `reference` is a complete harness written against
the specification, so a perfect score is reachable. `null` is the **positive control** the paper asks
for: a program that exits immediately. It must score zero, because a case it passed would be a case
that can be passed without doing anything — and the test suite fails if one ever does.

Each remaining row is `reference` with exactly one rule broken. They are the evidence that the cases
localise: breaking containment costs you the `paths` cases and nothing else, while letting a tool
failure kill the run costs you 27 cases in five categories. That second number is the paper's point
about cross-cutting behaviour, in miniature.

**No model-built harness has been graded here yet.** That is the open part: build one and send the
score.

## Grade a harness

```bash
git clone https://github.com/tatra-labs/doc2harness && cd doc2harness
pip install -e .

doc2harness grade reference -j 8          # 110/110 in about nine seconds
doc2harness grade controls/null           # 0/110
```

A candidate is any directory with a `harness.json` naming the command that starts it:

```json
{"run": ["python", "-m", "harness"]}
```

Any language, as long as that command runs. The grader appends `--prompt`, `--workdir`,
`--model-url` and whatever flags a case needs, with the candidate directory as the working
directory.

## Have an agent build one

```bash
doc2harness pack --out BUILD.md      # the task, the full specification, the skeleton
doc2harness new candidate            # or: the skeleton and spec in a directory to fill in
```

`BUILD.md` is one self-contained prompt. Hand it to Claude Code, Codex, Cursor, an API loop, or a
person; let them work; then

```bash
doc2harness grade candidate -v       # -v prints the failing checks
```

Grading needs no API key and no network: the whole second stage is this repository and a scripted
server on localhost. The only thing a model is needed for is stage one, writing the harness.

## What is being graded

[`HARNESS-1`](doc2harness/spec/DEVELOPMENT.md) is the specification — one document, nine sections,
consolidating behaviour that current coding-agent harnesses share. A harness that satisfies it:

* parses nine flags and distinguishes four exit codes — success, task failure, usage error, transport
  failure;
* assembles requests with a fixed system prompt, a seven-tool schema sorted by name, and the whole
  accumulated conversation with tool results as `role: tool` messages;
* implements `read_file`, `write_file`, `edit_file`, `list_dir`, `run_command`, `todo_write` and
  `finish`, each with exact result strings and exact failure messages;
* keeps every path inside the workspace and refuses a deny list of commands;
* feeds a tool failure back to the model and **carries on**;
* retries a 429 or a 5xx, does not retry a 404, and reports each retry;
* compacts the conversation when it outgrows a character budget, never leaving an orphaned tool
  result at the front;
* writes a JSON-lines transcript with one documented shape per event;
* and totals the tokens it was charged, as the last line it prints.

The last five are the cross-cutting ones. They are where the cases concentrate and where, in the
paper, frontier models lost.

## The four channels

Each case runs the candidate once, in a fresh empty workspace, against a fresh model server that
replays a fixed script and records what it was sent. Then:

| channel | what is compared |
|---|---|
| requests to the model | body keys, `turn`, the system prompt, every message's role, content and `tool_call_id`, the tool schemas |
| files on disk | exact bytes of every file, and that nothing else was created |
| exit code | the four codes of section 7 |
| command output | exact stdout lines and their order, exact stderr content |

110 cases, 383 checks. A case passes only when every one of its checks passes — that is the headline
number, as in the paper. The per-check count is a diagnostic: it tells you how close a failing
harness was.

```
$ doc2harness grade reference

category        cases passed   checks
cli                13     13   38/38
commands            9      9   26/26
compaction          4      4   28/28
loop               11     11   32/32
paths               7      7   17/17
protocol           15     15   74/74
tokens              7      7   14/14
tools              23     23   75/75
transcript         10     10   27/27
transport          11     11   45/45

110/110 cases (100.00%), 383/383 checks
```

## Writing a case

Cases are JSON, in [`doc2harness/cases/`](doc2harness/cases). A script of model responses goes in,
expectations over the four channels come out:

```json
{
  "name": "edit/not_unique",
  "why": "an ambiguous edit fails, counts the matches, and changes nothing",
  "files": {"a.txt": "x\nx\nx\n"},
  "script": [
    {"tool_calls": [{"id": "c1", "name": "edit_file",
                     "arguments": {"path": "a.txt", "old": "x", "new": "y"}}]},
    {"tool_calls": [{"id": "f", "name": "finish",
                     "arguments": {"success": true, "summary": "ok"}}]}
  ],
  "expect": {
    "exit_code": 0,
    "files": {"a.txt": "x\nx\nx\n"},
    "stdout_has": ["error: old string is not unique in a.txt: 3 occurrences"],
    "requests": [{"index": 1, "messages": [
      {"at": 3, "content": "ERROR: old string is not unique in a.txt: 3 occurrences"}]}]
  }
}
```

A script entry can also be `{"status": 500}` or `{"raw": "not json"}`, which is how the transport
cases are written. Twenty-one kinds of expectation are available; `doc2harness/checks.py` is the
list. New cases must keep `reference` at 110/110 and `null` at zero — `pytest` enforces both.

## Differences from the paper

This is an independent implementation of the paper's idea, not its code, and the two are not
comparable as numbers:

* the specification here is written from scratch and is shorter than the paper's document, which
  consolidated twelve frontier harnesses;
* 110 cases rather than 328, and the scoring is pass-or-fail per case with no partial credit;
* isolation is a fresh temporary workspace and a fresh server per case, rather than a container per
  case. Run the grader itself in a container if you want the paper's guarantee; nothing in it
  assumes otherwise;
* the paper's stage one ran the build inside a fixed builder harness. Here stage one is whatever you
  like — `doc2harness pack` emits the prompt and gets out of the way.

Determinism is the same, and it is the point: same candidate, same scores, every run.

## Licence

MIT. The specification, the cases and the reference harness are all in this repository; the paper is
[arXiv:2610.20344](https://arxiv.org/abs/2610.20344).
