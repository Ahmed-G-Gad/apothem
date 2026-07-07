<!-- SPDX-License-Identifier: MIT -->

# Apothem — Codex plugin

This directory is the **Codex plugin distribution surface** for Apothem,
installed through Codex's native marketplace:

```text
codex plugin marketplace add ahmed-g-gad/apothem
```

It is a thin wrapper, not authoritative source. What lives here:

| Path | Holds |
| ---- | ----- |
| `.codex-plugin/plugin.json` | The Codex plugin manifest — name, version, provenance, and the skills path. Its `version` is held in lockstep with `apothem.__version__` by `tests/unit/test_manifest_version_sync.py`. |
| `skills/apothem/SKILL.md` | The Apothem entry skill Codex loads. |

**Do not edit behavior here.** Everything Apothem ships is authored once under
[`src/apothem/`](../../src/apothem) and converted to each tool's native surface
at install / materialize time — see the Repository Layout section of the
[contributor guide](../../CONTRIBUTING.md). To change what a skill does, edit
its source under `src/apothem/skills/`, not this generated wrapper.
