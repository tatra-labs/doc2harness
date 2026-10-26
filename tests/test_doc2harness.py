"""The grader's own tests.

Two of them are the benchmark's integrity checks: the reference harness must pass every case,
and the null harness must fail every case. If a case ever passes for the null harness it can be
passed without doing any work, and it is not a test.
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from doc2harness.checks import _HANDLERS, evaluate  # noqa: E402
from doc2harness.cli import main as cli_main  # noqa: E402
from doc2harness.mock import MockModel  # noqa: E402
from doc2harness.runner import CandidateError, load_candidate, run_case  # noqa: E402
from doc2harness.score import grade, load_cases  # noqa: E402

REFERENCE = os.path.join(ROOT, "reference")
CONTROLS = os.path.join(ROOT, "controls")
JOBS = 8

# Which rule each control breaks, and the categories whose cases must therefore fail.
CONTROL_RULES = {
    "no_retry": "transport",
    "no_tokens": "tokens",
    "fatal_tool_error": "tools",
    "silent_tool_error": "tools",
    "open_paths": "paths",
    "unsorted_tools": "protocol",
    "no_compaction": "compaction",
    "tool_results_as_user": "protocol",
    "no_tool_events": "transcript",
    "lenient_arguments": "tools",
}


@pytest.fixture(scope="module")
def cases():
    return load_cases()


# --- the cases themselves --------------------------------------------------------------------


def test_every_case_is_well_formed(cases):
    seen = set()
    for case in cases:
        assert case["id"] not in seen, "duplicate case id %s" % case["id"]
        seen.add(case["id"])
        assert case.get("why"), "%s has no why" % case["id"]
        expect = case["expect"]
        assert expect, "%s expects nothing" % case["id"]
        for key in expect:
            assert key in _HANDLERS, "%s uses unknown check %r" % (case["id"], key)
        assert set(expect) - {"exit_code"}, (
            "%s checks only the exit code, which is too weak" % case["id"]
        )


def test_case_count_is_what_the_readme_says(cases):
    assert len(cases) == 110


# --- the two integrity checks ---------------------------------------------------------------


def test_the_reference_harness_passes_every_case(cases):
    report = grade(REFERENCE, cases, jobs=JOBS)
    failed = [result["id"] for result in report["results"] if not result["passed"]]
    assert failed == [], "the reference harness failed %s" % failed
    assert report["checks_passed"] == report["checks"]


def test_a_harness_that_does_nothing_passes_nothing(cases):
    report = grade(os.path.join(CONTROLS, "null"), cases, jobs=JOBS)
    vacuous = [result["id"] for result in report["results"] if result["passed"]]
    assert vacuous == [], "these cases can be passed without doing anything: %s" % vacuous


# --- the controls ---------------------------------------------------------------------------


@pytest.mark.parametrize("control,category", sorted(CONTROL_RULES.items()))
def test_each_control_fails_the_rule_it_breaks(control, category):
    subset = load_cases(category + "/")
    assert subset, "no cases in category %s" % category
    report = grade(os.path.join(CONTROLS, control), subset, jobs=JOBS)
    assert report["cases_passed"] < report["cases"], (
        "%s broke a rule in %s but passed every case there" % (control, category)
    )


def test_the_skeleton_does_not_pass(tmp_path):
    target = str(tmp_path / "candidate")
    assert cli_main(["new", target]) == 0
    assert os.path.isfile(os.path.join(target, "harness.json"))
    assert os.path.isfile(os.path.join(target, "DEVELOPMENT.md"))
    report = grade(target, load_cases("loop/"), jobs=JOBS)
    assert report["cases_passed"] == 0


# --- the runner and the mock ----------------------------------------------------------------


def test_run_case_reports_the_four_channels():
    case = {
        "id": "t/t",
        "files": {"a.txt": "hello\n"},
        "extra": ["--log", "{log}"],
        "script": [
            {"tool_calls": [{"id": "c1", "name": "read_file", "arguments": {"path": "a.txt"}}]},
            {"tool_calls": [{"id": "f", "name": "finish", "arguments": {"success": True, "summary": "ok"}}]},
        ],
        "expect": {},
    }
    observed = run_case(case, REFERENCE)
    assert observed["exit_code"] == 0
    assert observed["files"] == {"a.txt": "hello\n"}
    assert len(observed["requests"]) == 2
    assert observed["misroutes"] == []
    assert observed["log"].count("\n") == 6
    assert "tool: read_file" in observed["stdout"]


def test_an_exhausted_script_does_not_hang():
    case = {"id": "t/t", "script": [], "expect": {}}
    observed = run_case(case, REFERENCE, timeout=30)
    assert observed["timeout"] is False
    assert observed["exit_code"] == 0
    assert "done: script exhausted" in observed["stdout"]


def test_the_mock_refuses_the_wrong_path():
    import urllib.error
    import urllib.request

    with MockModel([{"content": "hi"}]) as mock:
        request = urllib.request.Request(
            mock.url + "/v1/completions", data=b"{}", headers={"content-type": "application/json"}
        )
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        assert caught.value.code == 404
        assert mock.misroutes == ["/v1/completions"]
        assert mock.requests == []


def test_a_timeout_fails_every_check(tmp_path):
    report = evaluate(
        {"expect": {"exit_code": 0}},
        {"timeout": True, "places": {}},
    )
    assert not report.passed
    assert report.failures[0]["name"] == "timeout"


def test_a_candidate_needs_a_manifest(tmp_path):
    with pytest.raises(CandidateError):
        load_candidate(str(tmp_path))
    (tmp_path / "harness.json").write_text('{"run": []}')
    with pytest.raises(CandidateError):
        load_candidate(str(tmp_path))
    (tmp_path / "harness.json").write_text('{"run": ["python", "-m", "harness"]}')
    assert load_candidate(str(tmp_path)) == ["python", "-m", "harness"]


# --- the command line -----------------------------------------------------------------------


def test_pack_carries_the_spec_and_the_skeleton(tmp_path):
    out = str(tmp_path / "prompt.md")
    assert cli_main(["pack", "--out", out]) == 0
    text = open(out, encoding="utf-8").read()
    assert "# The HARNESS-1 contract" in text
    assert "harness/loop.py" in text
    assert "harness.json" in text
    assert len(text) > 10000


def test_grade_exits_nonzero_for_a_failing_harness():
    done = subprocess.run(
        [sys.executable, "-m", "doc2harness", "grade", os.path.join(CONTROLS, "null"),
         "--only", "loop/", "-j", str(JOBS)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert done.returncode == 1
    assert b"FAIL" in done.stdout


def test_grade_writes_a_report(tmp_path):
    out = str(tmp_path / "report.json")
    code = cli_main(["grade", REFERENCE, "--only", "tokens/", "--json", out, "-j", str(JOBS)])
    assert code == 0
    report = json.loads(open(out, encoding="utf-8").read())
    assert report["cases"] == report["cases_passed"] > 0
    assert report["categories"]["tokens"]["cases"] > 0
