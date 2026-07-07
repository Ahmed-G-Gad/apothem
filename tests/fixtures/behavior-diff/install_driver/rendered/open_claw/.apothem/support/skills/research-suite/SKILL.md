---
name: "research-suite"
version: "0.1.0"
updated: "2026-06-16"
description: "Research Suite template — matched when the request is a structured research engagement from problem ideation and question formulation, conceptual / theoretical framing, evidence-gathering across primary sources, literature synthesis with an explicit gap statement, proposal authoring, falsifiable study design and preregistration, reproducible experiment execution, preregistered statistical analysis, paper authoring, peer-review-grade adversarial review, venue-formatted publication, or post-acceptance dissemination and impact; consumed by the /research pipeline commands (ideate, spec, theory, sources, synthesis, proposal, design, experiment, analysis, paper, review, publish, disseminate). Houses the canonical surface that defines research-suite structure, the ten rigor mandates (R1–R10), the thirteen-stage research lifecycle, and the Principal-Investigator Framework. Not directly user-invocable; the consuming /research pipeline stages resolve the surface by path."
archetype: "workflow-template"
userInvocable: false
disable-model-invocation: true
allowed-tools: "Read"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

> **Structural Note:** This skill is a *knowledge surface*, not a procedural skill. It deliberately omits the standard SKILL.md Detection-Signal / numbered-Procedure structure because it houses a reference surface, not a reusable technique. The `/research` pipeline stages consume it by **reading** its surface directly — never by following a procedure. The deviation is intentional and mirrors the structural sibling `skills/plan-suite/SKILL.md`.

Houses the Research Suite knowledge surface — the canonical specification every `/research` pipeline command resolves by path (`/research-ideate`, `/research-spec`, `/research-theory`, `/research-sources`, `/research-synthesis`, `/research-proposal`, `/research-design`, `/research-experiment`, `/research-analysis`, `/research-paper`, `/research-review`, `/research-publish`, `/research-disseminate`). It defines four things the stages share: the **research-suite directory structure**, the **ten rigor mandates (R1–R10)**, the **thirteen-stage lifecycle**, and the **Principal-Investigator Framework** the stages operate under. A single canonical surface guarantees every stage reads the same mandate IDs and lifecycle order — so cross-stage references never drift.

## Contents

- `research-template.md` — Full template defining research-suite artifact structure, the rigor-mandate checklist (R1–R10), the lifecycle stage skeleton, and the Principal-Investigator Framework.
- `references/` — Progressively-disclosed detail surfaces (loaded only when a consuming stage needs the section):
  - [`references/directory-structure.md`](references/directory-structure.md) — the research-suite directory-structure table (where every artifact lands).
  - [`references/rigor-mandates.md`](references/rigor-mandates.md) — the ten rigor mandates (R1–R10) in full.
  - [`references/lifecycle.md`](references/lifecycle.md) — the thirteen-stage lifecycle + the per-stage invoking-surfaces table.
  - [`references/principal-investigator-framework.md`](references/principal-investigator-framework.md) — the Principal-Investigator (PI) lens and its six commitments.
  - [`references/empirical-comparison-rigor.md`](references/empirical-comparison-rigor.md) — the statistical floor a head-to-head empirical comparison meets (operationalizes R7).
  - [`references/comparator-provenance.md`](references/comparator-provenance.md) — sourcing and verifying the executed baselines a comparison runs against (operationalizes R1 / R4).
  - [`references/experiment-program-scaffold.md`](references/experiment-program-scaffold.md) — the per-deliverable setup / pilot / comparison / ablation / sensitivity layout (operationalizes R2 / R5).
  - [`references/compute-utilization.md`](references/compute-utilization.md) — budget parity, tuning on disjoint splits, and safe parallelization (operationalizes R2).
  - [`references/autonomous-experiment-loop.md`](references/autonomous-experiment-loop.md) — the opt-in, default-off unattended propose → trial → retain-or-revert loop (operationalizes R2 / R5 / R7).
  - [`references/advancement-gate.md`](references/advancement-gate.md) — the definition-of-done advance gate and its auditable runbook (operationalizes R7 / R5).
  - [`references/blinding-and-disclosure.md`](references/blinding-and-disclosure.md) — anonymization and staged-disclosure / double-blind readiness (operationalizes R6).

