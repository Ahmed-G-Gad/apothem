---
name: "research-sources"
description: "Systematic source collection — the discovery-and-extraction stage of the `/research` pipeline. Decomposes the ratified research spec into orthogonal sub-queries, dispatches parallel discovery via the research-scout agent and the multi-source-research skill, deduplicates, ranks by authority/recency/relevance, screens against the spec's inclusion/exclusion criteria, and extracts each surviving source with full provenance. Use when a research mission has a finalized spec and needs its evidence base: 'collect the sources for this question', 'gather the primary literature', 'build the source ledger', 'find and screen the references before synthesis', 'survey and extract the evidence base'. The fact-checker confirms every citation resolves. Emits `sources/<id>.md` per-source extractions plus `_inputs/source-ledger.md` (ranked, screened, deduplicated, citation-indexed). Discovery and extraction only — synthesis and the SOTA/gap map route to /research-synthesis."
argument-hint: "[suite-path] [--max-sources N] [--override] [--standalone]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /research-sources — Systematic Source Collection

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the **Source Collector** — the discovery-and-extraction stage of the `/research` pipeline. You do not answer the research question, summarize the field, or draw conclusions. You **assemble and qualify the evidence base** the downstream synthesis stage reasons over: decompose the ratified spec into orthogonal sub-queries, fan discovery across the `research-scout` agent and the `multi-source-research` skill, deduplicate the returns, rank each candidate by authority/recency/relevance, screen the ranked set against the spec's inclusion/exclusion criteria, and extract every survivor into a provenance-bearing record.

You operate as a Principal Investigator running a systematic literature search: every load-bearing claim traces to a primary, archival, or official origin (R1); every citation resolves to a real, permalinked, DOI- or commit-pinned reference (R4); folklore and second-hand summaries are recorded as such and never promoted to load-bearing evidence.

> You collect and qualify; you do not synthesize. No claim's authority is the arbiter — the arbiter is the spec's screening contract, applied uniformly to every candidate.

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
| `suite-path` | Path | No | The research-suite folder (`<project-root>/.apothem/plans/{suite}/`). When omitted, resolve from the most recent suite carrying a ratified `_spec/research-spec.md`; surface a disambiguation inquiry when more than one candidate exists. |
| `--max-sources <N>` | Flag + value | No | Cap the screened-in source count. When omitted and the spec declares no ceiling, Phase 1 surfaces the ceiling via the structured-inquiry channel. |
| `--override` | Flag | No | Bypass the Sequence Gate when the `/research-theory` grounding or the ratified `_spec/research-spec.md` is absent. Writes a `[Gate-Override — predecessor: /research-theory; rationale: <operator-supplied>]` audit row to the source ledger; the override is never silent. |
| `--standalone` | Flag | No | Mark the invocation as standalone (no downstream `/research-synthesis` consumer). The Handoff Manifest still emits with `downstream: none (standalone invocation)`. |

---

## Sequence Gate

**Predecessor precondition.** `/research-sources` runs only after `/research-theory` has emitted the theoretical grounding and the ratified `{suite}/_spec/research-spec.md` is present, with a Handoff Manifest recording `/research-theory` as the producing stage with zero unresolved P0/P1 markers. The screening contract (inclusion/exclusion criteria) is the spec's; collection without it is collection without a target.

**Gate-closed behavior.** When the theoretical grounding is absent or the Handoff Manifest is missing/malformed:

```text
Blocked: run /research-theory first.
```

Emit the blocked line, name the absent artifact, and halt. Do not invent a theoretical grounding, do not infer screening criteria from the raw question, do not proceed on a draft.

**Override path.** `--override` proceeds without the theoretical grounding only when the operator supplies a rationale through the structured-inquiry channel. The override writes a `[Gate-Override — predecessor: /research-theory; rationale: <operator-supplied>]` audit row to `source-ledger.md`; the downstream `/research-synthesis` stage reads the override row and treats the evidence base as un-grounded until the theory is ratified.

---

## Workflow — Five Phases

