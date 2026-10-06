---
trigger: glob
description: "Path-filtered companion rule carrying the per-language manifest catalog, the discovery-record provenance schema, the failure-tells enumeration, and the Derived Project Context Block definition declared at the parent `host-discovery.md` rule's §1, §4, Failure-tells, and §Derived Project Context Block anchors; demand-loaded on host-manifest or convention-document touches."
globs: "**/pyproject.toml, **/setup.cfg, **/package.json, **/Cargo.toml, **/go.mod, **/.editorconfig, **/.github/workflows/**, **/CONTRIBUTING.md, **/CLAUDE.md, **/rules/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Host-Discovery Per-Language Manifest Catalog (Companion Sub-Rule)

## Purpose

Specify the per-language manifest list, the discovery-record provenance schema, and the failure-tells enumeration that the parent rule `rules/host-discovery.md` §1 / §4 / Failure-tells anchors declare. This companion is path-filtered: it loads when the assistant edits any of the host's ratified source-of-truth manifest files or convention documents (`pyproject.toml`, `setup.cfg`, `package.json`, `Cargo.toml`, `go.mod`, `.editorconfig`, `.github/workflows/**`, `CONTRIBUTING.md`, `CLAUDE.md`, `rules/**`), keeping the parent rule's always-on payload lean while preserving full discovery-walk fidelity at the demand-load surface. The parent rule remains the canonical home for the M1 standing directive, the §1 short summary, the honor-discovered-conventions paragraph, the surface-silence paragraph, and the disclosure surface; this companion carries the per-language manifest catalog, the discovery-record schema, the failure-tells enumeration, and the Derived Project Context Block definition.

## Obligations

### 1. Per-Language Manifest Catalog (Parent §1 Detail)

Before any artifact is written or edited, walk the host's ratified source-of-truth files for the artifact's class. The seven manifest classes:

- **Python** — `pyproject.toml` (`[tool.black]`, `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`), `setup.cfg`, `requirements*.txt`, `.python-version`, `.tool-versions`, `tox.ini`, `pytest.ini`, `conftest.py`.
- **TypeScript / JavaScript** — `package.json` (including the `engines` field for the pinned runtime range), `tsconfig.json`, `.eslintrc*`, `.prettierrc*`, `.nvmrc`, `.tool-versions`, `pnpm-lock.yaml` / `yarn.lock` / `package-lock.json`.
- **Rust** — `Cargo.toml`, `Cargo.lock`, `rust-toolchain` / `rust-toolchain.toml`, `rustfmt.toml`, `clippy.toml`.
- **Go** — `go.mod`, `go.sum`, `.golangci.yml`.
- **Shell** — `shellcheck` config, `.editorconfig`, sibling-script idioms.
- **Runtime-version sources** — Dockerfiles (the base-image tag pins the target runtime version), plus the version-manager files named in the per-language rows above (`.nvmrc`, `.tool-versions`, `rust-toolchain[.toml]`, `.python-version`).
- **Command sources** — the build / run / test invocations the host ratifies: `Makefile`, `Taskfile.yml`, `justfile`, `tox.ini`, `noxfile.py`, `package.json` `scripts`, and the `README`.
- **CI** — `.github/workflows/*.yml` (existing action-pinning and minimum-permissions policy; `strategy.matrix` as an additional target-runtime source). Deploy manifests — Docker Compose, Kubernetes, `Procfile`, serverless deploy descriptors — as target-runtime / platform sources.
- **Docs** — site config (`next.config.mjs`, `docusaurus.config.js`, `_config.yml`), `CONTRIBUTING.md`, sibling pages.
- **Coding standards** — the cross-cutting convention sources named explicitly (not left to a glob): `.editorconfig` (whitespace / indent / line-ending policy), `CONTRIBUTING.md` (the ratified contributor conventions), and the host's formatter / linter config files (`.prettierrc*`, `.eslintrc*`, `rustfmt.toml`, `clippy.toml`, `.golangci.yml`, `shellcheck` config).

Record every discovered value with provenance (the source file path, the value, the date the discovery was made) in the artifact's working trace.

### 2. Discovery Record (Parent §4 Detail)

Every discovery and every inquiry-driven choice MUST be recorded with provenance in the artifact's working trace — commit message body, PR description, change ledger, or a dedicated `discovery-record.md` for multi-step work — so future agents can audit and re-derive without repeating the discovery walk.