## Reference Surfaces

This router defines four foundational shared surfaces; each is progressively
disclosed through a bundled reference file, so the entry-point stays tight and a
consuming stage loads a section only when it needs it.

- **Research-suite directory structure** — where every working artifact and deliverable lands. See [`references/directory-structure.md`](references/directory-structure.md).
- **The ten rigor mandates (R1–R10)** — the research-suite floor every stage attests. See [`references/rigor-mandates.md`](references/rigor-mandates.md).
- **The thirteen-stage research lifecycle** — the fixed stage order + per-stage invoking-surfaces table. See [`references/lifecycle.md`](references/lifecycle.md).
- **The Principal-Investigator (PI) Framework** — the evidentiary-stewardship lens every stage operates under. See [`references/principal-investigator-framework.md`](references/principal-investigator-framework.md).

Seven operationalizing surfaces add empirical-experimentation detail to the
existing mandates — each operationalizes an R-mandate and introduces no new one
(R1–R10 stays a closed set of ten); a stage loads one only when its work needs
that detail:

- **Empirical-comparison rigor floor** — the repetition regime, reporting statistics, figures, and significance-and-effect-size protocol a head-to-head comparison meets (operationalizes R7). See [`references/empirical-comparison-rigor.md`](references/empirical-comparison-rigor.md).
- **Comparator provenance** — selecting, verifying, and recording the executed baselines a comparison runs against (operationalizes R1 / R4). See [`references/comparator-provenance.md`](references/comparator-provenance.md).
- **Experiment-program scaffold** — the per-deliverable setup / pilot / comparison / ablation / sensitivity layout (operationalizes R2 / R5). See [`references/experiment-program-scaffold.md`](references/experiment-program-scaffold.md).
- **Compute-utilization plan** — unified budget parity, tuning on disjoint splits, and safe parallelization (operationalizes R2). See [`references/compute-utilization.md`](references/compute-utilization.md).
- **Autonomous experiment loop** — the opt-in, default-off unattended propose → trial → retain-or-revert loop (operationalizes R2 / R5 / R7). See [`references/autonomous-experiment-loop.md`](references/autonomous-experiment-loop.md).
- **Advancement gate** — the definition-of-done advance gate and its auditable runbook (operationalizes R7 / R5). See [`references/advancement-gate.md`](references/advancement-gate.md).
- **Blinding & staged disclosure** — anonymization and double-blind readiness (operationalizes R6). See [`references/blinding-and-disclosure.md`](references/blinding-and-disclosure.md).

A single canonical surface guarantees every stage reads the same mandate IDs
and lifecycle order — so cross-stage references never drift.

## Auto-Load Contract

When any `/research-<stage>` command is invoked **cold** — without its predecessor stages' context explicitly loaded into the session — the consuming stage resolves this skill before executing, so the full pipeline context loads uniformly and no stage assumes manually-preloaded state.

**Cold-invocation trigger.** A `/research-<stage>` invocation is cold when the session carries none of: a resolved `_spec/research-spec.md`, a loaded research suite (`_inputs/source-ledger.md` / `_inputs/synthesis.md` / `_inputs/handoff-manifest.yml`), or a prior `/research-<stage>` turn in the same session. On a cold invocation the stage reads this skill first; on a warm invocation (predecessor context already loaded) the read is a no-op refresh.

## Non-Goals

The skill is a knowledge surface with a deliberately narrow surface. It is NOT:

