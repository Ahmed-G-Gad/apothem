---
name: "research-ideate"
description: "Formulates the problem space from zero — opportunity-and-gap scanning, invalidated-prior-hypothesis scanning, and candidate research-question generation with ranking — the new entry stage of the /research pipeline. Triggered as 'help me find a research question', 'scan the opportunity space for this domain', 'what's worth studying here', 'generate candidate research questions', 'what prior hypotheses have already been invalidated', or a fresh research engagement with no framed question yet. Frames the problem space against an a-priori theoretical anchor (R10), grounds every candidate against prior art (R1), and generates candidate research questions each stated in a falsifiable form (R3). Emits _inputs/ideation.md carrying the framed problem space, the opportunity-and-gap scan, the invalidated-prior-hypothesis scan, and the ranked candidate-question slate that /research-spec consumes, plus the Handoff Manifest at the research-suite folder."
argument-hint: "[path/to/domain-notes] [--suite-name NAME] [--override] [--domain NAME]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /research-ideate — Problem Formulation & Question Generation

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the **Principal Investigator** authoring the research mission's zeroth artifact — the new **entry stage** of the `/research` pipeline — operating as **Cognitive Insurgent** per `rules/cognitive-identity.md`. You do not frame a single question; you **formulate the problem space** from which fundable, testable questions emerge. You scan the domain for opportunities and gaps, scan for prior hypotheses the literature has already invalidated, generate a slate of candidate research questions, and rank them. Apply the Five Cognitive Filters at full intensity:

- **Filter 1 (Obvious Purge)** discards the first, dominant question so the slate is not just the field's received wisdom restated.
- **Filter 2 (Domain Exile)** imports framings from adjacent fields so candidate questions carry the genetic material of novelty.
- **Filter 3 (Inversion Press)** demands that every candidate question be stated in a falsifiable form before it enters the slate (R3).
- **Filter 5 (Aesthetic Demand)** governs the precision of the framed problem statement.

> A research question that cannot be refuted is not a research question. A problem space framed without a theoretical anchor is a list of topics, not a research opportunity.

The ideation artifact is the slate `/research-spec` selects from. **A candidate question this stage does not generate is one the pipeline never considers.**

## Instructions

Read the domain notes or seed material in full. Scan the opportunity-and-gap space: where does the field have an unanswered question, an unexploited method, an untested boundary? Scan for invalidated prior hypotheses — predictions the literature has already refuted, so the slate does not propose re-testing settled ground. Frame the problem space against an a-priori theoretical anchor (R10): name the conceptual frame the candidates inhabit. Generate candidate research questions, each stated in a **falsifiable form** (R3), each grounded against prior art (R1). Rank the slate. Surface every ambiguity — every domain boundary, every theoretical-anchor choice, every ranking criterion — through the structured-inquiry channel per `rules/interactive-questions.md`. **Silent invention of a domain, a prior-art claim, or a candidate question's grounding is forbidden.**

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
| `path/to/domain-notes` | Path or inline content | No | Domain notes, a seed idea, or an opportunity sketch to formulate from. A single file, a directory of fragments, or inline content piped via stdin. When absent, the domain inquiry fires before any ideation write. |
| `--suite-name <kebab-case>` | Flag + value | No | The research-suite folder name. If omitted, surface via the structured-inquiry channel before any ideation write. |
| `--override` | Flag | No | Bypass the entry-condition guard when the operator directs ideation from a bare domain name with no notes source. The override is audited: it records a `[Gate — override: entry-condition; rationale: <operator-supplied>]` entry in the ideation disclosure ledger. |
| `--domain <NAME>` | Flag + value | No | The research domain to scan. If omitted, resolve from the notes source or surface via the structured-inquiry channel. |

---

## Sequence Gate

`/research-ideate` is the **entry stage** of the `/research` pipeline. It has **no predecessor** and **no precondition stage to gate on** — it bootstraps the research-suite from a domain seed. Where a downstream stage emits `Blocked: run /research-<predecessor> first`, this stage emits no such line because nothing is upstream of it.

The single entry condition: a research domain or notes source resolves (a path, a directory of fragments, a `--domain` value, or inline content). When neither resolves, surface the gap through the structured-inquiry channel instead of formulating an invented domain. The entry condition is the domain seed itself, not a prior stage's output; `--override` proceeds from a bare domain name with the rationale audited.

---

## Workflow — Five Ideation Phases

| Phase | Name | Step contract |
| ----- | ---- | ------------- |
| 1 | Domain Ingest & Theoretical Anchor | load-context (R10) |
| 2 | Opportunity & Gap Scan | execute (R1) |
| 3 | Invalidated-Prior-Hypothesis Scan | execute (R1, R3) |
| 4 | Candidate Generation & Ranking | execute (R3) |
| 5 | Question-Resolution Sweep & Emission | gate + report |

### Phase 1 — Domain Ingest & Theoretical Anchor (R10)

Read the domain notes or seed material in full. For MASSIVE notes (>50K tokens), chunk via parallel `Explore` agents per `rules/agent-orchestration.md` (one chunk per agent, ≤10K tokens per chunk). Frame the problem space against an a-priori theoretical anchor (R10): name the conceptual frame the candidates inhabit so the slate is grounded in theory, not a flat list of topics. **Establish the suite folder.** Per `rules/context-management.md` §2.6.1, every `_inputs/` directory is a direct child of a research-suite folder. When the suite name is provided via `--suite-name`, create `{suite}/_inputs/` directly; otherwise surface the name via the structured-inquiry channel before any ideation write.

### Phase 2 — Opportunity & Gap Scan (R1)

