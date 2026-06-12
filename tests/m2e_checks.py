#!/usr/bin/env python3
"""M2E cast behavior + diagnostic tests.

Runtime cast values (each program self-checks the cast result and exits 0 iff
correct):
    - 300 as u8        -> 44
    - -1 as u8         -> 255
    - 255 as i8        -> -1
    - 65535 as i16     -> -1
    - u8 200 as i32    -> 200   (zero-extend)
    - i8 -5 as i32     -> -5    (sign-extend)

Negative diagnostics (rejected at compile time with a specific code, exit 1):
    - bool as i32      -> CRX0038 (invalid cast source)
    - i32 as bool      -> CRX0039 (invalid cast target)
    - struct as i32    -> CRX0038 (invalid cast source)
    - 5 as Foo         -> CRX0021 (unknown type)

Usage:  python3 tests/m2e_checks.py
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
    "cast_300_u8",
    "cast_neg1_u8",
    "cast_255_i8",
    "cast_65535_i16",
    "cast_u8_i32",
    "cast_i8neg_i32",
]

NEGATIVE = [
    (
        "bool as i32",
        "fn main() -> i32 { let b: bool = 1 < 2; let x: i32 = b as i32; return 0; }",
        "CRX0038",
    ),
    (
        "i32 as bool",
        "fn main() -> i32 { let x: bool = 5 as bool; return 0; }",
        "CRX0039",
    ),
    (
        "struct as i32",
        "struct S { x: i32 } fn main() -> i32 { let s: S = S { x: 1 }; "
        "let y: i32 = s as i32; return 0; }",
        "CRX0038",
    ),
    (
        "unknown target type",
        "fn main() -> i32 { let x: i32 = 5 as Foo; return 0; }",
        "CRX0021",
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
        print(f"FAIL: {failures}/{total} M2E cases did not behave as expected")
        return 1
    print(f"PASS: all {total} M2E cast behavior/diagnostic cases pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
