---
trigger: glob
description: "Every mutation of any artifact propagates, in the SAME change-set, to every dependent reference across the whole repository's reference graph — code, tests, docs, root files, `.github`, CHANGELOG, harness-rendered templates, the harness registry, plugin manifests, and cross-rule bindings. A mutation (add / edit / remove / rename / move / split / merge / deprecate) that lands without its reference updates is an orphan / half-edge finding. Unifies the docs-tier (living-docs) and component-tier (systemic-participation) propagation disciplines to the full reference graph; the existing drift gates are its mechanical arm."
globs: "**/*.py, **/*.md, **/*.mdx, **/*.json, **/*.yaml, **/*.yml, **/*.toml, **/*.sh, **/*.ps1, **/*.ts, **/*.js, **/*.mjs, **/*.css, **/*.mdc, **/*.txt"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Propagation — Same-Change-Set Sync to the Full Reference Graph

## What this rule enforces

Every mutation of any artifact MUST propagate, **in the same change-set**, to **every reference** across the repository's reference graph. A mutation is not done when the artifact changes — it is done when every dependent surface that references it is updated alongside it. This rule is the unifying generalization of the two existing propagation disciplines — `rules/living-docs.md` (docs tier) and `rules/systemic-participation.md` (component tier) — extended to the **full** reference graph, with the existing drift gates as its mechanical arm. Visibility is part of doneness — a change that works but is not surfaced where readers will find it is not finished; surface it.

## Pre-conditions

Applies whenever an artifact other surfaces reference is mutated. Trivial-scope single-line edits with no downstream reference are exempt; the obligation applies the moment a mutation changes a name, path, signature, count, public surface, or any value another surface depends on.

## Required behavior

### 1. Every mutation class triggers propagation

The triggering mutation classes are the closed set **{add, create, edit, modify, remove, delete, rename, move, split, merge, deprecate}**. Each, applied to a referenced artifact, triggers the same-change-set propagation obligation: a rename propagates to every citation of the old name; a removal propagates to (and removes) every reference to the removed artifact; an addition propagates to every index / registry / catalog that should list it.

### 2. The full reference graph

Every mutation propagates to the union below. The **component tier** (Code, Tests, Examples, READMEs, `.github`) is owned by `rules/systemic-participation.md` and the **docs tier** (documentation + source-generated reference pages) by `rules/living-docs.md` — this rule cites those owners for their per-surface obligations rather than restating them, and adds the surfaces neither sibling covers (AI-memory canon, CHANGELOG, harness-rendered templates / registry / plugin manifests, website catalog, cross-rule bindings):

- **Code** — dependent imports, call-sites, type references.
- **Inline symbol-level docs** — the docstring, type annotation, and why-not-what intent comment adjacent to a mutated symbol; a renamed parameter whose docstring still names the old parameter is a propagation miss (docstring authoring quality is owned by `rules/code-craft-python.md`; this surface is propagation *into* the inline symbol-doc when its symbol mutates).
- **Tests** — tests exercising or snapshotting the mutated surface (incl. behavior-diff golden fixtures).
- **Docs** — documentation pages; source-generated reference pages regenerated per `rules/living-docs.md`.
- **Examples · READMEs · root files** — example scaffolds, per-folder READMEs, root-level singletons.
- **Config templates & onboarding** — environment samples (`.env.example`), sample configs, and the contribution / onboarding guide (`CONTRIBUTING`) when a workflow or install step changes.
- **`.github`** — workflows, issue / PR templates that reference the surface.
- **AI-memory surfaces** — `CLAUDE.md` / `AGENTS.md` / `.github/copilot-instructions.md` canon + memory indexes.
- **CHANGELOG** — a user-facing change records an entry.
- **Harness-rendered templates · harness registry · plugin manifests** — the per-harness templates, `harness_registry.py`, and `.claude-plugin/plugin.json` (regenerated from its generator when commands / agents change).
- **Website catalog** — the docs-site catalog entry for the surface.
- **Cross-rule bindings** — reciprocal `## Bindings` back-pointers per `rules/bidirectional-binding.md`.

### 3. Mechanically attestable — the drift-gate arm

A mutation landing without its reference updates is an orphan / half-edge finding. The mechanical arm is the existing gate set; this rule binds, not duplicates, them:

- `conformity/orphan_output_grep.py` — orphan outputs (no consumer / no index / no provenance).
- `conformity/binding_reciprocity_grep.py` — half-edge cross-rule bindings.
- `.github/workflows/docs-drift.yml` + source-generated reference-page regeneration (`site/scripts/update-reference-inventory.mjs`) — docs drift.
- The plugin-manifest generator consistency test (`build_plugin_manifest` vs. the committed manifest) — manifest drift.
- The behavior-diff regression wall — install-output drift.

A new propagation surface the existing gates do not cover surfaces as a gap per `rules/persistent-conventions-vigilance.md` §4 (a candidate new matcher) — never a silent omission.

## Failure tells

A renamed symbol whose old name still appears at a call-site. A new command added without regenerating `.claude-plugin/plugin.json`. A removed artifact whose docs page / catalog entry / registry row survives. A user-facing change with no CHANGELOG entry. A new public surface absent from the reference pages. A cross-rule citation with no reciprocal back-pointer. A mutated surface whose behavior-diff golden fixture was not regenerated.

## Bindings (§0.j five-direction)

- **Drives →** Every mutation's same-change-set reference-graph update across the repo. The regeneration of generated artifacts (plugin manifest, reference pages, behavior-diff fixtures) when their source mutates. The CHANGELOG entry on every user-facing change.
- **Driven by ←** The WS-C propagation/sync mandate; the operator directive that every amendment propagate to every reference across the whole repo/project.
- **Gated by ←** The Pre-conditions trivial-scope carve-out: a single-line edit with no downstream reference is exempt; a change to a name, path, signature, count, public surface, or depended-on value is not. The frontmatter `pathFilter` (source, docs, and configuration file types). The documented-public-surface rule in `AGENTS.md` and the docs-reference-sync drift gate that holds regenerated reference pages to the source.
- **Satisfies →** The MAXIMAL reference-graph integrity end-state (no orphan, no half-edge, no stale reference); the CM-8 keystone (once propagation is mechanically attestable, every workstream's same-change-set obligation is enforced rather than manual).
- **Established by ↑** `rules/living-docs.md` (the docs-tier propagation this rule generalizes); `rules/systemic-participation.md` (the component-tier propagation this rule generalizes); `rules/bidirectional-binding.md` (the reciprocity surface).
- **Cross-bound with ↔** `rules/living-docs.md` (docs tier) · `rules/systemic-participation.md` (component tier) · `rules/bidirectional-binding.md` (binding reciprocity) · `rules/canonical-layout.md` (orphan prevention) · `rules/dynamism.md` (version/badge propagation) · `conformity/orphan_output_grep.py` + `conformity/binding_reciprocity_grep.py` + `.github/workflows/docs-drift.yml` (the mechanical drift-gate arm).