- **Not a one-shot research engagement.** The surface defines research-suite structure; it does not gather sources, fact-check claims, or synthesize a report directly. Source gathering and synthesis are the consuming `/research-sources` and `/research-synthesis` stages' responsibility, dispatching the `research-scout` agent and the `multi-source-research` + `source-synthesis` skills.
- **Not a plan-generation pipeline.** The research-suite surface consumes a research question and emits research artifacts; it does not decompose an engagement into execution phases. Plan decomposition is the `/plan` pipeline's responsibility, surfaced at `skills/plan-suite/SKILL.md`.
- **Not a documentation generator.** Research-suite working artifacts (`research-spec.md`, `source-ledger.md`, `synthesis.md`, `study-design.md`, `analysis.md`) are working documents driving the engagement; they are not user-facing documentation. The paper deliverable lands at a host-natural location; user-facing docs land at `site/content/docs/` and the host's documentation surfaces.
- **Not a registry.** The surface path is declared in `CLAUDE.md` and resolved path-based; no auto-discovery, no fallback registry, no plug-in-style extension.
- **Not stateful across sessions.** The skill carries no runtime state; each `/research` stage invocation re-reads the surface afresh and durable research-suite state lives in the per-suite folder under `<project-root>/.apothem/plans/{suite}/`.

## Invoking Surfaces

The thirteen `/research` pipeline stages consume this skill's
`research-template.md` by direct path resolution; no agent invokes the skill
directly. The per-stage consumption-point table (which command reads which
R-mandates at Step 0) is at
[`references/lifecycle.md`](references/lifecycle.md) § Invoking Surfaces,
beside the lifecycle it pairs with.

## Principal-Investigator Framework

Every consuming `/research` stage operates under the Principal-Investigator
(PI) lens — **steward of the evidentiary record, not the advocate of a
conclusion** — layered atop the Technical Co-Founder and Cognitive Insurgent
identities at `rules/cognitive-identity.md`. The six PI commitments
(evidence-over-assertion, refute-by-default, preregistration-as-contract,
reproducibility-as-deliverable, ethics-and-conflicts-surfaced, statistical
honesty) and the axs-of-inquiry frame are at
[`references/principal-investigator-framework.md`](references/principal-investigator-framework.md).

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror, adapted to this skill's passive knowledge-surface role so consuming `/research` pipeline stages inherit a coherent posture on surface resolution.

### Refusal & Escalation

REFUSE any consumer request that asks the skill to act outside its knowledge-surface mission — source gathering, synthesis, analysis, paper authoring, fixes. Refusal is explicit: name what was refused, name the mission boundary the request crossed, and route the consumer back to the appropriate `/research` stage via the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). When the surface file itself is missing, malformed, or unreachable, the skill STOPs and surfaces the recovery options listed in the Resolution & Recovery section below — it does NOT regenerate the surface from training-time memory or scaffold a partial replacement.

### Output Surface

The skill emits **no artifacts of its own**; it is a passive surface read by consuming commands. Research-suite working artifacts that the consumers emit while resolving this surface land at `<project-root>/.apothem/plans/{suite}/` per the suite-locality invariant at `rules/context-management.md` §2.6.1 — gitignored per the canonical `.gitignore` snippet. Deliverables (the paper, raw data, figures, code) land at host-natural locations per `rules/host-discovery.md` — NEVER inside `.apothem/plans/`. NEVER write a working artifact outside the suite folder, NEVER write to `<project-root>/.apothem/plans/` from a downstream-project context, and NEVER write to any global-ecosystem location. Per `rules/operational-mandates.md` CM-7, deliverable artifacts contain ZERO research-suite-internal references — natural domain language only.

### File-Authoring Contract

The skill is `allowed-tools: "Read"` — it authors no files directly. The contract applies to consuming `/research` pipeline stages: every NEW deliverable file the consumer creates routes through `scripts/inject-header.{sh,py}` so the canonical authorship-header banner — the byte-exact fixture at `src/apothem/schemas/authorship-header.txt` (the single source of truth) — is injected at the head; the injector is idempotent and detects the filetype variant automatically. The exempt classes (LICENSE, JSON configuration files, lockfiles, generated assets, vendored trees, `.audit/` ephemera, `<project-root>/.apothem/plans/` ephemera, `.keep` / `.gitkeep` markers, binary files) are enumerated at `src/apothem/schemas/header-exceptions.txt`. Research-suite working artifacts under `.apothem/plans/{suite}/` are header-exempt under the `.apothem/plans/**` exception class. The header-inject-guard hook at `hooks/messages/pretooluse-{write,edit}-header-guard.md` enforces the contract at every Write / Edit invocation made by the consuming command.

### Structured Inquiry on Ambiguity

