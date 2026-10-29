<!-- SPDX-License-Identifier: MIT -->

# CI requirements

Hash-locked requirement files that CI installs with `python -m pip install --require-hashes -r`. Each file pins its packages to exact versions and lists the SHA-256 of every distribution file, so pip refuses a download that does not match. The table below is the index: a file that is not listed here is documented nowhere.

## Files

| File | Purpose |
|------|---------|
| `requirements-ci-pip.txt` | The pip that CI upgrades to: one `pip==X.Y.Z` pin with the hashes of its wheel and sdist. Pip 26.2 or later fixes CVE-2026-13346, and `scripts/dev/check_pip_pin_drift.py` fails the build below that floor. Installed by every workflow that upgrades pip: `channel-smoke.yml`, `ci.yml`, `clean-install-gate.yml`, `conformity.yml`, `harness-convention-monitor.yml`, `license-audit.yml`, `markdown-lint.yml`, `npm-audit.yml`, `npm-shim.yml`, `pip-audit.yml` and `reusable-python-setup.yml`. `pip-audit.yml` also audits it weekly. Dependabot maintains it, and no other file in this folder pins pip. |
| `requirements-ci-dev.txt` | The runtime dependencies of `pyproject.toml` plus its `dev` extra, the set `pip install -e ".[dev]"` resolves, held at the lock date. Installed, followed by `python -m pip install --no-deps -e .`, by the `quality`, `coverage`, `release-preflight` and `metrics` jobs of `ci.yml`, by `harness-convention-monitor.yml`, by the `tool-lockfile-tests` job of `npm-audit.yml`, and, through `reusable-python-setup.yml`, by every cell of the `ci-matrix.yml` OS and Python matrix. |
| `requirements-ci-runtime.txt` | The runtime dependencies of `pyproject.toml` with no extras (`click`, `rich`, `pyyaml`, `jsonschema` and their closure). Installed by jobs that run the engine from `src/` without the package: the `docs-build` job of `ci.yml`, `docs-drift.yml`, `publish-static-site.yml`, `license-audit.yml` and the installer and shim smokes of `clean-install-gate.yml`. |
| `requirements-ci-test.txt` | The runtime dependencies plus `pytest`, `pytest-xdist` and `build`. Installed by the `clean-install-gate` and `wheel-smoke` jobs of `clean-install-gate.yml`, which run the tests against `src/` and build their own wheel. `pytest` and `pytest-xdist` pin to the same versions as in the dev lock. |
| `requirements-ci-prereqs.txt` | Only the host prerequisites of the engine, `click==8.4.2` and `rich>=15.0.0`, with their closure, exactly the specs the installers pin (`HOST_PREREQUISITES` in `src/apothem/__main__.py`). Installed by `channel-smoke.yml`. It is separate from the runtime lock because the engine vendors every other dependency, and an extra package in `site-packages` hides a broken vendored copy. |
| `requirements-ci-ruff.txt` | `ruff` alone, at the exact version the `dev` extra of `pyproject.toml` pins. Installed by `conformity.yml`. The `ruff-pre-commit` rev in `.pre-commit-config.yaml` and the dev lock carry the same version (see Bumping ruff). |
| `requirements-ci-bandit.txt` | `bandit[toml]` and its closure. Installed by the `security-scan` job of `ci.yml`. The `security` extra of `pyproject.toml` stays a floor for contributors. |
| `requirements-ci-pip-audit.txt` | `pip-audit` and its closure, without pip, compiled for Python 3.11 or later (see Why the pip-audit lock starts at Python 3.11). Installed by the `supply-chain-scan` job of `ci.yml` and by `pip-audit.yml`, both on Python 3.12, after the pip lock, so `pip-audit --desc` in `ci.yml` audits that pip and this closure. |
| `requirements-ci-pip-licenses.txt` | `pip-licenses` and its closure. Installed by `license-audit.yml`, before the runtime lock. |
| `requirements-ci-pre-commit.txt` | `pre-commit` and its closure, compiled for Python 3.11 or later because pre-commit 4.7.0 does not support 3.10. Installed by `markdown-lint.yml`, which runs Python 3.12. It carries a cooldown exception for `virtualenv` (see Cooldown exceptions). |

The version of each tool is the spec in the table in `scripts/dev/ci_lock_table.py`, and no workflow spells a tool version. The four dependency locks and the five tool locks together are the nine files `scripts/dev/refresh_ci_locks.py` writes.

## Why a hash-locked file

- Integrity: `--require-hashes` makes pip verify each download against the hashes in the file. pip checks hashes only when it downloads, so a runner that already has the locked version reports "Requirement already satisfied" and verifies nothing.
- Scorecard: OpenSSF Scorecard's Pinned-Dependencies check counts a `pip install` as pinned only when the command carries `--require-hashes`, installs a local path with `--no-deps -e`, or installs only `*.whl` files; an exact `==` pin without a hash is unpinned. `scripts/dev/check_pip_pin_drift.py` (rule d) holds every workflow `pip install` to that definition, so a tool installed as `pip install ruff==X` fails the build.
- One pip pin: every lock is compiled with `--no-emit-package pip`. pip-audit depends on `pip-api`, which depends on pip, so without the flag the pip-audit lock would pin a second pip and replace the one in `requirements-ci-pip.txt` on install, outside Dependabot's reach. `tests/scripts/test_ci_locks_fresh.py` fails when any lock but the pip lock pins pip.

