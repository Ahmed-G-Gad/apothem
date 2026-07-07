---
name: "interactive-questions-canonical-shapes"
description: "Path-filtered companion rule carrying the canonical invocation shapes, worked examples, recommendation-taxonomy details, harness-fallback shape, destructive-op canonical option-set templates, and default-pointer worked examples for the parent `interactive-questions.md` rule; demand-loaded on path match."
pathFilter: "**/commands/**/*.md, **/rules/**/*.md, **/skills/**/*.md, **/agents/**/*.md, **/hooks/**/*.md"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Interactive-Questions Canonical Shapes (Companion Sub-Rule)

## Purpose

Detail-tier companion to `rules/interactive-questions.md`: the canonical worked examples (single-select / multi-select), the three-segment annotation schema with label-postfix specification, the recommendation taxonomy (driver classes, vague-rationale forbid list, downgrade path, extension protocol), the harness-fallback specification (detection, prose shape, explicit-flag mandate, sole-permitted-free-form invariant), the four destructive-op option-set templates (Delete / Rename / Move / Revert), and the default-pointer worked examples. Path-filtered to artifact classes that author structured-inquiry invocations or fallback prompts. The parent rule owns the canonical-channel obligation, structured-inquiry shape table, section anchors, seriousness scaling, and CM-2 extension binding; this companion owns the worked examples and full schema bodies.

## Obligations

### 1. Worked Examples — Canonical Invocations

#### 1.1 Worked Example — Single-Select

Scenario: a prose-refinement workflow has completed signal crystallization and asks the operator whether the consolidated prose is ready to promote, or whether sections should iterate further. Three mutually-exclusive outcomes; the operator's pick is the sole gate on promotion.

```yaml
question:     Is the consolidated prose ready to promote, or should it iterate further?
header:       Prose output
multiSelect:  false
options:
  - label:    Accept (Recommended)
    description:
      rationale:         The prose meets the specification bar; promotion writes the output to the authored-specification path and closes the crystallization loop.
      recommendation:    recommended — the crystallization summary shows zero open unknowns and zero contradictions.
      default-pointer:   Accept — safe because the output is written to a versioned path and can be regenerated from the signal inventory.
  - label:    Iterate
    description:
      rationale:         Specific sections need surgical refinement before promotion; the rest of the draft is preserved.
      recommendation:    acceptable
      default-pointer:   Accept — the crystallization summary does not flag any section as weak; Iterate is offered for operator-driven refinement, not as the default.
  - label:    Reject
    description:
      rationale:         The draft is not salvageable; restart preserving only the raw input.
      recommendation:    discouraged — the crystallization check reports more than 50% signal capture, so iteration is viable.
      default-pointer:   Accept — Reject should be chosen only when the draft is fundamentally unsalvageable, which the crystallization check does not indicate here.
```

Exactly one option carries the ` (Recommended)` label postfix, bidirectionally bound to the `recommendation: recommended` body value on the same option per §2.

#### 1.2 Worked Example — Multi-Select

Scenario: an ecosystem-audit triage has surfaced four optional tooling components for the next release. Any combination is admissible — the release does not force exclusivity. Multi-select.

```yaml
question:     Which auxiliary tooling should ship with this release?
header:       Aux tools
multiSelect:  true
options:
  - label:    Migration helper (Recommended)
    description:
      rationale:         Automates schema upgrades for long-running deployments.
      recommendation:    recommended — 40% of active deployments still run the pre-migration schema per the telemetry dashboard.
      default-pointer:   no-default: user decision required.
  - label:    Admin dashboard
    description:
      rationale:         Web UI for runtime inspection; not required for headless deployments.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required.
  - label:    Metrics exporter
    description:
      rationale:         Exposes runtime metrics on a standard scrape endpoint; useful only when a metrics sink is already deployed.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required.
  - label:    Audit log shipper (Recommended)
    description:
      rationale:         Streams audit events to a downstream log destination; required only in regulated-deployment variants.
      recommendation:    recommended — two regulated deployments already require exportable audit trails per the release-readiness ledger.
      default-pointer:   no-default: user decision required.
```

Multi-select questions MAY carry more than one ` (Recommended)` label postfix when several options are independently recommended and the operator may select all of them. The label/body bind still applies per option: every `recommendation: recommended` option carries the postfix, no non-recommended option carries it. Multi-select questions carry `default-pointer: no-default` on every option when the question has no canonical subset-default — the operator's pick is the sole source of truth. When a canonical subset-default exists (e.g., a known-good default tool set), every option's `default-pointer:` names the same subset so the question stays internally consistent.

### 2. Three-Segment Option Annotation — Full Schema

Every option's description body contains exactly three segments, in fixed order, separated by newlines or period-space:

1. **rationale:** one sentence. What this option means and its immediate effect on ecosystem state. No forward-looking promises; only the direct, observable consequence.
2. **recommendation:** one value from the closed taxonomy, optionally followed by a concrete-driver why-clause (required when the value is non-neutral per §3):
   - `recommended` — the operator is advised to pick this.
   - `acceptable` — valid choice; the operator may pick freely.
   - `discouraged` — valid but the rationale makes it structurally inferior for the situation.
   - `destructive-no-default` — the option represents an irreversible operation; no default is admissible.
3. **default-pointer:** names the safe default with rationale, OR explicitly `no-default: user decision required`. Destructive operations always use the `no-default` form per §6.

A fifth taxonomy value is admissible only via the §3.3 extension protocol; ad-hoc values are non-compliant.

