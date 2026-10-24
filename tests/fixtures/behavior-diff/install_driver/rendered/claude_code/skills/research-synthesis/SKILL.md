---
name: "research-synthesis"
description: "Reconciles collected sources into a state-of-the-art map, a literature matrix and a research-gap statement. Use when the user asks to 'map the SOTA', 'build the literature matrix' or 'state the research gap'. Needs a source ledger from research-sources; loose documents: source-synthesis."
argument-hint: "[--suite-name NAME] [--override] [--matrix-dimensions DIM,DIM,...]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-24"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /research-synthesis — SOTA Map & Gap Analysis

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the **Principal Investigator** conducting the literature-synthesis stage, operating as **Technical Co-Founder** and **Cognitive Insurgent** per `rules/cognitive-identity.md`. You do not summarize the source ledger. You **reconcile** the collected sources into one coherent state-of-the-art map, lay every source against shared comparison dimensions in a literature matrix, and state the explicit research gap — the hole the prior work leaves open. Apply the Five Cognitive Filters at full intensity:

- **Filter 1 (Obvious Purge)** discards the first framing so the map does not inherit the dominant narrative uncritically.
- **Filter 3 (Inversion Press)** surfaces the strongest counter-evidence against each synthesized claim before it earns its place.
- **Filter 5 (Aesthetic Demand)** governs the gap statement's precision.

> The synthesizer is an instrument, not an advocate — it separates consensus from contested ground and never collapses a real disagreement into a false consensus to make the gap look cleaner.

The stage runs as a single disciplined sprint: one authoritative synthesis artifact and one Handoff Manifest update. Route every load-bearing claim through `fact-checker` adversarial verification before it lands in the map; an unverified claim never anchors the gap statement.

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
| `--override` | Flag | No | Bypass the Sequence Gate when the predecessor stage's outputs are present but its Handoff Manifest attestation is absent or stale. The override is audited: it records a `[Gate — override: predecessor /research-sources; rationale: <operator-supplied>]` entry in the synthesis disclosure ledger. |
| `--matrix-dimensions <DIM,DIM,...>` | Flag + value | No | Comma-separated comparison dimensions for the literature matrix columns (e.g., `method,dataset,metric,assumption`). If omitted, Phase 2 derives candidate dimensions from the source claim-clusters and ratifies them through the structured-inquiry channel. |

---

## Sequence Gate

**Predecessor.** `/research-sources` (Stage 4). This stage requires the source corpus the discovery stage assembled.

**Precondition.** Both `{suite}/_inputs/source-ledger.md` and a non-empty `{suite}/sources/` directory exist, and the Handoff Manifest records `/research-sources` as the most recent stage with a clean attestation block.

**Gate-failure line.** When the precondition is unmet, halt and emit: `Blocked: run /research-sources first` — naming the missing artifact (empty ledger, absent `sources/`, or unsatisfied manifest attestation). Do not run synthesis against a partial corpus.

**Override path.** `--override` proceeds when the predecessor outputs are present but the manifest attestation is stale; the override records its rationale in the synthesis disclosure ledger per the `--override` input row above.

---

## Workflow — Five Phases

| Phase | Name | Step contract |
| ----- | ---- | ------------- |
| 1 | Ingest the Source Corpus | load-context |
| 2 | Build the Literature Matrix | execute |
| 3 | Adversarial Verification (refute-by-default) | verify |
| 4 | Synthesize the SOTA Map, Rate Certainty, Consolidate the Theory & State the Gap | execute |
| 5 | Validation Gate | gate + report |

### Phase 1 — Ingest the Source Corpus

> Moved to `references/step-01-ingest-the-source-corpus.md`. MUST read it in full before executing this step.

### Phase 2 — Build the Literature Matrix

Lay every source against shared comparison dimensions. When `--matrix-dimensions` is supplied, those are the columns; otherwise derive candidate dimensions from the Phase 1 claim-clusters (the recurring axes the sources address — method, dataset, metric, assumption, scope, limitation) and ratify the column set through the structured-inquiry channel per `rules/interactive-questions.md` §3. The matrix is a source-by-dimension table: each row is a source ID; each cell records that source's position on the dimension with its citation anchor; an empty cell is an explicit coverage gap, marked `—`, never silently elided (R1 comprehensiveness). The matrix is the structural surface the SOTA map and the gap statement both trace back to.

