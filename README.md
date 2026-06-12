# CRusty++

**CRusty++** is a small, statically-typed systems programming language. It is a
design-first project: the language is being specified on paper before a single
line of the compiler is written.

The goal is a language with the *honesty* of C, the *memory discipline* of Rust,
and a deliberately *tiny* surface area — small enough that one person can hold
the entire language in their head.

> Status: **pre-implementation.** There is no compiler yet. This repository
> currently contains only the language design, specification, and example
> programs that the future compiler is expected to accept.

---

## What CRusty++ is

- A **systems language**: ahead-of-time compiled, no garbage collector, no
  runtime to speak of. You can reason about what the machine does.
- **Memory-safe by construction** for the safe subset: ownership and move
  semantics prevent use-after-free and double-free without a tracing GC.
- **Small and frozen in scope**: each version (`v0.1`, `v0.2`, …) defines a
  closed feature set. Nothing ships outside a frozen spec.
- **Readable**: the grammar fits on a few pages. There is one obvious way to do
  most things.

## What CRusty++ is not (yet)

See [`NON_GOALS.md`](./NON_GOALS.md) for the full list. In short: no generics,
no traits, no async, no macros, no package manager, and no self-hosting compiler
in `v0.1`. These are not rejected forever — they are simply out of the first
frozen scope.

## Repository layout

| Path | Purpose |
|------|---------|
| [`README.md`](./README.md) | This file — what CRusty++ is |
| [`DESIGN.md`](./DESIGN.md) | The "why": design philosophy and rationale |
| [`ROADMAP.md`](./ROADMAP.md) | Version-by-version plan |
| [`NON_GOALS.md`](./NON_GOALS.md) | What is deliberately excluded, and why |
| [`spec/v0.1.md`](./spec/v0.1.md) | The frozen `v0.1` language scope |
| [`spec/syntax.md`](./spec/syntax.md) | Lexical and grammatical reference |
| [`spec/memory-model.md`](./spec/memory-model.md) | Ownership, moves, lifetimes |
| [`spec/error-handling.md`](./spec/error-handling.md) | Results, panics, exit codes |
| [`examples/`](./examples/) | Target programs the compiler must accept |
| [`compiler/`](./compiler/) | (Empty) home of the future compiler |
| [`tests/`](./tests/) | (Empty) home of the conformance test suite |

## A taste

```crust
// examples/hello.crust
fn main() -> i32 {
    println("Hello, CRusty++!");
    return 0;
}
```

Source files use the `.crust` extension. See [`examples/`](./examples/) for more.

## Design principles

1. **Specify before implementing.** A feature does not exist until it is written
   down in a frozen spec.
2. **Small over clever.** When in doubt, leave it out.
3. **No hidden cost.** Allocation, copying, and control flow are visible in the
   source.
4. **One language, one mental model.** Memory safety comes from a single,
   teachable ownership model — not a pile of special cases.

## Contributing

This is the design phase. The most valuable contributions right now are
critiques of the spec and example programs that expose ambiguity. Please do not
send compiler code yet — there is nothing to attach it to.

## License

To be decided before the first code lands. See [`ROADMAP.md`](./ROADMAP.md).
