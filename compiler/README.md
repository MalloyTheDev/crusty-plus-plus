# compiler/

Home of `crustc`, the CRusty++ reference compiler.

**Status: milestones M1 + M2A + M2B + M2C + M2D + M2E + M3A + M3B implemented.**
`crustc.py` compiles the strict M1–M3B subset end-to-end to portable C:

- **M1** — [`../examples/hello.crust`](../examples/hello.crust): `println` + `i32`
  return.
- **M2A** — [`../examples/m2_structs.crust`](../examples/m2_structs.crust): plain
  structs, struct literals, field access, `let` bindings, integer arithmetic.
- **M2B** — [`../examples/m2b_checked_if.crust`](../examples/m2b_checked_if.crust):
  `bool`, comparisons, `if`/`else`, and **checked** integer arithmetic (overflow,
  divide-by-zero, and negation overflow abort with exit code **101**).
- **M2C** — [`../examples/m2c_loops.crust`](../examples/m2c_loops.crust): `let mut`,
  assignment statements, and `while` / `loop` / `break` / `continue`.
- **M2D** — [`../examples/m2d_numeric_types.crust`](../examples/m2d_numeric_types.crust):
  the full integer type set (`i8`…`i64`, `u8`…`u64`, `usize`) with context-typed
  literals, same-type-only checked arithmetic/comparisons, and non-`i32` struct
  fields.
- **M2E** — [`../examples/m2e_casts.crust`](../examples/m2e_casts.crust): explicit
  numeric `as` casts (the only way to narrow or reinterpret a numeric value;
  casts never panic).
- **M3A** — [`../examples/m3a_slices.crust`](../examples/m3a_slices.crust): the
  built-in fat-slice types `str` and `[]u8` with read-only `.len: usize`.
- **M3B** — [`../examples/m3b_result_option.crust`](../examples/m3b_result_option.crust):
  the built-in core types `Result<T, E>` and `Option<T>` with constructors
  `Ok`/`Err`/`Some`/`None` and inspectors `is_ok`/`is_err`/`unwrap`.

Everything beyond this subset is intentionally rejected with a diagnostic, not
parsed — the compiler never accepts more than the spec defines.

- **Implementation language:** Python 3 (standard library only; no dependencies).
- **Backend:** emits portable C, then invokes the system C compiler (`$CC`, or
  `cc`).

## Usage

```sh
# Emit C to stdout / file, build, build-and-run:
python3 compiler/crustc.py examples/m3b_result_option.crust
python3 compiler/crustc.py examples/m3b_result_option.crust --emit-c build/m3b.c
python3 compiler/crustc.py examples/m3b_result_option.crust --run

# Acceptance + behavior + diagnostic checks:
for t in m1_hello m2a_structs m2b_checked_if m2b_behavior m2c_loops \
         m2c_diagnostics m2d_numeric m2d_checks m2e_casts m2e_checks \
         m3a_slices m3a_checks m3b_result_option m3b_checks; do
    python3 tests/$t.py || break
done
```

## Grammar (exactly what `crustc` accepts today)

```
program     = item+                           ; must contain exactly `main`
item        = struct_decl | function
struct_decl = "struct" ident "{" sfields? "}"
sfields     = sfield ("," sfield)* ","?
sfield      = ident ":" type                  ; field types: numeric or bool
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
mul         = cast (("*" | "/") cast)*
cast        = unary ("as" type)*              ; explicit numeric cast
unary       = "-" unary | postfix
postfix     = primary ("." ident)*            ; field access
primary     = int_lit | string_lit | "(" expr ")"
            | ident                            ; variable
            | ident "{" finits? "}"            ; struct literal (not in a condition)
            | ("Ok" | "Err" | "Some") "(" expr ")"   ; core-type constructors
            | "None"
finits      = ident ":" expr ("," ident ":" expr)* ","?
type        = numeric_type | "bool" | "str" | "[" "]" "u8"
            | core_type | <declared struct name>
numeric_type = "i8" | "i16" | "i32" | "i64"
             | "u8" | "u16" | "u32" | "u64" | "usize"
core_type   = "Option" "<" type ">" | "Result" "<" type "," type ">"
```

`postfix`'s `.len` on a `str`/`[]u8` value is the built-in slice length; on a
struct it is ordinary field access.

