<!-- SPDX-License-Identifier: MIT -->

# Rules

Behavioral instruction rules — flat `.md` files, each a self-contained directive set the harness loads to govern agent behavior. Each carries YAML frontmatter declaring `name`, `description`, `pathFilter`, and `alwaysApply`; a body of obligations; and a `## Bindings` section wiring it to its peers.

## Always-on vs path-filtered rules

Every rule is one of two kinds, declared in frontmatter:

- **Always-on** — `alwaysApply: true` with an empty `pathFilter:`. Loaded into every session. To keep the always-on tier lean, each always-on body is capped at 500 substantive tokens per `token-budget-discipline.md`.
- **Path-filtered (companion)** — `alwaysApply: false` with a `pathFilter:` glob list. Demand-loaded only when the agent touches a matching artifact.

## The parent / companion-sub-rule pattern

When an always-on rule's content exceeds the token ceiling, it decomposes along a path-filtered seam: the **parent** rule retains the standing directive plus a one-line summary and a `(Companion Sub-Rule Anchor)` pointer; the **companion** sibling — named `<parent>-<aspect>.md`, path-filtered — carries the operational depth (catalogs, worked examples, executable matchers, full tables). The companion demand-loads only when relevant, so detail pays its context cost only where it applies. Pairs are reciprocally cited in each rule's `## Bindings` block.

## The `## Bindings` five-direction section

Every rule closes with a `## Bindings (§0.j five-direction)` section declaring its place in the rule graph along five reciprocal directions: **Drives →** (what it causes), **Driven by ← / Established by ↑** (what triggers / ratifies it), **Gated by ←** (the activation condition or enforcer that gates it), **Satisfies →** (what end-state it meets), and **Cross-bound with ↔** (sibling rules that mutually reinforce). `scripts/dev/validate_ecosystem.py --check binding-five-direction` requires Drives, Satisfies, Established by, Gated by, and Cross-bound with on every rule, command, agent, and skill, and the three-direction subset (Drives, Established by, Cross-bound with) on every hook message. Every declared binding has a reciprocal back-pointer at the other end; the discipline is specified in `bidirectional-binding.md`.

## Rule families

### Cognitive identity & generation methodology

| Rule | Concern |
|------|---------|
| `cognitive-identity.md` · `cognitive-identity-techniques.md` | The cognitive-insurgent identity — five creative filters, six ideation techniques, language standards, seven-axs-of-breadth taxonomy. |
| `clean-room-generation.md` · `clean-room-generation-protocols.md` | Specification-derived original output — Writing / Re-Writing protocols, code-generation discipline. |
| `planning-techniques.md` | Nine planning review techniques for plan generation, review, execution. |

### Operational mandates & quality gates

