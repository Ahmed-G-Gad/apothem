<!-- SPDX-License-Identifier: MIT -->

# Tools

Pinned third-party npm command-line tools that CI installs from a committed lockfile with `npm ci`; the release, publish and audit installs pass `--ignore-scripts`, and the channel-smoke install does not. Each directory holds a `package.json` and its `package-lock.json` and nothing else. The table below is the index: a directory that is not listed here is documented nowhere.

## Directories

| Directory | Purpose |
|-----------|---------|
| `vsce/` | The `vsce` packager for the VS Code extension. `.github/workflows/release.yml` installs it to build the `.vsix` on a tag, and `.github/workflows/publish-vscode.yml` installs it to package and publish the extension; that workflow takes this lockfile from the commit it runs from, not from the tag it packages. Its `package.json` overrides `@azure/msal-node`; the condition for dropping the override is written in `publish-vscode.yml`. |
| `channel-smoke/` | The harness command-line tools that `.github/workflows/channel-smoke.yml` installs to smoke each install channel. Its `package.json` overrides `sharp`; the condition for dropping the override is written beside the override in the workflow. |

## Keeping the lockfiles current

- Dependabot opens the update pull requests (`.github/dependabot.yml`): `vsce/` weekly, `channel-smoke/` monthly, each with a 7-day cooldown.
- `.github/workflows/npm-audit.yml` runs `npm audit` and a lockfile install on every pull request that touches either directory, and again weekly.
- Before merging a `vsce/` bump, run `python -m pytest tests/scripts/test_release_vsix.py`. A pull request that changes only the lockfile runs the npm audit and no other job that installs it.
- Before merging a `channel-smoke/` bump, dispatch `channel-smoke.yml` on the pull request branch.

To bump a tool by hand, read the pins in the directory's `package.json` first. Both files pin exact versions, so install with `--save-exact`:

```bash
npm install --prefix tools/<dir> --package-lock-only --ignore-scripts --save-exact <package>@<version>
```

`--package-lock-only` updates `package.json` and `package-lock.json` without installing into `node_modules/`. Commit both files. For a transitive dependency, `--save-exact <package>@<version>` would add it to `package.json` as a new direct dependency; run `npm update <package> --prefix tools/<dir> --package-lock-only --ignore-scripts` instead and commit only the lockfile change, or pin it with an `overrides` entry. To change an `overrides` entry, edit `package.json`, then run `npm install --prefix tools/<dir> --package-lock-only --ignore-scripts` to refresh the lockfile.

## Why these are not under `.github/`

Dependabot cannot open a pull request for an npm manifest under `.github/`. Only the `github-actions` ecosystem holds the `workflows` token scope that a change under `.github/` needs, so every version and security update for an npm lockfile there fails at pull request creation with `dependency_file_not_supported` ([dependabot-core#15237](https://github.com/dependabot/dependabot-core/issues/15237)). Keep these directories outside `.github/`. `tests/scripts/test_tool_lockfile_locations.py` fails when a non-Actions Dependabot entry points back under `.github/`.

## Release and archive exclusion

This folder stays out of every shipped archive. `scripts/build_release_tarball.py` lists `tools` in `ROOT_EXCLUDE_DIRS`, so the signed release archives leave it out, and `.gitattributes` marks `tools/` `export-ignore`, so GitHub source archives leave it out too.

## Working in this folder

Run the checks before handoff:

```bash
python -m pytest tests/scripts/test_tool_lockfile_locations.py tests/scripts/test_release_vsix.py
python -m apothem.conformity.gate --all .
```
