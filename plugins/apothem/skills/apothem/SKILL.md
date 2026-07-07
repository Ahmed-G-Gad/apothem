---
name: apothem
description: Install and manage the Apothem shared profile across AI assistant harnesses from Codex. Use when the operator asks to install, verify, update, or uninstall Apothem, or to sync their shared rules / skills / hooks / slash-commands / MCP-server profile into Codex or another supported tool.
---

# Apothem

Apothem is a host-agnostic AI-harness configuration manager: one
shared profile — rules, skills, hooks, slash-command pipelines, and MCP
servers — materialized into each tool's native configuration through
per-harness adapters.

## Managing the profile

Run the engine through the npm shim (needs Node.js and Python 3.10+ on the
`PATH`):

- `npx @ahmed-g-gad/apothem install --harness codex` — materialize the profile into Codex.
- `npx @ahmed-g-gad/apothem verify --harness codex` — report drift as structured JSON.
- `npx @ahmed-g-gad/apothem update --harness codex` — refresh to the current profile.
- `npx @ahmed-g-gad/apothem uninstall --harness codex` — reverse the install cleanly.

Pass `--harness all` to sync every supported tool at once. Every install backs
up existing targets first and is reversed cleanly by the matching uninstall.

## Engineering disciplines in force

Installing this plugin alone persists these directives as skill context, without
requiring the full `apothem install` run:

- **Plans-Locality.** Plan-suite artefacts (PROGRESS.md, PLAN-NOTES.md, PHASE.md, REPORT.md) live under `<project>/.apothem/plans/{suite}/` only — the sole canonical plans home, never in a global plans directory or any other global location. A legacy `<project>/.plans/` tree is no longer canonical; upgrade an existing one via `apothem migrate-workspace`.
- **Authority hygiene.** Never fabricate identity, scope, security posture, or version-pin data. Surface ambiguity via the structured-inquiry channel; the operator chooses.
- **Definitiveness.** Hedging vocabulary is eliminated where binding prescription is possible. Pre / post / failure conditions are stated on every contract.
- **Production-ready discipline.** Every change ships in production-ready form — tests, docs, CHANGELOG entry, conformant commit message, CI green — in the same change-set.
- **Plain-language.** Codebase artefacts and user-facing prose read as natural domain language with zero trace of internal planning structure.

Run `npx @ahmed-g-gad/apothem install --harness codex` to materialize the full
converted agent, skill, and hook cohort beyond these context directives.

Documentation: <https://apothem.ahmedgad.com/>
