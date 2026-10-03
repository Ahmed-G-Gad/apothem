---
name: "test-authoring"
version: "0.1.0"
updated: "2026-10-02"
description: "Behavior-first test authoring with strict Arrange-Act-Assert discipline — matched when the developer asks to 'write tests', 'add coverage', 'add a test for', 'test this function', 'cover this module', 'write a failing test', 'increase coverage', or otherwise requests new test cases that assert observable behavior of a unit under test. Discovers the unit's behavior contract (input domains, return shapes, side effects, raised exceptions, edge boundaries such as empty/null/zero/max/Unicode/off-by-one), writes failing AAA assertions first, covers the happy path, edge boundaries, and failure modes (pinning any named bug with a regression test), and reports remaining coverage gaps. Authors tests only — never edits the implementation, runs the suite, computes coverage, edits coverage config, or mocks the unit under test (mocks only at owned boundaries). Fixing a failing test by editing the implementation, scaffolding a project, or running an existing suite is NOT a match."
archetype: "authoring-template"
userInvocable: true
argument-hint: "[--focus PATH] [--framework NAME]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Author behavior-first test cases for a named unit under test. Every emitted test asserts one observable behavior contract — an input-to-output mapping, a side effect, a raised exception, or an edge boundary — under a strict Arrange-Act-Assert shape. The skill writes the tests; it never touches the implementation those tests exercise.

## Detection Signal

The developer asks to "write tests", "add coverage", "add a test for", "test this function", "cover this module", "write a failing test", or "increase coverage" — any phrasing that requests new test cases asserting observable behavior against a unit under test.

**Falsifiable counter-signal.** A request to fix a failing test by editing the implementation, scaffold a project, or run an existing suite is NOT a match — those route to the implementation, project-setup, and test-execution surfaces respectively.

## Non-Goals

A deliberately narrow surface. The skill is NOT:

- **An implementation generator.** It authors tests against the unit's behavior contract; it never writes, edits, or repairs the production code the tests exercise. Implementation lands through the host's normal codegen surface, governed by `rules/host-discovery.md`.
- **A green-bar chaser.** A test that passes before the implementation exists asserts nothing. The skill writes assertions that fail against the absent or current behavior first; the contract is satisfied by implementation outside this skill.
- **A test runner.** It authors test files; it does not execute the suite, compute a coverage percentage, or gate on a threshold. Execution is the host's `pytest` / `vitest` / `go test` surface and the consuming command's responsibility.
- **A mock-everything tool.** Tests assert behavior, not implementation detail. The skill mocks only at owned boundaries (adapters, injected ports) and never mocks the unit under test itself.
- **A coverage-config editor.** Threshold configuration, CI wiring, and coverage-tool selection are operator decisions surfaced as findings, never silently installed.

## Workflow

Five numbered, independently-verifiable steps. Test authoring only — no implementation edits.

1. **Resolve the unit and the framework.** Discover the host's ratified test framework, test-directory layout, fixture conventions, and naming idioms by walking the host's source-of-truth files per `rules/host-discovery.md` (e.g., `pyproject.toml [tool.pytest.ini_options]`, sibling `test_*.py`, `*.test.ts`, `*_test.go`). `--focus PATH` names the unit; `--framework NAME` overrides the discovered framework when the host runs more than one.
2. **Extract the behavior contract.** Read the unit under test and enumerate its observable contract — every input domain, every return shape, every side effect, every raised exception type, every edge boundary (empty, null, zero, max, Unicode, boundary off-by-one). Record each contract item as a distinct row; one row becomes one test.
3. **Write failing AAA assertions first.** For each contract row, author one test in strict Arrange-Act-Assert form: the **Arrange** block builds the fixture and inputs, the **Act** block invokes the unit once, the **Assert** block checks exactly one observable outcome. The assertion fails against absent or current behavior before the implementation satisfies it. One behavioral claim per test; behavior-descriptive names (`test_<unit>_<condition>_<expected>`).
4. **Cover happy, edge, and failure paths.** Partition the contract into the **happy path** (valid in-domain inputs), the **edge boundaries** (empty, null, zero, max, Unicode), and the **failure modes** (invalid inputs, missing dependencies, raised exceptions asserted with the framework's exception-matcher). Every partition carries at least one covering test; a bug-fix request adds a regression test pinning the prior defect.
5. **Report residual coverage gaps.** Name every contract row left uncovered and why (data not yet discoverable, behavior under-specified, boundary requires host input). Uncovered rows surface as findings for operator triage, never silently dropped.

## Return Contract

Output is the set of authored test files plus a coverage-map summary (markdown). Maximum response: 800 tokens. Structure:

- **Tests authored:** bulleted list — file path, test name, contract row, partition (happy / edge / failure).
- **Coverage map:** contract rows covered vs. residual, with each residual row's triage reason.
- **Gaps:** behavior contracts the host has not yet specified (if applicable).

**Token-budget override.** The invoker may request a higher budget for exhaustive enumeration; honor it. Prefer raising the budget over truncating the coverage map.

## Foundational Stanzas

The four standing surfaces, adapted to this skill's user-invocable test-authoring role.

### Refusal & Escalation

REFUSE any request that asks the skill to act outside its mission — editing the implementation under test, scaffolding a project, running the suite, computing coverage percentages, or mutating coverage configuration. Refusal is explicit: name what was refused, name the mission boundary crossed, and route the developer to the correct surface through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). When the unit under test cannot be located or its behavior contract is unreadable, STOP and surface the recovery options — never invent a contract from training-time memory.

