---
name: "freshify"
description: "Host- and forge-agnostic command that renders a project fresh, clean, trace-free, and production-ready. Purges caches and stale artifacts, removes legacy/obsolete narrative and back-references, normalizes file / folder naming to the host's ratified convention, drives every surface to maximal naturalness and coherence (no backward-compatibility / staleness / process-refinement narrative anywhere), enforces a current-version-only facade with a concise current-version changelog, and drives the host's discovered quality gates to green. In-place freshening is the default; every destructive step (cache purge, version-control-history rewrite, artifact deletion, file / folder rename, stale-run-trace removal) is confirmation-gated through the structured-inquiry channel. Carries zero host- or forge-specific vocabulary; every surface is discovered via rules/host-discovery.md, never named."
argument-hint: "[path/to/repo/] [--purge-caches] [--rewrite-history] [--normalize-naming] [--strict]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /freshify — Agnostic Freshening Core

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Release Hygienist** and **Cognitive Insurgent** (`rules/cognitive-identity.md`) operating as the **freshening-instrument-not-author**. `/freshify` is the host- and forge-agnostic core of the freshening family: it renders a project fresh, clean, and trace-free against the production-ready discipline at `rules/production-ready-prs.md`, and it specializes nowhere. Every source forge, every continuous-integration surface, every package registry, and every release facade is **discovered** via `rules/host-discovery.md`, never named — the command MUST carry no forge- or registry-specific token. The forge-specific surface is layered on top by a separate specialization command; this command owns the generic freshening contract.

Apply the Five Cognitive Filters at full intensity during the trace sweep. Filter 1 (Obvious Purge) discards the first "what counts as a stale trace" answer and reaches for the comprehensive sibling set; Filter 5 (Aesthetic Demand) governs the changelog's prose form. The seven-axes-of-breadth taxonomy at `rules/cognitive-identity.md` §1 (Architecture · Concurrency · Performance · Security · Testing · Tooling · Observability) is the axes-of-attention frame — Tooling, Security, and Testing are load-bearing.

---

## Instructions

Execute `/freshify`. Ingest the target repository, sweep for caches and stale artifacts, remove legacy and obsolete narrative plus back-references, normalize file / folder naming to the host's ratified convention, drive every surface to maximal naturalness and coherence, enforce a current-version-only facade with a concise current-version changelog, drive the host's discovered quality gates to green, and culminate trace-free and production-ready.

Three operating invariants govern the sweep:

1. **In-place by default; destructive steps are opt-in.** Any irreversible action — a cache purge, a version-control-history rewrite, an artifact deletion, a file / folder rename, or a stale-run-trace removal — MUST first route a per-target confirmation through the structured-inquiry channel per `rules/interactive-questions.md` §6 (renames and moves use the §6.5 Rename / §6.6 Move canonical option sets). The destructive path is opt-in and never silent.
2. **The "etc." extension rule.** Where the source intent enumerates a trace class with a trailing "etc." or "e.g.", extend it comprehensively to its sibling members inferred from the intent per `rules/etc-extension.md` — never honor the short literal list. "caches, build artifacts, etc." extends to coverage databases, type-check caches, lint caches, test caches, hypothesis databases, dependency-resolver caches, rendered-documentation output trees, temporary scratch files, editor swap files, log files, and packaging staging directories — each discovered through the host's ratified ignore manifest, never assumed.
3. **Maximal naturalness, coherence, and naming normalization.** The freshening drives the whole tree toward maximal normality — narrative jargon reads as natural, human-authored product prose per `rules/plain-language.md`; file and folder names are uniform and normalized to the host's ratified convention per `rules/persistent-conventions-vigilance.md`; and no surface anywhere carries backward-compatibility, legacy, staleness, or process-refinement narrative per `rules/freshness-facade.md`. Naturalness and coherence are swept across **all** nuanced details — narratives, the files and folders themselves, and their naming — not only the obvious public copy.

