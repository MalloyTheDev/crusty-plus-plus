# Roadmap

CRusty++ is built in frozen, versioned increments. Each version closes its scope
before the next opens. Versions below the line marked **frozen** do not change;
new ideas always target the next open version.

## Phase 0 — Design (current)

**Goal:** define the language on paper before writing a compiler.

- [x] Repository skeleton and design documents
- [ ] `spec/v0.1.md` complete and frozen
- [ ] `spec/syntax.md` — full lexical + grammar reference
- [ ] `spec/memory-model.md` — ownership, moves, borrows, scope rules
- [ ] `spec/error-handling.md` — `Result`, `panic`, exit codes
- [ ] Every program in `examples/` explained by the spec, no undefined constructs
- [ ] Design review: no open questions remaining

Exit criterion: the `v0.1` spec is internally consistent and the examples
conform. **No compiler code is written before this phase closes.**

## Phase 1 — `v0.1` compiler

**Goal:** a compiler that accepts exactly the frozen `v0.1` language.

- [x] **M1 — `hello.crust` end-to-end to C.** Lexer, parser, type checker, and C
      emitter for the M1 subset; builds and runs; `tests/m1_hello.py` passes.
      Compiler implemented in Python 3 (stdlib only).
- [x] **M2A — plain structs + local computation.** Structs, struct literals,
      field access, `let` bindings, integer arithmetic → `examples/m2_structs.crust`;
      `tests/m2a_structs.py` passes.
- [x] **M2B — checked arithmetic + branching.** `bool`, comparisons, `if`/`else`,
      and checked `i32` arithmetic (overflow / div-by-zero / negation overflow
      abort with exit 101) → `examples/m2b_checked_if.crust`;
      `tests/m2b_checked_if.py` and `tests/m2b_behavior.py` pass. Closes the M2A
      checked-arithmetic deferral.
- [x] **M2C — mutability + loops.** `let mut`, assignment statements, and
      `while`/`loop`/`break`/`continue` → `examples/m2c_loops.crust`;
      `tests/m2c_loops.py` and `tests/m2c_diagnostics.py` pass.
- [x] **M2D — full numeric type set.** `i8`…`i64`, `u8`…`u64`, `usize` with
      context-typed literals, same-type-only checked arithmetic/comparisons, and
      non-`i32` struct fields → `examples/m2d_numeric_types.crust`;
      `tests/m2d_numeric.py` and `tests/m2d_checks.py` pass.
- [ ] M2E — `as` casts (defined truncation/wrapping), `&& || !`, and `%`. (No I/O.)
- [ ] M3 — slices (`str`, `[]u8`), `Result`/`Option`, `?`, prelude → compile
      `file_read.crust` and `crust_inspect.crust`.
- [ ] Type checker for the full `v0.1` type set
- [ ] (No move/borrow checker — all v0.1 types copy; see `spec/memory-model.md` §1)
- [ ] Conformance test suite under `tests/` — every example compiles and runs
- [ ] Pick and add a `LICENSE`

Non-goals for this phase are listed in `NON_GOALS.md` and stay non-goals.

## Phase 2 — `v0.2` (candidate features)

Not committed. Most likely first additions, in rough priority order:

1. **Generics** (monomorphized) — the highest-demand non-goal.
2. **`match` expressions** with exhaustiveness.
3. **Sum types** (enums with payloads), paired with `match`.
4. **C FFI** for a minimal set of calling conventions.

Each requires a written proposal and a spec document before it is scheduled.

## Phase 3 and beyond — aspirations

These are explicitly *aspirations*, not commitments:

- A minimal but real standard library.
- A second compilation target / cross-compilation.
- Self-hosting: CRusty++ compiling CRusty++.
- Tooling: formatter, language server.

## Versioning policy

- Versions are frozen once their spec is marked frozen.
- A frozen spec is only ever corrected for *defects* (ambiguity, contradiction),
  never extended with new features.
- New features always create or target a higher version.

## Open decisions

Tracked here until resolved, then moved into the relevant spec:

- License choice (before broader code lands).

Resolved:

- **Backend = portable C** (no LLVM/WASM/native). See `compiler/README.md` and
  `spec/v0.1.md` §9.
- **Compiler implementation language = Python 3** (standard library only), chosen
  at M1 start for minimal footprint and direct `cc` invocation.
- Target triple for the first backend.
