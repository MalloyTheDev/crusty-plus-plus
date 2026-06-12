# CRusty++ Error Handling — Results, Options, and Panics

> Status: **FREEZE-CANDIDATE**, tracking `v0.1`. Frozen alongside
> [`v0.1.md`](./v0.1.md).

CRusty++ has **no exceptions and no stack unwinding**. Errors are ordinary
values. This document specifies how recoverable and unrecoverable failures work
in `v0.1`.

The split:

- **Recoverable** failures (a file is missing) are returned as a `Result` value
  the caller inspects.
- **Unrecoverable** failures (a broken invariant, arithmetic overflow) call
  `panic`, which prints a message and **aborts** the process.

---

## 1. `Option<T>` — presence or absence

A built-in tagged type:

```
Option<T> = Some(T) | None
```

`Option` is recognized in v0.1 (`syntax.md` §6.4) and constructed with `Some(v)`
/ `None`. It is used where absence is normal and not an error. No v0.1 example
needs `Option`, so the prelude ships **no** `Option` helpers yet; they are added
when an example requires them.

## 2. `Result<T, E>` — success or failure

A built-in tagged type:

```
Result<T, E> = Ok(T) | Err(E)
```

A function that can fail returns `Result<T, E>`:

```crust
fn read_size(path: str) -> Result<i32, FileError> {
    let bytes: []u8 = read_all_bytes(path)?;   // `?` returns Err on failure
    return Ok(bytes.len as i32);
}
```

The built-in `read_all_bytes(path: str) -> Result<[]u8, FileError>` is the v0.1
source of recoverable errors. `FileError` is a built-in opaque error type with a
read-only `.code: i32`. Richer error types and user error enums are deferred.

### Inspecting a `Result` without `match`

v0.1 has no `match`. A `Result` is inspected with the prelude predicates and
extractor, typically after an `if` guard:

```crust
let r: Result<i32, FileError> = read_size("input.txt");
if is_err(r) {
    println("error: could not read input.txt");
    return 1;
}
let n: i32 = unwrap(r);     // safe here: the Err case already returned
```

- `is_ok(r) -> bool`, `is_err(r) -> bool` — test the variant.
- `unwrap(r) -> T` — return the `Ok` payload; **panics** (aborts) if `r` is
  `Err`. Intended for use after an `is_ok`/`is_err` guard.

Because all v0.1 types copy (`memory-model.md` §1), passing a `Result` to
`is_err` and then `unwrap` copies it — there is no move to track.

## 3. The `?` propagation operator

`?` applied to a `Result` either unwraps `Ok` or returns the `Err` from the
current function:

```crust
fn total() -> Result<i32, FileError> {
    let a: []u8 = read_all_bytes("a.bin")?;   // if Err, `total` returns that Err
    let b: []u8 = read_all_bytes("b.bin")?;
    return Ok(a.len as i32 + b.len as i32);
}
```

Frozen rules:

- `?` is valid **only** inside a function whose return type is `Result<T, E>`.
- `expr?` requires `expr` to be `Result<T, E>` whose `E` matches the enclosing
  function's error type. On `Ok(v)` it evaluates to `v`; on `Err(e)` it executes
  `return Err(e)` immediately.
- v0.1 does **not** define `?` on `Option`.
- `?` is **not** usable in `main` when `main` returns `i32` (its return type is
  not `Result`). v0.1 examples use `fn main() -> i32` and therefore do not use
  `?` in `main`.

## 4. `panic` — unrecoverable failure

```crust
fn must_be_positive(n: i32) -> i32 {
    if n <= 0 {
        panic("expected a positive number");
    }
    return n;
}
```

- `panic(msg: str)` writes `msg` to standard error and **aborts** the process.
- A panic does **not** unwind, does **not** run drops, and **cannot be caught**.
- The process exit code on panic is fixed (§6).

## 5. Defined runtime panics

Per [`v0.1.md`](./v0.1.md) §8, the following are defined to `panic` rather than be
undefined behavior:

- Integer overflow in `+ - *` (checked arithmetic).
- Division or modulo by zero.
- Signed negation overflow (`-MIN`) and division overflow (`MIN / -1`).
- `unwrap` on an `Err` value (§2).

## 6. Exit codes

- `main` returns `i32` or `Result<i32, E>`.
  - `fn main() -> i32`: the returned value **is** the exit code (`0` = success).
    This is the form used by all v0.1 examples, keeping exit behavior explicit.
  - `fn main() -> Result<i32, E>`: defined for completeness, but how an `Err`
    maps to an exit code is **not yet specified**; until it is, do not write a
    `Result`-returning `main`. (Tracked in
    [`freeze-checklist.md`](./freeze-checklist.md).)
- A `panic` aborts with the fixed exit code **101** (distinct from common
  `1`/`2` application codes).

## 7. Ignored results and rejected mechanisms

- **Ignoring a `Result` is allowed** in v0.1 (e.g. calling a fallible function as
  a statement). A "must-use" warning is a possible *later* addition — never an
  error in v0.1.
- **Exceptions are explicitly rejected.** There is no `throw`, no `try`/`catch`,
  no unwinding. Recoverable failure is `Result`; unrecoverable failure is an
  aborting `panic`.

## 8. Style guidance

- Return `Result` for anything a caller could reasonably handle.
- Reserve `panic` for "this should be impossible" — broken invariants, not bad
  input. Treat `unwrap` as a guarded `panic`: only after you have proven `Ok`.
