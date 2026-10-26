"""Stage 2: run one frozen candidate harness against one case and collect the four channels."""

import json
import os
import shutil
import subprocess
import tempfile

from .mock import MockModel

DEFAULT_PROMPT = "do the task"
DEFAULT_TIMEOUT = 60


class CandidateError(Exception):
    """The candidate cannot be started at all."""


def load_candidate(root):
    """Read `harness.json` and return the argument vector that starts the harness."""
    manifest = os.path.join(root, "harness.json")
    if not os.path.isfile(manifest):
        raise CandidateError("no harness.json in " + root)
    try:
        with open(manifest, "rb") as fh:
            parsed = json.loads(fh.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise CandidateError("harness.json is not JSON: %s" % exc) from None
    run = parsed.get("run")
    if not isinstance(run, list) or not run or not all(
        isinstance(token, str) for token in run
    ):
        raise CandidateError('harness.json needs a "run" array of strings')
    return run


def _write_files(root, files):
    for relative, content in (files or {}).items():
        target = os.path.join(root, *relative.split("/"))
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(content.encode("utf-8"))


def snapshot(root):
    """Every file under `root`, as POSIX-relative path -> text. The files-on-disk channel."""
    found = {}
    for directory, _subdirs, names in os.walk(root):
        for name in sorted(names):
            full = os.path.join(directory, name)
            relative = os.path.relpath(full, root).replace(os.sep, "/")
            with open(full, "rb") as fh:
                raw = fh.read()
            try:
                found[relative] = raw.decode("utf-8")
            except UnicodeDecodeError:
                found[relative] = "<%d undecodable bytes>" % len(raw)
    return found


def argv_for(case, run, places):
    """The argument vector for one case, with placeholders filled in."""
    if case.get("argv") is not None:
        tokens = list(case["argv"])
    else:
        tokens = [
            "--prompt",
            case.get("prompt", DEFAULT_PROMPT),
            "--workdir",
            "{workdir}",
            "--model-url",
            "{model_url}",
        ]
        tokens += list(case.get("extra", []))
    filled = []
    for token in tokens:
        for key, value in places.items():
            token = token.replace("{%s}" % key, value)
        filled.append(token)
    return run + filled


def run_case(case, candidate, run=None, timeout=DEFAULT_TIMEOUT):
    """Run `case` against the harness at `candidate`. Returns the observed channels."""
    if run is None:
        run = load_candidate(candidate)
    sandbox = tempfile.mkdtemp(prefix="d2h-")
    try:
        workdir = os.path.join(sandbox, "work")
        os.makedirs(workdir)
        _write_files(workdir, case.get("files"))
        prompt_path = os.path.join(sandbox, "prompt.txt")
        with open(prompt_path, "wb") as fh:
            fh.write(case.get("prompt", DEFAULT_PROMPT).encode("utf-8"))
        log_path = os.path.join(sandbox, "transcript.jsonl")

        with MockModel(case.get("script", [])) as mock:
            places = {
                "workdir": os.path.realpath(workdir),
                "model_url": mock.url,
                "prompt_file": prompt_path,
                "log": log_path,
                "outside": os.path.join(sandbox, "escaped.txt"),
            }
            argv = argv_for(case, run, places)
            timed_out = False
            try:
                done = subprocess.run(
                    argv,
                    cwd=candidate,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                )
                code, out, err = done.returncode, done.stdout, done.stderr
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                code, out, err = None, exc.stdout or b"", exc.stderr or b""
            except OSError as exc:
                raise CandidateError("cannot start %r: %s" % (argv[:2], exc)) from None
            requests = list(mock.requests)
            misroutes = list(mock.misroutes)
            content_types = list(mock.content_types)

        log = None
        if os.path.isfile(log_path):
            with open(log_path, "rb") as fh:
                log = fh.read().decode("utf-8", "replace")

        return {
            "exit_code": code,
            "timeout": timed_out,
            "stdout": _text(out),
            "stderr": _text(err),
            "files": snapshot(workdir),
            "outside": sorted(
                name
                for name in os.listdir(sandbox)
                if name not in ("work", "prompt.txt", "transcript.jsonl")
            ),
            "requests": requests,
            "misroutes": misroutes,
            "content_types": content_types,
            "log": log,
            "places": places,
        }
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def _text(raw):
    return raw.decode("utf-8", "replace").replace("\r\n", "\n")
