<!-- SPDX-License-Identifier: MIT -->

# Commands

Slash-command definitions — flat `.md` files, each defining one `/command-name` invocable. A command file's YAML frontmatter declares the command's identity and argument surface; its body is the multi-step workflow the command runs. Forty-five commands register at the top level — the seven **planning-pipeline** stage commands plus the `/plan-amend` amendment command and the `/plan` wrapped-workflow orchestrator, the thirteen **research-pipeline** stage commands plus the `/research` wrapped-workflow orchestrator, the eleven **audit / review** passes plus the `/audit` wrapped-workflow orchestrator and the `/fortress` closed-loop hardening orchestrator, three **cohort** commands (`test-suite`, `eval`, `release-readiness`), four **deployment / elevation** commands (`freshify`, `github-deploy-fresh`, `github-deploy-next`, `elevate`), and two **operator-workflow** commands (`workflow`, `projectify`). Each planning and research stage is an independently invocable `/plan-<stage>` / `/research-<stage>` command, and the eleven audit passes are each individually invocable.

## Plan pipeline — seven first-class `/plan-<stage>` commands

The end-to-end planning workflow — prose → spec → plan suite → review → conditional architecture design → execution → status — is seven first-class commands, one per stage. Each is independently invocable as `/plan-<stage>`, preserving every per-stage gate and structured-inquiry discipline, with the three-tier scalability framework (small / medium / large, via [`../lib/plan_tiers.py`](../lib/plan_tiers.py)) governing suites up to thousands of tasks. Each non-initial stage carries a `## Sequence Gate` that refuses out-of-order invocation (absent `--override`, recorded as a finding) with a definitive `Blocked: run /plan-<predecessor> first` message. `/plan-design` runs only when `/plan-review` classifies the suite as architecture-bearing; non-architecture suites proceed directly to `/plan-execute`. `/plan-status` is orthogonal read-only at any point. `/plan-amend` amends an existing suite without destroying prior resolved decisions, re-deriving only affected downstream artifacts.

Each command is a flat top-level command file, registered by the non-recursive `commands/*.md` glob like every other command:

| Command | File | Purpose |
|---------|------|---------|
| `/plan-spec` | [`plan-spec.md`](plan-spec.md) | Refine free-form prose / raw notes into a spec-grade `_spec/spec.md`. Six transformation phases under four operational disciplines; every ambiguity surfaces via the structured-inquiry channel. `--quick` writes a lightweight project-local plan file instead. |
| `/plan-generate` | [`plan-generate.md`](plan-generate.md) | Generate a complete Master Plan Suite from the user's raw prose / requirements. |
| `/plan-review` | [`plan-review.md`](plan-review.md) | Forensic audit of an existing plan suite — prose fidelity, internal consistency, quality / gap analysis — then refine through interactive Q&A. |
| `/plan-design` | [`plan-design.md`](plan-design.md) | Conditional architecture gate. Produces `_inputs/design.md` for architecture-bearing suites after review and before execute; skipped explicitly for non-architecture suites. |
| `/plan-audit` | [`plan-audit.md`](plan-audit.md) | Closed-loop pipeline audit and active remediation — brings a suite to zero open findings, writes bounded reports under `_outputs/`, routes residual work to `*-maintenance`. |
| `/plan-execute` | [`plan-execute.md`](plan-execute.md) | Execute a specific phase from a Master Plan Suite with conformity checking and quality gates. |
| `/plan-status` | [`plan-status.md`](plan-status.md) | Read-only plan-suite progress report — status against task / phase / artifact dimensions, no modification. |
| `/plan-amend` | [`plan-amend.md`](plan-amend.md) | Amend / extend / refine / revert / weave an existing plan suite without destroying prior resolved decisions; re-derives only affected downstream artifacts and recommends the affected downstream stage (`/plan-review`). |
| `/plan` | [`plan.md`](plan.md) | The plan pipeline wrapped as a single dynamic multi-agent workflow (not itself a stage) — drives a planning mission from raw prose to executed phases by dispatching the first-class stages (`plan-spec → plan-generate → plan-review → plan-design` conditional `→ plan-execute`) as workflow phases under named Handoff-Manifest return contracts, routing each stage hand-off through a refute-by-default verification pass, and emitting a deterministic result with a single recommended next move. Stage logic stays first-class in `plan-*.md`; chaining + dispatch are opt-in via `--autonomous`, halting at each stage boundary by default. |