## What CI tests

CI installs the versions in these files, not the newest release on the day of the run. Each file records:

- `Locked as of:` the lock date, a UTC timestamp.
- `Cooldown:` the days a release must be public before it is locked, 7 unless the refresh passed `--cooldown-days`. It matches the 7-day cooldown in `.github/dependabot.yml`, so a release that Dependabot would not yet propose is not locked either.
- `Cutoff:` the lock date less the cooldown, the timestamp handed to uv as `--exclude-newer`.
- `Cooldown exception:` one line per package that the lock takes past the cutoff (see Cooldown exceptions). Most locks have none.
- `Compiled with:` the uv version that wrote the file.

A lock holds only files uploaded before the cutoff, so a release younger than the cooldown is not tested until a later refresh. All nine locks share one lock date and one cutoff.

`pip-audit.yml` keeps the early warning: it resolves `.[dev]` to the newest allowed versions each week and audits that tree, and it audits the nine locks and the pip lock as well. Every audit asks the OSV service (`pip-audit -s osv`) and not pip-audit's default PyPI feed, because that feed lists an advisory later than GitHub does: on 2026-10-29 it still showed none for `virtualenv` 21.14.12, which GHSA-cx6f-vjhg-g3cc (high) covers. Dependabot alerts, Dependency review and the Scorecard Vulnerabilities check read the GitHub advisories. The `supply-chain-scan` job of `ci.yml` keeps the default feed, so it fails a pull request only for an advisory that PyPI lists.

The audits run on Python 3.12 only. `pip-audit --disable-pip` skips a line whose environment marker is false on the runner, so the lines that apply only below Python 3.11 (`exceptiongroup`, `hypothesis`, `rpds-py`, `stevedore` and `tomli` today) are not audited there. Dependabot alerts, Dependency review and Scorecard still read them. Three of those pins are the last releases that support Python 3.10 (`hypothesis`, `rpds-py`, `stevedore`), so an advisory that only a release for 3.11 or later fixes has no remedy in the lock short of dropping Python 3.10, which is past its upstream end of life (October 2026) but still a supported floor of the project.

Each lock is one universal file for Python 3.10 and later (3.11 and later for the pip-audit and pre-commit locks) on Linux, macOS and Windows. A line that carries an environment marker (for example `colorama==0.4.6 ; os_name == 'nt' or sys_platform == 'win32'`) applies only where the marker is true. Every package carries the hashes of all its files, wheels and sdist, so the advisory Python 3.15 cell, where PyYAML publishes no wheel yet, builds that package from its hashed sdist; pip prefers a wheel wherever one exists. The package `build-system` requirement (`setuptools==84.1.0`) is not hashed: `--no-deps -e .` still fetches it through pip's isolated build environment.

### Why the pip-audit lock starts at Python 3.11

Compiled for Python 3.10, the pip-audit lock pinned `filelock==4.1.0` below 3.11, the newest release that supports 3.10. It has 17 published advisories (on 2026-10-29, the most severe GHSA-v4x8-3wr5-3wq8), and `filelock` 4.2.1, which fixes them, needs Python 3.11 or later. A scanner reads that line whatever its environment marker says, so Dependency review and Scorecard would have reported it for a package that the lock never installs on a current Python. The lock is therefore compiled for 3.11 (`python_floor` in the table), and both jobs that install it run Python 3.12.

## Keeping the files current

The nine locks are closures: regenerate them whole, never edit a pin by hand. `.github/dependabot.yml` limits its `/scripts/ci` entry to the dependency named `pip`, so Dependabot proposes only the pip lock. A Dependabot alert against a locked package is answered by regenerating.

```bash
# Regenerate every lock (needs uv on PATH and network access).
# Run it weekly and whenever pyproject.toml changes a dependency.
python scripts/dev/refresh_ci_locks.py
# Pick the lock date yourself (the cutoff is that date less the cooldown):
python scripts/dev/refresh_ci_locks.py --date 2026-10-29
# Change the cooldown. 0 locks every file uploaded before 00:00 UTC of the lock date,
# for an urgent security fix.
python scripts/dev/refresh_ci_locks.py --cooldown-days 0
# Compile again with each file's recorded cutoff and fail on any difference.
python scripts/dev/refresh_ci_locks.py --check
```

`--check` needs uv and network access, so it is an operator command and does not run in required CI. It also fails on a header whose cutoff is not its lock date less its cooldown, or whose `Cooldown exception:` lines differ from the table. `--date` and `--cooldown-days` do not apply to `--check`, which reads the dates each file records. `tests/scripts/test_ci_locks_fresh.py` runs offline and fails when a lock no longer satisfies its inputs (for example after a floor in `pyproject.toml` is raised or a tool spec changes): it evaluates each file's markers for Python 3.10 to 3.15 on Linux, macOS and Windows.

