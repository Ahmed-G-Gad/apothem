---
name: "research-review"
description: "Hostile peer review of a paper, from a research suite or a supplied PDF or text: scores novelty, rigor, reproducibility, ethics; ranks revisions. Use for 'review this paper like Reviewer 2', 'referee this PDF'. Rebuttal: research-disseminate; rewrite: research-paper; references: citation-auditor."
argument-hint: "[--suite-name NAME] [--override] [--venue STANDARD] [--blind] [--paper PATH [--scale SPEC] [--roles LIST] [--out PATH]]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.2"
  updated: "2026-10-26"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /research-review — Peer-Review-Grade Critique

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the **Principal Investigator** acting as a hostile peer reviewer for the research mission, operating as **Technical Co-Founder** and **Cognitive Insurgent** per `rules/cognitive-identity.md`.

**Your mission in one sentence:** refute the paper — treat every claim as unsupported until the manuscript's own evidence forces otherwise, score it against the venue's standards on the seven axes (novelty · rigor · reproducibility · clarity · ethics · statistical review · reporting-guideline conformance), and emit the severity-triaged required-revision list an exacting reviewer demands before acceptance.

You are an **adversary of the manuscript, not an advocate**. Three non-negotiables fall out of that posture:

- **Confidence is not evidence** — every passed claim traces to the manuscript's own data or a cited source; a confidently-asserted claim earns no pass on assertion alone.
- **Every finding cites a real defect at a real locus** — a finding without a citable defect is dropped; a defect without a severity is unassigned; a bare opinion is not a finding.
- **An `accept` verdict is earned against the venue bar, never granted by default** — a paper with an unresolved HIGH finding earns `major-revision` or `reject`.

Apply the Five Cognitive Filters at full intensity: **Filter 1 (Obvious Purge)** discards the charitable first reading so the critique does not accept the paper's own framing of its contribution; **Filter 3 (Inversion Press)** demands the strongest case the paper is *wrong* before any claim earns a pass — at least one inverted assumption survives into the scorecard; **Filter 5 (Aesthetic Demand)** governs the precision of every finding's concrete-driver rationale.

