<!-- SPDX-License-Identifier: MIT -->

# Apothem

Apothem is a host-agnostic AI-harness configuration manager. It
authors one shared profile — rules, slash-commands, skills, hooks,
output-styles, settings (MCP servers included), schemas, and docs — and
materializes that whole synced unit into each tool's
native configuration directory through per-harness adapters. One source of
truth, seventeen destinations, no hand-maintained drift.

## Using Apothem from Qwen Code

Run the engine through the npm shim (needs Node.js and Python 3.10+ on the
`PATH`):

```bash
npx @ahmed-g-gad/apothem install   --harness qwen-code
npx @ahmed-g-gad/apothem verify    --harness qwen-code
npx @ahmed-g-gad/apothem update    --harness qwen-code
npx @ahmed-g-gad/apothem uninstall --harness qwen-code
```

`install` materializes the profile into Qwen Code's user-global configuration
under `~/.qwen/` — the `QWEN.md` context file, `settings.json`, and the
`commands`, `skills`, and `agents` directories; pass `--harness all` to sync
every supported tool at once. `verify` reports drift as structured JSON. Every
install backs up existing targets first and is reversed cleanly by the matching
`uninstall`.

## Engineering disciplines in force

Installing this extension alone persists these directives as session context,
without requiring the full `apothem install` run:

- **Plans-Locality.** Plan-suite artefacts (PROGRESS.md, PLAN-NOTES.md, PHASE.md, REPORT.md) live under `<project>/.apothem/plans/{suite}/` — the sole canonical home; a legacy `<project>/.plans/` tree upgrades via `apothem migrate-workspace`. They are never written to a global plans directory or any other global location.
- **Authority hygiene.** Never fabricate identity, scope, security posture, or version-pin data. Surface ambiguity via the structured-inquiry channel; the operator chooses.
- **Definitiveness.** Hedging vocabulary is eliminated where binding prescription is possible. Pre / post / failure conditions are stated on every contract.
- **Production-ready discipline.** Every change ships in production-ready form — tests, docs, CHANGELOG entry, conformant commit message, CI green — in the same change-set.
- **Plain-language.** Codebase artefacts and user-facing prose read as natural domain language with zero trace of internal planning structure.

Run `npx @ahmed-g-gad/apothem install --harness qwen-code` to
materialize the full converted command, skill, and sub-agent cohort beyond these
context directives.

- Documentation: <https://apothem.ahmedgad.com/>
- Source: <https://github.com/ahmed-g-gad/apothem>