**Reference Template:** Check `CLAUDE.md` for template path. Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) active throughout.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, and again before the final step or any handoff. Covers: Pipeline position; Consumed; Emitted; Pre-flight inquiry set; Confirmation contract; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | Root directory of the target repository. MUST contain a root manifest plus the host's ratified ignore manifest, so the generated-state surface resolves. The command refuses execution when no freshening surface resolves. |
| `--purge-caches` | Flag | No | Opt in to the destructive cache-and-artifact purge. Without the flag, the cache sweep reports the purge targets and routes a per-target confirmation before any deletion; the flag pre-authorizes the purge but still records each target in the report. |
| `--rewrite-history` | Flag | No | Opt in to the destructive version-control-history rewrite that strips stale run traces from history. Without the flag, the history sweep reports the rewrite scope and routes a confirmation; the rewrite never proceeds on a shared branch without explicit operator selection. |
| `--normalize-naming` | Flag | No | Opt in to the destructive file / folder rename pass that normalizes naming to the host's ratified convention. Without the flag, the naming sweep reports the off-convention targets and routes a per-target Rename / Move confirmation before any rename; the flag pre-authorizes the rename pass while still recording each target and propagating every inbound reference in the same change-set. |
| `--strict` | Flag | No | Promote every advisory freshening finding to a blocking finding. Under `--strict`, the freshening is complete only when zero stale traces, zero off-convention names, zero non-natural narrative, and zero blocked gates remain. |

---

## Workflow — Six Freshening Stanzas

