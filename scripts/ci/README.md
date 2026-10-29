<!-- SPDX-License-Identifier: MIT -->

# CI requirements

Hash-locked requirement files that CI installs with `python -m pip install --require-hashes -r`. Each file pins its packages to exact versions and lists the SHA-256 of every distribution file, so pip refuses a download that does not match. The table below is the index: a file that is not listed here is documented nowhere.

## Files

| File | Purpose |
|------|---------|
| `requirements-ci-pip.txt` | The pip that CI upgrades to: one `pip==X.Y.Z` pin with the hashes of its wheel and sdist. Pip 26.2 or later fixes CVE-2026-13346, and `scripts/dev/check_pip_pin_drift.py` fails the build below that floor. Installed by every workflow that upgrades pip: `channel-smoke.yml`, `ci.yml`, `clean-install-gate.yml`, `conformity.yml`, `harness-convention-monitor.yml`, `license-audit.yml`, `markdown-lint.yml`, `npm-audit.yml`, `npm-shim.yml`, `pip-audit.yml` and `reusable-python-setup.yml`. `pip-audit.yml` also audits it weekly. Dependabot maintains it. |
| `requirements-ci-dev.txt` | The runtime dependencies of `pyproject.toml` plus its `dev` extra, the set `pip install -e ".[dev]"` resolves, held at the lock date. Installed, followed by `python -m pip install --no-deps -e .`, by the `quality`, `coverage`, `release-preflight` and `metrics` jobs of `ci.yml`, by `harness-convention-monitor.yml`, by the `tool-lockfile-tests` job of `npm-audit.yml`, and, through `reusable-python-setup.yml`, by every cell of the `ci-matrix.yml` OS and Python matrix. |
| `requirements-ci-runtime.txt` | The runtime dependencies of `pyproject.toml` with no extras (`click`, `rich`, `pyyaml`, `jsonschema` and their closure). Installed by jobs that run the engine from `src/` without the package: the `docs-build` job of `ci.yml`, `docs-drift.yml`, `publish-static-site.yml`, `license-audit.yml` and the installer and shim smokes of `clean-install-gate.yml`. |
| `requirements-ci-test.txt` | The runtime dependencies plus `pytest`, `pytest-xdist` and `build`. Installed by the `clean-install-gate` and `wheel-smoke` jobs of `clean-install-gate.yml`, which run the tests against `src/` and build their own wheel. `pytest` and `pytest-xdist` pin to the same versions as in the dev lock. |
| `requirements-ci-prereqs.txt` | Only the host prerequisites of the engine, `click==8.4.2` and `rich>=15.0.0`, with their closure, exactly the specs the installers pin (`HOST_PREREQUISITES` in `src/apothem/__main__.py`). Installed by `channel-smoke.yml`. It is separate from the runtime lock because the engine vendors every other dependency, and an extra package in `site-packages` hides a broken vendored copy. |

## Why a hash-locked file

- Integrity: `--require-hashes` makes pip verify each download against the hashes in the file. pip checks hashes only when it downloads, so a runner that already has the locked version reports "Requirement already satisfied" and verifies nothing.
- Scorecard: OpenSSF Scorecard's Pinned-Dependencies check counts a `pip install` as pinned only when the command carries `--require-hashes`, installs a local path with `--no-deps -e`, or installs only `*.whl` files; an exact `==` pin without a hash is unpinned. `scripts/dev/check_pip_pin_drift.py` (rule d) holds every workflow `pip install` to that definition.

## What CI tests

CI installs the versions in these files, not the newest release on the day of the run. Each file records `Locked as of:` (a UTC timestamp) and the uv version that wrote it. The lock holds only files uploaded before that date, so a release newer than the date is not tested until the next refresh. `pip-audit.yml` keeps the early warning: it resolves `.[dev]` to the newest allowed versions each week and audits that tree, and it audits the four locks as well.

Each lock is one universal file for Python 3.10 and later on Linux, macOS and Windows. A line that carries an environment marker (for example `colorama==0.4.6 ; os_name == 'nt' or sys_platform == 'win32'`) applies only where the marker is true. Every package carries the hashes of all its files, wheels and sdist, so the advisory Python 3.15 cell, where PyYAML publishes no wheel yet, builds that package from its hashed sdist; pip prefers a wheel wherever one exists. The package `build-system` requirement (`setuptools==84.1.0`) is not hashed: `--no-deps -e .` still fetches it through pip's isolated build environment.

## Keeping the files current

The four dependency locks are closures: regenerate them whole, never edit a pin by hand. `.github/dependabot.yml` limits its `/scripts/ci` entry to `pip`, so Dependabot proposes only the pip lock. A Dependabot alert against a locked package is answered by regenerating.

```bash
# Regenerate every dependency lock (needs uv on PATH and network access).
# Run it weekly and whenever pyproject.toml changes a dependency.
python scripts/dev/refresh_ci_locks.py
# Pick the lock date yourself (only files uploaded before it are used):
python scripts/dev/refresh_ci_locks.py --date 2026-10-29
# Compile again with each file's recorded date and fail on any difference.
python scripts/dev/refresh_ci_locks.py --check
```

`--check` needs uv and network access, so it is an operator command and does not run in required CI. `tests/scripts/test_ci_locks_fresh.py` runs offline and fails when a lock no longer satisfies `pyproject.toml` (for example after a floor is raised): it evaluates each file's markers for Python 3.10 to 3.14 on Linux, macOS and Windows.

`requirements-ci-pip.txt` stays a Dependabot file. To regenerate it by hand, write the pin to a scratch file, compile it, and paste the output beneath the comment block at the top of the lock:

```bash
echo "pip==<version>" > /tmp/in.txt
uv pip compile /tmp/in.txt --generate-hashes --no-header --no-annotate -o /tmp/out.txt
```

Commit no `.in` file in this folder: Dependabot's pip support would rewrite a universal lock for one platform when it finds a sibling `.in` file. The inputs of each dependency lock live in the table in `scripts/dev/refresh_ci_locks.py`.

A pull request that touches only this folder runs `ci.yml` (its `scripts/**` filter), `conformity.yml`, `clean-install-gate.yml` and `pip-audit.yml`; `ci-matrix.yml` runs for a change to `requirements-ci-dev.txt`, `license-audit.yml` and `docs-drift.yml` for `requirements-ci-runtime.txt`, and `channel-smoke.yml` for `requirements-ci-prereqs.txt`.

Then run the checks before handoff:

```bash
python scripts/dev/check_pip_pin_drift.py
python -m pytest tests/scripts/test_check_pip_pin_drift.py tests/scripts/test_ci_locks_fresh.py tests/scripts/test_refresh_ci_locks.py tests/scripts/test_tool_lockfile_locations.py
```
