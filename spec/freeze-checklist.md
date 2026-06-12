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

> **Tracked impl gap (not a spec defect): checked arithmetic.** M2A lowers
> arithmetic to plain C operators. `v0.1.md` §8 / `error-handling.md` §5 require
> overflow, div-by-zero, and negation/division overflow to `panic`. That lowering
> (an abort shim + overflow checks) is **deferred** to the milestone that adds the
> remaining integer types and casts (M2B). The M2A example does not overflow, so
> its observable behavior is conformant. This gap must close before v0.1 is
> declared fully implemented.

Subsequent milestones (M2 structs + arithmetic + literal typing; M3 slices +
`Result` + `?` + prelude → `file_read.crust`/`crust_inspect.crust`) proceed as
the specs move FREEZE-CANDIDATE → FROZEN. Do **not** implement `Result`-returning
`main`, buffer reclamation, references, moves, or `unsafe` in the prototype —
they are out of v0.1 or deferred.

## H. Do NOT do (still hard limits)

No LLVM/WASM/native backend; no generics/traits/closures/`match`/`for`/indexing;
no owned `String`; no package manager; no module system; no compiler code beyond
the authorized milestone subset.
