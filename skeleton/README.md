# Build a HARNESS-1 harness

`DEVELOPMENT.md` is the whole specification. Fill in every module here — or throw the
layout away and write your own, as long as `harness.json` names a command that runs it.

```
harness.json      the argument vector that starts the harness
harness/cli.py    arguments and usage errors        (section 1)
harness/model.py  the transport and its retries     (section 5)
harness/schema.py the system prompt and tool list   (sections 2.1, 2.3)
harness/context.py the conversation and compaction  (sections 2.2, 2.6, 4)
harness/tools.py  the seven tools                   (section 3)
harness/policy.py containment and the deny list     (sections 3.1, 3.6)
harness/logbook.py the transcript                   (section 6)
harness/loop.py   the loop that ties them together  (sections 2.4, 2.5)
```

When it runs, grade it:

```
doc2harness grade .
```