When a consuming `/research` stage reaches a decision in any of the seven authoritative-data categories per `rules/authority-inquiry.md` — identity (study authors, contributors), scope direction (research boundary, time horizon, target population), preference (instruments, statistical method, venue), security (data-privacy handling, deny rules, allowed network egress), naming of public surfaces (suite name, hypothesis identifiers, the paper title), infrastructure endpoints (data sources, compute), version pins (dataset version, tool pins) — and the host is silent, the consumer routes the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data — a fabricated citation violates R4 outright. Required-category inquiries (identity, scope direction, security posture, naming of public surfaces) block emission until answered; optional inquiries fall back to the recommended option and record the fallback as a finding. **Per-file destructive-op floor.** Every delete / rename / move / overwrite-without-retention / revert-uncommitted operation the consumer performs against an existing research-suite artifact routes through the structured-inquiry channel on a per-file basis per `rules/interactive-questions.md` §6 — one invocation per file, every time, no `multiSelect` batching across files, every option's `default-pointer:` carries the verbatim `no-default: user decision required` marker.

## Conformity Posture

The three-element conformity discipline applies to **consumers** of this surface — every `/research` stage invocation that resolves the surface inherits the obligations below — and is reproduced here so consumers reach the discipline at the same surface they reach the knowledge surface.

**Discover-don't-assume preamble (M1).** Before any `/research` stage populates a deliverable from this surface, the consuming command walks the host's ratified source-of-truth files per `rules/host-discovery.md` — the host's documentation layout, data-directory convention, figure/table naming, citation-style convention, and any host-discovered analog of the rigor mandates. Honor discoveries; never silently install a research convention where the host has its own.

**Authority inquiry surface (M5).** Per the Structured Inquiry on Ambiguity stanza above; this anchor binds the M5 discipline to the seven-category inquiry catalog at `rules/authority-inquiry-categories.md` §1.

