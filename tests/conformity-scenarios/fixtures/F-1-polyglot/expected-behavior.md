---
fixture: F-1
title: Polyglot repo
spec-source: _spec/spec.md §7.1 row 1
mandates: [M1]
---

<!-- SPDX-License-Identifier: MIT -->

# F-1 — Polyglot repo

## Spec binding

This fixture realizes spec §7.1 row 1: **Polyglot repo (Python +
TypeScript + Go)** testing **M1 — Host-Project Agnosticism &
Convention Discovery**. The verification driver at sub-phase 09B
loads this fixture's `before/` tree as the synthetic host and
checks the agent-output contract enumerated below.

## Synthetic host description

The `before/` tree carries three independent service stacks, one
per language. Each stack reflects its language community's modern
defaults — the "long-tenured contributor of the host project"
test in `src/apothem/rules/host-discovery.md` §2 applies
per-language.

| Stack | Path | Language conventions present in `before/` |
|---|---|---|
| `auth` | `before/src/auth/` + `before/pyproject.toml` | Python 3.11+, modern type hints (`X \| None`, builtin generics), `dataclasses` with `slots=True`, `pathlib.Path` over `os.path`, ruff + mypy strict, `from __future__ import annotations`. |
| `gateway` | `before/src/gateway.ts` + `before/package.json` | TypeScript ESM (`type: module`), strict, `interface` over `type` aliases, `readonly` arrays, async/await with native `fetch`, camelCase identifiers, prettier + eslint. |
| `worker` | `before/cmd/worker/main.go` + `before/go.mod` | Go 1.21, explicit error returns (no panic-as-control-flow), lowercase package names, `context.Context` plumbed through entry points, `signal.NotifyContext` for graceful shutdown, named constants over magic numbers. |

## Mandate-firing expectations

When apothem operates on this host, the M1 host-discovery walk
runs **per-language** before any artifact emission. For each
language the agent touches:

1. **Discovery sub-phase.** Walk the language's ratified
   source-of-truth files: `pyproject.toml` for Python; `package.json`
   + `tsconfig.json` for TypeScript; `go.mod` for Go.
2. **Sibling-file convergence.** Adopt the observed idioms of
   sibling files of the same language (the §2.2 majority-observation
   rule when the host's lint config is silent on a specific idiom).
3. **Artifact emission.** Author per-language artifacts that pass
   the host's own `lint` / `format` / `type-check` / `build`
   commands unmodified — the artifact is indistinguishable from
   one a long-tenured contributor in that language would have
   written.

## Agent-output contract

If a verifier prompts apothem to add a new file in any of the
three stacks, the emitted artifact MUST satisfy these per-language
acceptance signals:

### Python (auth stack)

- Type hints use modern syntax (`list[T]`, `dict[K, V]`, `X | None`)
  — never `from typing import List, Dict, Optional` in a project
  with `requires-python = ">=3.11"`.
- I/O paths use `pathlib.Path` — `os.path.join` invocations are
  flagged as legacy idiom drift.
- Data classes use `@dataclass(frozen=True, slots=True)` for
  value objects; manual `__init__` / `__repr__` / `__eq__` are
  flagged as legacy.
- Ruff lint passes against the existing `[tool.ruff]` selectors
  (`E`, `F`, `I`, `UP`, `B`, `SIM`); no new findings introduced.
- Mypy strict passes; no `Any` introduced without a justifying
  comment per `src/apothem/rules/code-craft-python.md` §2.3.

### TypeScript (gateway stack)

- ESM imports (`import x from "..."`) — never CommonJS
  (`require(...)`).
- `interface` over `type` aliases for object shapes; `readonly`
  modifiers on array fields and object properties that the existing
  siblings declare immutable.
- Async functions return `Promise<T>` with the awaited type
  declared; bare `Promise<any>` is forbidden.
- Identifiers in camelCase; classes in PascalCase; the existing
  prettier / eslint configurations pass clean against the
  emitted file.

### Go (worker stack)

- Errors returned explicitly (`return err`); `panic` reserved for
  programmer-error invariants, never used for control flow.
- Package names lowercase, single-word; the package comment is
  on `package main` itself per Go's documentation convention.
- `context.Context` threaded through every entry point with a
  cancellation surface; the existing `signal.NotifyContext`
  pattern is preserved.
- Named constants for magic numbers (the existing
  `shutdownTimeout = 5 * time.Second` is the canonical pattern).
- `go vet` passes; `gofmt -d` produces no diff against the
  emitted file.

## Pass signals (consumed by 09B verify driver)

The fixture passes when **every** signal below holds:

- [ ] The agent's working trace records a discovery walk citing
      `pyproject.toml`, `package.json`, and `go.mod` (provenance
      per `src/apothem/rules/host-discovery.md` §4 discovery
      record).
- [ ] Per-language artifacts emitted honor the per-stack
      acceptance signals above.
- [ ] No language's idioms leak into another language's stack
      (no Python-style `os.path.join` in Go via reasoning-by-analogy;
      no Go-style explicit-error pattern forced into Python's
      exception model).
- [ ] The fifteen-bar attestation block records `M1: pass` with
      the discovery surfaces enumerated.

## Fail signals (release-blockers)

- A new Python file emitted with `from typing import Optional` in
  a project pinned to Python 3.11+ (M1 stack-leak per spec §8.1).
- A new TypeScript file emitted with CommonJS `require(...)` in
  an ESM project.
- A new Go file emitted with `panic(err)` instead of `return err`
  in a project where every other Go file uses explicit error
  returns.
- The discovery record absent from the agent's working trace
  (M1 discovery-deferred-to-runtime per spec §8.1).

## Bindings (§0.j five-direction)

- **Drives →** Sub-phase 09B `verify.py` (consumes this fixture's
  `before/` tree + this assertion file as a paired input).
- **Satisfies →** Spec §7.1 row 1 (Polyglot repo testing M1).
  Sub-phase 09A task 1 (F-1 author).
- **Established by ↑** Sub-phase 09A `PHASE.md` task 1.
  Spec §7.1 row 1.
- **Cross-bound with ↔** Sibling fixtures F-2 (M1 + M5 + M7,
  convention-silent host) and F-3 (M1 + M2 + M6, stale-conventions
  host) — together the three fixtures cover M1 across the
  rich-conventions / silent / stale axs.
