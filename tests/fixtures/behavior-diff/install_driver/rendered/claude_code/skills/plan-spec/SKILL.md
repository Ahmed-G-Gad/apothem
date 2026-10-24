---
name: "plan-spec"
description: "Turns free-form prose, notes or rough requirements into a spec-grade _spec/spec.md that keeps the author's wording and settles open questions by inquiry. Use when the user asks to 'turn these notes into a spec', 'refine these requirements' or 'prepare this for planning'. Research: research-spec."
argument-hint: "[path/to/prose-source] [--suite-name NAME] [--refine-existing] [--standalone] [--quick SLUG [--tag TAG]]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-24"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /plan-spec — Prose-to-Spec Lifecycle Command

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the **Forge** — the upstream prose-refinement stage of the `/plan` pipeline. You do not summarize, paraphrase, or reword the operator's prose. You **weave** it into a spec-grade artifact in which:

- every distinctive phrase is preserved verbatim at its analogous locus,
- every requirement is operationally enforced — not merely quoted,
- every tonal choice (bold · italic · ALL-CAPS · repeated intensifiers · slash-alternations · paired adjectives · rhetorical repetition) survives at its structural counterpart, and
- every preserved element is paired with its potent operational form.

The Forge runs under four operational disciplines and emits five appendices inline, yet stays a single-pass handoff surface: no duplicated round-trip prose, appendices proportionate to source complexity, downstream evidence routed to the suite's `_outputs/` rather than inflating the spec.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, after any context compaction, and before the final step or any handoff. Covers: Pipeline position — Initial; Handoff Manifest; Pre-flight inquiry set; Pre-emission gate; Inquiry Cadence (D4).

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step and after any context compaction; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/prose-source` | Path or inline content | Yes | The free-form prose, raw notes, requirements document, or ad-hoc request to refine. A single file, a directory of fragments, or inline content piped via stdin. |
| `--suite-name <kebab-case>` | Flag + value | No | The plan-suite folder name. If omitted, surface via the structured-inquiry channel at Phase 1 before any forge write. |
| `--refine-existing` | Flag | No | When the suite folder already carries a `_spec/spec.md`, treat the existing spec as the starting point and apply iterative refinement; otherwise the run starts from `_inputs/forge.md` and promotes to `_spec/spec.md` at G4. |
| `--standalone` | Flag | No | Mark the invocation as standalone (no downstream `/plan-generate` consumer). The Handoff Manifest still emits with `downstream: none (standalone invocation)` per §4.8.6. |
| `--quick <slug>` | Flag + value | No | Bypass Forge elicitation entirely; write a single lightweight plan file at `<project-root>/.apothem/plans/<YYYY-MM-DD>--<kebab-slug>.md`. Mutually exclusive with `--refine-existing` and the six-phase Forge workflow. See [Mode: `--quick`](#mode---quick-lightweight-plan-local-write). |
| `--tag <tag>` | Flag + value | No | Repeatable. Adds a tag to the lightweight plan file's frontmatter `tags:` array. Meaningful only with `--quick`; ignored in Forge mode. |

---

## Mode: `--quick` (Lightweight Plan-Local Write)

> Moved to `references/mode-quick.md`. MUST read it when invoked with `--quick`; otherwise skip it.

---

## Workflow — Six Transformation Phases

### Phase 1 — Discovery & Extraction (Pre-G1)

Read the prose source in full. For MASSIVE prose (>50K tokens), chunk via parallel `Explore` agents (one chunk per agent, ≤10K tokens each) and persist each extraction at `{suite}/_inputs/extract-chunk-{A,B,...}.md`. Capture extraction lineage explicitly — every chunk file is an authoritative signal-lineage anchor referenced at Phase 6's Question-Resolution Audit.

**Establish the suite folder.** Per `rules/context-management.md` §2.6.1, every `_inputs/` and `_spec/` directory is a direct child of a plan-suite folder. Two sub-cases:

- **Suite name known up front (`--suite-name`):** create `{suite}/_inputs/forge.md` directly.
- **Suite name not provided:** surface via the structured-inquiry channel (single-select; options derived from a prose-content scan; safe default named per §7.1 of the canonical-channel rule). The question fires before any forge write.

### Phase 2 — Meticulous Consideration (D1)

> Moved to `references/step-02-meticulous-consideration-d1.md`. MUST read it in full before executing this step.

### Phase 3 — Potency Mapping (D2)

> Moved to `references/step-03-potency-mapping-d2.md`. MUST read it in full before executing this step.

### Phase 4 — Preservation Verification (D3) — Three Levels

> Moved to `references/step-04-preservation-verification-d3-three.md`. MUST read it in full before executing this step.

### Phase 5 — Expertise Application (D4) — Seven Axes of Breadth

Every transformation attests which of the seven axes applied: Domain · Adjacent-domain · Meta-engineering · Operational · Process · Scholarly-technical-literature · Second-order-systems-thinking. Inline markers `**[Expertise amendment — axis: X — rationale: ...]**` at every amended locus.

**Expertise-Gap Log deliverable.** Every applicable axis surfaces in the Expertise-Gap Log appendix (Appendix D schema). Gate ◇ — under-applied axes block emission as `**P1**` per §4.8.3 D4.

### Phase 6 — Question-Resolution Sweep (Ten Disciplines D1–D10) — Mandatory Gates G0–G5

> Moved to `references/step-06-question-resolution-sweep-ten.md`. MUST read it in full before executing this step.

### End-of-Command Synthesis (D6)

> Moved to `references/step-07-end-of-command-synthesis-d6.md`. MUST read it in full before executing this step.

---

## Four-Discipline Operational Invariant (Six Conditions)

Output emission is gated on six conditions; failure on any = malpractice + blocks emission:

1. Every distinctive prose phrase verbatim-preserved at an analogous locus (D3 L1).
2. Every requirement / directive operationally enforced in scaffolding (D3 L2).
3. Every tonal choice preserved at an analogous locus (D3 L3).
4. Every preserved element paired with its potent form (D2).
5. Every applicable expertise axis applied with attestation (D4).
6. Every transformation choice traceable to a Consideration Log entry (D1).

The invariant is checked at G4 (Pre-emission); failure on any condition holds the spec at `{suite}/_inputs/forge.md` and surfaces a `**P1**` block until resolved.

---

## Output

| Artifact | Path | Purpose |
| -------- | ---- | ------- |
| Spec | `{suite}/_spec/spec.md` | The promoted spec ready for `/plan-generate`. Carries five appendices inline. |
| Forge scratch | `{suite}/_inputs/forge.md` | Pre-promotion draft (deleted at G4 after promotion per the forge → spec lifecycle in `rules/context-management.md` §2.6.1). |
| Extraction lineage | `{suite}/_inputs/extract-chunk-*.md` | Per-chunk extraction files for MASSIVE prose; preserved as authoritative signal-lineage anchors. |
| Handoff Manifest | `{suite}/_inputs/handoff-manifest.yml` | Emitted unconditionally at G5 with `p0-unresolved: 0` and `p1-unresolved: 0` attestations. |

**Five appendices inline** in `{suite}/_spec/spec.md`: Consideration Log (A) · Potency Map (B) · Preservation Audit (C) · Expertise-Gap Log (D) · Question-Resolution Audit (E). Appendices are proportionate — enough evidence to verify preservation and downstream generation, never repeated full-source transcripts or duplicate review reports.

---

## Failure Modes

| Mode | Trigger | Recovery |
|------|---------|----------|
| Empty Consideration Log | D1 ◇ Gate fires; no consideration items captured. | Re-run Phase 2 with deeper prose engagement; do not emit. |
| Missing potent-form pairing | D2: a preserved element has no Potency Map entry. | Re-run Phase 3 on the unpaired element; emit `**P1**` block. |
| Level-1 grep-miss | D3 L1: a distinctive phrase fails the verbatim-presence check. | Re-weave at the analogous locus in Phase 4; do not emit until the grep-match holds. |
| Level-2 quote-without-enforcement | D3 L2: a quoted requirement carries no operational scaffolding. | Re-run Phase 4 + Phase 3; install scaffolding; emit `**P1**` block until honored. |
| Level-3 flattening | D3 L3: a tonal choice flattened at the analogous locus. | Re-weave in Phase 4; emit `**P2**` (escalating to `**P1**` where interpretive weight is material). |
| Under-applied expertise axis | D4 ◇ Gate: an applicable axis carries no amendment. | Re-run Phase 5; emit `**[Expertise amendment — axis: X — rationale: ...]**`; emit `**P1**` block until applied. |
| Silent default | D8 anti-pattern: any of the twelve silent-X patterns detected. | Halt emission; surface the silent-X via the structured-inquiry channel at the appropriate gate; log the recovery in the Question-Resolution Audit. |
| Falsified Handoff Manifest | D7: manifest emitted with non-zero `p0-unresolved` or `p1-unresolved`. | P0 integrity failure; halt downstream; surface to operator. |

---

## Verification Recipe (per §I.6)

Where an installed copy holds this command as a skill directory (a `SKILL.md` plus `references/` files), run each `rg` below against that directory instead of `commands/plan-spec.md`, and count a step heading once even though it appears in both `SKILL.md` and its step file.

1. **Frontmatter.** `rg --no-heading -nP '^name: "plan-spec"$' commands/plan-spec.md` returns 1 hit; `rg --no-heading -nP '^description: .+$' commands/plan-spec.md` returns 1 hit with a non-empty description.
2. **Phase enumeration.** `rg --no-heading -nP '^### Phase [1-6] —' commands/plan-spec.md` returns 6 hits (one per transformation phase).
3. **Discipline enumeration.** `rg --no-heading -nP '^- \*\*D[1-9]0?' commands/plan-spec.md` returns at least 14 hits (D1–D4 operational + D1–D10 structured-inquiry disciplines).
4. **Gate enumeration.** `rg --no-heading -nP '\*\*G[0-5]\*\*' commands/plan-spec.md` returns 6 hits (G0–G5).
5. **Self-application attestation.** `/plan-spec --self-application-attestation` emits a PASS attestation per the §4.8.4 four-discipline invariant; the attestation lists each of the six conditions with a PASS verdict.
6. **Standalone-invocation attestation.** `/plan-spec --standalone <prose-path>` emits the Handoff Manifest with `downstream: none (standalone invocation)` per §4.8.6; no silent terminal-ness.
7. **Work-root naming attestation.** The Manifest's `repository` + `mission` fields are non-empty per the §1.5 INQ-WORKROOT-SCHEME ratification.

---

## Examples

> Moved to `references/examples.md`. SHOULD read it before composing the final output.

---

## Self-Application Attestation

`/plan-spec --self-application-attestation` runs the verification recipe (§I.6 above) against this command file and emits a PASS/FAIL verdict per condition. The attestation is the canonical reflexive self-check per §0.d recursive self-application; failure on any condition surfaces as a `**P1**` block.

---

## Mandates (§I.0.a–§I.0.o restated, scoped to the prose→spec domain)

This command's restatement of `_spec/spec.md` §0.a–§0.o, scoped to the prose-to-spec transformation domain. Each mandate is atomically installed on the command:

- **§I.0.a Co-equal mandates** — every §0.x is co-equal; no implicit priority ordering.
- **§I.0.b Decomposition** — the six transformation phases are the canonical decomposition; sub-sprint decomposition is admissible per Phase 1 establishment.
- **§I.0.c Ten dimensional gates** — the §0.d fifteen-bar self-check applies recursively at G4.
- **§I.0.d Self-application** — this command is itself subject to the verification recipe (§I.6).
- **§I.0.e Authority before invention** — no prose datum is fabricated; gaps surface as `<USER-CONFIRM:kind=...>` placeholders per D4 Deferral Discipline.
- **§I.0.f Expertise** — D4 Seven Axes of Breadth applied with attestation.
- **§I.0.g Option annotation** — every structured-inquiry invocation carries the §3 three-segment body per `rules/interactive-questions.md`.
- **§I.0.h Definitiveness** — closed-set enumeration on every option set; airtight input-class coverage.
- **§I.0.i Visual leverage** — Mermaid diagrams installed where the prose admits flow / sequence / state structure per the D2 pairing dictionary.
- **§I.0.j Bidirectional binding** — every cross-reference carries the five-direction stamping.
- **§I.0.k Agile** — this command is a single-sprint operation with the G5 Handoff Manifest as the Sprint Review artifact.
- **§I.0.l Phase reporting** — the spec.md IS the rollup; the Handoff Manifest IS the per-phase report.
- **§I.0.m Code-craft** — N/A on a prose-class command; the operational disciplines stand in.
- **§I.0.n Systemicity** — no orphan; this command is reciprocally bound to `/plan-generate` (downstream consumer) and to the prose source (upstream lineage).
- **§I.0.o Production-readiness** — N/A on a `commands/` artifact; production-readiness applies to the suite the command produces.

---

## Critical Rules

- **NEVER silently default.** Every questionable surfaces via the structured-inquiry channel; the twelve D8 anti-patterns are forbidden.
- **NEVER suppress questions to reduce user burden.** Question-fatigue-optimization is not a legitimate optimization per §4.8.8.
- **NEVER emit `_spec/spec.md` without the five appendices inline.** Consideration Log + Potency Map + Preservation Audit + Expertise-Gap Log + Question-Resolution Audit are mandatory.
- **NEVER duplicate ceremony for its own sake.** The Forge produces one authoritative spec and one Handoff Manifest; downstream evidence and bulky reports belong to `_outputs/` or later command reports, not repeated inside the spec.
- **NEVER skip the G5 Handoff Manifest.** Even on standalone invocation, the Manifest emits with `downstream: none (standalone invocation)`.
- **NEVER bypass the four-discipline invariant.** All six conditions PASS before emission; failure on any holds the spec.

---

## Recommended Next Step

Invoke `/plan-generate` to consume the ratified `_spec/spec.md` and materialize the plan suite — the canonical pipeline successor per the Forge → Generate handoff.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
