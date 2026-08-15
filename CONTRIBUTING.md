<!-- SPDX-License-Identifier: MIT -->

# Contributing to Apothem

Welcome, and thank you for considering a contribution to **Apothem** — a host-agnostic AI-harness configuration manager that materializes one shared profile into each supported AI tool's native configuration directory via per-harness adapters under `src/apothem/harnesses/<harness>/` (for example, the Claude Code adapter materializes into `~/.claude/`). The project ships rules, skills, commands, hooks, and tooling that shape how every supported AI tool operates across every host that adopts the configuration. Every well-scoped contribution — a sharper rule, a tighter hook, a clearer doc, a regression-catching test — compounds across every session that loads this configuration. Contributions of all sizes are welcome.

## Code of Conduct

This project commits to inclusive, respectful participation. All contributors, maintainers, and reviewers are expected to follow the [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) at the repository root. Conduct concerns are reported to the security contact named in [`SECURITY.md`](./SECURITY.md), which provides a private channel separate from the public issue tracker.

## Development Environment Setup

The project targets **Python 3.10 or newer**. Dependencies and tooling are declared in `pyproject.toml`.

### One-time setup

```bash
# Clone your fork
git clone https://github.com/<your-username>/apothem.git
cd apothem

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate          # POSIX
# .venv\Scripts\Activate.ps1       # Windows PowerShell

# Install the package with dev dependencies (ruff + mypy + pytest + pytest-cov + pytest-xdist)
pip install -e ".[dev]"
# or, with uv (faster):
uv pip install -e ".[dev]"


# Enable the ratified pre-commit hooks
pre-commit install
```

After install, verify the toolchain resolves:

```bash
python -c "import xdist"                       # parallel pytest plugin available
pytest -n auto --collect-only -q | tail -1     # the full pytest suite collects cleanly (no '-n auto' parse error)
pre-commit run markdownlint --all-files                         # markdownlint-cli runs via pre-commit, not the pip dev extra
python -m apothem.conformity.gate --all .    # exits 0 across the ecosystem
```

### Routine verification

Run these locally before opening a pull request:

```bash
# Lint + format + type-check (Ruff + mypy)
make lint

# Conformity validators (every standalone validator via the orchestrator)
make validate

# Structural ecosystem sweep (frontmatter / registry / coherence checks)
make validate-ecosystem

# Full test suite
make test
```

All four targets are wired into CI; running them locally catches the common failures before a reviewer is involved. The orchestrator at `src/apothem/conformity/gate.py` is the canonical entry point for both `make validate` and the local pre-commit hooks below — list the registered validators with `python -m apothem.conformity.gate --list` or invoke a single one with `python -m apothem.conformity.gate --check <name>`.

### Pre-commit hooks

Pre-commit installation is part of the **One-time setup** above (the `pre-commit install` line). With the hooks installed, every `git commit` runs the ratified hook set from `.pre-commit-config.yaml`:

- **Generic hygiene** — `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-json`, `check-toml`, `check-added-large-files`, `check-merge-conflict`, `mixed-line-ending` (normalizes to LF).
- **Python** — `ruff` (lint, `--fix`) and `ruff-format`, then `mypy`.
- **Markdown / YAML** — `markdownlint` and `yamllint`.
- **Secrets** — `gitleaks`.
- **Commit message** — `conventional-pre-commit` (commit-msg stage, enforcing Conventional Commits).
- **Conformity corpus** — `conformity-corpus-perwrite`, the single per-Write matcher-corpus runner that fires the mechanical conformity bars over the git-tracked tree under `--strict` (a blocking finding fails the commit; advisory matchers report but do not gate).
- **GitHub Actions** — `actionlint`.

To run every hook against the entire working tree on demand (useful before opening a pull request, or after pulling new hooks via `pre-commit autoupdate`):

```bash
pre-commit run --all-files
```

### Line endings