Before committing a refresh, audit every lock the way the weekly run does, with Python 3.11 or later. The cooldown can lock a version whose fix is younger than the cutoff, and pip-audit's default PyPI feed lists an advisory later than GitHub does, so name the OSV service:

```bash
for lock in scripts/ci/requirements-ci-*.txt; do
  pip-audit -s osv --desc --disable-pip -r "$lock"
done
```

The seven-day cooldown has a cost: a fix released in the last week is not in the locks, and `pip-audit.yml` fails when OSV lists an advisory against a locked package that only a newer release fixes. Cooldown exceptions, below, are the two ways to lock such a fix.

`requirements-ci-pip.txt` stays a Dependabot file. To regenerate it by hand, write the pin to a scratch file, compile it, and paste the output beneath the comment block at the top of the lock:

```bash
echo "pip==<version>" > /tmp/in.txt
uv pip compile /tmp/in.txt --generate-hashes --no-header --no-annotate -o /tmp/out.txt
```

Commit no `.in` file in this folder: Dependabot's pip support would rewrite a universal lock for one platform when it finds a sibling `.in` file. The inputs of each lock live in the table in `scripts/dev/ci_lock_table.py`.

A pull request that touches only this folder runs `ci.yml` (its `scripts/**` filter), `conformity.yml`, `clean-install-gate.yml` and `pip-audit.yml`; `ci-matrix.yml` runs for a change to `requirements-ci-dev.txt`, `license-audit.yml` for `requirements-ci-runtime.txt` or `requirements-ci-pip-licenses.txt`, `docs-drift.yml` for `requirements-ci-runtime.txt`, `markdown-lint.yml` for `requirements-ci-pre-commit.txt`, and `channel-smoke.yml` for `requirements-ci-prereqs.txt`.

Then run the checks before handoff:

```bash
python scripts/dev/check_pip_pin_drift.py
python -m pytest tests/scripts/test_check_pip_pin_drift.py tests/scripts/test_ci_locks_fresh.py tests/scripts/test_ci_tool_locks.py tests/scripts/test_refresh_ci_locks.py tests/scripts/test_refresh_ci_locks_run.py tests/scripts/test_tool_lockfile_locations.py
```

### Cooldown exceptions

Dependabot's cooldown does not apply to its security updates, and the locks follow that rule in two ways:

- **For one package**, add a `cooldown_exceptions` entry to the lock's row in `scripts/dev/ci_lock_table.py`: the package name and a UTC timestamp after the fix was uploaded, such as `("virtualenv", "2026-10-23T00:00:00Z")`, then run the refresh. That package takes the newest file uploaded before the timestamp, every other pin stays at the cutoff, and the lock header records a `Cooldown exception:` line. The pre-commit lock carries one today: `virtualenv` 21.14.12, the newest release before the cutoff, is in GHSA-cx6f-vjhg-g3cc (high), and 21.14.13 fixes it. The refresh refuses an entry once the cutoff has reached its timestamp, because uv would then hold the package back to it; delete the entry when it does.
- **For every package**, run `python scripts/dev/refresh_ci_locks.py --cooldown-days 0`. It locks every file uploaded before 00:00 UTC of the lock date, so every pin moves to its newest release: commit it only when that is acceptable, and the next default refresh moves back to the cooldown. A fix uploaded on the lock date itself is not in that set; give it a `cooldown_exceptions` entry with a time of day on the lock date after its upload, such as `2026-10-29T14:30:00Z`, not the next midnight: an exception may not name a time after the refresh, or `--check` could not reproduce the lock.

A tool pin or the ruff pin that names a release younger than the cooldown cannot resolve either: uv reports no solution, and the script says to wait, to use `--cooldown-days 0` or to add an exception.

### Bumping ruff

ruff is pinned exactly in five places, and `tests/scripts/test_ci_tool_locks.py` fails until all of them agree:

1. the `dev` extra of `pyproject.toml` (`ruff==X.Y.Z`);
2. the `astral-sh/ruff-pre-commit` rev in `.pre-commit-config.yaml` (`vX.Y.Z`, a tag that must exist);
3. the ruff row of the table in `scripts/dev/ci_lock_table.py`;
4. `requirements-ci-ruff.txt` and `requirements-ci-dev.txt`, which `python scripts/dev/refresh_ci_locks.py` writes.

To move ruff, edit 1 to 3 together and run the refresh. X.Y.Z must be older than the cooldown on the lock date, or the ruff row and the dev row of the table must each carry a cooldown exception for ruff, because both locks pin it. Dependabot leaves the hook alone, and a Dependabot security pull request for ruff edits only `pyproject.toml`, so apply 2 and 3 and the refresh on its branch. Run `ruff check .` and `ruff format --check .` at the new version before the refresh.

To move another tool, change its spec in the table and refresh. `pre-commit` needs Python 3.11 or later: its row sets `python_floor`, and `markdown-lint.yml` must keep a Python at or above it.
