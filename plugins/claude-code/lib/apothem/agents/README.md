<!-- SPDX-License-Identifier: MIT -->

# Agents

Persistent agent definitions — the reusable sub-agent specifications the harness materializes whenever the orchestrator deploys a research, audit, or quality team. Each agent is a flat `<name>.md` entry point: a Markdown file whose YAML frontmatter declares the agent's capabilities and whose body is the agent's system prompt.

## Index

| Agent | Purpose | Tool posture |
|-------|---------|--------------|
| [`codebase-explorer.md`](codebase-explorer.md) | Deep codebase exploration — find patterns, trace dependencies, discover conventions, map architecture | Read-only (`Read, Glob, Grep, Bash`; `Write/Edit` disallowed) |
| [`convention-auditor.md`](convention-auditor.md) | Audits artifacts against ecosystem conventions — naming, structure, cross-references, registry coherence | Read-oriented audit |
| [`memory-auditor.md`](memory-auditor.md) | Audits the auto-memory tree — staleness, contradictions, orphan topic files, MEMORY.md index integrity | Read-oriented audit |
| [`quality-gate.md`](quality-gate.md) | Runs lint, test, type-check, and security scans with structured pass/fail output | `Bash, Read, Glob, Grep` |
| [`test-runner.md`](test-runner.md) | Runs the host's test suite and triages every failure by root cause — discovers the test command, never assumes pytest | Read-only (`Read, Glob, Grep, Bash`; `Write/Edit` disallowed) |
| [`refactor-surgeon.md`](refactor-surgeon.md) | Scoped, behavior-preserving refactors — extract the contract, re-derive clean-room, name the deficiency, verify via host tests | `Read, Write, Edit, Glob, Grep, Bash` |
| [`dependency-auditor.md`](dependency-auditor.md) | Dependency-tree risk audit — flags unpinned, stale, duplicate, and known-vulnerable dependencies across npm, pip, cargo, go | Read-only (`Read, Glob, Grep, Bash`; `Write/Edit` disallowed) |
| [`security-scanner.md`](security-scanner.md) | Read-only secret, SAST-pattern, and config-risk sweep — coarse first-pass that routes deep scanning to the host's CI scanners | Read-only (`Read, Glob, Grep, Bash`; `Write/Edit` disallowed) |
| [`research-scout.md`](research-scout.md) | Source discovery and ranking — decomposes a question, runs parallel web queries, ranks sources by authority, recency, relevance | Read-only web (`Read, Glob, Grep, WebSearch, WebFetch`; `Write/Edit` disallowed) |
| [`fact-checker.md`](fact-checker.md) | Adversarial claim verification — extracts discrete claims, seeks independent sources, attempts refutation, assigns cited verdicts | Read-only web (`Read, Glob, Grep, WebSearch, WebFetch`; `Write/Edit` disallowed) |
| [`prompt-evaluator.md`](prompt-evaluator.md) | Scores prompt and model outputs against an explicit rubric — per-criterion pass-rate, failure examples, regression flags | Read-only (`Read, Glob, Grep, Bash`; `Write/Edit` disallowed) |
| [`mcp-builder.md`](mcp-builder.md) | Scaffolds Model Context Protocol (MCP) server skeletons from a tool/resource spec — contract-first, well-typed tools, minimal surface | `Read, Write, Edit, Glob, Grep, Bash` |

## What an agent definition is

An agent definition packages a focused mission into a re-deployable unit. The orchestrator dispatches one or more agents — in parallel where the work is independent — and each agent returns a bounded, structured result against its declared return contract. The twelve agents here are the persistent flat definitions the agent-orchestration rule's team patterns dispatch to.

## Frontmatter contract

Agent frontmatter is validated against [`../schemas/agent.schema.json`](../schemas/agent.schema.json). Observed fields:

- `name` — agent identifier (kebab-case). The schema does not require it to match the filename; the stem-equals-`name` rule is an Apothem folder convention layered on top (see Conventions).
- `version` / `updated` — semantic version and ISO-8601 revision date.
- `description` — one-line statement of the agent's mission.
- `tools` — comma-separated allowed tool list.
- `disallowedTools` — comma-separated explicit denials.
- `maxTurns` — turn ceiling (with an inline rationale comment when it exceeds the 5–10 norm).
- `portability` — harness-portability classification (e.g. `universal`).

No shipped agent sets `memory`. Claude Code defines it as a persistent-memory scope (`user`, `project`, or `local`), and leaving it out means no persistent memory, so an agent sets it only when it needs that scope. `version`, `updated`, and `portability` are Apothem metadata the schema admits; harnesses ignore them.

The body after the frontmatter is the agent's system prompt: mission, operating principles, and return-format specification.

## Harness adapters

These definitions are harness-agnostic. Per-harness adapters materialize each `<name>.md` into the host harness's native sub-agent format at install time; the cross-harness compatibility surface is declared in [`../schemas/compatibility-matrix.yaml`](../schemas/compatibility-matrix.yaml).

## Conventions

- One flat `.md` file per agent; filename stem equals the `name` field.
- Every file carries the canonical single-line SPDX license header.
- Deployment patterns and return-contract discipline are specified in `../rules/agent-orchestration.md` and its companion `../rules/agent-orchestration-patterns.md`.

## Operating in this folder

- The file shape is the canon: YAML frontmatter block → the single-line SPDX license header (HTML-comment form) → the prompt body.
- Tool boundaries never widen past the universal-deny floor; a read-only agent's `disallowedTools` keeps `Write`/`Edit` denied.
- `maxTurns` above the 5–10 norm carries an inline rationale comment.
- Definitions stay harness-agnostic — name a harness only by its catalog slug, never by a privileging brand phrase, and pre-set no model, effort, or permission preference (the agnostic posture).
- **A new or removed agent updates this README's agent index in the same change-set.** The cross-harness [`../schemas/compatibility-matrix.yaml`](../schemas/compatibility-matrix.yaml) tracks the agents cohort (compatible harnesses + materialization strategy), not individual agents by name, so it changes only when cohort-level harness compatibility changes. To modify an agent, keep the frontmatter schema-valid and the return contract intact.
- Validate a change with `python -m ruff check`, the conformity gate `python -m apothem.conformity.gate --all .` (frontmatter/header coverage), and `python -m pytest` (agent-definition and matrix tests).

## Bindings (§0.j five-direction)

- **Drives →** The agent index above and every definition it lists: `agents/codebase-explorer.md` · `agents/convention-auditor.md` · `agents/memory-auditor.md` · `agents/quality-gate.md` · `agents/test-runner.md` · `agents/refactor-surgeon.md` · `agents/dependency-auditor.md` · `agents/security-scanner.md` · `agents/research-scout.md` · `agents/fact-checker.md` · `agents/prompt-evaluator.md` · `agents/mcp-builder.md`. The per-harness materialization of each definition at install time.
- **Satisfies →** The agent-guidance locality canon in `AGENTS.md` (each folder's operating contract lives in its README). The same-change-set rule above: a new or removed agent updates this index.
- **Established by ↑** `AGENTS.md` (the root agent-instruction canon). `rules/agents-md-convention.md` (the per-folder README contract). `rules/agent-orchestration.md` (the team patterns that dispatch these agents).
- **Gated by ←** `scripts/dev/check_readme_file_coverage.py --strict` (every shipped file in this folder is named here). `schemas/agent.schema.json` (the frontmatter contract each definition validates against). The propagation manifest's `README.md` exclusion (this file never ships into a harness discovery directory).
- **Cross-bound with ↔** `rules/README.md` + `commands/README.md` (the sibling contracts for the other convention directories).
