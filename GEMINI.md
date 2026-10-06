<!-- SPDX-License-Identifier: MIT -->

# Apothem

Apothem is a host-agnostic AI-harness configuration manager. It
authors one shared profile — rules, slash-commands, skills, hooks,
output-styles, settings (MCP servers included), schemas, and docs — and
materializes that whole synced unit into each tool's
native configuration directory through per-harness adapters. One source of
truth, seventeen destinations, no hand-maintained drift.

## Using Apothem from Gemini CLI

Run the engine through the npm shim (needs Node.js, and Python 3.10+ with
the `click` and `rich` packages, on the `PATH`):

```bash
npx @ahmed-g-gad/apothem@1.1.0 install   --harness gemini-cli --project .
npx @ahmed-g-gad/apothem@1.1.0 verify    --harness gemini-cli --project .
npx @ahmed-g-gad/apothem@1.1.0 update    --harness gemini-cli --project .
npx @ahmed-g-gad/apothem@1.1.0 uninstall --harness gemini-cli --project .
```

`install` materializes the profile into this project's `GEMINI.md` and
`.gemini/commands/`; pass `--harness all` to sync every supported tool at
once. `verify` reports drift as structured JSON. Every install backs up
existing targets first and is reversed cleanly by the matching `uninstall`.

The bundled `/apothem` command runs any engine subcommand and summarizes the
result.

## Engineering disciplines in force

Installing this extension alone persists these directives as session context,
without requiring the full `apothem install` run:

- **Plans-Locality.** Plan-suite artefacts (PROGRESS.md, PLAN-NOTES.md, PHASE.md, REPORT.md) live under `<project>/.apothem/plans/{suite}/` — the sole canonical home; a legacy `<project>/.plans/` tree upgrades via `apothem migrate-workspace`. They are never written to a global plans directory or any other global location.
- **Authority hygiene.** Never fabricate identity, scope, security posture, or version-pin data. Surface ambiguity via the structured-inquiry channel; the operator chooses.
- **Definitiveness.** Hedging vocabulary is eliminated where binding prescription is possible. Pre / post / failure conditions are stated on every contract.
- **Production-ready discipline.** Every change ships in production-ready form — tests, docs, CHANGELOG entry, conformant commit message, CI green — in the same change-set.
- **Plain-language.** Codebase artefacts and user-facing prose read as natural domain language with zero trace of internal planning structure.

Run `npx @ahmed-g-gad/apothem@1.1.0 install --harness gemini-cli --project .` to
materialize the full converted command, skill, and agent cohort beyond these
context directives.

- Documentation: <https://apothem.ahmedgad.com/>
- Source: <https://github.com/ahmed-g-gad/apothem>