At the label level, one marker is permitted: ` (Recommended)` (single leading space) MAY be appended to the label of the option whose body `recommendation:` value is exactly `recommended`. Bidirectional bind — the label carries the marker iff the body says `recommended`. No option carries more than one marker; no two options in the same question carry it — in a single-select (`multiSelect: false`) question. A `multiSelect: true` question MAY carry the marker on more than one option per §2.1 (each independently-recommended option carries its own postfix); see the §1.2 multi-select worked example. The marker lives SOLELY in the `label`; it MUST NOT appear anywhere in the option body (`rationale:` / `recommendation:` / `default-pointer:` narrative). The body carries verifiable concrete-driver evidence per §3.2, never the postfix string.

#### 2.1 Label Postfix Convention — Formal Specification

The label postfix is a positive-highlight marker that draws the operator's attention to the recommended path without competing for visual weight across the rest of the option set.

| Rule | Specification |
|------|---------------|
| Postfix string | Literal `(Recommended)` — the past-participle `Recommended` wrapped in parentheses, matching the native tool schema's own recommended-option convention. The canonical form is capital-`R` `(Recommended)`, recognized case-correctly. No abbreviations (`(Rec)`, `(R)`), no variants (`(recommend)`, the lowercase `(recommended)`, `[Recommended]` square-bracketed), no translation. |
| Separator | Exactly one space between the domain label and the opening parenthesis. `Accept (Recommended)` is compliant; `Accept(Recommended)` and `Accept  (Recommended)` are not. |
| Placement | End of the `label` field. No trailing whitespace, no trailing punctuation after the closing parenthesis. |
| Trigger condition | The option's body `recommendation:` value is exactly the string `recommended`. No other taxonomy value triggers the postfix; `acceptable`, `discouraged`, and `destructive-no-default` carry the body segment only. |
| Per-invocation cardinality | `multiSelect: false` invocations allow at most one postfix, since the choices are mutually exclusive. `multiSelect: true` invocations may carry one or more postfixes when multiple options are independently recommended and can be selected together. An invocation with zero recommended options (all `acceptable`/`discouraged`/`destructive-no-default`) carries zero postfixes and is compliant when no option dominates. |
| Bidirectional bind | If the label carries `(Recommended)`, the body `recommendation:` value MUST be exactly `recommended`. If the body value is exactly `recommended`, the label MAY carry `(Recommended)` — in practice, the label SHOULD carry the postfix on the recommended option to realize the positive-highlight intent. The H6 heuristic flags label↔body mismatches in both directions. |
| Label-only placement | The `(Recommended)` (and the prose-and-document `**Recommended**`) marker lives SOLELY in the `label`. It MUST NOT appear in any body segment — not in `rationale:`, not in `recommendation:`, not in `default-pointer:`. The body's `recommendation:` segment carries the closed-taxonomy value plus a verifiable concrete-driver why-clause per §3.2, never the marker string. A marker string surfacing inside a body segment is a `narrative-marker-leak` — the H6 matcher flags it as a finding (`conformity/option_annotation_grep.py`). |
| Multi-select cardinality | A `multiSelect: true` question MAY carry the marker on more than one option — one postfix per independently-recommended option whose body value is exactly `recommended`. Only `multiSelect: false` questions are capped at a single recommended option. The §1.2 multi-select worked example is the canonical multiple-recommended shape. |

##### 2.1.1 Runtime Call-Time Validator

The static H4–H7 sweep (`rules/interactive-questions-sweep-matchers.md`) checks committed `*.md` artifacts; it does NOT see the live `AskUserQuestion` tool payload at the moment the agent asks the operator. The runtime PreToolUse `AskUserQuestion` validator (`hooks/askuserquestion_validator.py`, dispatch-routed via the `pretooluse-askuserquestion-recommended` message basename and persisting plugin-alone through `_PLUGIN_HOOK_ENTRIES` in `lib/plugin_tree.py`) closes that call-time gap. It inspects the live `questions` array — each question's `options[].label` and `multiSelect` — and validates the §2.1 postfix specification against the payload directly, reusing the canonical marker forms from `conformity/option_annotation_grep.py`.

The validator checks two finding classes:

- **Well-formedness (block-eligible under the strict opt-in)** — objectively decidable from the payload: a banned lowercase `(recommended)` (non-canonical case), a non-canonical bracket/spacing form (`[Recommended]`, `(Rec)`, `(Recommended )`), the marker on a clearly-destructive option label (contradicts the §5.8 no-default floor for irreversible operations), and more than one marker on a `multiSelect: false` question (single-select multi-recommended).
- **Nudge (advisory only — never blocks)** — a `multiSelect: false` question with two or more substantive options and zero markers is *advised* to mark its recommended option. Because the native payload carries no separate "recommended" field — the marker IS the only signal of which option is recommended — a missing marker cannot be proven a defect at runtime; forcing a recommendation to exist remains a behavioral-convention obligation, surfaced here only as a heuristic nudge.

The validator is advisory by default (a `systemMessage`; the question proceeds) and escalates well-formedness findings — never the nudge — to a `decision: block` under the repo's strict opt-in (`APOTHEM_CONFORMITY_STRICT=1` or `--strict`, mirroring `conformity/gate.py`). It is fail-open: any exception yields an allow envelope, so a validator error never crashes the operator's question.

#### 2.2 Invariants — Failure Modes

The heuristic sweep (`rules/interactive-questions-sweep-matchers.md`) detects these as HIGH-severity gate findings:

