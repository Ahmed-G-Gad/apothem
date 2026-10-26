<!-- SPDX-License-Identifier: MIT -->

# Skills

Skill definitions — reusable, detectable techniques the harness loads on demand. Each skill is **one folder** whose canonical entry point is `SKILL.md`: a Markdown file with YAML frontmatter declaring the skill's identity and trigger surface, and a body specifying the procedure.

## Index

| Skill | Purpose | Invocability |
|-------|---------|--------------|
| [`ecosystem-audit/`](ecosystem-audit/) | Blind audit of the apothem ecosystem — detects drift, staleness, orphans, dangling references, conflicting directives, frontmatter invalidity, registry-vs-disk count mismatches, secret exposure. Optionally applies FIX-class fixes under `--fix`. | Model-invocable and user-invocable; also dispatchable from `/plan-execute` discovery context. |
| [`plan-suite/`](plan-suite/) | Master Plan Suite template — houses the canonical template defining plan-suite structure, mandates, core principles, and the Technical Co-Founder Framework. | Reference only: not user-invocable and not model-invocable. The `/plan` pipeline stages resolve the template by path. |
| [`research-suite/`](research-suite/) | Research Suite knowledge surface — houses the canonical research-suite template defining the suite directory structure, the ten rigor mandates (R1–R10), the thirteen-stage research lifecycle, and the Principal-Investigator Framework. | Reference only: not user-invocable and not model-invocable. The `/research` pipeline stages resolve the template by path. |
| [`test-authoring/`](test-authoring/) | Behavior-first test authoring with strict Arrange-Act-Assert discipline — discovers a unit's behavior contracts, writes failing AAA assertions covering happy path, edge boundaries, and failure modes, and reports residual coverage gaps. Authors tests only. | Model-invocable and user-invocable. |
| [`refactor-extract/`](refactor-extract/) | Scoped behavior-preserving extraction refactor — extracts what the code does, clean-room re-derives from the extracted specification, elevates quality against a named deficiency, and verifies behavior is preserved. | Model-invocable and user-invocable. |
| [`dependency-upgrade/`](dependency-upgrade/) | Changelog-reviewed, pinned, gate-verified dependency upgrade — enumerates outdated dependencies, reviews each changelog for breaking changes, applies host-policy pinned bumps, and runs the host's lint / test / type-check gates. | User-invocable only (it applies version bumps to manifests and lockfiles). |
| [`incident-runbook/`](incident-runbook/) | Operational incident runbook authoring and execution — produces a Trigger → Diagnosis → Action → Verification → Rollback procedure where every action carries an explicit, tested rollback path. | Model-invocable and user-invocable. |
| [`secret-rotation/`](secret-rotation/) | Safe secret-rotation template — detects the exposure surface, revokes the compromised credential at its issuer, re-issues a replacement, rewires config through env-var or secret-manager indirection, and verifies no plaintext residue remains. | User-invocable only (it revokes and re-issues live credentials). |
| [`vuln-triage/`](vuln-triage/) | Vulnerability and security-advisory triage — severity-classifies an advisory, maps it to the affected surface, determines exploitability and reachability, routes remediation, and records the disposition with rationale. | Model-invocable and user-invocable. |
| [`multi-source-research/`](multi-source-research/) | Multi-source research harness — decomposes the question, fans out parallel source-discovery queries, fetches and extracts per source, adversarially verifies each claim against two or more independent sources, and synthesizes a cited report. | Model-invocable and user-invocable. |
| [`source-synthesis/`](source-synthesis/) | Reconcile a fixed set of provided sources into one cited synthesis — extracts the claim set per source, reconciles agreements and contradictions, and separates consensus from contested ground while flagging coverage gaps. | Model-invocable and user-invocable. |
| [`prompt-engineering/`](prompt-engineering/) | Design and eval-validate structured prompts — clarifies the task contract, drafts a structured prompt with explicit role / instructions / output schema, defines happy / edge / adversarial eval cases, and iterates against them. | Model-invocable and user-invocable. |
| [`eval-harness/`](eval-harness/) | Build and run reproducible LLM evaluation harnesses — defines a labeled dataset, a scorer with an explicit pass criterion, a candidate runner, and an aggregated metrics report with per-category breakdowns, confidence, and regression detection. | Model-invocable and user-invocable. |
| [`workflow/`](workflow/) | Workflow-harnessing orchestration — decomposes a mission, dispatches genuinely-independent multi-agent dynamic workflows under named return contracts, runs a refute-by-default verification pass before any finding survives, and self-augments from current authoritative sources. Multi-agent dispatch is opt-in / confirmation-gated. | User-invocable only (entry form `/workflow <<mission>>`; it dispatches multi-agent runs). |
| [`projectify/`](projectify/) | Chat-app Project elevation — produces the three deliverables (Description, Instruction, knowledge Files) for a Claude Project / ChatGPT Custom GPT / Gemini Gem through a structured-inquiry-saturated elicitation, holding knowledge files within a measurable per-platform context budget. | Model-invocable and user-invocable. |
| [`diagram-authoring/`](diagram-authoring/) | Diagram authoring and rendering — one author → validate → render → export pipeline covering declarative diagrams (flowchart / sequence / state / class / ER / gantt) and data-driven visualizations, exporting to SVG / PNG / PDF via a headless renderer. | Model-invocable and user-invocable. |
| [`document-authoring/`](document-authoring/) | Long-form structured-document authoring — an approval-gated outline → draft → review pipeline with verified citations (every reference resolves to a real source) and a deterministic compile pipeline routing engine / bibliography / index passes by detected source features. | Model-invocable and user-invocable. |
| [`dev-toolkit/`](dev-toolkit/) | Engineering-discipline toolkit — sequences the core loops (structured debugging, test-first red-green-refactor, vertical-slice decomposition, requirement-to-issue breakdown) into one composable, gated procedure; cross-references sibling capabilities (does not duplicate them). | Model-invocable and user-invocable. |
| [`knowledge-wiki/`](knowledge-wiki/) | Index-first Markdown knowledge base grown from project sources — focus-driven source pages with their reading basis, typed relations with confidence, deterministic lint, change-triggered drift report, and hub analysis. | Model-invocable and user-invocable. |
| [`decision-matrix/`](decision-matrix/) | Weighted, evidence-cited choice between options — dealbreakers first, a sensitivity check on the weights, a runner-up, and the cheapest reversible first step. | Model-invocable and user-invocable. |
| [`issue-lifecycle/`](issue-lifecycle/) | Issue to fix with evidence at each stage — duplicate-checked issue drafts, read-only sizing, a marked failing-test checkpoint, an ours-or-dependency fix decision, a drafted reporter request, and an opt-in draft pull request. | User-invocable only (it drafts outward-facing text; it pushes and opens a draft pull request only in `publish`, after three confirmations, and never posts the reporter request). |
| [`ui-design/`](ui-design/) | Interface design and refinement to a craft floor — surface classification, ranked rule categories, adjustable variance / motion / density, a `DESIGN.md` project context, and a pre-delivery checklist. | Model-invocable and user-invocable. |
| [`paper-toolkit/`](paper-toolkit/) | Suite-free paper work: a reading note with its basis, a 2 to 5 paper comparison with comparability verdicts and a cite-for table, a related-work draft from supplied sources with visible citation-needed markers and a coverage report, an author-side critique, a reference style pass, and reference entries built from identifiers with every field copied from an opened record. | Model-invocable and user-invocable. |
| [`perspectives/`](perspectives/) | Contested-question panel: several separate viewpoints argue from evidence, then a reconciliation of agreement, real disagreements and what would settle each, a recommendation with its confidence, and the strongest dissent kept visible. | Model-invocable and user-invocable. |
| [`teaching-pack/`](teaching-pack/) | Teaching pack from one paper or technical document: learning goals, a section-by-section curriculum, plain-step formula and algorithm walk-throughs, worked examples, a quiz with answer key, a glossary and an optional slide outline. Each line is marked with its source section or as outside it, and parts the source cannot support are reported as thin. | Model-invocable and user-invocable. |
| [`surgical-guard/`](surgical-guard/) | Surgical-edit + reactive-guard — pairs a minimal-diff, anchor-bounded editing discipline with a post-edit diff-based quality guard (clean-code / test / docs checks with progressive rule loading); feeds the `surgical-manipulation` mandate. | Model-invocable and user-invocable. |

