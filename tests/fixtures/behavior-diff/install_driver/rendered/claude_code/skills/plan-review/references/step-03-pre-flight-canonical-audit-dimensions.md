<!-- SPDX-License-Identifier: MIT -->

### Step 2.7: Pre-Flight Canonical-Audit Dimensions

> Mandatory pre-flight sweep firing before the Step 3 forensic audit. These 9 dimensions are not optional; they apply at every seriousness ≥ PERSONAL_USE and on every `--focus` value (including `all`). Each dimension specifies (i) detection logic, (ii) finding classification (severity floor + category), (iii) routing to the receiving scorecard. Findings emitted here are appended to the Step 6.1 Findings Registry and re-checked at Step 11 Final Verification.
>
> Deploy an Audit Team (CM-25A) — one agent per dimension where parallel coverage is feasible (a–i are non-overlapping by detection target). Each agent returns pass/fail + per-finding evidence (CM-25C; max 200 tokens per agent; required fields: `dimension`, `findings[]` with `evidence`, `severity`, `category`).

**2.7.a — Foundational Naming-Drift Detection.**

- **Detection logic.** Sweep every host artifact (source files, configs, docs, plan-suite files) for naming-token drift against the ratified per-language conventions: kebab-case (filenames, folders, slugs), snake_case (Python identifiers, env vars where ratified), PascalCase (Python classes, TypeScript types, Rust types), camelCase (TypeScript identifiers, Go exported), UPPER_SNAKE_CASE (constants). For each token, compare the observed form against the ratified convention for its scope; flag every mixed-convention occurrence (e.g., `UserService` alongside `user_service` for the same entity; `kebab-case-file.py` in a snake_case-Python corpus).
- **Classification.** **MEDIUM** severity floor; category **Internal Consistency**. Promote to **HIGH** when the drift crosses a public-API surface (exported identifier, CLI flag, config key).
- **Routing.** Findings route to the **Internal Consistency Scorecard** (Step 3.10) alongside Step 3.3 Naming Coherence outcomes; pre-flight findings are pre-seeded so Step 3.3 inherits them without re-discovery.

**2.7.b — State-Freshness Sweep.**

- **Detection logic.** Sweep `PROGRESS.md` / `PLAN-NOTES.md` / every `phases/**/PHASE.md` / every `phases/**/REPORT.md` for stale references: (i) references to removed APIs or renamed identifiers (cross-check against the current source tree), (ii) dead URLs (links to repositories, vendor docs, RFCs that 404 or redirect), (iii) files cited at paths that no longer exist (moved or removed), (iv) decision references (D-N) pointing at decisions no longer in the Resolved Decisions table.
- **Classification.** **MEDIUM** severity floor; category **Internal Consistency**. Promote to **HIGH** when the stale reference is load-bearing for downstream `/plan-execute` (a critical-files-manifest entry, a Resumption Contract pointer).
- **Routing.** Findings route to the **Internal Consistency Scorecard** (Step 3.10); cross-fed into Step 3.6 Progress/State Consistency for synthesis.

**2.7.c — Scope-Evolution / Directive-Codification Propagation Audit.**

