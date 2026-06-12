# CRusty++ v0.1 Freeze Checklist

> Purpose: the single gate between design and compiler work. It tracks which
> blockers are resolved, what remains open, and whether the prototype may begin.
>
> Spec status after the 2026-06-12 decisions: the four specs and this checklist
> are **FREEZE-CANDIDATE**. They move to **FROZEN** when §G reports zero blockers
> *and* the remaining should-resolve items in §C are either closed or explicitly
> accepted as prototype limitations.

Legend: 🔴 **blocker** · 🟡 **should resolve** (non-blocking) · 🟢 **resolved /
settled**. This file does not expand v0.1 scope; see
[`../NON_GOALS.md`](../NON_GOALS.md).

---

## A. Settled from day one (unchanged) 🟢

`main` entry; errors-as-values; abort-only `panic` (exit 101); immutable-by-
default; no implicit numeric conversion; whole-program/one-namespace; control
flow `if`/`while`/`loop`; checked arithmetic. All consistent across docs.

## B. Blockers B1–B6 — RESOLVED 🟢

All six audit blockers are decided and reflected in the specs.

- **B1 — `str` model.** ✅ `str` is a built-in **immutable fat slice** (pointer +
  length), non-owning, non-null, passed **by value**. `&str` removed from specs
  and examples. (`v0.1.md` §2.1/§2.5, `memory-model.md` §1, `syntax.md` §6.4.)
- **B2 — `Option`/`Result` syntax.** ✅ `Option<T>` and `Result<T, E>` are the
  **only** angle-bracket types — built-in `core_type` sugar, **not** user
  generics. Grammar recognizes exactly these two forms. (`syntax.md` §6.4/§7,
  `v0.1.md` §2.7, `NON_GOALS.md`.)
- **B3 — `String` construction / `::`.** ✅ Owned `String` **removed** from v0.1;
  text is `str`. No `::` syntax. No `String::from`. (`v0.1.md` §2.1,
  `syntax.md` §5/§7, examples.)
- **B4 — prelude.** ✅ Frozen prelude table: `print`, `println`,
  `read_all_bytes`, `is_ok`, `is_err`, `unwrap`, `panic`, plus constructors
  `Ok`/`Err`/`Some`/`None` and built-in `FileError`. Undefined helpers
  (`read_to_string`, `string_len`) removed. (`v0.1.md` §2.9.)
- **B5 — integer-literal typing.** ✅ Integer literals are context-typed,
  defaulting to `i32`; float literals default to `f64`. (`v0.1.md` §2.2,
  `syntax.md` §4.)
- **B6 — backend.** ✅ Backend is **portable C**; generated-C shape and ABI
  stance defined. (`v0.1.md` §9, `compiler/README.md`.)

## C. Should-resolve items 🟡 / 🟢

Most are now decided; the few still open are **non-blocking** for the prototype.

- **C1 generated-C style** 🟢 — defined (`compiler/README.md` → Generated C).
- **C2 ABI/layout** 🟢 — no stability guarantee across versions; stated.
- **C3 ignored `Result`** 🟢 — allowed in v0.1; warning is a later, never an
  error. (`error-handling.md` §7.)
- **C4 `?` in `main`** 🟢 — not allowed when `main` returns `i32`; examples use
  `i32` `main`. (`error-handling.md` §3.)
- **C5 struct copy vs move** 🟢 — all v0.1 types **copy**; no move types yet.
  (`v0.1.md` §7, `memory-model.md` §1.)
- **C6 assign to immutable** 🟢 — compile error; moves don't exist in v0.1.
  (`v0.1.md` §6.)
- **C7 evaluation order** 🟢 — strict left-to-right; argument order L-to-R; RHS
  before mutation. (`v0.1.md` §2.8.)
- **C8 div/negation overflow** 🟢 — both defined panics. (`v0.1.md` §8,
  `error-handling.md` §5.)
- **C9 unused variables** 🟢 — allowed in v0.1.
- **C10 length type** 🟢 — `.len` is `usize`; no `str_len` function.
- **C11 field-move granularity** 🟡 — documented as future design intent only;
  irrelevant to v0.1 (no moves). Not a blocker. (`memory-model.md` §3.)
- **C12 diagnostics** 🟢 — error code + path + line/col span + message defined.
  (`compiler/README.md` → Diagnostics.)
- **C13 `read_all_bytes` buffer ownership** 🟡 — the returned `[]u8` is
  **leaked** in v0.1 (no owned buffers, no drops). Documented and accepted as a
  prototype limitation; revisited with owned-buffer types. (`v0.1.md` §2.9.) Not
  a blocker.
- **C14 `Result`-returning `main`** 🟡 — `fn main() -> Result<i32, E>` is
  *recognized* but `Err`→exit-code mapping is **unspecified**; do not use it
  until specified. v0.1 examples use `i32` `main`, so this does not block.
  (`error-handling.md` §6.)