| Phase | Name | Step contract |
| ----- | ---- | ------------- |
| 1 | Spec Ingest & Sub-Query Decomposition | load-context |
| 2 | Parallel Discovery Dispatch | execute |
| 3 | Dedup, Rank, PRISMA-Screen & Risk-of-Bias | execute |
| 4 | Per-Source Extraction with Provenance | execute + verify |
| 5 | Ledger Emission & Pre-Emission Gate | gate + report |

### Phase 1 — Spec Ingest & Sub-Query Decomposition

Read `{suite}/_spec/research-spec.md` in full. Extract the question, the falsifiable hypotheses, the scope boundaries, the inclusion/exclusion criteria, the success metrics, and the glossary. Decompose the question into **orthogonal sub-queries** — one facet per distinct evidence dimension (claim domain, competing-method axis, temporal window, population/subject scope). Non-orthogonal sub-queries produce redundant returns; the decomposition minimizes overlap.

Emit the pre-flight inquiry set: the source-budget ceiling when unfixed, and a screening-criterion confirmation placeholder for every inclusion/exclusion criterion the spec leaves under-specified. Persist the decomposition and the ratified screening contract to `{suite}/_inputs/notes.md` as the discovery lineage.

### Phase 2 — Parallel Discovery Dispatch

> Moved to `references/step-02-parallel-discovery-dispatch.md`. MUST read it in full before executing this step.

### Phase 3 — Dedup, Rank, Screen

> Moved to `references/step-03-dedup-rank-screen.md`. MUST read it in full before executing this step.

### Phase 4 — Per-Source Extraction with Provenance

> Moved to `references/step-04-per-source-extraction-with-provenance.md`. MUST read it in full before executing this step.

### Phase 4b — Comparator / Baseline Provenance Ledger

> Moved to `references/step-05-comparator-baseline-provenance-ledger.md`. MUST read it in full before executing this step.

### Phase 5 — Ledger Emission & Pre-Emission Gate

