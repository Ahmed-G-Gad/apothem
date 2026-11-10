<!-- SPDX-License-Identifier: MIT -->

# Tests

The `apothem` test suite. `pytest` is the sole test framework; the configuration lives in the root `pyproject.toml` under `[tool.pytest.ini_options]`.

## Configuration

| Setting | Value |
|---------|-------|
| `testpaths` | `tests` |
| `addopts` | `-ra --strict-markers --import-mode=importlib -n auto` |

`--import-mode=importlib` avoids basename collisions between sibling `test_*.py` files across subtrees; `-n auto` runs the suite in parallel via `pytest-xdist`.

## Layout

| Subtree | Holds |
|---------|-------|
| `unit/` | Per-module unit tests — the harness adapters (one per registered harness in the 17-harness cohort), the CLI surface, the harness materializer, the conformity-gate scope, the parallel sweep, the propagation manifest — **plus a repo-coherence-guard class**: cross-surface drift guards (`test_harness_registry.py` against `site/app/page.tsx` + `pyproject.toml`, `test_citation_cff.py`, `test_example_settings_sync.py`, `test_example_cursor_rules_sync.py`, `test_assets_manifest_coverage.py`, `test_guard_wiring_coherence.py`, `test_crlf_set_sync.py` against `.gitattributes` + `.editorconfig` + `.pre-commit-config.yaml`) and the `unit/docs/` subtree, which validates the docs-site frontmatter examples against the conformity contract. |
| `integration/` | Cross-component integration tests — multi-harness parity, the hermetic clean-machine installer gate, installer tag-verification aborts, clean-slate install, the rollback CLI, the install-ledger acceptance matrix, memory portability / isolation, the self-contained vendored runtime, and the byte-golden behavior-diff walls (CLI + install-driver), with a guard that their oracles capture the same bytes on Windows and Linux. |
| `conformity/` | Per-validator self-tests. Most matchers own a directory named for the matcher's kebab module (`hedging-grep`, `secret-leak-grep`, `magic-number-grep`, `bare-except-grep`, `binding-reciprocity-grep`, `unpinned-action-grep`, and more) carrying `pass` / `fail` fixtures or scenario tests; a set of top-level `test_*.py` files hold cross-matcher infrastructure and scope-contract tests (the corpus per-write runner, the matcher-coverage loop, the standalone-grep in-process sweep). See [Conformity corpus layout](#conformity-corpus-layout) for the directory-name resolution rules. |
| `hooks/` | Hook-infrastructure tests — the dispatcher, hook-context emission, the session-start bootstrap, the interpreter locator, the header-inject guard, and the plan-write guard. |
| `scripts/` | Tests for the executables under [`scripts/`](../scripts/) — the header injector, the installer invocation model, the release-notes extractor, the SBOM recipe, script-pair parity, the behavior-diff golden regenerator, and the validation tooling. |
| `packaging/` | Release-artifact packaging tests — sdist + wheel payload contract, runtime tarball/zip build, examples validity. |
| `commands/` | Slash-command behavior tests (e.g., `plan-spec-quick`). |
| `property/` | Property-based tests (Hypothesis) over the invariants — frontmatter parsing, materialize round-trip, profile merge, path-safety, and operator settings entries surviving install, update, uninstall and rollback. |
| `fuzz/` | Atheris fuzz targets for the operator-file parsers (the JSONC / JSON5 reader, the hook-file merge, the profile loader, the install ledger, the frontmatter probe), their seed inputs, and `test_fuzz_seed_replay.py`, which replays every seed in the ordinary run. ClusterFuzzLite fuzzes them in CI (`.github/workflows/fuzzing.yml`); see [`fuzz/README.md`](fuzz/README.md). |
| `conformity-scenarios/` | End-to-end multi-mandate fixture scenarios (`F-*`) driven by `verify.py` and gated in CI by `.github/workflows/conformity.yml` — not collected by the default `pytest` run (see Running). |
| `fixtures/` | Shared cross-suite fixtures — the multi-surface-claims schema, the plans-discipline fixture, and the byte-golden `behavior-diff/` corpus — each with a paired schema/fixture test. |
| `_shared/` | Cross-subtree test helpers imported as `tests._shared`, not collected as tests. `bash_resolver.py` locates a usable POSIX `bash` (and refuses the Windows WSL launcher, which is not one), so the installer tests skip honestly on a host without it instead of failing. `git_env.py` builds the environment for a test's git subprocesses with the host's global, system and environment-carried git config switched off, so a developer's `gpg.format ssh`, `commit.gpgsign` or global hooks path cannot change a fixture repository. `python_shim.py` writes a `python3` shim that execs the interpreter running the test, so a script or hook command that names `python3` does not run the host's, which can lack the test's dependencies or be the Windows Store alias. `claude_rule_scope.py` restates two Claude Code rule behaviors for the rule tests: a `paths` list that scopes nothing (empty after a trailing `/**` is stripped, or `**` alone) loads the rule at launch, and a rule glob matches a path with `.gitignore` semantics. |

