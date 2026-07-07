---
name: "interactive-questions-sweep-matchers"
description: "Path-filtered companion rule carrying the canonical-channel sweep matcher specifications (H1–H7); demand-loaded when the parent `interactive-questions.md` rule's §8 anchor surfaces."
pathFilter: "**/commands/**/*.md, **/rules/**/*.md, **/skills/**/*.md, **/agents/**/*.md, **/hooks/**/*.md, **/CLAUDE.md, **/settings.json"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Interactive-Questions Sweep Matchers (Companion Sub-Rule)

## Purpose

Specify the executable matcher catalog for the canonical-channel compliance gate declared at the parent rule's `rules/interactive-questions.md` §8 anchor. This companion is path-filtered: it loads when the assistant edits any of the governed-core surfaces the matchers sweep, keeping the parent's always-on payload lean while preserving full matcher fidelity at the demand-load surface. The parent rule remains the canonical home for the canonical-channel obligation, the three-segment option-annotation schema, the recommendation taxonomy, the harness fallback, the per-file destructive-op confirmation, and the default-pointer convention; this companion carries the H1–H7 sweep matcher catalog.

## Obligations

### 1. Heuristic Catalog (H1–H7)

The compliance gate sweeps for two heuristic classes: conversational-form heuristics (H1–H3), which detect raw conversational prompts that bypass the canonical channel; and annotation-compliance heuristics (H4–H7), which detect structured-inquiry invocation payloads that violate the option-annotation schema.

- **H1 — Imperative + question mark.** A sentence opens with an imperative verb ("Confirm", "Approve", "Choose", "Select", "Pick", "Decide") and ends with `?`. Exemption: the phrase appears inside a code fence, a blockquote marked as preserved conversation, or a raw-notes context explicitly tagged as the parent rule's §1 exception 1 material.
- **H2 — "Please confirm" / "Please approve" / "Please choose".** The literal phrase appears as a primary input prompt. Same exemption as H1.
- **H3 — "Which of the following".** The phrase opens a primary input prompt without an immediately preceding structured-inquiry invocation. Same exemption as H1.
- **H4 — Option without three-segment body.** A structured-inquiry invocation has any option whose `description` lacks any of the three canonical segments (`rationale:`, `recommendation:`, `default-pointer:`).
- **H5 — Non-neutral recommendation without concrete driver.** A `recommendation:` body value is `recommended`, `discouraged`, or `destructive-no-default`, and the same body segment carries no concrete-driver why-clause of the form admissible by `rules/interactive-questions-canonical-shapes.md` §3.2.1.
- **H6 — Label–body mismatch and cardinality.** An option's label carries the `(Recommended)` postfix but its body `recommendation:` value is not exactly `recommended`; an option's body value is exactly `recommended` and its own label does not carry the postfix; or a `multiSelect: false` question carries more than one recommended option. `multiSelect: true` questions may carry multiple recommended options when each label/body pair matches.
- **H7 — Destructive op without `no-default` floor.** A `recommendation:` body value is `destructive-no-default` and the same option's `default-pointer:` is not the `no-default: user decision required` form; or a question has at least one option marked `destructive-no-default` and another option in the same question carries a named default.

Every heuristic hit is a gate finding at severity HIGH unless the artifact is outside the interactive-surface catalog's compliance scope (fallback-permitted harnesses recording a compliant fallback use, raw-notes preservation contexts per §3). The H6 sweep is bidirectional — it checks both label→body and body→label.

### 2. Sweep Scope

The zero-match sweep runs across the ecosystem's governed-core tree:

- `commands/` — all `.md` files
- `rules/` — all `.md` files
- `skills/` — recursive, all `.md` / `.py` / `.sh` / `.ps1` / `.json` files
- `agents/` — all flat `<name>.md` entry points
- `hooks/` — recursive, all `.py` / `.sh` / `.ps1` / `.md` / `.json` files
- `settings.json` in the harness config root — root-level hook-configuration file
- `CLAUDE.md` — root-level ecosystem-config file

The sweep does not recurse into `<project-root>/.apothem/plans/` (plan-suite internal artifacts are exempt from the gate) or `<harness-root>/projects/` (per-project memory outside ecosystem authorship).

