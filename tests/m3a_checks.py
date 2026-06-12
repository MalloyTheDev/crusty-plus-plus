#!/usr/bin/env python3
"""M3A slice/string behavior + diagnostic tests.

Runtime (compile, build, run; each program self-checks and exits 0 iff correct):
    - tests/behavior/slice_str_len.crust      str literal `.len` byte length
    - tests/behavior/slice_escaped_len.crust  escaped literal `.len` byte length
    - tests/behavior/slice_struct_str.crust   `.len` through a struct `str` field
    - tests/behavior/slice_u8_field.crust     `[]u8` struct field compiles (no value)

Negative diagnostics (rejected at compile time with a specific code, exit 1):
    - `str` arithmetic            -> CRX0028
    - `str` comparison            -> CRX0029
    - `str as i32`                -> CRX0038
    - `5 as str`                  -> CRX0039
    - `.len` on an `i32`          -> CRX0026
    - `str` field other than len  -> CRX0025

Usage:  python3 tests/m3a_checks.py
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

RUNTIME = [
    "slice_str_len",
    "slice_escaped_len",
    "slice_struct_str",
    "slice_u8_field",
]

NEGATIVE = [
    (
        "str arithmetic",
        'fn main() -> i32 { let a: str = "x"; let b: str = "y"; '
        "let c: bool = a + b == 0; return 0; }",
        "CRX0028",
    ),
    (
        "str comparison",
        'fn main() -> i32 { let a: str = "x"; let b: str = "y"; '
        "let c: bool = a == b; return 0; }",
        "CRX0029",
    ),
    (
        "str as i32",
        'fn main() -> i32 { let a: str = "x"; let n: i32 = a as i32; return 0; }',
        "CRX0038",
    ),
    (
        "i32 as str",
        "fn main() -> i32 { let a: str = 5 as str; return 0; }",
        "CRX0039",
    ),
    (
        ".len on i32",
        "fn main() -> i32 { let a: i32 = 5; let n: usize = a.len; return 0; }",
        "CRX0026",
    ),
    (
        "str non-len field",
        'fn main() -> i32 { let a: str = "x"; let n: usize = a.foo; return 0; }',
        "CRX0025",
    ),
]


def run_runtime() -> int:
    os.makedirs(BUILD_DIR, exist_ok=True)
    cc = os.environ.get("CC", "cc")
    failures = 0
    for name in RUNTIME:
        source = os.path.join("tests", "behavior", name + ".crust")
        emitted_rel = os.path.join("build", name + ".c")
        emitted_c = os.path.join(ROOT, emitted_rel)
        exe = os.path.join(ROOT, "build", name)
        subprocess.run(
            [sys.executable, CRUSTC, source, "--emit-c", emitted_rel],
            check=True,
            cwd=ROOT,
        )
        subprocess.run([cc, emitted_c, "-o", exe], check=True)
        code = subprocess.run([exe], capture_output=True).returncode
        if code == 0:
            print(f"  ok: {name} -> exit 0")
        else:
            print(f"  FAIL: {name} exit {code}, expected 0", file=sys.stderr)
            failures += 1
    return failures


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
        if proc.returncode == 1 and expected_code in proc.stderr:
            print(f"  ok: {label} -> {expected_code}")
        else:
            print(
                f"  FAIL: {label}: expected {expected_code} (exit 1), "
                f"got exit {proc.returncode}\n{proc.stderr.strip()}",
                file=sys.stderr,
            )
            failures += 1
    return failures


def main() -> int:
    failures = run_runtime() + run_negative()
    total = len(RUNTIME) + len(NEGATIVE)
    if failures:
        print(f"FAIL: {failures}/{total} M3A cases did not behave as expected")
        return 1
    print(f"PASS: all {total} M3A slice/string behavior/diagnostic cases pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
