---
name: "production-ready-prs-surfaces"
description: "Path-filtered companion to `rules/production-ready-prs.md` carrying the operational depth of M15: the seven visibility surfaces, the supply-chain posture catalog, the release-engineering invariants, the commit-message convention (with the human-only authorship clause), the CI-green discipline, and the modern-project-surface specification. Demand-loaded when the assistant edits any visibility-surface artifact (README / CHANGELOG / CONTRIBUTING / LICENSE / SECURITY / `.github/**` / install / update / uninstall scripts)."
pathFilter: "**/README.md, **/CHANGELOG.md, **/CONTRIBUTING.md, **/LICENSE, **/.github/**, **/install.*, **/update.*, **/uninstall.*, **/CODEOWNERS, **/SECURITY.md, **/SUPPORT.md"
alwaysApply: false
paths:
  - "**/README.md"
  - "**/CHANGELOG.md"
  - "**/CONTRIBUTING.md"
  - "**/LICENSE"
  - "**/.github/**"
  - "**/install.*"
  - "**/update.*"
  - "**/uninstall.*"
  - "**/CODEOWNERS"
  - "**/SECURITY.md"
  - "**/SUPPORT.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Production-Ready Visibility Surfaces & Modern Project Surface (Companion Sub-Rule)

## Purpose

Specify the catalog surfaces and the modern-project-surface specification that the parent rule `rules/production-ready-prs.md` cites at its anchor lines. This companion is path-filtered: it loads when the assistant edits any of the visibility-surface artifact classes (README, CHANGELOG, CONTRIBUTING, LICENSE, SECURITY, SUPPORT, CODEOWNERS, `.github/**`, install / update / uninstall scripts). The parent rule remains the canonical home for the same-change-set discipline (§1), the gap-surfacing summary (§5), and the disclosure-surface / failure-tells / bindings; this companion carries the moved sections (§2, §3, §4, §6, §7, §8.1–§8.7).

## Obligations

### 1. The Seven Visibility Surfaces

The seven visibility surfaces of a production-ready artifact set, applied to the host project:

| Surface | Question the surface answers | Where it lives in the host |
|---|---|---|
| **What-is-this** | What does this project do, in one sentence I can read on landing? | `README.md` opening paragraph; `pyproject.toml` `description` field; documentation site landing page |
| **How-to-install / use** | How do I install / get started / run my first example? | `README.md` Quick Start section; `INSTALL.md`; documentation site Installation page |
| **Is-it-alive** | Is this project actively developed? Is the build passing? | CI status badges in `README.md`; recent commits in git log; CHANGELOG `[Unreleased]` section freshness |
| **Is-it-safe** | What's the license? Is there a security policy? What versions are supported? | `LICENSE` file; `SECURITY.md`; `SUPPORT.md`; supported-versions table in README |
| **How-to-contribute** | How do I report a bug, propose a feature, submit a PR? | `CONTRIBUTING.md`; `CODE_OF_CONDUCT.md`; issue templates at `.github/ISSUE_TEMPLATE/`; PR template at `.github/pull_request_template.md` |
| **Can-I-trust** | License clear? CHANGELOG maintained? Release signing ratified? CI green? Tests exist? | All-of-above must align: LICENSE present, CHANGELOG up-to-date, release signing where required, CI green, test coverage above the host's ratified threshold |
| **What-changed-and-when** | What changed in this version? When? Why? | `CHANGELOG.md`; release notes at the host's release surface; clean git history |

Where the host already operates these surfaces, the agent honors them — every change keeps them current. Where the host lacks a surface, the agent **MUST NOT unilaterally install** it: surface the gap as a finding per `rules/authority-inquiry.md` with the recommended option per `rules/option-annotation.md`.

### 2. Supply-Chain Posture Preservation (M13.8 reinforced)

Every change MUST preserve the host's supply-chain posture:

- **No new unpinned dependency.** New production dependencies are pinned per the host's ratified policy (`==X.Y.Z` for Python production; `^X.Y.Z` for libraries; equivalent elsewhere). Library projects MAY use ranges in `pyproject.toml` per host convention; production projects pin.
- **No secret literal.** No API key, token, password, private key, or certificate committed to source — and, at the done boundary, none present anywhere in the working tree, whether staged, unstaged, or untracked (a leaked `.env` never committed still fails the gate). The done-state is a clean tree, not merely a clean commit. The `secret-leak-grep` matcher at `conformity/secret_leak_grep.py` operationalizes the check.
- **No permission escalation.** CI workflow permission scopes MUST NOT widen without explicit justification; existing minimum-scope `permissions:` blocks are preserved.
- **Pinned actions.** GitHub Actions `uses:` references are pinned to commit SHAs (with version-tag comments) per the host's ratified policy. The `unpinned-action-grep` matcher at `conformity/unpinned_action_grep.py` operationalizes the check.
- **No unsigned release artifact** where the host's release policy requires signing (Sigstore cosign, GPG, SLSA provenance).

### 3. Release-Engineering Invariants

- **Versioning scheme honored.** The host's ratified scheme (semver, calver, custom) is preserved across every change. Breaking changes increment MAJOR (semver) or signal incompatibility per the host's convention.
- **Tag-to-version consistency.** Git tags MUST match the version declared in the host's manifest (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod` module-major-version suffix). A tag with no matching manifest version-bump is a violation.
- **Tag signing where ratified.** When the host's release policy requires GPG-signed tags, the tag is signed.
- **Current-version public facade.** Release-facing repositories expose the current version as the single visible public story: one current release tag, one release entry, one package per registry surface, current deployment records, and no public narrative referencing superseded release work or internal planning history. Publication follows green local validation and release-readiness workflows.

### 4. Commit-Message Discipline

Every commit message honors the host's ratified convention, discovered per `rules/host-discovery.md`:

- **Conventional Commits.** When sibling commits use `<type>(<scope>): <summary>` with types from `{feat, fix, chore, docs, refactor, test, perf, ci, build, style, revert}`, the new commit follows the same shape.
- **Host-specific format.** When `CONTRIBUTING.md` documents a project convention (e.g., `[CATEGORY] <summary>`, ticket-prefix `JIRA-1234: <summary>`), the new commit follows it.
- **Subject line length.** Under the host's ratified limit (commonly 50 / 72 / 80 chars per `.gitmessage` template or sibling commits).
- **Body discipline.** The body explains the **why**, not just the **what**, wraps at the host's ratified column (commonly 72 / 80), and references issue trackers per the host's pattern.
- **Co-author attribution.** A `Co-Authored-By:` trailer is added only when the change is genuinely co-authored by **another human contributor**, per the host's pattern.
- **Human-only authorship.** Every authorship surface of every git artifact — commit subject, commit body, `Author:` field, `Co-Authored-By:` trailer, `Signed-off-by:` trailer, branch name, tag name, tag annotation, stash name, git-notes body, PR title, PR description — names **human contributors only**. The agent **MUST NOT** add itself, the underlying language model, the runtime / harness / IDE / extension / vendor, or any other automated tool to any of those surfaces. Forbidden patterns include but are not limited to: `Co-Authored-By: Claude …`, `Co-Authored-By: GPT …`, `Co-Authored-By: Copilot …`, `Co-Authored-By: Cursor …`, `Co-Authored-By: <any-LLM-name> …`, `Co-Authored-By: <noreply@*-vendor.com>`, body narrative like "generated with X" / "co-authored by an AI" / "with assistance from `<agent>`" / "🤖 Generated with …", and any subject-line marker signalling agent authorship. **Why.** Co-authorship trailers carry legal and audit weight — joint authorship for licensing, code-review attribution, contribution metrics, downstream provenance, supply-chain attestation. Naming a non-human misrepresents the authorship graph, pollutes contributor analytics, and creates ambiguity in licensing-derived works. The sole authorship git resolves at commit time is the operator's own identity; the agent is the instrument the operator wields, not a co-author of record. A change-set that seems to need non-human attribution is a process failure resolved out-of-band (release notes, project docs, the PR description's tooling section), never inside git authorship metadata.