Notes: an `ident {` immediately inside an `if`/`while` condition is the block
opener, not a struct literal (parenthesize if you need a struct literal there).
Assignment is statement-only (no assignment expression, no `+=`, no field
assignment); `break`/`continue` are valid only inside a loop.

`as` binds **looser than unary `-`** but **tighter than `* /` and the other
binary operators**: `-x as T` is `(-x) as T`; `a as T + b` is `(a as T) + b`.
Casts are left-associative. Parenthesize for any other grouping.

This is a strict subset of [`../spec/syntax.md`](../spec/syntax.md). Function
parameters, `%`, `&& || !`, field assignment, indexing/slicing expressions, array
literals, `?`, file I/O, nested/struct-field core types, struct-typed fields, and
any function other than `main` are **rejected** (see Diagnostics). They arrive in
later milestones (see [`../spec/freeze-checklist.md`](../spec/freeze-checklist.md)
and the M3C recommendation in [`../ROADMAP.md`](../ROADMAP.md)).

## Casts (M2E)

`expr as Type` converts between numeric types only (`bool`/struct sources or
targets are rejected: `CRX0038`/`CRX0039`). The source is type-checked on its own
(so `300 as u8` is allowed even though `300` overflows `u8`). **Casts never
panic** — they are the explicit escape valve from checked arithmetic. Semantics
(defined two's-complement):

| Cast | Result |
|------|--------|
| widen signed → signed | sign-extend |
| widen unsigned → unsigned/wider signed | zero-extend |
| signed → unsigned | reinterpret modulo 2^width |
| narrow / same-width sign change | truncate to width, reinterpret |

Examples: `300 as u8 == 44`, `-1 as u8 == 255`, `255 as i8 == -1`,
`65535 as i16 == -1`.

**Lowering:** casts to an unsigned type, and value-preserving widenings, lower to
a direct C cast (both fully defined). Casts to a signed type whose value may not
fit (narrowing, or a same-width unsigned source) lower through a
`crx_cast_to_<itype>` helper that masks to the target width and reinterprets as
two's complement, avoiding C's implementation-defined out-of-range signed
conversion.

**Target model:** `usize` is treated as **64-bit** (`size_t`) — the current build
target. A future multi-target backend must make pointer width explicit; M2E does
not solve cross-target `usize`.

## Numeric type rules (M2D)

- **Types:** `i8 i16 i32 i64`, `u8 u16 u32 u64`, `usize` (`size_t`), plus `bool`.
- **Literal typing:** an integer literal is context-typed (from the `let`/field/
  operand it flows into) and defaults to `i32` with no context. A literal must
  fit its target type or it is a compile-time error (`CRX0036`). A negative
  literal is unary `-` over a positive literal, range-checked as a whole — so
  `i8 = -128` and `i32 = -2147483648` are valid even though `128`/`2147483648`
  alone overflow.
- **Same-type only:** arithmetic and comparison operands must have the **exact
  same** numeric type — no implicit promotion, no mixed sign, no mixed width
  (`CRX0035` / `CRX0029`). The result is that type (arithmetic) or `bool`
  (comparison). Unary `-` is signed-only (`CRX0037`).

## Slices: `str` and `[]u8` (M3A)

- `str` and `[]u8` are built-in **fat slices** — a (pointer, length) pair. They
  are non-owning, non-null in the language model, immutable, and copied by value
  (the C struct is copied; the pointee is not).
- A **string literal has type `str`**. As a `let`/field value it lowers to a
  `crx_str` over the C string literal; as a `println` argument it stays a direct
  `puts("...")` (M1 behavior).
- **`.len`** is a built-in read-only `usize` on `str`/`[]u8` and takes precedence
  over struct field lookup (they are not user structs). `.len` on a struct is
  ordinary field access; `.len` on a numeric/`bool` value is rejected
  (`CRX0026`); any slice field other than `.len` is rejected (`CRX0025`).
- Arithmetic, comparison, and casts involving `str`/`[]u8` are **invalid** — they
  fall out of the numeric-only rules (`CRX0028` / `CRX0029` / `CRX0038` /
  `CRX0039`).
- **No indexing, slicing, mutation, or bounds model** yet (none are implemented),
  and there is **no value source for `[]u8`** in M3A — it is a valid type (e.g. a
  struct field) and lowers to C, but cannot yet be constructed (that arrives with
  M3 file I/O). No fake I/O primitive is invented to produce one.

**String byte length.** `str.len` (and the lowered `crx_str` length) is the
**UTF-8 byte length**, with each escape (`\n \t \\ \"`) counted as the one byte
it decodes to — not a Unicode scalar count.

**Lowering.** `str` → `typedef struct { const char *ptr; size_t len; } crx_str;`;
`[]u8` → `typedef struct { const uint8_t *ptr; size_t len; } crx_slice_u8;`. A
string literal value → `(crx_str){ "literal", <byte-len> }`. `.len` → the C `.len`
field. The slice typedefs are emitted before any user struct that embeds them.

## Core types: `Result<T, E>` and `Option<T>` (M3B)

- These two are the **only** angle-bracket type forms — built-in core type
  constructors, **not** user generics. Any other `Name<...>` is rejected
  (`CRX0041`).
- Constructors `Ok(v)`, `Err(e)`, `Some(v)`, `None` are **context-typed**: their
  type comes from the expected `Result<T, E>` / `Option<T>` at the use site (a
  `let` annotation, assignment target, struct field, …). A constructor with no
  matching expected type is rejected (`CRX0042`); one whose type cannot be
  inferred at all (e.g. `is_ok(None)`) is `CRX0040`. Two core types are equal iff
  their constructor and all parameters are equal. They copy by value.
- **Inspectors:** `is_ok(r)` / `is_err(r)` are `Result`-only and return `bool`;
  `unwrap(x)` works on both `Result` and `Option`, returning the `Ok`/`Some`
  payload and **panicking (exit 101) on `Err`/`None`** via `crx_panic`. A wrong
  inspector argument type is `CRX0043`.
- **Restrictions (M3B):** nested core types (`Result<Option<i32>, i32>`) and core
  types as struct fields are deferred (`CRX0015`). Arithmetic/comparison/cast on a
  core type fall out of the numeric-only rules.

**Lowering (tag 1 = present/success, 0 = absent/failure):**
- `Option<T>` → `typedef struct { int32_t tag; T some; } crx_option_<T>;`.
- `Result<T, E>` → `typedef struct { int32_t tag; union { T ok; E err; } payload; } crx_result_<T>_<E>;`.
- `Ok(v)`→`{ .tag = 1, .payload.ok = v }`, `Err(e)`→`{ .tag = 0, .payload.err = e }`,
  `Some(v)`→`{ .tag = 1, .some = v }`, `None`→`{ .tag = 0 }`.
- `is_ok`/`is_err` → `(x.tag == 1)` / `(x.tag == 0)`; `unwrap` → a
  `crx_unwrap_<type>` helper. Core typedefs are emitted after slices and user
  structs (their payloads may be either); unwrap helpers after the typedefs.

## Checked arithmetic

`+ - * /` and unary `-` lower to per-type runtime helpers
(`crx_checked_<op>_<type>`), **not** raw C operators. On overflow, underflow,
divide-by-zero, or `MIN`-negation/division, the helper calls `crx_panic`, which
prints to stderr and `exit(101)` (abort-only; no unwinding, no catch). Narrow
types are checked by widening to 64-bit; 64-bit types use range/wraparound
guards. Each helper is emitted only when referenced.

`bool` lowers to C `<stdbool.h>`; each integer type to its `<stdint.h>` /
`<stddef.h>` fixed-width C type; comparisons to C comparison operators;
`if`/`else` to C `if`/`else`.

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
| `CRX0028` | non-numeric arithmetic operand |
| `CRX0029` | non-numeric or mixed-type comparison operands |
| `CRX0030` | non-`bool` `if` / `while` condition |
| `CRX0031` | assignment to an immutable local |
| `CRX0032` | invalid assignment target (field assignment / non-variable) |
| `CRX0033` | `break` outside a loop |
| `CRX0034` | `continue` outside a loop |
| `CRX0035` | mixed-type arithmetic (operands differ in numeric type) |
| `CRX0036` | integer literal out of range for its type |
| `CRX0037` | unary `-` applied to an unsigned type |
| `CRX0038` | invalid cast source type (`bool` / struct / core type) |
| `CRX0039` | invalid cast target type (`bool` / struct / core type) |
| `CRX0040` | cannot infer a constructor's type (no expected core type) |
| `CRX0041` | user-defined generic type (only built-in `Option`/`Result`) |
| `CRX0042` | constructor used where a non-matching type is expected |
| `CRX0043` | inspector (`is_ok`/`is_err`/`unwrap`) given a wrong argument type |

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
