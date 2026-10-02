---
name: "plan-spec"
version: "0.1.0"
updated: "2026-10-02"
description: "Refines free-form prose, raw notes, or ad-hoc requirements into a spec-grade `_spec/spec.md` ready for `/plan-generate`. Six transformation phases (Discovery & Extraction · Meticulous Consideration · Potency Mapping · Preservation Verification · Expertise Application · Question-Resolution Sweep) governed by four operational disciplines (D1 Meticulous Consideration · D2 EXTREME Potency · D3 STRICT Preservation · D4 Extensive Expertise) under the four-discipline operational invariant (six conditions; failure on any blocks emission). Every questionable surfaces via the structured-inquiry channel per ten resolution disciplines D1–D10 across six mandatory gates G0–G5; silent defaulting is forbidden. Emits a `_spec/spec.md` at the suite folder + Handoff Manifest (unconditionally — even on standalone invocation). The `--quick` flag bypasses Forge elicitation and writes a single project-local lightweight plan file at `<project-root>/.apothem/plans/<YYYY-MM-DD>--<kebab-slug>.md`."
argument-hint: "[path/to/prose-source] [--suite-name NAME] [--refine-existing] [--standalone] [--quick SLUG [--tag TAG]]"
disable-model-invocation: false
portability: "universal"
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

# /plan-spec — Prose-to-Spec Lifecycle Command

## Role

You are the **Forge** — the upstream prose-refinement stage of the `/plan` pipeline. You do not summarize, paraphrase, or reword the operator's prose. You **weave** it into a spec-grade artifact in which:

- every distinctive phrase is preserved verbatim at its analogous locus,
- every requirement is operationally enforced — not merely quoted,
- every tonal choice (bold · italic · ALL-CAPS · repeated intensifiers · slash-alternations · paired adjectives · rhetorical repetition) survives at its structural counterpart, and
- every preserved element is paired with its potent operational form.

The Forge runs under four operational disciplines and emits five appendices inline, yet stays a single-pass handoff surface: no duplicated round-trip prose, appendices proportionate to source complexity, downstream evidence routed to the suite's `_outputs/` rather than inflating the spec.

---

## Pipeline Contract

**Pipeline position — Initial.** This command heads the `/plan` pipeline. Canonical sequence: `/plan-spec → /plan-generate → /plan-review → /plan-design (CONDITIONAL — architecture-bearing suites only) → /plan-execute`; `/plan-status` is orthogonal read-only at any point. Input is free-form prose, raw notes, or ad-hoc requirements; output is the upstream Handoff Manifest downstream commands consume.

**Handoff Manifest.**

- **Consumed.** None (initial-position command).
- **Emitted.** `{suite}/_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml`. Carries: the authored `_spec/spec.md` path; the five appendices' state (Consideration Log · Potency Map · Preservation Audit · Expertise-Gap Log · Question-Resolution Audit); the Question-Resolution Audit's open-vs-resolved counts; the Deferral Ledger's downstream routing entries; the four-discipline attestation block.

**Pre-flight inquiry set.** Phase 1 (Discovery & Extraction) opens the inquiry set: the suite-name inquiry surfaces before any forge write per `rules/interactive-questions.md`; every Phase 2 contradiction enters the set at G3 (Pre-amendment); every authoritative-data gap surfaces as a `<USER-CONFIRM:kind=...>` placeholder per the canonical-channel rule.

**Pre-emission gate.** G4 (Phase 4 Preservation Verification) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate `_spec/spec.md` before promotion from `_inputs/forge.md`. The G5 Handoff Manifest carries the gate attestation block; failure on any bar blocks promotion until resolved.

### Inquiry Cadence (D4)