The top-level `command_skills` propagation registers every planning-pipeline command (the seven stages, `/plan-amend`, and the `/plan` wrapped-workflow orchestrator) and the audit / review commands alike by the non-recursive `commands/*.md` glob.

## Research pipeline — thirteen first-class `/research-<stage>` commands

The end-to-end research workflow — idea → question → theory → sources → synthesis → proposal → study design → experiment → analysis → paper → peer review → publish → disseminate — is thirteen first-class commands, one per stage, mirroring the plan pipeline. Each is independently invocable as `/research-<stage>`, with a `## Sequence Gate` that refuses out-of-order invocation (absent `--override`, recorded as a finding) with a definitive `Blocked: run /research-<predecessor> first` message, and a Handoff Manifest chaining each stage to the next. The pipeline operates under ten rigor mandates (authoritative sources · reproducibility · falsifiability · citation integrity · preregistration · ethics / conflicts · statistical rigor · open-science / FAIR · reporting-guideline conformance · theoretical grounding / impact) and resolves the [`research-suite`](../skills/research-suite/) knowledge surface by path.

| Command | File | Purpose |
|---------|------|---------|
| `/research-ideate` | [`research-ideate.md`](research-ideate.md) | Zero-ideation entry — formulate the problem space from a domain seed, generate and rank candidate research questions, and frame the opportunity the spec stage consumes. |
| `/research-spec` | [`research-spec.md`](research-spec.md) | Frame a candidate question into a spec-grade research spec — falsifiable hypotheses, scope, inclusion / exclusion criteria, success metrics. `--quick` writes a lightweight project-local research brief. |
| `/research-theory` | [`research-theory.md`](research-theory.md) | Build the foundational conceptual framework and theory-of-change — name the constructs, their relationships, and the mechanism the study tests. |
| `/research-sources` | [`research-sources.md`](research-sources.md) | Systematic source collection — decompose into sub-queries, parallel discovery via `research-scout` + `multi-source-research`, dedup, rank by authority / recency / relevance, screen against inclusion criteria, extract per source. |
| `/research-synthesis` | [`research-synthesis.md`](research-synthesis.md) | State-of-the-art map + literature matrix + explicit gap statement; every load-bearing claim adversarially verified by `fact-checker` via the `source-synthesis` skill. |
| `/research-proposal` | [`research-proposal.md`](research-proposal.md) | Objectives / aims, feasibility assessment, impact pathway, and the preregistration plan — the fundable proposal the study design operationalizes. |
| `/research-design` | [`research-design.md`](research-design.md) | Operationalize hypotheses into testable predictions; design variables / controls / sample / instruments / power analysis / threats-to-validity; freeze the analysis plan as a preregistration. |
| `/research-experiment` | [`research-experiment.md`](research-experiment.md) | Run the designed study and capture raw data with full provenance + a reproducibility manifest (environment, seed, protocol, version pins). |
| `/research-analysis` | [`research-analysis.md`](research-analysis.md) | Analyze per the preregistered plan — effect sizes + confidence intervals, robustness / sensitivity checks, disclosed deviations, figures / tables. |
| `/research-paper` | [`research-paper.md`](research-paper.md) | Assemble a top-tier paper draft (abstract → conclusion + references) from synthesis + design + analysis; every citation verified to resolve to a real source. |
| `/research-review` | [`research-review.md`](research-review.md) | Peer-review-grade adversarial critique — reviewer scorecard (novelty / rigor / reproducibility / clarity / ethics) + a severity-triaged required-revision list. |
| `/research-publish` | [`research-publish.md`](research-publish.md) | Venue-formatted submission package — supplementary materials, data / code-availability statement, cover letter, ethics / COI declarations, preprint / DOI plan, submission checklist. |
| `/research-disseminate` | [`research-disseminate.md`](research-disseminate.md) | Post-acceptance dissemination, impact, and archival — plain-language summary, channel plan, FAIR data / code deposit, persistent-identifier registration, and the impact-tracking record. |
| `/research` | [`research.md`](research.md) | The research pipeline wrapped as a single dynamic multi-agent workflow (not itself a stage) — drives a research mission from a raw idea to a disseminated, peer-reviewed paper by dispatching the stages as workflow phases under named Handoff-Manifest return contracts, routing each hand-off through a refute-by-default verification pass. Chaining is opt-in via `--autonomous`, halting at each stage boundary by default; `--quick` runs `research-sources` + `research-synthesis` only for a single-shot cited report. |