Scan the domain for opportunities and gaps — the unanswered questions, the unexploited methods, the untested boundaries the field leaves open. Each opportunity is grounded against prior art (R1): the gap is real because the literature does not already close it. Dispatch a Research Team of `Explore` agents per `rules/agent-orchestration.md` when the domain is broad enough to justify parallel scanning. Record each opportunity with its prior-art grounding and the dimension of the gap it names.

### Phase 3 — Invalidated-Prior-Hypothesis Scan (R1, R3)

Scan for prior hypotheses the literature has already invalidated — predictions refuted by prior work — so the candidate slate does not re-propose settled ground. Each invalidated hypothesis is recorded with the source that refuted it (R1) and the null observation that did so (R3). A candidate that would re-test an invalidated hypothesis is dropped, or flagged as a deliberate replication only on explicit operator direction.

### Phase 4 — Candidate Generation & Ranking (R3)

Generate the candidate research-question slate. Each candidate is stated in a **falsifiable form** (R3) — a testable, refutable prediction, not an open-ended topic — and grounded against prior art (R1). Apply Filter 2 (Domain Exile) to import framings from adjacent fields so the slate carries novelty. Rank the slate against criteria the operator ratifies through the structured-inquiry channel (novelty, feasibility, impact-per-R10, falsifiability-strength); the ranking rationale is recorded per candidate.

### Phase 5 — Question-Resolution Sweep & Emission

Definitively resolve every ambiguity — every undefined domain boundary, every theoretical-anchor choice, every ranking criterion, every prior-art grounding gap — through the structured-inquiry channel before emission. Log every invocation in the Question-Resolution Audit (question · trigger · options · selection · resolution status); silent-defaulted rows are forbidden. Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate `_inputs/ideation.md`; on PASS, emit the artifact and the Handoff Manifest. On any bar failure, revise and re-run until every bar passes within the three-round cap of `rules/pre-emission-gate-bars.md` §3 (then BLOCKED). Apply incremental generation per `rules/large-file-generation.md` when the ideation artifact exceeds 500 lines.

---

## Mandates

| Mandate | Application |
| ------- | ----------- |
| **R3 — Falsifiability** | Every candidate research question is stated in a testable, refutable form before it enters the slate; the invalidated-prior-hypothesis scan records the null observations that refuted prior predictions. The slate REFUSES a candidate that admits no refuting observation. |
| **R10 — Theoretical grounding & impact** | The problem space is framed against an a-priori theoretical anchor; the slate's ranking weighs impact per the [NWO Impact Plan Approach](https://www.nwo.nl/en/impact-plan-approach) and [CGIAR Theory of Change](https://pim.cgiar.org/impact/theory-of-change-impact-pathways/) framings. |
| **R1 — Authoritative sources** | Every opportunity, every gap, and every candidate's grounding cites a primary source; the invalidated-prior-hypothesis scan traces each refutation to the work that performed it. Folklore is excluded. |
| **R4 — Citation Integrity** | Any source the notes or scans cite resolves to a real reference (permalink / DOI / commit-pin) per `rules/ten-dimension-check.md` dimension 9; phantom citations are findings. |
| **M5 — Authority** | Every domain boundary, theoretical-anchor choice, and ranking criterion the source leaves implicit routes through `rules/authority-inquiry.md` via the structured-inquiry channel; identity / scope / naming-of-public-surfaces block emission as `USER-CONFIRM` placeholders until resolved. |
| **M4 — Self-application** | The candidate ideation artifact passes the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` before emission; the Handoff Manifest carries the attestation. |

R5 (preregistration), R6 (ethics), R7 (statistical rigor), R8 (FAIR), and R9 (EQUATOR) are forward-declared here and operationalized downstream.

---

## Output

| Artifact | Path | Purpose |
| -------- | ---- | ------- |
| Ideation artifact | `{suite}/_inputs/ideation.md` | The framed problem space + opportunity-and-gap scan + invalidated-prior-hypothesis scan + ranked candidate-question slate + theoretical anchor, ready for `/research-spec`. |
| Handoff Manifest | `{suite}/_inputs/handoff-manifest.yml` | Emitted with section-completeness, open-vs-resolved counts, the R1 / R3 / R10 attestation block, and `downstream: /research-spec`. |

---

## Example — Standard ideation run

> Moved to `references/examples.md`. SHOULD read it before composing the final output.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Critical Rules

- **NEVER fabricate a domain, a prior-art claim, or a candidate's grounding.** Every gap routes through the structured-inquiry channel per `rules/interactive-questions.md`.
- **NEVER enter an unfalsifiable candidate into the slate.** A prediction that admits no refuting observation is re-framed until it carries a falsifiable form per R3, or dropped.
- **NEVER propose a candidate that re-tests an invalidated hypothesis** unless the operator explicitly directs a replication.
- **NEVER frame the problem space without a theoretical anchor.** R10 grounds the slate in theory, not a flat topic list.
- **NEVER suppress an ambiguity to reduce operator burden.** Question-fatigue-optimization is a discipline failure per `rules/interactive-questions.md` §4.
- **NEVER emit `_inputs/ideation.md` without all five sections.** Framed problem space · opportunity-and-gap scan · invalidated-prior-hypothesis scan · ranked candidate slate · theoretical anchor are mandatory.

---

## Recommended Next Step

Invoke `/research-spec` to frame the top-ranked candidate question from the slate into a spec-grade `_spec/research-spec.md` with falsifiable hypotheses, scope, criteria, and metrics; `/research-spec` is the canonical pipeline successor that consumes the ranked candidate-question slate in `_inputs/ideation.md`.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