## D. Memory-model honesty (stated in `memory-model.md` §0) 🟢

v0.1 is safer than C but not Rust-level; copy semantics, no move checker; non-null
references; no raw pointers/`unsafe` implementation (keyword reserved); slices are
ptr+len; arena/allocator deferred.

## E. Acceptance set (examples that define v0.1 success)

- `examples/hello.crust` — **clean.** Uses only `main`, `println`, `return`.
- `examples/file_read.crust` — **clean.** `Result`, `?`, `read_all_bytes`,
  `is_err`, `unwrap`, `[]u8`, `.len`, `as`, distinct exit codes.
- `examples/crust_inspect.crust` — **clean (flagship).** Adds `struct`, struct
  literal, context-typed literals, and `panic`.

All three are fully explained by the FREEZE-CANDIDATE specs. No example uses an
undefined construct.

## F. Remaining open questions (none block the first milestone)

1. Implementation language for the first compiler (chosen at Phase 1 start).
2. License (before any code lands).
3. Richer `FileError` representation (v0.1 ships an opaque error with `.code`).
4. `Result`-returning `main` semantics (C14) — deferred until needed.
5. `read_all_bytes` buffer reclamation (C13) — deferred with owned buffers.

## G. Readiness verdict

- **Blockers remaining: 0.** B1–B6 resolved; no 🔴 items left.
- **Spec status: FREEZE-CANDIDATE** (not yet FROZEN: §F items 3–5 are accepted
  prototype limitations rather than fully specified, so the prudent status is
  FREEZE-CANDIDATE until the first milestone validates the C lowering).
- **Compiler prototype: MAY START — milestone 1 only.**

### Implemented milestones

**M1 — `hello.crust` end-to-end to C.** ✅ Implemented in `compiler/crustc.py`
(Python 3, stdlib only): lexer → parser → type checker → portable-C emitter.
`tests/m1_hello.py` builds via the system C compiler, runs, and asserts stdout
`Hello, CRusty++!` and exit `0`. Resolved open question F1 (implementation
language = Python 3).

**M2A — plain structs + local computation.** ✅ Structs, struct literals, field
access, `let` bindings (annotations still mandatory per `v0.1.md` §2.3; the
checker infers the initializer type and validates it against the annotation), and
`+ - * /` integer arithmetic. Target `examples/m2_structs.crust`;
`tests/m2a_structs.py` passes (exit `0`). New diagnostics CRX0020–CRX0028.

**M2B — checked arithmetic + branching.** ✅ `bool`, comparisons (→ `bool`),
`if`/`else` (condition must be `bool`), unary `-`, and **checked `i32`
arithmetic**. Target `examples/m2b_checked_if.crust` (`tests/m2b_checked_if.py`,
exit `0`). New diagnostics CRX0029 (comparison operand type) and CRX0030 (non-bool
`if` condition).

> **Checked-arithmetic gap — CLOSED for `i32`.** `+ - * /` and unary `-` lower to
> runtime helpers that `panic` (abort, exit 101) on overflow, divide-by-zero, and
> `i32::MIN` negation/division, per `v0.1.md` §8 and `error-handling.md` §5.
> Proven by `tests/m2b_behavior.py` (six cases, all exit 101). Remaining scope:
> apply the same checked lowering to the other integer widths when they are added
> (M2D) — `i32` is the only integer type implemented so far.

**M2C — mutability + loops.** ✅ `let mut`, statement-level assignment to local
variables (no field assignment, no compound assignment, no assignment
expression), and `while` / `loop` / `break` / `continue`. Immutable locals reject
assignment; `break`/`continue` outside a loop are rejected; `while` conditions
must be `bool`; the all-paths-return check now reasons conservatively about loops.
Target `examples/m2c_loops.crust` (`tests/m2c_loops.py`, exit `0`) plus
`tests/m2c_diagnostics.py` (5 negative + 2 positive cases). New diagnostics
CRX0031 (assign to immutable), CRX0032 (invalid assignment target), CRX0033
(`break` outside loop), CRX0034 (`continue` outside loop); CRX0030 now also covers
non-`bool` `while` conditions.

**M2D — full numeric type set.** ✅ `i8`…`i64`, `u8`…`u64`, `usize` (plus `bool`
from M2B). Integer literals are context-typed (default `i32`) and range-checked
against their target type; negative literals are range-checked as a whole.
Arithmetic and comparison operands must be the **exact same** numeric type (no
implicit promotion, sign mix, or width mix); unary `-` is signed-only. Checked
arithmetic now covers every width via per-type `crx_checked_<op>_<type>` helpers
(narrow types widen to 64-bit; 64-bit types use range/wraparound guards). Struct
fields may be any numeric type or `bool`. Target `examples/m2d_numeric_types.crust`
(`tests/m2d_numeric.py`, exit `0`) plus `tests/m2d_checks.py` (5 runtime-101
cases, 1 usize-positive, 4 negative compile cases). New diagnostics CRX0035
(mixed arithmetic), CRX0036 (literal out of range), CRX0037 (unsigned unary `-`);
CRX0028/CRX0029 generalized from "non-i32" to "non-numeric / mixed type".