1. **Body-segment omission (H4).** An option's `description` lacks any of the three required segments (`rationale:`, `recommendation:`, `default-pointer:`). Every option carries all three regardless of taxonomy value.
2. **Missing label postfix (H6, body→label direction).** An option's body `recommendation:` value is exactly `recommended` but the label does not end with ` (Recommended)`. Bidirectional bind violated.
3. **Spurious label postfix (H6, label→body direction).** An option's label ends with ` (Recommended)` but the body `recommendation:` value is not `recommended`. Bidirectional bind violated; the lowercase ` (recommended)` form is itself a non-canonical-case violation.
4. **Single-select multi-postfix (H6, cardinality direction).** A `multiSelect: false` invocation has more than one recommended postfix. The mutually-exclusive shape cannot recommend multiple choices.

Two related failure modes anchor to adjacent subsections:

- **Non-neutral recommendation without concrete driver (H5)** — flagged per §3.2's concrete-driver citation requirement.
- **Destructive op without `no-default` floor (H7)** — flagged per §5.2's default floor and §6's default-pointer convention.

#### 2.3 Worked Examples — Anchor

The canonical worked examples for the annotation schema are §1.1 (single-select) and §1.2 (multi-select). §4.2 shows the same schema rendered in fallback prose form; §5.4–§5.7 show it applied to destructive-op canonical option sets. Downstream artifacts copy any of these fenced blocks as invocation templates.

### 3. Recommendation Taxonomy

#### 3.1 Closed Four-Value Set

The closed taxonomy is `{recommended, acceptable, discouraged, destructive-no-default}`. Every `recommendation:` body segment resolves to exactly one value from the set.

#### 3.2 Concrete-Driver Citation Requirement

Every non-neutral recommendation (`recommended`, `discouraged`, `destructive-no-default`) cites at least one concrete driver in its why-clause. The neutral value `acceptable` requires no why-clause but may carry one.

##### 3.2.1 Driver Taxonomy

A concrete driver is one of six classes:

1. **Locked decision** — a previously-resolved decision referenced by its identifier (e.g., a plan-suite decision-log row, an RFC resolution, a design-review outcome). The citation is the identifier plus the anchor (e.g., `D-7` in the plan-suite decision log, or a section pointer in the design-review minute).
2. **Named risk** — a risk the ecosystem has cataloged with an identifier and a mitigation path (e.g., an entry in a risk register). The citation is the identifier.
3. **Named constraint** — a constraint the ecosystem has declared with an identifier (e.g., a non-negotiable invariant, a compliance requirement, an SLA clause). The citation is the identifier.
4. **Open-question posture** — a decision the operator has deferred or not yet resolved, referenced by its identifier. The citation is the identifier and a note on the posture's current state.
5. **Rule citation** — a specific rule with an explicit path and section anchor (e.g., `rules/context-management.md §2.6.1`). The citation is the full rule-file path plus the section anchor that states the binding clause.
6. **Observed ecosystem state** — a measured fact (metric, file contents, gate result, log entry, dependency-graph analysis) with a reproducible evidence pointer (path, line range, or command that produces the evidence). The citation includes enough context for an auditor to verify the observation.

Every non-neutral recommendation cites at least one driver from classes 1–6 inside its why-clause. Citing two or three is admissible when they jointly justify the recommendation; citing more than three signals the recommendation is probably `acceptable` in disguise (the weight of evidence makes the call underdetermined).

##### 3.2.2 Vague-Rationale Forbid List

The following phrases are NOT concrete drivers and MUST NOT serve as the sole justification for a non-neutral recommendation. The list is non-exhaustive — any phrase expressing an opinion without grounding it in one of the six driver classes falls under the same prohibition:

- `"this is better"` / `"this is safer"` / `"this is faster"` — opinion without measurement
- `"industry standard"` / `"best practice"` / `"widely accepted"` — appeal to external consensus without a named source
- `"more scalable"` / `"more maintainable"` / `"more robust"` — quality claim without a specific pressure metric
- `"cleaner"` / `"more elegant"` / `"more idiomatic"` — aesthetic claim without a concrete reader or convention citation
- `"generally speaking"` / `"in most cases"` / `"usually"` — hedge that concedes the recommendation does not apply to the specific case

The anti-example: `"Safer, generally speaking"` is not a concrete driver; `"rollback is trivial if we keep the prior file around"` is.

##### 3.2.3 Downgrade Path

When no concrete driver supports a non-neutral recommendation, the author's obligation is to downgrade the recommendation to `acceptable` and make the rationale neutral — no implied ordering between options, no hedge words, no appeal to opinion. A downgraded option's `recommendation:` value becomes `acceptable`; its label drops the ` (Recommended)` postfix if it carried one; its `rationale:` describes the option's observable effect without claiming superiority. The downgrade is the safe default when evidence is insufficient; it is never a degradation of the option set.

##### 3.2.4 Worked Example — Before / After

**Before (non-compliant):**

```yaml
- label:    Rewrite from scratch (Recommended)
  description:
    rationale:         Fresh rewrite resets accumulated technical debt.
    recommendation:    recommended — this is safer and cleaner.
    default-pointer:   Rewrite from scratch — the cleaner option is the default.
```

The `recommendation:` why-clause cites no concrete driver. `"safer and cleaner"` is on the forbid list.

**After (compliant):**

```yaml
- label:    Rewrite from scratch (Recommended)
  description:
    rationale:         Fresh rewrite resets accumulated technical debt.
    recommendation:    recommended — cites observed-state fact: the current module has 14 `# TODO:` markers and 6 orphan branches per the dependency graph; a partial rewrite would preserve the orphan branches. Also cites the rule `rules/clean-room-generation.md` §3 re-writing protocol requiring quality elevation over cosmetic editing.
    default-pointer:   Rewrite from scratch — the current module's measured defect density supports the default.
