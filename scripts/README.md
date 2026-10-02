<!-- SPDX-License-Identifier: MIT -->

# Scripts

Operator-, release-, install-, and dev-facing executables for the `apothem` repository — every standalone script lives here. Root-level entries are the operator / contributor utilities; `installer/` holds the install ceremonies, `release/` the release-engineering recipes, and `dev/` the internal CI/QA orchestration and audit / validation tooling. The tables below are the index: `dev/` has no README of its own, so a script that is not listed here is documented nowhere.

## Root-level scripts

| Script | Purpose |
|--------|---------|
| `apothem` / `apothem.ps1` / `apothem.cmd` | The `apothem` CLI binary. Dispatches `apothem <subcommand>` to the matching install/update/uninstall script; serves `--help` and `--version` inline. `.ps1` is the PowerShell parity sibling; `.cmd` is the Windows CMD wrapper delegating to the `.ps1`. |
| `build_release_tarball.py` | Cross-platform release-runtime archive builder (tar.gz on darwin/linux, zip on windows). Adds the `bin/` launcher layout the installers consume, excludes plan-suite ephemera / CI metadata / VCS internals, and emits the archive's SHA-256 digest to stdout. |
| `inject-header.py` / `inject-header.sh` | Deterministic authorship-header injector. Reads the canonical SPDX header line from `src/apothem/schemas/`; runs in `fix-in-place`, `emit-patch`, or `check` modes. The `.sh` wrapper locates a Python 3 interpreter and delegates to the `.py`. |

## `dev/` — contributor maintenance utilities

