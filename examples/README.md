<!-- SPDX-License-Identifier: MIT -->

# Examples

Minimal, runnable demonstrations of every artifact class in Apothem. Each subdirectory ships the smallest possible working example for one class plus a per-example `README.md` explaining what it demonstrates and how to use it.

## Index

| Example | Class | What it shows |
|---------|-------|---------------|
| [`minimal-claude-md/`](minimal-claude-md/) | Project configuration | A minimal `CLAUDE.md` at project scope |
| [`minimal-skill/`](minimal-skill/) | Skill | A folder skill with `SKILL.md` entry point and frontmatter |
| [`minimal-agent/`](minimal-agent/) | Agent | A persistent agent definition with mission, deliverable, and constraints |
| [`minimal-command/`](minimal-command/) | Slash command | A flat `.md` command definition with frontmatter and workflow |
| [`minimal-hook/`](minimal-hook/) | Hook | A POSIX shell hook script wired into a `PreToolUse` event |
| [`minimal-output-style/`](minimal-output-style/) | Output style | A flat `.md` output-style definition with `name` + `description` frontmatter |
| [`minimal-plan-pipeline/`](minimal-plan-pipeline/) | Plan pipeline | A walkthrough of the core `/plan-spec` → `/plan-generate` → `/plan-review` → `/plan-execute` pipeline (`/plan-design` adds the architecture stage for architecture-bearing suites) |
| [`minimal-research-pipeline/`](minimal-research-pipeline/) | Research pipeline | A walkthrough of the thirteen-stage `/research-ideate` → `/research-spec` → `/research-theory` → `/research-sources` → `/research-synthesis` → `/research-proposal` → `/research-design` → `/research-experiment` → `/research-analysis` → `/research-paper` → `/research-review` → `/research-publish` → `/research-disseminate` pipeline (also driven end-to-end by the wrapped `/research` workflow) |
| [`mcp/`](mcp/) | MCP server config | MCP server-configuration template (`example-server.json`) — templates only, no secrets |
| [`harnesses/`](harnesses/) | Harness-native layout | Per-harness native install layouts (e.g. a Claude Code `settings.local.example.json`) |

## Conventions

- Every example is self-contained — no cross-example dependencies.
- Every example carries its own `README.md` describing inputs, outputs, and how to invoke it.
- Filenames follow kebab-case; canonical entry points (`SKILL.md`, `CLAUDE.md`) follow ecosystem-wide conventions.
- Examples are intentionally minimal; production artifacts will be larger and more elaborate.
- Every example is listed in the Index table above — an unlisted example is an orphan.
- The single-artifact `minimal-*` scaffolds are fixture-class folders.

## Working in this folder

To add an example: create a `minimal-<class>/` subdirectory with its entry
artifact plus a `README.md` documenting inputs, outputs, and invocation, then
add a row to the Index table above — all in the same change-set. Exercise the
CLI-facing examples against the packaged fake profile fixtures via the dry-run
path (which validates a profile and a materialization plan without writing
harness files), then run the repository conformity gate before handoff:

```bash
python -m apothem.conformity.gate --all .
```

## Running the examples

Most examples are read-only documentation. Where invocation is meaningful, the
per-example `README.md` shows the exact command and the expected output.

## CLI profile and harness smoke checks

Use the packaged fake profile fixtures when exercising examples:

```bash
apothem profile show --profile src/apothem/schemas/profile.minimal.yaml --json
apothem install --harness claude-code --profile src/apothem/schemas/profile.minimal.yaml --dry-run --json
apothem install --harness all --project . --profile src/apothem/schemas/profile.minimal.yaml --dry-run --json
```

The dry-run commands validate profiles and materialization plans without
creating harness files. Project-scope adapters require `--project PATH`; the
registry-wide `all` selector includes project-scope adapters.
