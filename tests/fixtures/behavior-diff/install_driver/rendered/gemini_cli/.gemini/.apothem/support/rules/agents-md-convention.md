---
name: "agents-md-convention"
description: "The repository carries a single agent-facing canon at the root AGENTS.md; per-folder operating guidance lives in each folder's README.md, which serves both the human and the agent reader. Per-folder AGENTS.md companions are not required; any present companion stays current with its folder and the root AGENTS.md stays coherent with the AI-surface canon."
pathFilter: "**/AGENTS.md, **/README.md"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Root-Only AGENTS.md Convention — One Canon, Folder READMEs, Canon-Coherent

## What this rule enforces

The repository carries a **single agent-facing canon** at the root `AGENTS.md`. Per-folder operating guidance lives in each folder's `README.md` — one file per folder, **two audiences** (human + agent). The model:

- **Root `AGENTS.md`** is the agent-facing source of truth.
- **Per-folder `README.md`** is the navigable-folder guide an agent and a contributor both read on arrival.
- **Per-folder `AGENTS.md` companions are NOT required.** A meaningful folder without one is conformant.
- **Materialized harness-output `AGENTS.md`** under `harnesses/*/templates/` are **product surfaces**, not companions — they carry **no** obligation under this rule.

Where a folder genuinely needs a standalone agent companion beyond its README, the rare per-folder `AGENTS.md` it authors MUST stay **current** with its folder (updated in the same change-set that materially alters the folder's artifacts or conventions). The root `AGENTS.md` MUST stay **semantically coherent** with the AI-surface canon — it contradicts no shared claim.

## Pre-conditions

Applies whenever a meaningful folder is created, its load-bearing artifacts or local conventions change, its `README.md` is authored or edited, or a rare standalone per-folder `AGENTS.md` is authored or edited. The meaningful-folder set — the navigable-folder set the README convention applies to — is defined mechanically in §1.

## Required behavior

### 1. The Meaningful-Folder Definition

A folder is **meaningful** when it is navigable (a contributor or agent reasons about it as a unit) and load-bearing. Under the root-only convention this is the **navigable-folder set the README convention applies to** — each meaningful folder carries a `README.md` serving both readers. It is no longer an `AGENTS.md`-coverage requirement; the matcher retains the enumeration as its source-of-truth for the freshness check's folder-ownership map. The set is the union of two reproducible rules minus a fixed exclusion list:

- **(A) Companion-anchored.** Any folder that directly carries a contributor `README.md`. Excluded: test-fixture leaf directories whose README is itself the subject of a presence check (the `tests/conformity/<matcher>/{pass,fail}` fixture trees, the inject-header fixture trees) and single-artifact example scaffolds (`examples/minimal-*`) — their README documents a fixture, not a navigable subsystem.
- **(B) Source-package.** Any `src/apothem` folder that directly contains a Python source file but carries no `README.md` — the harness adapter packages, the shared adapter helpers, the hook library. An agent operating inside one of these packages needs the same orientation a README-bearing folder provides.

Constant exclusions across both rules: vendored trees (`_vendor/`), generated trees (`dist/`, `site/dist/`), git/cache/ephemera directories, the plan-suite scratch (`.apothem/`, `.plans/`, `.audit/`), and rendered harness-output template leaves (`src/apothem/harnesses/*/templates/`). Including any would pollute fixtures or describe machinery no contributor navigates by hand.

The definition is **executable**: `conformity/agents_md_coverage_grep.py` exposes `meaningful_folders(root) -> list[str]` as the single source of truth. Re-running the enumeration over an unchanged tree yields the identical set — the definition, the freshness check's folder-ownership map, and the CI gate all consume the same function, so the set never drifts between prose and gate. The matcher reports the set's size as `folders_inspected`; it raises **no** finding for a folder lacking a per-folder `AGENTS.md`.

### 2. The Folder README — One File, Both Readers

A folder's `README.md` carries the documentation for **both** the human reader and the agent reader. The agent-facing operating guidance a per-folder companion previously held now lives in a dedicated section of the same README. One file covers these concerns with no separate companion:

| Concern | What the folder `README.md` carries |
|---|---|
| **Purpose** | What the folder is and its role in the system — prose a contributor reads on arrival and an agent reads to understand what depends on it. |
| **Contents** | A map of children plus the load-bearing artifacts an agent touches and how they are organized. |
| **Conventions** | The concrete invariants an agent MUST respect — file-header form, frontmatter contract, naming scheme, gate requirements, mutation guards. |
| **Operating guidance** | How to add, modify, or remove an artifact in this folder safely, and which checks verify the change. |
| **Relationships** | Cross-links to sibling folders and the upstream / downstream edges — what this folder consumes and produces. |

The agent-facing section is **stable operating contract**, not volatile inventory: it does NOT carry counts (e.g., "71 rule files") that go stale. The root `AGENTS.md` remains the agent-facing **canon**; the folder README extends it folder-by-folder for the navigable-folder reader.

### 3. The Optional Standalone Companion File Shape

A per-folder `AGENTS.md` is **optional**. Where a folder genuinely needs a standalone agent companion beyond the agent-facing section of its README, the companion follows the root canon's file shape: a YAML frontmatter block (`name`, `version`, `updated`, `description`, `scope: folder`, `portability: repo-local`), then the canonical single-line SPDX license header, then the body authored against `templates/agents-md-template.md`. Any such companion is **agnostic**: it privileges no single harness, model, or tool, and pre-sets no model or effort preference. A folder describing a specific harness adapter names that harness by its catalog slug (one entry among the registered set), never by a privileging brand phrase. The same shape and agnostic discipline apply to the agent-facing section of a folder's README.

### 4. The Living-Document Rule

A folder's `README.md` — the file carrying its operating contract — MUST be updated in the **same change-set** that materially alters its folder's artifacts or conventions: a new load-bearing artifact, a removed one, a changed local convention, a changed mutation guard. The same obligation binds any present standalone `AGENTS.md` the folder keeps. A folder change that lands without updating the present companion is a **freshness defect**: the companion now misdescribes the folder.

The defect is detected mechanically. `agents_md_coverage_grep.py` reads git commit history and flags a folder whose directly-contained artifacts were last committed more recently than its **present** `AGENTS.md`. A folder with no per-folder `AGENTS.md` raises no finding — absence is conformant. The signal is **commit time**, not filesystem mtime — a checkout rewrites mtimes, so only commit history carries the truth of what changed when. Where git history is unavailable, the check degrades to a clean pass and never blocks a fresh clone.

### 5. The Canon-Sync Rule

The root `AGENTS.md` is the AI-surface **canon**. Every folder README's agent-facing guidance — and any present standalone per-folder `AGENTS.md` — **extends** the canon folder-by-folder and **contradicts no shared claim** the canon makes. The shared claims to stay coherent with: plans locality, authorship headers, ambiguity handling, naming, release freshness, human-only authorship, and public-surface plain-language. A folder MAY add folder-specific operating guidance the canon does not carry; it MUST NOT state a folder-specific rule that conflicts with a canon shared claim. When a folder's reality and the canon diverge, the divergence is a **canon-sync defect**: reconcile the folder guidance to the canon, or — if the folder genuinely needs an exception — route the exception through the canon, never silently in the per-folder file.

## Disclosure surface

Every folder-guidance emission, refresh, or reconciliation is recorded in the disclosure ledger:

- `[Companion — authored: <folder>/README.md (agent section); covers: <artifact-set>]` for new agent-facing folder guidance (or `<folder>/AGENTS.md` for a rare standalone companion).
- `[Companion — refreshed: <folder>/README.md; reason: <folder-change | convention-change | canon-sync>]` for an update.
- `[Companion — canon-sync: <folder>/README.md; reconciled: <shared-claim>]` for a divergence reconciled against the canon.

## Failure tells

A meaningful folder with no `README.md` (the navigable-folder reader has no guide). A folder README that omits agent-facing operating guidance, leaving an agent without the folder's invariants and safe-operation steps. A folder README — or a present standalone `AGENTS.md` — carrying a volatile inventory count that has gone stale. A folder whose artifacts changed in a commit that did not touch its operating-contract surface (the README, or a present companion). Folder guidance that contradicts a root-canon shared claim (e.g., asserts a plans location other than `<project-root>/.apothem/plans/`). Folder guidance that privileges one harness by a brand phrase or pre-sets a model / effort preference. A materialized harness-output `AGENTS.md` under `harnesses/*/templates/` mistaken for a companion and held to the folder-guidance obligation.

## Bindings (§0.j five-direction)

- **Drives →** Every meaningful folder's `README.md` agent-facing guidance and any rare present standalone `AGENTS.md`. The present-companion freshness matcher at `conformity/agents_md_coverage_grep.py`. The optional template at `templates/agents-md-template.md`. The CI coverage gate that runs the matcher on every change.
- **Driven by ←** The root `AGENTS.md` AI-surface canon (the §5 canon each folder's guidance extends). The own-voice, harness-agnostic baseline established by `agnostic-posture.md` (every surface inherits the agnostic posture).
- **Gated by ←** The frontmatter `pathFilter` (`**/AGENTS.md, **/README.md`): the rule loads when a folder README or a standalone `AGENTS.md` is touched. The §1 meaningful-folder definition (a folder outside the navigable set carries no README obligation). `conformity/agents_md_coverage_grep.py` (the advisory corpus sweep for missing or stale folder companions under `gate --all`) and `scripts/dev/check_readme_file_coverage.py --strict` (every shipped file named in its folder README).
- **Satisfies →** The root-only agent-surface discipline: one agent-facing canon at the root, per-folder operating guidance in each folder's README, every present companion current and canon-coherent.
- **Established by ↑** The root `AGENTS.md` AI Surface Canon section; the per-folder README convention this rule centers.
- **Cross-bound with ↔** `agnostic-posture.md` (the §3 agnostic invariant the folder-guidance content sweep enforces). `own-voice-reimplementation.md` (the own-voice baseline every folder-guidance prose honors). `plain-language.md` (the folder's agent-facing guidance is an out-of-scope agent-facing process surface, not a user-facing surface — its agent vocabulary is load-bearing).
