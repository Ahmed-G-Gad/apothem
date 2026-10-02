<!-- SPDX-License-Identifier: MIT -->

# Apothem — Global Instructions

Apothem wrote this block with `apothem install --harness antigravity`.
`~/.gemini/GEMINI.md` is a shared global instruction file: more than one
coding tool loads it, so this block carries guidance that holds in every
project and names no single tool as its reader. Apothem's Antigravity cohort
is installed as the `apothem` plugin under
`~/.gemini/antigravity-cli/plugins/apothem/`.

## Apothem reference material

The install placed Apothem's files here:

- `~/.gemini/antigravity-cli/plugins/apothem/plugin.json` — plugin metadata.
- `~/.gemini/antigravity-cli/plugins/apothem/skills/` — reusable techniques
  plus slash-command prompts converted into skills.
- `~/.gemini/antigravity-cli/plugins/apothem/rules/` — behavioral reference
  rules.
- `~/.gemini/antigravity-cli/plugins/apothem/agents/` — local agent
  definitions normalized from Apothem agents.
- `~/.gemini/antigravity-cli/plugins/apothem/.apothem/support/templates/` — support
  templates retained for prompts that cite reusable plan or audit assets.
- `~/.gemini/antigravity-cli/plugins/apothem/.apothem/support/hooks/` — hook support
  material retained as reference content; Apothem does not register
  Antigravity hook events until the adapter owns the schema translation.

## Project-Scope Surface

Project-specific instructions remain project-owned. This user-scope adapter
does not write workspace files unless the operator invokes a project-scope
harness adapter separately.

## Operator Surface

Operators may extend this file with project-specific instructions outside the
Apothem managed block. The apothem install folds its content into a
sentinel-delimited managed block on every `apothem install --harness
antigravity` invocation and preserves any operator prose outside the sentinels
verbatim; `apothem uninstall --harness antigravity` strips that block, backing
the prior file up under the Apothem backup root first. Project-scope
instructions still belong in `<workspace>/.agents/` or an operator-owned
Antigravity plugin.
