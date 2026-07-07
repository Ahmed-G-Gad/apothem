<!-- SPDX-License-Identifier: MIT -->

# Apothem — Gemini CLI Bootstrap

This file is materialised by `apothem install --harness gemini-cli --project <path>` and lands at `<project>/GEMINI.md`, the vendor-canonical project-context surface. Analogous to the project `CLAUDE.md` anchor, this file is read by `gemini-cli` at every session start in this project.

The gemini-cli adapter is project-scope only. User-scope `~/.gemini/` is already claimed by the antigravity adapter (which writes `~/.gemini/GEMINI.md` as its anchor); the gemini-cli adapter sidesteps the namespace collision by materialising under `<project>/` exclusively.

## What Apothem governs in this project

Apothem propagates a shared governance and convention surface across every supported AI harness in this project's host environment. Inside `gemini-cli`, the surface manifests at the project root as native Gemini files plus an Apothem support tree:

- `<project>/GEMINI.md` — this file; the vendor-discovered project-context anchor.
- `<project>/.gemini/commands/*.toml` — Gemini slash commands converted from Apothem command prompts.
- `<project>/.gemini/agents/*.md` — local Gemini subagents normalized from Apothem agents.
- `<project>/.gemini/skills/*/SKILL.md` — Apothem skills where a skill surface is available.
- `<project>/.gemini/.apothem/support/rules/` — Apothem Markdown rules used as reference material.
- `<project>/.gemini/.apothem/support/templates/` — plan, report, and audit templates.
- `<project>/.gemini/.apothem/support/hooks/` — hook messages and helper scripts retained as support material.

Do not treat `.gemini/.apothem/support/` as a
Gemini-native discovery namespace. They are Apothem-owned support trees
referenced by this bootstrap, generated commands, and installed skills.

## Engineering disciplines in force

Apothem's foundational mandates apply uniformly across every harness, including gemini-cli:

- **Plans-Locality.** Plan-suite artefacts (PROGRESS.md, PLAN-NOTES.md, PHASE.md, REPORT.md) live under `<project>/.apothem/plans/{suite}/` — the sole canonical home; a legacy `<project>/.plans/` tree upgrades via `apothem migrate-workspace`. They never land in a global plans directory or any other global-ecosystem location.
- **Authority hygiene.** Never fabricate identity, scope, security posture, or version-pin data. Surface ambiguity via the canonical structured-inquiry channel; the operator chooses.
- **Definitiveness.** Hedging vocabulary (`maybe`, `might`, `usually`, `generally`, `typically`, `probably`) is eliminated where binding prescription is possible. Pre / post / failure conditions are stated on every contract.
- **Production-ready discipline.** Every change ships in production-ready form — tests, docs, CHANGELOG entry, conformant commit message, CI green — in the same change-set.
- **Plain-language.** Codebase artefacts and user-facing prose read as natural domain language with zero trace of internal planning structure.
- **Observe-decide-act discipline.** Tool use runs as a loop — observe the current state, decide the next move from what was observed, then act — never an edit before a read or a result asserted before a check. Independent reads and searches run together in one pass, not one per turn; the loop closes on a verifiable condition (a gate green, a read confirmed), never a fixed number of tries. Advisory, never an auto-applied behavior.

## Refreshing the file

Re-run `apothem install --harness gemini-cli --project <this-project-root>` to refresh the Apothem managed block in this `GEMINI.md`, the converted native entries, and the support cohorts. The install folds Apothem's content into a sentinel-delimited managed block in `GEMINI.md` and preserves any operator prose outside the sentinels verbatim; the converted `.gemini/` entries are Apothem-owned and replaced in place while unrelated operator files are left untouched; it is idempotent. The companion `apothem uninstall --harness gemini-cli --project <this-project-root>` strips the managed block from `GEMINI.md` (leaving operator prose in place; the file is removed only when nothing but the block remained), backing the prior file up under the Apothem backup root (`~/.apothem/backups/<timestamp>/gemini_cli/`) first. `apothem verify --harness gemini-cli --project <this-project-root>` checks the file is present and non-empty.