| Script | Purpose |
|--------|---------|
| `rebuild-assets-resvg.py` | The single canonical asset generator: regenerate the raster brand assets in [`assets/`](../assets/) from the editable SVG sources in `assets/src/` via a `resvg` binary plus Pillow. Supports a `--check-only` mode; `tests/unit/test_assets_manifest_coverage.py` asserts it produces every icon the PWA manifest references. |
| `regenerate-completions.sh` / `.ps1` | Re-emit the shell-completion scripts (`bash` / `zsh` / `fish`) into `src/apothem/cli/completions/` after a CLI surface change; byte-identical regeneration is the verification check. |
| `regen-behavior-goldens.py` | Regenerate the behavior-diff golden corpus under `tests/fixtures/behavior-diff/` from the deterministic HOME-isolated install-driver and CLI oracles after an intended behavior change; the canonicalized comparison stays portable across platforms, so a non-empty `git diff` flags platform-form churn to review. |
| `check_pip_pin_drift.py` | Assert every workflow's `PIP_PIN_VERSION` matches the canonical pin and no raw `pip==<version>` literal has been reintroduced. Invoked by CI. |
| `check_site_version_parity.py` | Assert `site/package.json`'s version matches `pyproject.toml`'s. Both are hand-maintained and the site renders its copy in the landing footer, so drift is silent — the site simply advertises a release that is no longer shipping. Invoked by CI beside the pin-drift check. |
| `check_changelog_links.py` | Assert every `## [x.y.z]` heading in `CHANGELOG.md` has a link definition naming tag `vx.y.z`, that `[Unreleased]` compares from the latest heading, and that no version link is orphaned. Both are hand-kept: after 1.1.0 the `[1.1.0]` link was never added and `[Unreleased]` still compared from v1.0.2. Invoked by CI beside the site version parity check; `bump_version.py` leaves a changelog it accepts. |
| `check_readme_file_coverage.py` | Report every git-tracked file a folder ships that the folder's own README never names. A per-folder README is that folder's operating contract, so its file table is load-bearing — a module missing from it reads as nonexistent. Advisory by default; `--strict` exits non-zero and is how CI invokes it. |
| `channel_smoke.py` | Run each documented install channel anonymously: an isolated home, credential variables removed, Git prompts disabled. Each channel lists its commands verbatim from the README, and `tests/scripts/test_channel_smoke.py` keeps the two in step. `--list` prints channel ids for the workflow matrix; `--channel ID` or `--all` runs them. Invoked by `channel-smoke.yml`. |
| `check_pr_title_squash_length.py` | Reject a PR title that GitHub's squash-merge suffix would push past the 72-character Conventional Commits cap. A squash merge composes the subject as `<title> (#<number>)`, so a compliant title can still produce a non-conforming commit: PR #6's title was 68 characters, its merge commit 73, and every `quality` job on `main` failed the conformity step after a fully green branch. The branch cannot catch this from its own commits — the subject does not exist until the merge. Imports the limit from `conventional_commit_grep` rather than restating it. Invoked by CI on pull requests only. |
| `assemble_plugin_tree.py` | Materialize the committed Claude Code plugin package at [`plugins/claude-code/`](../plugins/claude-code/) from `apothem.lib.plugin_tree`. The repository root is not a shippable package — Cowork caps a plugin at 5,000 files and the repo carries ~6,150, of which `site/` and `tests/` are 85% — and plugin packages have no exclusion mechanism, so the distribution unit is this assembled tree. `--check` re-assembles into a scratch directory and fails on any drift from the commit; invoked by CI. |
| `collect_metrics.py` | Write the per-commit metrics artifact the CI `metrics` job uploads: line + branch coverage per package (engine, conformity, audit) with floors from `pyproject.toml` (`--check-floors` exits 1 below a floor), the always-on instruction bytes each of the 17 harnesses loads at launch after an isolated install (per-harness rule in the script and the developer guide), CLI cold start, and end-to-end hook latency from `bench_hooks.py`. Every `null` value names its reason under `nulls`. |
| `sync_eval_rule_cases.py` | Rewrite the `append_system_prompt` of every `arm:rule-on` case under [`evals/rules/`](../evals/rules/) from its rule's runtime text (frontmatter, SPDX line and `## Bindings` removed), so a rule-effect pair measures the rule as it ships. `--check` reports drift without writing; `tests/unit/test_eval_suite.py` runs the check. |
| `run_corpus_gate.py` | Repo-root shim that puts the checkout's `src/` on `sys.path` and dispatches to `apothem.conformity.gate`. The pre-commit corpus hook runs in an isolated venv where the package is not importable, so it cannot call `python -m apothem` the way the engine does; every argument forwards unchanged. |
| `validate_harness_convention_pins.py` | Assert every registered adapter carries a `STANDARD-CONVENTION-PIN.md` and that none has gone stale. The adapter count is derived from the filesystem, never hardcoded. |
| `validate_ecosystem.py` | Ecosystem-wide structural and frontmatter validator: required directories and core files exist, every artifact declares the mandatory frontmatter fields, `version` is SemVer-shaped, `updated` is ISO 8601, `name` is kebab-case. Delegates hook checks to `validate_hooks.py`. |
| `validate_hooks.py` | Hook-infrastructure validator: the Claude Code `settings.json` template is present and valid JSON, each runtime declares its required events, the Python hook scripts exist and import cleanly, the message files are present, and no hardcoded absolute user path has crept in. |
| `chaos_pass.py` | Adversarial hook exercise — every configured hook command against a storm of hostile inputs (garbled stdin, a missing context file, a temp working directory with a fake `HOME`). Each must still exit 0 with a valid envelope, which is the dispatcher's fail-open contract stated as a test. |
| `audit_all.py` | One-shot quality orchestrator: `ruff check`, `ruff format --check`, `mypy`, `pytest`, `validate_ecosystem`, `chaos_pass`, in that order. Aborts on the first failure unless `--continue-on-error` aggregates them. |
| `auto_update.py` | Report the latest signed release tag the checkout has not incorporated; `--apply` fast-forwards to it. Updates target a signed tag rather than a moving branch, and `--apply` refuses an unsigned or tampered tag unless `APOTHEM_ALLOW_UNVERIFIED=1` downgrades the refusal to a warning. |
| `memory_audit.py` | Health audit of the harness memory tiers — each `MEMORY.md` index's line budget, topic-index integrity, orphan topic files, and frontmatter-date freshness. `--fix` is the only mutating path and truncates an over-budget index, nothing else. |
| `admin_merge.py` | Solo-maintainer self-merge ceremony. Main-branch protection requires one approving review and is admin-enforced, which by design stops the maintainer merging their own PR even with `--admin`. This runs the documented relax → merge → restore toggle inside `try`/`finally` so the protection is never left relaxed on failure. |
| `per-claim-register.md` | Not a script: the evidence register backing every threshold- or measurement-bearing claim in `src/apothem/rules/*.md`, one row per claim with its evidence pointer and verification stamp. |

## `installer/` — the canonical install scripts

The operator-facing bootstrap, update, and uninstall ceremonies — paired across three shell families. These are the scripts the network-install one-liners (`curl … | bash`, `irm … | iex`) fetch and the release-runtime archives bundle.

| Script family | Purpose |
|---------------|---------|
| `install.sh` / `install.ps1` / `install.bat` | Bootstrap the `apothem` package and materialize harness config. Idempotent; honors `APOTHEM_HARNESS` / `APOTHEM_REF` and sibling environment overrides. The `.bat` translates the documented POSIX flags (`--clean`, `--fresh`, `--dry-run`, `--yes`) to their PowerShell parameters, then delegates to the `.ps1`. |
| `update.sh` / `update.ps1` / `update.bat` | Update an existing install in place. Driven by environment overrides only (no CLI flags), so the `.bat` forwards its arguments verbatim. |
| `uninstall.sh` / `uninstall.ps1` / `uninstall.bat` | Remove the materialized harness config (via the engine) and the `apothem` PATH shim; confirms before removal unless `--yes`. Optional `--remove-source` deletes the managed clone. The `.bat` translates these POSIX flags — plus `--harness NAME` — to their PowerShell parameters, then delegates to the `.ps1`. |

