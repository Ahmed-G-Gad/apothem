---
name: "living-docs"
description: "Every change to a documented public surface — a CLI command or flag, a harness adapter, a profile field, an installer flag or environment variable, a configuration key, or any surface with a page under site/content/docs/ — MUST update its documentation page in the same change-set; source-generated reference pages are kept current by re-running the reference-inventory generator and committing the regenerated pages."
pathFilter: "**/site/content/docs/**, **/src/apothem/cli/**, **/src/apothem/harnesses/**, **/src/apothem/schemas/profile.schema.json, **/scripts/installer/**"
alwaysApply: false
paths:
  - "**/site/content/docs/**"
  - "**/src/apothem/cli/**"
  - "**/src/apothem/harnesses/**"
  - "**/src/apothem/schemas/profile.schema.json"
  - "**/scripts/installer/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Living Documentation — Same-Change-Set Docs for Every Documented Public Surface

## What this rule enforces

Documentation is part of the change, not a follow-up. When a behavior change touches a **documented public surface**, the page describing that surface **MUST** be updated in the **same change-set** as the behavior change. This is the documentation analogue of the production-ready same-change-set discipline at `rules/production-ready-prs.md`: just as a code change ships its tests, CHANGELOG entry, and conformant commit together, a public-surface change ships its docs update together. A documented surface that drifts ahead of its page — even transiently across a commit boundary — is non-conformant. Apothem self-applies this rule: its own docs tree under `site/content/docs/` is kept current under the same binding it ships to host projects.

## Pre-conditions

The rule applies whenever a change touches a documented public surface:

| Surface | Source of truth | Documented at |
|---|---|---|
| **CLI command / flag** | `src/apothem/cli/` | `site/content/docs/reference/cli.mdx` |
| **Harness adapter** | `src/apothem/harnesses/<name>/` | the harness-registry reference + the harness's how-to page |
| **Profile field** | `src/apothem/schemas/profile.schema.json` | the profile-fields reference |
| **Installer flag / env var** | `scripts/installer/` | the install how-to |
| **Configuration key / any other** | — | its page under `site/content/docs/` |

The rule does NOT apply to internal-only surfaces with no public docs page (private helpers, test fixtures, conformity matchers) — they carry no living-docs obligation. Trivial-scope edits per the host's threshold that do not alter a documented surface's behavior, signature, or default are exempt.

## Required behavior

### 1. Same-Change-Set Docs Update

A change to a documented public surface **MUST** update the corresponding page in the same change-set. Deferring the docs update to a later commit or PR is forbidden — the follow-up never lands, and the page is stale at the merge boundary. The update covers every observable shift the change introduces: a renamed flag updates the flag's documented name; a new profile field documents its type, default, and meaning; a removed adapter removes its registry row and how-to page.

### 2. Source-Generated Reference Pages

Three reference surfaces are **source-generated** — derived mechanically from the source of truth, never hand-maintained:

- **CLI reference** (`reference/cli.md`) — generated from the Click command tree.
- **Harness-registry reference** — generated from the registered `apothem.harnesses` entry points.
- **Profile-fields reference** — generated from `profile.schema.json`.

A change touching any of these source surfaces **MUST** regenerate the affected pages by re-running `node site/scripts/update-reference-inventory.mjs` and committing the regenerated pages in the same change-set. The generator output is authoritative; hand-edits to a source-generated page are overwritten on the next regeneration and **MUST NOT** be relied upon.

### 3. Hand-Authored How-To Pages

Hand-authored pages (how-to guides, conceptual pages, tutorials) describing a changed surface **MUST** be updated by hand in the same change-set. Adding a CLI flag that changes a documented workflow updates both the regenerated `reference/cli.md` **and** the relevant how-to page that walks the workflow.

### 4. Worked Example — Adding a CLI Flag

A developer adds a `--dry-run` flag to `apothem install` in `src/apothem/cli/`. The living-docs binding requires the same PR to:

1. **Regenerate `reference/cli.md`** — run `node site/scripts/update-reference-inventory.mjs`; the regenerated page now lists `--dry-run` with its help text under `apothem install`. Commit the regenerated page.
2. **Update the relevant how-to** — the install how-to under `site/content/docs/` that walks `apothem install` gains a sentence on `--dry-run` (when to use it, what it previews). Edit by hand.

Both land in the same change-set as the flag. Ship the flag without the docs update and CI's docs-reference-sync / stale-doc drift gate (§Mechanical enforcement) fails: it re-runs the generator in a clean tree and diffs the result against the committed pages; a non-empty diff means the committed `reference/cli.md` is stale, and the gate blocks the merge until the regenerated page is committed.

### 5. Two-Reader-Class Definition of Done

