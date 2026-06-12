# compiler/

This directory is the future home of the CRusty++ compiler. **It is intentionally
empty of code.**

Per the project's first principle — *specify before implementing* — no compiler
work begins until the design phase closes. See
[`../ROADMAP.md`](../ROADMAP.md) (Phase 0 → Phase 1).

## Entry criteria (when code may start here)

Work in this directory begins only when **all** of the following hold. This list
is the gate; the live status of each item is tracked in
[`../spec/freeze-checklist.md`](../spec/freeze-checklist.md).

1. **Syntax subset frozen.** [`../spec/syntax.md`](../spec/syntax.md) is marked
   **frozen** with no open questions.
2. **Semantics frozen.** [`../spec/v0.1.md`](../spec/v0.1.md),
   [`../spec/memory-model.md`](../spec/memory-model.md), and
   [`../spec/error-handling.md`](../spec/error-handling.md) are frozen with no
   open questions.
3. **Non-goals frozen.** [`../NON_GOALS.md`](../NON_GOALS.md) is frozen, so the
   compiler knows exactly what it must *reject*.
4. **First target examples frozen.** Every program in
   [`../examples/`](../examples/) is fully explained by the frozen spec — no
   construct appears that the spec does not define — and forms the acceptance set.
5. **Expected generated C shape defined.** v0.1 emits **portable C** (see
   below); the rough mapping from CRusty++ constructs to C must be written down
   before codegen starts (freeze-checklist B6/C1).
6. **Diagnostics expectations defined.** What every rejection must report — a
   stable diagnostic code plus a source span — is specified (freeze-checklist
   C12), so the reject-tests have something to assert against.

All six blockers in [`../spec/freeze-checklist.md`](../spec/freeze-checklist.md)
§F must be closed first.

## Planned shape of the first compiler

A straightforward, single-pass-ish pipeline (details fixed at Phase 1 start):

```
source (.crust)
   │  lexer        → tokens          (per spec/syntax.md §3–5)
   │  parser       → AST             (per spec/syntax.md §6)
   │  type checker → typed AST       (per spec/v0.1.md §2)
   │  move/borrow checker            (per spec/memory-model.md)
   │  codegen      → portable C      (recommended backend, per freeze-checklist B6)
   ▼
C source  →  system C compiler  →  executable
```

The recommended v0.1 backend is **emitting portable C** and invoking a system C
compiler — not LLVM, not WASM (both [non-goals](../NON_GOALS.md)). This keeps the
first prototype small. The exact generated-C shape must be written down before
codegen starts (freeze-checklist B6/C1) and is *pending freeze*, not yet final.

## Open decisions (tracked in ROADMAP and freeze-checklist)

- Implementation language for this first compiler.
- Backend confirmation (recommended: portable C) and the generated-C shape.
- License (must be chosen before any code lands here).

Until the entry criteria are met, the only correct change to this directory is to
the specification it depends on — not to this directory.