**Pre-emission self-check (M4).** Every research-suite artifact emitted from this surface passes the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` before the consuming `/research` stage considers the artifact complete, with the applicable R1–R10 mandates attested in the same trace. The gate's attestation lands in the artifact's working trace. Mechanical-fraction bars run via the per-bar matchers at `conformity/*-grep.py`; reasoned bars are evaluated inline by the consuming command.

## Resolution & Recovery

Not directly invocable. The `/research` pipeline stages resolve this surface via the path declared in `CLAUDE.md` (currently `skills/research-suite/research-template.md`). Resolution is path-based, not registry-based — there is no fallback registry and no auto-discovery; the path must match exactly.

**Fallback handling.** If the surface file is missing, malformed (corrupted YAML/markdown that prevents parsing of the R1–R10 / lifecycle sections), or unreachable: STOP and inform the user. Do NOT attempt to regenerate the surface from training-time memory or scaffold a partial replacement — `/research` pipeline stages depend on the canonical R-mandate IDs and lifecycle order, and any divergence silently corrupts every cross-reference downstream. Recovery options surfaced via the structured-inquiry channel: (a) re-clone or re-install the apothem ecosystem from version control (Recommended); (b) restore the surface file from a backup; (c) point commands at a known-good surface via an explicit override path.

**Version compatibility.** Commands declare `Requires surface v0.1.0+`. Bump the surface's version field when changes alter R-mandate or lifecycle semantics; consumers refuse to operate against an older major version than they expect.

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-16 %%
%% provenance: hand-authored from skills/research-suite/SKILL.md §Thirteen-Stage Research Lifecycle %%
%% cross-reference: skills/research-suite/SKILL.md §Thirteen-Stage Research Lifecycle %%
flowchart TD
    Start[/research-stage invoked] --> Cold{Cold invocation?}
    Cold -->|no| Warm[Warm refresh · proceed on loaded context]
    Cold -->|yes| Resolve[Resolve research-template.md by path]
    Resolve --> Found{Surface resolves?}
    Found -->|no| Stop[STOP · surface recovery options via structured inquiry]
    Found -->|yes| Stage{Which stage?}
    Stage -->|ideate| S0[research-ideate · problem formulation + question generation]
    Stage -->|spec| S1[research-spec · question + falsifiable hypotheses]
    Stage -->|theory| ST[research-theory · conceptual framework + theory-of-change]
    Stage -->|sources| S2[research-sources · ledger + per-source extractions]
    Stage -->|synthesis| S3[research-synthesis · SOTA map + gap statement]
    Stage -->|proposal| SP[research-proposal · objectives + SMART aims + impact pathway]
    Stage -->|design| S4[research-design · study design + preregistration]
    Stage -->|experiment| S5[research-experiment · log + reproducibility manifest]
    Stage -->|analysis| S6[research-analysis · preregistered tests + effect sizes]
    Stage -->|paper| S7[research-paper · deliverable with verified citations]
    Stage -->|review| S8[research-review · adversarial reviewer scorecard]
    Stage -->|publish| S9[research-publish · submission package + FAIR deposit]
    Stage -->|disseminate| SD[research-disseminate · dissemination + impact + altmetrics]
    Warm --> Stage
    S0 --> Gate[Honor R1-R10 · pre-emission gate · emit + handoff]
    S1 --> Gate
    ST --> Gate
    S2 --> Gate
    S3 --> Gate
    SP --> Gate
    S4 --> Gate
    S5 --> Gate
    S6 --> Gate
    S7 --> Gate
    S8 --> Gate
    S9 --> Gate
    SD --> Gate
```

## Recommended Next Step

Invoke `/research-ideate` to consume this skill's `research-template.md` and formulate the problem space into `_inputs/ideation.md` with candidate questions and an invalidated-prior-hypothesis scan. `/research-ideate` is the canonical entry stage that opens the thirteen-stage lifecycle and emits the first Handoff Manifest the downstream stages chain against.

## Bindings (§0.j five-direction)

- **Drives →** ● Every `/research` stage's resolution of the research surface at `skills/research-suite/research-template.md`. ● Every R1–R10 cross-reference resolution across the thirteen `/research` pipeline stages. ● Every research-suite emission's structural conformity (the surface is the canonical schema). ◐ The version-compatibility gate (`Requires surface v0.1.0+`).
- **Satisfies →** ● `CLAUDE.md` Source Layout row "research-suite". ● `CLAUDE.md` Project Purpose (the thirteen `/research` pipeline stages consume this skill's surface).
- **Established by ↑** ● `CLAUDE.md` Source Layout. ● `CLAUDE.md` Project Purpose (the path declaration `skills/research-suite/research-template.md`). ● `CLAUDE.md` Source Layout (skills/ class declaration with the folder-with-`SKILL.md` convention).
- **Gated by ←** ● The harness's Read tool surface (commands resolve the surface by reading the canonical path). ● The presence of the surface file at the canonical path (path-based resolution per the Resolution & Recovery clause).
- **Cross-bound with ↔** ↔ `commands/research-ideate.md` + `commands/research-spec.md` + `commands/research-theory.md` + `commands/research-sources.md` + `commands/research-synthesis.md` + `commands/research-proposal.md` + `commands/research-design.md` + `commands/research-experiment.md` + `commands/research-analysis.md` + `commands/research-paper.md` + `commands/research-review.md` + `commands/research-publish.md` + `commands/research-disseminate.md` (the thirteen consumer commands). ↔ `commands/research.md` (the wrapped dynamic workflow over the thirteen stages). ↔ `skills/plan-suite/SKILL.md` (the structural sibling this surface mirrors). ↔ `skills/multi-source-research/SKILL.md` + `skills/source-synthesis/SKILL.md` + `agents/research-scout.md` + `agents/fact-checker.md` (the discovery / extraction / synthesis / verification surfaces the stages dispatch). ↔ [`references/empirical-comparison-rigor.md`](references/empirical-comparison-rigor.md) + [`references/comparator-provenance.md`](references/comparator-provenance.md) + [`references/experiment-program-scaffold.md`](references/experiment-program-scaffold.md) + [`references/compute-utilization.md`](references/compute-utilization.md) + [`references/autonomous-experiment-loop.md`](references/autonomous-experiment-loop.md) + [`references/advancement-gate.md`](references/advancement-gate.md) + [`references/blinding-and-disclosure.md`](references/blinding-and-disclosure.md) (the seven operationalizing detail surfaces the empirical stages load at Step 0).
