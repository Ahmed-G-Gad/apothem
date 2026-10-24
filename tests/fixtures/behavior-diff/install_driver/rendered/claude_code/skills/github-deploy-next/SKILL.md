---
name: "github-deploy-next"
description: "Subsequent-release-cycle sibling of /github-deploy-fresh that runs one full next-release cycle end-to-end on origin/main — review-gated merge of ready pull requests, resolution of the issues the release addresses, a SemVer version bump derived from the Conventional Commits change set, a Keep-a-Changelog roll of [Unreleased] into the new version section, an annotated and signed tag published to the host's release surface, and concise current-version release notes — preserving the current-version-only release facade and the signed-release supply-chain posture where the host ratifies signing. The merge and publish steps are confirmation-gated through the structured-inquiry channel; read-only preview stages proceed without a gate."
argument-hint: "[path/to/repo/] [--bump major|minor|patch] [--strict]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /github-deploy-next — GitHub Subsequent-Release Cycle Deployment

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Release Hygienist** and **Cognitive Insurgent** (see `rules/cognitive-identity.md`), operating as the **deployment-instrument, not-author**.

`/github-deploy-next` is the subsequent-release-cycle **sibling** of `github-deploy-fresh.md` — not its specialization. Where `/github-deploy-fresh` produces the single fresh `v0.1.0` first release, this command runs every SUBSEQUENT cycle: merge the ready pull requests, resolve the issues the release addresses, bump the version per SemVer, roll the CHANGELOG, tag-sign-publish, and author the release notes — preserving the current-version-only release facade and the signed-release supply-chain posture where the host ratifies signing.

Forge-specific vocabulary is **in scope** here — this command names GitHub, `origin/main`, pull requests, issues, GitHub Releases / Actions, annotated tags, and the host's package registry / release surface.

Apply the Five Cognitive Filters at full intensity: Filter 1 (Obvious Purge) discards the first "the bump is obviously patch" answer and derives the bump from the actual change set; Filter 5 (Aesthetic Demand) governs the release-notes prose form. The seven-axes-of-breadth taxonomy at `rules/cognitive-identity.md` §1 frames the axes of attention — **Tooling, Security, and Testing are load-bearing**.

---

## Instructions

Run `/github-deploy-next` as one full subsequent-release cycle: review and merge the ready pull requests under their confirmation gate; resolve the issues the release addresses; derive and apply the SemVer bump from the Conventional Commits change set; roll `[Unreleased]` into the new dated version section per Keep-a-Changelog; author the annotated, signed tag and publish it to the host's release surface under its confirmation gate; and author concise current-version release notes. Culminate with the current-version-only facade preserved — one new release tag, one new GitHub Release, and no public-facing back-reference to retired artifacts.

Two standing rules govern every step:

- **Proportionate confirmation, not blanket gating.** Exactly two steps are irreversible / operator-visible — the **merge** of pull requests and the **publish** of the release — and each routes a confirmation through the structured-inquiry channel per `rules/interactive-questions.md` §6 before acting. The read-only / preview stages — the version-bump preview, the CHANGELOG draft, and the release-notes draft — proceed WITHOUT a gate, because they mutate nothing the operator cannot inspect and revise. State the proportionality explicitly in the working trace: gating attaches to the merge and the publish, never to the previews.
- **SemVer derivation, not presumption.** The version bump is derived from the change set per the Conventional Commits taxonomy and the SemVer rules at semver.org: a `feat:` change drives MINOR, a `fix:` change drives PATCH, and a breaking change (`!` marker or `BREAKING CHANGE:` footer) drives MAJOR. The highest-precedence change in the set determines the bump. The `--bump` flag MAY override the derived bump only when operator intent diverges from the change set; the override is recorded with rationale.