The docs surface is complete only when it serves both reader classes. Documentation is done when, and only when, **both** hold:

- **(a) Newcomer self-sufficiency.** A newcomer with no prior context can clone, understand, configure, and run the project from the documentation surfaces **alone** — without reading the implementation, consulting a maintainer, or reconstructing intent from commit history. The mechanical README structure that carries this bar (the Install section, quickstart-path coexistence, anti-orphanism machinery) is specified at `rules/production-ready-prs-surfaces.md` §6.6 and is not restated here.
- **(b) Agent locatability.** The documentation structure and surrounding pages let an AI coding agent locate any feature and infer its purpose **without** reading the implementation — the docs tree names where a feature lives and what it is for. Locatability under this bar (an agent can find and read the *intent* of a surface from the docs) is distinct from the reachability discipline at `rules/systemic-participation.md` (a surface is wired into the graph); a surface can be reachable yet undocumented, and this bar is unmet until its page states what it is for.

Neither class is optional: a page that satisfies (a) but leaves an agent unable to locate a feature, or satisfies (b) but leaves a newcomer unable to run the project, is not done.

## Mechanical enforcement

The **docs-reference-sync / stale-doc drift gate** enforces this rule in CI. It runs `node site/scripts/update-reference-inventory.mjs` in a clean checkout and diffs the regenerated source-generated pages against the committed pages. A non-empty diff means a documented source surface changed without its reference page being regenerated; the gate fails and names the stale page. This is the docs analogue of the production-ready CI-green discipline: a stale source-generated reference page blocks the merge the way a failing test does. Hand-authored how-to drift is a reasoned review check, not mechanically diffable — reviewers confirm a surface change carries its how-to update.

## Disclosure surface

Every living-docs outcome is recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[Living-Docs — surface: <cli | harness | profile-field | installer | config-key>; page: <docs-path>; update: regenerated | hand-edited]` for every same-change-set docs update.
- `[Living-Docs — regenerated: reference/cli.md | harness-registry | profile-fields; generator: update-reference-inventory.mjs]` for every source-generated page refresh.
- `[Living-Docs — deferred: docs update out-of-scope because <reason>; tracking: <where>]` only when the surface change genuinely carries no documented public effect; the deferral names why the page needs no update.

## Failure tells

A PR adding a CLI flag with no change to `reference/cli.md`. A new harness adapter merged without a registry-reference regeneration or a how-to page. A renamed profile field whose documented name still shows the old identifier. An installer env var added to `scripts/installer/` with no mention in the install how-to. A hand-edit to a source-generated reference page (overwritten on the next regeneration). A "docs update coming in a follow-up PR" note on a surface-changing diff. A green local build with a CI docs-reference-sync drift-gate failure (the committed reference page is stale against the source of truth).

## Bindings (§0.j five-direction)

- **Drives →** The same-change-set docs update on every documented-public-surface change under this rule's `pathFilter`. The regeneration of source-generated reference pages via `node site/scripts/update-reference-inventory.mjs`. The CI docs-reference-sync / stale-doc drift gate that diffs regenerated pages against committed pages.
- **Satisfies →** The living-documentation mandate (documented surfaces never drift ahead of their pages). The documentation analogue of the production-ready same-change-set discipline.
- **Established by ↑** The production-ready same-change-set discipline at `rules/production-ready-prs.md` (this rule projects that discipline onto the documentation surface). The source-generated reference-inventory generator at `site/scripts/update-reference-inventory.mjs`.
- **Gated by ←** The `pathFilter` (documented public source surfaces + the docs tree only; internal-only surfaces are exempt). The trivial-scope threshold (edits that do not alter a documented surface's behavior, signature, or default are exempt). The CI docs-reference-sync drift gate's clean-tree diff baseline.
- **Cross-bound with ↔** `rules/production-ready-prs.md` (the production-ready same-change-set discipline this rule is the documentation analogue of). `rules/production-ready-prs-surfaces.md` (§6.6 carries the mechanical README structure for the newcomer-self-sufficiency limb of §5's two-reader-class definition of done). `rules/systemic-participation.md` (a documented surface and its page are reciprocal participants; the page is the surface's downstream consumer; its reachability discipline is distinct from the agent-locatability limb of the two-reader-class definition of done). `rules/recommend-next-step.md` (terminal-surface forward-move discipline this rule's tail honors). `rules/propagation.md` (the full reference-graph propagation mandate this docs-tier rule is one participant of).

## Recommended Next Step

**Run `node site/scripts/update-reference-inventory.mjs`** after any change to a CLI command, harness adapter, or profile field, then commit the regenerated reference pages alongside the source change so the CI docs-reference-sync drift gate stays green, per `rules/recommend-next-step.md`.
