#!/usr/bin/env python3
"""M3A acceptance harness.

Compiles `examples/m3a_slices.crust` end-to-end and asserts:

  1. crustc emits C matching the golden `tests/golden/m3a_slices.c`.
  2. The system C compiler builds the generated C.
  3. The executable exits with code 0 (every slice/.len check holds).

Usage:  python3 tests/m3a_slices.py
Exit:   0 on PASS, 1 on FAIL.
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRUSTC = os.path.join("compiler", "crustc.py")
SOURCE = os.path.join("examples", "m3a_slices.crust")
GOLDEN = os.path.join(ROOT, "tests", "golden", "m3a_slices.c")
BUILD_DIR = os.path.join(ROOT, "build")

EXPECTED_EXIT = 0


def fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    os.makedirs(BUILD_DIR, exist_ok=True)
    emitted_rel = os.path.join("build", "m3a_slices.c")
    emitted_c = os.path.join(ROOT, emitted_rel)
    exe = os.path.join(ROOT, "build", "m3a_slices")

    subprocess.run(
        [sys.executable, CRUSTC, SOURCE, "--emit-c", emitted_rel],
        check=True,
        cwd=ROOT,
    )
    with open(emitted_c, "r", encoding="utf-8") as fh:
        emitted = fh.read()
    with open(GOLDEN, "r", encoding="utf-8") as fh:
        golden = fh.read()
    if emitted != golden:
        fail(
            "generated C does not match tests/golden/m3a_slices.c\n"
            "--- emitted ---\n" + emitted + "\n--- golden ---\n" + golden
        )

    cc = os.environ.get("CC", "cc")
    subprocess.run([cc, emitted_c, "-o", exe], check=True)

    result = subprocess.run([exe], capture_output=True)
    if result.returncode != EXPECTED_EXIT:
        fail(f"exit code was {result.returncode}, expected {EXPECTED_EXIT}")

    print("PASS: m3a_slices.crust compiled, built, ran; exit code matches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
