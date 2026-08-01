#!/usr/bin/env python3
"""Validate the problem bank.

Every problem's reference solution is executed against its own test cases.
A problem is only allowed into the bank if it passes 100% of its own tests,
plus a set of structural checks. Exit code is non-zero if anything fails, so
this can gate the build.

Usage:
    python3 tools/validate.py                 # validate everything
    python3 tools/validate.py data/problems/warmup-1.json
"""

import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK = ROOT / "data" / "problems"

GUARD_SECONDS = 5
IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
REQUIRED = [
    "id", "category", "title", "function", "difficulty", "concept",
    "brief", "description", "starter", "solution", "hints", "example",
    "explainer", "tests",
]


class Problem:
    def __init__(self, raw, source):
        self.raw = raw
        self.source = source
        self.id = raw.get("id", "<no id>")


def run_solution(problem):
    """Exec the reference solution and return (callable, error_string)."""
    namespace = {}
    try:
        exec(problem["solution"], namespace)
    except Exception as exc:  # noqa: BLE001
        return None, f"solution failed to exec: {type(exc).__name__}: {exc}"
    fn = namespace.get(problem["function"])
    if not callable(fn):
        return None, f"solution does not define {problem['function']}()"
    return fn, None


def check_structure(problem, seen_ids):
    errors = []
    for field in REQUIRED:
        if field not in problem:
            errors.append(f"missing field '{field}'")
    if errors:
        return errors

    pid = problem["id"]
    if not IDENT.match(pid):
        errors.append(f"id '{pid}' is not snake_case")
    if pid != problem["function"]:
        errors.append(f"id '{pid}' != function '{problem['function']}'")
    if pid in seen_ids:
        errors.append(f"duplicate id '{pid}' (also in {seen_ids[pid]})")

    if not isinstance(problem["tests"], list) or len(problem["tests"]) < 5:
        errors.append(f"needs >= 5 tests, has {len(problem.get('tests', []))}")
    if not isinstance(problem["hints"], list) or len(problem["hints"]) < 2:
        errors.append("needs >= 2 hints")
    if not isinstance(problem["difficulty"], int) or not 1 <= problem["difficulty"] <= 5:
        errors.append("difficulty must be int 1-5")

    # starter must parse and define the function too, or the editor seeds broken code
    ns = {}
    try:
        exec(problem["starter"], ns)
        if not callable(ns.get(problem["function"])):
            errors.append("starter does not define the target function")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"starter failed to exec: {type(exc).__name__}: {exc}")

    # everything must survive a JSON round trip (Pyodide gets this as JSON)
    for i, test in enumerate(problem["tests"]):
        if "args" not in test or "expected" not in test:
            errors.append(f"test[{i}] missing args/expected")
            continue
        if not isinstance(test["args"], list):
            errors.append(f"test[{i}] args must be a list")
        try:
            json.dumps(test)
        except (TypeError, ValueError) as exc:
            errors.append(f"test[{i}] is not JSON serializable: {exc}")

    return errors


def check_behavior(problem):
    """The core gate: does the reference solution actually produce every expected value?"""
    errors = []
    fn, err = run_solution(problem)
    if err:
        return [err]

    for i, test in enumerate(problem["tests"]):
        args = test.get("args", [])
        expected = test.get("expected")
        # snapshot BEFORE the call so we can detect argument mutation afterwards
        before = json.loads(json.dumps(args))
        try:
            start = time.time()
            actual = fn(*args)
            elapsed = time.time() - start
        except Exception as exc:  # noqa: BLE001
            errors.append(
                f"test[{i}] {problem['function']}({fmt(args)}) raised "
                f"{type(exc).__name__}: {exc}"
            )
            continue

        if elapsed > GUARD_SECONDS:
            errors.append(f"test[{i}] took {elapsed:.1f}s, over the {GUARD_SECONDS}s runtime budget")

        if not same(actual, expected):
            errors.append(
                f"test[{i}] {problem['function']}({fmt(args)}) -> {actual!r}, "
                f"but expected {expected!r}"
            )

        # mutation check: solutions must not mutate their arguments, because the
        # browser echoes those same objects back into the results table
        if args != before:
            for j, (now, was) in enumerate(zip(args, before)):
                if now != was:
                    errors.append(
                        f"test[{i}] arg {j} was mutated by the solution: "
                        f"{was!r} -> {now!r}"
                    )

    return errors


def json_to_py(value):
    return value


def same(actual, expected):
    """Strict-ish equality. Guards against 1 == True sneaking through."""
    if isinstance(expected, bool) or isinstance(actual, bool):
        return isinstance(actual, bool) and isinstance(expected, bool) and actual == expected
    return actual == expected


def fmt(args):
    return ", ".join(repr(a) for a in args)


def main(argv):
    files = [pathlib.Path(p) for p in argv[1:]] or sorted(BANK.glob("*.json"))
    if not files:
        print("no problem files found", file=sys.stderr)
        return 1

    seen_ids = {}
    total = 0
    failed = 0
    by_category = {}

    for path in files:
        try:
            problems = json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {path.name}: not valid JSON: {exc}")
            failed += 1
            continue

        if not isinstance(problems, list):
            print(f"FAIL {path.name}: top level must be a JSON array")
            failed += 1
            continue

        for problem in problems:
            total += 1
            pid = problem.get("id", f"<{path.name} #{total}>")
            errors = check_structure(problem, seen_ids)
            if not errors:
                errors = check_behavior(problem)
                seen_ids[pid] = path.name
                by_category.setdefault(problem["category"], 0)
                by_category[problem["category"]] += 1

            if errors:
                failed += 1
                print(f"FAIL {pid}  ({path.name})")
                for err in errors:
                    print(f"     - {err}")

    passed = total - failed
    print()
    print(f"{'=' * 52}")
    print(f"problems: {total}   passed: {passed}   failed: {failed}")
    if total:
        print(f"success rate: {passed / total * 100:.1f}%")
    for cat in sorted(by_category):
        print(f"  {cat:<12} {by_category[cat]}")
    print(f"{'=' * 52}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
