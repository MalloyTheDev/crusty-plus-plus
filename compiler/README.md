# compiler/

Home of `crustc`, the CRusty++ reference compiler.

**Status: milestones M1 + M2A + M2B + M2C implemented.** `crustc.py` compiles the
strict M1–M2C subset end-to-end to portable C:

- **M1** — [`../examples/hello.crust`](../examples/hello.crust): `println` + `i32`
  return.
- **M2A** — [`../examples/m2_structs.crust`](../examples/m2_structs.crust): plain
  structs, struct literals, field access, `let` bindings, integer arithmetic.
- **M2B** — [`../examples/m2b_checked_if.crust`](../examples/m2b_checked_if.crust):
  `bool`, comparisons, `if`/`else`, and **checked** integer arithmetic (overflow,
  divide-by-zero, and negation overflow abort with exit code **101**).
- **M2C** — [`../examples/m2c_loops.crust`](../examples/m2c_loops.crust): `let mut`,
  assignment statements, and `while` / `loop` / `break` / `continue`.

Everything beyond this subset is intentionally rejected with a diagnostic, not
parsed — the compiler never accepts more than the spec defines.

- **Implementation language:** Python 3 (standard library only; no dependencies).
- **Backend:** emits portable C, then invokes the system C compiler (`$CC`, or
  `cc`).

## Usage

```sh
# Emit C to stdout:
python3 compiler/crustc.py examples/m2c_loops.crust

# Emit C to a file / build / build-and-run:
python3 compiler/crustc.py examples/m2c_loops.crust --emit-c build/m2c.c
python3 compiler/crustc.py examples/m2c_loops.crust --build build/m2c
python3 compiler/crustc.py examples/m2c_loops.crust --run

# Acceptance + behavior + diagnostic checks:
python3 tests/m1_hello.py
python3 tests/m2a_structs.py
python3 tests/m2b_checked_if.py
python3 tests/m2b_behavior.py
python3 tests/m2c_loops.py
python3 tests/m2c_diagnostics.py
```

## Grammar (exactly what `crustc` accepts today)

```
program     = item+                           ; must contain exactly `main`
item        = struct_decl | function
struct_decl = "struct" ident "{" sfields? "}"
sfields     = sfield ("," sfield)* ","?
sfield      = ident ":" type                  ; field types: i32 only
function    = "fn" "main" "(" ")" "->" "i32" block
block       = "{" statement* "}"
statement   = let_stmt | assign_stmt | return_stmt | if_stmt
            | while_stmt | loop_stmt | "break" ";" | "continue" ";" | call_stmt
let_stmt    = "let" "mut"? ident ":" type "=" expr ";"
assign_stmt = ident "=" expr ";"              ; target is a local variable only
return_stmt = "return" expr ";"
if_stmt     = "if" expr block ("else" (if_stmt | block))?   ; condition is bool
while_stmt  = "while" expr block              ; condition is bool
loop_stmt   = "loop" block                    ; infinite unless break/return
call_stmt   = "println" "(" string_lit ")" ";"   ; M1 carry-over
expr        = equality
equality    = relational (("==" | "!=") relational)*
relational  = add (("<" | "<=" | ">" | ">=") add)*
add         = mul (("+" | "-") mul)*
mul         = unary (("*" | "/") unary)*
unary       = "-" unary | postfix
postfix     = primary ("." ident)*            ; field access
primary     = int_lit | string_lit | "(" expr ")"
            | ident                            ; variable
            | ident "{" finits? "}"            ; struct literal (not in a condition)
finits      = ident ":" expr ("," ident ":" expr)* ","?
type        = "i32" | "bool" | <declared struct name>
```

Notes: an `ident {` immediately inside an `if`/`while` condition is the block
opener, not a struct literal (parenthesize if you need a struct literal there).
Assignment is statement-only (no assignment expression, no `+=`, no field
assignment); `break`/`continue` are valid only inside a loop.

This is a strict subset of [`../spec/syntax.md`](../spec/syntax.md). Function
parameters, `%`, `&& || !`, `as` casts, field assignment, slices, `Result`/
`Option`, `?`, struct-typed fields, integer types other than `i32`, and any
function other than `main` are **rejected** (see Diagnostics). They arrive in
later milestones (see [`../spec/freeze-checklist.md`](../spec/freeze-checklist.md)
and the M2D recommendation in [`../ROADMAP.md`](../ROADMAP.md)).

## Checked arithmetic

`+ - * /` and unary `-` on `i32` lower to runtime helpers, **not** raw C
operators, closing the M2A deferral. On overflow, divide-by-zero, or negation of
`i32::MIN`, the helper calls `crx_panic`, which prints to stderr and `exit(101)`
(abort-only; no unwinding, no catch). The helpers are:

```
crx_panic, crx_checked_add_i32, crx_checked_sub_i32,
crx_checked_mul_i32, crx_checked_div_i32, crx_checked_neg_i32
```

Each is emitted only when referenced. `bool` lowers to C `<stdbool.h>`;
comparisons lower to C comparison operators; `if`/`else` to C `if`/`else`.

Control flow (M2C): `let mut` and assignment lower to ordinary C locals and `=`;
`while` to C `while`; `loop` to `for (;;)`; `break`/`continue` to C
`break`/`continue`. A conservative all-paths-return check ensures `main` cannot
fall off the end (a `while` may fall through; a `loop` with no `break` does not).

## Pipeline

```
source (.crust)
   │  lexer        → tokens          (crustc.py: tokenize)
   │  parser       → AST             (crustc.py: Parser)
   │  type checker → validated AST   (crustc.py: Checker)
   │  C emitter    → portable C      (crustc.py: Emitter)
   ▼
C source  →  system C compiler  →  executable
```

## Diagnostic codes

| Code | Meaning |
|------|---------|
| `CRX0001` | unexpected character / unknown escape (lexer) |
| `CRX0002` | unterminated string literal |
| `CRX0003` | parse error (expected token X) |
| `CRX0010` | program has no `main` |
| `CRX0011` | invalid `main` signature / `main` does not return on every path |
| `CRX0012` | unknown function (only `println` exists) |
| `CRX0013` | wrong argument count |
| `CRX0014` | type mismatch (argument, return, `let`, or struct field init) |
| `CRX0015` | construct not supported yet (params, struct-typed fields, …) |
| `CRX0020` | duplicate struct field (declaration) |
| `CRX0021` | unknown type (in a type annotation or field type) |
| `CRX0022` | unknown struct type (in a struct literal) |
| `CRX0023` | missing struct field (in a struct literal) |
| `CRX0024` | extra / duplicate struct field (in a struct literal) |
| `CRX0025` | unknown field access |
| `CRX0026` | field access on a non-struct value |
| `CRX0027` | unknown variable |
| `CRX0028` | invalid arithmetic operand type (non-`i32`) |
| `CRX0029` | invalid comparison operand type (non-`i32`) |
| `CRX0030` | non-`bool` `if` / `while` condition |
| `CRX0031` | assignment to an immutable local |
| `CRX0032` | invalid assignment target (field assignment / non-variable) |
| `CRX0033` | `break` outside a loop |
| `CRX0034` | `continue` outside a loop |

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