A skill is model-invocable when `disable-model-invocation` is `false`: the model may load it when a request matches its description. The default is `false` for read-only and advisory skills. A skill is user-invocable only (`true`) when running it changes state outside the working tree or depends on the operator choosing the moment. Of the 26 skills, 20 are model-invocable, 4 are user-invocable only (`dependency-upgrade`, `secret-rotation`, `workflow`, `issue-lifecycle`), and 2 are reference-only templates (`plan-suite`, `research-suite`). The session-start skill index lists the model-invocable and manual names by domain; see the Hooks reference page.

## What a skill is

A skill packages a technique with a **detection signal** — the frontmatter `description` enumerates the phrasings or contexts that match the skill — and a **procedure** — the body that runs once matched. The harness surfaces a matched skill to the agent; the agent invokes it.

## Progressive disclosure

Skills load on demand. Keep `description` precise enough that the harness can
match the skill from the user's request, touched paths, or task class without
pulling unrelated procedures into baseline context. When a skill applies only to
one subtree, name the subtree or file class in the detection signal and keep
supporting references beside `SKILL.md` so the procedure can load them
selectively.

## The skill convention

- **One folder per skill**, named in kebab-case, under `skills/`.
- **Entry point is always `SKILL.md`** with YAML frontmatter validated against [`../schemas/skill.schema.json`](../schemas/skill.schema.json). Required frontmatter fields (per `skill.schema.json`): `name`, `version`, `updated`, `description` (the detection signal), `archetype` (the skill's shape class, e.g. `audit-template`, `workflow-template`), `userInvocable`, `disable-model-invocation`, and `allowed-tools`; the optional `argument-hint` field may also appear.
- **Supporting files** live alongside `SKILL.md` in the same folder. The `plan-suite/` skill ships `master-template.md` — the canonical plan-suite template the `/plan` pipeline stages consume.
- Every file carries the canonical single-line SPDX license header.

## Folder contents

| Path | Role |
|------|------|
| `ecosystem-audit/SKILL.md` | The audit skill's concise entry-point router. |
| `ecosystem-audit/references/procedure.md` | The five-phase audit procedure, improvement-classification taxonomy, failure-recovery table, cadence guidance, and phase-thread diagram (progressively disclosed by the router). |
| `ecosystem-audit/references/audit-fortress.md` | The Audit-Fortress Phase Skeleton (canonical flowchart + per-command parameter table) the eleven audit-fortress commands cite. |
| `plan-suite/SKILL.md` | The plan-suite skill's entry point. |
| `plan-suite/master-template.md` | The canonical Master Plan Suite template resolved by `/plan-spec`, `/plan-generate`, `/plan-review`, `/plan-audit`, `/plan-design`, `/plan-execute`, `/plan-status`. |
| `research-suite/SKILL.md` | The research-suite skill's concise entry-point router. |
| `research-suite/research-template.md` | The canonical Research Suite template resolved by the `/research-<stage>` commands. |
| `research-suite/references/directory-structure.md` | The research-suite directory-structure map (progressively disclosed by the router). |
| `research-suite/references/rigor-mandates.md` | The ten rigor mandates (R1–R10) in full (progressively disclosed by the router). |
| `research-suite/references/lifecycle.md` | The thirteen-stage research lifecycle + per-stage invoking-surfaces table (progressively disclosed by the router). |
| `research-suite/references/principal-investigator-framework.md` | The Principal-Investigator (PI) lens and its six commitments (progressively disclosed by the router). |
| `research-suite/references/advancement-gate.md` | The gate a stage must clear before the lifecycle advances. |
| `research-suite/references/analysis-discipline.md` | Test selection by design, unit of analysis, missing data, reading a null, Bayesian plans and result-level bias appraisal. |
| `research-suite/references/autonomous-experiment-loop.md` | The unattended experiment loop and its stopping conditions. |
| `research-suite/references/blinding-and-disclosure.md` | Blinding protocol and the disclosure obligations that accompany it. |
| `research-suite/references/comparator-provenance.md` | How a comparator's origin and version are recorded so a result stays attributable. |
| `research-suite/references/compute-utilization.md` | Compute accounting for a run — what is measured and what is reported. |
| `research-suite/references/empirical-comparison-rigor.md` | The bar an empirical comparison clears before its claim may be stated. |
| `research-suite/references/experiment-program-scaffold.md` | The scaffold an experiment program is laid out against. |
| `research-suite/references/figure-integrity.md` | The honesty, disclosure and accessibility floor for research figures and experimental images. |
| `research-suite/references/plan-branching-and-contingencies.md` | The plan stress test, evidence labels on plan inputs and the contingency records that complete the `/research-proposal` risk register. |
| `research-suite/references/power-and-sample-size.md` | Recorded sizing inputs, effect-range sensitivity, sizing for the planned analysis, clustering, attrition, simulation power and sequential looks. |
| `research-suite/references/search-record.md` | The search record, study-level flow counts, integrity status and risk-of-bias record `/research-sources` keeps in the source ledger. |
| `research-suite/references/study-allocation-and-structure.md` | The experimental unit, allocation, masking, nuisance factors and run order, within-unit and multi-factor layouts, and control conditions. |
| `research-suite/references/talk-and-poster.md` | Talk intake, time budget, poster adaptation, the figure rule and the compiled-artifact check for `/research-disseminate` and `/research-publish`. |
| `research-suite/references/venue-profiles.md` | Generic venue profiles, the axis-to-verdict rule and the recommendation-scale mappings that `/research-review --paper` applies. |
| `research-suite/references/external-paper-checks.md` | Paper types, reviewer roles and the equation, ablation, baseline and consistency checks for a paper outside any suite. |
| `test-authoring/SKILL.md` | The test-authoring skill's entry point and procedure. |
| `refactor-extract/SKILL.md` | The refactor-extract skill's entry point and procedure. |
| `dependency-upgrade/SKILL.md` | The dependency-upgrade skill's entry point and procedure. |
| `incident-runbook/SKILL.md` | The incident-runbook skill's entry point and procedure. |
| `secret-rotation/SKILL.md` | The secret-rotation skill's entry point and procedure. |
| `vuln-triage/SKILL.md` | The vuln-triage skill's entry point and procedure. |
| `multi-source-research/SKILL.md` | The multi-source-research skill's entry point and procedure. |
| `source-synthesis/SKILL.md` | The source-synthesis skill's entry point and procedure. |
| `prompt-engineering/SKILL.md` | The prompt-engineering skill's entry point and procedure. |
| `eval-harness/SKILL.md` | The eval-harness skill's entry point and procedure. |
| `workflow/SKILL.md` | The workflow-harnessing skill's entry point and procedure. |
| `projectify/SKILL.md` | The projectify skill's entry point and procedure. |
| `diagram-authoring/SKILL.md` | The diagram-authoring skill's entry point and procedure. |
| `document-authoring/SKILL.md` | The document-authoring skill's entry point and procedure. |
| `dev-toolkit/SKILL.md` | The dev-toolkit skill's entry point and procedure. |
| `surgical-guard/SKILL.md` | The surgical-guard skill's entry point and procedure. |
| `knowledge-wiki/SKILL.md` | The knowledge-wiki skill's entry point and procedure. |
| `knowledge-wiki/references/page-templates.md` | Page templates for sources, entities, syntheses, the index and the log. |
| `knowledge-wiki/references/lint-catalog.md` | The deterministic lint checks and how each is detected. |
| `knowledge-wiki/references/drift-and-hubs.md` | The drift fingerprint and the hub and bridge analysis. |
| `decision-matrix/SKILL.md` | The decision-matrix skill's entry point and procedure. |
| `decision-matrix/references/scoring-and-sensitivity.md` | Scoring rules, totals and the weight-sensitivity check. |
| `issue-lifecycle/SKILL.md` | The issue-lifecycle skill's entry point and procedure. |
| `issue-lifecycle/references/stage-details.md` | Per-stage detail for create, size, reproduce, fix and publish, plus the reporter request. |
| `paper-toolkit/SKILL.md` | The paper-toolkit skill's entry point and procedure. |
| `paper-toolkit/references/reading-note.md` | The one-paper reading note: claim, method, evidence, limits and what the paper is citable for. |
| `paper-toolkit/references/paper-comparison.md` | The 2 to 5 paper comparison: comparability axes, verdicts and the cite-for table. |
| `paper-toolkit/references/related-section.md` | The related-work draft from supplied sources, with citation-needed markers and a coverage report. |
| `paper-toolkit/references/critique-template.md` | The author-side critique: strengths, reviewer questions, ranked changes and what was not judged. |
| `paper-toolkit/references/reference-style-pass.md` | The reference style pass: duplicates, missing fields, inconsistent form, key collisions, truncated author lists and BibTeX well-formedness. |
| `paper-toolkit/references/bibliography-entries.md` | The `entries` guide: reference entries from identifiers with fields taken from an opened record, the entry type chosen from the record, blank-field states and the normalised entry form. |
| `perspectives/SKILL.md` | The perspectives skill's entry point and procedure. |
| `perspectives/references/viewpoint-roster.md` | Viewpoint roster, brief, return template and reconciliation worksheet. |
| `teaching-pack/SKILL.md` | The teaching-pack skill's entry point and procedure. |
| `teaching-pack/references/pack-templates.md` | The source-marker legend and the shape of each pack part. |
| `teaching-pack/references/source-requirements.md` | What each part needs from the source, what each reading basis allows and the signs of padding. |
| `teaching-pack/references/slide-outline.md` | The optional slide-outline shape and the hand-off to a host slide or document skill. |
| `teaching-pack/references/pre-delivery-checks.md` | The checks run before a pack is delivered. |
| `ui-design/SKILL.md` | The ui-design skill's entry point and procedure. |
| `ui-design/references/surface-classes.md` | The four surface classes and the priorities each sets. |
| `ui-design/references/rule-catalog.md` | The ranked rule categories with the conflict-priority table. |
| `ui-design/references/design-md-template.md` | The `DESIGN.md` project design-context template. |
| `ui-design/references/pre-delivery-checklist.md` | The checklist run before a UI is called done. |

## Operating in this folder

- **One folder per skill; the entry point is always `SKILL.md`,** never a differently-named file. The `description` frontmatter field is the match surface: make it precise enough that the harness selects the skill from the request, touched paths, or task class without pulling unrelated procedures into context. Keep it to 1,024 characters or fewer (the [Agent Skills](https://agentskills.io/specification) limit, enforced by `skill.schema.json`).
- **Keep supporting files self-loading and beside the entry point;** do not scatter a skill's references across the tree, so they load selectively with the procedure rather than into baseline context.
- **Adding a skill:** create a new kebab-case subfolder, author its `SKILL.md` with valid frontmatter and an SPDX header, place supporting files beside it, then register the skill in the index and Folder-contents tables above and in any consuming command — in the same change-set. **Removing or renaming a skill** updates the same tables and every consumer in the same change-set.
- Validate a change with `python -m apothem.conformity.gate --all .`, `python -m pytest`, and `python -m ruff check`.

## Cross-references

- The `/plan` pipeline stages that consume `plan-suite/` are under [`../commands/`](../commands/).
- Convention and gap-detection discipline for skills is specified in `../rules/persistent-conventions-vigilance.md`.
