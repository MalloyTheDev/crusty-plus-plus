# CRusty++ Memory Model — Copy Semantics Now, Ownership Later

> Status: **FREEZE-CANDIDATE**, tracking `v0.1`. Frozen alongside
> [`v0.1.md`](./v0.1.md).

CRusty++ has no garbage collector and no manual `free`. This document specifies
what the `v0.1` memory model actually *is* for the first compiler prototype, and
records the ownership/move design that activates later — kept clearly separate so
neither is oversold.

---

## 0. Honesty about scope (read this first)

- **CRusty++ v0.1 is safer than C, but not Rust-level memory-safe.** It removes
  the rawest C footguns (no raw pointers, no null references, no manual free) but
  does not prove the absence of every aliasing or lifetime bug.
- **v0.1 uses copy semantics.** Every v0.1 type is copied by value (§1). There
  are no resource-owning types yet, so there are **no destructors** and **no
  move/use-after-move checking** in the first prototype.
- **References (`&T`, `&mut T`) are non-null.** There is no null reference.
- **v0.1 has no raw pointers and no `unsafe` implementation.** The `unsafe`
  keyword is *reserved* (`syntax.md` §3) but unimplemented; raw pointers are a
  later feature and their dereference will be `unsafe` when added.
- **Slices are pointer + length.** The only slices in v0.1 are `str` and `[]u8`
  (§1). They are non-owning, non-null, immutable views.
- **Arena/allocator work is planned but not required** for the first prototype.

The detailed ownership/move/borrow rules in §3–§5 are **design intent** for when
resource-owning types are introduced. They are **not** active v0.1 behavior.

---

## 1. v0.1 reality: copy by value

Every value in v0.1 is duplicated on binding, assignment, and function call:

- **Scalars** (`i8`…`u64`, `usize`, `f64`, `bool`) copy bitwise.
- **Slices** (`str`, `[]u8`) copy their `{ pointer, length }` view. The viewed
  bytes are **not** duplicated and **not** owned by the slice.
- **Structs** copy field-by-field.
- `Option<T>` / `Result<T, E>` copy when their payloads copy — true for all v0.1
  payload types.

```crust
struct Point { x: i32, y: i32 }

fn main() -> i32 {
    let a: Point = Point { x: 1, y: 2 };
    let b: Point = a;     // COPY: `a` is still valid afterwards
    let c: i32 = a.x + b.x;
    return c;
}
```

Because everything copies and nothing owns a resource, the first prototype needs
**no ownership analysis** to be sound about double-free or use-after-free: there
is nothing to free.

## 2. References (recognized, not required)

`&T` and `&mut T` are recognized by the grammar (`syntax.md` §6.4) and are
non-null. However:

- v0.1 **examples do not use references** — values are small and copy cheaply.
- `&mut` is **reserved** and not required by the first prototype.
- Borrow checking (§4) is design intent, not active v0.1 behavior.

Keeping references in the grammar avoids a breaking change when borrowing becomes
load-bearing; until then, prefer passing by value.

## 3. Future: ownership and moves (design intent)

When resource-owning types (e.g. an owned string, heap buffers, file handles) are
introduced in a later version, the model becomes:

> Every value has exactly one owner. Binding or passing a non-`Copy` value
> **moves** it, after which the source is invalid. You may temporarily **borrow**
> a value (`&T` to read, `&mut T` to mutate); a borrow may not outlive its owner,
> and a `&mut` borrow is exclusive. Resource-owning values are **dropped**
> deterministically when their owning scope ends.

- A move transfers ownership and invalidates the source binding; reading a
  moved-from binding becomes a compile-time error.
- `Copy` types (today: all v0.1 types) are exempt — they copy instead of move.
- Field-move granularity (intended rule): moving a field invalidates only that
  field; the struct may not be moved as a whole until the field is reinitialized.

None of this is enforced in v0.1 because v0.1 has no non-`Copy` types.

## 4. Future: borrow rules (design intent)

When borrowing becomes load-bearing, the intended rules are:

1. A borrow may not outlive the value it refers to (no dangling references).
2. While a `&mut T` borrow is live, no other borrow of that value may exist.
3. While any `&T` borrow is live, no `&mut T` borrow of that value may exist.
4. You may not move a value while it is borrowed.

These will be enforced **lexically** at first (a borrow is live from creation to
the end of the enclosing block). There are **no named lifetimes** (`'a`); that is
a non-goal. v0.1 does **not** implement a borrow checker.

## 5. Future: drops (design intent)

When resource-owning types exist:

- A resource-owning value is dropped at the end of its owning scope, in reverse
  declaration order.
- Moving a value out of a scope means it is not dropped there.
- `panic` does **not** run drops (it aborts; see
  [`error-handling.md`](./error-handling.md) §4).

In v0.1 there are no resource-owning types, so no drops occur.

## 6. `unsafe` and raw pointers

- `unsafe` is a reserved keyword with no v0.1 semantics.
- v0.1 has no raw pointer type and no way to take or dereference a raw pointer.
- When raw pointers are added, obtaining one will be safe but **dereferencing one
  will require `unsafe`**, keeping the safe subset free of pointer dereference.

This section exists so the boundary is documented now; no v0.1 example uses any
of it.
