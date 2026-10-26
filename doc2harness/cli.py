"""The doc2harness command line."""

import argparse
import json
import os
import shutil
import sys

from .runner import CandidateError
from .score import grade, load_cases

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec", "DEVELOPMENT.md")
SKELETON = os.path.normpath(os.path.join(HERE, "..", "skeleton"))


def _spec_text():
    with open(SPEC, "rb") as fh:
        return fh.read().decode("utf-8")


def cmd_spec(args):
    if args.path:
        print(SPEC)
    else:
        sys.stdout.write(_spec_text())
    return 0


def cmd_cases(args):
    cases = load_cases(args.only)
    by_category = {}
    for case in cases:
        by_category.setdefault(case["category"], []).append(case)
    for category in sorted(by_category):
        print("%s (%d)" % (category, len(by_category[category])))
        if args.verbose:
            for case in by_category[category]:
                print("  %-44s %s" % (case["name"], case.get("why", "")))
    print("\n%d cases" % len(cases))
    return 0


def cmd_new(args):
    target = args.directory
    if os.path.exists(target) and os.listdir(target):
        print("%s is not empty" % target, file=sys.stderr)
        return 2
    shutil.copytree(SKELETON, target, dirs_exist_ok=True)
    shutil.copy2(SPEC, os.path.join(target, "DEVELOPMENT.md"))
    print("wrote the skeleton and DEVELOPMENT.md to %s" % target)
    print("fill it in, then: doc2harness grade %s" % target)
    return 0


def cmd_pack(args):
    """Emit one self-contained prompt: the task, the specification, the skeleton."""
    parts = [
        "# Task\n",
        "Build a complete HARNESS-1 harness in the current directory, following the\n"
        "specification below to the letter. The skeleton that follows it is a suggested\n"
        "module layout; keep it or replace it, but `harness.json` must name a command that\n"
        "starts your harness. Write real code: every module must work, and the harness is\n"
        "graded by running it, not by reading it.\n",
        "\n# DEVELOPMENT.md\n\n",
        _spec_text(),
        "\n# Skeleton\n",
    ]
    for directory, _subdirs, names in os.walk(SKELETON):
        for name in sorted(names):
            full = os.path.join(directory, name)
            relative = os.path.relpath(full, SKELETON).replace(os.sep, "/")
            if relative == "README.md":
                continue
            with open(full, "rb") as fh:
                body = fh.read().decode("utf-8")
            parts.append("\n## %s\n\n```python\n%s```\n" % (relative, body))
    text = "".join(parts)
    if args.out:
        with open(args.out, "wb") as fh:
            fh.write(text.encode("utf-8"))
        print("wrote %s (%d characters)" % (args.out, len(text)))
    else:
        sys.stdout.write(text)
    return 0


def cmd_grade(args):
    cases = load_cases(args.only)
    if not cases:
        print("no cases match %r" % args.only, file=sys.stderr)
        return 2
    width = max(len(case["id"]) for cases_ in [cases] for case in cases_)

    def show(result):
        mark = "pass" if result["passed"] else "FAIL"
        print("%-4s %-*s %d/%d" % (
            mark,
            width,
            result["id"],
            sum(1 for check in result["checks"] if check["ok"]),
            len(result["checks"]),
        ))
        if not result["passed"] and args.verbose:
            for failure in result["failures"]:
                print("       %s: %s" % (failure["name"], failure["detail"]))

    try:
        report = grade(
            args.candidate,
            cases,
            timeout=args.timeout,
            on_result=show,
            jobs=args.jobs,
        )
    except CandidateError as exc:
        print("cannot grade %s: %s" % (args.candidate, exc), file=sys.stderr)
        return 2

    print("\n%-14s %6s %6s   %s" % ("category", "cases", "passed", "checks"))
    for category in sorted(report["categories"]):
        bucket = report["categories"][category]
        print("%-14s %6d %6d   %d/%d" % (
            category,
            bucket["cases"],
            bucket["passed"],
            bucket["checks_passed"],
            bucket["checks"],
        ))
    print("\n%d/%d cases (%.2f%%), %d/%d checks" % (
        report["cases_passed"],
        report["cases"],
        100.0 * report["pass_rate"],
        report["checks_passed"],
        report["checks"],
    ))
    if args.json:
        with open(args.json, "wb") as fh:
            fh.write((json.dumps(report, indent=2) + "\n").encode("utf-8"))
        print("wrote %s" % args.json)
    return 0 if report["cases_passed"] == report["cases"] else 1


def build_parser():
    parser = argparse.ArgumentParser(
        prog="doc2harness",
        description="Grade a coding-agent harness against the HARNESS-1 contract.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("grade", help="run every case against a candidate harness")
    one.add_argument("candidate", help="directory containing harness.json")
    one.add_argument("--only", help="run only cases whose id contains this")
    one.add_argument("--json", help="write the full report here")
    one.add_argument("--timeout", type=int, default=60, help="seconds per case")
    one.add_argument(
        "--jobs", "-j", type=int, default=4, help="cases to run at once (default 4)"
    )
    one.add_argument("-v", "--verbose", action="store_true", help="show failed checks")
    one.set_defaults(handler=cmd_grade)

    two = sub.add_parser("cases", help="list the test cases")
    two.add_argument("--only", help="list only cases whose id contains this")
    two.add_argument("-v", "--verbose", action="store_true")
    two.set_defaults(handler=cmd_cases)

    three = sub.add_parser("spec", help="print the development document")
    three.add_argument("--path", action="store_true", help="print its path instead")
    three.set_defaults(handler=cmd_spec)

    four = sub.add_parser("new", help="copy the skeleton and the spec somewhere")
    four.add_argument("directory")
    four.set_defaults(handler=cmd_new)

    five = sub.add_parser("pack", help="emit one prompt for a coding agent to build from")
    five.add_argument("--out", help="write it to this file instead of stdout")
    five.set_defaults(handler=cmd_pack)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.handler(args)