| Rule | Concern |
|------|---------|
| `agnostic-posture.md` · `agnostic-posture-checklist.md` | Default-off, opt-in posture for every shipped behavior; correctness gates stay advisory; harness-neutral surfaces; model / effort / workflow preference is end-user-invoked — plus the per-invariant verification checklist every phase's definition of done satisfies. |
| `agents-md-convention.md` | The root `AGENTS.md` is the single agent-facing canon; per-folder operating guidance lives in each folder's `README.md` (one file, both the human and agent reader); per-folder `AGENTS.md` companions are not required, and any present companion stays current and canon-coherent with the root AI-surface canon. |
| `operational-mandates.md` · `operational-mandates-expanded.md` | Operational mandates CM-1–CM-10 — critical evaluation, zero assumptions, search-before-implement, brutal honesty. |
| `pre-emission-gate.md` · `pre-emission-gate-bars.md` | The fifteen-bar pre-emission gate (M1–M15) every artifact passes before emission, with a recorded attestation. |
| `ten-dimension-check.md` · `ten-dimension-check-dimensions.md` | The ten quality dimensions applied to every artifact (M3). |
| `definitiveness.md` · `definitiveness-virtues.md` | Definitive, airtight statements; hedging elimination; the rigorous-systems virtues (M8). |
| `etc-extension.md` | Enumerations are seeds, not ceilings — every open-set marker (`etc.` / `e.g.` / `such as` / `like` / `including` / `…`) is a directive to extend comprehensively from intent; an explicitly-closed enumeration is exempt. |
| `source-accessibility.md` · `source-accessibility-scaling-tells.md` | Source trust outranks accessibility — reach a trusted-but-inaccessible source via browser then operator interview; never prefer untrusted-but-free over trusted-but-inaccessible; record the source-trust decision. The path-filtered companion carries the four-level seriousness-scaling table and the failure-tells enumeration. |
| `authoritative-referencing.md` · `authoritative-referencing-homes.md` · `authoritative-referencing-quotation.md` | Every claim / argument / hypothesis / fact cites an authoritative, official, current source — the scattered dim-9 / sota named-exemplar / disclosure-ledger / output-style-citation discipline consolidated by reference; folklore and "industry standard" appeals are non-conformant. The `-homes` companion carries the four per-surface referencing-home list, the seriousness-scaling table, and the failure-tells enumeration; the `-quotation` companion binds the reproduction form: paraphrase by default with attribution, quote sparingly and briefly, never reproduce a full third-party work, attribute without a legal opinion. |
| `dynamism.md` | No static substitutions for dynamic-source-of-truth values — version / badge / release / docs-version / runtime `__version__` / social-card stamps render from one live authority; the `static-version-grep` matcher enforces the closed surface set. |
| `sota-elevation.md` · `sota-elevation-exemplars.md` | State-of-the-art elevation as the default posture for OSS-distribution surfaces — eight SOTA evaluation surfaces, named-exemplar discipline, MAXIMAL upper-bound calibration. |

### Host-project conduct (the M-mandate family)

| Rule | Concern |
|------|---------|
| `host-discovery.md` · `host-discovery-manifests.md` | Discover and honor host-project conventions before emitting (M1). |
| `disclosure-ledger.md` · `disclosure-ledger-markers.md` | Disclosed amendments, never silent — the change ledger (M2). |
| `authority-inquiry.md` · `authority-inquiry-categories.md` | Inquire, do not invent — names, endpoints, scope, version pins (M5). |
| `expertise-posture.md` · `expertise-posture-elements.md` | Read intent, amend proactively, surface gaps (M6). |
| `option-annotation.md` · `option-annotation-form.md` | Every multi-option choice carries a Recommended marker plus rationale (M7). |
| `visual-leverage.md` | Diagrams where structure is the subject (M9). |
| `bidirectional-binding.md` | Reciprocal five-direction bindings; phase-execution threading (M10). |
| `agile-sprints.md` · `agile-sprints-elements.md` | Non-trivial multi-step work runs as disciplined Agile sprints (M11). |
| `canonical-layout.md` · `canonical-layout-reporting-tiers.md` | Two-tier phase reporting; canonical output layout; orphan prevention (M12). |
| `systemic-participation.md` · `systemic-participation-relations.md` | Artifacts join the host as systemic participants — no orphans, no silos (M14). |
| `production-ready-prs.md` · `production-ready-prs-surfaces.md` | Every change ships production-ready — tests, docs, CHANGELOG, CI green (M15). |
| `own-voice-reimplementation.md` | Reference-derived features reauthored in apothem's own voice — zero verbatim copy, mandatory elevation, harness-doc-aligned. |
| `living-docs.md` | Every change to a documented public surface updates its docs page in the same change-set — the documentation analogue of the production-ready discipline; CI's docs-reference-sync drift gate enforces it. |
| `freshness-facade.md` | Shipped public surfaces stay a current-version-only facade — no AI-disclosure, backward / legacy / placeholder, or fix-and-refinement narrative; the `freshness-token-grep` matcher gives the closed token-class list mechanical teeth on README plus site copy. |
| `surgical-manipulation.md` | Surgical, anchor-bounded, minimal-diff mutation discipline — scoped edits over blunt whole-file overwrites across every file class; paired with the `surgical-guard` skill's post-edit quality pass. |
| `propagation.md` | Full-reference-graph propagation — every mutation propagates same-change-set across code / docs / tests / examples / registries / plugins / bindings; generalizes `living-docs.md` + `systemic-participation.md` and binds the existing drift gates (the CM-8 keystone). |
| `refactoring-discipline.md` | Agent-driven refactoring is test-gated (green before AND after), one concern at a time, plan-first, and continuous — the workflow / cadence discipline that gates the clean-room re-writing protocol for a refactor. |
| `harness-adapter-shape.md` · `harness-adapter-shape-schemas.md` | Every adapter in the 17-harness cohort performs host discovery, converges on the sibling adapter shape, declares divergences, carries the adapter-test matrix, and ships a co-resident STANDARD-CONVENTION-PIN. |
| `i18n-discipline.md` · `i18n-discipline-locale-cohorts.md` | Translated surfaces ship in every Modern-Dev-Cohort locale or surface the gap — framework i18n integration, machine-seed + human-review gate, per-locale glossary, RTL + hreflang discipline. |
| `plain-language.md` | User-facing narrative free of process-tooling leak — AI / harness / plan-stage / process vocabulary stays out of README / docs / site copy; the `plain-language-grep` matcher enforces the closed set with domain carve-outs. |

