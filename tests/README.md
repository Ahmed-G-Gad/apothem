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
- The root `tests/conftest.py` owns the suite-wide bootstrap: two `sys.path` inserts (`src/`, so `apothem` imports from a plain checkout with no editable install; and the repo root, so the helpers under `_shared/` resolve as `tests._shared` however pytest is invoked) plus the isolation of what an install or a hook writes outside the test's temporary folders: the user home itself (`HOME` and `USERPROFILE`), the install ledger (`install_ledger.STATE_ROOT`), the backup root (`install_driver.BACKUP_ROOT`), the Codex root (`CODEX_HOME`, cleared), the Claude Code folder (`CLAUDE_CONFIG_DIR`, cleared), the hook state folder (`APOTHEM_HOOK_STATE_DIR`, pointed at a temporary folder) and the XDG base directories (`XDG_CONFIG_HOME`, `XDG_STATE_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, cleared, so the code and the tools a test launches, such as `pwsh`, fall back to the temporary home). The ledger and backup roots are bound from `Path.home()` when their modules are imported, before any fixture runs, so redirecting `HOME` does not move them; the three variables place a write or a read whatever `HOME` says. Each of these is therefore redirected twice: for the whole session, which covers module-, class- and package-scoped fixtures that run an install (pytest builds higher-scoped fixtures first), and again for every test. A session-scoped fixture that runs an install MUST request `_isolate_session_home` as a parameter, because pytest sets up session-scoped autouse fixtures in the order they were registered (a plugin's first, then a conftest's by name), not by intent. `unit/test_suite_state_isolation.py` pins the session-level redirect and fails on any other module-level path that still names the real home. The writes no fixture can catch (collection-time code, a plugin's session-scoped fixture) are audited by running pytest with `HOME` and `USERPROFILE` set to an empty folder and checking that nothing appears in it; the `home-isolation` job in `.github/workflows/ci.yml` does that for the whole suite whenever that workflow runs, with the XDG base directories on empty folders too. Per-subtree conftests carry only subtree-specific fixtures.

## Real-home guard

A test must never run Apothem against your real home folder. The isolation fixtures in `tests/conftest.py` move the home and Apothem's state folders into temporary folders, and their names start with `_`. A probe folder whose conftest star-imported `tests/conftest.py`, at a time when a star import skipped those names, once ran an install and an uninstall against a developer's real home: it deleted a real install ledger and overwrote a file in `~/.config/apothem`.

Two things in `tests/conftest.py` now stop that:

