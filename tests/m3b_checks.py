#!/usr/bin/env python3
"""M3B Result/Option behavior + diagnostic tests.

Runtime (compile, build, run; assert exit code):
    - m3b_ok_path        Result Ok path / is_ok / unwrap      -> 0
    - m3b_err_path       Result Err path / is_err             -> 0
    - m3b_some_path      Option Some path / unwrap             -> 0
    - m3b_none_path      Option None constructed + reassigned  -> 0
    - m3b_result_strlen  Result<usize, i32> over str.len       -> 0
    - m3b_unwrap_err     unwrap(Err(...))                      -> 101
    - m3b_unwrap_none    unwrap(None)                          -> 101

Negative diagnostics (rejected at compile time with a specific code, exit 1):
    - malformed Result<>            -> CRX0003
    - malformed Option<>            -> CRX0003
    - user-defined generic type     -> CRX0041
    - None without expected Option  -> CRX0042
    - Ok outside expected Result    -> CRX0042
    - Some outside expected Option  -> CRX0042

Usage:  python3 tests/m3b_checks.py
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
    ("m3b_ok_path", 0),
    ("m3b_err_path", 0),
    ("m3b_some_path", 0),
    ("m3b_none_path", 0),
    ("m3b_result_strlen", 0),
    ("m3b_unwrap_err", 101),
    ("m3b_unwrap_none", 101),
]

NEGATIVE = [
    (
        "malformed Result<>",
        "fn main() -> i32 { let r: Result<i32> = Ok(1); return 0; }",
        "CRX0003",
    ),
    (
        "malformed Option<>",
        "fn main() -> i32 { let o: Option<i32, i32> = None; return 0; }",
        "CRX0003",
    ),
    (
        "user generic type",
        "fn main() -> i32 { let x: Vec<i32> = 0; return 0; }",
        "CRX0041",
    ),
    (
        "None without expected Option",
        "fn main() -> i32 { let x: i32 = None; return 0; }",
        "CRX0042",
    ),
    (
        "Ok outside Result",
        "fn main() -> i32 { let x: i32 = Ok(5); return 0; }",
        "CRX0042",
    ),
    (
        "Some outside Option",
        "fn main() -> i32 { let x: i32 = Some(5); return 0; }",
        "CRX0042",
    ),
]


def run_runtime() -> int:
    os.makedirs(BUILD_DIR, exist_ok=True)
    cc = os.environ.get("CC", "cc")
    failures = 0
    for name, expected in RUNTIME:
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
        if code == expected:
            print(f"  ok: {name} -> exit {expected}")
        else:
            print(f"  FAIL: {name} exit {code}, expected {expected}", file=sys.stderr)
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
        print(f"FAIL: {failures}/{total} M3B cases did not behave as expected")
        return 1
    print(f"PASS: all {total} M3B behavior/diagnostic cases pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