### Phase 3 — Adversarial Verification (refute-by-default)

Route every load-bearing claim destined for the SOTA map through `agents/fact-checker.md` adversarial verification. The fact-checker treats each claim as false until ≥2 independent sources force otherwise, seeks the strongest counter-evidence first (Filter 3 Inversion Press), and assigns a cited verdict per claim:

| Verdict | Condition | Destination |
| ------- | --------- | ----------- |
| `corroborated` | Two or more independent sources agree; no surviving counter-evidence. | Anchors the SOTA map. |
| `contested` | Sources disagree; both positions carry evidence. | Contested-findings ledger (both positions + evidence). |
| `unverified` | No independent corroboration. | Contested-findings ledger. |

A claim defaults to contested-or-unverified when evidence is insufficient, never a charitable `corroborated`. Only `corroborated` claims anchor the SOTA map (R1, R3). Dispatch the verification as an Audit Team per `rules/agent-orchestration.md` when the claim count justifies parallel fan-out (3+ independent claims); each agent returns a pass/fail verdict plus cited evidence under the 200-token audit return contract.

### Phase 4 — Synthesize the SOTA Map, Rate Certainty, Consolidate the Theory & State the Gap

> Moved to `references/step-04-synthesize-the-sota-map-rate-certainty.md`. MUST read it in full before executing this step.

### Phase 5 — Validation Gate

Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the emitted synthesis. M5 authority: zero fabricated citations; every map assertion and matrix cell cites a retrievable source ID (R4). M8 definitiveness: hedging vocabulary absent from the gap statement and map prose. M9 visual leverage: the literature matrix is a table, and any structural relationship the SOTA map reveals (a dependency, a research-lineage timeline, a contested-finding graph) carries a diagram with the metadata header per `rules/visual-leverage.md`. M14 systemicity: the synthesis declares its upstream (the source ledger + extractions), downstream (`/research-design`), peers (sibling research-suite artifacts), and enforcers (the `fact-checker` verification pass + the citation index). Iterate on failure per the gate rule's §3 until every bar passes or its three-round cap returns BLOCKED; record the attestation block inside the synthesis and update the Handoff Manifest.

---

## Mandates

| Discipline | Rule | Enforcement point |
| ---------- | ---- | ----------------- |
| Authoritative sources (R1) | `rules/ten-dimension-check.md` | Every map assertion cites a primary source by ledger ID; folklore excluded. |
| Falsifiability (R3) | `rules/definitiveness.md` | The gap statement is a testable, refutable claim; null findings recorded in the ledger. |
| Citation integrity (R4) | `rules/ten-dimension-check.md` | Every citation resolves to a real source ID (permalink/DOI/commit-pinned); Phase 5 M5 enforces zero phantom citations. |
| Authoritative inquiry | `rules/authority-inquiry.md` | Phase 1 blocks emission until matrix-dimension and gap-framing inquiries resolve. |
| Structured inquiry | `rules/interactive-questions.md` | Every contested-finding resolution and dimension ratification routes through the canonical channel; free-form prose questions forbidden. |
| Adversarial verification | `agents/fact-checker.md` | Phase 3 routes every load-bearing claim through refute-by-default verification before it anchors the map. |
| Agent orchestration | `rules/agent-orchestration.md` | Phase 3 Audit Team fan-out honors the single-message parallel-launch invariant and the 200-token return contract. |
| Reporting-guideline conformance (R9) | `rules/ten-dimension-check.md` | Phase 4 assigns a GRADE-style certainty rating per evidence body, carrying the source-ledger risk-of-bias judgments forward per the EQUATOR catalog. |
| Theoretical grounding (R10) | `rules/definitiveness.md` | Phase 4 consolidates the sources' theoretical frameworks into a single model the gap statement and proposal trace to; a contested construct is never collapsed into false consensus. |
| Cross-corpus coherence (R1, R3) | `skills/research-suite/references/advancement-gate.md` | Phase 4 reconciles the SOTA map, model, and gap against sibling corpora before finalization; a cross-corpus conflict routes to the contested-findings ledger and the gap resolves to a distinct, parsimonious contribution the downstream advance gate re-checks. |
| Pre-emission gate | `rules/pre-emission-gate.md` | Phase 5 runs all fifteen bars against the synthesis before the manifest update. |

