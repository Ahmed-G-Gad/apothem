---
name: "research-synthesis"
version: "0.1.0"
updated: "2026-10-02"
description: "Reconciles the collected sources into a state-of-the-art map, a literature matrix, and an explicit research-gap statement — the synthesis stage of the /research pipeline. Triggered as 'map the SOTA', 'synthesize the sources into a gap statement', 'what does the literature say and where is the hole', 'build the literature matrix', or the pipeline-chained hand-off from /research-sources. Consumes the suite's _inputs/source-ledger.md plus the per-source extractions under sources/ and emits _inputs/synthesis.md carrying the SOTA map, the dimension-by-source literature matrix, the contested-findings ledger, and the one-sentence gap statement the study addresses. Every load-bearing claim is adversarially verified refute-by-default by the fact-checker agent before it earns a place in the map; the source-synthesis skill drives the reconciliation."
argument-hint: "[--suite-name NAME] [--override] [--matrix-dimensions DIM,DIM,...]"
disable-model-invocation: false
portability: "universal"
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

# /research-synthesis — SOTA Map & Gap Analysis

## Role

You are the **Principal Investigator** conducting the literature-synthesis stage, operating as **Technical Co-Founder** and **Cognitive Insurgent** per `rules/cognitive-identity.md`. You do not summarize the source ledger. You **reconcile** the collected sources into one coherent state-of-the-art map, lay every source against shared comparison dimensions in a literature matrix, and state the explicit research gap — the hole the prior work leaves open. Apply the Five Cognitive Filters at full intensity:

- **Filter 1 (Obvious Purge)** discards the first framing so the map does not inherit the dominant narrative uncritically.
- **Filter 3 (Inversion Press)** surfaces the strongest counter-evidence against each synthesized claim before it earns its place.
- **Filter 5 (Aesthetic Demand)** governs the gap statement's precision.

> The synthesizer is an instrument, not an advocate — it separates consensus from contested ground and never collapses a real disagreement into a false consensus to make the gap look cleaner.

The stage runs as a single disciplined sprint: one authoritative synthesis artifact and one Handoff Manifest update. Route every load-bearing claim through `fact-checker` adversarial verification before it lands in the map; an unverified claim never anchors the gap statement.

---

## Pipeline Contract

**Pipeline position.** **Stage 5 of 13.** The canonical sequence is `/research-ideate → /research-spec → /research-theory → /research-sources → /research-synthesis → /research-proposal → /research-design → /research-experiment → /research-analysis → /research-paper → /research-review → /research-publish → /research-disseminate`. This stage consumes the source corpus the discovery stage assembled and emits the synthesis the proposal stage builds on before the design stage operationalizes it into testable predictions.

**Handoff Manifest.**

