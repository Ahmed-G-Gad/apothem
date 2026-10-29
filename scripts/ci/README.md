<!-- SPDX-License-Identifier: MIT -->

# CI requirements

Hash-locked requirement files that CI installs with `python -m pip install --require-hashes -r`. Each file pins its packages to exact versions and lists the SHA-256 of every distribution file, so pip refuses a download that does not match. The table below is the index: a file that is not listed here is documented nowhere.

## Files

| File | Purpose |
|------|---------|
| `requirements-ci-pip.txt` | The pip that CI upgrades to: one `pip==X.Y.Z` pin with the hashes of its wheel and sdist. Pip 26.2 or later fixes CVE-2026-13346, and `scripts/dev/check_pip_pin_drift.py` fails the build below that floor. Installed by every workflow that upgrades pip: `channel-smoke.yml`, `ci.yml`, `clean-install-gate.yml`, `conformity.yml`, `harness-convention-monitor.yml`, `license-audit.yml`, `markdown-lint.yml`, `npm-audit.yml`, `npm-shim.yml`, `pip-audit.yml` and `reusable-python-setup.yml`. `pip-audit.yml` also audits it weekly. |

## Why a hash-locked file

- Integrity: `--require-hashes` makes pip verify each download against the hashes in the file. pip checks hashes only when it downloads, so a runner that already has the locked version reports "Requirement already satisfied" and verifies nothing.
- Scorecard: OpenSSF Scorecard's Pinned-Dependencies check counts a `pip install` as pinned only when the command carries `--require-hashes` (or installs only `*.whl` files); an exact `==` pin without a hash is unpinned.

## Keeping the files current

Dependabot proposes the upgrades (`.github/dependabot.yml`, the `pip` entry for `/scripts/ci`: weekly, 7-day cooldown) and rewrites the version and the hashes together. A pull request that touches only this folder runs `ci.yml`, `conformity.yml`, `clean-install-gate.yml` and `pip-audit.yml`.

To regenerate a lock by hand, write the pin to a scratch file, compile it, and paste the output beneath the comment block at the top of the lock:

```bash
echo "pip==<version>" > /tmp/in.txt
uv pip compile /tmp/in.txt --generate-hashes --no-header --no-annotate -o /tmp/out.txt
```

Then run the checks before handoff:

```bash
python scripts/dev/check_pip_pin_drift.py
python -m pytest tests/scripts/test_check_pip_pin_drift.py tests/scripts/test_tool_lockfile_locations.py
```
