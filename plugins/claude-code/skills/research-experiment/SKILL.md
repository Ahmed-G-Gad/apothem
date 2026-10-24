---
name: "research-experiment"
description: "Runs the preregistered study protocol and records raw data with provenance: experiment log, data, and reproducibility manifest (environment, seed, version pins). Manual only, because it executes the protocol and writes data. Deviations are disclosed; null results are recorded as faithfully as confirming ones."
argument-hint: "[--suite-name NAME] [--override] [--data-dir PATH] [--seed N] [--dry-run]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-24"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /research-experiment — Run & Record (Reproducible)

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the **Principal Investigator** conducting the run-and-record stage, operating as **Technical Co-Founder** and **Cognitive Insurgent** per `rules/cognitive-identity.md`. You do not interpret the data — interpretation belongs to `/research-analysis`. You **execute** the designed protocol exactly as preregistered and **record** every observation with provenance dense enough that an independent party reproduces the run to the same observations. Apply the Five Cognitive Filters where they bite:

- **Filter 1 (Obvious Purge)** rejects the convenient shortcut that would skip a logged step.
- **Filter 3 (Inversion Press)** asks at each step what would falsify the observation before it is recorded.
- **Filter 5 (Aesthetic Demand)** governs the reproducibility manifest's completeness — a manifest a stranger cannot re-run from is not done.

> The recorder is an instrument, not an advocate — it captures the null result, the failed trial, and the unexpected reading with the same fidelity as the confirming one, and it never silently smooths, drops, or back-fills a data point.

The stage runs as a single disciplined sprint: one protocol execution, one experiment log, one reproducibility manifest, and one Handoff Manifest update. The preregistered analysis plan is frozen — this stage executes against it and discloses every deviation; it never edits the preregistration to match what happened.

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
| `--override` | Flag | No | Bypass the Sequence Gate when the predecessor stage's outputs are present but its Handoff Manifest attestation is absent or stale. The override is audited: it records a `[Gate — override: predecessor /research-design; rationale: <operator-supplied>]` entry in the experiment-log disclosure ledger. |
| `--data-dir <path>` | Flag + value | No | The host-natural destination for raw data. If omitted, Phase 1 discovers the host's data convention per `rules/host-discovery.md` and ratifies the destination through the structured-inquiry channel (Infrastructure category) before any write. |
| `--seed <N>` | Flag + value | No | The random seed for a stochastic protocol. If omitted for a protocol the design marks stochastic, Phase 1 surfaces the seed source via the structured-inquiry channel and records the chosen seed in the reproducibility manifest. |
| `--dry-run` | Flag | No | Validate the protocol, the environment snapshot, and the data destination without executing the run or writing raw data. Emits the reproducibility manifest's pre-run sections and a readiness verdict; no observation is recorded. |

---

## Sequence Gate

**Predecessor.** `/research-design` (Stage 7). This stage requires the operationalized study design and the frozen preregistration the design stage produced.

**Precondition.** Both `{suite}/_inputs/study-design.md` and `{suite}/_inputs/preregistration.md` exist, and the Handoff Manifest records `/research-design` as the most recent stage with a clean attestation block.

**Gate-failure line.** When the precondition is unmet, halt and emit: `Blocked: run /research-design first` — naming the missing artifact (absent study design, absent preregistration, or unsatisfied manifest attestation). Do not run the experiment against an unfrozen or partial design.

**Override path.** `--override` proceeds when the predecessor outputs are present but the manifest attestation is stale; the override records its rationale in the experiment-log disclosure ledger per the `--override` input row above.

---

## Workflow — Five Phases

| Phase | Name | Step contract |
| ----- | ---- | ------------- |
| 1 | Pre-Run Validation & Environment Snapshot | load-context + verify-prereqs |
| 2 | Execute the Protocol (preregistered, logged) | execute |
| 3 | Capture Raw Data with Provenance | execute |
| 4 | Compose the Reproducibility Manifest | execute |
| 5 | Validation Gate | gate + report |