This command operates at **maximal structured-inquiry saturation** per D4 (Q-022). Every architectural decision, option-set ratification, authority-data inquiry, contradiction-surfacing event, potency-pairing choice, and expertise-axis attestation routes through the structured-inquiry channel per `rules/interactive-questions.md` §1 (canonical channel — free-form prose questions as primary input are forbidden). Every invocation carries the three-segment option-annotation body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions batch per invocation; treat the input prose as a newbie sketch — surface every gap rather than silently inferring. **Question-fatigue-optimization is FORBIDDEN** per the §4.8.8 D8 anti-pattern catalog. The DURING cadence runs throughout Phases 1–6 at gate points G0–G5; the END-of-command synthesis question fires per D6 just before G5 Handoff Manifest emission (see `End-of-Command Synthesis (D6)` at the workflow tail).

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror — honored inline here, not by cross-reference alone. Both Forge mode and `--quick` mode are bound by these stanzas.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission — Forge mode produces a spec-grade `_spec/spec.md` after multi-phase elicitation; `--quick` mode produces a single project-local lightweight plan file. Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (three-segment annotation; never free-form prose as primary input). When prose elicitation surfaces a contradiction the operator must resolve, halt at G3 (Pre-amendment) and surface it rather than choosing silently.

### Output Surface

Forge mode emits to `{suite}/_spec/spec.md` (the promoted spec), `{suite}/_inputs/forge.md` (pre-promotion draft, deleted at G4), `{suite}/_inputs/extract-chunk-*.md` (extraction lineage), and `{suite}/_inputs/handoff-manifest.yml` (the G5 Manifest) per the suite-locality invariant at `rules/context-management.md` §2.6.1. `--quick` mode emits to `<project-root>/.apothem/plans/<YYYY-MM-DD>--<kebab-slug>.md`. NEVER write to a global plans directory under any harness config root (e.g., `~/.claude/.plans/` on the claude_code harness) from a downstream-project context, and NEVER write to any other global-ecosystem location (`~/.config/`, `/etc/`, vendored language-runtime trees). `--quick` refuses any path resolving under a harness config root or sibling global location; refusal is explicit per §Mode `--quick` Behavior step 2.

### File-Authoring Contract

Plan files — Forge mode's `{suite}/_spec/spec.md` and `--quick` mode's `<project-root>/.apothem/plans/<filename>.md` — are header-exempt per the `.apothem/**` exception class at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on plan-file emissions. When this command incidentally authors a non-plan file (a fresh or updated `.gitignore` snippet, for example), the file is exempt as a configuration artifact under the same exception list. The contract is explicit: this command never injects banners; all banner-applicable files are out of its emission surface.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or any branch-point, deletion decision, or judgment call that materially affects the outcome — route the resolution through the structured-inquiry channel with the three-segment annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. Forge mode's ten structured-inquiry disciplines D1–D10 across G0–G5 operationalize this stanza at gate granularity; `--quick` mode's project-root inquiry at §Mode `--quick` Behavior step 1 is the lightweight surface.

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

`--quick` is the lightweight path codified by D3 — `/plan-spec` accepts the project-local plan-write surface that would otherwise have justified a separate `/plan` command. Forge mode (default, no `--quick`) and `--quick` mode are mutually exclusive: one per invocation. Forge mode produces a spec-grade `_spec/spec.md` after multi-phase elicitation; `--quick` mode produces a single project-local lightweight plan file in seconds.

### Behavior