```

The non-compliant version was downgradeable to `acceptable` if no evidence were available. The compliant version cites a class 6 observed-state fact and a class 5 rule citation, satisfying §3.2.1 with double-grounded justification.

##### 3.2.5 Mitigation Anchor

The concrete-driver requirement mitigates driverless-recommendation bias — a recommendation without a driver nudges the operator without giving them reasoning to evaluate. H5 sweeps every invocation for non-neutral `recommendation:` values lacking an admissible §3.2.1 driver or matching the §3.2.2 forbid list; hits are HIGH-severity gate findings.

#### 3.3 Extension Protocol

Introducing a fifth taxonomy value requires: (a) a documented rationale grounded in a concrete driver the existing four cannot capture, (b) a definition entry written into this companion's §3.1 closed set, (c) a matching update to any compliance checks the sweep tooling emits. Ad-hoc extension in a single artifact is non-compliant; the extension is ecosystem-wide when it lands.

### 4. Harness Fallback — Full Specification

When the active harness exposes structured inquiry on neither the runtime tool surface (direct inspection) nor the deferred-tool discovery mechanism, the structured prose fallback replaces the tool invocation.

#### 4.1 Detection Logic

The activation predicate is `direct-surface-outcome = absent AND deferred-resolution-outcome ∈ {absent, not-applicable}`. Any other combination (including `direct-surface-outcome = absent` with `deferred-resolution-outcome = exposed-after-resolution`) keeps the tool as the primary channel; the fallback does not fire.

The detection record is the authoritative upstream source. Artifacts cite the pre-flight probe record (path, `final-state` field, timestamp) instead of re-inferring state. The probe record and its post-install re-probe sibling carry the five-field schema. Detection pseudocode:

```python
probe = read(probe-record-path)
direct  = probe.fields["direct-surface-outcome"]
deferred = probe.fields["deferred-resolution-outcome"]
final    = probe.fields["final-state"]

if direct == "absent" and deferred in {"absent", "not-applicable"}:
    emit_fallback()   # §4.2 + §4.3 apply
else:
    invoke_tool()     # canonical channel per parent §1
```

A harness whose runtime surface exposes neither direct nor deferred-tool discovery declares the absent-absent combination by default; an operator override (explicit declaration that the harness lacks the tool) produces the same combination and activates the fallback.

#### 4.2 Fallback Prose Shape

The fallback emits a structured prose prompt mirroring the tool's schema:

- one-sentence question ending in `?`, identical shape to the tool's `question` field;
- a short header (at most 12 characters) on its own line;
- a labeled option list, one option per line, in the form `- <label>: <three-segment body>`;
- a closing instruction of the exact form `Reply with the label of your choice.` (or, when multi-select is explicitly admissible, `Reply with the labels of your choices, comma-separated.`).

The three-segment body inside the fallback mirrors §2 exactly — `rationale:`, `recommendation:`, `default-pointer:` — so the operator sees identical information density in both forms. The `(Recommended)` label postfix per §2 is carried through unchanged. Destructive-op fallbacks carry the §5.4–§5.7 canonical option sets verbatim and the §5.2 default-floor (`default-pointer: no-default: user decision required` on every option); the §5.8 no-multiSelect invariant applies equally (the closing instruction uses the single-label phrasing, never the comma-separated variant, on destructive-op invocations).

**Worked example — single-select fallback (mirrors §1.1):**

```text
[FALLBACK — structured-inquiry channel unavailable]

Is the consolidated prose ready to promote, or should it iterate further?

Prose output

- Accept (Recommended): rationale: The prose meets the specification bar; promotion writes the output to the authored-specification path and closes the crystallization loop. recommendation: recommended — the crystallization summary shows zero open unknowns and zero contradictions. default-pointer: Accept — safe because the output is written to a versioned path and can be regenerated from the signal inventory.
- Iterate: rationale: Specific sections need surgical refinement before promotion; the rest of the draft is preserved. recommendation: acceptable. default-pointer: Accept — the crystallization summary does not flag any section as weak; Iterate is offered for operator-driven refinement, not as the default.
- Reject: rationale: The draft is not salvageable; restart preserving only the raw input. recommendation: discouraged — the crystallization check reports more than 50% signal capture, so iteration is viable. default-pointer: Accept — Reject should be chosen only when the draft is fundamentally unsalvageable, which the crystallization check does not indicate here.

