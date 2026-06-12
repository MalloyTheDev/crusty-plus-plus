#!/usr/bin/env python3
"""M2B checked-arithmetic behavior tests.

Each program in `tests/behavior/` triggers one checked-arithmetic fault and must
abort with exit code 101 (the frozen panic exit code). This harness compiles,
builds, and runs each, asserting the exit code.

Usage:  python3 tests/m2b_behavior.py
Exit:   0 if all cases abort with 101, 1 otherwise.
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRUSTC = os.path.join("compiler", "crustc.py")
BEHAVIOR_DIR = os.path.join("tests", "behavior")
BUILD_DIR = os.path.join(ROOT, "build")

PANIC_EXIT = 101

CASES = [
    "add_overflow",
    "sub_overflow",
    "mul_overflow",
    "div_zero",
    "div_overflow",
    "neg_overflow",
]


def main() -> int:
    os.makedirs(BUILD_DIR, exist_ok=True)
    cc = os.environ.get("CC", "cc")
    failures = 0

    for name in CASES:
        source = os.path.join(BEHAVIOR_DIR, name + ".crust")
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
        if result.returncode == PANIC_EXIT:
            print(f"  ok: {name} aborted with exit {PANIC_EXIT}")
        else:
            print(
                f"  FAIL: {name} exited {result.returncode}, expected {PANIC_EXIT}",
                file=sys.stderr,
            )
            failures += 1

    if failures:
        print(f"FAIL: {failures}/{len(CASES)} behavior cases did not abort with 101")
        return 1
    print(f"PASS: all {len(CASES)} checked-arithmetic cases abort with exit 101.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