**Version-Control Safety.** Beyond message shape, the change-set's version-control mechanics bind: a change-set **MUST** default to a dedicated branch, never landing directly on `main` or a shared branch; it **MUST** be broken into small atomic commits grouped by intent — one concern per commit, so granularity holds as strictly as message form; shared / published history is **never** rewritten proactively; and provenance — the true-authorship trail and the commit lineage — is preserved. The force-push deny-floor tokens (`git push --force*`) enforce the no-proactive-rewrite clause mechanically; this sub-clause does not restate their deny home. `rules/refactoring-discipline.md` §2 is the refactor analogue — a refactor is worked in its own isolated workspace under the same one-concern-per-unit discipline.

### 5. CI-Green Discipline

The change-set MUST be **CI-green** before the change is complete:

- **Lint / format / type-check / test** — the host's full quality matrix passes. The lint / type-check branch is done under one of two states and no third: either the quality matrix is green with zero residual findings, **or** every residual lint / type-check warning carries a documented reason recorded in the session's verification attestation (per `rules/session-closure.md`) — an undocumented residual warning is a violation. Lint findings are not deferred; test failures are not skipped absent an explicit `@pytest.mark.skip` / equivalent annotation citing the reason.
- **Coverage** — where the host enforces a threshold, the change-set holds coverage at or above it.
- **Security scans** — CodeQL, Bandit, Trivy, gitleaks (where configured) report no new HIGH-severity findings.
- **Build** — the host's build artifact (sdist + wheel for Python; `npm pack` for Node; `cargo build` for Rust) succeeds.
- **Documentation build** — a Fumadocs / Docusaurus / Sphinx / equivalent docs build (where present) is clean.

A CI failure is **diagnosed and fixed in the same change-set**, never deferred. Marking a CI failure flaky without diagnosis is itself a finding.

### 6. Modern Project Surface

Every host project — and apothem itself, by self-application — ships a **modern project surface** that any operator can install, update, and uninstall in seconds without reading the source. It has six required components.

#### 6.1 Multi-OS Install Scripts

Paired install scripts at the repository root, one per supported shell family:

| Script | Hosts | Run-from-network form |
|---|---|---|
| `scripts/installer/install.sh` | macOS, Linux, WSL2, BSD, Termux, ChromeOS Linux container | `curl -fsSL <raw>/install.sh \| bash` |
| `scripts/installer/install.ps1` | Windows PowerShell 5.1+, PowerShell 7+ on any platform | `irm <raw>/install.ps1 \| iex` |

Both scripts MUST be **idempotent** (re-running on an existing checkout fast-forwards rather than failing or duplicating), **prerequisite-checked** (refuse to run when required tooling is missing), and **environment-configurable** (install destination, remote URL, target ref, skip flags). Each emits a clear next-steps banner on success. A project targeting one shell family declares the limitation explicitly in its README; silent omission is non-conformant.

#### 6.2 Multi-OS Update / Auto-Update Path

Every host project supports update via at least one of three paths: idempotent re-run of the install script; a dedicated `scripts/installer/update.sh` + `scripts/installer/update.ps1` pair; or an auto-update tool (CLI or scheduled task) that reports upstream commits and optionally fast-forwards.

The auto-update tool MUST be **read-only by default** — a single invocation MUST NOT mutate the working tree without an explicit `--apply` / `-Apply` flag. A silently-mutating integration is non-conformant per M5 authority-inquiry: a silent fast-forward is silent override of the operator's working state.

#### 6.3 Multi-OS Uninstall Path

Paired uninstall scripts at the repository root: `scripts/installer/uninstall.sh` and `scripts/installer/uninstall.ps1`. Each script MUST:

- **Confirm with the operator** before any destructive action (interactive prompt unless `--yes` / `-Yes`).
- **Preserve operator state** — back up targets before removal, or delegate to a CLI that already backs up managed replacements; permanent deletion requires an explicit documented path.
- **Refuse unsafe targets** (`$HOME`, `/`, an empty path, a directory failing the project's sentinel-file check).
- **Clean up companion install state** (editable Python install, shell-profile environment-variable references) per the host's ratified install footprint.

#### 6.4 Logo Asset

Every host project ships a logo at the canonical location `assets/logo.svg`:

- **SVG-first** (scalable, version-controllable, themable). A raster fallback at `assets/logo.png` (256×256) is acceptable; SVG is preferred.
- **Wired into the README header** via a centered `<p align="center"><img src="assets/logo.svg" ...></p>` block as the first content element.
- **Wired into the documentation site** via the host docs framework's logo hook.
- **Accessible** — the `<img>` carries an `alt` attribute; the SVG carries `<title>` and `<desc>` elements.

A project that has not yet authored a logo declares the absence in its README rather than leaving the header silent; the absence is a gap-surfacing per the parent rule's §5.

#### 6.5 Modern README Header — MAXIMAL Pattern

Every host project's `README.md` opens with the **MAXIMAL centered-header pattern** per `rules/sota-elevation.md` (the SOTA floor for OSS distribution projects):

1. **Centered logo** per §6.4 — `<p align="center"><img src="assets/logo.svg" ...></p>` as the first content element.
2. **Centered project title** — `<h1 align="center">`.
3. **Centered one-sentence tagline** — `<p align="center"><em>`.
4. **Centered badge row** covering the **closed-set of 8 header-link classes**:
   1. **Build** — CI status (e.g., GitHub Actions build badge per workflow).
   2. **License** — SPDX-form license badge (MIT / Apache-2.0 / etc.).
   3. **Version** — npm / crates.io / equivalent registry version badge, dynamic per `rules/dynamism.md`.
   4. **Coverage** — Codecov / Coveralls / equivalent line+branch threshold badge (≥ 80% where the host has ratified a threshold).
   5. **OSSF Scorecard** — Scorecard.dev badge for supply-chain posture.
   6. **Community** — Discord / Slack / chat-channel badge linking the live community.
   7. **Docs** — documentation-site link badge (Read the Docs / Fumadocs / equivalent).
   8. **Downloads** — npm / crates.io downloads-per-month badge (dynamic per `rules/dynamism.md`).
5. **Centered nav strip** linking to `Install` / `Quick tour` / `Documentation` / `Changelog` / `Contributing` (and optionally `Community` / `Sponsors`).
6. **Horizontal rule** separating the header from the body.

**Rich-content surface (also MAXIMAL).** Following the header, the README MUST carry:

- **Animated demo or feature screenshot** near the top — a short GIF / SVG / WebP showing the core value-proposition in under 10 seconds, positioned immediately after the horizontal rule.
- **Feature matrix** — a compact table of primary capabilities surfacing SOTA differentiators relative to the named-exemplar cohort at `rules/sota-elevation-exemplars.md` §2.
- **Quick Start ≤ 3 commands** — install / configure / first-run as three shell lines or fewer; operators MUST reach a working first run without scrolling past Quick Start.
- **Dedicated sections** — `## Install` (with the §6.6 sub-paths) + `## Updating` + `## Uninstalling` + (where applicable) `## Auto-update`, each carrying concrete invocations.
- **Community + Support** at the tail — community-channel link + sponsorship / funding (where a `.github/FUNDING.yml` exists) + Showcase / Users + Blog / RSS.

The centering uses inline HTML inside Markdown — the GitHub-rendered conventional pattern, not a custom convention. A project shipping below this MAXIMAL floor is non-conformant against M15 + `rules/sota-elevation.md`; the gap surfaces as a finding per §5.

#### 6.6 Installation Guide

Every README carries an `## Install` section with at least three sub-paths: a **one-shot installer** (the curl / iwr-piped command for both shell families, in a two-row table), a **manual install** (`git clone` + dependency-install + verification, for operators who decline pipe-to-shell), and a **verify the install** sub-path (the post-install verification commands). Plus `## Updating`, `## Uninstalling`, and (where applicable) `## Auto-update` subsections with concrete invocations.

#### 6.7 Self-Application Surface

Apothem itself ships every component above: `scripts/installer/install.{sh,ps1}` + `scripts/installer/update.{sh,ps1}` + `scripts/installer/uninstall.{sh,ps1}`, `scripts/dev/auto_update.py` (read-only check; `--apply` to fast-forward), `assets/logo.svg` (hexagonal three-layer architecture mark), and the README's modern header + Install / Updating / Uninstalling / Auto-update sections.

## Enforcement

Path-filtered (the eleven glob patterns in this rule's `pathFilter` field), demand-loaded companion to `rules/production-ready-prs.md`. The parent rule retains the same-change-set discipline (§1), the gap-surfacing summary (§5), the disclosure surface, the failure tells, and the bindings; this companion carries the visibility-surface catalog, the supply-chain table, the release-engineering invariants, the commit-message convention detail, the CI-green catalog, and the modern-project-surface specification. Together the parent and companion constitute the canonical specification for **M15 — Production-Ready Discipline on Host-Project Artifacts**.

## Bindings (§0.j five-direction)

- **Drives →** ● Every visibility-surface artifact emission across every host project (README / CHANGELOG / CONTRIBUTING / LICENSE / SECURITY / SUPPORT / CODEOWNERS / `.github/**` / install / update / uninstall scripts). ● The seven visibility surfaces' continuous maintenance across the host's lifecycle. ● The modern-project-surface ratifications at every install / update / uninstall / logo / README-header touch. ● The commit-message human-only-authorship clause at every git-write touch.
- **Satisfies →** ● the fifteen-mandate registry row **M15 — Production-Ready** (companion sub-rule scope). ● `rules/production-ready-prs.md` anchor lines pointing here for the moved sections.
- **Established by ↑** ● `rules/production-ready-prs.md` (parent-rule anchor). ● the fifteen-mandate registry (ratifies M15). ● Keep-a-Changelog convention (the upstream changelog standard). ● Conventional Commits specification (the upstream commit-message convention).
- **Gated by ←** ● The path-filter (the eleven glob patterns) — this rule demand-loads only on visibility-surface artifact touches. ● `rules/production-ready-prs.md` always-on baseline (parent rule's anchor lines must be live for the companion to demand-load coherently).
- **Cross-bound with ↔** ↔ `rules/production-ready-prs.md` (parent rule; anchor lines bind this companion). ↔ `rules/authority-inquiry.md` (M5 — visibility-gap inquiries route through the canonical channel). ↔ `rules/option-annotation.md` (M7 — every visibility-gap inquiry's option set carries the Recommended marker plus concrete-driver rationale). ↔ `rules/host-discovery.md` (M1 — commit-message convention, action-pinning policy, release-signing requirement all discovered). ↔ `rules/disclosure-ledger.md` (M2 — production-ready outcomes recorded in the ledger). ↔ `rules/sota-elevation.md` (production-ready surfaces are the floor; SOTA lifts the ceiling on those same surfaces). ↔ `rules/session-closure.md` (§5 — a documented residual lint / type-check warning is recorded in the session's verification attestation). ↔ `rules/living-docs.md` (§6.6 carries the mechanical README structure for the newcomer-self-sufficiency limb of §5's two-reader-class definition of done). ↔ `rules/sota-elevation-exemplars.md` (§6.5 modern-README escalation cites the parent; this companion's surface 1 + surface 2 materialise the SOTA tier above the production-ready floor).