The repository normalizes line endings to **LF** in the index for every text file via `.gitattributes` (`* text=auto eol=lf` plus per-extension reinforcement on shell scripts, Python, Markdown, YAML, and so on). `shellcheck` reads the working-tree bytes directly and surfaces SC1017 literal-CR errors when those bytes are CRLF; consequently the working tree must also be LF for the gate at `src/apothem/rules/code-craft-shell.md` M13.7 to pass clean.

**Windows contributors:** before cloning, set the local Git config so the working tree honors the LF index without per-checkout CRLF conversion:

```bash
git config --global core.autocrlf input
# Then clone normally.
```

If you cloned with `core.autocrlf=true` already in effect (the Git-for-Windows default), flush the working tree to LF after toggling the config:

```bash
git config core.autocrlf input
git rm --cached -r .
git reset --hard
```

The `core.autocrlf=input` setting keeps committed files LF-only while leaving locally-edited files untouched on commit, which is the contract the rest of the toolchain expects.

## Repository Layout — Where Things Live

The most common onboarding trap: several **root-level** directories look like
the authoritative source cohorts, but they are thin **distribution wrappers**
generated or maintained for each tool's native plugin/extension format. The
single source of truth a contributor edits lives under `src/apothem/`.

### Authoritative cohorts — edit these

Everything Apothem ships is authored once under `src/apothem/` and converted to
each tool's native surface at install/materialize time:

| Path | Holds |
| ---- | ----- |
| `src/apothem/commands/` | Slash-command definitions (`.md`) |
| `src/apothem/agents/` | Sub-agent definitions (`.md`) |
| `src/apothem/skills/` | Skills, one folder per skill with a `SKILL.md` entry point |
| `src/apothem/rules/` | Behavioral instruction files (`.md`) |
| `src/apothem/hooks/` | Shared hook scripts and message contexts |
| `src/apothem/output-styles/` | Output-style definitions |
| `src/apothem/statuslines/` | Statusline definitions |
| `src/apothem/templates/` | Plan-suite and ledger templates |
| `src/apothem/harnesses/<name>/templates/` | Per-harness output templates |
| `src/apothem/cli/` | Click CLI (`install`, `uninstall`, `update`, `verify`, …) |
| `src/apothem/harnesses/` | One sub-package per harness adapter |
| `src/apothem/conformity/` | Pre-emission conformity validators |
| `src/apothem/schemas/` | Schemas and fixture files |

If you are changing what a command, agent, skill, rule, or hook *does*, the file
you edit is under `src/apothem/` — never under a root-level wrapper.

### AI-instruction surfaces — keep the three in lockstep

Three root-level files carry the repo-internal agent-instruction canon and must
stay semantically equivalent: [`AGENTS.md`](AGENTS.md) is the canonical voice,
and [`CLAUDE.md`](CLAUDE.md) (Claude Code) and
[`.github/copilot-instructions.md`](.github/copilot-instructions.md) (GitHub
Copilot) mirror it. When you change a shared discipline — plans locality,
authorship headers, naming, session closure, the operating loop, the synthesis
posture — update all three in the same change-set. Editing one and leaving the
others stale reintroduces the fix-in-one-place-missed-in-many drift Apothem
exists to eliminate.

### Distribution surfaces — generated/wrapper, do not edit logic here

The following root-level surfaces exist so each tool can discover and install
Apothem through its own native plugin/extension mechanism. They package or point
at the authoritative cohorts; they do not contain the logic you edit:

| Surface | Role |
| ------- | ---- |
| `.claude-plugin/plugin.json` | Claude Code plugin manifest — generated from the source cohorts (see the regeneration checklist below) |
| `.claude-plugin/marketplace.json` | Claude Code plugin-marketplace entry |
| `commands/apothem.toml` | A single passthrough slash-command that shells out to the engine, for the tool whose native commands are TOML files |
| `plugins/apothem/` | The bundled plugin tree for the tool that consumes a local plugin source (carries `.codex-plugin/plugin.json` plus a bundled `skills/` copy) |
| `.agents/plugins/marketplace.json` | The plugin-marketplace entry that points at `plugins/apothem/` |
| `gemini-extension.json` | Gemini CLI extension manifest |
| `qwen-extension.json` | Qwen Code extension manifest |
| `vscode-extension/` | VS Code-family extension package (`package.json`, `extension.js`, icon) |
| `bin/apothem.mjs` | The npm shim — a Node launcher that locates Python and runs `python -m apothem` (see `bin/README.md`) |

