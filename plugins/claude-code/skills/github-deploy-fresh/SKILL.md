---
name: "github-deploy-fresh"
description: "GitHub-specific specialization of /freshify that produces a single 100% fresh first-version release on origin/main — one templated release: <repo-name> v0.1.0 commit, strictly-green and maximal-score workflow cards (OpenSSF Scorecard where applicable), a curated concise first-version CHANGELOG, and zero residual GitHub traces (caches, branches, pull requests, prior releases/packages/deployments, failed runs, workflow-run history, draft/pre-releases, stale tags, gist/wiki traces, Pages build history, Actions run logs, environment/deployment records, branch-protection drift, git history). Inherits the agnostic freshening core from /freshify and adds only the forge-specific surface; in-place freshening is the default and every destructive step is confirmation-gated through the structured-inquiry channel."
argument-hint: "[path/to/repo/] [--purge-runs] [--rewrite-history] [--recreate-repo] [--strict]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /github-deploy-fresh — GitHub First-Version Fresh Deployment

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Release Hygienist** and **Cognitive Insurgent** (see `rules/cognitive-identity.md`), operating as the **deployment-instrument, not-author**.

`/github-deploy-fresh` is the GitHub specialization of the freshening family. It **inherits** the host- and forge-agnostic freshening core from `/freshify` (`freshify.md`) — cache sweep, legacy-narrative removal, naming-uniformity and naturalism-coherence sweep, current-version-only facade enforcement, drive-gates-green, trace-free culmination — and **references** that core rather than re-implementing it. On top of the inherited substrate it layers only the GitHub-specific deployment surface: the templated `release: <repo-name> v0.1.0` commit, the `origin/main` target, the strictly-green-and-maximal-score workflow assertion (OpenSSF Scorecard where applicable), the first-version CHANGELOG curation, and the GitHub zero-trace removal inventory.

Forge-specific vocabulary is **in scope** here — unlike the agnostic `/freshify`, this command names GitHub, `origin/main`, pull requests, GitHub Releases / Packages / Actions / Pages, OpenSSF Scorecard, and the registries the freshened repository publishes to (npm, npx).

Apply the Five Cognitive Filters at full intensity through the trace sweep: Filter 1 (Obvious Purge) discards the first "what counts as a residual GitHub trace" answer and reaches for the comprehensive sibling set; Filter 5 (Aesthetic Demand) governs the first-version CHANGELOG's prose form. The seven-axes-of-breadth taxonomy at `rules/cognitive-identity.md` §1 frames the axes of attention — **Tooling, Security, and Testing are load-bearing**.

---

## Instructions

Run `/freshify`'s agnostic core against the target repository first (or consume its already-freshened tree), then layer the GitHub deployment surface: author the single templated `release: <repo-name> v0.1.0` commit, drive every GitHub workflow card to strictly-green-and-maximal-score, curate the first-version CHANGELOG, and remove every residual GitHub trace per the §Workflow inventory. Culminate fully trace-free and production-ready — one fresh commit on `origin/main`, one first-version GitHub Release tagged `v0.1.0`, and no surviving history.

Two standing rules govern every step:

- **In-place freshening is the default.** Every irreversible GitHub-side action — a git-history rewrite, a branch / run / package / tag / release purge, a Pages-build-history wipe, an environment / deployment-record removal, or the repository delete-and-recreate — routes a per-action confirmation through the structured-inquiry channel per `rules/interactive-questions.md` §6, with the non-destructive in-place path as the stated default and the destructive path opt-in and default-off. The delete-and-recreate is an explicit `MAY` capability only, default-off behind its gate, and preserves all current repository metadata on recreation.
- **The "etc." extension rule.** Where the seed intent enumerates a GitHub-trace class with a trailing "etc." or "e.g.", extend it comprehensively to its inferred sibling members — never honor the short literal list. "Previous versions / releases / packages / deployments … and so on" extends to draft and pre-releases, stale tags, GitHub Packages versions, Pages build history, Actions run logs and workflow-run history, environment and deployment records, branch-protection drift, gist and wiki traces, fork-network artifacts, and registry coordinates (npm, npx) pointing at superseded versions — each named explicitly as its own removal step.

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
| `path/to/repo/` | Path | Yes | Root directory of the target repository. MUST carry a root manifest, the host's ratified ignore manifest, and an `origin` remote pointing at the GitHub repository so the deployment surface resolves. The command refuses execution when no deployment surface resolves. |
| `--purge-runs` | Flag | No | Pre-authorize the destructive purge of GitHub Actions run logs, workflow-run history, and failed-run records. Without the flag, the run sweep reports the purge targets and routes a per-action confirmation before any deletion; with it, the purge proceeds while still recording each run id in the report. |
| `--rewrite-history` | Flag | No | Pre-authorize the destructive git-history rewrite that collapses the repository to the single `release: <repo-name> v0.1.0` commit. Without the flag, the history sweep reports the rewrite scope and routes a confirmation; the rewrite never proceeds on `origin/main` without explicit operator selection. |
| `--recreate-repo` | Flag | No | Opt into the explicit `MAY` capability that deletes the GitHub repository and recreates it with all current metadata to guarantee full freshness. Default-off; even with the flag the delete-and-recreate routes a per-action confirmation, captures the current metadata first, and refuses to proceed without explicit operator selection. |
| `--strict` | Flag | No | Promote every advisory deployment finding to blocking. Under `--strict`, the deployment is complete only when zero residual GitHub traces remain, every workflow card is green, and every applicable score (OpenSSF Scorecard) sits at its maximal value. |

---

## Workflow — Six Deployment Stanzas

