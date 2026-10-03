<!-- SPDX-License-Identifier: MIT -->

# Plugin distribution surfaces

One subdirectory per host whose plugin system Apothem publishes to. Neither is
authoritative source: both are distribution wrappers around the engine and
catalog in [`src/apothem/`](../src/apothem/). Edit the source, not these trees.

| Directory | Host | Manifest | Assembly |
|-----------|------|----------|----------|
| [`apothem/`](apothem/) | Codex | `.codex-plugin/plugin.json` | Hand-authored. The Codex plugin schema carries `skills` only, so the directory is a thin bootstrap: one skill plus its manifest. |
| [`claude-code/`](claude-code/) | Claude Code, Claude Cowork | `.claude-plugin/plugin.json` | **Generated.** Run `python scripts/dev/assemble_plugin_tree.py`; never edit by hand. |

## Why `claude-code/` is committed rather than built at release

The repository root is not a shippable plugin package. Cowork caps a plugin
package at 5,000 files and this repository carries roughly 6,150 — `site/` and
`tests/` alone are 85% of it, and neither is plugin content. Plugin packages
have no exclusion mechanism (no `.pluginignore`, no `exclude` manifest field),
so the only way to ship a package that fits is to give the plugin a root holding
plugin content and nothing else.

A git-source marketplace resolves a plugin's `source` against a clone of the
repository, so that root has to exist in the repository at the ref being
installed. Building it at release time would leave `main` unable to serve the
marketplace. Hence: assembled by
[`scripts/dev/assemble_plugin_tree.py`](../scripts/dev/assemble_plugin_tree.py)
from `apothem.lib.plugin_tree`, committed, and held to the generator by a CI
drift gate plus `tests/unit/test_plugin_tree.py`.

Claude Code itself never surfaced the problem: it clones a marketplace locally
and applies no file cap, so `"source": "./"` installed there and failed only in
Cowork.

## Working in this folder

Never hand-edit `claude-code/`. After changing any command, agent, skill, rule,
output style, or hook message under `src/apothem/`, regenerate and commit the
result in the same change-set:

```bash
python scripts/dev/assemble_plugin_tree.py
```

The manifest `version` comes from `pyproject.toml`. Claude Code keeps an
installed plugin on its cached copy until that string changes, so any change to
`claude-code/` after a release must ship under a new version:
[`scripts/release/check_plugin_version_bump.py`](../scripts/release/check_plugin_version_bump.py)
fails CI when the package differs from the last release tag under the same
version, and
[`scripts/release/bump_version.py`](../scripts/release/bump_version.py) moves
every version anchor at once.

Verify before handoff — the first command fails on drift, the second on a
malformed manifest:

```bash
python scripts/dev/assemble_plugin_tree.py --check
```

```bash
claude plugin validate plugins/claude-code
```