Treat these as packaging. A change to behavior belongs in `src/apothem/`; the
distribution surfaces are then refreshed per the checklist below.

## Editing a Cohort → Regenerate Manifests

When you **add, rename, or remove** a command, agent, or skill under
`src/apothem/`, the generated distribution surfaces must be regenerated **in the
same change-set**, then the gates must pass. Run these from the repository root:

```bash
# 1. Regenerate the Claude Code plugin manifest (.claude-plugin/plugin.json).
#    The manifest is produced by build_plugin_manifest() in
#    src/apothem/lib/plugin_tree.py; there is no standalone CLI for it, so
#    regenerate via the module and write the result. The
#    test_committed_repo_manifest_matches_generator test pins the exact
#    arguments (catalog_prefix + address_default_command_dir):
python -c "import json; from pathlib import Path; from apothem.lib.plugin_tree import build_plugin_manifest; m = build_plugin_manifest(Path('src/apothem'), catalog_prefix='./src/apothem/', address_default_command_dir=True); Path('.claude-plugin/plugin.json').write_text(json.dumps(m, indent=2) + '\n', encoding='utf-8')"

# 2. Regenerate the docs reference inventory (source-generated reference pages).
node site/scripts/update-reference-inventory.mjs

# 3. Regenerate the behavior-diff golden corpus.
python scripts/dev/regen-behavior-goldens.py

# 4. Run the conformity gate and the test suite.
python -m apothem.conformity.gate --all .
make test
```

Step 1 has no dedicated script — the `build_plugin_manifest` function in
`src/apothem/lib/plugin_tree.py` is the canonical generator, and the
`test_committed_repo_manifest_matches_generator` test fails if the committed
`.claude-plugin/plugin.json` drifts from its output, so confirm that test is
green after regenerating. Steps 2 and 3 are run by `node` and the dev script
respectively. The behavior-diff and docs-drift gates run in CI and will block a
PR whose generated surfaces drifted from the source cohorts.

## Issue Filing

Before opening a new issue, search the existing issues — including closed ones — to confirm the topic is not already tracked. Templates live under [`.github/ISSUE_TEMPLATE/`](./.github/ISSUE_TEMPLATE/) and cover four classes:

- **Bug report** — unexpected behavior, regression, or incorrect output.
- **Feature request** — new capability, rule, skill, command, or hook.
- **Documentation** — gaps, errors, or improvements in the docs.
- **Question** — usage, configuration, or support questions.

Pick the closest template and fill every prompted field; the template structure is what reviewers rely on to triage quickly.

**Security issues do not belong in the public issue tracker.** Report vulnerabilities through the private channel documented in [`SECURITY.md`](./SECURITY.md).

## Pull Request Submission

The project uses a **fork-and-PR** workflow against the `main` branch.

1. Fork the repository on GitHub.
2. Create a feature branch on your fork (see *Branching strategy* below).
3. Make your changes; commit with sign-off (see *Sign-off / DCO* below).
4. Push the branch to your fork and open a pull request against `main`.

**One logical change per PR.** A PR that bundles a refactor, a feature, and a doc update is harder to review and harder to revert. Split unrelated work into separate PRs.

The PR description must include:

- **What** the change does, in one or two sentences.
- **Why** the change is being made — link the originating issue (`Fixes #123`, `Closes #456`).
- **Verification** — exactly which commands you ran locally and what their outcomes were.

