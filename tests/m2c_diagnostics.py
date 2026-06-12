#!/usr/bin/env python3
"""M2C diagnostic + control-flow behavior tests.

Two halves:

  Negative (must be rejected at compile time with a specific diagnostic code):
    - assignment to an immutable local            -> CRX0031
    - assignment of the wrong type                -> CRX0014
    - `break` outside a loop                      -> CRX0033
    - `continue` outside a loop                   -> CRX0034
    - non-`bool` `while` condition                -> CRX0030

  Positive (must compile, build, and run with the expected exit code):
    - tests/behavior/loop_break.crust             -> exit 0
    - tests/behavior/continue_skip.crust          -> exit 0

Usage:  python3 tests/m2c_diagnostics.py
Exit:   0 if every case behaves as expected, 1 otherwise.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRUSTC = os.path.join(ROOT, "compiler", "crustc.py")
BUILD_DIR = os.path.join(ROOT, "build")

NEGATIVE = [
    (
        "assign to immutable",
        "fn main() -> i32 { let x: i32 = 1; x = 2; return x; }",
        "CRX0031",
    ),
    (
        "assign wrong type",
        "fn main() -> i32 { let mut x: i32 = 1; x = 1 < 2; return x; }",
        "CRX0014",
    ),
    (
        "break outside loop",
        "fn main() -> i32 { break; return 0; }",
        "CRX0033",
    ),
    (
        "continue outside loop",
        "fn main() -> i32 { continue; return 0; }",
        "CRX0034",
    ),
    (
        "non-bool while condition",
        "fn main() -> i32 { while 1 { return 0; } }",
        "CRX0030",
    ),
]

POSITIVE = [
    ("loop_break", os.path.join("tests", "behavior", "loop_break.crust"), 0),
    ("continue_skip", os.path.join("tests", "behavior", "continue_skip.crust"), 0),
]


def run_negative() -> int:
    failures = 0
    for label, source, expected_code in NEGATIVE:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".crust", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(source)
            path = tmp.name
        try:
            proc = subprocess.run(
                [sys.executable, CRUSTC, path], capture_output=True, text=True
            )
        finally:
            os.unlink(path)
        ok = proc.returncode == 1 and expected_code in proc.stderr
        if ok:
            print(f"  ok: {label} -> {expected_code}")
        else:
            print(
                f"  FAIL: {label}: expected {expected_code} (exit 1), "
                f"got exit {proc.returncode}\n{proc.stderr.strip()}",
                file=sys.stderr,
            )
            failures += 1
    return failures


def run_positive() -> int:
    os.makedirs(BUILD_DIR, exist_ok=True)
    cc = os.environ.get("CC", "cc")
    failures = 0
    for name, source, expected_exit in POSITIVE:
        emitted_rel = os.path.join("build", name + ".c")
        emitted_c = os.path.join(ROOT, emitted_rel)
        exe = os.path.join(ROOT, "build", name)
        subprocess.run(
            [sys.executable, CRUSTC, source, "--emit-c", emitted_rel],
            check=True,
            cwd=ROOT,
        )
        subprocess.run([cc, emitted_c, "-o", exe], check=True)
        result = subprocess.run([exe], capture_output=True)
        if result.returncode == expected_exit:
            print(f"  ok: {name} -> exit {expected_exit}")
        else:
            print(
                f"  FAIL: {name}: exit {result.returncode}, expected {expected_exit}",
                file=sys.stderr,
            )
            failures += 1
    return failures


def main() -> int:
    failures = run_negative() + run_positive()
    total = len(NEGATIVE) + len(POSITIVE)
    if failures:
        print(f"FAIL: {failures}/{total} M2C cases did not behave as expected")
        return 1
    print(f"PASS: all {total} M2C diagnostic/behavior cases pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
