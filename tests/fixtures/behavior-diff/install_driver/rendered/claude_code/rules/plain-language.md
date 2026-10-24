---
name: "plain-language"
description: "User-facing apothem narrative reads as human-authored with zero process-tooling leak — a closed-set forbidden vocabulary (AI / agent / LLM / attestation / ratified / cutover-rehearsal / harness brand identifiers / plan-stage tokens) is eliminated from in-scope codebase-artifact surfaces; the product noun harness is a domain carve-out; dev-facing tech-spec, rule-tier, and per-harness materializer modules are out-of-scope process artifacts that retain their native vocabulary."
pathFilter: "**/README*.md, **/CHANGELOG*.md, **/site/**, **/docs/**"
alwaysApply: false
paths:
  - "**/README*.md"
  - "**/CHANGELOG*.md"
  - "**/site/**"
  - "**/docs/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Plain-language — User-Facing Narrative Free of Process-Tooling Leak

## Obligations

User-facing surfaces MUST read as human-authored product copy. Process-tooling vocabulary belongs in rules, commands, plans, matchers, adapters, and developer-only surfaces — not README / docs / site copy. Human-authored copy flows as prose by default; a list earns its place only where the content is genuinely enumerable, per the prose-over-lists floor at `rules/code-craft-markdown.md` §2.1 — a bulleted stub where a sentence carries the meaning reads as machine-fragmented, not human-authored.

### 1. Forbidden Vocabulary (closed set)

Eliminate from in-scope surfaces — the set is exactly what `conformity/plain_language_grep.py` enforces, word-boundary case-insensitive:

- **Mechanistic generics:** `AI`, `agent` (+ `agents`), `LLM` (+ `LLMs`), `attestation` (+ `attestations`).
- **Process-tooling markers:** `ratified`, `cutover-rehearsal`.
- **Harness brand identifiers:** `claude_code` / `claude-code`, `cursor`, `gemini`, `copilot`, `windsurf`, `codex`, `hermes`, `kimi_code` / `kimi-code`, `glm`.
- **Plan-stage patterns:** numbered stage labels (`phase <N>`), stream labels (`stream <A-Z>`), zero-padded nested-stage tokens (`<NN><A-Z>`).

### 2. Domain Carve-Outs

Allowed: `Apothem`, `apothem`, `polygon`, `regular polygon`, `apothem distance`. The product noun `harness` / `harnesses` is allowed — apothem's central product domain, not a leak. The generic `agent` / `agents` clears ONLY as a directory or cohort-directory reference (`agents/`, or `agents` enumerated beside sibling cohort directories), never as a mechanistic prose noun.

### 3. Boundary — In-Scope vs Out-of-Scope

- **In-scope:** README files, docs / site copy, workflow names and step names, asset alt / ARIA text, commit messages, PR / issue templates, CHANGELOG entries, Pages copy.
- **Out-of-scope:** `.apothem/plans/**`, `.plans/**`, rules, commands, matchers, adapter modules, materializers, and developer-only technical surfaces whose process vocabulary is load-bearing.

### 4. Resolution Paths

Resolve every finding by exactly one of: **rewrite** to natural product wording, **relocate** to an out-of-scope surface, or **carve-out citation** (a §2 domain term). Silent acceptance is non-conformant.

## Disclosure surface

Record each interception in the disclosure ledger per `rules/disclosure-ledger.md` as rewrite, relocate, or carve-out.

## Mechanical enforcement

`conformity/plain_language_grep.py` enforces §1 against §3 in-scope surfaces with the §2 carve-outs whitelisted.

## Failure tells

A user-facing sentence naming a mechanistic generic (`AI` / `agent` / `LLM`), a harness brand identifier, a plan stage, or a process marker (`ratified` / `attestation` / `cutover-rehearsal`) where natural product wording carries the meaning.