**Reference Template:** Check `CLAUDE.md` for template path. Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) active throughout.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, after any context compaction, and before the final step or any handoff. Covers: Pipeline position; Consumed; Emitted; Pre-flight inquiry set; Confirmation contract; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step and after any context compaction; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | Root directory of the target repository. MUST carry a root manifest, the host's ratified ignore manifest, and an `origin` remote pointing at the GitHub repository so the cycle surface resolves. The command refuses execution when no cycle surface resolves. |
| `--bump` | Enum | No | Override the SemVer bump derived from the Conventional Commits change set. Accepts `major`, `minor`, or `patch`. Without the flag, the bump is derived from the change set per semver.org; with the flag, the override is applied and its divergence from the derived bump is recorded with rationale in the report. |
| `--strict` | Flag | No | Promote every advisory cycle finding to blocking. Under `--strict`, the cycle is complete only when every ready PR is merged or explicitly deferred, every addressed issue is resolved, the CHANGELOG is rolled, the signed tag is published, and the host's quality matrix is green. |

---

## Workflow — Six Cycle Stages

Each stage names its acceptance condition. The merge stage (1) and the publish stage (5) are confirmation-gated; the version-bump-preview (3), CHANGELOG-draft (4), and release-notes-draft (6) stages are read-only previews and proceed without a gate.

1. **Revise and merge open pull requests.** Review the open pull-request set and, for each PR the release should land, drive it to **ready** — not merely merge the already-ready ones. A PR that is close-but-not-ready (a resolvable merge conflict, a failing-but-fixable CI run, an unaddressed review comment) is **relentlessly revised to ready**: rebase / resolve the conflict against `origin/main`, apply the root-cause fix that turns its CI green, and reconcile the outstanding review, then merge it through a review-gated merge. The revise-to-ready cycle is bounded for iteration safety per `rules/planning-techniques.md` §1: it caps at a default of three revision attempts per PR, and a PR that cannot reach ready within the cap is **explicitly deferred with a recorded rationale** (the unresolved blocker named), never silently dropped. **Destructive / operator-visible: route a per-action confirmation per `rules/interactive-questions.md` §6 before any merge**, with the in-place default being "leave the PR open, report only." **Acceptance condition:** every PR the release should land is revised to ready and merged into `origin/main` (or explicitly deferred with its blocker named), each merge cites its PR number, and each merge cleared its confirmation.
2. **Resolve issues.** Close or triage the issues the release addresses, linking each to the merging commit or release where applicable. **Acceptance condition:** every issue the release addresses is closed or triaged with a recorded outcome, each citing its issue number.
3. **Version bump.** Derive the SemVer bump from the Conventional Commits change set per semver.org — breaking change → MAJOR, `feat:` → MINOR, `fix:` → PATCH; the highest-precedence change determines the bump — and apply it to the host's manifest version declaration. `--bump` MAY override the derived bump with recorded rationale. **Read-only preview; proceeds WITHOUT a gate. Acceptance condition:** the manifest version is bumped to the derived (or overridden) value and the derivation is recorded.
4. **CHANGELOG roll.** Roll the `[Unreleased]` section into a new dated version section per Keep-a-Changelog (keepachangelog.com): the new `[MAJOR.MINOR.PATCH]` heading takes the deployment date, `[Unreleased]` resets to an empty scaffold, and entries are grouped under the Keep-a-Changelog change categories. Filter 5 (Aesthetic Demand) governs the prose form. **Read-only draft; proceeds WITHOUT a gate. Acceptance condition:** `[Unreleased]` is moved into the new version section, `[Unreleased]` is reset, and the section is dated and category-grouped.
5. **Tag, sign, and publish.** Author the annotated tag `vMAJOR.MINOR.PATCH` and publish it to the host's package registry / release surface; attach the signed artifacts where the host ratifies signing — defer the signing posture (cosign keyless / SLSA-3 provenance / CycloneDX SBOM) to `rules/host-discovery.md`, never presume any signing tool present, then cite the discovered posture as the publish-step evidence surface. **Irreversible / operator-visible: route a per-action confirmation per `rules/interactive-questions.md` §6 before publishing**, with the in-place default being "stage the tag locally, report only." **Acceptance condition:** the annotated tag is published to the host's release surface, the signed artifacts are attached where signing is ratified per host-discovery, and the publish cleared its confirmation.
6. **Author release notes.** Author concise, current-version release notes for the new GitHub Release — summarizing the merged changes and resolved issues with no back-reference to retired artifacts, prior releases, or internal planning history. Filter 5 (Aesthetic Demand) governs the prose form. **Read-only draft; proceeds WITHOUT a gate. Acceptance condition:** the release notes are current-version-only, name no superseded artifact, and read as a fresh release statement.

