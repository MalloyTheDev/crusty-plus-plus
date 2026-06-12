#!/usr/bin/env python3
"""M1 acceptance harness.

Compiles `examples/hello.crust` end-to-end and asserts the frozen M1 acceptance
target:

  1. crustc emits C that matches the golden file `tests/golden/hello.c`
     (codegen stability test).
  2. The system C compiler builds the generated C.
  3. Running the executable prints exactly "Hello, CRusty++!\n".
  4. The executable exits with code 0.

Usage:  python3 tests/m1_hello.py
Exit:   0 on PASS, 1 on FAIL.
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Paths are kept relative to ROOT so the path crustc embeds in the generated C
# comment is stable (and matches the golden file) regardless of where the
# harness is launched from.
CRUSTC = os.path.join("compiler", "crustc.py")
SOURCE = os.path.join("examples", "hello.crust")
GOLDEN = os.path.join(ROOT, "tests", "golden", "hello.c")
BUILD_DIR = os.path.join(ROOT, "build")

EXPECTED_STDOUT = b"Hello, CRusty++!\n"
EXPECTED_EXIT = 0


def fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    os.makedirs(BUILD_DIR, exist_ok=True)
    emitted_rel = os.path.join("build", "hello.c")
    emitted_c = os.path.join(ROOT, emitted_rel)
    exe = os.path.join(ROOT, "build", "hello")

    # 1. Emit C and compare to the golden file. Run from ROOT so the embedded
    #    source path is the stable relative "examples/hello.crust".
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
            "generated C does not match tests/golden/hello.c\n"
            "--- emitted ---\n" + emitted + "\n--- golden ---\n" + golden
        )

    # 2. Build with the system C compiler.
    cc = os.environ.get("CC", "cc")
    subprocess.run([cc, emitted_c, "-o", exe], check=True)

    # 3 & 4. Run and assert stdout + exit code.
    result = subprocess.run([exe], capture_output=True)
    if result.stdout != EXPECTED_STDOUT:
        fail(f"stdout was {result.stdout!r}, expected {EXPECTED_STDOUT!r}")
    if result.returncode != EXPECTED_EXIT:
        fail(f"exit code was {result.returncode}, expected {EXPECTED_EXIT}")

    print("PASS: hello.crust compiled, built, ran; stdout and exit code match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
