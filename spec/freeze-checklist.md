# CRusty++ v0.1 Freeze Checklist

> Purpose: a single gate between the design phase and any compiler work. Nothing
> in [`../compiler/`](../compiler/) starts until every **blocker** below is
> resolved and the four spec documents are marked **frozen**.
>
> This file is the output of the first strict spec audit (2026-06-12). It records
> what is settled, what is open, and the recommended resolution for each open
> item. It does **not** expand v0.1 scope; see [`../NON_GOALS.md`](../NON_GOALS.md).

Legend: 🔴 **blocker** (must resolve before compiler) · 🟡 **should resolve** ·
🟢 **settled intent** (consistent across docs; freeze as-is).

---

## A. Decisions already consistent (freeze as-is) 🟢

These are stated the same way everywhere and only need to be marked frozen:

- Program entry point is `fn main() -> i32`; the return value is the process exit
  code; `0` is success. (`spec/v0.1.md` §1, `error-handling.md` §6)
- No exceptions, no stack unwinding. Errors are values. (`error-handling.md`)
- `panic(msg: str)` is **abort-only**: prints to stderr, does not unwind, does not
  run drops, exits with code **101**. (`error-handling.md` §4, §6)
- Mutability is immutable-by-default; `let mut` opts in. (`v0.1.md` §2.3)
- No implicit numeric conversion; conversions are explicit via `as`. (`v0.1.md`
  §2.1, §2.6)
- Whole-program compile; one global namespace; no modules/imports in v0.1.
  (`v0.1.md` §5)
- Deterministic, scope-bound drops in reverse declaration order. (`memory-model.md`
  §1, §5)
- Single owner per value; no shared ownership / refcounting in v0.1.
  (`memory-model.md` §1)
- Control flow is `if`/`else`, `while`, `loop`/`break`/`continue`, `return`. No
  `for`, no `match`. (`v0.1.md` §2.7)
- Checked arithmetic: overflow on `+ - *`, and divide/modulo by zero, are defined
  panics — no undefined behavior. (`v0.1.md` §6, `error-handling.md` §5)

## B. Blockers — must be resolved before any compiler work 🔴

### B1. `str` vs `&str` — one model, used everywhere 🔴
**Problem.** `str` is used by-value in the prelude (`println(s: str)`,
`print(s: str)`) and as the `Result` error type (`error-handling.md` §2,
`Result<String, str>`), but the examples and `memory-model.md` §4 pass `&str` and
say `str` is "treated as an immutable borrow." A `&String → &str` coercion is
implied (`memory-model.md` line ~59) but never defined.
- Files: `v0.1.md` §2.1/§2.8, `syntax.md` §6.4, `memory-model.md` §2/§4,
  `error-handling.md` §2, `examples/file_read.crust`.
- **Recommended decision:** `str` is a built-in **immutable slice (pointer +
  length)** value type — already a borrowed view, so it is passed **by value as
  `str`** and is a `Copy`-like view that owns nothing. Then:
  - Drop `&str` everywhere; write `str`.
  - Define exactly one coercion: a `String` may be used where `str` is expected
    by an explicit prelude call (e.g. `as_str(&s)`), **not** an implicit
    `&String → &str` coercion.
  - `str` cannot be mutated and is never dropped (it owns nothing).

### B2. Built-in `Option`/`Result` type syntax vs "no generics" 🔴
**Problem.** Examples and specs write `Result<T, E>` / `Option<T>` with angle
brackets, but `syntax.md` §6.4 has no production for type application and §7 plus
`NON_GOALS.md` forbid `<T>` syntax. As written, `Result<i32, str>` does not parse.
- Files: `syntax.md` §6.4/§7, `v0.1.md` §2.1, `error-handling.md` §1–§3,
  `examples/file_read.crust`.
- **Recommended decision:** Add **one** grammar production for the two built-in
  type constructors only — `builtin_generic = ("Option" | "Result") "<" type ("," type)* ">"` —
  and state explicitly in `syntax.md` §7 and `NON_GOALS.md` that this is
  *fixed built-in sugar*, **not** user-definable generics. User `<T>` stays a
  non-goal.

### B3. `String` construction has no grammar 🔴
**Problem.** `memory-model.md` uses `String::from("hi")`, but `::` is not an
operator anywhere in `syntax.md` (§5) and `call` is only `ident "(" args ")"`.
`String::from(...)` cannot parse. (Already flagged in `memory-model.md` §8.)
- Files: `memory-model.md` (6 sites), `syntax.md` §5.
- **Recommended decision:** Provide a prelude **free function**
  `string_from(s: str) -> String` and replace all `String::from` with it. Do
  **not** add `::` path syntax in v0.1 (avoids namespacing surface area).

### B4. Prelude surface is undefined but used by examples 🔴
**Problem.** `examples/file_read.crust` calls `read_to_string`, `string_len`,
`is_err`, `unwrap`; none are defined in any spec. `Option`/`Result` inspection
without `match` (`is_some`, `unwrap_or`, …) is referenced but never enumerated.
- Files: `v0.1.md` §2.8, `syntax.md` prelude, `error-handling.md` §1,
  `examples/file_read.crust`.
- **Recommended decision:** Freeze a **minimal prelude table** before compiler
  work. Proposed v0.1 set (names only — confirm and freeze):
  - I/O: `print(s: str)`, `println(s: str)`.
  - String: `string_from(s: str) -> String`, `str_len(s: str) -> u64`,
    `as_str(s: &String) -> str`.
  - Result: `is_ok`, `is_err`, `unwrap` (panics on the wrong variant),
    `unwrap_or`.
  - Option: `is_some`, `is_none`, `unwrap`, `unwrap_or`.
  - Errors: `panic(msg: str)`.
  - File I/O (`read_to_string`) is **deferred** unless an FFI/IO story is frozen;
    `file_read.crust` must not depend on it (see §F).

