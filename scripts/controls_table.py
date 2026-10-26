"""Grade every control and print the README's table.

    python scripts/controls_table.py [--jobs 8]

`null` must score 0/110: that is the positive control, and a case it passed would be a case
that can be passed without doing anything. Each other control is the reference harness with
one rule broken, so the cases it fails say what that rule is worth.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doc2harness.score import grade, load_cases  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTROLS = os.path.join(ROOT, "controls")

ORDER = [
    "reference",
    "null",
    "fatal_tool_error",
    "tool_results_as_user",
    "lenient_arguments",
    "open_paths",
    "silent_tool_error",
    "no_tokens",
    "no_retry",
    "no_compaction",
    "unsorted_tools",
    "no_tool_events",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", "-j", type=int, default=8)
    args = parser.parse_args()

    cases = load_cases()
    total = len(cases)
    rows = []
    for name in ORDER:
        path = os.path.join(ROOT, "reference") if name == "reference" else os.path.join(CONTROLS, name)
        report = grade(path, cases, jobs=args.jobs)
        failed = sorted(
            {result["category"] for result in report["results"] if not result["passed"]}
        )
        rows.append((name, report["cases_passed"], report["checks_passed"], report["checks"], failed))
        print("%-22s %3d/%d" % (name, report["cases_passed"], total), flush=True)

    print()
    print("| harness | cases passed | checks passed | categories with a failure |")
    print("|---|---:|---:|---|")
    for name, passed, checks_passed, checks, failed in rows:
        print(
            "| `%s` | %d/%d | %d/%d | %s |"
            % (
                name,
                passed,
                total,
                checks_passed,
                checks,
                ", ".join(failed) if failed else "none",
            )
        )


if __name__ == "__main__":
    main()