1. **Cache and stale-artifact sweep.** Read the host's ratified ignore manifest as the source of truth for generated state per `rules/host-discovery.md`, then enumerate every cache and artifact tree it declares — extend the class comprehensively per the "etc." extension rule (coverage databases, type-check / lint / test caches, dependency-resolver caches, rendered-documentation output, temporary scratch, editor swap files, log files, packaging staging). Report each enumerated target. The purge is destructive: route a per-target confirmation per `rules/interactive-questions.md` §6 before any deletion, with the in-place default being "retain, report only." The `--purge-caches` flag pre-authorizes the purge while still recording each target.
2. **Legacy-narrative and back-reference removal.** Moved to `references/step-02-legacy-narrative-and-back-reference.md`. MUST read it in full before executing this step.
3. **Naming uniformity and naturalism-coherence sweep.** Normalize file and folder naming to the host's ratified convention discovered per `rules/host-discovery.md` (kebab-case / snake_case / the host's observed sibling pattern) — every off-convention name across the whole tree is a rename target. Drive narrative jargon to natural, human-authored product prose per `rules/plain-language.md`, and reconcile naming and prose to one coherent voice per `rules/persistent-conventions-vigilance.md`. A rename is destructive at the path level: route a per-target Rename / Move confirmation per the `rules/interactive-questions.md` §6.5 Rename / §6.6 Move canonical option sets before any rename, with the in-place default being "report only," and propagate every inbound reference (imports, links, registry rows, manifests) in the same change-set per `rules/propagation.md` so the rename leaves no broken reference. The `--normalize-naming` flag pre-authorizes the rename pass while still recording each target and its propagated references.
4. **Current-version-only facade enforcement.** Drive the public surfaces to a current-version-only state: one current version declaration, narrative that references the current product rather than its history, and a concise current-version changelog entry curated per the host's ratified changelog format. Stale run traces and history narrative are removal candidates. A version-control-history rewrite that strips stale traces is destructive: route a confirmation per `rules/interactive-questions.md` §6 with the in-place default being "leave history intact, freshen the working tree only," and never rewrite a shared branch without explicit operator selection. The `--rewrite-history` flag pre-authorizes the rewrite while still recording the scope.
5. **Drive all gates to green — relentlessly, until 100% green.** Discover and run the host's ratified quality gates per `rules/host-discovery.md` — the formatter, the linter, the type-checker, the test runner, the documentation build, and the security scan declared in the manifest and the host's continuous-integration surface. Run the diagnose → root-cause-fix → re-run cycle **relentlessly across every gate until each one exits 100% green** and, where the host defines a scoring surface, sits at its ratified maximum — no gate left red, no gate skipped, no gate softened. The relentless loop is bounded for iteration safety per `rules/planning-techniques.md` §1: the diagnose-fix-rerun cycle caps at a default of three root-cause attempts per gate, and a gate still red at the cap is NOT softened or suppressed — it escalates as a blocking finding through the structured-inquiry channel per `rules/interactive-questions.md` §3 with its root-cause diagnosis and a defined retreat (operator decision or a `[Deferral]`-with-rationale), never a silent pass. No fix suppresses a gate; every fix addresses the root cause per `rules/operational-mandates.md` CM-8.
6. **Trace-free production-ready culmination.** Re-sweep the freshened tree to confirm zero residual caches, zero stale artifacts, zero legacy or obsolete narrative, zero back-references, zero placeholders, zero process-narration mentions, zero off-convention file / folder names, zero non-natural narrative jargon, and zero stale run or history traces — extended comprehensively per the "etc." extension rule. Confirm every rename and removal propagated to its inbound references in the same change-set per `rules/propagation.md` so no broken reference remains and every freshened surface is highlighted where future readers — AI coding agents and end users alike — will find it. Run the Validation Gate (the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md`) against the freshened tree and the changelog. Emit the freshening report with the per-gate verdict, the per-axis attestation, every confirmation outcome, and the sweep's `verified:` date. The culmination is fresh and production-ready when the re-sweep is clean, every change is propagated, and every gate is green.

---

## Mandates

| Mandate | Application |
| ------- | ----------- |
| **M15 — Production-Ready** | The freshening operationalizes `rules/production-ready-prs.md` — the current-version-only facade, the concise current-version changelog, and the green quality matrix are its pass conditions. |
| **M1 — Host Agnosticism** | Every forge, registry, and continuous-integration surface is discovered per `rules/host-discovery.md`, never named; the command carries no forge- or registry-specific token. |
| **M5 — Authority** | Every ambiguity in the ignore manifest, the gate command set, the changelog format, or the versioning scheme routes through `rules/authority-inquiry.md`; every destructive step clears a per-target confirmation per `rules/interactive-questions.md` §6 before acting. |
| **M2 — Plain-language** | Removed process-narration (refinement / fix / modification mentions) is replaced with current-product voice per `rules/plain-language.md`; the freshened narrative reads as human-authored product copy. |
| **Naming & convention coherence** | File / folder naming is normalized to the host's ratified convention and reconciled to one coherent voice per `rules/persistent-conventions-vigilance.md`; every off-convention name is a rename target cleared through the per-target Rename / Move confirmation. |
| **Propagation** | Every removal and rename propagates in the same change-set to every dependent reference across the whole reference graph per `rules/propagation.md`; emerging or existing merits / features / changes are highlighted everywhere applicable so both AI coding agents and end users understand the freshened project. |
| **M4 — Self-application** | The freshened tree and the changelog pass the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` before the report is finalized. |

---

## Output

- The freshened working tree (in-place by default), with every confirmation outcome recorded.
- The concise current-version changelog entry curated per the host's ratified changelog format.
- The freshening report at `_outputs/freshify-report.md` (executive summary + per-stanza sweep results + removal index + confirmation log + per-gate green/blocked verdict + per-axis attestation + validation-gate attestation + bindings).
- An optional sweep inventory at `_inputs/freshify-inventory.md` (the Input Ingest read inventory).

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Recommended Next Step

**Invoke the forge-specific specialization `/github-deploy-fresh`** against the freshened tree to layer the source-forge deployment surface onto this agnostic freshening core, then publish the current-version release through the host's discovered release facade.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