- **`__all__`.** It lists the isolation fixtures, the guard's names and the other public names, so `from tests.conftest import *` brings the isolation with it.
- **The guard, `real_home_guard`.** Importing `tests/conftest.py` inside a pytest session registers this plugin object with that session, however the import is written: pytest loading the file as a conftest, `-p tests.conftest`, a star import, or a conftest that imports single names, such as two isolation fixtures and no guard name. It is registered once per session, as `apothem-real-home-guard`, and pytest calls its hooks on the object, so deleting or rebinding a name in a conftest does not remove it. If the file was imported before the session started, the `pytest_configure` hook `pytest_register_real_home_guard`, which a star import carries, registers it instead. Its hooks:
  - **Setup.** It runs first when pytest sets up a test, before any fixture, and fails the test when `_isolate_session_home`, `_isolate_user_home`, `_isolate_install_ledger` or `_isolate_backup_root` does not apply to it, whichever import brought the others in. It also fails the test when `_isolate_session_home` is a fixture of the same name from somewhere else, and when a session-scoped fixture would be set up before `_isolate_session_home` without requesting it: pytest sets up session-scoped autouse fixtures in the order they were registered (a `-p` plugin's, then a parent conftest's, then a conftest's own by name), so a fixture named `_install_x` would run first, against the real home. The test's own fixtures then never run, so they cannot write to the real home while they are set up, and the same holds under `--setup-only`. The message names the missing fixtures or the fixture that would run too early. Fixtures of a plugin installed as a package are not checked for their order.
  - **Call.** It runs after every fixture of the test is set up, after every `pytest_runtest_call` hook and every `pytest_pyfunc_call` wrapper has started, including those of a conftest that imported the file and of a plugin registered before it, right before pytest calls the test function. A `unittest` case or a doctest is checked in `pytest_runtest_call` instead, right before pytest runs it. It fails the test before the body starts if any of these points at the real home or at a real folder in it:
    - the `HOME` and `USERPROFILE` variables and `Path.home()`;
    - the user home the install manifest uses (`propagation.user_home()`);
    - the data home (`~/.apothem`) and the profile and support folder (`~/.config/apothem`);
    - the install ledger root (`install_ledger.STATE_ROOT`) and the backup root (`install_driver.BACKUP_ROOT`);
    - `CODEX_HOME`, `CLAUDE_CONFIG_DIR` and `XDG_CONFIG_HOME`, which move the Codex home, the Claude Code folder and the OpenCode folder;
    - the hook state folder, which falls back to `LOCALAPPDATA` on Windows when `APOTHEM_HOOK_STATE_DIR` is unset, and `CLAUDE_PLUGIN_DATA` or `XDG_STATE_HOME` when it builds that folder.
  - **Report.** A test the guard stopped stays failed when it is marked `xfail`. Without this, pytest would report it as XFAIL and the run would pass.

The guard reads the real home once, when pytest imports `tests/conftest.py` and before any fixture changes it: `HOME`, `USERPROFILE`, `HOMEDRIVE` with `HOMEPATH`, `~` and, on Linux and macOS, the account's home. If a job points `HOME` at a temporary folder for the whole run, that folder is the real home. The real folders are the home's `.apothem`, `.config/apothem`, `.local/state/apothem`, `.codex`, `.claude` and `.config` folders, the folders that `CODEX_HOME`, `CLAUDE_CONFIG_DIR` and `XDG_CONFIG_HOME` named at that moment, and the `apothem` folder in `XDG_STATE_HOME` and in `LOCALAPPDATA`. Other folders below the real home are allowed, because the Windows temporary folder, where every test's temporary home lives, is one of them. `LOCALAPPDATA` itself is allowed for the same reason: every test inherits it, and the temporary folder is inside it. The failure message names each variable or path and the real location it reaches.

The isolation clears `CODEX_HOME` and `CLAUDE_CONFIG_DIR` for every test, so a developer's own setting does not stop the suite.

The guard does not catch:

- writes made outside a test's setup and call: while a conftest is imported, during collection, in a setup hook of a conftest's own that runs before the guard's or between it and the fixtures, in a session-scoped fixture of a plugin installed as a package, and in a fixture's teardown after it undoes the isolation;
- what a test body changes after it starts, including a fixture it requests with `request.getfixturevalue`, and the environment it builds for a child process; and a conftest's own plain `pytest_pyfunc_call` that calls the test itself;
- a fixture that a conftest defines under `_isolate_user_home`, `_isolate_install_ledger` or `_isolate_backup_root` (one suite test replaces `_isolate_backup_root` on purpose): the setup check sees the name and passes, and the call check sees only what that fixture left;
- a run with `--noconftest`, which loads neither the isolation nor the guard; a run with `-p no:apothem-real-home-guard`, which turns the guard off; and a conftest that imports single names from `tests/conftest.py` after an earlier import in the same process, in an earlier pytest session (a script that calls `pytest.main` twice) or outside pytest, which registers nothing;
- the folders it does not compare: harness folders in a home other than `.codex`, `.claude` and `.config` (such as `.cursor`, `.gemini` or `.agents`), whether a test passes one as its own install root or `CODEX_HOME` or `XDG_CONFIG_HOME` points at one; `XDG_DATA_HOME` and `XDG_CACHE_HOME`, which Apothem does not read but the tools a test launches do; `OPENCODE_CONFIG_DIR`, which only adds an install note; and `APOTHEM_HOOK_STATE_DIR`, which counts only through the hook state folder it names;
- a script that imports Apothem outside pytest.

So:

- Never star-import a conftest.
- Put probes and experiments under `tests/`, so `tests/conftest.py` applies to them.
- Outside pytest, point `HOME` and `USERPROFILE` at a temporary folder before you import Apothem. Apothem sets its ledger and backup roots from the home when it is imported, so changing the home later does not move them.

`unit/test_real_home_guard.py` checks the guard. Its in-suite tests confirm that the import registered one guard object, that its setup hook runs before pytest's, that its call hooks run before pytest's own (`pytest_pyfunc_call` right before the function is called), that its report hook wraps the `skipping` plugin's, that `__all__` carries the isolation and the guard, and that the call check finds nothing for a suite test. It also runs a separate pytest session with the `pytester` plugin, in which each case writes a probe folder, points the home and `LOCALAPPDATA` at fresh folders that the probe session takes as the real ones, and runs two probe tests, one with no fixture and one with `tmp_path`. A probe conftest that star-imports `tests/conftest.py` runs both tests. A probe conftest that imports one plain name, or two isolation fixtures by name, is stopped at setup, with or without `--setup-only` and with or without `xfail`, and neither its own fixtures nor the test bodies write the file each writes first; so is a star-importing one with a session-scoped fixture named to run before `_isolate_session_home` (one that requests it runs), or with a fixture of its own named `_isolate_session_home`. A fixture that puts the real home, the ledger and backup roots, `CODEX_HOME`, `CLAUDE_CONFIG_DIR`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME` or `CLAUDE_PLUGIN_DATA` for the hook state, or, on Windows, `LOCALAPPDATA` for the hook state back on a real location gets both tests stopped before their bodies, and so do a conftest that deletes the guard's names, a later `pytest_runtest_call` or `pytest_pyfunc_call` wrapper that puts the real home back, an `xfail` mark (reported as failed), and a session that imported the file before it started.

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
