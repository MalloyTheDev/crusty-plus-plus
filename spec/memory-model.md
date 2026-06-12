# CRusty++ Memory Model — Ownership, Moves, and Borrows

> Status: **DRAFT**, tracking `v0.1`. Frozen alongside
> [`v0.1.md`](./v0.1.md).

CRusty++ has no garbage collector and no manual `free`. Memory safety in the safe
subset comes from a single ownership discipline, checked at compile time. This
document specifies that discipline for `v0.1`.

The whole model fits in one paragraph:

> Every value has exactly one owner. Binding or passing a non-`Copy` value
> **moves** it, after which the source is invalid. You may temporarily **borrow**
> a value (`&T` to read, `&mut T` to mutate); a borrow may not outlive its owner,
> and a `&mut` borrow is exclusive. Values are **dropped** deterministically when
> their owning scope ends.

The rest is detail.

---

## 0. Honesty about scope (what this model is and is not)

So the model is neither oversold nor misimplemented, v0.1 commits to the
following plainly:

- **CRusty++ v0.1 is safer than C, but not Rust-level memory-safe.** It removes
  the most common C footguns (use-after-free of moved values, double-free) but
  does not prove the absence of every aliasing or lifetime bug.
- **There is no full borrow checker in v0.1.** Borrows are checked **lexically**:
  a borrow is live from its creation to the end of the enclosing block (§4).
  There is no flow-sensitive non-lexical lifetime analysis and no named
  lifetimes (`'a`) — those are [non-goals](../NON_GOALS.md) for now.
- **References (`&T`, `&mut T`) are non-null.** There is no null reference. A
  reference always points at a live value of the right type.
- **v0.1 has no raw pointers and no `unsafe`.** When raw pointers are added in a
  later version, **dereferencing a raw pointer will be `unsafe`** and outside the
  safe subset. v0.1 simply does not have them.
- **Slices are pointer + length.** The only slice type in v0.1 is `str` (an
  immutable `{ ptr, len }` view; §2). General arrays and user slices are
  deferred.
- **Arena/allocator work is planned but not required** for the first compiler
  prototype. v0.1 relies on scope-bound drops; a custom allocator/arena is a
  later concern and is not a precondition for the prototype.

---

## 1. Ownership

- Every value is owned by exactly one binding (a `let`/`let mut` variable, a
  function parameter, or a struct field) at any moment.
- When the owning binding goes out of scope, the value is **dropped**: its storage
  is released. Drops are deterministic and occur at the closing `}` of the scope,
  in reverse order of declaration.
- There is no shared ownership in v0.1 (no reference counting, no `Rc`-like type).

## 2. `Copy` vs. move types

Types divide into two categories:

- **`Copy` types** — duplicated bitwise on assignment/passing; the source remains
  valid. In v0.1 the `Copy` types are exactly: all integer types (`i8`…`u64`),
  `f64`, and `bool`.
- **Move types** — everything else: `String`, `struct` values, and the built-in
  `Option`/`Result` shapes. Assigning or passing them **moves** ownership.

`str` is a borrowed view and is neither owned nor moved in the usual sense; it is
treated as an immutable borrow (see §4).

## 3. Moves

```crust
let a: String = String::from("hi");
let b: String = a;     // ownership moves from `a` to `b`
// reading `a` here is a COMPILE-TIME ERROR: `a` has been moved
```

- A move transfers ownership and **invalidates the source binding**. Any later use
  of a moved-from binding is rejected at compile time (`v0.1.md` §6).
- Passing a move-type value to a function moves it into the callee unless the
  parameter is a borrow:

```crust
fn consume(s: String) -> i32 { return 0; }   // takes ownership
fn inspect(s: &str) -> i32   { return 0; }   // borrows, does not take ownership
```

- Returning a value from a function moves it out to the caller.
- A moved-from binding may be reassigned (with `let mut`) and becomes valid again
  for its new value.

## 4. Borrows

A borrow is a temporary, non-owning reference to a value.

```crust
let s: String = String::from("data");
let r: &str = &s;          // shared (immutable) borrow
```

Two forms:

- **Shared borrow** `&T` — read-only. Any number may coexist.
- **Exclusive borrow** `&mut T` — read/write. At most one may exist, and it
  excludes all other borrows (shared or exclusive) of the same value while live.

### Borrow rules (v0.1)

1. A borrow may not outlive the value it refers to (no dangling references).
2. While a `&mut T` borrow is live, no other borrow of that value may exist.
3. While any `&T` borrow is live, no `&mut T` borrow of that value may exist.
4. You may not move a value while it is borrowed.

These rules are enforced lexically in v0.1: a borrow is considered live from its
creation to the end of the enclosing block. There are **no named lifetimes**
(`'a`) in v0.1; borrow scope is purely structural. Named lifetimes are a
[non-goal](../NON_GOALS.md) for now.

## 5. Drops and scope

```crust
fn demo() -> i32 {
    let outer: String = String::from("o");
    {
        let inner: String = String::from("i");
        // `inner` dropped here, at the inner block's closing brace
    }
    // `outer` dropped here, at the function block's closing brace
    return 0;
}
```

- Drop order within a scope is the reverse of declaration order.
- Moving a value *out* of a scope (e.g. by returning it) means it is **not**
  dropped at that scope's end — ownership left with it.
- `Copy` values have trivial drops (no action).

## 6. No undefined behavior

The model is designed so that, in the safe subset:

- There is no use-after-free: a borrow cannot outlive its owner (§4 rule 1), and a
  moved-from binding cannot be read (§3).
- There is no double-free: a value has one owner and is dropped exactly once.
- There are no data races within a single thread (v0.1 is single-threaded; see
  [`../NON_GOALS.md`](../NON_GOALS.md)).

## 7. Worked example

```crust
struct Buffer {
    data: String,
}

fn len_of(b: &Buffer) -> i32 {
    // borrows `b`; does not take ownership, so the caller keeps it
    return 0;          // (string length API specified in syntax.md prelude)
}

fn main() -> i32 {
    let buf: Buffer = Buffer { data: String::from("hello") };
    let n: i32 = len_of(&buf);   // shared borrow; `buf` still owned here
    let moved: Buffer = buf;     // ownership moves to `moved`
    // using `buf` here would be a compile-time error
    return n;
    // `moved` is dropped at end of scope; `buf` is not (it was moved out)
}
```

## 8. Open questions (must be closed before freeze)

- Exact spelling of `String` construction (`String::from` vs. a prelude function).
  Tracked against [`syntax.md`](./syntax.md) §6.7.
- Whether struct field moves invalidate the whole struct or only the field in
  v0.1 (current intent: moving a field invalidates only that field, and the
  struct may not then be moved as a whole until the field is reinitialized).