**M2E — explicit numeric casts.** ✅ `expr as Type` converts between numeric types
only (`bool`/struct source or target → CRX0038/CRX0039; unknown target → CRX0021).
The source is type-checked independently so `300 as u8` is legal. Casts are
**total and never panic**, with defined two's-complement semantics: widen
sign-/zero-extends, narrow truncates, sign changes reinterpret. Lowering uses a
direct C cast where defined (unsigned target, value-preserving widening) and a
`crx_cast_to_<itype>` reinterpretation helper otherwise. `as` binds looser than
unary `-`, tighter than `* /` (a spec-precedence inconsistency between
`syntax.md` §5 and §6.7 was corrected to match). Target
`examples/m2e_casts.crust` (`tests/m2e_casts.py`, exit `0`) plus
`tests/m2e_checks.py` (6 cast-value programs + 4 negative cases).

> **M2 numeric system is complete; boolean/`%` layer is not.** Casts close the
> last *numeric* foundation. Still deferred for later: `%`, `&& || !`. `usize`
> is treated as 64-bit `size_t`; cross-target pointer width is future work.

**M3A — slices.** ✅ Built-in fat-slice types `str` and `[]u8` (`{ ptr, len }`,
non-owning, non-null, immutable, copied by value) with read-only `.len: usize`.
String literals have type `str`; `str.len` is the UTF-8 **byte** length (escapes
counted as their bytes). Slice `.len` takes precedence over struct field lookup;
`.len` on a non-slice/non-struct value is rejected (CRX0026); a slice field other
than `len` is rejected (CRX0025). Arithmetic/comparison/cast on `str`/`[]u8` are
rejected via the existing numeric-only rules (CRX0028/CRX0029/CRX0038/CRX0039) —
**no new diagnostic codes were needed**. Lowering: `str → crx_str`,
`[]u8 → crx_slice_u8`, string literal → `(crx_str){ "...", byte_len }`. Target
`examples/m3a_slices.crust` (`tests/m3a_slices.py`, exit `0`) plus
`tests/m3a_checks.py` (4 runtime + 6 negative cases).

> **`[]u8` is type/lowering only in M3A.** There is no value source for `[]u8`
> yet (no file I/O, indexing, or array literals), so it is allowed as a type and
> struct field and lowers to C, but cannot be constructed. A runtime `[]u8` value
> arrives with **M3D** (`read_all_bytes`).

**M3B — `Result`/`Option` core types.** ✅ Built-in `Result<T, E>` and `Option<T>`
(the only angle-bracket types; user generics rejected, CRX0041) with constructors
`Ok`/`Err`/`Some`/`None` and inspectors `is_ok`/`is_err`/`unwrap`. Constructors are
context-typed (their type comes from the expected core type; no expected → CRX0042,
un-inferrable → CRX0040; wrong inspector arg → CRX0043). Lowering: tagged structs
`crx_option_<T>` / `crx_result_<T>_<E>` (tag 1 = Some/Ok, 0 = None/Err); `unwrap`
helpers panic (exit 101) on None/Err. Target `examples/m3b_result_option.crust`
(`tests/m3b_result_option.py`, exit 0) + `tests/m3b_checks.py` (7 runtime, 6
negative).

> **Two deliberate decisions, recorded:** (1) `unwrap` was extended to accept
> `Option<T>` (the frozen prelude listed it as Result-only) so the M3B
> Option/None paths are testable — spec updated (`v0.1.md` §2.9,
> `error-handling.md` §1–2) under the user's M3B directive. (2) **Nested core
> types and core-typed struct fields are deferred** in M3B (CRX0015); the spec
> grammar admits nesting, so this is a milestone restriction, not a spec change.
> Agent-1 recommended clarifications applied: `None` context-typing, core-type
> equality, constructor payload typing. Next: **M3C** (`?` propagation). Specs
> remain **FREEZE-CANDIDATE**, not FROZEN.

Subsequent milestones (M2 structs + arithmetic + literal typing; M3 slices +
`Result` + `?` + prelude → `file_read.crust`/`crust_inspect.crust`) proceed as
the specs move FREEZE-CANDIDATE → FROZEN. Do **not** implement `Result`-returning
`main`, buffer reclamation, references, moves, or `unsafe` in the prototype —
they are out of v0.1 or deferred.

## H. Do NOT do (still hard limits)

No LLVM/WASM/native backend; no generics/traits/closures/`match`/`for`/indexing;
no owned `String`; no package manager; no module system; no compiler code beyond
the authorized milestone subset.
