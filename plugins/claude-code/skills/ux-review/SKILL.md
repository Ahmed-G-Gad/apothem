---
name: "ux-review"
description: "Reviews a repository's developer experience from a first-time user's view: CLI ergonomics, error messages, install flow and docs discoverability. Use when the user asks to 'review the CLI UX', 'audit the install flow' or 'is this easy to adopt'. Read-only. Screens: design-critic."
argument-hint: "[path/to/repo/] [--focus SURFACE] [--dry-run]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-24"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /ux-review — Developer-Experience Review (CLI · Install · Docs · Errors)

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Senior Developer-Experience Engineer** and **Cognitive Insurgent** (`rules/cognitive-identity.md`), operating from the **first-time-operator posture**. Read every surface — CLI invocation, install transcript, README header, error message, progress indicator, documentation nav — as the operator's *first encounter* with the repository. The maintainer's familiarity is the enemy of clarity: what reads as obvious to the author is opaque to the operator landing cold.

Apply the Five Cognitive Filters at full intensity. Filter 1 (Obvious Purge) and Filter 5 (Aesthetic Demand) are non-negotiable; Filters 2–4 fire on every non-trivial usability decision per the rule's §2 non-trivial heuristic.

---

## Instructions

Execute `/ux-review`: ingest the deployed repository (the operator-facing artifact set — installed binaries, install scripts, documentation site, CLI surface), apply four review phases, and emit a severity-ranked findings ledger at the consuming suite's `_inputs/ux-review-findings.md` ready for audit-fortress consumption.

**Reference frame.** clig.dev (Command Line Interface Guidelines) is the canonical CLI-ergonomics rulebook; the Nielsen Norman Group ten usability heuristics govern documentation discoverability and error-recovery affordances; the GNU coreutils convention manual governs argument naming, short/long flag parity, and standard-stream discipline. Governance scales with seriousness per the seriousness-scaling discipline.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, after any context compaction, and before the final step or any handoff. Covers: Pipeline position; Audit-fortress sequence; Handoff Manifest; Pre-flight inquiry; Pre-emission gate; Inquiry Cadence (D4); Question-fatigue-optimization is FORBIDDEN.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step and after any context compaction; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | Root of the deployed host repository. MUST contain at minimum a README, install/update/uninstall scripts per `rules/production-ready-prs-surfaces.md` §6.1–§6.3, and either an installed CLI binary on PATH or a CLI entry-point declared in the project manifest. |
| `--focus SURFACE` | Enum | No | Restrict the review to one surface from `{cli, install, docs, errors, all}`. Default `all`. Useful for a targeted re-run after a prior cycle resolved findings on some surfaces. |
| `--dry-run` | Flag | No | Enumerate the review surfaces the command would walk and the inferred severity buckets without committing the ledger. Reports the surface inventory, the deployed-binary presence check, and the SOTA reference frame the run would apply. |

---

## Workflow — Five Phases

### Phase 0 — Input Ingest

Read the deployed repository in full. Deploy a Research Team (CM-25A) — one agent per surface (CLI binary + `--help` transcripts, install/update/uninstall scripts, README + docs site, error-message corpus). Each agent returns a structured summary ≤ 500 tokens (CM-25C), required fields `status` · `surface-inventory` · `evidence-pointers` · `gaps`.

**Required reads.**

- **CLI surface.** The installed CLI binary; every subcommand's `--help` and `-h` output; the project manifest's entry-point declaration; sibling CLI tools the repository ships (auto-update, dev-loop helpers).
- **Installation surface.** `scripts/installer/{install,update,uninstall}.{sh,ps1}` at the repository root; any `CONTRIBUTING.md` install section; the README's `## Install` section per `rules/production-ready-prs-surfaces.md` §6.6.
- **Documentation surface.** The README header (logo, badges, nav strip); the documentation-site landing page (or docs source when no rendered site exists); TOC/sidebar; the search affordance; the supported-versions matrix; cross-references between pages.
- **Error-message corpus.** Every error message the CLI emits across the failure-mode catalog (invalid argument, missing prerequisite, network failure, permission denied, file-not-found, malformed input).

**Externalize the inventory** at `_inputs/ux-review-inventory.md` (free-form `{kebab-case-topic}.md` per `rules/context-management-scratch.md` §1).

### Phase 1 — CLI-Ergonomics Walk