### Code craft (M13, per language)

| Rule | Concern |
|------|---------|
| `code-craft-conventions.md` | Universal code-craft delegation stub for languages without a dedicated rule. |
| `code-craft-python.md` | Python — SOLID, modern type hints, Google-style docstrings, pytest, security guardrails. |
| `code-craft-shell.md` | Shell — POSIX bash + PowerShell idioms, strict mode, injection prevention. |
| `code-craft-markdown.md` | Markdown / prose — purpose-driven structure, sentence-level justification, active voice. |
| `clean-architecture-layers.md` | Domain / Application / Infrastructure / Presentation layer discipline. |

### Context, memory & conventions

| Rule | Concern |
|------|---------|
| `context-management.md` · `context-management-protocol.md` · `context-management-scratch.md` · `context-management-budget.md` | Context-rot mitigation, blind-execution protocol, externalization, plan-workflow scratch convention, per-task effort calibration + context-budget discipline. |
| `auto-memory.md` · `auto-memory-topic-files.md` | Auto-memory lifecycle — topic files, MEMORY.md index, promotion ledger. |
| `persistent-conventions-vigilance.md` · `persistent-conventions-vigilance-checklist.md` | Ecosystem-convention adherence and proactive artifact evolution (CM-22). |
| `large-file-generation.md` | Large file generation via incremental appends (CM-23). |
| `token-budget-discipline.md` | The 500-token ceiling on always-on rule bodies. |
| `large-file-reading.md` | Size-aware file reading — pre-read assessment, locate-before-read, structural traversal, segmentation; the read-side analogue of `large-file-generation.md`. |
| `token-efficiency-rewrite.md` · `token-efficiency-rewrite-protocol.md` | Token-efficiency as a rewrite discipline — preserve L2 semantic content + L3 structural anchors, discard L1 scaffolding; pairs with `token-budget-discipline.md` (caps) to fit the always-on ceiling. |

### Agent orchestration & interaction