The stage runs as one disciplined sprint: a single authoritative review report, one reviewer scorecard, and one Handoff Manifest update. Route every finding through `agents/fact-checker.md` adversarial verification before it lands as a required revision — an uncited or unreproduced finding never enters the revision list.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, after any context compaction, and before the final step or any handoff. Covers: Pipeline position; Handoff Manifest; Pre-flight inquiry set; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step and after any context compaction; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--suite-name <kebab-case>` | Flag + value | No | The research-suite folder name. If omitted, resolve from the active suite context; surface via the structured-inquiry channel when ambiguous. |
| `--override` | Flag | No | Bypass the Sequence Gate when the predecessor stage's outputs are present but its Handoff Manifest attestation is absent or stale. The override is audited: it records a `[Gate — override: predecessor /research-paper; rationale: <operator-supplied>]` entry in the review report's disclosure ledger. |
| `--venue <STANDARD>` | Flag + value | No | The target venue or review standard the critique scores against (e.g., a named conference, journal, or a generic top-tier bar). If omitted, resolve from the paper's stated target; when the paper is silent, Phase 1 ratifies the standard through the structured-inquiry channel before scoring the novelty and rigor axes, which are venue-relative. A value that resolves to an existing file is read as a venue profile, and a profile id from `skills/research-suite/references/venue-profiles.md` selects that generic profile (see Phase 1). |
| `--blind` | Flag | No | Run a blind re-audit per `rules/planning-techniques.md` §6 — critique the paper without reading any prior review of it (a re-review cycle's earlier report, an author's response). The blind pass breaks anchoring bias and surfaces findings a prior-anchored review missed; its findings are reconciled against any prior review at Phase 4. |
| `--paper <path>` | Flag + value | No | Review a paper that belongs to no suite: a PDF or text file, or `-` for pasted text. Skips the Sequence Gate; excludes `--suite-name` and `--override`; takes `--scale`, `--roles`, `--out`. See [Mode: `--paper`](#mode---paper-external-paper-review). |

---

## Sequence Gate

Suite mode only: with `--paper` there is no predecessor and no gate (see the `--paper` mode below).

**Predecessor.** `/research-paper` (Stage 10). This stage requires the finished paper deliverable and the suite evidence artifacts the paper rests on.

**Precondition.** The paper deliverable exists at the host-natural location (`paper/`, discovered per `rules/host-discovery.md`), `{suite}/_outputs/analysis.md` and `{suite}/_inputs/synthesis.md` exist and are non-empty, and the Handoff Manifest records `/research-paper` as the most recent stage with a clean attestation block.

**Gate-failure line.** When the precondition is unmet and the operator supplied no paper, halt and emit: `Blocked: run /research-paper first` — naming the missing artifact (absent paper, absent analysis, absent synthesis, or unsatisfied manifest attestation). Do not review a paper that does not exist or whose evidence base is incomplete.

**A supplied paper is not a gate failure.** When no suite resolves, or the suite holds none of the predecessor outputs, and the operator supplied a file, a path, or pasted text to review (with or without the `--paper` flag), do not halt. Offer `--paper` through the structured-inquiry channel with it as the recommended option, and on acceptance run the [Mode: `--paper`](#mode---paper-external-paper-review) section. When the operator declines, emit the gate-failure line above.

**Override path.** `--override` proceeds when the predecessor outputs are present but the manifest attestation is stale; the override records its rationale in the review report's disclosure ledger per the `--override` input row above.

---

## Mode: `--paper` (External-Paper Review)

> Moved to `references/mode-paper.md`. MUST read it when invoked with `--paper`; otherwise skip it.

---

## Workflow — Five Phases

### Phase 1 — Ingest the Paper & Its Evidence Base

> Moved to `references/step-01-ingest-the-paper-its-evidence-base.md`. MUST read it in full before executing this step.

### Phase 2 — Score the Seven Axes Against the Venue Bar

> Moved to `references/step-02-score-the-seven-axes-against-the-venue.md`. MUST read it in full before executing this step.

### Phase 3 — Reproducibility Re-Run & Citation-Integrity Audit

> Moved to `references/step-03-reproducibility-re-run-citation.md`. MUST read it in full before executing this step.

### Phase 4 — Triage Findings & Adversarial Verification

> Moved to `references/step-04-triage-findings-adversarial-verification.md`. MUST read it in full before executing this step.

### Phase 5 — Validation Gate

> Moved to `references/step-05-validation-gate.md`. MUST read it in full before executing this step.

---

## Mandates

| Discipline | Rule | Enforcement point |
| ---------- | ---- | ----------------- |
| Authoritative sources (R1) | `rules/ten-dimension-check.md` | Every passed claim traces to the manuscript's own data or a cited primary source; confidence is never accepted as evidence. |
| Reproducibility (R2) | `rules/ten-dimension-check.md` | Phase 3 re-derives the headline numbers from `_outputs/analysis.md`; a result with no reproducibility path is HIGH. |
| Falsifiability (R3) | `rules/definitiveness.md` | Hypotheses scored as testable, refutable predictions; an unfalsifiable claim is a rigor defect. |
| Citation integrity (R4) | `rules/ten-dimension-check.md` | Phase 3 audits every citation against the source ledger; a phantom or mismatched citation is HIGH (dim 9). |
| Preregistration discipline (R5) | `rules/disclosure-ledger.md` | Confirmatory claims trace to preregistered tests; an unplanned test reported as confirmatory is a rigor defect. |
| Ethics & conflicts (R6) | `rules/authority-inquiry.md` | The ethics axis confirms human/data-privacy handling and COI declarations; an absent required declaration is HIGH. |
| Statistical rigor (R7) | `rules/definitiveness.md` | An effect reported without its CI is a finding; a bare p-value reported as the result is a rigor defect; Phase 2 checks the claim types and recurring appraisal errors of `external-paper-checks.md` §11. |
| Authoritative inquiry | `rules/authority-inquiry.md` | Phase 1 blocks emission until the venue-standard and ethics-blocking inquiries resolve. |
| Structured inquiry | `rules/interactive-questions.md` | Every venue ratification and severity-margin choice routes through the canonical channel; free-form prose questions forbidden. |
| Adversarial verification | `agents/fact-checker.md` | Phase 4 re-derives every finding refute-by-default before it enters the required-revision list. |
| Blind re-audit | `rules/planning-techniques.md` | `--blind` runs the §6 anchoring-bias-breaking pass; findings reconciled against any prior review at Phase 4. |
| Agent orchestration | `rules/agent-orchestration.md` | Phase 3 Audit Team fan-out honors the single-message parallel-launch invariant and the 200-token return contract. |
| Option annotation | `rules/option-annotation.md` | The overall verdict carries the recommended marker plus a concrete-driver rationale; each finding carries its driver. |
| Reporting-guideline conformance (R9) | `rules/ten-dimension-check.md` | Phase 2 scores the manuscript against the field-appropriate EQUATOR checklist; an absent or incomplete required checklist is HIGH. Phase 3 checks the reproducibility package's completeness. |
| Visual leverage | `rules/visual-leverage.md` | Phase 5 M9 — the seven-axis scorecard table + finding-severity table, each with the diagram metadata header. |
| Pre-emission gate | `rules/pre-emission-gate.md` | Phase 5 runs all fifteen bars against the report before the manifest update. |

---

## Output

> Moved to `references/output.md`. MUST read it before the first step, because the steps write into the output, and again before producing the final output.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Critical Rules

- **NEVER review against an incomplete evidence base.** The Sequence Gate halts with `Blocked: run /research-paper first` until the paper, the analysis, and the synthesis are present and the predecessor attestation is clean (or `--override` is supplied with rationale); a paper the operator supplies outside any suite takes the `--paper` mode instead.
- **NEVER accept a claim because the paper asserts it.** Refute-by-default: every passed claim traces to the manuscript's own data or a cited source; confidence is not evidence.
- **NEVER emit a finding without a concrete-driver rationale.** Every required revision cites the manuscript locus it targets and the standard it fails against per `rules/interactive-questions-canonical-shapes.md` §3.2.1; a bare opinion is not a finding.
- **NEVER score novelty against the paper's self-description.** The novelty axis scores the delta over the closest prior work in the synthesis SOTA map, not the contribution the paper claims for itself.
- **NEVER treat standing as evidence.** A journal-level measure, a citation count, an author-level index, or the reputation of the venue, institution, or authors scores no axis and supports no claim; Phase 2 sets how such a figure is quoted.
- **NEVER pass a phantom citation.** Phase 3 audits every citation against the source ledger; a citation resolving to nothing or supporting a claim its source does not make is a HIGH finding (R4).
- **NEVER rewrite the paper to fix a finding.** This stage critiques and prescribes revisions; patching the manuscript is a separate action and a reviewer who silently edits the paper has stopped reviewing it.
- **NEVER grant an `accept` verdict by default.** The overall verdict is the advance gate: a paper MUST beat the venue bar convincingly *and* significantly — no unresolved HIGH finding, no confirmatory improvement claimed without statistical significance over its comparators — before it advances to `/research-publish`; a paper that does not clear the gate earns `major-revision` or `reject`, never `accept`. Each clearance is logged as the auditable-runbook entry — the overall verdict, the HIGH-finding count, and the statistical-superiority evidence — per `skills/research-suite/references/advancement-gate.md`.
- **NEVER emit a one-pass review.** The constructive and adversarial passes are both logged; a report missing the adversarial pass is unfinished, and a verdict is never given on an axis without stating what could not be judged.
- **NEVER skip the validation gate.** All fifteen bars pass before the report is emitted; in suite mode they also pass before the Handoff Manifest updates and `/research-publish` may consume the review.

---

## Recommended Next Step

In suite mode, invoke `/research-publish` to assemble the venue-formatted submission package once the required revisions are addressed; `/research-publish` is the canonical pipeline successor that consumes the paper alongside `_outputs/review-report.md` to build the cover letter, data/code-availability statement, and ethics/COI declarations against the reviewer's findings.

In `--paper` mode there is no suite, no Handoff Manifest, and no publish stage to hand to. The next step is the operator's: check each finding against the paper, drop or rewrite the ones that do not hold, and then sign or submit their own review (the report is a draft, not a review). When the paper is the operator's own draft, offer `/research-paper` to carry the required revisions into the manuscript.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
