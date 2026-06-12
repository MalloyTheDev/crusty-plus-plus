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

- [ ] Lexer + parser producing an AST that matches `spec/syntax.md`
- [ ] Type checker for the `v0.1` type set
- [ ] Ownership / move checker per `spec/memory-model.md`
- [ ] Code generation for a single target triple
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

- Implementation language for the first compiler (Phase 1).
- License choice (before any code lands).
- Target triple for the first backend.
