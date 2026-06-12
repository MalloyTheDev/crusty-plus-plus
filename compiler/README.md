# compiler/

Home of `crustc`, the CRusty++ reference compiler.

**Status: milestone M1 implemented.** `crustc.py` compiles the strict M1 subset
(just enough for [`../examples/hello.crust`](../examples/hello.crust)) end-to-end
to portable C. Everything beyond M1 is intentionally rejected with a diagnostic,
not parsed — the compiler never accepts more than the spec defines.

- **Implementation language:** Python 3 (standard library only; no dependencies).
- **Backend:** emits portable C, then invokes the system C compiler (`$CC`, or
  `cc`).

## Usage

```sh
# Emit C to stdout:
python3 compiler/crustc.py examples/hello.crust

# Emit C to a file:
python3 compiler/crustc.py examples/hello.crust --emit-c build/hello.c

# Build an executable via the system C compiler:
python3 compiler/crustc.py examples/hello.crust --build build/hello

# Build and run:
python3 compiler/crustc.py examples/hello.crust --run

# Full M1 acceptance check (golden C + build + run + stdout/exit assertions):
python3 tests/m1_hello.py
```

## M1 grammar (exactly what `crustc` accepts today)

```
program   = function+                         ; must contain exactly `main`
function  = "fn" "main" "(" ")" "->" "i32" block
block     = "{" statement* "}"
statement = call_stmt | return_stmt
call_stmt = "println" "(" string_lit ")" ";"
return_stmt = "return" int_lit ";"
```

This is a strict subset of [`../spec/syntax.md`](../spec/syntax.md). Parameters,
operators, variables, structs, slices, `Result`/`Option`, and any function other
than `main` are rejected (see Diagnostics below). They arrive in later milestones
(see [`../spec/freeze-checklist.md`](../spec/freeze-checklist.md) and the M2
recommendation in [`../ROADMAP.md`](../ROADMAP.md)).

## Pipeline

```
source (.crust)
   │  lexer        → tokens          (crustc.py: tokenize)
   │  parser       → AST             (crustc.py: Parser)
   │  type checker → validated AST   (crustc.py: check)
   │  C emitter    → portable C      (crustc.py: emit_c)
   ▼
C source  →  system C compiler  →  executable
```

## Diagnostic codes (M1)

| Code | Meaning |
|------|---------|
| `CRX0001` | unexpected character / unknown escape (lexer) |
| `CRX0002` | unterminated string literal |
| `CRX0003` | parse error (expected token X) |
| `CRX0010` | program has no `main` |
| `CRX0011` | invalid `main` signature / missing `i32` return |
| `CRX0012` | unknown function (only `println` exists in M1) |
| `CRX0013` | wrong argument count |
| `CRX0014` | type mismatch (argument or return) |
| `CRX0015` | construct not supported in M1 (params, variables, extra fns, …) |

---

## Entry criteria for later milestones (M2+)

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
5. **Expected generated C shape defined.** ✅ v0.1 emits **portable C**; the
   construct→C mapping is defined under "Generated C" below.
6. **Diagnostics expectations defined.** ✅ Defined under "Diagnostics" below:
   stable error code, file path, line/column span, short message.

All six blockers in [`../spec/freeze-checklist.md`](../spec/freeze-checklist.md)
§F must be closed first.

## Planned shape of the first compiler

A straightforward, single-pass-ish pipeline (details fixed at Phase 1 start):

```
source (.crust)
   │  lexer        → tokens          (per spec/syntax.md §3–5)
   │  parser       → AST             (per spec/syntax.md §6)
   │  type checker → typed AST       (per spec/v0.1.md §2)
   │  (no move/borrow checker in v0.1 — all types copy; memory-model.md §1)
   │  codegen      → portable C      (frozen backend; see "Generated C" below)
   ▼
C source  →  system C compiler  →  executable
```

## Backend: portable C (frozen)

The v0.1 backend **emits portable C** and invokes a system C compiler — **not**
LLVM, **not** WASM, **not** a native machine-code backend. This keeps the first
prototype small, readable, and debuggable.

### Generated-C shape

Generated C must be readable and debuggable, and must preserve the strict
left-to-right evaluation order of [`../spec/v0.1.md`](../spec/v0.1.md) §2.8.

| CRusty++ construct | Lowers to |
|--------------------|-----------|
| function `fn f(...) -> T` | one C function `T f(...)` |
| `struct S { ... }` | a plain C `struct S { ... }` |
| slice `str`, `[]u8` | a `{ pointer, length }` C struct (e.g. `crust_slice`) |
| `.len` | read of the slice struct's `length` field |
| `Result<T, E>` | a tagged struct: a tag plus a union/payload of `T`/`E` |
| `Option<T>` | a tagged struct (tag plus payload), pending later optimization |
| `()` | C `void` (for returns) |
| checked `+ - * / %`, negation | inline check that calls the abort shim on overflow / div-by-zero |
| `panic(msg)` | print `msg` to stderr, then `abort()`-like exit with code 101 |

v0.1 makes **no ABI/layout stability guarantees** across versions; the generated
C shape may change between versions.

## Diagnostics (frozen expectations)

Every compiler **error** must include:

- a **stable error code** (e.g. `CRX0001`) that tests can assert on;
- the **file path**;
- a **line/column span**;
- a **short message**;
- a **one-line help suggestion** when one is obvious.

Diagnostics tests assert on the **error code and span**, not exact prose, so
messages can be reworded without breaking tests. Fancy/structured suggestions are
an optional later refinement.

## Open decisions (tracked in ROADMAP and freeze-checklist)

These do **not** block starting the first milestone; they are chosen at Phase 1
start:

- Implementation language for this first compiler.
- License (must be chosen before any code lands here).

Until the entry criteria are met, the only correct change to this directory is to
the specification it depends on — not to this directory.