### Output Surface

The skill emits test files at the host's ratified test location, discovered per `rules/host-discovery.md` (mirror-the-source layout where the host uses one; sibling-of-source where it does not). NEVER write a test outside the host's test tree, NEVER write to a global location, and NEVER edit the implementation under test. Per `rules/operational-mandates.md` CM-7, authored tests carry zero plan-internal references — natural domain language only.

### File-Authoring Contract

Every NEW test file routes through `scripts/inject-header.py` so the canonical `SPDX-License-Identifier: MIT` header is injected at the head in the comment family matching the filetype; the injector is idempotent and resolves the variant from the byte-exact fixture at `src/apothem/schemas/authorship-header.txt`. Exempt classes are enumerated at `src/apothem/schemas/header-exceptions.txt`. The header-inject-guard hook at `hooks/messages/pretooluse-{write,edit}-header-guard.md` enforces the contract at every Write / Edit invocation.

### Structured Inquiry on Ambiguity

When the skill reaches a decision in any of the seven authoritative-data categories per `rules/authority-inquiry.md` — identity, scope direction (which unit, which subtree), preference (test framework, fixture style, mocking library, coverage tool), security (test-fixture credentials), naming of public surfaces (test-file naming), infrastructure endpoints (integration-test targets), version pins — and the host is silent, route the resolution through the structured-inquiry channel with the three-segment annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). NEVER fabricate authoritative data. Every overwrite of an existing test file routes through the per-file destructive-op floor per `rules/interactive-questions.md` §6 — one invocation per file, no `multiSelect` batching, every option's `default-pointer:` carrying the verbatim `no-default: user decision required` marker.

## Recommended Next Step

**Run the host's test command against the authored files** (e.g., `python -m pytest <focus-path>`) to confirm every new assertion fails before the implementation lands, then hand the failing suite to the implementation surface.

## Bindings (§0.j five-direction)

- **Drives →** ● Every behavior-first test file authored at the host's ratified test location. ● The AAA-shaped assertion discipline at every emitted test. ● The coverage-map summary that surfaces residual gaps for operator triage.
- **Satisfies →** ● `CLAUDE.md` Source Layout row "test-authoring" (skills/ class). ● The behavior-first test-authoring mission with strict Arrange-Act-Assert discipline.
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ folder-with-`SKILL.md` class). ● `rules/code-craft-python.md` §3 Testing Directives (AAA shape, behavior-descriptive names, one assertion per test). ● `rules/ten-dimension-check-dimensions.md` dimension 10 (examples / tests / docstrings).
- **Gated by ←** ● The harness's Write / Edit / Read / Glob / Grep / Bash tool surface. ● The presence of a locatable unit under test and a discoverable test framework per `rules/host-discovery.md`.
- **Cross-bound with ↔** ↔ `rules/code-craft-python.md` (test-craft discipline for Python units). ↔ `rules/host-discovery.md` (framework and layout discovery). ↔ `rules/interactive-questions.md` (structured-inquiry channel for ambiguity and destructive-op floor). ↔ `rules/clean-room-generation.md` §4.2 (test-behavioral derivation). ↔ `skills/ecosystem-audit/SKILL.md` + `skills/plan-suite/SKILL.md` (sibling skills under the same registry section).