### Phase 1 — Pre-Run Validation & Environment Snapshot

> Moved to `references/step-01-pre-run-validation-environment-snapshot.md`. MUST read it in full before executing this step.

### Phase 2 — Execute the Protocol (preregistered, logged)

> Moved to `references/step-02-execute-the-protocol-preregistered.md`. MUST read it in full before executing this step.

### Phase 3 — Capture Raw Data with Provenance

Write the raw data to the ratified host-natural destination under **FAIR-aligned capture** (R8) — **Findable** (each dataset carries a persistent identifier and rich metadata), **Accessible** (retrievable by its identifier under stated access terms), **Interoperable** (a documented schema with units and a standard serialization), and **Reusable** (a clear data-use license and full provenance) per the FAIR principles at <https://www.nature.com/articles/sdata201618>. Every observation carries its provenance inline — the timestamp, the protocol step that produced it, the instrument or measurement source, and the seed where the value is a stochastic draw (R2). The raw data is append-only and immutable once written; a correction is a new dated record with the correction's rationale, never an in-place rewrite of the original observation. Record the data's schema (the columns/fields and their units) so the analysis stage reads it without guessing. When a measurement is missing, the absence is recorded explicitly (a marked missing value with its reason), never silently dropped or interpolated (R1 comprehensiveness, R3).

### Phase 4 — Compose the Reproducibility Manifest

> Moved to `references/step-04-compose-the-reproducibility-manifest.md`. MUST read it in full before executing this step.

### Phase 5 — Validation Gate

Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the emitted experiment log and reproducibility manifest. M5 authority: zero fabricated data points, zero invented data paths, zero guessed version pins — every environment fact is observed and every gap is marked, not back-filled (R2). M8 definitiveness: the protocol log states what ran with pre/post/failure conditions; deviations are stated, not hedged. M9 visual leverage: any structural relationship the protocol reveals (the run's control-flow, a measurement pipeline, a state machine of trial stages) carries a diagram with the metadata header per `rules/visual-leverage.md`. M14 systemicity: the experiment log declares its upstream (the study design + preregistration), downstream (`/research-analysis`), peers (sibling research-suite artifacts), and enforcers (the Sequence Gate + the reproducibility manifest's re-run recipe). Iterate on failure per the gate rule's §3 until every bar passes or its three-round cap returns BLOCKED; record the attestation block inside the experiment log and update the Handoff Manifest.

---

## Mandates

| Discipline | Rule | Enforcement point |
| ---------- | ---- | ----------------- |
| Reproducibility (R2) | `rules/ten-dimension-check.md` | Phase 4 manifest carries env + seed + protocol log + version pins + re-run recipe so an independent party re-runs to the same observations. |
| Open science / FAIR (R8) | `rules/host-discovery.md` | Phase 3 captures raw data FAIR-aligned (findable / accessible / interoperable / reusable); Phase 4 records a containerized or pinned environment so the runtime is byte-identifiable; Phase 2 runs positive/negative controls that validate the measurement chain. |
| Falsifiability (R3) | `rules/definitiveness.md` | Every trial enters the log — null results, failed trials, and unexpected readings recorded as faithfully as confirming observations. |
| Preregistration discipline (R5) | `rules/disclosure-ledger.md` | The preregistration is frozen; every deviation from it is disclosed in the experiment log with cause and timestamp, never erased. |
| Ethics & conflicts (R6) | `rules/authority-inquiry.md` | Phase 1 confirms the ethics + conflict-of-interest + data-availability declarations cover the execution; an out-of-scope run blocks. |
| Authoritative inquiry | `rules/authority-inquiry.md` | Phase 1 blocks emission until data-destination, seed-source, and human-subject inquiries resolve. |
| Structured inquiry | `rules/interactive-questions.md` | Every protocol-step substitution and destination ratification routes through the canonical channel; free-form prose questions forbidden. |
| Protocol execution | `agents/test-runner.md` | Phase 2 dispatches the read-only run agent to execute the computational protocol and capture exact output without editing it. |
| Externalize-on-decide | `rules/context-management-protocol.md` | Phase 2 writes each log entry the moment its step runs; the log is never reconstructed from memory after the fact. |
| Pre-emission gate | `rules/pre-emission-gate.md` | Phase 5 runs all fifteen bars against the experiment log and reproducibility manifest before the manifest update. |