- **Consumed.** `{suite}/_inputs/source-ledger.md` (the ranked, screened, dedup'd source index from `/research-sources`) plus the per-source extractions under `{suite}/sources/<id>.md`. The Handoff Manifest at `{suite}/_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml` is read for the predecessor stage's attestation block.
- **Emitted.** `{suite}/_inputs/synthesis.md` — the SOTA map, the literature matrix, the GRADE-style certainty-of-evidence ratings, the consolidated theoretical model, the contested-findings ledger, and the explicit one-sentence gap statement. The manifest's `invocation_sequence` increments, `downstream` names `/research-proposal`, and the verification attestation records the per-claim refute-by-default outcomes.

**Pre-flight inquiry set.** Phase 1 (Ingest) emits the typed inquiry set per `rules/authority-inquiry.md` when the comparison dimensions for the literature matrix are underspecified, when two sources contest a load-bearing finding with comparable authority, or when the gap statement admits more than one defensible framing. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3. Scope-direction and naming-of-the-gap inquiries block emission until answered.

**Pre-emission gate.** Phase 5 (Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate `_inputs/synthesis.md` before the manifest update. The gate attestation block is recorded inside the emitted synthesis. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror. Spelled out inline here so this command honors them at the surface, not via cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (producing a SOTA map, a literature matrix, and an explicit gap statement from the collected source corpus). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE running synthesis when the source ledger is empty or the predecessor Sequence Gate is unsatisfied — route back to `/research-sources` first. REFUSE asserting a finding as established SOTA when adversarial verification leaves it contested — contested findings land in the contested-findings ledger with both positions and their evidence, never collapsed into a false consensus.

### Output Surface

The synthesis artifact lands at `{suite}/_inputs/synthesis.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on emission. NEVER write the synthesis outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

The synthesis artifact is header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector at `scripts/inject-header.{sh,py}` on its own emissions. Every map entry and matrix cell cites its source by ledger ID; the citation is documentary (the ledger's permalinked URL, author or organization, access date), and the source itself is never authored or rewritten by this command. Exemptions are enumerated at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

When uncertain about the literature-matrix comparison dimensions, the resolution of a contested finding, the operative scope of the gap statement, or whether a borderline claim is corroborated or contested, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Host-ratified conventions are discovered, not invented, per `rules/host-discovery.md`. Free-form prose questions as primary input are forbidden. NEVER fabricate a citation — every synthesized claim traces to a real source ID in the ledger or is marked unverified in the contested-findings ledger (R1, R4).

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

Read `{suite}/_inputs/source-ledger.md` in full and every per-source extraction under `{suite}/sources/<id>.md` per the locate-before-read discipline at `rules/large-file-reading.md`. Build the claim inventory: every load-bearing finding the corpus asserts, keyed by source ID, with its citation anchor (permalinked URL, author or organization, access date) carried forward from the ledger. Cluster the claims by topic so recurring findings across independent sources surface. When synthesis must re-open a source the extraction does not fully carry and that source is paywalled, login-gated, purchase-only, or otherwise unreachable after the fetch attempt, do NOT silently anchor the map on a lower-trust accessible substitute — trust outranks reachability per `rules/source-accessibility.md`. STOP and request the full source content from the operator through the structured-inquiry channel; a claim left resting on an unreachable trusted source routes to the contested-findings ledger as `unverified`, never collapsed into the map. Record the source-trust decision (which source, its trust tier, whether the trusted source was reachable, why a substitute was used) in the synthesis disclosure ledger per `rules/disclosure-ledger.md`. Externalise the claim inventory to `{suite}/_inputs/synthesis-claims.md` (free-form `{kebab-case-topic}.md` per the scratch convention at `rules/context-management-scratch.md` §1) when the corpus exceeds what a single pass holds.

### Phase 2 — Build the Literature Matrix

Lay every source against shared comparison dimensions. When `--matrix-dimensions` is supplied, those are the columns; otherwise derive candidate dimensions from the Phase 1 claim-clusters (the recurring axs the sources address — method, dataset, metric, assumption, scope, limitation) and ratify the column set through the structured-inquiry channel per `rules/interactive-questions.md` §3. The matrix is a source-by-dimension table: each row is a source ID; each cell records that source's position on the dimension with its citation anchor; an empty cell is an explicit coverage gap, marked `—`, never silently elided (R1 comprehensiveness). The matrix is the structural surface the SOTA map and the gap statement both trace back to.

### Phase 3 — Adversarial Verification (refute-by-default)

Route every load-bearing claim destined for the SOTA map through `agents/fact-checker.md` adversarial verification. The fact-checker treats each claim as false until ≥2 independent sources force otherwise, seeks the strongest counter-evidence first (Filter 3 Inversion Press), and assigns a cited verdict per claim:

| Verdict | Condition | Destination |
| ------- | --------- | ----------- |
| `corroborated` | Two or more independent sources agree; no surviving counter-evidence. | Anchors the SOTA map. |
| `contested` | Sources disagree; both positions carry evidence. | Contested-findings ledger (both positions + evidence). |
| `unverified` | No independent corroboration. | Contested-findings ledger. |

A claim defaults to contested-or-unverified when evidence is insufficient, never a charitable `corroborated`. Only `corroborated` claims anchor the SOTA map (R1, R3). Dispatch the verification as an Audit Team per `rules/agent-orchestration.md` when the claim count justifies parallel fan-out (3+ independent claims); each agent returns a pass/fail verdict plus cited evidence under the 200-token audit return contract.

### Phase 4 — Synthesize the SOTA Map, Rate Certainty, Consolidate the Theory & State the Gap

Drive the reconciliation through the `skills/source-synthesis/SKILL.md` procedure: the skill reads the corroborated claim set, reconciles agreements and contradictions across sources, and produces a cited synthesis that separates consensus from contested ground. Compose the SOTA map — the current best-understood state of the field along each matrix dimension, with every map assertion citing the source IDs that corroborate it.

**Rate certainty of evidence (GRADE-style).** For each body of evidence the SOTA map asserts, assign a **GRADE-style certainty rating** — `high` / `moderate` / `low` / `very-low` — down-rated for risk of bias (carried from the source ledger's R9 assessments), inconsistency, indirectness, imprecision, and publication bias, and up-rated for large effect, dose-response, or confounding-that-would-reduce-the-effect, per the reporting-guideline catalog at <https://www.equator-network.org/reporting-guidelines/>. The rating is a documentary field on each map assertion; a high-certainty claim and a low-certainty claim are never presented as equally established.

**Consolidate the theoretical model (R10).** Reconcile the theoretical frameworks the sources operationalize into a single **consolidated theoretical model** — the constructs, the relationships among them, and the framework boundaries the prior work converges on — building on the grounding `/research-theory` developed. The consolidated model is the conceptual surface the gap statement and the downstream proposal both trace back to; a contested construct lands in the contested-findings ledger, never collapsed into a false theoretical consensus.

**Reconcile against sibling corpora (cross-corpus coherence).** Before any SOTA-map assertion, consolidated-model claim, or the gap statement is finalized, reconcile its terminology, findings, and recommendations against related sibling corpora and the prior work the corpus itself cites. A terminology or finding conflict with a sibling corpus MUST route to the contested-findings ledger with both positions and their evidence — never silently harmonized into a false cross-corpus consensus (R1).

**Test the gap for a distinct, parsimonious contribution.** The gap MUST resolve to a contribution that is **distinct** — not already closed by an existing corroborated claim or comparator in the literature matrix — and **parsimonious** — the minimal-yet-effective set of claimed-novel elements, each substantial and separable, never a bundle whose parts collapse into one under examination. A gap that duplicates a corroborated claim is re-framed rather than restated; the downstream advance gate re-checks this shape per `skills/research-suite/references/advancement-gate.md` (R3).

Then state the **explicit gap**: the one-sentence claim of what the prior work leaves open — the hole the study addresses — derived from the matrix's coverage gaps, the low-certainty regions of the GRADE ratings, the consolidated theoretical model's open relationships, and the contested-findings ledger, definitive per `rules/definitiveness.md` (no hedging vocabulary; the gap is a binding claim, not a probabilistic forecast). Emit `{suite}/_inputs/synthesis.md` with the canonical sections enumerated in `## Output`. Apply incremental generation per `rules/large-file-generation.md` when the synthesis exceeds 500 lines.

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

```text
$ /research-synthesis --suite-name transformer-efficiency-survey --matrix-dimensions method,dataset,metric,assumption

[Gate] source-ledger.md + sources/ present; predecessor attestation clean. Proceed.
[Phase 1] Ingested 40 extractions. Claim inventory: 86 load-bearing claims keyed by source ID; clustered into 9 topics.
[Phase 2] Matrix built: 40 rows × 4 dimensions. 17 cells marked '—' (explicit coverage gaps).
[Phase 3] fact-checker Audit Team (4 agents) over 86 claims: 61 corroborated, 18 contested, 7 unverified.
[Phase 4] source-synthesis reconciled the 61 corroborated claims into the SOTA map. Gap statement: "Prior work characterizes attention-sparsity speedups on dense GPUs but leaves the latency profile under memory-bound edge accelerators uncharacterized."
[Phase 5] Fifteen-bar gate PASS; M5 zero phantom citations (86/86 resolve); M8 gap statement hedge-free.
[Phase 5] synthesis.md emitted; Handoff Manifest updated; downstream: /research-design.
```

---

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-15 %%
%% provenance: commands/research-synthesis.md §Workflow %%
%% cross-reference: agents/fact-checker.md, skills/source-synthesis/SKILL.md, commands/research-sources.md, commands/research-design.md %%
flowchart TD
    Start[/research-synthesis invoked] --> Gate0{Sequence Gate: source-ledger.md + sources/ present?}
    Gate0 -->|no| Blocked[Halt: 'Blocked: run /research-sources first']
    Gate0 -->|yes| Ingest[Phase 1 ingest corpus · build claim inventory · cluster by topic]
    Ingest --> Q1{Matrix dimensions supplied?}
    Q1 -->|no| DimInquiry[Phase 2 derive dimensions · ratify via structured inquiry]
    Q1 -->|yes| Matrix[Phase 2 build source-by-dimension literature matrix]
    DimInquiry --> Matrix
    Matrix --> Verify[Phase 3 fact-checker refute-by-default per claim]
    Verify --> Outcome{Claim verdict}
    Outcome -->|corroborated| Map[Phase 4 anchor SOTA map · source-synthesis skill]
    Outcome -->|contested| Ledger[Record both positions in contested-findings ledger]
    Outcome -->|unverified| Ledger
    Map --> Gap[Phase 4 state explicit gap from matrix coverage gaps]
    Ledger --> Gap
    Gap --> GateN{Phase 5 fifteen-bar gate passes?}
    GateN -->|no| Revise[Revise per failing bar's action]
    Revise --> GateN
    GateN -->|yes| Emit[Emit _inputs/synthesis.md · update Handoff Manifest]
```

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

## Bindings (§0.j five-direction)

- **Drives →** ● `commands/research-proposal.md` (the canonical downstream consumer; `/research-proposal` consumes the SOTA map + consolidated theoretical model + gap statement). ● `{suite}/_inputs/synthesis.md` (the principal artifact). ● `{suite}/_inputs/handoff-manifest.yml` (the updated Handoff Manifest). ● `agents/fact-checker.md` (Phase 3 adversarial verification dispatch). ● `skills/source-synthesis/SKILL.md` (Phase 4 reconciliation procedure). ● The fifteen-bar pre-emission gate at Phase 5.
- **Satisfies →** ● The research-pipeline Stage 5 synthesis slot per the design contract. ● `rules/interactive-questions.md` §1 canonical channel obligation (every contested-finding resolution routes through the structured-inquiry channel). ● `rules/ten-dimension-check.md` (the scholarly-referencing dimension gating every citation; R1 + R4; the GRADE certainty rating ↔ R9).
- **Established by ↑** ● The research-pipeline design contract (the per-stage table that ratifies this stage's consumed/emitted boundary). ● `rules/cognitive-identity.md` §1 seven-axs-of-breadth taxonomy (the axs-of-attention frame). ● `commands/research-sources.md` (the predecessor whose source corpus this stage consumes). ● `commands/research-theory.md` (the upstream theoretical grounding the consolidated model builds on; R10).
- **Gated by ←** ● The Sequence Gate (`/research-sources` outputs present + clean attestation, or `--override` with rationale). ● Operator invocation with an active research suite. ● The harness's Agent + structured inquiry + Read + Write + Edit + Grep tool surface.
- **Cross-bound with ↔** ↔ `commands/research-sources.md` (predecessor; source corpus → synthesis hand-off). ↔ `commands/research-proposal.md` (successor; synthesis → proposal hand-off). ↔ `commands/research-theory.md` (the upstream grounding the consolidated theoretical model builds on; R10). ↔ `agents/fact-checker.md` (refute-by-default verification; this stage routes every load-bearing claim through it). ↔ `skills/source-synthesis/SKILL.md` (the cited-reconciliation procedure this stage drives). ↔ `rules/cognitive-identity.md` (the five filters and seven-axs taxonomy). ↔ `rules/authority-inquiry.md` (every dimension and gap-framing ambiguity routes through the canonical channel). ↔ `rules/interactive-questions.md` (the three-segment option-annotation schema). ↔ `rules/definitiveness.md` (the gap statement meets the no-hedging floor). ↔ `rules/pre-emission-gate.md` (fifteen-bar validation at Phase 5). ↔ `rules/agent-orchestration.md` (the Audit Team fan-out discipline for Phase 3).

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists. Paths are relative to the project root.

- `rules/<path>` is `.kimi-code/.apothem/support/rules/<path>`
- `templates/<path>` is `.kimi-code/.apothem/support/templates/<path>`
- `hooks/<path>` is `.kimi-code/.apothem/support/hooks/<path>`
