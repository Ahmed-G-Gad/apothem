<!-- SPDX-License-Identifier: MIT -->

## Cross-Dimension Critique Axes

Each nuance is zero-trust-critiqued across the full axis list. To suppress redundancy, the axes split into two tiers: the **audit-detected tier** (detected by dispatching `/audit` per stanza 2 — `/elevate` consumes the findings, never re-derives them) and the **`/elevate`-bespoke tier** (the SOTA-and-elevation dimensions no audit pass covers, critiqued in stanza 3). Each tier is a seed to extend comprehensively per the "etc." extension rule.

**Audit-detected tier** — owned by the eleven first-class passes, dispatched through `/audit`:

| Axis cluster | Owning audit pass | Critiques |
| ------------ | ----------------- | --------- |
| Code quality · naming · complexity · magic numbers · comment quality | `/code-review` + `/code-audit` | Per-file and cross-file code craft against the four code-craft rules and the ten quality dimensions; hidden coupling, dead code, duplicates. |
| Architecture · layering · modularity | `/architecture-review` | Architectural integrity against the clean-architecture layer discipline (`rules/clean-architecture-layers.md`). |
| Documentation · links · citations · public-API coverage | `/docs-review` | Markdown code-craft + ten-dimension prose review, link integrity, citation completeness. |
| Security · injection · secrets · deserialization · path-traversal | `/security-audit` + `/threat-model-audit` | OWASP ASVS / Top 10 / CWE + STRIDE / PASTA trust boundaries and residual risk. |
| Dependencies · CVEs · pins · provenance · SBOM · signing | `/dependency-audit` + `/supply-chain-audit` | Per-dependency license / CVE / deprecation + SLSA + Sigstore + SBOM posture. |
| Performance · budgets | `/perf-audit` | The per-class budgets in `rules/performance-discipline.md` via the benchmark drivers. |
| Accessibility | `/a11y-audit` | WCAG 2.2 AA — semantic HTML, ARIA, keyboard-navigability, contrast, alt-text. |
| Developer experience · CLI ergonomics · install flow | `/ux-review` | clig.dev + NN/g heuristics + GNU coreutils conventions. |
| Test rigor · coverage | `/test-suite` | Behavior-shaped coverage of critical paths. |
| Language-model output quality | `/eval` | Model-agnostic evaluation campaign, where the host carries one. |

**`/elevate`-bespoke tier** — critiqued only here (no audit pass covers them):

