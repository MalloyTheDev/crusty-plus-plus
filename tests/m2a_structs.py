#!/usr/bin/env python3
"""M2A acceptance harness.

Compiles `examples/m2_structs.crust` end-to-end and asserts the M2A target:

  1. crustc emits C matching the golden file `tests/golden/m2_structs.c`.
  2. The system C compiler builds the generated C.
  3. The executable exits with code 0 (it produces no stdout).

Usage:  python3 tests/m2a_structs.py
Exit:   0 on PASS, 1 on FAIL.
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRUSTC = os.path.join("compiler", "crustc.py")
SOURCE = os.path.join("examples", "m2_structs.crust")
GOLDEN = os.path.join(ROOT, "tests", "golden", "m2_structs.c")
BUILD_DIR = os.path.join(ROOT, "build")

EXPECTED_STDOUT = b""
EXPECTED_EXIT = 0


def fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    os.makedirs(BUILD_DIR, exist_ok=True)
    emitted_rel = os.path.join("build", "m2_structs.c")
    emitted_c = os.path.join(ROOT, emitted_rel)
    exe = os.path.join(ROOT, "build", "m2_structs")

    # 1. Emit C and compare to the golden file (run from ROOT for a stable path).
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
            "generated C does not match tests/golden/m2_structs.c\n"
            "--- emitted ---\n" + emitted + "\n--- golden ---\n" + golden
        )

    # 2. Build with the system C compiler.
    cc = os.environ.get("CC", "cc")
    subprocess.run([cc, emitted_c, "-o", exe], check=True)

    # 3. Run and assert stdout + exit code.
    result = subprocess.run([exe], capture_output=True)
    if result.stdout != EXPECTED_STDOUT:
        fail(f"stdout was {result.stdout!r}, expected {EXPECTED_STDOUT!r}")
    if result.returncode != EXPECTED_EXIT:
        fail(f"exit code was {result.returncode}, expected {EXPECTED_EXIT}")

    print("PASS: m2_structs.crust compiled, built, ran; exit code matches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
