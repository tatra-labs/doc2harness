"""Load the cases and grade a candidate harness against them."""

import json
import os
from concurrent.futures import ThreadPoolExecutor

from .checks import evaluate
from .runner import load_candidate, run_case

CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases")


def load_cases(only=None):
    """Every case, in file order, optionally filtered by a substring of category/name."""
    cases = []
    for filename in sorted(os.listdir(CASES_DIR)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(CASES_DIR, filename), "rb") as fh:
            group = json.loads(fh.read().decode("utf-8"))
        for case in group["cases"]:
            case = dict(case)
            case["category"] = group["category"]
            prefix = group["category"] + "/"
            case["id"] = (
                case["name"]
                if case["name"].startswith(prefix)
                else prefix + case["name"]
            )
            cases.append(case)
    if only:
        cases = [case for case in cases if only in case["id"]]
    return cases


def grade(candidate, cases=None, timeout=60, on_result=None, jobs=1):
    """Run every case against the harness at `candidate` and return the scored report.

    Cases are independent: each gets its own workspace and its own model server, so they
    can run concurrently. The report is always in case order whatever `jobs` is.
    """
    cases = load_cases() if cases is None else cases
    run = load_candidate(candidate)

    def one(case):
        observed = run_case(case, candidate, run=run, timeout=timeout)
        report = evaluate(case, observed)
        return {
            "id": case["id"],
            "category": case["category"],
            "why": case.get("why", ""),
            "passed": report.passed,
            "checks": report.checks,
            "failures": report.failures,
        }

    if jobs > 1:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(one, cases))
        if on_result is not None:
            for result in results:
                on_result(result)
    else:
        results = []
        for case in cases:
            result = one(case)
            results.append(result)
            if on_result is not None:
                on_result(result)
    return summarise(candidate, results)


def summarise(candidate, results):
    checks = [check for result in results for check in result["checks"]]
    categories = {}
    for result in results:
        bucket = categories.setdefault(
            result["category"], {"cases": 0, "passed": 0, "checks": 0, "checks_passed": 0}
        )
        bucket["cases"] += 1
        bucket["passed"] += 1 if result["passed"] else 0
        bucket["checks"] += len(result["checks"])
        bucket["checks_passed"] += sum(1 for check in result["checks"] if check["ok"])
    return {
        "candidate": os.path.abspath(candidate),
        "cases": len(results),
        "cases_passed": sum(1 for result in results if result["passed"]),
        "checks": len(checks),
        "checks_passed": sum(1 for check in checks if check["ok"]),
        "pass_rate": (
            sum(1 for result in results if result["passed"]) / len(results)
            if results
            else 0.0
        ),
        "categories": categories,
        "results": results,
    }
