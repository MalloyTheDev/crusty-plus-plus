# Design Philosophy

This document explains *why* CRusty++ is shaped the way it is. The normative
rules live in [`spec/`](./spec/); this file is the reasoning behind them.

## The one-sentence pitch

> A systems language small enough to specify completely, safe enough to trust
> with memory, and honest enough to predict at the machine level.

## Influences, and what we take from each

- **C** — the model of "what you write is roughly what runs." We keep explicit
  control flow, explicit allocation, and a flat memory model. We drop undefined
  behavior as a design tool: CRusty++ has no `gets()`-style traps.
- **Rust** — ownership and move semantics as the route to memory safety without
  a garbage collector. We take the *idea* (single owner, moves invalidate the
  source, scoped borrows) but not the full borrow-checker surface area (no named
  lifetimes, no traits) in v0.1.
- **Go** — the discipline of a *small* language and fast, whole-program
  compilation. We admire the "you can learn it in an afternoon" property.
- **Zig** — errors as values and a suspicion of hidden control flow. We borrow
  the attitude, not the syntax.

## Core principles

### 1. Specify before implementing
A feature does not exist until it is written into a frozen spec. This repository
is intentionally docs-first. The compiler is downstream of the specification, not
the other way around. This prevents the language from becoming "whatever the
compiler happens to do."

### 2. Small over clever
Every feature must justify its weight against the cost of a larger language. The
default answer to "should we add X?" is no. See [`NON_GOALS.md`](./NON_GOALS.md)
for the long list of things we have said no to on purpose.

### 3. No hidden cost
Allocation, copying, and branching are visible in the source. There are no
implicit heap allocations, no hidden destructors running at surprising times
(destruction is scope-bound and predictable), and no implicit numeric coercion
that silently changes representation.

### 4. One mental model for memory
Safety comes from a single, teachable rule set: every value has one owner; moving
transfers ownership and invalidates the source; borrows are scoped and may not
outlive their owner. If you understand that paragraph, you understand CRusty++
memory. See [`spec/memory-model.md`](./spec/memory-model.md).

### 5. Errors are values
No exceptions, no unwinding. Recoverable failures are returned as values;
unrecoverable failures `panic` and abort the process. Control flow stays visible.
See [`spec/error-handling.md`](./spec/error-handling.md).

### 6. Freeze and version
Scope is frozen per version. `v0.1` is closed; new ideas target `v0.2` and
beyond. This keeps each milestone finishable and the language legible over time.
See [`ROADMAP.md`](./ROADMAP.md).

## Deliberate tensions

Good design is choosing which discomfort to keep. CRusty++ chooses:

- **Verbosity over magic.** Explicit moves and explicit error propagation are
  more typing but less surprise.
- **Fewer features over expressive power.** We would rather you write a loop than
  reach for an abstraction the language can't yet specify cleanly.
- **A slow, deliberate roadmap over early adoption.** It is better to be small and
  correct than large and ambiguous.

## What "done" looks like for the design phase

The design phase ends when:

1. `spec/v0.1.md` is frozen and internally consistent.
2. Every program in [`examples/`](./examples/) is fully explained by the spec —
   no construct appears that the spec does not define.
3. The memory model and error-handling documents have no open questions marked.

Only then does work begin in [`compiler/`](./compiler/).