The `unit/` repo-coherence guards also include `test_no_hidden_bidi_controls.py`: it lists the tracked files with `git ls-files`, skips binary ones, and fails on any text file that holds a hidden bidirectional control (U+202A to U+202E, U+2066 to U+2069), naming its file, line, column and code point. The marks LRM, RLM and ALM stay allowed; a file that needs a control goes on the test's allowlist with its reason.

## Running

```sh
pytest
```

The configured `-n auto` parallelism is the default. On Python 3.14, the `pytest-xdist` worker capture interacts poorly with some output-capturing tests; run those with `pytest -n0 -s` to disable parallel workers and output capture when a 3.14 capture quirk surfaces.

The `conformity-scenarios/` subtree is **not** collected by `pytest` (it carries no `test_*.py` — only a `verify.py` runner plus `F-*` fixtures). It is gated in CI by `.github/workflows/conformity.yml`; run it locally with `python tests/conformity-scenarios/verify.py`.

## Conventions

- Test files mirror their source: `tests/<subtree>/test_<unit>.py` for the unit under test.
- Conformity self-tests follow the `pass` / `fail` fixture pattern where the matcher is fixture-driven.
- Markers are strict (`--strict-markers`) — every marker used is declared, or collection fails.
- Tests assert behavior over implementation, name the behavior in the test name, and never depend on test ordering (the suite runs in parallel).
- A test that builds a fixture git repository (init, config, commit, tag), or runs a script that does git work on one, SHOULD take the subprocess environment from `hermetic_git_env()` in `_shared/git_env.py`, so the host's git config cannot change the outcome.
- A test that runs a script or command naming `python3` SHOULD put a `write_python_shim()` shim from `_shared/python_shim.py` first on the subprocess PATH, so the host's `python3` cannot change the outcome.
- The root `tests/conftest.py` owns the suite-wide bootstrap: two `sys.path` inserts (`src/`, so `apothem` imports from a plain checkout with no editable install; and the repo root, so the helpers under `_shared/` resolve as `tests._shared` however pytest is invoked) plus the isolation of what an install or a hook writes outside the test's temporary folders: the user home itself (`HOME` and `USERPROFILE`), the install ledger (`install_ledger.STATE_ROOT`), the backup root (`install_driver.BACKUP_ROOT`), the Codex root (`CODEX_HOME`, cleared), the hook state folder (`APOTHEM_HOOK_STATE_DIR`, pointed at a temporary folder) and the XDG base directories (`XDG_CONFIG_HOME`, `XDG_STATE_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, cleared, so the code and the tools a test launches, such as `pwsh`, fall back to the temporary home). The ledger and backup roots are bound from `Path.home()` when their modules are imported, before any fixture runs, so redirecting `HOME` does not move them; the two variables place a write whatever `HOME` says. Each of these is therefore redirected twice: for the whole session, which covers module-, class- and package-scoped fixtures that run an install (pytest builds higher-scoped fixtures first), and again for every test. A session-scoped fixture that runs an install MUST request `_isolate_session_home` as a parameter, because pytest sets up session-scoped autouse fixtures in the order they were registered (a plugin's first, then a conftest's by name), not by intent. `unit/test_suite_state_isolation.py` pins the session-level redirect and fails on any other module-level path that still names the real home. The writes no fixture can catch (collection-time code, a plugin's session-scoped fixture) are audited by running pytest with `HOME` and `USERPROFILE` set to an empty folder and checking that nothing appears in it; the `home-isolation` job in `.github/workflows/ci.yml` does that for the whole suite whenever that workflow runs, with the XDG base directories on empty folders too. Per-subtree conftests carry only subtree-specific fixtures.