| Rule | Concern |
|------|---------|
| `agent-orchestration.md` · `agent-orchestration-patterns.md` | Agent / agent-team deployment patterns, return contracts, context isolation. |
| `agent-capability-discipline.md` · `agent-capability-discipline-matrix.md` | Per-harness agentic-capability matrix across the 17-harness cohort — MCP support, sub-agent dispatch, tool-surface restriction, agent-memory convention, output-style / custom-command / hooks / skills surfaces. |
| `multi-agent-workflow.md` · `multi-agent-workflow-shape.md` | Independent-critique / open-loop / dynamic multi-agent execution as an available, specified capability — opt-in and default-off under the agnostic posture; orchestration mechanics owned by `agent-orchestration.md`. The path-filtered companion carries the four-property capability-shape enumeration, the model- and effort-agnostic detail, the synthesis-quality-and-lean-main-thread form, and the seriousness-scaling recommendation table. |
| `tool-use-discipline.md` · `tool-use-discipline-failure-tells.md` | Ordinary tool use as a disciplined loop — independent calls batched in one turn (the ordinary-tool-tier generalization of the agent-tier single-message parallel-launch), the observe → decide → act cadence named, and iteration to a verifiable exit rather than a fixed count. The path-filtered companion carries the five failure-shape diagnostics for §1 / §2 / §3. |
| `interactive-questions.md` · `interactive-questions-canonical-shapes.md` · `interactive-questions-sweep-matchers.md` · `interactive-questions-detail.md` | The structured-inquiry channel — Structured-Inquiry Shape, option annotation, sweep matchers, authoring discipline + anti-patterns. |
| `determinism.md` · `recommend-next-step.md` | Deterministic output shape across command and skill surfaces; the `(Recommended)`-in-header invariant; every terminal surface closes with a definitive named next step. |
| `session-closure.md` · `session-closure-scaling.md` | Every session — ad-hoc conversational sessions included, not only plan phases — ends with a formal, verifiable close: a terminal Recommended Next Step, a done/deferred ledger, and a verification attestation; harness-agnostic. The path-filtered companion carries the under-/over-close scaling bound and the delta-only re-engagement mechanics. |
| `performance-discipline.md` | Per-class performance budgets and quantitative gates. |

## Conventions

- One flat `.md` file per rule; kebab-case filenames; companion files suffix the parent name with the aspect.
- Every file carries the canonical single-line SPDX license header and a non-empty `description` frontmatter field.
- Cross-references between rules use relative paths and are reciprocal in the `## Bindings` section.

## Operating in this folder

- **File shape.** YAML frontmatter (`name`, `description`, `pathFilter`, `alwaysApply`) → the single-line SPDX license header (HTML-comment form) → the obligations body → a closing `## Bindings (§0.j five-direction)` section. The frontmatter `description` field MUST be populated; the PreToolUse frontmatter check rejects an empty one.
- **Token budget.** An always-on body (`alwaysApply: true`, empty `pathFilter`) is capped at 500 substantive tokens per `token-budget-discipline.md`; over-budget content decomposes into a path-filtered companion rather than inflating the parent.
- **Reciprocal bindings.** Every `## Bindings` cross-reference has a matching back-pointer at the cited peer; half-edges fail the bindings-reciprocity gate.
- **Harness-neutral prose.** This folder is swept by the agnosticism and reference-token matchers. Name a harness only by its catalog slug — one entry among the registered set — never by a privileging brand phrase, and pre-set no model or effort preference.
- **Adding a rule:** author the file with the shape above, add its row to the registry table above, and wire it into the rule graph via its `## Bindings` section; decide always-on vs companion by the token budget. **Splitting an over-budget always-on rule:** move depth to a `<parent>-<aspect>.md` companion, leave the `(Companion Sub-Rule Anchor)` pointer in the parent, and make both `## Bindings` blocks cite each other.
- Validate every change with `python -m apothem.conformity.gate --all .` (frontmatter, token-budget, bindings-reciprocity, agnosticism, reference-token matchers) and `python -m pytest`.

## Bindings (§0.j five-direction)

- **Drives →** The rule registry tables above and the file shape every rule in this folder follows, including its closing `## Bindings` section.
- **Satisfies →** The agent-guidance locality canon in `AGENTS.md` (each folder's operating contract lives in its README).
- **Established by ↑** `AGENTS.md` (the root agent-instruction canon). `rules/agents-md-convention.md` (the per-folder README contract). `rules/bidirectional-binding.md` (the five-direction notation this folder's rules use). `rules/token-budget-discipline.md` (the always-on budget that decides parent versus companion).
- **Gated by ←** `scripts/dev/check_readme_file_coverage.py --strict` (every shipped rule is named here). The propagation manifest's `README.md` exclusion (this file never ships into a harness discovery directory, where it would load as a rule).
- **Cross-bound with ↔** `agents/README.md` + `commands/README.md` (the sibling contracts for the other convention directories).