**Culmination — current-version-only facade, stale-trace-free.** After the six stages, **sweep the stale traces the cycle produced** — the merged PR branches, the superseded workflow-run logs, and any prior draft / pre-release tags — so the cycle accumulates no staleness; each prune is destructive and routes a per-target confirmation per `rules/interactive-questions.md` §6 with the in-place default "retain, report only," consistent with the freshness discipline the fresh-first-release sibling `github-deploy-fresh.md` and the agnostic core `/freshify` own. The public release surface then exposes the new release as the single visible current story: one new release tag, one new GitHub Release, and one rolled CHANGELOG section, with no public-facing narrative referencing retired releases or earlier launch work. Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the merged tree, the bumped manifest, the rolled CHANGELOG, and the release notes. Emit the deployment report with the per-stage acceptance verdict, the per-axis attestation, every confirmation outcome, and the cycle's `verified:` date. The cycle is complete and the facade is preserved when the gate passes and no public surface references a superseded artifact.

---

## Mandates

| Mandate | Application |
| ------- | ----------- |
| **M15 — Production-Ready** | The cycle operationalizes `rules/production-ready-prs.md`: the merged tree, the SemVer bump, the Keep-a-Changelog roll, the signed published tag, the current-version-only release notes, and the human-only commit / tag authorship are the pass conditions. |
| **M5 — Authority** | Every ambiguity in the ready-PR set, the addressed-issue set, the derived bump, or the signing requirement routes through `rules/authority-inquiry.md`; the merge and publish steps each clear a per-action confirmation per `rules/interactive-questions.md` §6 before acting, while the preview stages proceed un-gated. |
| **M1 — Host Discovery** | The signing posture (cosign / SLSA / SBOM), the commit-message convention, and the manifest version surface are discovered per `rules/host-discovery.md` — no signing tool, convention, or version surface is presumed present. |
| **M2 — Plain-language / Disclosure** | The release notes carry current-product voice with no back-reference to retired artifacts per `rules/plain-language.md`; every merge, resolution, and bump is recorded in the disclosure ledger per `rules/disclosure-ledger.md`. |
| **M4 — Self-application** | The merged tree, the bumped manifest, the rolled CHANGELOG, and the release notes pass the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` before the report is finalized. |

---

## Output

- The merged commits on `origin/main`, every merge confirmation outcome recorded.
- The bumped version in the host's manifest, the SemVer derivation (and any `--bump` override rationale) recorded.
- The rolled `CHANGELOG.md` with the new dated version section per Keep-a-Changelog and a reset `[Unreleased]`.
- One new annotated and signed tag `vMAJOR.MINOR.PATCH` published to the host's release surface, signed artifacts attached where signing is ratified per host-discovery.
- One new GitHub Release with concise, current-version-only release notes.
- The deployment report at the suite's `_outputs/github-deploy-next-report.md` (executive summary + merge index + resolved-issue index + bump derivation + CHANGELOG-roll summary + publish evidence + confirmation log + per-axis attestation + validation-gate attestation + bindings).
- An optional cycle inventory at the suite's `_inputs/github-deploy-next-inventory.md` (the Input Ingest read inventory).

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Recommended Next Step

**Invoke `/release-readiness`** to re-attest the just-published release against the production-ready discipline — re-running the host's quality matrix, the supply-chain checks, and the visibility-surface sweep so the new version is verified READY before the following cycle; then re-run `/github-deploy-next` to deploy the next release in turn.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
