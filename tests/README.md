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
| `unit/` | Per-module unit tests — the harness adapters (one per registered harness in the 17-harness cohort), the CLI surface, the harness materializer, the conformity-gate scope, the parallel sweep, the propagation manifest — **plus a repo-coherence-guard class**: cross-surface drift guards (`test_harness_registry.py` against `site/app/page.tsx` + `pyproject.toml`, `test_citation_cff.py`, `test_example_settings_sync.py`, `test_assets_manifest_coverage.py`, `test_guard_wiring_coherence.py`) and the `unit/docs/` subtree, which validates the docs-site frontmatter examples against the conformity contract. |
| `integration/` | Cross-component integration tests — multi-harness parity, the hermetic clean-machine installer gate, installer tag-verification aborts, clean-slate install, the rollback CLI, the install-ledger acceptance matrix, memory portability / isolation, the self-contained vendored runtime, and the byte-golden behavior-diff walls (CLI + install-driver). |
| `conformity/` | Per-validator self-tests. Most matchers own a directory named for the matcher's kebab module (`hedging-grep`, `secret-leak-grep`, `magic-number-grep`, `bare-except-grep`, `binding-reciprocity-grep`, `unpinned-action-grep`, and more) carrying `pass` / `fail` fixtures or scenario tests; a set of top-level `test_*.py` files hold cross-matcher infrastructure and scope-contract tests (the corpus per-write runner, the matcher-coverage loop, the standalone-grep in-process sweep). See [Conformity corpus layout](#conformity-corpus-layout) for the directory-name resolution rules. |
| `hooks/` | Hook-infrastructure tests — the dispatcher, hook-context emission, the session-start bootstrap, the interpreter locator, the header-inject guard, and the plan-write guard. |
| `scripts/` | Tests for the executables under [`scripts/`](../scripts/) — the header injector, the installer invocation model, the release-notes extractor, the SBOM recipe, script-pair parity, and the validation tooling. |
| `packaging/` | Release-artifact packaging tests — sdist + wheel payload contract, runtime tarball/zip build, examples validity. |
| `commands/` | Slash-command behavior tests (e.g., `plan-spec-quick`). |
| `property/` | Property-based tests (Hypothesis) over the invariants — frontmatter parsing, materialize round-trip, profile merge, path-safety, and operator settings entries surviving install, update, uninstall and rollback. |
| `conformity-scenarios/` | End-to-end multi-mandate fixture scenarios (`F-*`) driven by `verify.py` and gated in CI by `.github/workflows/conformity.yml` — not collected by the default `pytest` run (see Running). |
| `fixtures/` | Shared cross-suite fixtures — the multi-surface-claims schema, the plans-discipline fixture, and the byte-golden `behavior-diff/` corpus — each with a paired schema/fixture test. |
| `_shared/` | Cross-subtree test helpers imported as `tests._shared`, not collected as tests. `bash_resolver.py` locates a usable POSIX `bash` (and refuses the Windows WSL launcher, which is not one), so the installer tests skip honestly on a host without it instead of failing. `git_env.py` builds the environment for a test's git subprocesses with the host's global, system and environment-carried git config switched off, so a developer's `gpg.format ssh`, `commit.gpgsign` or global hooks path cannot change a fixture repository. |

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
- The root `tests/conftest.py` owns the suite-wide bootstrap: two `sys.path` inserts (`src/`, so `apothem` imports from a plain checkout with no editable install; and the repo root, so the helpers under `_shared/` resolve as `tests._shared` however pytest is invoked) plus two autouse isolations — the install ledger and the backup root, both of which default under the developer's real home and would otherwise be written there by any test that installs. Per-subtree conftests carry only subtree-specific fixtures.

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