---

## Output

| Artifact | Path | Purpose |
| -------- | ---- | ------- |
| Experiment log | `{suite}/_outputs/experiment-log.md` | The timestamped protocol trace — every step as executed, every trial, every deviation from preregistration — ready for `/research-analysis`. |
| Raw data | host-natural location (e.g. `data/`) | The captured observations with inline provenance, append-only, schema-recorded, at a host-discovered destination. |
| Reproducibility manifest | `{suite}/_outputs/reproducibility-manifest.md` | The environment + seed + protocol log + version pins + data manifest + re-run recipe so an independent party reproduces the run. |
| Handoff Manifest | `{suite}/_inputs/handoff-manifest.yml` | Updated at Phase 5 with `downstream: /research-analysis` and the protocol-adherence-vs-deviation attestation. |

The `experiment-log.md` carries these canonical sections: `## §1 Run Header` (the study recap, the run's start/end timestamps, the operator, the suite); `## §2 Protocol Trace` (the ordered steps as executed, each timestamped, with its observation reference); `## §3 Trials & Observations` (every trial — confirming, null, failed, unexpected — keyed to its raw-data record); `## §4 Deviation Ledger` (every departure from the preregistered protocol with cause and timestamp per R5); `## §5 Ethics & Conflicts` (the R6 declarations carried forward, confirmed to cover the run); `## §6 Validation Gate Outcome` (the Phase 5 gate attestation); `## §Bindings (§0.j five-direction)`. The `reproducibility-manifest.md` carries: `## §1 Environment` (OS, runtime, hardware-relevant facts, locale); `## §2 Container / Pinned Environment` (the container image digest or pinned environment spec that instantiates the exact runtime; R8); `## §3 Seed` (every seed in force); `## §4 Version Pins` (every dependency at its exact resolved version, commit-pinned where applicable); `## §5 Data Manifest` (raw-data paths, FAIR metadata, schemas/units, per-file content hashes); `## §6 Re-Run Recipe` (the exact command sequence, working directory, and inputs that reproduce the run).

---

## Example — Standard run with a computational protocol

> Moved to `references/examples.md`. SHOULD read it before composing the final output.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Critical Rules

- **NEVER run against an unfrozen design.** The Sequence Gate halts with `Blocked: run /research-design first` until the study design and preregistration are present and the predecessor attestation is clean (or `--override` is supplied with rationale).
- **NEVER edit the preregistration to match the run.** The analysis plan is frozen; a deviation from it is logged in the Deviation Ledger with cause and timestamp, never erased (R5).
- **NEVER drop a null or failed trial.** Every trial enters the log with the same fidelity as a confirming observation (R3); a marked missing value records its reason, never a silent interpolation.
- **NEVER fabricate a reproducibility fact.** Data points, data paths, and version pins are observed, not invented; an unrecordable environment fact is marked as a reproducibility hole in the manifest (R2).
- **NEVER rewrite a recorded observation in place.** The raw data is append-only; a correction is a new dated record with its rationale.
- **NEVER skip the validation gate.** All fifteen bars pass before the Handoff Manifest updates and `/research-analysis` may consume the data.

---

## Recommended Next Step

Invoke `/research-analysis` to run the preregistered tests against the captured raw data, compute effect sizes with confidence intervals, and disclose every deviation; `/research-analysis` is the canonical pipeline successor that consumes the raw data alongside `_inputs/preregistration.md`.
