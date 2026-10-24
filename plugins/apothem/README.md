<!-- SPDX-License-Identifier: MIT -->

# Apothem — Codex plugin

This directory is the **Codex plugin distribution surface** for Apothem,
installed through Codex's native marketplace:

```text
codex plugin marketplace add ahmed-g-gad/apothem
```

It is a hand-authored bootstrap, not authoritative source. What lives here:

| Path | Holds |
| ---- | ----- |
| `plugin.json` | The Codex plugin manifest, at the location Codex documents for a new package: a root `plugin.json` that declares the Agent Plugins 1.0.0 schema and carries the name, version, description, author, homepage, repository, license, and keywords. It names no skills path, because Codex discovers `skills/` from the plugin root. Its `version` is held in lockstep with `apothem.__version__` by `tests/unit/test_manifest_version_sync.py`. |
| `.codex-plugin/plugin.json` | The compatibility fallback, for Codex builds that read only this older manifest location. Codex documents it as still supported, with the root manifest canonical for identity; the fallback supplies only OpenAI-specific settings, and only when the root manifest has no `extensions.com.openai` object. It keeps the `skills` path the older layout needs. Its `version` is held in lockstep with the root manifest by the same test. |
| `skills/apothem/SKILL.md` | The Apothem entry skill Codex loads. |
| `README.md` | This file. |

The marketplace entry that points Codex at this directory is
[`.agents/plugins/marketplace.json`](../../.agents/plugins/marketplace.json).

## Manifest rules

`tests/unit/test_codex_plugin_manifest.py` checks each rule below.

- The root `plugin.json` MUST stay inside the schema's property set
  (`$schema`, `name`, `version`, `description`, `author`, `homepage`,
  `repository`, `license`, `keywords`, `extensions`). The schema sets
  `additionalProperties: false`, so a `skills` key there is invalid.
- The root `plugin.json` MUST NOT gain an `extensions.com.openai` object while
  the fallback stays: that object replaces the whole fallback overlay, and the
  two are not merged. Retire the fallback and this rule together.
- Neither manifest MAY declare custom agents. Codex documents no agents
  component for plugins, and the upstream request to add one is still open.
  Apothem agents reach Codex as `~/.codex/agents/*.toml` through
  `apothem install --harness codex`.
- The marketplace entry MUST carry a `policy` block. Codex tells authors to
  always include `policy.installation` (`AVAILABLE`, `INSTALLED_BY_DEFAULT`, or
  `NOT_AVAILABLE`) and `policy.authentication` (`ON_INSTALL` or `ON_USE`) on each
  entry. The entry sets the defaults Codex documents for a new entry,
  `AVAILABLE` and `ON_INSTALL`.
- This bundle ships a skill and nothing else. Codex plugins can also carry an
  `mcp.json`, hooks, and assets; a plugin that carries lifecycle hooks is not
  eligible for the public plugin directory, and installing it does not trust its
  hooks.

<!-- TODO(clarify): The Codex changelog gives no release for when a root
plugin.json became readable, so the fallback is kept on the strength of "still
supported" rather than a known minimum Codex version. Name that version, then
decide whether to retire .codex-plugin/plugin.json. -->

**Do not edit behavior here.** Everything Apothem ships is authored once under
[`src/apothem/`](../../src/apothem) and converted to each tool's native surface
at install / materialize time — see the Repository Layout section of the
[contributor guide](../../CONTRIBUTING.md). To change what a shipped skill does,
edit its source under `src/apothem/skills/`. The `apothem` entry skill has no
source there: `skills/apothem/SKILL.md` is hand-authored and is edited directly
in this directory.