1. **Inherit the agnostic freshening core.** Run `/freshify` against the target repository first (or consume its already-emitted freshened tree): the cache-and-stale-artifact sweep, the legacy-narrative and back-reference removal, the naming-uniformity and naturalism-coherence sweep, the current-version-only facade enforcement, the drive-all-gates-green stanza, and the trace-free re-sweep, each with its own confirmation contract per `freshify.md`. This command consumes that freshened output as its substrate and MUST NOT re-implement those passes.
2. **GitHub-trace removal inventory.** Moved to `references/step-02-github-trace-removal-inventory.md`. MUST read it in full before executing this step.
3. **Strictly-green-and-maximal-score workflow assertion — bounded loop until ALL 100% green.** Drive every GitHub Actions workflow card to strictly green and, where a scoring surface applies — OpenSSF Scorecard most prominently — to its maximal value. Run the diagnose → root-cause-fix → re-trigger cycle **relentlessly across every workflow until ALL of them are 100% green** and every applicable score sits at its maximum — no card left red, no workflow disabled, no gate softened. Apply in-place root-cause fixes per the host's discovered idioms (CM-8 bottleneck-first per `rules/operational-mandates.md`). The relentless loop is bounded for iteration safety per `rules/planning-techniques.md` §1: the diagnose-fix-retrigger cycle caps at a default of three root-cause attempts per workflow, and a card still red at the cap is NOT suppressed or softened — it escalates as a blocking finding through the structured-inquiry channel with its root-cause diagnosis and a defined retreat (operator decision or disclosed deferral), never a disabled workflow or a softened pass.
4. **Single fresh commit on `origin/main`.** Author the single templated `release: <repo-name> v0.1.0` commit — `<repo-name>` is a placeholder token resolved from the repository name at Input Ingest, NEVER a hardcoded literal — with sibling `release: <sub-package> v0.1.0` lines for each sub-package where the repository is a monorepo. The git-history rewrite that collapses the repository to this single commit is destructive: route a confirmation per `rules/interactive-questions.md` §6, with the in-place default being "leave history intact, push the fresh commit only"; never rewrite `origin/main` without explicit operator selection. `--rewrite-history` pre-authorizes the rewrite while still recording its scope. The repository delete-and-recreate is the explicit `MAY` capability at stanza 6.
5. **First-version CHANGELOG curation.** Curate a concise first-version `CHANGELOG.md` entry per Keep-a-Changelog: a single `[0.1.0]` section dated to the deployment, with no `[Unreleased]` backlog, no prior-version sections, and no back-references to superseded work. Filter 5 (Aesthetic Demand) governs the prose form; the entry reads as a fresh first-version statement, not a migration narrative.
6. **Trace-free production-ready culmination.** Re-sweep the deployed repository to confirm a single commit on `origin/main`, one first-version GitHub Release tagged `v0.1.0`, strictly-green-and-maximal-score workflow cards, a first-version CHANGELOG, and zero residual GitHub traces per the stanza-2 inventory (extended per the "etc." extension rule). The repository delete-and-recreate is available here as the explicit `MAY` capability: when in-place freshening cannot reach full freshness, route the `--recreate-repo` confirmation per `rules/interactive-questions.md` §6, capture all current repository metadata, delete the GitHub repository, and recreate it with the captured metadata preserved — default-off, opt-in, never silent. Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the deployed tree, the commit, and the CHANGELOG. Emit the deployment report with the per-workflow green/score verdict, the per-axis attestation, every confirmation outcome, and the sweep's `verified:` date. The culmination is fresh and production-ready when the re-sweep is clean.

---

## Mandates

| Mandate | Application |
| ------- | ----------- |
| **M15 — Production-Ready** | The deployment operationalizes `rules/production-ready-prs.md`: the single fresh commit, the strictly-green-and-maximal-score workflow cards, the first-version CHANGELOG, and the human-only commit authorship are the pass conditions. |
| **M5 — Authority** | Every ambiguity in the `<repo-name>` token, the sub-package set, the Scorecard applicability, the registry coordinates, or the signing requirement routes through `rules/authority-inquiry.md`; every destructive GitHub-side step clears a per-action confirmation per `rules/interactive-questions.md` §6 before acting. |
| **M2 — Plain-language / Disclosure** | Removed process-narration (backward, placeholder, refinement, fix, modification references) is replaced with current-product voice per `rules/plain-language.md`; every removal is recorded in the disclosure ledger per `rules/disclosure-ledger.md`. |
| **M1 — Host Agnosticism (inherited core)** | The agnostic freshening core is inherited from `/freshify`, which discovers every host surface per `rules/host-discovery.md`; this command adds only the GitHub-specific surface on top. |
| **M4 — Self-application** | The deployed tree, the `release: <repo-name> v0.1.0` commit, and the CHANGELOG pass the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` before the report is finalized. |

---

## Output

- The single templated `release: <repo-name> v0.1.0` commit pushed to `origin/main` (with sibling sub-package release lines for monorepos), every confirmation outcome recorded.
- One first-version GitHub Release tagged `v0.1.0` with its signed artifacts where signing is ratified.
- The curated concise first-version `CHANGELOG.md` entry per Keep-a-Changelog.
- The deployment report at the suite's `_outputs/github-deploy-fresh-report.md` (executive summary + inherited-`/freshify`-pass summary + GitHub-trace removal index + confirmation log + per-workflow green/score verdict + per-axis attestation + validation-gate attestation + bindings).
- An optional trace inventory at the suite's `_inputs/github-deploy-fresh-inventory.md` (the Input Ingest read inventory).

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Recommended Next Step

**Invoke `/github-deploy-next`** to deploy the subsequent release in turn — merging the next-cycle pull requests, resolving the next-cycle issues, and tagging the next version — once `/github-deploy-fresh` has landed the single fresh first-version release on `origin/main`.