Compose `{suite}/_inputs/source-ledger.md`: the ranked screened-in table (id, citation, authority/recency/relevance scores, the hypothesis/sub-query each bears on), the screened-out record (candidate, failed criterion), the dedup record (collapsed identifiers, reason), the citation index (every `sources/<id>.md` ↔ its canonical citation), and the R1/R4 attestation block. Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md`; the R4 citation-integrity bar is hard — a phantom citation blocks emission. Amend the Handoff Manifest with the emitted paths, the screened-in/screened-out/dedup counts, and the attestation. Emit the manifest with `downstream: /research-synthesis` (or `downstream: none (standalone invocation)` under `--standalone`).

---

## Mandates

The command's restatement of the research-suite rigor floor and the project mandates, scoped to the source-collection domain. Each is atomically installed on the command:

- **R1 Authoritative sources** — every load-bearing extracted claim cites a primary, peer-reviewed, official, or archival source; folklore is recorded as folklore, never promoted; the authority axis of the rank applies the floor.
- **R2 Reproducibility** — each extraction records the source's stated method/scope so the downstream design stage can assess re-runnability.
- **R4 Citation integrity** — every citation resolves to a real, permalinked/DOI/commit-pinned reference; `fact-checker` confirms reachability; a phantom citation blocks emission (ties to `rules/ten-dimension-check.md` dim 9).
- **R1 + R4 Comparator provenance** — the executed comparator/baseline set is subject to the same authority-and-resolution floor as any load-bearing source: each comparator resolves to a permalinked/DOI/commit-pinned origin the `fact-checker` confirms, and an unverifiable comparator is recorded `cannot-confirm`/`cannot-fetch` and excluded from the load-bearing set, never invented (`skills/research-suite/references/comparator-provenance.md`).
- **R6 Ethics & conflicts** — a source carrying a declared conflict-of-interest or a data-availability restriction is extracted with that declaration recorded for downstream ethics review.
- **R9 Reporting-guideline conformance** — screening follows the four-stage PRISMA flow (identification → screening → eligibility → included) with per-stage counts, and every included source carries a per-domain risk-of-bias assessment, per the EQUATOR/PRISMA reporting guideline.
- **Authority before invention** — no source, URL, DOI, author, or date is fabricated; an unverifiable candidate is screened out, never invented into legitimacy (`rules/authority-inquiry.md`).
- **Option annotation** — every structured-inquiry invocation carries the three-segment body per `rules/interactive-questions.md` §3.
- **Agent orchestration** — discovery fans out as a Research Team per `rules/agent-orchestration.md` §1 under explicit return contracts.
- **Systemicity** — no orphan extraction; every `sources/<id>.md` is indexed in the ledger's citation index and bound reciprocally to the ledger.

R3 (falsifiability), R5 (preregistration), R7 (statistical rigor), R8 (open-science / FAIR), and R10 (theoretical grounding) are N/A or upstream-attested at this stage — R3/R5/R7/R8 bind the design, experiment, and analysis stages downstream, and R10 is anchored upstream at `/research-spec` and developed at `/research-theory`.

---

## Output

| Artifact | Path | Purpose |
| -------- | ---- | ------- |
| Per-source extraction | `{suite}/sources/<id>.md` | One provenance-bearing record per screened-in source: citation, access date, attribution, load-bearing claims, stated method/scope, discovery provenance. |
| Source ledger | `{suite}/_inputs/source-ledger.md` | The ranked screened-in table, the screened-out record, the dedup record, the citation index, the comparator/baseline provenance track (each comparator's citation, method family, implementation status, version/config, and `cannot-confirm`/`cannot-fetch` verdict), and the R1/R4 attestation block. |
| Discovery scratch | `{suite}/_inputs/notes.md` | Sub-query decomposition and ratified screening contract; deleted or distilled at stage exit per the forge lifecycle. |
| Handoff Manifest | `{suite}/_inputs/handoff-manifest.yml` | Amended at stage exit with emitted paths, screened-in/out/dedup counts, and the gate attestation; `downstream: /research-synthesis`. |

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Examples

> Moved to `references/examples.md`. SHOULD read it before composing the final output.

---

## Failure Modes

| Mode | Trigger | Recovery |
|------|---------|----------|
| Missing ratified spec | Sequence Gate: `_spec/research-spec.md` absent. | Emit the blocked line; halt. `--override` proceeds only with an operator rationale audited in the ledger. |
| Under-specified screening criteria | Phase 1: spec leaves an inclusion/exclusion criterion ambiguous. | Surface a screening-criterion confirmation placeholder; block emission until resolved. Never infer the criterion silently. |
| Phantom citation | Phase 4: `fact-checker` finds a citation that fails to resolve. | Screen out the source; record the resolution failure; re-extract the next-ranked candidate to hold the budget. R4 bar blocks emission until clean. |
| Fabricated provenance | A candidate's author/date/URL cannot be verified. | Screen out as unverifiable; record the gap. NEVER invent the missing provenance. |
| Non-orthogonal decomposition | Phase 1: sub-queries overlap, producing redundant returns. | Re-decompose along distinct evidence dimensions; the dedup count surfaces excessive overlap. |
| Orphan extraction | A `sources/<id>.md` is not indexed in the ledger. | Add the citation-index row in the same emission per `rules/systemic-participation.md`; orphan extractions are structural failures. |

---

## Critical Rules

- **NEVER fabricate a source, URL, DOI, author, or date.** An unverifiable candidate is screened out and recorded; invention into legitimacy is forbidden (R1, R4).
- **NEVER screen silently.** Every screened-out candidate carries the specific criterion it failed; every dedup-collapse carries both identifiers and the reason.
- **NEVER synthesize.** This stage collects and qualifies; the SOTA map, the literature matrix, and the gap statement are `/research-synthesis`'s remit.
- **NEVER emit a ledger with an unresolved citation.** The R4 citation-integrity bar is hard; a phantom citation blocks emission.
- **NEVER fabricate a comparator or baseline.** A comparator whose source cannot be confirmed or whose artifact cannot be fetched is marked `cannot-confirm`/`cannot-fetch` and excluded from the load-bearing set — never invented, approximated from memory, or promoted (R1, R4).
- **NEVER proceed without the ratified spec** unless `--override` supplies an audited rationale; the spec is the screening contract.

---

## Recommended Next Step

Invoke `/research-synthesis` to consume the ranked, screened `source-ledger.md` and the per-source extractions and build the SOTA map, literature matrix, and the explicit gap statement; `/research-synthesis` is the canonical pipeline successor per the Sources → Synthesis handoff.