## Audit / review passes

Operator-driven review passes against a deployed repository. Each walks a defined surface and emits a severity-triaged (HIGH / MEDIUM / LOW) findings artifact under the consuming suite's `_inputs/` directory with concrete-driver rationale per finding. The [`/audit`](audit.md) **wrapped-workflow orchestrator** drives all eleven as a single parallel sweep — the audit-fortress analogue of `/plan` and `/research` — fanning the dimensions out under named findings return contracts, refute-by-default-verifying each finding, and synthesizing one deduplicated, severity-triaged report. `/audit` is report-only (remediation routes to `/elevate` or the owning surface); each pass below is also individually invocable.

The [`/fortress`](fortress.md) **closed-loop hardening orchestrator** closes the loop report-only `/audit` opens: it detects through `/audit`, adversarially verifies each finding, remediates every survivor at its owning surface, re-audits in a bounded loop until the walls hold, and gates the result through `/release-readiness` — the production-hardening analogue of `/plan` and `/research`. Distinct from `/elevate` (broad open-loop whole-repo SOTA lift) and `/release-readiness` (single READY / BLOCKED verdict), `/fortress` is the security/production-scoped detect → remediate → re-audit → gate loop.

| Command | Surface audited |
|---------|-----------------|
| [`code-review.md`](code-review.md) | Per-file code-quality review — readability, naming, complexity, magic numbers, comment quality, against the four code-craft rules and the ten quality dimensions. |
| [`code-audit.md`](code-audit.md) | Cross-file forensic code audit — hidden coupling, layer-boundary violations, type-hint accuracy, coverage gaps, dead code, duplicates. The cross-file counterpart to `/code-review`. |
| [`architecture-review.md`](architecture-review.md) | Architectural-integrity review against `_inputs/design.md` and the clean-architecture layer discipline. |
| [`docs-review.md`](docs-review.md) | Documentation review against the Markdown code-craft and ten-dimension rules — prose clarity, link integrity, citation completeness, public-API coverage. |
| [`security-audit.md`](security-audit.md) | Security posture audit against OWASP ASVS, OWASP Top 10, and CWE Top 25 — secrets, injection surfaces, deserialization, path-traversal, dependency CVEs. |
| [`dependency-audit.md`](dependency-audit.md) | Per-dependency audit — license compatibility, CVE status, deprecation, pinned-vs-range posture, transitive depth. |
| [`supply-chain-audit.md`](supply-chain-audit.md) | Supply-chain audit against SLSA + Sigstore + SBOM standards — provenance, signing, SBOM completeness, action pinning. |
| [`threat-model-audit.md`](threat-model-audit.md) | Threat-modeling audit against STRIDE + PASTA — trust boundaries, threat actors, mitigation posture, residual risk. |
| [`perf-audit.md`](perf-audit.md) | Performance audit against the per-class budgets in `../rules/performance-discipline.md`, via the benchmark drivers under `../benchmarks/`. |
| [`a11y-audit.md`](a11y-audit.md) | Accessibility audit against WCAG 2.2 AA — semantic HTML, ARIA, keyboard-navigability, contrast, alt-text. |
| [`ux-review.md`](ux-review.md) | Developer-experience review — CLI ergonomics, installation flow, documentation discoverability — against clig.dev, the NN/g heuristics, and GNU coreutils conventions. |

