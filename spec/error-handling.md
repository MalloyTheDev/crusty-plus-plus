# CRusty++ Error Handling — Results, Panics, and Exit Codes

> Status: **DRAFT**, tracking `v0.1`. Frozen alongside
> [`v0.1.md`](./v0.1.md).

CRusty++ has **no exceptions and no stack unwinding**. Errors are ordinary
values. This document specifies how recoverable and unrecoverable failures work
in `v0.1`.

The split:

- **Recoverable** failures (a file is missing, input is malformed) are returned
  as a `Result`-shaped value the caller must handle.
- **Unrecoverable** failures (a broken invariant, arithmetic overflow) call
  `panic`, which prints a message and aborts the process.

---

## 1. `Option` — presence or absence

A built-in shape representing "a value, or nothing":

```
Option<T> = Some(T) | None
```

- `Some(v)` carries a value of type `T`.
- `None` carries nothing.

`Option` is used where absence is normal and not an error (e.g. "find returned
no match"). v0.1 provides `Some`/`None` constructors in the prelude. Inspecting an
`Option` in v0.1 is done with `if` against the constructors (full destructuring
`match` is a [non-goal](../NON_GOALS.md) for now); the exact prelude predicates
(`is_some`, `unwrap_or`, …) are listed in [`syntax.md`](./syntax.md)'s prelude
section before freeze.

## 2. `Result` — success or failure

A built-in shape representing "a value, or an error":

```
Result<T, E> = Ok(T) | Err(E)
```

- `Ok(v)` is success carrying a `T`.
- `Err(e)` is failure carrying an error value `E`.

A function that can fail returns `Result<T, E>`:

```crust
fn read_count(path: str) -> Result<i32, str> {
    // ... on failure:
    return Err("could not read file");
    // ... on success:
    // return Ok(count);
}
```

In v0.1, `E` is commonly `str` (a static error message). Richer error types are a
later concern.

## 3. The `?` propagation operator

`?` applied to a `Result` either unwraps `Ok` or returns the `Err` from the
current function:

```crust
fn total() -> Result<i32, str> {
    let a: i32 = read_count("a.txt")?;   // if Err, `total` returns that Err
    let b: i32 = read_count("b.txt")?;
    return Ok(a + b);
}
```

Rules:

- `?` is only valid in a function whose return type is `Result<_, E>`.
- `expr?` requires `expr` to be `Result<T, E>` where `E` matches the function's
  error type. On `Ok(v)` it evaluates to `v`; on `Err(e)` it executes
  `return Err(e)` immediately.
- v0.1 does **not** define `?` on `Option`. (Candidate for a later version.)

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
- A panic does **not** unwind the stack and does **not** run drops; it terminates
  immediately. (This is a deliberate simplification for v0.1.)
- The process exit code on panic is a fixed nonzero value (see §6).

## 5. Defined runtime panics

Per [`v0.1.md`](./v0.1.md) §6, the following are defined to `panic` rather than be
undefined behavior:

- Integer overflow in `+ - *` (checked arithmetic).
- Division or modulo by zero.

These produce a panic with a descriptive message and the standard panic exit
code.

## 6. Exit codes

- `main` has signature `fn main() -> i32`; its returned value **is** the process
  exit code. By convention `0` means success.
- A `panic` aborts with a fixed nonzero exit code. v0.1 reserves **`101`** for
  panic (chosen to be distinct from common `1`/`2` application codes).
- Programs are encouraged to return small nonzero codes from `main` for ordinary
  failures and reserve `panic` for genuine invariant violations.

## 7. Style guidance

- Prefer returning `Result` for anything a caller could reasonably handle.
- Reserve `panic` for "this should be impossible" situations — broken invariants,
  not bad input.
- Use `Option` for plain absence; use `Result` when the *reason* for failure
  matters.

## 8. Open questions (must be closed before freeze)

- Whether `?` should also work on `Option` in v0.1 (current intent: no).
- Final prelude surface for inspecting `Option`/`Result` without `match`.
- Whether panic should optionally run drops in a future version (v0.1: no).