## `release/` — release-engineering recipes

Invoked by the release engineer and by `.github/workflows/release.yml`. Each ships a POSIX `.sh` and a PowerShell `.ps1` parity sibling (the `.py` scripts and `requirements-build-linux.txt` are single-file siblings: Python runs on every host).

| Script family | Purpose |
|---------------|---------|
| `bump_version.py` | Move every version anchor (packaging, npm, site, extension, marketplace and citation manifests, the CHANGELOG section and links, the SECURITY.md support row) to one new `MAJOR.MINOR.PATCH`, then regenerate the plugin package, behavior goldens and docs pages. Stdlib only; `--dry-run` lists the changes. Its anchor list is held to `tests/unit/test_manifest_version_sync.py` by `tests/scripts/test_bump_version.py`. |
| `build-release-assets` | Build the full GitHub Releases asset matrix for a version tag (runtime tarballs/zips, sdist + wheel supply-chain evidence, SBOM, SHA256SUMS). |
| `check_plugin_version_bump.py` | Fail when a Claude Code marketplace plugin differs from the newest earlier release tag (moved source or changed files) while its manifest `version` is unchanged; Claude Code keeps users on a cached plugin until that string changes. Skips with a message when no `vMAJOR.MINOR.PATCH` tag is reachable; `--base-ref` overrides the base. Run by CI's release-preflight on pull requests and pushes and by the release build on tags. |
| `check-release-ready` | Gate post-release follow-up work: the tag must name an existing non-draft release and every required workflow for the release commit must be green. |
| `generate_sbom.py` | Write the CycloneDX SBOM of the built distributions: the wheel's metadata and declared requirements, every package vendored under `apothem/_vendor` (the `vendor.txt` pins, each checked against the wheel, with licenses held to `REUSE.toml` by a test), and each distribution's SHA-256. Deterministic under `SOURCE_DATE_EPOCH`. The release build writes it into `dist/` so it is signed and is a provenance subject. Stdlib only. |
| `normalize_sdist.py` | Rewrite sdist archives in place so identical sources give identical bytes: entries sorted, mtimes clamped to `SOURCE_DATE_EPOCH`, owners cleared, modes normalized (0755/0644), gzip header time fixed and no file name stored; contents unchanged, unsafe member names refused. The release build runs it after `python -m build --no-isolation`. Stdlib only. |
| `generate-sbom` | Thin `.sh` / `.ps1` wrappers that run `generate_sbom.py` on `dist/` (or a given directory) for the local asset matrix. |
| `sign-assets` | Cosign keyless-OIDC `sign-blob` recipe for the release asset matrix: one `<asset>.cosign.bundle` (signature, Fulcio certificate and Rekor entry) per asset plus one for `SHA256SUMS`, the same naming `release.yml` publishes. |
| `verify-provenance` | Verify a downloaded release asset set (default: the current directory): the `SHA256SUMS` manifest, every `<asset>.cosign.bundle` (or legacy `<asset>.sig`) against the exact identity `https://github.com/Ahmed-G-Gad/apothem/.github/workflows/release.yml@refs/tags/<tag>`, and `provenance.intoto.jsonl` for the wheel and sdist via `slsa-verifier --source-uri github.com/Ahmed-G-Gad/apothem --source-tag <tag>`. The tag comes from the wheel name unless `--tag` / `-Tag` is given. Owner casing matters: the certificates say `Ahmed-G-Gad`. |

## Conventions

- Every script carries the canonical SPDX header line at its head.
- Shell scripts ship a POSIX `.sh` and a PowerShell `.ps1` sibling for cross-platform parity; `.bat` wrappers translate the documented POSIX flags to their PowerShell parameters and then delegate to the `.ps1`, so a CMD user gets the same `--flag` UX as the `.sh` sibling (a wrapper for a command with no CLI flags, such as `update`, forwards its arguments verbatim). Cross-platform parity is structural — touching one member of a family obliges updating its siblings in the same change-set.
- One-shot migration / normalization utilities default to `--dry-run` and are idempotent on re-run.
- Regenerator scripts (assets, shell completions) verify by byte-identical regeneration; the install/uninstall ceremonies keep their idempotency and unsafe-target-refusal guards.
- Self-tests for these scripts live under [`tests/scripts/`](../tests/scripts/).

## Working in this folder

To add or change a script: place it in the matching class subdirectory (or the
root for operator utilities), supply the cross-platform sibling(s), and add a
row to the relevant table above. Self-tests live under
[`tests/scripts/`](../tests/scripts/) (and [`tests/packaging/`](../tests/packaging/)
for the release-artifact builders); run them plus the conformity gate before
handoff:

```bash
python -m pytest tests/scripts tests/packaging
python -m apothem.conformity.gate --all .
python scripts/inject-header.py --mode check <path>   # confirm SPDX headers
```

Lint shell with the project's shell linters before handoff.