- **Detection logic.** Enumerate every operator-ratified directive (every decision in the suite's decision registry, every locked-decision-class citation per `rules/interactive-questions-canonical-shapes.md` §3.2.1). For each directive, verify it propagates to its declared target phase(s) and sub-phase(s) tasks — the directive's mandate is materially reflected in task descriptions, acceptance criteria, or scope boundaries of the target phases. A directive ratified but absent from its target phase is a silent omission.
- **Classification.** **HIGH** severity floor; category **Prose Fidelity** (the directive IS the prose contract per the suite's spec-relative anchoring). Promote to **Critical** when the omission affects an irreversible decision class (per `rules/operational-mandates.md` §CM-9).
- **Routing.** Findings route to the **Prose Fidelity Scorecard** (Step 2.6) — pre-flight findings raise the Step 2.6 grade ceiling (a directive omission caps Prose Fidelity at CONDITIONAL until resolved).

**2.7.d — Tooling-Reconsideration Audit.**

- **Detection logic.** Inspect the host's ratified toolchain — formatter (e.g., `ruff format` / `black` / `prettier`), linter (e.g., `ruff check` / `eslint` / `clippy`), type-checker (e.g., `mypy` / `pyright` / `tsc`), test framework (e.g., `pytest` / `vitest` / `cargo test`), docs generator (e.g., Fumadocs / Docusaurus / `mdBook`), CI provider (e.g., GitHub Actions / GitLab CI / CircleCI). For each, compare the host's ratified version (per `pyproject.toml` / `package.json` / `Cargo.toml` and sibling configs) against the tool's current SOTA release (vendor latest stable). Flag stale ratifications (e.g., `mypy` pinned at a version superseded by a newer release with material correctness improvements; `black` where the host's idiom drifted toward `ruff format`).
- **Classification.** **LOW** to **MEDIUM** advisory; category **Tooling-axis Quality** (per `rules/cognitive-identity.md` §1 seven-axes taxonomy — Tooling axis). Promote to **HIGH** only when the staleness blocks a CI-green gate (e.g., a deprecated tool version produces breaking changes against newer Python).
- **Routing.** Findings route to the **Quality Scorecard** (Step 4 — specifically the Standards sub-check 4.3 and the Tooling-axis surface).

**2.7.e — Harness-Cohort Audit.**

- **Detection logic.** At every phase or sub-phase that touches multi-harness work (any phase whose scope names ≥ 2 harness adapters, or whose outputs land under `src/apothem/harnesses/*`), verify the 17-harness adapter cohort is honored: `antigravity`, `claude_code`, `codebuddy`, `codex`, `cursor`, `gemini_cli`, `github_copilot`, `hermes`, `kimi_code`, `kiro`, `open_claw`, `opencode`, `qwen_code`, `trae`, `windsurf`, `zed`, `glm`. Any missing harness in a multi-harness-touching phase is a silent cohort drop.
- **Classification.** **HIGH** severity floor; category **Completeness**. Promote to **Critical** when the missing harness is operator-installed in the active project (verified via the host's harness registry).
- **Routing.** Findings route to the **Completeness Scorecard** (Step 4.1).

**2.7.f — i18n-Cohort Audit.**

- **Detection logic.** At every phase or sub-phase that touches i18n work (any phase whose scope names ≥ 2 locales, or whose outputs land under `docs/i18n/`, `locales/`, or sibling i18n surfaces), verify the 12-locale Modern dev cohort is honored: EN, ZH-CN, ES, PT-BR, FR, DE, JA, KO, RU, ID, AR, HI. Any missing locale in an i18n-touching phase is a silent cohort drop.
- **Classification.** **HIGH** severity floor; category **Completeness**. Promote to **Critical** when the missing locale is mandated by a published rollout commitment.
- **Routing.** Findings route to the **Completeness Scorecard** (Step 4.1).

**2.7.g — Widget-Class Audit.**

- **Detection logic.** At every phase or sub-phase that touches README widgets (any phase whose scope names README header / badge / activity-widget surfaces, or whose outputs land at the host's README), verify the 4 widget classes are honored: (i) Star History, (ii) contrib.rocks contributors graph, (iii) Repobeats activity pulse, (iv) Sponsors / Discord / Showcase badges. Any missing class in a widget-touching phase is a silent omission.
- **Classification.** **MEDIUM** severity floor; category **Completeness**. Promote to **HIGH** when the omission lands on a release-tier README that ships to a public registry.
- **Routing.** Findings route to the **Completeness Scorecard** (Step 4.1).

**2.7.h — Adoption-Maximization Audit.**

- **Detection logic.** At the adoption-surfaces phase, verify the 4 N2 adoption surfaces are honored: (i) Comparison page, (ii) Showcase / Users page, (iii) Discord / Slack community page, (iv) Blog / RSS feed surface. Any missing surface in that cohort is a silent omission.
- **Classification.** **MEDIUM** severity floor; category **Completeness**. Promote to **HIGH** when the omission affects a launch-blocker surface declared in the suite's release-readiness checklist.
- **Routing.** Findings route to the **Completeness Scorecard** (Step 4.1).

**2.7.i — Standard-Conformance Audit.**

- **Detection logic.** Pre-flight check: every adapter, config, framework, or tool the plan uses MUST adhere to its vendor-documented LATEST convention, with a **commit-SHA-pinned citation** and a **per-harness STANDARD CONVENTION PIN** where the artifact is a harness adapter. For each adapter / config / framework / tool reference, verify: (i) the citation names the vendor's canonical convention document with a commit-SHA-pinned URL (not a branch-pointed URL), (ii) the per-harness pin block carries the harness's ratified convention version, (iii) the cited version matches the vendor's current LATEST (no stale conformance). Unpinned-or-stale conformance is a silent fabrication risk per `rules/authority-inquiry.md` (M5 authority half).
- **Classification.** **HIGH** severity floor; category **Authority (M5)**. Promote to **Critical** when the unpinned reference governs a security-relevant adapter surface (auth, secrets, network egress).
- **Routing.** Findings route to the **Standards Scorecard** (Step 4.3) AND the **Risk Assessment** (Step 5.2 Strategic Risks — unpinned conformance is a long-tail supply-chain risk).

**Pre-flight emission contract.** Each dimension above emits at minimum a per-dimension verdict line (`2.7.{letter}: PASS | CONDITIONAL | FAIL — <count> findings`) recorded inline in PLAN-NOTES.md `## Pre-Flight Canonical-Audit`. Findings cross-link to the receiving scorecard per the Routing field above. The pre-flight verdicts feed Step 3 (Internal Consistency), Step 4 (Quality/Completeness/Standards), and Step 5 (Risk) without re-discovery.