Reply with the label of your choice.
```

The fallback prose preserves the ` (Recommended)` label postfix, every option's three-segment body, the same default-pointer convention, and the exact closing-instruction form the canonical schema specifies. Annotation-compliance heuristics (H4–H7) sweep the fallback form with the same matchers used against native tool invocations — the fallback is not an exemption channel.

#### 4.3 Explicit-Flag Mandate

Every fallback invocation emits two concurrent artifacts — a conversation-visible marker and a ledger-append record — so the degradation from tool to prose is never silent on either surface.

**Conversation marker (required).** The fallback prompt is immediately preceded by the literal string `[FALLBACK — structured-inquiry channel unavailable]` on its own line, rendered as part of the assistant's reply. The marker is visible to the operator; it is never suppressed, collapsed, or moved to a peripheral location.

**Ledger-append record (required).** Every fallback invocation appends one row to `ecosystem-remediation-ledger.md` under a `fallback-invocations` section, with these fields:

| Field | Type | Content |
|-------|------|---------|
| `timestamp` | ISO 8601 UTC | Invocation moment |
| `surface-id` | string | Catalog ID of the surface that emitted the fallback (e.g., `S-003`), or a synthesized `adhoc-<short-uuid>` when the invocation does not originate from a cataloged surface |
| `detection-outcome` | tuple | `(direct-surface-outcome, deferred-resolution-outcome, final-state)` as derived from the pre-flight probe record |
| `question-text` | string | The exact `question` field as rendered in the fallback |
| `options-labels` | ordered array of strings | The option labels in render order |
| `multiSelect` | boolean | `false` on destructive-op invocations per §5.8; otherwise matches the underlying invocation's shape |
| `probe-record-path` | string | Path to the probe record that established the absent-absent detection outcome |

A fallback invocation that lands on the conversation without its ledger-append row, or in the ledger without its conversation marker, is a protocol violation flagged HIGH severity by the 13th-gate heuristic sweep.

#### 4.4 Invariant — Fallback Is the Sole Permitted Free-Form Prompt

Outside the fallback context defined by §4.1's activation predicate, free-form prose questions as primary input are forbidden ecosystem-wide. The fallback's structured prose shape (§4.2) is the SOLE permitted free-form-looking prompt, and even that form carries the §4.3 conversation marker so the degradation is unambiguous. Every non-fallback free-form question across commands, rules, skills, agents, and hook code is a violation of heuristic H1, H2, or H3 and fails the interactive-channel compliance gate admitted to the airtightness composite. The invariant's enforcement arm is the heuristic sweep at `rules/interactive-questions-sweep-matchers.md`; this subsection declares the invariant itself.

### 5. Per-File Destructive-Op Confirmation — Canonical Option Sets

Every destructive operation routes through the structured-inquiry channel on a per-file basis. One question per file, every time, with no batching across files.

#### 5.1 Option Set

Destructive-op questions carry a standardized two-option body at minimum:

- one option representing the destructive action, with `recommendation: destructive-no-default` and a concrete-driver why-clause explaining why the destruction is proposed;
- one option representing the non-destructive alternative (retain, rename-to-archive, convert-to-reference), with `recommendation: recommended` or `acceptable` as appropriate and a concrete-driver why-clause.

A third option is admissible when the decision has a genuinely three-way shape; a fourth when genuinely four-way. Padding the option count for symmetry is non-compliant.

#### 5.2 Default Floor

Every option in a destructive-op question carries `default-pointer: no-default: user decision required`. No silent agent-proposed default is admissible on irreversible operations. Pre-selection, pre-highlighting, or pre-sorting the options so the destructive option lands in the first slot — all are non-compliant.

#### 5.3 Logging Mandate

The operation, its options, the user's response, and the post-confirmation filesystem delta all land in the authoritative remediation record for the session.

#### 5.4 Canonical Option Set — Delete

File or directory removal from the working tree. The canonical option set is `{Retire, Keep, Defer, Explain-first}`.

- **Retire** — destructive; the artifact is removed from the working tree. Body `recommendation: destructive-no-default` with a concrete-driver why-clause naming why removal is proposed (e.g., "zero inbound references in the dependency graph; not load-bearing per the stratum assignment").
- **Keep** — non-destructive; the artifact remains at its current path. Body `recommendation: acceptable` by default, or `recommended` when the retain-bias invariant applies (retention preserves the option of a later retire cycle).
- **Defer** — the decision is deferred to a later cycle; the artifact is flagged for re-examination. Body `recommendation: acceptable`.
- **Explain-first** — the agent surfaces additional evidence (dependency graph, usage trace, stratum classification) before the operator commits; a follow-up invocation runs once the evidence is reviewed. Body `recommendation: acceptable`.

#### 5.5 Canonical Option Set — Rename

Path change at the file level (name change; parent directory unchanged). The canonical option set is `{Rename-as-proposed, Keep-current, Propose-alternative, Defer}`.

- **Rename-as-proposed** — destructive at the path level; the artifact moves to the agent's proposed new path and its prior path becomes invalid for any inbound reference. Body `recommendation: destructive-no-default` with a concrete-driver why-clause naming why the proposed name is superior (e.g., "conforms to kebab-case convention; current name is a legacy outlier per the naming-convention sweep").
- **Keep-current** — non-destructive; the path is unchanged.
- **Propose-alternative** — the operator supplies a different name via the Other-text affordance; the agent re-invokes with the alternative as the proposed rename, preserving the per-file invocation floor.
- **Defer** — decision deferred; the artifact retains its current path for now.

#### 5.6 Canonical Option Set — Move

Path change at the directory level. The canonical option set is `{Move-as-proposed, Keep-current, Propose-alternative, Defer}`.

- **Move-as-proposed** — destructive at the path level; the artifact moves to the agent's proposed new directory. Body `recommendation: destructive-no-default` with a concrete-driver why-clause naming why the move preserves reachability.
- **Keep-current** — non-destructive; the artifact stays in its current directory.
- **Propose-alternative** — the operator supplies a different destination via Other-text; the agent re-invokes with the alternative.
- **Defer** — decision deferred; the artifact retains its current directory.

#### 5.7 Canonical Option Set — Revert Uncommitted Modifications

Version-control-level discard: uncommitted edits in the working tree are dropped. The canonical option set is `{Discard, Keep, Stash-for-later, Defer}`.

- **Discard** — destructive; `git restore --worktree` (or the VCS-equivalent) removes the uncommitted edits from the working tree. Body `recommendation: destructive-no-default` with a concrete-driver why-clause naming why the revert is proposed (e.g., "partial task state is inconsistent; the documented recovery path is a clean re-execute of the task from scratch").
- **Keep** — non-destructive; the uncommitted edits remain in the working tree for the operator to triage. Body `recommendation: acceptable`.
- **Stash-for-later** — non-destructive; the uncommitted edits are stashed to a VCS-managed holding area (`git stash push` or the VCS-equivalent) and can be retrieved later via `git stash pop`. Body `recommendation: acceptable`.
- **Defer** — decision deferred; STOP and emit a fresh invocation before any subsequent action. Body `recommendation: acceptable`.

#### 5.8 Invocation-Shape Invariants

Destructive-op invocations carry two invariants on top of the generic invocation shape:

- **No multi-select.** `multiSelect: true` is non-compliant on destructive-op invocations. Each invocation resolves a single destructive decision on a single file. Batching destructive decisions across multiple files — whether via `multiSelect: true` or via a single invocation whose options conflate multiple files — is forbidden by the per-file floor. The loop-over-files-and-invoke pattern is the only compliant shape.
- **Default floor preserved.** Every option's `default-pointer:` is `no-default: user decision required` per §5.2. Enforcement of the floor is specified at §6 (default-pointer convention) and compliance-checked by the H7 heuristic. The label-level postfix marker ` (Recommended)` per §2 MUST NOT mark a destructive option, because a recommendation marker on an irreversible action contradicts the no-default floor; the postfix may mark a non-destructive option when its body `recommendation:` value is `recommended`.

### 6. Default-Pointer Convention — Worked Examples

The `default-pointer:` body segment names the safe default with rationale OR explicitly declares `no-default: user decision required`.

- **Named-default form:** `default-pointer: <option-label> — <one-sentence rationale>`. The named option's rationale explains why it is safe (reversible, low-impact, aligns with prior decisions). The named default must be one of the question's actual options.
- **No-default form:** `default-pointer: no-default: user decision required`. Destructive operations always use this form per §5.2. Non-destructive operations may use it when the decision is genuinely non-comparable across options (e.g., strategic scope choices).

The convention is bidirectional: a question whose options all carry `destructive-no-default` in their `recommendation:` values MUST carry the no-default form on every option's `default-pointer:`. A question carrying a mix of neutral and named-default pointers MUST be consistent — no option's pointer contradicts another's.

#### 6.1 Safe-Default Naming

When the question admits a safe default, every option's `default-pointer:` uses the named-default form:

```yaml
default-pointer: <option-label> — <one-sentence rationale citing a concrete driver from §3.2.1>
```

The named option's rationale cites at least one concrete driver from the six-class taxonomy at §3.2.1. "Safe" is never a bare claim — it is grounded in a class 6 observed-state fact (e.g., "the output is written to a versioned path and can be regenerated") or a class 5 rule citation (e.g., "the retain-bias invariant prevents silent destruction") or another admissible driver class.

Every option in the same question carries the SAME named-default value — the default is a question-wide property, not a per-option property. Each option's `default-pointer:` may vary the rationale text (explaining why the default applies from that option's vantage) but MUST name the same default option.

#### 6.2 No-Default Declaration

When no safe default exists, every option's `default-pointer:` uses the no-default form with the verbatim marker string:

```yaml
default-pointer: no-default: user decision required
```

The string is literal — no abbreviations (`no-default: user decides`), no variants (`no-default: none`), no translation. The H7 heuristic matcher searches for this exact string; a question carrying a near-variant is a HIGH-severity gate finding.

Non-destructive operations use no-default when the decision is genuinely non-comparable across options — strategic scope choices, subset-triage decisions under multi-select, tier-selection decisions where operator context dominates agent heuristics.

#### 6.3 Destructive-Op Invariant

Every destructive-op invocation (delete / rename / move / overwrite-without-retention / revert-uncommitted-modifications) carries the no-default marker on every option; silent agent-proposed defaults on irreversible operations are forbidden. Anchored at §5.2 Default Floor + §5.8 Invocation-Shape Invariants; inherited by every §5.4–§5.7 canonical option-set.

#### 6.4 Worked Examples — Contrast

**Non-destructive, safe-default named:**

```yaml
question:     Should the schema migration apply a patch or a full rewrite?
header:       Migration
multiSelect:  false
options:
  - label:    Patch (Recommended)
    description:
      rationale:         Applies the minimal diff to the schema; preserves every existing row without touching column types.
      recommendation:    recommended — cites observed-state fact: the migration target is one additive column, no type change, no data migration; the rule `rules/clean-room-generation.md` §1.1 case (c) applies (needs-integration-changes; re-write-only-the-modified-portion).
      default-pointer:   Patch — safe because the patch is reversible via a down-migration and the schema's primary-key column is untouched.
  - label:    Full rewrite
    description:
      rationale:         Reconstructs the schema from scratch with a clean re-derivation.
      recommendation:    discouraged — cites observed-state fact: migration scope is one additive column, far below the clean-room-threshold for full re-derivation.
      default-pointer:   Patch — safe because the patch is reversible via a down-migration and the schema's primary-key column is untouched.
