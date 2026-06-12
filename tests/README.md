# tests/

The CRusty++ conformance test suite.

**Status: M1 + M2A + M2B harnesses in place.**

Acceptance tests (compile → build → run → assert golden C + exit code):

- [`m1_hello.py`](./m1_hello.py) — `hello.crust`; stdout `Hello, CRusty++!\n`, exit `0`.
- [`m2a_structs.py`](./m2a_structs.py) — `m2_structs.crust`; no stdout, exit `0`.
- [`m2b_checked_if.py`](./m2b_checked_if.py) — `m2b_checked_if.crust`; exit `0`.

Behavior tests (checked arithmetic must abort):

- [`m2b_behavior.py`](./m2b_behavior.py) — builds and runs each program in
  [`behavior/`](./behavior/) and asserts exit code `101`: `add_overflow`,
  `sub_overflow`, `mul_overflow`, `div_zero`, `div_overflow`, `neg_overflow`.

Goldens live in [`golden/`](./golden/) (one `.c` per acceptance example) for the
codegen stability checks.

Run them all:

```sh
python3 tests/m1_hello.py
python3 tests/m2a_structs.py
python3 tests/m2b_checked_if.py
python3 tests/m2b_behavior.py
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
