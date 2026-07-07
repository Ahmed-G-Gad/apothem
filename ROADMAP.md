<!-- SPDX-License-Identifier: MIT -->

# Roadmap

This roadmap describes where Apothem is headed. It is a statement of intent,
not a commitment; priorities shift as the project and its users evolve. For
what has already shipped, see [CHANGELOG.md](CHANGELOG.md).

Status legend: **planned** · **in-progress** · **shipped**.

## Current Release

The current line ships the host-agnostic harness-configuration manager: a
shared profile (`~/.config/apothem/profile.yaml`) materialized into
harness-native config for the registered adapters, driven by the `apothem`
CLI (`quickstart` · `install` · `update` · `uninstall` · `rollback` ·
`verify` · `status` · `diff` · `harnesses` · `profile` · `doctor` ·
`migrate-workspace` · `completion`).

| Item | Status | Notes |
| ---- | ------ | ----- |
| Multi-harness adapter cohort | shipped | Antigravity, Claude Code, CodeBuddy, Codex, Cursor, Gemini CLI, GitHub Copilot, GLM (Z.ai), Hermes, Kimi Code, Kiro, Open-Claw, OpenCode, Qwen Code, Trae, Windsurf, Zed |
| Manifest-driven template propagation | shipped | Single source of propagation truth at `src/apothem/lib/propagation-manifest.yaml` |
| Documentation site | shipped | Public Next.js + Fumadocs site, generated reference indexes, brand assets, `llms.txt`, and release runbooks |
| Release hardening | shipped | Static project version with signed release artifacts, SBOM, and provenance attached to each GitHub Release |
| Deterministic `/plan` + thirteen-stage `/research` pipelines | shipped | Staged spec → generate → review → execute planning, plus the thirteen-stage research pipeline, applied to changes made to the profile itself |
| Eleven-command audit fortress + `/fortress` closed-loop | shipped | On-demand security, code, accessibility, performance, dependency, supply-chain, threat-model, architecture, code-review, docs-review, and UX audits, wrapped by the `/fortress` production-hardening loop |
| Conformity governance gate | shipped | Pre-emission validators — authorship headers, naming, code-craft, hedging, binding reciprocity — over every materialized surface, with a behavior-diff golden corpus regression-locking each adapter's output |
| Durable memory + opt-in continuous learning | shipped | A persistent memory tier and an opt-in learning loop that carry confirmed conventions forward across sessions |

## Planned

| Item | Status | Notes |
| ---- | ------ | ----- |
| Expanded adapter coverage | planned | Additional harnesses as their config conventions stabilize |
| Profile schema enhancements | planned | Richer per-harness override surfaces and stricter validation diagnostics |
| Documentation polish | in-progress | More task-focused guides, diagrams, and examples for real harness setups |
| npm / npx distribution maturation | planned | Keep the `@ahmed-g-gad/apothem` npx entry point aligned with each release and broaden its platform coverage |
| Plugin-marketplace maturation | planned | Grow the Claude Code plugin listing as the marketplace surface stabilizes |

## Long-Term Vision

Apothem aims to be the default way anyone manages AI-harness configuration
across every tool they use: write conventions once, materialize them
everywhere, and keep them in sync as both preferences and harnesses evolve.

## How To Influence The Roadmap

- Open or upvote an issue on the
  [issue tracker](https://github.com/ahmed-g-gad/apothem/issues).
- Start a thread in
  [GitHub Discussions](https://github.com/ahmed-g-gad/apothem/discussions).
- See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose and land changes.