## Cohort commands

Operator-driven workflow commands, each orchestrating a multi-step engagement across its own skill / agent cohort. Output lands at the consuming suite's `_inputs/` directory with concrete-driver rationale per finding.

| Command | Cohort | Purpose |
|---------|--------|---------|
| [`test-suite.md`](test-suite.md) | developer | Behavior-first test authoring and execution — discover the host's test framework, author behavior-shaped AAA tests, run them, triage failures, and report coverage gaps against critical paths. |
| [`eval.md`](eval.md) | ai-engineering | Run a model-agnostic language-model evaluation campaign — define dataset and scorer, score every output, aggregate metrics with a per-category breakdown, and surface regressions against the prior baseline. |
| [`release-readiness.md`](release-readiness.md) | developer / security | Pre-release gate sweep against the production-ready discipline — quality matrix, dependency risk, supply-chain checks, visibility surfaces, CHANGELOG currency, and version-to-tag consistency, emitting a single READY / BLOCKED verdict. |

## Deployment / elevation

Repository-wide freshening, release, and SOTA-elevation commands. Each routes
every destructive step through the structured-inquiry confirmation channel with
in-place freshening as the default.

| Command | Purpose |
|---------|---------|
| [`freshify.md`](freshify.md) | Host- and forge-AGNOSTIC freshening core — purges caches and stale artifacts, removes legacy/obsolete narrative and back-references, normalizes file/folder naming and drives every surface to maximal naturalness and coherence, enforces a current-version-only facade, and drives the host's discovered gates to green. Specialized by `/github-deploy-fresh`. |
| [`github-deploy-fresh.md`](github-deploy-fresh.md) | GitHub specialization of `/freshify` — a single fresh `release: <repo-name> v0.1.0` to `origin/main`, strictly-green (maximal-score where applicable) workflows, a curated first-version CHANGELOG, and a trace-free repository (delete+recreate available as a metadata-preserving, confirmation-gated `MAY`). |
| [`github-deploy-next.md`](github-deploy-next.md) | The next-release-cycle sibling — merge PRs, resolve issues, SemVer bump, Keep-a-Changelog roll, tag + sign + publish (signing host-discovered), and current-version release notes; merge and publish are confirmation-gated. |
| [`elevate.md`](elevate.md) | Aggressive, relentless, multi-agent, zero-trust, open-loop **master** repository elevation — a major multi-pass undertaking (not a quick amendment) that detects the technically-auditable nuances by dispatching the report-only `/audit` fortress (reusing its eleven passes, never re-deriving them), runs bespoke critique over the SOTA/elevation dimensions no audit covers, stops at each nuance folder-by-folder, file-by-file, line-by-line, remediates with the most appropriate action through the dimension-native skills (destruction included), propagates every change across the reference graph, and culminates trace-free via `/freshify`. |

## Operator workflow

General-purpose operator commands that harness a whole mission end to end. Each emits deterministic output closing on a single recommended next move; multi-agent dispatch and multi-step autonomy are opt-in / confirmation-gated, never default-on.

| Command | Purpose |
|---------|---------|
| [`workflow.md`](workflow.md) | Workflow-harnessing command (entry form `/workflow <<mission>>`) — decomposes a mission and drives genuinely-independent multi-agent dynamic workflows under named return contracts, subjects every finding to a refute-by-default verification pass before it survives, and self-augments from current authoritative sources, not memory alone. |
| [`projectify.md`](projectify.md) | Chat-app Project elevation command — produces the three deliverables (Description, Instruction, knowledge Files) for a Claude Project / ChatGPT Custom GPT / Gemini Gem through a structured-inquiry-saturated elicitation, holding knowledge files within a measurable per-platform context budget. |

