# Non-Goals

This document records what CRusty++ is **deliberately not** — at least not yet.

A non-goal is not a rejection. It is a statement that something is *out of the
current frozen scope* so that the scope stays small enough to actually finish.
When a non-goal is promoted into the language, it moves out of this file and into
a versioned spec under [`spec/`](./spec/).

The rule: **if it is not in a frozen spec, it does not exist.** This file exists
so that "no" has a written home and we stop relitigating the same questions.

---

## Not in scope for v0.1

### Language features

- **Generics / parametric polymorphism.** No `fn id<T>(x: T) -> T`. v0.1 has only
  concrete, monomorphic types. Generics are the single most likely v0.2 addition,
  but they are *hard* to specify well and we will not rush them.
- **Traits / interfaces / typeclasses.** No shared-behavior abstraction. No
  `impl Trait for Type`. Dispatch is static and direct.
- **Inheritance / subtyping.** Structs are flat records. There is no class
  hierarchy and no implicit conversion between struct types.
- **Closures / lambdas / function values.** Functions are top-level only. You
  cannot capture environment or pass functions as values in v0.1.
- **Macros / metaprogramming / `comptime`.** No textual or syntactic macros, no
  compile-time evaluation beyond constant folding.
- **Operator overloading.** Operators have fixed, built-in meanings.
- **Async / await / coroutines / green threads.** Control flow is synchronous.
- **Exceptions / unwinding.** Errors are values (see
  [`spec/error-handling.md`](./spec/error-handling.md)). A panic aborts; it does
  not unwind.
- **Pattern matching with guards / exhaustive `match`.** v0.1 has `if`/`else` and
  simple equality only. A `match` construct is a candidate for later.

### Types

- **No floating point in arithmetic-critical paths beyond `f64`.** v0.1 keeps the
  numeric tower tiny (see [`spec/v0.1.md`](./spec/v0.1.md)).
- **No user-defined enums with payloads (sum types).** Only `struct` records and
  built-in `Result`/`Option`-style types provided by the language.
- **No references with explicit lifetime annotations.** v0.1 borrowing is scoped
  and inferred; named lifetimes (`'a`) are a later concern. See
  [`spec/memory-model.md`](./spec/memory-model.md).

### Tooling and ecosystem

- **No package manager.** No registry, no dependency resolution, no lockfiles.
  A program is the files you hand to the compiler.
- **No build system / incremental compilation.** Whole-program compile only.
- **No standard library beyond a minimal prelude.** I/O, basic collections, and
  string handling come from a small built-in prelude — not a sprawling stdlib.
- **No formatter, linter, or language server.** These come after the language
  stops moving.
- **No self-hosting.** The first compiler will be written in another language.
  CRusty++ compiling CRusty++ is a long-term aspiration, not a v0.1 milestone.

### Platform

- **One target triple at a time.** v0.1 targets a single platform end-to-end
  before any cross-compilation work begins.
- **No ABI stability guarantees.** Nothing about the layout or calling convention
  is promised across versions yet.
- **No FFI / C interop in v0.1.** Calling into C is desirable but unspecified.

---

## How a non-goal graduates

1. Someone writes a concrete proposal: motivation, syntax, semantics, and the
   interactions with the existing memory model.
2. It is reviewed against the design principles in [`DESIGN.md`](./DESIGN.md).
3. If accepted, it is assigned to a target version in [`ROADMAP.md`](./ROADMAP.md)
   and specified in a new or revised `spec/` document.
4. Only then is it removed from this file.

Until all four steps happen, the answer is "not yet" — and that is a feature.