- **Currency** — reflects current SOTA, not a superseded convention; deprecated APIs, patterns, and idioms are replaced with their current equivalents through documented migration paths, language and runtime targets are raised where safe, legacy shims and polyfills no longer needed are removed, and the ecosystem's current standard tooling and stack conventions are adopted where the host runs a superseded toolchain? Where the host's OWN uniform convention has itself fallen behind the ecosystem's current standard structure / layout / formatting, that gap is surfaced as a Currency finding routed through inquiry (judgment-dependent) rather than silently honored — the host's-ratified-convention default holds until the operator ratifies the migration.
- **Cross-sync** — synchronized with its dependents (CLAUDE.md, AGENTS.md, docs, website, tests, examples, README files) per `rules/propagation.md`?
- **Storytelling & clarity** — the narrative reads as one coherent, intuitive product story a newcomer-level end user follows on first pass, and the tree carries one logical end-to-end flow — a reader's journey from the entry surface through the whole project composes as a single coherent arc, with no dead-end or non-sequitur hop between neighboring surfaces?
- **Naming uniformity** — identifier and file/folder naming reveal intent and match the convention uniformly across cohorts per `rules/persistent-conventions-vigilance.md`?
- **Consolidation & modularity** — free of whole-repo redundancy and duplication; concerns drawn into clean module boundaries; fragmentation healed?
- **Necessity** — does the surface earn its place, or is it dead weight retained only by inertia? A surface with no consumer and no distinct purpose is a removal candidate per `rules/systemic-participation.md`, not a keep-by-default; where necessity is genuinely ambiguous rather than clearly absent, the preserve-and-record default at the Derived Constraints block governs, and any removal still clears its per-target confirmation.
- **Synthesis & coherence** — belongs to the same mental model as its neighbors; the whole tree composes as one united surface?
- **Interdependence & weaving** — wired and cross-linked to its siblings with reciprocal bindings per `rules/bidirectional-binding.md`; harmony, connectiveness, correlation across the whole?
- **Visualization & tabulation** — structural subject matter carries a current-reality diagram, and dense data carries a table, per `rules/visual-leverage.md`; analysis and stats are surfaced where they aid understanding?
- **Naturalness & normalization** — narrative reads as natural, human-authored product prose per `rules/plain-language.md`; surfaces normalized to one uniform voice and convention?
- **Definitiveness & airtightness** — tight, precise, airtight, with no hedging, no gaps, no contradiction per `rules/definitiveness.md`?
- **Scientific rigor, validity & soundness** — every claim is evidence-based, falsifiable where applicable, sound on its own terms, and free of folklore per `rules/ten-dimension-check.md` dimension 1 + `rules/authoritative-referencing.md`?
- **Agnosticism & abstraction** — privileges no harness, model, or tool; abstracts cleanly per `rules/agnostic-posture.md`?
- **Harness-component alignment** — every shipped harness component (skill, command, agent, hook, MCP surface) stays aligned with its per-harness latest official documentation and best-practices, carries durable cross-linked reusable structure, presets no model / effort / permissionMode and privileges no single harness (MAXIMAL agnosticism), and renders an expected, stable output / message structure generalized across all harnesses (determinism) — audited per the ecosystem-audit Harness-Component Alignment Dimension at `skills/ecosystem-audit/references/procedure.md` (which cites `rules/harness-adapter-shape.md` + `rules/agent-capability-discipline.md` + `rules/agnostic-posture.md` + `rules/determinism.md`). Detected through `/audit`, never re-derived here.
- **Extensibility & scalability** — accommodates future growth without rework; the seams future work needs are drawn?
- **Anti-orphanism** — reachable in the reference graph, with a consumer, an index entry, and producer attribution per `rules/systemic-participation.md`?
- **Backward-compatibility elimination** — carries no legacy or backward-compatibility cruft retained only to honor the past; the current form stands alone per `rules/freshness-facade.md`?
- **Configuration & portability** — configuration is separated from code with sane defaults and no environment-specific hardcoding (twelve-factor), so the surface is portable and reproducible across environments?
- **Internationalization** — user-facing text is externalized and translatable, and every locale surface stays synchronized with its source per `rules/i18n-discipline.md`?
- **Type-safety & static guarantees** — types are as strong and narrow as the domain allows, illegal states are made unrepresentable, exhaustiveness is checked at compile / static time rather than deferred to runtime, and `Any` is narrowed at the boundary? The packaging facet of this surface is the exemplar at `rules/sota-elevation-exemplars.md`, cited rather than restated.
- **Observability & diagnostics** — structured logging, deliberate log levels, no `print()` for operational output, and actionable error diagnostics per the criteria at `rules/sota-elevation-exemplars.md` §1 surface 7?
- **Tooling & developer-experience hygiene** — the project's own engineering toolchain is present and current: formatter / linter / type-checker / pre-commit / editorconfig configured, reproducible one-command setup, and fast local feedback? (Distinct from the `/ux-review` end-user-CLI row in the audit-detected tier, which critiques the shipped CLI's ergonomics, not the project's build toolchain.)
- **Aesthetic SOTA** — beyond mechanical conformity, the surface feels inevitable once seen (Filter 5) per `rules/sota-elevation.md`?
- **… (extend)** — professionalism, technicality, rigor, type safety and static guarantees, observability and actionable diagnostics, mastering, sophistication / contemporaneousness, conciseness, proofreading, precision, freshness, fidelity, robustness, correctness, intuition, recognizability, understandability, and every other dimension the underlying intent implies. The seven-axes-of-breadth taxonomy (Architecture · Concurrency · Performance · Security · Testing · Tooling · Observability) is the standing technical-axis frame.