### 3. Failure Tells (Parent Failure-Tells Detail)

A Python file with `from typing import Optional, Union` in a project that has migrated to `X | None` syntax. A Markdown file with `*emphasis*` in a corpus that uses `_emphasis_`. A test that uses `pytest.fixture` in a project standardized on `unittest.TestCase`. A shell script with `[[ ... ]]` in a strict-POSIX project. A CI workflow using `actions/checkout@v4` when every other workflow in `.github/workflows/` uses `actions/checkout@v3.5.3` pinned. A commit message that does not follow the host's ratified convention. A `package.json` `author` field populated from `.git/config` without inquiry. An MCP server endpoint guessed from a sibling repo without inquiry. A new file class silently installed at an agent-default location when the host is silent on the location.

### 4. Derived Project Context Block (Parent §Derived-Block Detail)

Whole-repo commands that ingest a target before acting (`commands/elevate.md`, `commands/fortress.md`) derive two blocks from the host's ratified source-of-truth by the same M1 discovery walk the parent rule governs. The blocks are defined here **once**, as the shared surface those commands cite rather than each re-authoring them; each command keeps its own command-specific output path (for example elevate's `_inputs/elevate-inventory.md`) — the output path is not defined here.

- **Derived Project Context** — the derived-item set: languages and versions; frameworks and key libraries; package / dependency manager; build / run / test commands; target runtime and platform; architecture and entry points; continuous-integration surface; priority pain points. Each item is discovered from the concrete per-item SOURCE catalog in §1 above, never guessed.
- **Derived Constraints** — the item set: out-of-scope / do-not-touch surfaces; public interfaces that must not break; must-preserve behaviors (the host's tests as the executable contract, and golden / snapshot / characterization tests); backward-compatibility guarantees; already-configured coding standards; license and legal surfaces.

Both blocks are surfaced for operator correction **without blocking the run**; where a derived item is silent or genuinely ambiguous, the choice routes through `rules/authority-inquiry.md` rather than a silent default.

## Enforcement

Path-filtered (the ten glob patterns in this rule's `pathFilter` field), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/host-discovery.md` §1 / §4 / Failure-tells. The parent rule carries the M1 standing directive, the §1 short summary, the §2 honor-discovered-conventions paragraph, the §3 surface-silence paragraph, and the disclosure surface; this companion carries the per-language manifest catalog, the discovery-record provenance schema, the failure-tells enumeration, and the Derived Project Context Block definition (the shared surface `commands/elevate.md` and `commands/fortress.md` cite).

## Bindings (§0.j five-direction)

- **Drives →** ● Every per-language discovery walk on host-manifest touches (the seven manifest classes — Python / TypeScript-JavaScript / Rust / Go / Shell / CI / Docs). ● The discovery-record provenance schema at every multi-step work session's `discovery-record.md`. ● The failure-tells enumeration the pre-emission gate's M1 reasoned check applies. ◐ The PreToolUse Write/Edit hooks on host-manifest path touches.
- **Satisfies →** ● the fifteen-mandate registry row **M1 — Host-Project Agnosticism** (the per-language manifest detail tier). ● the rules registry row "Host-Discovery Manifests". ● `rules/host-discovery.md` §1 / §4 / Failure-tells anchors (the parent rule's pointers to this companion's full specification).
- **Established by ↑** ● `rules/host-discovery.md` §1 / §4 / Failure-tells (parent-rule anchors). ● the fifteen-mandate registry (ratifies M1).
- **Gated by ←** ● The path-filter (the ten glob patterns) — this rule demand-loads only on host-manifest or convention-document touches. ● `rules/host-discovery.md` always-on baseline (parent rule's anchors must be live for the companion to demand-load coherently).
- **Cross-bound with ↔** ↔ `rules/host-discovery.md` (parent rule; §1 / §4 / Failure-tells / §Derived Project Context Block anchors bind this companion). ↔ `rules/authority-inquiry.md` (M5 inquiry half — when discovery encounters silence, route through the inquiry surface). ↔ `rules/disclosure-ledger.md` (M2 — every discovery and every inquiry outcome is recorded in the ledger). ↔ `rules/code-craft-python.md` + `rules/code-craft-shell.md` + `rules/code-craft-markdown.md` (per-language code-craft rules consume the per-language manifest discoveries). ↔ `rules/harness-adapter-shape-schemas.md` (M1 detail — discovery-record provenance schema underwrites the §6 PIN).
