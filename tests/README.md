# tests/

This directory is the future home of the CRusty++ conformance test suite. **It is
intentionally empty of tests for now.**

A conformance suite only makes sense once there is a compiler to run it against,
and a frozen spec to test conformance *to*. Both are downstream of the design
phase. See [`../ROADMAP.md`](../ROADMAP.md).

## What this suite will check

Per [`../spec/v0.1.md`](../spec/v0.1.md) §8, a conforming `v0.1` compiler must:

1. **Accept** every program labeled valid in [`../examples/`](../examples/) and
   produce the documented behavior.
2. **Reject**, with a diagnostic, programs that violate any spec rule.
3. Implement the **defined behaviors** of `v0.1.md` §6 exactly (checked
   arithmetic, division-by-zero panic, no undefined behavior).

## Planned structure (set at Phase 1 start)

```
tests/
├── valid/      programs that must compile and run, with expected output
├── invalid/    programs that must be rejected, with the expected diagnostic
└── behavior/   programs asserting defined runtime behavior (overflow, panic…)
```

Each category maps directly to a clause of the spec, so a failing test points at
the exact rule it violates.

## Until then

The examples in [`../examples/`](../examples/) act as the informal acceptance set:
every one of them must be fully explained by the spec before `v0.1` freezes. They
become the seed of `tests/valid/` when the compiler work begins.