### 3. Exclusion Zones

Hits inside the following contexts are exempt from the zero-match verdict:

- **Raw-notes contexts** per the parent rule's §1 exception 1 — quoted conversational material preserved for audit fidelity. Preservation is explicit: the artifact declares itself as a preservation artifact (frontmatter `purpose: preserved-conversation` marker, or an enclosing `<raw-notes>…</raw-notes>` fence, or a blockquote whose preceding paragraph labels the block as preserved conversation).
- **Parent rule's own §1, §5, §6, and §Anti-Patterns bodies** — the parent rule specifies the patterns it regulates; the self-referential citations are definitional. The §1 Scope statement, the §5.2 fallback-shape worked example, the §6.4–§6.7 canonical option-set subsections, and the §Anti-Patterns first bullet may quote the forbidden phrases verbatim for definitional purposes.
- **This companion rule's own §1 H1–H7 catalog body** — the catalog specifies the patterns it regulates; its self-referential citations of the H1, H2, H3 trigger phrases are definitional and exempt.
- **Migration-ledger paths** — `ecosystem-remediation-ledger.md` and every per-sub-phase `ledger-fragment.md` under `.apothem/plans/*/phases/*/` may quote forbidden phrases as "before-state" evidence of a migration.
- **Code fences and blockquotes tagged as preserved conversation** — inline preservation anchors inside otherwise-non-exempt files.

### 4. Sweep Invocation Specification — H1–H3 (Conversational-Form)

The sweep uses ripgrep with the following per-heuristic invocations. Each invocation returns a hit count; the gate passes when every count equals the number of hits inside exclusion zones.

| Heuristic | Pattern (ripgrep regex) | Case | Exclusion-zone count |
|-----------|-------------------------|------|----------------------|
| H1 | `^(Confirm\|Approve\|Choose\|Select\|Pick\|Decide\|Specify\|Indicate)\b.*\?$` | literal | 0 active hits; 1 definitional reference at this companion's §1 H1 (inside quote marks, exempt) |
| H2 | `Please (confirm\|approve\|choose\|select)` | case-insensitive | 0 active hits; definitional references at the parent rule's §1, this companion's §1 H2, and the parent rule's §Anti-Patterns |
| H3 | `Which of (the following\|these)` | case-insensitive | 0 active hits; definitional references at the parent rule's §1 and this companion's §1 H3 |

Reproducible invocation from the ecosystem root (identical in POSIX bash and PowerShell 7+ since ripgrep is cross-platform):

```sh
rg --no-heading -nP '^(Confirm|Approve|Choose|Select|Pick|Decide|Specify|Indicate)\b.*\?$' \
  commands/ rules/ skills/ agents/ hooks/ settings.json CLAUDE.md

rg --no-heading -ni 'Please (confirm|approve|choose|select)' \
  commands/ rules/ skills/ agents/ hooks/ settings.json CLAUDE.md

rg --no-heading -ni 'Which of (the following|these)' \
  commands/ rules/ skills/ agents/ hooks/ settings.json CLAUDE.md
```

### 5. Gate Admission — Interactive-Channel Compliance

The interactive-channel compliance gate is a named member of the airtightness composite alongside the numeric gates (5–19) and the other two named gates (Portability Gate, Kerning Gate). The gate's pass predicate is:

