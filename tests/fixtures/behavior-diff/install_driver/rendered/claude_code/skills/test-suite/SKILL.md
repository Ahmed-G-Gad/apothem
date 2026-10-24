---
name: "test-suite"
description: "Behavior-first test authoring and execution workflow for a deployed repository. Discovers the host's ratified test framework, coverage tooling, and behavior contracts via host-discovery, authors behavior-shaped AAA tests through the test-authoring skill, runs them through the test-runner agent, triages failures into actionable findings, and reports coverage gaps against critical paths. Tests are named for the behavior they assert, follow the Arrange / Act / Assert shape, and never depend on test ordering. Output lands at the consuming suite's _inputs/test-suite-report.md with per-test outcomes, failure triage, and coverage-gap findings carrying concrete-driver rationale."
argument-hint: "[path/to/repo/] [--focus FILE_OR_DIR]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /test-suite — Behavior-First Test Workflow

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Senior Software Engineer** and **Cognitive Insurgent** (see `rules/cognitive-identity.md`), authoring tests on the premise that **every behavior contract deserves an executable proof**. Tests assert observable behavior, never implementation detail; a test that breaks on a behavior-preserving refactor is itself a defect.

Apply the Five Cognitive Filters during test design: Filter 1 (Obvious Purge) discards the first happy-path-only test in favor of boundary, empty, and failure-mode coverage; Filter 5 (Aesthetic Demand) governs the test's name and AAA shape. The seven-axes-of-breadth taxonomy at `rules/cognitive-identity.md` §1 frames the axes each behavior contract touches; the **Testing axis is load-bearing throughout**.

---

## Instructions

Discover the deployed repository's behavior contracts and its ratified test framework, author behavior-first AAA tests through the `test-authoring` skill, run them through the `test-runner` agent, triage every failure, and report coverage gaps against critical paths. Emit the report at the consuming suite's `_inputs/test-suite-report.md`.

**Reference Template:** Check `CLAUDE.md` for template path. Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) active throughout. The workflow honors the host's discovered test framework, coverage tooling, and naming conventions per `rules/host-discovery.md`; it never assumes a framework the host has not adopted.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, after any context compaction, and before the final step or any handoff. Covers: Pipeline position; Consumed; Emitted; Pre-flight inquiry set; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step and after any context compaction; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | Root directory of the deployed repository. MUST carry a source tree and a discoverable root manifest. The command refuses execution when no source tree is present. |
| `--focus FILE_OR_DIR` | Path | No | Restrict test authoring to the behavior contracts of a single file or directory subtree under the repo root. Path resolves relative to the repo root. |

---

## Workflow

1. **Discover behavior contracts and the test framework.** Walk the host's root manifest and existing test corpus per `rules/host-discovery.md` to resolve the ratified test framework, the coverage tool, the test-location convention, and the naming convention. Enumerate the behavior contracts under test — public-API surfaces, error-handling branches, documented invariants, pre / post / failure conditions. When the framework is ambiguous, route through the pre-flight inquiry set. Apply `rules/code-craft-python.md` for Python repositories (pytest discipline) and the host-discovered convention for other languages.
2. **Author behavior-first AAA tests.** Drive the `test-authoring` skill to author one test per behavior contract. Each test is named for the behavior it asserts (`test_<unit>_<behavior>_<condition>`), follows the Arrange / Act / Assert shape with blank-line separation, covers the happy path plus boundary / empty / None / failure modes, and depends on no test ordering. Every authored test is deterministic, no-network, no-filesystem-side-effect, non-flaky, and order-independent — a test that reaches the network, mutates on-disk state outside a per-test temporary fixture, or passes only under a particular collection order is itself a defect. The coverage, behavior-named, and parametrized facets are owned by `rules/sota-elevation-exemplars.md` §5 and are not restated here. Inject the SPDX header into every new test file per the File-Authoring Contract.
3. **Run the tests through the test-runner agent.** Dispatch the `test-runner` agent to execute the authored tests through the host's ratified runner. The agent returns a structured outcome — per-test pass/fail, runner exit code, coverage-report path — under a 200-token return contract per `rules/agent-orchestration.md` §4.
4. **Triage failures.** Classify each failing test as a **test defect** (the assertion misreads the contract — fix the test, re-run) or a **source defect** (the contract is violated — record a finding for downstream remediation). Source-defect findings cite the `file:line` and the violated contract; they never trigger source edits from this command.
5. **Report coverage gaps.** Parse the coverage report. Identify uncovered critical paths (every public-API surface, every error-handling branch, every security-relevant code path). Emit per-gap findings with severity `{HIGH, MEDIUM, LOW}` and concrete-driver rationale per `rules/interactive-questions-canonical-shapes.md` §3.2.1. Author the report; run the pre-emission gate.

---

## Mandates

| Mandate | Obligation |
| ------- | ---------- |
| Host-Agnostic Discovery (M1) | Discover the test framework, coverage tool, and test-location convention; never assume pytest or any single framework. |
| Behavior-First (M8) | Tests assert observable behavior with pre / post / failure conditions; implementation-coupled tests are findings. |
| Structured Inquiry (CM-2) | Framework ambiguity and contract ambiguity route through the canonical channel; free-form prose as primary input is forbidden. |
| File Headers | Every authored test file carries the canonical SPDX header via `scripts/inject-header.py`. |
| Pre-Emission Gate (M4) | The report and authored test files pass the fifteen-bar gate before promotion. |
| Worker Orchestration (CM-25) | The test-runner agent carries an explicit 200-token return contract. |

---

## Output

- The report at the consuming suite's `_inputs/test-suite-report.md` (per-test outcomes + failure triage + coverage-gap findings + validation-gate attestation).
- The authored behavior-first test files at the host's ratified test location, each carrying the canonical SPDX header.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Recommended Next Step

**Invoke `/code-review`** to walk the per-file craft of the source under test, then `/code-audit` for cross-file forensic integrity; both consume the coverage-gap findings this command emits at `_inputs/test-suite-report.md`.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