```

Both options' `default-pointer:` names `Patch` as the question-wide default, with rationales citing class 6 observed-state facts per §3.2.1.

**Destructive, no-default universal:**

```yaml
question:     How should the orphan module at `src/legacy/parser_v1.py` be retired?
header:       Retire file
multiSelect:  false
options:
  - label:    Retire
    description:
      rationale:         Removes the file from the working tree.
      recommendation:    destructive-no-default — cites observed-state fact: zero inbound references in the dependency graph; the stratum assignment places the file in the orphan tail; the retain-bias invariant yields to the measurable absence of callers.
      default-pointer:   no-default: user decision required
  - label:    Keep
    description:
      rationale:         Preserves the file at its current path for a later re-examination cycle.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required
  - label:    Defer
    description:
      rationale:         Marks the file for re-examination in a subsequent retire-cycle; no filesystem change now.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required
  - label:    Explain-first
    description:
      rationale:         Surfaces additional evidence before the operator commits; a follow-up invocation runs after review.
      recommendation:    acceptable
      default-pointer:   no-default: user decision required
```

Every option's `default-pointer:` carries the verbatim no-default marker; no named default is admissible because the Retire leg is irreversible. No option carries the ` (Recommended)` label postfix — §5.8 forbids the postfix on destructive options, and the only `recommendation: recommended`-eligible candidate would be the Retire leg, which is destructive.

### 5.9 Canonical Option Set — Plans-Locality Guard

Plans-Discipline write guard for Write / Edit / NotebookEdit / Bash tool calls intercepting plan-shaped writes that would land outside the active project's `.apothem/plans/` tree. Two variants — the hard-block 2-option set fires when the target path is under a harness-config-root `.plans/` directory; the soft-flag 3-option set fires when the target path is in another global-ecosystem location with plan-shaped filename or content. Sourced by `hooks/messages/pretooluse-write-plan-guard.md` and `hooks/messages/pretooluse-bash-plan-guard.md`.

#### 5.9.1 Hard-Block Variant — 2-Option Set

```yaml
question:    "The write target '<rejected-path>' is under a global plans
              directory (e.g., '~/.claude/.plans/' on the claude_code harness)
              but the active project root is '<project-root>'.
              Plans-Discipline forbids writing plans to the global ecosystem;
              redirect to the project-local plans directory or cancel?"