- For every conversational-form heuristic H1–H3: total hit count equals the documented exclusion-zone count. Equivalently, every conversational-question pattern that appears in the ecosystem is inside a declared exclusion zone (§3).
- For every annotation-compliance heuristic H4–H7: zero hits. The annotation sweep has no exclusion zone — every structured-inquiry invocation in the ecosystem must satisfy the annotation schema (parent rule's §3 three-segment body, §4 recommendation taxonomy, §6.2 default-floor on destructive ops, §3 bidirectional label-postfix rule).

Gate failures at HIGH severity block the composite's pass verdict. The gate's downstream enforcement arm is the semantic blind re-audit in the diagnostic phase, which re-executes §4's sweep specifications and verifies the exclusion-zone count matches the documented values. A drift (e.g., the H2 exclusion count rises without a corresponding definitional-use change recorded in the remediation ledger) is itself a gate finding.

### 6. H4–H7 Machine Matchers — Annotation-Compliance Heuristics

H4–H7 sweep the structured-inquiry invocation payloads themselves rather than free-form prose. Each heuristic's matcher semantics are specified below.

#### 6.1 H4 — Body-Segment Omission

**Pass predicate:** every option's `description` field contains all three body-segment markers `rationale:`, `recommendation:`, and `default-pointer:` in that order, separated by newlines or period-space per the parent rule's §3.

**Matcher:** for each structured-inquiry invocation, walk every option; for each option, test that its `description` string contains all three segment-marker tokens (case-sensitive literal match). Absence of any one token = HIGH-severity hit.

**Normative source:** parent rule's §3 Three-Segment Option Annotation.

#### 6.2 H5 — Non-Neutral Recommendation Without Concrete Driver

**Pass predicate:** every option whose body `recommendation:` value is one of `{recommended, discouraged, destructive-no-default}` carries a why-clause that cites at least one admissible driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 AND does not match any phrase on `rules/interactive-questions-canonical-shapes.md` §3.2.2 forbid list.

**Matcher:** for each option, extract the body `recommendation:` value. If the value is `acceptable`, skip (neutral; no driver required). Otherwise, extract the why-clause (text after the `—` em-dash separator on the `recommendation:` segment line, up to the next newline). Test:

- **Admissibility test** — the why-clause contains at least one token from the six driver-class signature set: (1) a decision identifier of shape `D-\d+` or equivalent; (2) a risk identifier of shape `R-\d+`; (3) a constraint identifier of shape `C-\d+`; (4) an open-question identifier of shape `OQ-\d+`; (5) a rule-file path of shape `rules/*.md §X.Y.Z`; (6) an observed-state citation pattern — a measured metric + source, a file path + line range, a gate-result citation. At least one signature token must match.
- **Forbid-list test** — the why-clause does NOT contain any literal phrase from `rules/interactive-questions-canonical-shapes.md` §3.2.2 vague-rationale forbid list (case-insensitive). A match on the forbid list is a HIGH-severity hit even when an admissible token is also present (the forbid phrase must be removed or the recommendation downgraded to `acceptable`).

**Normative source:** `rules/interactive-questions-canonical-shapes.md` §3.2.1 Driver Taxonomy + §3.2.2 Vague-Rationale Forbid List.

#### 6.3 H6 — Label-Postfix ↔ Body-Value Bidirectional Consistency

**Pass predicate:** for every option, the bidirectional bind holds — `label` ends with ` (Recommended)` IFF body `recommendation:` value is exactly `recommended`. Additionally, `multiSelect: false` invocations have zero or one recommended option; `multiSelect: true` invocations may have one or more recommended options.

**Matcher:** for each option, extract the `(label, description)` coupled pair. Compute two booleans:

- `label_has_postfix` — the `label` string ends with the exact suffix ` (Recommended)` (one leading space, literal past-participle wrapped in parentheses, no trailing whitespace or punctuation).
- `body_is_recommended` — the body `recommendation:` value is exactly the string `recommended`.

Three failure modes (all HIGH-severity):

- **Missing postfix (body→label direction):** `body_is_recommended = true` AND `label_has_postfix = false`.
- **Spurious postfix (label→body direction):** `label_has_postfix = true` AND `body_is_recommended = false`.
- **Single-select multi-postfix:** invocation `multiSelect = false` AND more than one option has `body_is_recommended = true`.

Options with body values `acceptable`, `discouraged`, or `destructive-no-default` MUST carry no label postfix — absence is the normal state, not a finding. Multiple recommended options are compliant only on non-exclusive `multiSelect: true` invocations.

**Normative source:** parent rule's §3.1 Label Postfix Convention.

#### 6.4 H7 — Destructive-Op Missing No-Default Floor

**Pass predicate:** every option in a destructive-op invocation carries the verbatim string `no-default: user decision required` on its `default-pointer:` segment.

**Matcher:** for each structured-inquiry invocation, determine whether it is a destructive-op invocation by two signals:

1. **Op-type signal:** the invocation's option set matches one of the parent rule's §6.4–§6.7 canonical option-set templates (delete/rename/move/revert-uncommitted) by label-set intersection — the canonical set labels are `{Retire, Keep, Defer, Explain-first}` (§6.4), `{Rename-as-proposed, Keep-current, Propose-alternative, Defer}` (§6.5), `{Move-as-proposed, Keep-current, Propose-alternative, Defer}` (§6.6), `{Discard, Keep, Stash-for-later, Defer}` (§6.7).
2. **Taxonomy-value signal:** any option carries body `recommendation: destructive-no-default` (per the parent rule's §4.1 this is the destructive-irreversible taxonomy value).

An invocation satisfying either signal is a destructive-op invocation. For every option in such an invocation, test that the `default-pointer:` segment contains the verbatim string `no-default: user decision required`. Failure = HIGH-severity hit.

Two sub-conditions of H7:

- **Missing no-default marker** — the destructive-op invocation's option has a named-default pointer instead of the verbatim no-default marker.
- **Contradictory pointer mix** — the invocation has at least one option marked `destructive-no-default` and another option carries a named-default pointer (the parent rule's §6.2 consistency rule is violated).

**Normative source:** parent rule's §6.2 Default Floor + §6.8 Invocation-Shape Invariants + §7.3 Destructive-Op Invariant.

### 7. Payload Inspection Procedure

The H4–H7 matchers operate on structured-inquiry invocation payloads extracted from two source surfaces:

- **Native invocations** — call sites where the tool is invoked with a `questions` array. Extraction uses static pattern matching on the tool-invocation syntax (e.g., in command `.md` specifications that describe an invocation inline with `question: … / header: … / options: [ label / description / multiSelect ]` block form, or in the skill-template `{…}` block form). The matcher walks the `questions` array, then each question's `options` array, then each option's `label` and `description` pair.
- **Fallback prose mirrors** (per the parent rule's §5.2) — the fallback prose shape is a faithful mirror of the tool's schema. Extraction uses the fallback-form parser: the closing instruction `Reply with the label of your choice.` (or the multi-select variant) delimits the option list; each bullet `- <label>: <three-segment body>` is parsed into `(label, description)`.

For H6 (label-postfix ↔ body-value), the matcher treats `label` and `description` as a coupled pair — extracting the trailing parenthetical from `label` and the `recommendation:` segment from `description` together so both booleans in §6.3's pass predicate can be computed from a single option's payload.

For H7 (destructive-op no-default), the matcher first classifies the invocation as destructive using the §6.4 op-type and taxonomy-value signals, then walks every option's `default-pointer:` segment.

Exemption: the §3 exclusion zones apply equally to H4–H7. Invocation payloads inside the canonical-shapes companion's body (e.g., its §2.1, §2.2, §5.2, §3.2.4 worked examples) are definitional uses; the companion specifies the patterns it regulates, and its own worked examples are the normative source. The rule self-citation exemption covers these; the companion's §3.2.4 "Before" anti-example is specifically designed as a non-compliant example demonstrating the pattern to avoid and is covered by the rule-self-citation exemption.

### 8. Sweep Invocation Specification — H4–H7

Each H4–H7 heuristic has a reproducible sweep invocation. Because H4–H7 operate on structured payloads rather than line-oriented prose, the invocations use an AST-walk or JSON-path parser where the source format supports it; for Markdown source artifacts, the invocations combine ripgrep with structural context (`--multiline` and `--no-heading` flags).

| Heuristic | Incantation sketch (Markdown source — the tooling sub-phase materializes a full script) |
|-----------|------------------------------------------------------------------------------------------|
| H4 | `rg --multiline --no-heading -U 'structured inquiry[\s\S]*?options:[\s\S]*?(?:label:.*?(?!.*rationale:).*?(?!.*recommendation:).*?(?!.*default-pointer:))' <scope>` — matches any option block missing any of the three body-segment markers |
| H5 | Two-pass: (pass 1) `rg -nP 'recommendation:\s+(recommended\|discouraged\|destructive-no-default)\b([^\n]*)' <scope>` to enumerate non-neutral recommendations; (pass 2) for each match, verify the tail `[^\n]*` contains at least one driver-class signature token (D-/R-/C-/OQ-/rule-path/observed-state pattern) AND does not contain any forbid-list phrase |
| H6 | Two linked passes plus a cardinality pass: (a) `rg -nP '^\s+label:\s+.+(?<! \(Recommended\))$' <scope>` enumerating labels NOT ending with the canonical postfix, paired with their option's body `recommendation:` segment — hit when the body value is `recommended` (missing-postfix direction); (b) `rg -nP '^\s+label:\s+.+ \(Recommended\)$' <scope>` enumerating labels ending with the canonical postfix, paired with their option's body `recommendation:` segment — hit when the body value is not `recommended` (spurious-postfix direction); a label ending with the lowercase ` (recommended)` variant is itself a non-canonical-case hit; (c) count recommended options per invocation and hit when `multiSelect: false` has more than one |
| H7 | Two-step: (step 1) classify invocation as destructive by (a) label-set intersection with the parent rule's §6.4–§6.7 canonical sets OR (b) any option carrying `recommendation: destructive-no-default`; (step 2) for every option in a destructive invocation, verify `default-pointer:` segment contains the verbatim literal `no-default: user decision required` — hit on any option where the verbatim string is absent |

The annotation-compliance-sweep tooling materializes these sketches into a single runnable sweep script (POSIX bash + PowerShell 7+ equivalents) honoring the §4 cross-platform convention. The sweep script's executable matcher implementations are the authoritative realization of these specifications.

## Enforcement

Path-filtered (the eight glob patterns in this rule's `pathFilter` field), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/interactive-questions.md` §8. The parent rule carries the canonical-channel obligation, the option-annotation schema, the recommendation taxonomy, the harness fallback, the per-file destructive-op confirmation, and the default-pointer convention; this companion carries the H1–H7 sweep matcher catalog. Together they constitute the canonical specification for user-input surface discipline and interactive-channel compliance heuristics.

## Bindings (§0.j five-direction)

- **Drives →** ● The H1–H7 heuristic sweep across the governed-core surface classes (commands, rules, skills, agents, hooks, `settings.json`, `CLAUDE.md`). ● The interactive-channel compliance gate's pass/fail verdict (§5 Gate Admission). ● The `scripts/dev/validate_ecosystem.py --check option-annotation` subcommand (the H4–H7 annotation-compliance matchers operationalize here). ◐ The semantic blind re-audit in the diagnostic phase (the gate's downstream-enforcement arm).
- **Satisfies →** ● CM-2 extension (rule-delegated companion sub-rule). ● the rules registry row "Interactive Questions Sweep Matchers". ● `rules/interactive-questions.md` §8 anchor (the parent rule's pointer to this companion's full executable matcher catalog).
- **Established by ↑** ● `rules/interactive-questions.md` §8 (parent-rule anchor). ● CM-2 extension. ● Option Annotation Discipline (the mandate the H4–H7 matchers enforce).
- **Gated by ←** ● The path-filter (the eight glob patterns) — this rule demand-loads only on governed-core surface touches. ● `rules/interactive-questions.md` always-on baseline (parent rule must be live for the §8 anchor to surface).
- **Cross-bound with ↔** ↔ `rules/interactive-questions.md` (parent rule; §8 anchor binds this companion). ↔ `scripts/dev/validate_ecosystem.py` (the `--check option-annotation` subcommand operationalizes the H4–H7 matchers; this rule specifies the matchers' executable semantics). ↔ `rules/operational-mandates.md` (CM-2 zero-assumptions's structured-inquiry surface delegates to the parent rule, which delegates the matcher catalog here). ↔ `rules/interactive-questions-canonical-shapes.md` (sibling companion; H4–H7 matcher catalog enforces this companion's annotation-schema and destructive-op invariants). ↔ `rules/interactive-questions-detail.md` (sibling companions carrying the schema worked-examples and the H1–H7 matcher catalog). ↔ `rules/option-annotation.md` (the H4–H7 annotation-compliance heuristics enforce this rule's prose-and-document scope at the pre-emission gate).