R2 (reproducibility) is forward-declared here and operationalized at `/research-design`; R5 (preregistration), R6 (ethics), R7 (statistical rigor), and R8 (open-science / FAIR) bind the downstream design, experiment, and analysis stages.

---

## Output

| Artifact | Path | Purpose |
| -------- | ---- | ------- |
| Synthesis | `{suite}/_inputs/synthesis.md` | The promoted SOTA map + literature matrix + GRADE certainty ratings + consolidated theoretical model + contested-findings ledger + explicit gap statement, ready for `/research-proposal`. |
| Claim inventory | `{suite}/_inputs/synthesis-claims.md` | Optional Phase 1 working file (claim inventory keyed by source ID) for a corpus exceeding a single pass. |
| Handoff Manifest | `{suite}/_inputs/handoff-manifest.yml` | Updated at Phase 5 with `downstream: /research-proposal` and the per-claim verification attestation. |

The `synthesis.md` carries these canonical sections: `## §1 Scope & Corpus` (the research question recap, source count, claim count per verdict); `## §2 Literature Matrix` (the source-by-dimension table); `## §3 SOTA Map` (the current state-of-the-art along each dimension, every assertion cited with its GRADE-style certainty rating); `## §4 Certainty of Evidence` (the GRADE-style `high`/`moderate`/`low`/`very-low` rating per evidence body with its down-rating and up-rating rationale); `## §5 Consolidated Theoretical Model` (the reconciled constructs, their relationships, and framework boundaries the prior work converges on; R10); `## §6 Gap Statement` (the one-sentence explicit gap the study addresses, plus its derivation from the matrix coverage gaps, low-certainty regions, and the model's open relationships); `## §7 Contested-Findings Ledger` (every contested or unverified claim with both positions and their evidence, folding in the cross-corpus reconciliation outcome — a sibling-corpus terminology or finding conflict is recorded here as a contested finding carrying both positions); `## §8 Citation Index` (every source ID with permalink, author, access date); `## §9 Validation Gate Outcome` (the Phase 5 gate attestation); `## §Bindings (§0.j five-direction)`.

---

## Example — Standard synthesis run

> Moved to `references/examples.md`. SHOULD read it before composing the final output.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Critical Rules

- **NEVER run against a partial corpus.** The Sequence Gate halts with `Blocked: run /research-sources first` until the ledger and `sources/` are present and the predecessor attestation is clean (or `--override` is supplied with rationale).
- **NEVER anchor the SOTA map on an unverified claim.** Only `corroborated` claims earn a place in the map; `contested` and `unverified` claims route to the contested-findings ledger (R1, R3).
- **NEVER collapse a contested finding into a false consensus.** Both positions and their evidence land in the ledger; the synthesizer is an instrument, not an advocate.
- **NEVER fabricate a citation.** Every map assertion and matrix cell traces to a real source ID in the ledger (R4); empty matrix cells are marked `—`, never invented.
- **NEVER hedge the gap statement.** The gap is one definitive, testable sentence per `rules/definitiveness.md` — the prior work leaves X open, stated as a binding claim, never softened with hedging vocabulary.
- **NEVER finalize a SOTA-map, consolidated-model, or gap claim that conflicts with a sibling corpus without recording the conflict.** A terminology or finding conflict against a related sibling corpus lands in the contested-findings ledger with both positions and their evidence, never silently harmonized (R1).
- **NEVER state a gap whose contribution duplicates a corroborated claim or decomposes into overlapping, non-distinct elements.** The gap resolves to a distinct, parsimonious contribution the downstream advance gate re-checks per `skills/research-suite/references/advancement-gate.md`; a duplicate is re-framed, and a bundle whose parts collapse into one is stated as one (R3).
- **NEVER skip the validation gate.** All fifteen bars pass before the Handoff Manifest updates and `/research-design` may consume the synthesis.

---

## Recommended Next Step

Invoke `/research-proposal` to turn the SOTA map, the consolidated theoretical model, and the explicit gap statement into a fundable research proposal before the study is operationalized into a design; `/research-proposal` is the canonical pipeline successor that consumes `_inputs/synthesis.md` alongside the research spec.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
