#!/usr/bin/env python3
"""M3C `?`/function behavior + diagnostic tests.

Runtime (compile, build, run; assert exit 0):
    - m3c_ok_passthrough     `?` yields the Ok payload
    - m3c_err_shortcircuit    `?` short-circuits on Err
    - m3c_chain_err           chained `?` stops at the first Err (no panic)
    - m3c_arg_order           a 2-arg call computes correctly (1 + 2 - 3 == 0)

Codegen (left-to-right argument evaluation):
    - m3c_arg_order: the emitted C hoists `one()` before `two()`.

Negative diagnostics (rejected at compile time with a specific code, exit 1):
    - `?` in `main() -> i32`        -> CRX0045
    - `?` on an Option             -> CRX0044
    - `?` on an i32                -> CRX0044
    - `?` with mismatched Err type -> CRX0046
    - unknown function             -> CRX0012
    - wrong argument count         -> CRX0013
    - wrong argument type          -> CRX0014

Usage:  python3 tests/m3c_checks.py
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
    "m3c_ok_passthrough",
    "m3c_err_shortcircuit",
    "m3c_chain_err",
    "m3c_arg_order",
]

NEGATIVE = [
    (
        "? in main",
        "fn g(x: i32) -> Result<i32, i32> { return Ok(x); } "
        "fn main() -> i32 { let y: i32 = g(1)?; return y; }",
        "CRX0045",
    ),
    (
        "? on Option",
        "fn f() -> Result<i32, i32> { let o: Option<i32> = Some(1); "
        "let y: i32 = o?; return Ok(y); } fn main() -> i32 { return 0; }",
        "CRX0044",
    ),
    (
        "? on i32",
        "fn f() -> Result<i32, i32> { let x: i32 = 5; let y: i32 = x?; "
        "return Ok(y); } fn main() -> i32 { return 0; }",
        "CRX0044",
    ),
    (
        "? mismatched Err type",
        "fn g() -> Result<i32, i32> { return Ok(1); } "
        "fn f() -> Result<i32, usize> { let y: i32 = g()?; return Ok(y); } "
        "fn main() -> i32 { return 0; }",
        "CRX0046",
    ),
    (
        "unknown function",
        "fn main() -> i32 { let x: i32 = nope(1); return 0; }",
        "CRX0012",
    ),
    (
        "wrong argument count",
        "fn g(a: i32, b: i32) -> i32 { return a; } "
        "fn main() -> i32 { let x: i32 = g(1); return 0; }",
        "CRX0013",
    ),
    (
        "wrong argument type",
        "fn g(a: i32) -> i32 { return a; } "
        "fn main() -> i32 { let b: bool = 1 < 2; let x: i32 = g(b); return 0; }",
        "CRX0014",
    ),
]


def run_runtime() -> int:
    os.makedirs(BUILD_DIR, exist_ok=True)
    cc = os.environ.get("CC", "cc")
    failures = 0
    arg_order_c = None
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
        if name == "m3c_arg_order":
            with open(emitted_c, "r", encoding="utf-8") as fh:
                arg_order_c = fh.read()

    # Left-to-right codegen: `one()` is hoisted before `two()`.
    if arg_order_c is not None and "one()" in arg_order_c and "two()" in arg_order_c:
        if arg_order_c.index("one()") < arg_order_c.index("two()"):
            print("  ok: m3c_arg_order -> args hoisted left-to-right")
        else:
            print("  FAIL: m3c_arg_order: args not left-to-right", file=sys.stderr)
            failures += 1
    else:
        print("  FAIL: m3c_arg_order: could not check codegen order", file=sys.stderr)
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
    total = len(RUNTIME) + 1 + len(NEGATIVE)  # +1 for the codegen-order check
    if failures:
        print(f"FAIL: {failures}/{total} M3C cases did not behave as expected")
        return 1
    print(f"PASS: all {total} M3C behavior/diagnostic cases pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
