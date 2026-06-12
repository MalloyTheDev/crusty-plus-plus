# tests/

The CRusty++ conformance test suite.

**Status: M1 + M2A + M2B + M2C + M2D + M2E + M3A harnesses in place.**

Acceptance tests (compile → build → run → assert golden C + exit code):

- [`m1_hello.py`](./m1_hello.py) — `hello.crust`; stdout `Hello, CRusty++!\n`, exit `0`.
- [`m2a_structs.py`](./m2a_structs.py) — `m2_structs.crust`; no stdout, exit `0`.
- [`m2b_checked_if.py`](./m2b_checked_if.py) — `m2b_checked_if.crust`; exit `0`.
- [`m2c_loops.py`](./m2c_loops.py) — `m2c_loops.crust`; exit `0`.
- [`m2d_numeric.py`](./m2d_numeric.py) — `m2d_numeric_types.crust`; exit `0`.
- [`m2e_casts.py`](./m2e_casts.py) — `m2e_casts.crust`; exit `0`.
- [`m3a_slices.py`](./m3a_slices.py) — `m3a_slices.crust`; exit `0`.
- [`m3b_result_option.py`](./m3b_result_option.py) — `m3b_result_option.crust`; exit `0`.

Behavior tests (runtime exit-code assertions):

- [`m2b_behavior.py`](./m2b_behavior.py) — six `i32` checked-arithmetic faults in
  [`behavior/`](./behavior/), each must exit `101`.

Diagnostic + control-flow + numeric tests:

- [`m2c_diagnostics.py`](./m2c_diagnostics.py) — 5 negative compile cases
  (`CRX0031`, `CRX0014`, `CRX0033`, `CRX0034`, `CRX0030`) + 2 positive runtime
  cases (`loop_break`, `continue_skip`, exit `0`).
- [`m2d_checks.py`](./m2d_checks.py) — runtime panics for `u8`/`i8` overflow,
  `u8` underflow, `i8` negation overflow, and `u64` divide-by-zero (all exit
  `101`); a `usize` local + struct-field program (exit `0`); and negative
  compile cases for mixed arithmetic (`CRX0035`), mixed comparison (`CRX0029`),
  unsigned unary minus (`CRX0037`), and out-of-range literal (`CRX0036`).
- [`m2e_checks.py`](./m2e_checks.py) — six cast-value programs that self-check
  their result and exit `0` (`300 as u8`, `-1 as u8`, `255 as i8`, `65535 as
  i16`, `u8→i32`, `i8→i32`); and negative compile cases `bool as i32`
  (`CRX0038`), `i32 as bool` (`CRX0039`), `struct as i32` (`CRX0038`),
  `5 as Foo` (`CRX0021`).
- [`m3a_checks.py`](./m3a_checks.py) — four slice runtime programs (exit `0`):
  `str` literal `.len` byte length, escaped-literal `.len`, `.len` through a
  struct `str` field, and a `[]u8` struct field that compiles with no value; and
  negative compile cases `str` arithmetic (`CRX0028`), `str` comparison
  (`CRX0029`), `str as i32` (`CRX0038`), `5 as str` (`CRX0039`), `.len` on `i32`
  (`CRX0026`), `str` non-`len` field (`CRX0025`).
- [`m3b_checks.py`](./m3b_checks.py) — seven core-type runtime programs: Result
  Ok/Err and Option Some/None paths and `Result<usize, i32>` over `str.len` (exit
  `0`), and `unwrap(Err)` / `unwrap(None)` (exit `101`); and negative compile
  cases malformed `Result<>`/`Option<>` (`CRX0003`), user generic (`CRX0041`),
  `None`/`Ok`/`Some` against a non-matching expected type (`CRX0042`).

Goldens live in [`golden/`](./golden/) (one `.c` per acceptance example) for the
codegen stability checks.

Run them all:

```sh
for t in m1_hello m2a_structs m2b_checked_if m2b_behavior m2c_loops \
         m2c_diagnostics m2d_numeric m2d_checks m2e_casts m2e_checks \
         m3a_slices m3a_checks m3b_result_option m3b_checks; do
    python3 tests/$t.py || break
done
```

The broader category layout below is the plan for M2+; only the `examples`
(acceptance) and `codegen_c` (golden) categories are populated so far.

## What this suite will check

Per [`../spec/v0.1.md`](../spec/v0.1.md) §8, a conforming `v0.1` compiler must:

1. **Accept** every program labeled valid in [`../examples/`](../examples/) and
   produce the documented behavior.
2. **Reject**, with a diagnostic, programs that violate any spec rule.
3. Implement the **defined behaviors** of `v0.1.md` §6 exactly (checked
   arithmetic, division-by-zero panic, no undefined behavior).

## Planned structure (set at Phase 1 start)

The suite separates the compiler stages so a failure points at the exact stage
that broke, not just "something went wrong":

```
tests/
├── lexer/        token streams for given source (per spec/syntax.md §3–5)
├── parser/       parse success/failure for grammar cases (per syntax.md §6)
├── ast/          parsed AST shape assertions (structure, not just acceptance)
├── typecheck/    type rules: pass/fail per spec/v0.1.md §2 (incl. literal typing)
├── diagnostics/  rejected programs assert a stable diagnostic code + span
├── codegen_c/    generated-C shape and that the C compiles & runs (per B6/C1)
├── examples/     every program in ../examples/ compiles and runs as documented
└── behavior/     defined runtime behavior (overflow panic, div-by-zero, exit codes)
```

- **lexer / parser / ast** are front-end tests: tokens, grammar acceptance, and
  AST structure.
- **typecheck** covers the type system, including the integer-literal typing rule
  (freeze-checklist B5) once frozen.
- **diagnostics** assert on a stable diagnostic *code* and source span, not exact
  prose (freeze-checklist C12), so messages can be reworded without breaking
  tests.
- **codegen_c** checks the emitted C against the agreed shape and that it compiles
  and runs under a system C compiler (recommended backend, freeze-checklist B6).
- **examples** is the acceptance set seeded from [`../examples/`](../examples/).
- **behavior** asserts the defined behaviors of `spec/v0.1.md` §6.

Each category maps directly to a clause of the spec, so a failing test points at
the exact rule it violates.

## Until then

The examples in [`../examples/`](../examples/) act as the informal acceptance set:
every one of them must be fully explained by the spec before `v0.1` freezes. They
become the seed of `tests/valid/` when the compiler work begins.
