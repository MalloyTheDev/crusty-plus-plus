#!/usr/bin/env python3
"""M2D behavior + diagnostic tests.

Runtime behavior (compile, build, run; assert exit code):
    - tests/behavior/u8_overflow.crust       -> 101
    - tests/behavior/u8_underflow.crust       -> 101
    - tests/behavior/i8_overflow.crust        -> 101
    - tests/behavior/i8_neg_overflow.crust    -> 101
    - tests/behavior/u64_div_zero.crust       -> 101
    - usize local + struct field (inline)     -> 0

Negative diagnostics (must be rejected with a specific code, exit 1):
    - mixed-type arithmetic                   -> CRX0035
    - mixed-type comparison                   -> CRX0029
    - unary `-` on an unsigned type           -> CRX0037
    - integer literal out of range            -> CRX0036

Usage:  python3 tests/m2d_checks.py
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
    ("u8_overflow", os.path.join("tests", "behavior", "u8_overflow.crust"), 101),
    ("u8_underflow", os.path.join("tests", "behavior", "u8_underflow.crust"), 101),
    ("i8_overflow", os.path.join("tests", "behavior", "i8_overflow.crust"), 101),
    ("i8_neg_overflow", os.path.join("tests", "behavior", "i8_neg_overflow.crust"), 101),
    ("u64_div_zero", os.path.join("tests", "behavior", "u64_div_zero.crust"), 101),
]

USIZE_POSITIVE = (
    "struct S { n: usize }\n"
    "fn main() -> i32 { let x: usize = 10; let s: S = S { n: x }; return 0; }"
)

NEGATIVE = [
    (
        "mixed arithmetic",
        "fn main() -> i32 { let a: i32 = 1; let b: i64 = 2; "
        "let c: bool = a + b == 3; return 0; }",
        "CRX0035",
    ),
    (
        "mixed comparison",
        "fn main() -> i32 { let a: i32 = 1; let b: i64 = 2; "
        "let c: bool = a == b; return 0; }",
        "CRX0029",
    ),
    (
        "unsigned unary minus",
        "fn main() -> i32 { let x: u8 = -5; return 0; }",
        "CRX0037",
    ),
    (
        "literal out of range",
        "fn main() -> i32 { let a: u8 = 256; return 0; }",
        "CRX0036",
    ),
]


def compile_run(name: str, source_path: str, cwd_relative: bool) -> int:
    os.makedirs(BUILD_DIR, exist_ok=True)
    cc = os.environ.get("CC", "cc")
    emitted_rel = os.path.join("build", name + ".c")
    emitted_c = os.path.join(ROOT, emitted_rel)
    exe = os.path.join(ROOT, "build", name)
    subprocess.run(
        [sys.executable, CRUSTC, source_path, "--emit-c", emitted_rel],
        check=True,
        cwd=ROOT,
    )
    subprocess.run([cc, emitted_c, "-o", exe], check=True)
    return subprocess.run([exe], capture_output=True).returncode


def run_runtime() -> int:
    failures = 0
    for name, source, expected in RUNTIME:
        code = compile_run(name, source, True)
        if code == expected:
            print(f"  ok: {name} -> exit {expected}")
        else:
            print(f"  FAIL: {name} exit {code}, expected {expected}", file=sys.stderr)
            failures += 1

    # usize positive case (inline source).
    with tempfile.NamedTemporaryFile(
        "w", suffix=".crust", delete=False, dir=os.path.join(ROOT, "build"),
        encoding="utf-8",
    ) as tmp:
        tmp.write(USIZE_POSITIVE)
        rel = os.path.join("build", os.path.basename(tmp.name))
    code = compile_run("usize_positive", rel, True)
    if code == 0:
        print("  ok: usize_positive -> exit 0")
    else:
        print(f"  FAIL: usize_positive exit {code}, expected 0", file=sys.stderr)
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
    total = len(RUNTIME) + 1 + len(NEGATIVE)
    if failures:
        print(f"FAIL: {failures}/{total} M2D cases did not behave as expected")
        return 1
    print(f"PASS: all {total} M2D behavior/diagnostic cases pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