The canonical PR shape is captured in [`.github/PULL_REQUEST_TEMPLATE.md`](./.github/PULL_REQUEST_TEMPLATE.md); GitHub will populate it automatically when you open the PR.

## Branching Strategy

- Branch off the latest `main`.
- Name branches `type/short-description`, where `type` is a Conventional Commits type and the description is kebab-case: `fix/hook-timeout-windows`, `feat/add-ratify-skill`, `docs/contributing-guide`.
- Before opening the PR, rebase on top of the current `main` so your history is linear and conflicts are resolved on your branch rather than during merge.

```bash
git fetch origin
git rebase origin/main
```

Avoid long-lived branches — short feedback cycles produce better reviews.

## Commit Message Convention

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```text
type(scope): subject

Optional body explaining the why behind the change.
Wrap the body at ~72 characters per line.

Signed-off-by: Your Name <you@example.com>
```

Recognized types:

| Type       | Use for                                                      |
| ---------- | ------------------------------------------------------------ |
| `feat`     | New user-facing capability                                   |
| `fix`      | Bug fix                                                      |
| `docs`     | Documentation-only changes                                   |
| `chore`    | Tooling, build, dependency updates with no behavioral impact |
| `refactor` | Internal restructuring with no behavioral change             |
| `test`     | Adding or refining tests                                     |
| `ci`       | CI workflow and pipeline changes                             |
| `perf`     | Performance improvements with no behavioral change           |
| `build`    | Build system, packaging, or distribution changes             |
| `style`    | Formatting-only changes with no logic impact                 |
| `revert`   | Reverting a previous commit                                  |
| `release`  | Release mechanics (version bump, changelog roll)             |

This set matches the `conventional-pre-commit` commit-msg hook in
`.pre-commit-config.yaml`, which rejects any commit message whose type is not
listed above.

Keep the **subject line under 72 characters**, in the imperative mood (`add hook timeout guard`, not `added` or `adds`). Use the body to explain the *why* — the *what* should already be visible in the diff.

## Code-Review Expectations

Every PR requires:

- **At least one approving review** from a maintainer listed in [`.github/CODEOWNERS`](./.github/CODEOWNERS).
- **All CI checks passing** — the ecosystem-validation sweep, the test suite, and any pre-commit hooks wired into CI.
- **Squash-merge** is the default strategy; the squashed commit message is derived from the PR title and description, so make those publish-quality.

Reviewers aim to respond within **5 business days**. If a PR is blocked on a review longer than that, a polite ping on the PR is welcome.

## Sign-off / DCO

Every commit must carry a `Signed-off-by` trailer per the [Developer Certificate of Origin](https://developercertificate.org/):

```text
Signed-off-by: Your Name <you@example.com>
```

Use the `-s` flag to add the trailer automatically:

```bash
git commit -s -m "feat(rules): add performance budget for hooks"
```

Enforcement happens at pull-request time: the `DCO` workflow ([`.github/workflows/dco.yml`](./.github/workflows/dco.yml)) runs on every PR targeting `main` and fails when any commit in the PR range lacks a `Signed-off-by: Name <email>` trailer. No local pre-commit hook checks the trailer, so add it yourself at commit time with `-s`. If the workflow flags a missing trailer, repair the branch with:

```bash
git commit --amend --signoff     # last commit only
git rebase --signoff HEAD~N      # the last N commits
```

## License Acknowledgement

This project is released under the [MIT License](./LICENSE) with copyright held by Ahmed G. Gad. By submitting a contribution, you agree that your work is licensed under the same MIT terms and that you have the right to make that grant — which is precisely what the DCO sign-off attests.

## Getting Help

- **Discussion and questions** — open a thread under [GitHub Discussions](https://github.com/ahmed-g-gad/apothem/discussions).
- **Bug reports and feature requests** — file an issue using the templates in [`.github/ISSUE_TEMPLATE/`](./.github/ISSUE_TEMPLATE/).
- **Security disclosures** — follow the private reporting process in [`SECURITY.md`](./SECURITY.md).

Welcome aboard.