## Frontmatter contract

Command frontmatter is validated against [`../schemas/command.schema.json`](../schemas/command.schema.json). Observed fields:

- `name` — command identifier; the slash command is `/<name>`.
- `version` / `updated` — semantic version and ISO-8601 revision date.
- `description` — statement of what the command does, 1,024 characters or fewer: several harnesses install each command as a skill, where the [Agent Skills](https://agentskills.io/specification) limit applies (`command.schema.json` enforces it).
- `argument-hint` — the command's argument / flag surface, shown in invocation help.
- `disable-model-invocation` — when `true`, the command is operator-invoked only and is never auto-invoked by the model.
- `portability` — the command's portability class across harnesses (e.g. `universal`).
- `allowed-tools` — the tools a harness may run without asking while the command is active. Read-only by default (`Read, Glob, Grep`); a side-effecting tool appears only as a scoped rule such as `Bash(git log *)`. The schema rejects `*` and bare `Bash`, `PowerShell`, `Write`, `Edit`, `NotebookEdit`, and `WebFetch`.

The body after the frontmatter is the command's workflow specification: ordered steps, gates, structured-inquiry invocation points, and output contract.

## Model invocation

`disable-model-invocation: true` makes a command operator-invoked only: the model never runs it on its own. With `false`, the model may run the command when a request matches its description. This table records every command's current setting; `tests/unit/test_command_invocation_table.py` checks it against the command files, so a change to a command's flag updates its row in the same change-set.

TODO(clarify): the reason for each setting is not recorded, and two patterns need an operator decision before reasons can be written here. In the plan pipeline, the `/plan` orchestrator is operator-only while every stage command is model-invocable. In the research pipeline, the `/research` orchestrator and four stages (`/research-ideate`, `/research-theory`, `/research-proposal`, `/research-disseminate`) are operator-only while the other nine stages are model-invocable, although `/research-theory` and `/research-proposal` describe the same pipeline-chained hand-off as the model-invocable stages.

| Command | `disable-model-invocation` | Section |
| --- | --- | --- |
| `/plan` | `true` | Plan pipeline (orchestrator) |
| `/plan-spec` | `false` | Plan pipeline |
| `/plan-generate` | `false` | Plan pipeline |
| `/plan-review` | `false` | Plan pipeline |
| `/plan-design` | `false` | Plan pipeline |
| `/plan-audit` | `false` | Plan pipeline |
| `/plan-execute` | `false` | Plan pipeline |
| `/plan-status` | `false` | Plan pipeline |
| `/plan-amend` | `false` | Plan pipeline |
| `/research` | `true` | Research pipeline (orchestrator) |
| `/research-ideate` | `true` | Research pipeline, stage 1 |
| `/research-spec` | `false` | Research pipeline, stage 2 |
| `/research-theory` | `true` | Research pipeline, stage 3 |
| `/research-sources` | `false` | Research pipeline, stage 4 |
| `/research-synthesis` | `false` | Research pipeline, stage 5 |
| `/research-proposal` | `true` | Research pipeline, stage 6 |
| `/research-design` | `false` | Research pipeline, stage 7 |
| `/research-experiment` | `false` | Research pipeline, stage 8 |
| `/research-analysis` | `false` | Research pipeline, stage 9 |
| `/research-paper` | `false` | Research pipeline, stage 10 |
| `/research-review` | `false` | Research pipeline, stage 11 |
| `/research-publish` | `false` | Research pipeline, stage 12 |
| `/research-disseminate` | `true` | Research pipeline, stage 13 |
| `/audit` | `true` | Audit / review passes (orchestrator) |
| `/fortress` | `true` | Audit / review passes (orchestrator) |
| `/code-review` | `true` | Audit / review passes |
| `/code-audit` | `true` | Audit / review passes |
| `/architecture-review` | `true` | Audit / review passes |
| `/docs-review` | `true` | Audit / review passes |
| `/security-audit` | `true` | Audit / review passes |
| `/dependency-audit` | `true` | Audit / review passes |
| `/supply-chain-audit` | `true` | Audit / review passes |
| `/threat-model-audit` | `true` | Audit / review passes |
| `/perf-audit` | `true` | Audit / review passes |
| `/a11y-audit` | `true` | Audit / review passes |
| `/ux-review` | `true` | Audit / review passes |
| `/eval` | `true` | Cohort commands |
| `/release-readiness` | `true` | Cohort commands |
| `/test-suite` | `true` | Cohort commands |
| `/elevate` | `true` | Deployment / elevation |
| `/freshify` | `true` | Deployment / elevation |
| `/github-deploy-fresh` | `true` | Deployment / elevation |
| `/github-deploy-next` | `true` | Deployment / elevation |
| `/projectify` | `true` | Operator workflow |
| `/workflow` | `true` | Operator workflow |

## Conventions

- One flat `.md` file per command; filename stem equals the `name` field and the slash-command name.
- Every file carries the canonical single-line SPDX license header.
- Plan-pipeline commands are also surfaced as skills; the `/plan-<stage>` command family resolves the plan-suite template under [`../skills/plan-suite/`](../skills/plan-suite/) by path.
- Harness installation of custom slash commands is controlled by each adapter's `capabilities.yml` `custom_command_support` value. `yes` means the adapter propagates this cohort to a native command directory; `no` means the surface is unsupported; `discovery-pending` means the adapter must not assume native support until its pin is refreshed.
- Planning-technique discipline applied during these workflows is specified in `../rules/planning-techniques.md`.

## Operating in this folder

- **This folder is swept by the agnosticism matcher.** Command definitions stay harness-neutral: name no harness, model, or tool as privileged, and **do not pre-set an effort or model preference** in frontmatter or body. Native-support routing is a per-adapter `capabilities.yml` concern, not a per-command claim.
- Command files carry determinism and recommend-next-step gates: a definitive forward-move block closes a workflow's terminal surface, and directive prose stays hedging-free.
- **Adding a command:** author a flat `commands/<name>.md` file (stem = `name` = slash name) with schema-valid frontmatter and a workflow body. The discovery glob is non-recursive, so a command must sit at the top level (not nested in a subdirectory) to register. Surface ambiguity through the structured-inquiry channel or a `TODO(clarify)` marker — never invented.
- **A command and a skill sharing a name** (`projectify`, `workflow`): where an install converts commands into skills inside the directory it also installs `skills/` into, the command is left out and the skill holds the name — the same resolution a harness that loads both applies (the skill wins). Installs that keep commands and skills apart ship both. `tests/unit/test_skill_command_collisions.py` fails on any shared name whose installed bodies diverge.
- A documented public command surface change updates its `site/content/docs/` page in the same change-set.
- Validate with `python -m apothem.conformity.gate --all .` (name+description floor, determinism, recommend-next-step) and `python -m pytest`.

## Bindings (§0.j five-direction)

- **Drives →** The command catalog above and the flat-file shape every slash command in this folder follows.
- **Satisfies →** The agent-guidance locality canon in `AGENTS.md` (each folder's operating contract lives in its README). The registry entry each command's own Bindings cite as its catalog row.
- **Established by ↑** `AGENTS.md` (the root agent-instruction canon). `rules/agents-md-convention.md` (the per-folder README contract). `rules/determinism.md` + `rules/recommend-next-step.md` (the output-structure and forward-move gates every command carries).
- **Gated by ←** `scripts/dev/check_readme_file_coverage.py --strict` (every shipped command is named here). The propagation manifest's `README.md` exclusion (this file never ships into a harness discovery directory, where it would register as a command).
- **Cross-bound with ↔** `agents/README.md` + `rules/README.md` (the sibling contracts for the other convention directories).
