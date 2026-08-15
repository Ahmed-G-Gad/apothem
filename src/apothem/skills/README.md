<!-- SPDX-License-Identifier: MIT -->

# Skills

Skill definitions — reusable, detectable techniques the harness loads on demand. Each skill is **one folder** whose canonical entry point is `SKILL.md`: a Markdown file with YAML frontmatter declaring the skill's identity and trigger surface, and a body specifying the procedure.

## Index

| Skill | Purpose | Invocability |
|-------|---------|--------------|
| [`ecosystem-audit/`](ecosystem-audit/) | Blind audit of the apothem ecosystem — detects drift, staleness, orphans, dangling references, conflicting directives, frontmatter invalidity, registry-vs-disk count mismatches, secret exposure. Optionally applies FIX-class fixes under `--fix`. | User-invocable; also dispatchable from `/plan-execute` discovery context. |
| [`plan-suite/`](plan-suite/) | Master Plan Suite template — houses the canonical template defining plan-suite structure, mandates, core principles, and the Technical Co-Founder Framework. | Not directly user-invocable; the `/plan` pipeline stages resolve the template by path. |
| [`research-suite/`](research-suite/) | Research Suite knowledge surface — houses the canonical research-suite template defining the suite directory structure, the ten rigor mandates (R1–R10), the thirteen-stage research lifecycle, and the Principal-Investigator Framework. | Not directly user-invocable; the `/research` pipeline stages resolve the template by path. |
| [`test-authoring/`](test-authoring/) | Behavior-first test authoring with strict Arrange-Act-Assert discipline — discovers a unit's behavior contracts, writes failing AAA assertions covering happy path, edge boundaries, and failure modes, and reports residual coverage gaps. Authors tests only. | User-invocable. |
| [`refactor-extract/`](refactor-extract/) | Scoped behavior-preserving extraction refactor — extracts what the code does, clean-room re-derives from the extracted specification, elevates quality against a named deficiency, and verifies behavior is preserved. | User-invocable. |
| [`dependency-upgrade/`](dependency-upgrade/) | Changelog-reviewed, pinned, gate-verified dependency upgrade — enumerates outdated dependencies, reviews each changelog for breaking changes, applies host-policy pinned bumps, and runs the host's lint / test / type-check gates. | User-invocable. |
| [`incident-runbook/`](incident-runbook/) | Operational incident runbook authoring and execution — produces a Trigger → Diagnosis → Action → Verification → Rollback procedure where every action carries an explicit, tested rollback path. | User-invocable. |
| [`secret-rotation/`](secret-rotation/) | Safe secret-rotation template — detects the exposure surface, revokes the compromised credential at its issuer, re-issues a replacement, rewires config through env-var or secret-manager indirection, and verifies no plaintext residue remains. | User-invocable. |
| [`vuln-triage/`](vuln-triage/) | Vulnerability and security-advisory triage — severity-classifies an advisory, maps it to the affected surface, determines exploitability and reachability, routes remediation, and records the disposition with rationale. | User-invocable. |
| [`multi-source-research/`](multi-source-research/) | Multi-source research harness — decomposes the question, fans out parallel source-discovery queries, fetches and extracts per source, adversarially verifies each claim against two or more independent sources, and synthesizes a cited report. | User-invocable. |
| [`source-synthesis/`](source-synthesis/) | Reconcile a fixed set of provided sources into one cited synthesis — extracts the claim set per source, reconciles agreements and contradictions, and separates consensus from contested ground while flagging coverage gaps. | User-invocable. |
| [`prompt-engineering/`](prompt-engineering/) | Design and eval-validate structured prompts — clarifies the task contract, drafts a structured prompt with explicit role / instructions / output schema, defines happy / edge / adversarial eval cases, and iterates against them. | User-invocable. |
| [`eval-harness/`](eval-harness/) | Build and run reproducible LLM evaluation harnesses — defines a labeled dataset, a scorer with an explicit pass criterion, a candidate runner, and an aggregated metrics report with per-category breakdowns, confidence, and regression detection. | User-invocable. |
| [`workflow/`](workflow/) | Workflow-harnessing orchestration — decomposes a mission, dispatches genuinely-independent multi-agent dynamic workflows under named return contracts, runs a refute-by-default verification pass before any finding survives, and self-augments from current authoritative sources. Multi-agent dispatch is opt-in / confirmation-gated. | User-invocable (entry form `/goal <<mission>>`). |
| [`projectify/`](projectify/) | Chat-app Project elevation — produces the three deliverables (Description, Instruction, knowledge Files) for a Claude Project / ChatGPT Custom GPT / Gemini Gem through a structured-inquiry-saturated elicitation, holding knowledge files within a measurable per-platform context budget. | User-invocable. |
| [`diagram-authoring/`](diagram-authoring/) | Diagram authoring and rendering — one author → validate → render → export pipeline covering declarative diagrams (flowchart / sequence / state / class / ER / gantt) and data-driven visualizations, exporting to SVG / PNG / PDF via a headless renderer. | User-invocable. |
| [`document-authoring/`](document-authoring/) | Long-form structured-document authoring — an approval-gated outline → draft → review pipeline with verified citations (every reference resolves to a real source) and a deterministic compile pipeline routing engine / bibliography / index passes by detected source features. | User-invocable. |
| [`dev-toolkit/`](dev-toolkit/) | Engineering-discipline toolkit — sequences the core loops (structured debugging, test-first red-green-refactor, vertical-slice decomposition, requirement-to-issue breakdown) into one composable, gated procedure; cross-references sibling capabilities (does not duplicate them). | User-invocable. |
| [`surgical-guard/`](surgical-guard/) | Surgical-edit + reactive-guard — pairs a minimal-diff, anchor-bounded editing discipline with a post-edit diff-based quality guard (clean-code / test / docs checks with progressive rule loading); feeds the `surgical-manipulation` mandate. | User-invocable. |

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
| `research-suite/references/autonomous-experiment-loop.md` | The unattended experiment loop and its stopping conditions. |
| `research-suite/references/blinding-and-disclosure.md` | Blinding protocol and the disclosure obligations that accompany it. |
| `research-suite/references/comparator-provenance.md` | How a comparator's origin and version are recorded so a result stays attributable. |
| `research-suite/references/compute-utilization.md` | Compute accounting for a run — what is measured and what is reported. |
| `research-suite/references/empirical-comparison-rigor.md` | The bar an empirical comparison clears before its claim may be stated. |
| `research-suite/references/experiment-program-scaffold.md` | The scaffold an experiment program is laid out against. |
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

## Operating in this folder

- **One folder per skill; the entry point is always `SKILL.md`,** never a differently-named file. The `description` frontmatter field is the match surface: make it precise enough that the harness selects the skill from the request, touched paths, or task class without pulling unrelated procedures into context.
- **Keep supporting files self-loading and beside the entry point;** do not scatter a skill's references across the tree, so they load selectively with the procedure rather than into baseline context.
- **Adding a skill:** create a new kebab-case subfolder, author its `SKILL.md` with valid frontmatter and an SPDX header, place supporting files beside it, then register the skill in the index and Folder-contents tables above and in any consuming command — in the same change-set. **Removing or renaming a skill** updates the same tables and every consumer in the same change-set.
- Validate a change with `python -m apothem.conformity.gate --all .`, `python -m pytest`, and `python -m ruff check`.

## Cross-references

- The `/plan` pipeline stages that consume `plan-suite/` are under [`../commands/`](../commands/).
- Convention and gap-detection discipline for skills is specified in `../rules/persistent-conventions-vigilance.md`.
