<!-- SPDX-License-Identifier: MIT -->

# Roadmap

This roadmap describes where Apothem is headed. It is a statement of intent,
not a commitment; priorities shift as the project and its users evolve. For
what has already shipped, see the
[changelog](https://github.com/ahmed-g-gad/apothem/blob/main/CHANGELOG.md).
The repository's
[ROADMAP.md](https://github.com/ahmed-g-gad/apothem/blob/main/ROADMAP.md) is
the single roadmap; the
[roadmap page](https://apothem.ahmedgad.com/docs/community/roadmap) on the
project website is generated from it.

Status legend: **planned** · **in-progress** · **shipped**.

## Current release

The current line ships the host-agnostic harness configuration manager: a
shared profile (`~/.config/apothem/profile.yaml`) materialized into
harness-native configuration for the registered adapters, driven by the
`apothem` command line (`quickstart` · `install` · `update` · `uninstall` ·
`rollback` · `verify` · `status` · `diff` · `harnesses` · `profile` ·
`doctor` · `migrate-workspace` · `completion`).

| Item | Status | Notes |
| ---- | ------ | ----- |
| Seventeen harness adapters | shipped | Each with install, uninstall, update and verify; the [supported harnesses](https://apothem.ahmedgad.com/docs/harnesses) pages list them |
| Manifest-driven template propagation | shipped | One source of propagation truth at `src/apothem/lib/propagation-manifest.yaml` |
| Documentation site | shipped | Public site with generated reference indexes, brand assets, a machine-readable site index and release runbooks |
| Signed releases | shipped | Every GitHub Release carries signed artifacts, an SBOM and build provenance |
| `/plan` and `/research` pipelines | shipped | The staged spec, generate, review and execute planning pipeline, plus the thirteen-stage research pipeline |
| Audit commands and the `/fortress` loop | shipped | On-demand security, code, accessibility, performance, dependency, supply-chain, threat-model, architecture, code-review, docs-review and UX audits, wrapped by the `/fortress` hardening loop |
| Audit and drift-review infrastructure | shipped | Inventory and drift scanners behind the audit commands |
| Conformity gate | shipped | Validators for authorship headers, naming, code craft, hedging and binding reciprocity over every materialized surface, with behavior-diff goldens locking each adapter's output |
| Durable memory and opt-in continuous learning | shipped | A persistent memory tier and an opt-in learning loop that carry confirmed conventions across sessions |
| CI/CD pipeline and signed-release supply chain | shipped | Every change gated on lint, tests, type checks, a docs build and supply-chain checks before release |

## Near term

| Item | Status | Notes |
| ---- | ------ | ----- |
| Documentation guides | in-progress | More task-focused guides, diagrams and examples for real harness setups |
| npm / npx distribution | planned | Keep the `@ahmed-g-gad/apothem` npx entry point aligned with each release and broaden its platform coverage |
| Claude Code plugin listing | planned | Grow the plugin listing as the marketplace surface stabilizes |
| More harness adapters | planned | Additional harnesses as their configuration conventions stabilize and users request them |
| Profile schema enhancements | planned | Richer per-harness override surfaces and stricter validation diagnostics |
| Profile validation in the conformity gate | planned | Validate the shared profile against its schema as a gate check |
| Profile versioning and migration | planned | Version the profile format and migrate older profiles forward |
| `apothem update --watch` | planned | Re-materialize harness configuration when the profile changes |

## Longer term

| Item | Status | Notes |
| ---- | ------ | ----- |
| Cloud-hosted profile sync | planned | Optional and operator-controlled |
| Team-shared profile management | planned | One profile shared across a team |
| Editor extension with live conformity feedback | planned | Conformity findings while you edit, in VS Code-family editors |

## Long-term vision

Apothem aims to be the default way anyone manages harness configuration
across every tool they use: write conventions once, materialize them
everywhere, and keep them in sync as both preferences and harnesses evolve.

## How to influence the roadmap

- Open or upvote an issue on the
  [issue tracker](https://github.com/ahmed-g-gad/apothem/issues); a feature
  request there is the way to propose a roadmap item. Popular requests move
  faster.
- See [CONTRIBUTING.md](https://github.com/ahmed-g-gad/apothem/blob/main/CONTRIBUTING.md)
  for how to propose and land changes.