Apply clig.dev and the GNU coreutils convention manual against the Phase 0 CLI surface:

- **Argument naming.** Short flags single-character, lowercase, conventional (`-h` help, `-v` verbose, `-f` force, `-o` output, `-q` quiet). Long flags kebab-case, descriptive, paired with short flags where the short flag exists. Boolean flags read as predicates (`--dry-run`, `--no-color`); valued flags carry their value separator (`--output=PATH` or `--output PATH` per the host's ratified style).
- **Help text.** Each `--help` opens with a one-line synopsis, then a one-paragraph description, then a flag table, then an examples block, then a `See also:` list. Help paginates past one terminal page. `-h` is a synonym for `--help`.
- **Error messages.** Errors land on stderr (not stdout); the exit code is non-zero and documented; the message names what failed, why, and what the operator can do next (NN/g heuristic 9 — error recognition and recovery). Stack traces are suppressed unless `--verbose`/`--debug`; the operator-facing form is one or two sentences with a remediation pointer.
- **Progress indicators.** Long-running operations (install, build, network sync) emit progress to stderr at a cadence matching duration — sub-second operations emit none, multi-second emit a spinner or bar, multi-minute emit elapsed-time + ETA.
- **Standard streams.** Result to stdout; diagnostics (errors, warnings, progress) to stderr; stdin read when designed to compose in pipelines. The exit code is the canonical success signal (0 success; non-zero failure with the failure class encoded per the host's exit-code catalog).
- **TTY-awareness.** Color enabled when stdout is a TTY and `NO_COLOR` is unset (per `https://no-color.org/`); disabled when output is redirected. Progress indicators degrade gracefully when stderr is not a TTY.

Externalize the CLI walk at `_inputs/ux-review-cli-walk.md`.

### Phase 2 — Installation-Flow + Error-Recovery Audit

Walk the installation flow as a first-time operator. For each install path at `rules/production-ready-prs-surfaces.md` §6.6 (one-shot installer, manual install, verify install), audit:

- **Prerequisite discovery.** Scripts fast-fail with a named missing prerequisite when the host lacks required tooling (git, Python, curl, PowerShell version). The error names the prerequisite, the installation pointer (vendor URL or package-manager invocation), and the re-run option.
- **Idempotency.** Re-running on an existing checkout fast-forwards rather than failing or duplicating per §6.1; the script reports what was found, updated, and skipped.
- **Environment-variable configurability.** Install destination, remote URL, target ref, skip flags configurable via env vars; the names and defaults documented in the script header comment and the README's `## Install` section.
- **Update path.** The auto-update tool is read-only by default per §6.2; a single invocation MUST NOT mutate the working tree without explicit `--apply`/`-Apply`. Surface silent mutation as a HIGH finding (M5 authority-inquiry).
- **Uninstall affordances.** The uninstall scripts confirm before destructive action; default to a timestamped backup; refuse unsafe targets (`$HOME`, `/`, empty path, sentinel-file fail). Surface missing confirmation as a HIGH finding.
- **Error-recovery affordances.** On mid-install failure, the script names what succeeded, what failed, and how to recover or retry (NN/g heuristic 9). Cryptic Bash/PowerShell tracebacks surface as MEDIUM findings.
- **Per-harness parity.** The POSIX `install.sh` and PowerShell `install.ps1` cover the same configuration surface, emit the same diagnostic vocabulary (the same error class → the same operator-facing form across harnesses), and reach the same post-install state. Per-harness divergence in flag names, env-var names, or post-install verification surfaces as HIGH per the systemic-participation convention-divergence class.

Externalize the install walk at `_inputs/ux-review-install-walk.md`.

### Phase 3 — Documentation-Discoverability Sweep

Apply the NN/g ten usability heuristics against the Phase 0 documentation surface:

1. **Visibility of system status** — the README header carries CI badges, version, and last-updated indicators per `rules/production-ready-prs-surfaces.md` §6.5.
2. **Match between system and real world** — vocabulary matches the operator's mental model (domain terms over implementation terms; concrete examples over abstract descriptions).
3. **User control and freedom** — every documented operation has its inverse documented (install→uninstall; enable→disable; create→delete).
4. **Consistency and standards** — sibling pages share heading hierarchy, code-block conventions, and cross-reference shape per `rules/code-craft-markdown.md` §8.
5. **Error prevention** — common pitfalls documented before they fire (the `## Install` section names the prerequisite-discovery failure mode; `## Updating` names the auto-update read-only-by-default contract).
6. **Recognition rather than recall** — navigation surfaces (TOC, sidebar, search) expose the full scope at every page; the operator does not memorize a path to the next page.
7. **Flexibility and efficiency of use** — quickstart paths coexist with deep-dive paths; expert operators reach the reference without traversing the tutorial.
8. **Aesthetic and minimalist design** — pages carry purpose-driven structure per `rules/code-craft-markdown.md` §1; filler/throat-clearing/restatement is absent.
9. **Help users recognize, diagnose, and recover from errors** — every documented error links to a recovery procedure; the error itself names the recovery path.
10. **Help and documentation** — a `## Troubleshooting` section (or equivalent) covers the failure-mode catalog; `CONTRIBUTING.md` and `SUPPORT.md` are present and current.

For each heuristic, record a verdict (PASS / FAIL / N/A-with-reason) and, on FAIL, the observed surface plus a severity classification. Externalize the docs sweep at `_inputs/ux-review-docs-sweep.md`.

### Phase 4 — Findings Emission + Validation Gate

Emit `_inputs/ux-review-findings.md` with canonical sections:

1. **`## §1 Executive Summary`** — the review's mission + review-surface inventory + finding count by severity (HIGH/MEDIUM/LOW).
2. **`## §2 Severity Classification Method`** — the three severity classes and the concrete-driver classes (`rules/interactive-questions-canonical-shapes.md` §3.2.1) grounding each: HIGH cites class 2 (named risk), 3 (named constraint), or 5 (rule citation against a binding rule); MEDIUM cites class 6 (observed state) measured against a convention; LOW cites class 6 against a recommendation rather than a binding.
3. **`## §3 CLI-Ergonomics Findings`** — per-finding entries from the Phase 1 walk.
4. **`## §4 Installation-Flow + Error-Recovery Findings`** — per-finding entries from the Phase 2 audit.
5. **`## §5 Documentation-Discoverability Findings`** — per-finding entries from the Phase 3 sweep, organized by heuristic.
6. **`## §6 Per-Harness Parity Findings`** — per-finding entries naming POSIX/PowerShell divergence.
7. **`## §7 Validation Gate Outcome`** — the fifteen-bar attestation block (`rules/pre-emission-gate.md` §2).
8. **`## §8 Bindings (§0.j five-direction)`** — the ledger's own outward bindings.

Each finding carries `**F-<N>** [SEVERITY] <one-line summary>` followed by Observed Surface (file path + line range or CLI invocation + transcript) + Reference Frame (clig.dev section / NN/g heuristic / GNU coreutils rule) + Concrete-Driver Rationale + Proposed Remediation.

Apply incremental generation (`rules/large-file-generation.md`) past 500 lines. Run the fifteen-bar pre-emission gate; iterate on failure per `rules/pre-emission-gate.md` §3.

---

## Critical Rules

- **NEVER fabricate observations** — every finding cites a concrete observed surface; surfaces not present in the deployed repository route to inquiry or surface as a `gaps` entry in the Phase 0 inventory.
- **NEVER mutate the host repository** — read-only review; the ledger is the sole emission.
- **NEVER classify a finding without a concrete-driver class** — classifications without a class 2/3/5/6 citation are non-conformant (`rules/interactive-questions-canonical-shapes.md` §3.2.1).
- **NEVER use a vague-rationale phrase as the sole severity justification** — the `rules/interactive-questions-canonical-shapes.md` §3.2.2 forbid list applies.
- **NEVER emit a ledger without the validation-gate attestation** — the Phase 4 gate is non-optional.
- **Per-file destructive-op floor.** Inapplicable — the command is read-only against the host repository.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Output

- The findings ledger at `_inputs/ux-review-findings.md` (executive summary + severity classification method + per-surface findings + per-harness parity findings + validation-gate attestation + bindings).
- The updated Handoff Manifest at `_inputs/handoff-manifest.yml` (findings-ledger path + finding counts by severity + gate attestation block).
- An optional input-inventory at `_inputs/ux-review-inventory.md` (Phase 0).
- Optional per-phase walk files at `_inputs/ux-review-{cli-walk,install-walk,docs-sweep}.md`.

---

## Recommended Next Step

Invoke `/a11y-audit` to advance the audit-fortress sequence — the canonical successor per the 11-command audit-fortress sequence.