### B5. Integer-literal typing rule 🔴
**Problem.** `v0.1.md` §2.6 says operands "must already be the same type; there is
no implicit promotion," but examples rely on `s.id * 2`, `i + 1`, `count >= 3`
where the literal has no declared type. How an untyped integer literal acquires a
type is undefined.
- Files: `v0.1.md` §2.2/§2.6, `syntax.md` §4, every example.
- **Recommended decision:** An integer literal takes the type required by its
  context (the other operand or the binding annotation). If context is absent,
  it defaults to `i32`. Float literals default to `f64`. State this as the only
  inference allowed in v0.1 (binding annotations remain mandatory).

### B6. Backend strategy is unstated 🔴
**Problem.** `ROADMAP.md` and `compiler/README.md` say "single target triple" and
emit an "executable," but the project's intended backend (and this audit's test
plan) assume **C codegen**. No document states what the compiler emits.
- Files: `ROADMAP.md` (open questions), `compiler/README.md`.
- **Recommended decision:** v0.1 compiler **emits portable C** (C99/C11), then
  invokes a system C compiler. This avoids LLVM/WASM (both non-goals) and keeps
  the first prototype small. Define the generated-C shape and ABI stance (see
  C1, C2) before codegen work.

## C. Should-resolve semantic gaps 🟡

- **C1. Generated-C style.** Naming, struct layout mapping, how `panic`/checked
  arithmetic lower to C. *Recommend:* one CRusty++ function → one C function;
  structs → plain C structs; checked ops → inline helper that calls an abort
  shim; `str` → `{ const char* ptr; uint64_t len; }`.
- **C2. ABI / layout guarantees.** *Recommend:* explicitly **no** stability
  guarantee across versions in v0.1 (already the stance in `NON_GOALS.md`); state
  it for codegen too.
- **C3. Ignored `Result`/`Option` values.** Allowed? *Recommend:* allowed in
  v0.1 (no must-use enforcement); revisit later. State it in `error-handling.md`.
- **C4. `?` in `main`.** `main` returns `i32`, and `?` requires a `Result`
  return, so `?` is **not** allowed in `main`. *Recommend:* state this explicitly
  in `error-handling.md` §3.
- **C5. Struct copy vs move.** `v0.1.md`/`memory-model.md` say structs **move**.
  Confirm there is **no** opt-in `Copy` for structs in v0.1. *Recommend:* confirm
  — all structs are move types in v0.1, even all-scalar ones.
- **C6. Assignment to immutable / moved-from binding.** *Recommend:* assigning to
  a non-`mut` binding is a compile error; a `mut` binding may be reassigned after
  a move to revive it (already implied in `memory-model.md` §3 — make explicit).
- **C7. Evaluation order.** Operand and argument evaluation order is unspecified.
  *Recommend:* define strict **left-to-right** evaluation.
- **C8. Division/negation overflow.** `INT_MIN / -1` and `-INT_MIN`. *Recommend:*
  both are defined panics (extend `v0.1.md` §6 to name `/` and unary `-`).
- **C9. Unused variables/parameters.** *Recommend:* allowed (no diagnostic) in
  v0.1; revisit with linting later.
- **C10. `str_len` return type.** Pick `u64`. State that v0.1 has no `usize`.
- **C11. Field-move granularity.** Already an open question in `memory-model.md`
  §8. *Recommend:* moving a field invalidates only that field; the struct may not
  be moved as a whole until the field is reinitialized.
- **C12. Diagnostics expectations.** What a rejection must report. *Recommend:*
  every rejection carries a stable message + source span; the conformance suite
  matches on a diagnostic code, not exact prose.

## D. Memory-model honesty (now stated in `memory-model.md` §0) 🟢

The audit added an explicit honesty section so the model is not oversold:

- CRusty++ v0.1 is **safer than C but not Rust-level** memory-safe.
- There is **no full borrow checker** in v0.1; borrows are checked lexically.
- References (`&T`, `&mut T`) are **non-null**.
- v0.1 has **no raw pointers and no `unsafe`**; when raw pointers are added later,
  dereferencing them will be `unsafe`.
- Slices are **pointer + length**; the only slice type in v0.1 is `str`.
- Arena/allocator work is **planned but not required** for the first prototype.

## E. Examples that define v0.1 success

These are the acceptance set. They must compile and run once the prototype lands:

- `examples/hello.crust` — **clean.** Uses only frozen constructs (`main`,
  `println`, `return`). No open dependencies.
- `examples/crust_inspect.crust` — **clean except B5.** Structs, borrows, moves,
  `while`/`loop`/`break`, checked arithmetic, `panic`. Depends only on the
  integer-literal rule (B5).
- `examples/file_read.crust` — **blocked.** Depends on B1, B2, B4 (undefined
  prelude + file I/O). Header now lists these dependencies; it cannot be a
  success criterion until they freeze, or it must be reduced to defined calls.

## F. Do NOT start the compiler until these are resolved

Hard gate. The prototype may not begin until **all** of:

1. **B1–B6 resolved** and reflected in the four spec docs.
2. The four specs (`v0.1.md`, `syntax.md`, `memory-model.md`,
   `error-handling.md`) marked **FROZEN** (no remaining "open questions").
3. The **prelude table (B4)** is enumerated and frozen.
4. The **generated-C shape (B6/C1)** is roughly defined.
5. **Diagnostics expectations (C12)** are defined.
6. Every example in §E is fully explained by the frozen specs — `file_read.crust`
   either reduced to defined calls or removed from the acceptance set.

Until then, the only valid changes are to the specification, the examples, and
this checklist — never to `compiler/`.