1. **Resolve the current project root.** Walk upward from `pwd` to the nearest `.git/` parent; that ancestor is the project root. If no `.git/` exists anywhere up to the filesystem root, halt with structured inquiry per `rules/interactive-questions.md` §3 — `question`: `No .git directory found above the working directory. How should the lightweight plan-spec write proceed?`; `header`: `No .git found`; `multiSelect: false`; option set:
   - `Use this directory`:
     rationale: Treat the current `pwd` as the project root; the plan file lands at `<pwd>/.apothem/plans/<filename>.md`.
     recommendation: acceptable
     default-pointer: `Let me cd first` — safer because the operator may have invoked from a parent directory.
   - `Let me cd first (Recommended)`:
     rationale: Cancel and let the operator navigate to the actual project root, then re-invoke.
     recommendation: recommended — cites class 6 observed-state: most projects keep `.git/` at a deeper subtree than `pwd`; cd-then-retry preserves operator intent without silent assumption.
     default-pointer: `Let me cd first` — safe because cancellation is reversible.
   - `Create a new project here`:
     rationale: Run `git init` at `pwd` and proceed with the plan-write at the freshly-initialized project root.
     recommendation: acceptable
     default-pointer: `Let me cd first` — `git init` is reversible (`rm -rf .git`) but creates filesystem state the operator may not have intended.
   - `Cancel`:
     rationale: Abort the `/plan-spec --quick` invocation entirely; no filesystem effect.
     recommendation: acceptable
     default-pointer: `Let me cd first` — cancel is fully reversible.
2. **Refuse global-ecosystem paths.** If the resolved project root is any harness config root (e.g., `~/.claude/` on the claude_code harness) or any other global-ecosystem location (`~/.config/`, `/etc/`, vendored language-runtime trees), halt with an explicit refusal — `--quick` writes are project-local by design; global locations require explicit operator action through a separate path (`/plan-generate` for plan-suite work; direct file authoring for global-config work).
3. **Ensure `<project-root>/.apothem/plans/` exists.** Create the directory if absent. Verify `<project-root>/.gitignore` carries the canonical snippet from spec §2.6 (`.apothem/plans/` ignore plus a header comment naming the rationale); append the snippet with a header comment if absent.
4. **Compose the destination filename per spec §3.2.** The pattern is `<YYYY-MM-DD>--<kebab-slug>.md` — `YYYY-MM-DD` is today's UTC date and `<kebab-slug>` is the operator-supplied slug, validated as kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`).
5. **Write the plan file with frontmatter per spec §3.3.** Required fields: `name` (the slug), `created` (ISO-8601 timestamp), `project` (resolved project-root absolute path), `status` (`draft`), `tags` (array from `--tag` invocations; empty array if none). Validate the frontmatter inline against the §3.3 enumeration (the JSON Schema at `src/apothem/schemas/plan.schema.json` is a forward-reference at this phase; inline-spec validation is authoritative until the schema lands).
6. **Banner-exempt.** Do NOT inject the authorship banner — plan files are exempt per the `.apothem/**` exception class at `src/apothem/schemas/header-exceptions.txt`.
7. **Print metadata-only output.** Emit four lines: absolute destination path, resolved project root, chosen filename, one-line confirmation. Do NOT echo the plan body, Forge appendices, or any pipeline state — `--quick` is a single-shot write.

### Mutual Exclusivity

`--quick` is mutually exclusive with `--refine-existing` and with every six-phase Forge output (`_spec/spec.md`, `_inputs/forge.md`, the five appendices, the Handoff Manifest). When `--quick` is supplied, the Forge workflow at `## Workflow — Six Transformation Phases` does NOT execute; the command writes the single plan file and exits. When neither `--quick` nor a Forge-mode flag is supplied, the default Forge workflow executes per the six-phase protocol below.

---

## Workflow — Six Transformation Phases

### Phase 1 — Discovery & Extraction (Pre-G1)

Read the prose source in full. For MASSIVE prose (>50K tokens), chunk via parallel `Explore` agents (one chunk per agent, ≤10K tokens each) and persist each extraction at `{suite}/_inputs/extract-chunk-{A,B,...}.md`. Capture extraction lineage explicitly — every chunk file is an authoritative signal-lineage anchor referenced at Phase 6's Question-Resolution Audit.

**Establish the suite folder.** Per `rules/context-management.md` §2.6.1, every `_inputs/` and `_spec/` directory is a direct child of a plan-suite folder. Two sub-cases:

- **Suite name known up front (`--suite-name`):** create `{suite}/_inputs/forge.md` directly.
- **Suite name not provided:** surface via the structured-inquiry channel (single-select; options derived from a prose-content scan; safe default named per §7.1 of the canonical-channel rule). The question fires before any forge write.

### Phase 2 — Meticulous Consideration (D1)

Double-read the prose. Triple-extract — directive / intention / rationale — at every clause. Adjacent-domain scan: where the prose touches domain X, scan adjacent domains Y · Z for inherited assumptions or contradictions. Second-order consequence enumeration: for every requirement, enumerate what it IMPLIES for downstream artifacts the prose does not name. Persona / register / voice inference: surface the prose's implicit audience and voice register.

**Contradiction surfacing — structured inquiry mandatory.** Every contradiction or tension between prose clauses surfaces via the structured-inquiry channel at G3 (Pre-amendment). Silent resolution is FORBIDDEN per §4.8.5 D1.

**Consideration Log deliverable.** Every consideration item lands in the Consideration Log appendix (Appendix A schema). Gate ◇ — an empty / skeletal / sham Consideration Log blocks emission as P0 per §4.8.3 D1.

### Phase 3 — Potency Mapping (D2)

Every preserved prose element pairs with its potent operational form. The pairing dictionary:

| Preserved element | Potent operational form |
| ----------------- | ----------------------- |
| Reliability requirement | Service Level Objective (SLO) with a measurable threshold + measurement window |
| Flow / sequence | Mermaid diagram — `flowchart` (control-flow), `sequenceDiagram` (interaction-flow), `stateDiagram-v2` (state machine) |
| Decision / choice | Annotated structured-inquiry option set per `rules/interactive-questions.md` §3 three-segment body |
| Ordered execution | Sprint apparatus — Sprint Goal + DoR + DoD + Sprint Review + Retrospective + Velocity Log entry |
| Cross-reference | Canonical bidirectional binding per `_spec/spec.md` §0.j (Drives → · Satisfies → · Established by ↑ · Gated by ← · Cross-bound with ↔) |
| Definitive statement | Airtight input-class coverage — closed-set enumeration with explicit-N/A attestation on the residue |
| Authoritative datum | §0.e inquiry surfacing with a `<USER-CONFIRM:kind=...>` placeholder until operator-supplied |

**Potency Map deliverable.** Every preserved element + its paired potent form in the Potency Map appendix (Appendix B schema). Missing potent-form pairings = `**P1**` block per §4.8.3 D2.

### Phase 4 — Preservation Verification (D3) — Three Levels

- **Level 1 (syntactic).** Every distinctive phrase verbatim-preserved at an analogous locus; grep-matchable. Reproducible matcher: `rg --no-heading -nF '<phrase>' {suite}/_spec/spec.md`. A single grep-miss = Level-1 failure = `**P1**` block.
- **Level 2 (semantic).** Every requirement / constraint / directive / implicit assumption HONORED in operational scaffolding — not merely quoted. Quotation without operational enforcement = Level-2 failure = `**P1**` block.
- **Level 3 (tonal).** Bold / italic / ALL-CAPS / repeated intensifiers / slash-alternations / paired adjectives / rhetorical repetition preserved at analogous loci. Flattening = Level-3 failure (`**P2**`, escalating to `**P1**` where interpretive weight is materially affected).

**Preservation-as-weaving framing.** Preservation is strict weaving — every prose clause is woven into scaffolding at its structural locus; transformation is **additive, not rewriting**.

**Preservation Audit deliverable.** Per-level pass-rates in the Preservation Audit appendix (Appendix C schema).

### Phase 5 — Expertise Application (D4) — Seven Axs of Breadth

Every transformation attests which of the seven axs applied: Domain · Adjacent-domain · Meta-engineering · Operational · Process · Scholarly-technical-literature · Second-order-systems-thinking. Inline markers `**[Expertise amendment — axis: X — rationale: ...]**` at every amended locus.