header:      "Plan guard"
multiSelect: false
options:
  - label:       "redirect-to-project-plans (Recommended)"
    description:
      rationale:       Rewrites the target path under the resolved project's
                       .apothem/plans/ directory ('<project-root>/.apothem/plans/...'), preserving
                       the file's relative position within the suite.
      recommendation:  recommended — cites class 5 rule citation: the CLAUDE.md Plans
                       Discipline section (Plans-Locality) and the spec at
                       suite specification; class 6 observed-state: the
                       target path resolves under the global ecosystem but the
                       active project has its own .apothem/plans/ directory.
      default-pointer: redirect-to-project-plans — safe because the redirected
                       write lands at the canonical project-local destination
                       and is reversible at the project's git layer.
  - label:       "cancel"
    description:
      rationale:       Blocks the write; no file is modified; the operator may
                       revise the target path or invoke /plan-spec --quick to
                       route the content through the canonical plan-write path.
      recommendation:  acceptable
      default-pointer: redirect-to-project-plans — cancel is appropriate when
                       the write requires architectural review before emission.
```

For Bash-tool invocations the label is `rewrite-redirect-to-project-plans` (in place of `redirect-to-project-plans`) and the question prose substitutes "Bash command would write … via shell redirection" for the Write-route phrasing; option bodies are otherwise identical.

#### 5.9.2 Soft-Flag Variant — 3-Option Set

```yaml
question:    "The write target '<flagged-path>' lies outside the project's
              .apothem/plans/ directory but carries plan-shaped content. Redirect to
              project-local .apothem/plans/, write as proposed, or cancel?"
header:      "Plan flag"
multiSelect: false
options:
  - label:       "redirect-to-project-plans (Recommended)"
    description:
      rationale:       Rewrites the target path under the resolved project's
                       .apothem/plans/ directory ('<project-root>/.apothem/plans/<basename>'),
                       capturing the plan-shaped artifact at its canonical
                       destination.
      recommendation:  recommended — cites class 6 observed-state: the proposed
                       content has plan-shaped markers (filename pattern or
                       frontmatter signature) and the current target is outside
                       the project's .apothem/plans/ directory.
      default-pointer: redirect-to-project-plans — safe because plan-shaped
                       artifacts at the canonical location preserve the
                       project's planning history under version control.
  - label:       "write-as-proposed"
    description:
      rationale:       Writes the content at the originally-proposed path
                       without redirection; appropriate when the soft-flag
                       triggered on a false positive (a non-plan artifact whose
                       filename happens to contain 'plan' / 'notes' / 'draft').
      recommendation:  acceptable
      default-pointer: redirect-to-project-plans — choose this only when the
                       artifact is genuinely not a plan despite the heuristic
                       match.
  - label:       "cancel"
    description:
      rationale:       Blocks the write; no file is modified.
      recommendation:  acceptable
      default-pointer: redirect-to-project-plans — cancel is appropriate when
                       the write requires triage before emission.
```

For Bash-tool invocations the action labels are `rewrite-redirect-to-project-plans` and `run-as-proposed` (in place of `redirect-to-project-plans` and `write-as-proposed`); option bodies are otherwise identical.

### 5.10 Canonical Option Set — Authorship-Header Guard

Authorship-header inject guard for Write / Edit tool calls — fires when a target file is applicable (suffix or basename maps to a known variant family) and `file-header-grep.check()` returns `HEADER_ABSENT` or `HEADER_MALFORMED`. Sourced by `hooks/messages/pretooluse-write-header-guard.md` (Write scope) and `hooks/messages/pretooluse-edit-header-guard.md` (Edit corner cases A and B).

```yaml
question:    "The write target '<path>' has no canonical authorship header
              (<rule-or-corner-case> · variant '<variant>') — accept the
              corrected content, override with justification, or cancel?"
