<!-- SPDX-License-Identifier: MIT -->

# Harness-native layouts

Examples of how a harness's configuration looks in its own **native** layout —
both the files an install materializes and the operator-authored local
overrides that sit beside them. Use these to understand where artifacts land
for a given tool before you install, and as a starting point for your own
project-local configuration.

## Files

| Path | Role |
|------|------|
| [`claude-code/native-install/settings.json`](claude-code/native-install/settings.json) | A materialized Claude Code `settings.json` — the shape an install writes into the harness's native location. |
| [`claude-code/settings.local.example.json`](claude-code/settings.local.example.json) | A template for a project-local `settings.local.json`. Copy it to `<project-root>/settings.local.json`, edit, and keep it out of version control (the `.local.json` suffix matches the gitignore pattern). |
| [`opencode/native-install/opencode.json`](opencode/native-install/opencode.json) | A materialized OpenCode `opencode.json` — a profile-rendered native config: the `$schema` pin, the `instructions` list naming each always-on rule in the `.apothem/support/` subtree, and the shared MCP inventory rendered into OpenCode's native `mcp` surface (`type: local`/`remote`, `${VAR}` secret indirection). |
| [`cursor/native-install/apothem-rules.mdc`](cursor/native-install/apothem-rules.mdc) | A materialized Cursor rules file — the shape a project-scope install writes into `<project-root>/.cursor/rules/`. The Apothem template and the profile-projected managed block are folded together inside the `<!-- BEGIN/END APOTHEM MANAGED BLOCK -->` sentinels; operator prose outside the sentinels is preserved on re-install. |

## Three adapter classes, side by side

These three examples show the three ways a harness receives configuration,
the distinction the [adapter-design deep-dive](https://apothem.ahmedgad.com/docs/blog/posts/multi-harness-adapter-design)
calls Class I, Class II-A, and Class II-B:

- **Claude Code (Class II-A) — raw plus vendor templates.** Apothem propagates
  its authored artifacts and ships vendor settings templates; the
  `settings.json` above is one such template, not a render of your profile.
- **OpenCode (Class II-B) — profile-rendered.** A materializer reads the shared
  profile's structured fields and emits a single native config file. The
  `opencode.json` above shows what that render produces — the schema pin, the
  always-on rule list, and an MCP inventory projected into OpenCode's native
  `mcp` surface, including the `headers` and `${VAR}` secret indirection a
  remote server needs. Its server list is illustrative and does not correspond
  to `profile.example.yaml`; to see the exact output for a given profile, use
  the `--dry-run` preview below.
- **Cursor (Class I, project-scope) — raw propagation into a project tree.**
  Cursor is a project-scope harness with no materializer:
  `apothem install --harness cursor --project <path>` merges the Apothem
  template into the operator's project at `<project-root>/.cursor/rules/apothem-rules.mdc`
  rather than a user-scope config home, and writes its skills and the shared
  rules and templates folders into your user home. The `apothem-rules.mdc`
  above shows the project file for the shared `profile.example.yaml`: the
  shared sentinel-merge step folds the identity, preferences (including the
  `verbose` per-harness override), and custom rules from the profile into the
  managed block. The MCP inventory is named there as reference, not rendered
  into Cursor's own MCP configuration. To see the exact output for your own
  profile, including the user-home folders, use the `--dry-run` preview below.

## Using these

The `native-install` file is illustrative — it shows the layout, not a profile
to install. To produce your own native config from the shared profile, preview
an install with `--dry-run`:

```bash
apothem install --harness claude-code --dry-run --json
```

For a project-scope harness such as Cursor, pass `--project` to preview where
the file lands in your project tree:

```bash
apothem install --harness cursor --project . --dry-run --json
```

To add a local override, copy `settings.local.example.json` to
`settings.local.json` in your project root and fill in the placeholders. The
local file layers on top of the installed configuration and is never committed.