## Real-home guard

A test must never run Apothem against your real home folder. The isolation fixtures in `tests/conftest.py` move the home and Apothem's state folders into temporary folders, but their names start with `_`, and `from tests.conftest import *` skips such names. A probe folder whose conftest star-imported `tests/conftest.py` once ran an install and an uninstall against a developer's real home: it deleted a real install ledger and overwrote a file in `~/.config/apothem`.

`tests/conftest.py` therefore also holds a guard, the pytest hook `pytest_real_home_guard`. Its name has no leading `_`, so a star import carries it, and it runs wherever the conftest's names land. It wraps pytest's call of each test: it runs after every fixture of the test has been set up, and it fails the test before the body starts if any of these points at the real home or into its Apothem folders:

- the `HOME` and `USERPROFILE` variables and `Path.home()`;
- the user home the install manifest uses (`propagation.user_home()`);
- the data home (`~/.apothem`) and the profile and support folder (`~/.config/apothem`);
- the install ledger root (`install_ledger.STATE_ROOT`) and the backup root (`install_driver.BACKUP_ROOT`).

The real home is read once, when pytest imports `tests/conftest.py` and before any fixture changes it: `HOME`, `USERPROFILE`, `HOMEDRIVE` with `HOMEPATH`, `~` and, on Linux and macOS, the account's home. If a job points `HOME` at a temporary folder for the whole run, that folder is the real home. Other folders below the real home are allowed, because the Windows temporary folder, where every test's temporary home lives, is one of them. The failure message names each variable or path and the real location it reaches.

The guard does not see what a test body changes after it starts, what a fixture writes while it is set up or torn down, the environment a test builds for a child process, or a script that imports Apothem outside pytest. So:

- Never star-import a conftest.
- Put probes and experiments under `tests/`, so `tests/conftest.py` applies to them.
- Outside pytest, point `HOME` and `USERPROFILE` at a temporary folder before you import Apothem. Apothem sets its ledger and backup roots from the home when it is imported, so changing the home later does not move them.

`unit/test_real_home_guard.py` checks the guard. Its in-suite tests confirm that the guard wraps the call of a suite test and finds nothing there. It also runs a separate pytest session with the `pytester` plugin, in which each case writes a probe folder, points the home at a fresh folder that the probe session takes as the real home, and runs two probe tests, one with no fixture and one with `tmp_path`. A probe conftest that star-imports `tests/conftest.py` gets both tests stopped, and the file each test body writes first is never created. The same probes pass once their conftest gives them their own home and roots, or when `tests/conftest.py` is loaded as a plugin.

## Conformity corpus layout

The `conformity/` subtree holds two kinds of module. Per-matcher tests live in a
directory named for the matcher; top-level `test_*.py` files hold cross-matcher
infrastructure and scope-contract tests.

**Directory-name resolution.** The matcher-coverage loop
(`conformity/matcher-coverage/test_matcher_coverage_loop.py`) maps each matcher's
underscore module name to kebab-case and resolves its corpus directory by trying,
in order: the bare kebab form (`bare-except-grep`), the `<kebab>-grep` form, and —
for a name already ending in `-grep` — the suffix-stripped form. Most directories
carry the module's full kebab name; a few historical directories drop the `-grep`
suffix or diverge (`file-header`, `link-check`, `copilot-instructions-presence`),
which is why the resolver probes more than one candidate. Prefer the exact
`<module-kebab>` directory name for any new matcher so the mapping stays one-to-one.

**Fixture forms.** A matcher directory satisfies coverage with any one of three
equivalent fixture forms:

- a `test_*.py` scenario/contract test;
- a `pass.*` + `fail.*` content-file pair (a single conformant / non-conformant file each); or
- a `pass` + `fail` corpus-directory pair (a whole conformant / non-conformant tree, used by the standalone root-walking greps).

## Working in this folder

Add or modify a test in the subtree that mirrors the changed source, then run
`python -m pytest`. When a behavioral or public-surface change lands in the
package, the covering test ships in the **same change-set**. Conformity matcher
fixtures are also swept by the conformity gate itself:

```bash
python -m pytest
python -m apothem.conformity.gate --all .
```