header:      "Header guard"
multiSelect: false
options:
  - label:       "accept-corrected (Recommended)"
    description:
      rationale:       Writes the corrected content with the canonical single-line SPDX license header
                       prepended at the correct position; the file body is
                       otherwise byte-identical to the original.
      recommendation:  recommended — the canonical single-line SPDX license header is required for all
                       applicable files per the ratification at
                       src/apothem/schemas/authorship-header.txt.
      default-pointer: accept-corrected — safe because the change is limited
                       to the prepended header block and the write is fully
                       reversible.
  - label:       "write-anyway-with-justification"
    description:
      rationale:       Writes the original headerless content and appends a
                       timestamped override row to .audit/header-overrides.md
                       (schema: timestamp · path · variant · rule ·
                       justification from Other-text, or
                       "[no justification supplied]" when absent).
      recommendation:  discouraged — bypasses the header policy; the override
                       record is an audit trail, not a closure; inject via
                       the apothem header-injector at
                       https://github.com/ahmed-g-gad/apothem/blob/main/scripts/inject-header.py
                       or add the path to
                       src/apothem/schemas/header-exceptions.txt to close the gap.
      default-pointer: accept-corrected — choose this only when the file is
                       an exemption candidate not yet listed in
                       src/apothem/schemas/header-exceptions.txt.
  - label:       "cancel"
    description:
      rationale:       Blocks the write; no file is modified; the user may
                       revise the content, update src/apothem/schemas/header-exceptions.txt,
                       or run the apothem header-injector
                       (https://github.com/ahmed-g-gad/apothem/blob/main/scripts/inject-header.py)
                       independently before retrying.
      recommendation:  acceptable
      default-pointer: accept-corrected — cancel is appropriate when the write
                       requires architectural review before emission.
```

**Override-record schema.** When the operator selects `write-anyway-with-justification`, the guard appends one row to `.audit/header-overrides.md` with these columns: `timestamp` (ISO 8601 UTC) · `path` (target file's absolute path) · `variant` (variant-family identifier from SUFFIX_VARIANT / BASENAME_VARIANT) · `rule` (Write-route rule label OR Edit-route corner-case label: `create-via-edit` | `header-removal`) · `justification` (operator's Other-text content, or the literal `[no justification supplied]` when absent). The override record is an audit trail, not a closure — gap closure requires either injecting the header via the apothem header-injector or adding the path to `src/apothem/schemas/header-exceptions.txt`.

## Enforcement

Path-filtered (the five glob patterns in this rule's `pathFilter` field), always-on at every seriousness level when in scope. Demand-loaded canonical-shapes companion to `rules/interactive-questions.md`. The parent rule owns the canonical-channel obligation, structured-inquiry shape, section anchors, seriousness scaling, anti-patterns, and CM-2 extension binding; this companion owns the worked examples, annotation schema body, recommendation-taxonomy details, harness-fallback specification, destructive-op option-set templates, and default-pointer worked examples. With `rules/interactive-questions-sweep-matchers.md` (H1–H7 matcher catalog) they constitute the canonical specification for user-input surface discipline.

## Bindings (§0.j five-direction)

- **Drives →** ● Every authored structured-inquiry invocation (downstream artifacts copy §1.1 / §1.2 / §6.4 fenced blocks as templates). ● Every concrete-driver citation on non-neutral recommendations (the §3.2.1 driver taxonomy). ● Every fallback invocation's prose shape and explicit-flag emission (the §4.2 + §4.3 surfaces). ● Every destructive-op invocation's canonical option-set (the §5.4–§5.7 templates).
- **Satisfies →** ● CM-2 extension (companion-shapes tier of the structured-inquiry surface CM-2 delegates to). ● the rules registry row "Interactive Questions" (canonical-shapes companion). ● `rules/interactive-questions.md` (the parent rule's pointer to this companion's full schema and worked examples).
- **Established by ↑** ● `rules/interactive-questions.md` (parent-rule anchor at §2/§3/§4/§5/§6/§7). ● CM-2 extension. ● Option Annotation Discipline (the mandate the schema and examples enforce).
- **Gated by ←** ● The path-filter (the five glob patterns) — this rule demand-loads only on artifact classes that author structured-inquiry invocations. ● `rules/interactive-questions.md` always-on baseline (parent rule must be live for the section anchors to resolve coherently).
- **Cross-bound with ↔** ↔ `rules/interactive-questions.md` (parent rule; section anchors at §2/§3/§4/§5/§6/§7 bind this companion). ↔ `rules/interactive-questions-sweep-matchers.md` (sibling companion; H4–H7 matcher catalog enforces this companion's annotation-schema and destructive-op invariants). ↔ `rules/operational-mandates.md` (CM-2 inline anchor delegates to the parent, which delegates schema bodies here). ↔ `commands/plan-execute.md` + `commands/plan-generate.md` + `commands/plan-spec.md` + `commands/plan-review.md` (every plan-pipeline command's structured-inquiry invocations adopt this companion's worked-example templates). ↔ `scripts/dev/validate_ecosystem.py` (the `--check option-annotation` subcommand operationalizes matcher specifications grounded in this companion's schema). ↔ `rules/determinism.md` (the canonical option-set shapes render deterministically — same decision space yields the same invocation payload). ↔ `rules/interactive-questions-detail.md` (↔ reciprocal of the peer's Cross-bound citation). ↔ `rules/option-annotation-form.md` (§2.1 per-invocation cardinality, §3.2.2 vague-rationale forbid list). ↔ `rules/sota-elevation-exemplars.md` (concrete-driver class 6 citation requirement).
