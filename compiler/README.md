# compiler/

This directory is the future home of the CRusty++ compiler. **It is intentionally
empty of code.**

Per the project's first principle — *specify before implementing* — no compiler
work begins until the design phase closes. See
[`../ROADMAP.md`](../ROADMAP.md) (Phase 0 → Phase 1).

## Entry criteria (when code may start here)

Work in this directory begins only when **all** of the following hold:

1. [`../spec/v0.1.md`](../spec/v0.1.md) is marked **frozen**.
2. The companion specs are frozen and have no open questions:
   - [`../spec/syntax.md`](../spec/syntax.md)
   - [`../spec/memory-model.md`](../spec/memory-model.md)
   - [`../spec/error-handling.md`](../spec/error-handling.md)
3. Every program in [`../examples/`](../examples/) is fully explained by the
   frozen spec — no construct appears that the spec does not define.

## Planned shape of the first compiler

A straightforward, single-pass-ish pipeline (details fixed at Phase 1 start):

```
source (.crust)
   │  lexer        → tokens          (per spec/syntax.md §3–5)
   │  parser       → AST             (per spec/syntax.md §6)
   │  type checker → typed AST       (per spec/v0.1.md §2)
   │  move/borrow checker            (per spec/memory-model.md)
   │  codegen      → single target   (one triple, per ROADMAP open questions)
   ▼
executable
```

## Open decisions (tracked in ROADMAP)

- Implementation language for this first compiler.
- Backend / target triple.
- License (must be chosen before any code lands here).

Until the entry criteria are met, the only correct change to this directory is to
the specification it depends on — not to this directory.