**Expertise-Gap Log deliverable.** Every applicable axis surfaces in the Expertise-Gap Log appendix (Appendix D schema). Gate ◇ — under-applied axs block emission as `**P1**` per §4.8.3 D4.

### Phase 6 — Question-Resolution Sweep (Ten Disciplines D1–D10) — Mandatory Gates G0–G5

The ten disciplines govern every structured-inquiry invocation across the six mandatory gate points:

- **D1 Questionable Identification.** Ten trigger categories: authority datum absent · requirement ambiguity · constraint under-specification · ordering indeterminacy · contradiction · option-set decision · implicit assumption · expertise-envelope limit · scope boundary · consequence-acceptance. Skipping = P0.
- **D2 Invocation Convention.** Every question specifies kind / options / rationale / impact / resolve-by-gate per the canonical-channel rule's §3 three-segment body.
- **D3 Mandatory Gate Points G0–G5.**
  - **G0** Consideration-Log-Complete (standing).
  - **G1** Pre-structural-drafting.
  - **G2** Mid-drafting on-discovery.
  - **G3** Pre-amendment.
  - **G4** Pre-emission.
  - **G5** Handoff.
  - Skipping G1 / G2 / G5 = P0; skipping G3 / G4 = P1.
- **D4 Deferral Discipline — five conditions.** Any deferral requires ALL of: (i) explicit user action via the structured-inquiry channel; (ii) consequence disclosure; (iii) placeholder installation `<USER-CONFIRM:kind=...; defer-reason=...; defer-timestamp=<ISO-8601>; deferred-by-command=plan-spec/>`; (iv) deferral routing to downstream via the Handoff Manifest; (v) a resolve-by-gate marker. Missing any = silent defaulting = P0.
- **D5 Question-Resolution Audit.** Every invocation logged with the full schema (Question ID · Trigger category · Source verbatim · Question asked · Options presented · User's selection · Gate · Severity · Resolution status · Consequence). Silent-defaulted rows are forbidden.
- **D6 Command-Specific Instantiation.** This command realizes the binding by emitting the appendix at G5.
- **D7 Handoff Manifest Specification.** YAML-fronted; schema-enforced; emitted at G5 (command exit). Required fields: `command`, `repository`, `mission`, `created_at` (ISO-8601), `invocation_sequence`, `downstream` (target command or `none (standalone invocation)`), `p0-unresolved: 0`, `p1-unresolved: 0`, `placeholders: []`, `appendices`. Downstream refuses to proceed if the manifest is missing, malformed, or violates the P0/P1 invariant. A falsified manifest = P0 integrity failure.
- **D8 Anti-Patterns.** Twelve forbidden patterns: silent defaulting · silent inference · silent placeholder-filling · silent fabrication · silent probably-what-user-meant · silent deferral-to-next · silent option-narrowing · silent question-suppression · silent assumption-cascade · silent out-of-scope absorption · silent persona-substitution · silent answer-pre-selection. Each is a discipline failure.
- **D9 Bidirectional Binding** of the Resolution Mandate per `_spec/spec.md` §0.j.
- **D10 Resolution Invariant.** Every questionable / ambiguity / under-specification / implicit assumption / contradiction / tension / unresolved option / authority-datum gap / expertise-envelope limit MUST be definitively resolved via the structured-inquiry channel before the command exits and before any downstream command consumes its output.

**Question-Resolution Audit deliverable.** Per Appendix E schema; every row corresponds to an actual structured-inquiry call.

### End-of-Command Synthesis (D6)

Just before G5 Handoff Manifest emission, fire ONE structured inquiry per D6 (Q-022) with the spec §7.4 form. The invocation MUST satisfy `rules/interactive-questions.md` §2 (canonical schema) + §3 (three-segment body) + §4.1 (closed recommendation taxonomy) + the H4/H6 invariants from `rules/interactive-questions-sweep-matchers.md` (every option carries all three body segments; the `(Recommended)` label postfix bidirectionally binds the body `recommendation: recommended` value):

- `question:` `Spec phase complete. Are there any suggested improvements, ambiguities, contradictions to surface before handoff?`
- `header:` `End synthesis`
- `multiSelect:` `false`
- Option `All clear (Recommended)`:
  - `rationale:` No deferred concerns; the spec command's outputs are ready for handoff to /plan-generate.
  - `recommendation:` recommended — cites class 6 observed-state: the command's crystallization summary shows zero open unknowns and zero contradictions at the synthesis boundary.
  - `default-pointer:` no-default: user decision required (operator's final ratification surface; silent default would bypass the operator's judgment on long-lived spec content).
- Option `Surface findings`:
  - `rationale:` Operator has substantive concerns to raise before handoff; agent captures them inline in the synthesis record and routes to /plan-generate as input rather than as authoritative spec.
  - `recommendation:` acceptable
  - `default-pointer:` no-default: user decision required.
- Option `Defer findings`:
  - `rationale:` Operator notes findings but defers resolution to a later cycle; agent appends `[Deferral — out-of-scope: <description>; tracking: <PLAN-NOTES.md or follow-up issue>]` per `rules/disclosure-ledger.md`.
  - `recommendation:` acceptable
  - `default-pointer:` no-default: user decision required.

The selection routes the post-synthesis flow: `All clear` proceeds to G5 Manifest emission unchanged; `Surface findings` captures the findings inline at the synthesis record in PLAN-NOTES.md and re-runs Phases 4–6 on affected loci; `Defer findings` appends the deferral marker to the disclosure ledger and emits G5 with the deferral routed via the Manifest's `deferrals` field per `rules/disclosure-ledger.md`.

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

1. **Frontmatter.** `rg --no-heading -nP '^name: "plan-spec"$' commands/plan-spec.md` returns 1 hit; `rg --no-heading -nP '^description: .+$' commands/plan-spec.md` returns 1 hit with a non-empty description.
2. **Phase enumeration.** `rg --no-heading -nP '^### Phase [1-6] —' commands/plan-spec.md` returns 6 hits (one per transformation phase).
3. **Discipline enumeration.** `rg --no-heading -nP '^- \*\*D[1-9]0?' commands/plan-spec.md` returns at least 14 hits (D1–D4 operational + D1–D10 structured-inquiry disciplines).
4. **Gate enumeration.** `rg --no-heading -nP '\*\*G[0-5]\*\*' commands/plan-spec.md` returns 6 hits (G0–G5).
5. **Self-application attestation.** `/plan-spec --self-application-attestation` emits a PASS attestation per the §4.8.4 four-discipline invariant; the attestation lists each of the six conditions with a PASS verdict.
6. **Standalone-invocation attestation.** `/plan-spec --standalone <prose-path>` emits the Handoff Manifest with `downstream: none (standalone invocation)` per §4.8.6; no silent terminal-ness.
7. **Work-root naming attestation.** The Manifest's `repository` + `mission` fields are non-empty per the §1.5 INQ-WORKROOT-SCHEME ratification.

---

## Examples

### Example 1 — Greenfield Forge run

```text
$ /plan-spec ~/notes/migration-plan-draft.md --suite-name database-migration-v2

[Phase 1] Reading 12K-token prose source. Suite folder created at <project-root>/.apothem/plans/database-migration-v2/.
[Phase 1] Forge file initialized at <project-root>/.apothem/plans/database-migration-v2/_inputs/forge.md.
[Phase 2] Consideration pass — 38 items captured; G0 ◇ Consideration-Log-Complete satisfied.
[Phase 2] Tension surfaced (rollback-strategy ambiguity); structured inquiry fired at G3.
[Phase 3] Potency Map — 47 element/potent-form pairings; 0 unpaired.
[Phase 4] Preservation Audit — L1 PASS (124 distinctive phrases all grep-matched); L2 PASS (47 requirements operationally enforced); L3 PASS (12 ALL-CAPS / repeated-intensifier loci preserved).
[Phase 5] Expertise — 5 of 7 axs applied; 2 explicitly N/A-with-rationale.
[Phase 6] Question-Resolution Sweep — 6 questions across 4 gates; 0 P0-unresolved; 0 P1-unresolved.
[G4] Four-Discipline Invariant — PASS on all 6 conditions; promotion authorized.
[G4] Promoting forge.md → _spec/spec.md.
[G5] Handoff Manifest emitted at <project-root>/.apothem/plans/database-migration-v2/_inputs/handoff-manifest.yml; downstream: /plan-generate.
```

### Example 2 — Iterative refinement (`--refine-existing`)

```text
$ /plan-spec --refine-existing <project-root>/.apothem/plans/database-migration-v2

[Phase 1] Existing spec.md detected (1,247 lines). Treating as starting point.
[Phase 2] Re-consideration pass — 4 new items captured (delta against the prior Consideration Log).
[Phase 3] Re-pairing pass — 2 new potent-form pairings added.
[Phase 4] Preservation Audit re-run — L1 PASS preserved; L2 PASS preserved; L3 PASS preserved.
[Phase 5] Expertise delta — 1 newly-applicable axis surfaced.
[Phase 6] Question-Resolution Sweep — 2 new questions surfaced; 0 unresolved.
[G4] Invariant PASS; spec.md updated in place; forge.md not used (refinement mode).
[G5] Handoff Manifest re-emitted with incremented invocation_sequence.
```

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
- **§I.0.f Expertise** — D4 Seven Axs of Breadth applied with attestation.
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

## Bindings (§0.j five-direction)

- **Drives →** ● `commands/plan-generate.md` (the canonical downstream consumer; `/plan-generate` consumes the promoted `_spec/spec.md`). ● `{suite}/_spec/spec.md` (the principal artifact). ● `{suite}/_inputs/handoff-manifest.yml` (the G5 Handoff Manifest). ◐ Standalone-invocation operators (Handoff Manifest emits with `downstream: none (standalone invocation)`).
- **Satisfies →** ● `_spec/spec.md` §4.8 Appendix I (this command's canonical specification). ● D-16 (`/plan-spec` installation as Wave 18 deliverable). ● D-17 anti-waterfall decision (every operation is a disciplined sprint). ● `rules/interactive-questions.md` §1 canonical-channel obligation (every questionable routes through the structured-inquiry channel). ● `rules/context-management.md` §2.6.1 forge → spec lifecycle.
- **Established by ↑** ● `_spec/spec.md` §4.8.1–§4.8.9 (the canonical specification). ● The `src/apothem/commands/` cohort (this command joins it as the upstream entry to the `/plan` pipeline). ● D-16 + D-17 (the ratified locked decisions).
- **Gated by ←** ● Operator invocation with a prose source. ● `rules/interactive-questions.md` (every structured-inquiry invocation conforms). ● `rules/context-management.md` §2.6.1 (suite-locality invariant for `_inputs/`, `_outputs/`, and `_spec/` directories).
- **Cross-bound with ↔** ↔ `commands/plan-generate.md` (Forge → Generate handoff; `/plan-generate` consumes spec.md and produces the plan suite). ↔ `commands/plan-execute.md` (Generate → Execute handoff; spec.md fidelity preserved through the pipeline). ↔ `commands/plan-review.md` (Forge fidelity is reviewable via the Preservation Audit appendix). ↔ `rules/interactive-questions.md` (every structured-inquiry call obeys the canonical-channel rule). ↔ `rules/context-management.md` §2.6.1 (forge → spec lifecycle compliance).

## Installed Reference Paths

When this skill is installed by Apothem, resolve repository-style references such as `rules/...` under `<ROOT>`, `templates/...` and `hooks/...` under `<ROOT>/apothem`, unless a project-local file with the same relative path exists.
