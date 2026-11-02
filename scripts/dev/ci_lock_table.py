# SPDX-License-Identifier: MIT

"""The table of hash-locked requirement files that ``refresh_ci_locks.py`` compiles.

CI installs its Python dependencies from the files in ``scripts/ci/`` with
``python -m pip install --require-hashes -r <lock>``. Each row of ``LOCKS`` is one
of those files: what it resolves, which Python it is compiled for and which
workflows install it. ``refresh_ci_locks.py`` reads the table and re-exports it,
and the tests under ``tests/scripts/`` hold the files and the workflows to it.

Two kinds of row:

* Project locks resolve ``pyproject.toml`` (``dev``, ``runtime``, ``test``) or the
  engine's host prerequisites (``prereqs``).
* Tool locks (``tool=True``) resolve one CI tool and its dependencies from an
  exact spec held here, so the tool version lives in one place and the workflow
  carries none.

``requirements-ci-pip.txt`` is not a row: Dependabot maintains it, and no other
lock may pin pip (``--no-emit-package pip`` keeps the closures free of it).

Every lock waits out the same cooldown as Dependabot's version updates.
Dependabot does not apply its cooldown to its security updates, and a row can do
the same for one package: ``cooldown_exceptions`` names a package and a UTC
timestamp, and the lock then takes that package's newest file uploaded before the
timestamp even when the cutoff is earlier. Use it for a release that fixes a
published advisory and is younger than the cutoff; the refresh refuses an
exception that the cutoff has passed, so the entry is removed once the cooldown
has caught up.

The module needs only the standard library, so it runs on Python 3.10.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CI_DIR = "scripts/ci"

# The oldest supported Python. The locks are universal (one file for every
# interpreter and platform from this version up) and keep the lines that older
# interpreters need. A tool that needs a newer Python sets its own floor.
PYTHON_FLOOR = "3.10"

# The header line that records one cooldown exception, and the timestamp format
# of an exception (a full UTC time, so a release from the lock date itself fits).
EXCEPTION_PREFIX = "# Cooldown exception: "
_EXCEPTION_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@dataclass(frozen=True)
class Lock:
    """One lock file: where it lands, what it resolves and who installs it."""

    filename: str
    purpose: str
    installed_by: str
    # Positional inputs for `uv pip compile`; "-" reads `stdin_requirements`.
    sources: tuple[str, ...]
    extras: tuple[str, ...] = ()
    stdin_requirements: tuple[str, ...] = ()
    # Why the lock exists beside the others, one sentence for the header.
    note: str = ""
    # `uv pip compile --python-version`: the oldest interpreter the lock serves.
    python_floor: str = PYTHON_FLOOR
    # True for a lock that resolves one CI tool from an exact spec in
    # `stdin_requirements`.
    tool: bool = False
    # (package, UTC timestamp) pairs: the lock takes that package's newest file
    # uploaded before the timestamp (`uv pip compile --exclude-newer-package`), even
    # when the cutoff, the lock date less the cooldown, is earlier. For a release
    # that fixes a published advisory and is younger than the cutoff. The timestamp
    # must be later than the cutoff, or uv would hold the package back to it, and
    # no later than the lock date (a time of day on that date for a fix uploaded
    # that day), or `--check` could not reproduce the lock.
    cooldown_exceptions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name, until in self.cooldown_exceptions:
            if not _EXCEPTION_TIMESTAMP_RE.match(until):
                raise ValueError(
                    f"{self.filename}: the cooldown exception for {name} needs a UTC "
                    f"timestamp like 2026-10-23T00:00:00Z, not {until!r}"
                )

    @property
    def relpath(self) -> str:
        return f"{CI_DIR}/{self.filename}"

    @property
    def exception_lines(self) -> list[str]:
        """The header lines that record this lock's cooldown exceptions."""
        return [
            f"{EXCEPTION_PREFIX}{name}, files uploaded before {until}"
            for name, until in self.cooldown_exceptions
        ]

    def stale_exceptions(self, cutoff: str) -> list[str]:
        """Return the packages whose exception ``cutoff`` has already passed.

        Such an exception lifts nothing, and uv would hold the package back to its
        timestamp, so the refresh refuses it. Timestamps compare as text because
        every one has the fixed format ``YYYY-MM-DDTHH:MM:SSZ``.
        """
        return [name for name, until in self.cooldown_exceptions if until <= cutoff]


# One row per lock. The test lock, the prerequisites lock and the tool locks read
# their requirements from stdin, so no `.in` file exists for Dependabot to find
# (Dependabot's pip support rewrites a universal lock for one platform when it
# finds a sibling `.in` file).
LOCKS: tuple[Lock, ...] = (
    Lock(
        filename="requirements-ci-dev.txt",
        purpose=(
            "the runtime dependencies and the dev extra of pyproject.toml "
            "(the set that `pip install -e .[dev]` resolves, held at the lock date)"
        ),
        installed_by=(
            "ci.yml (quality, coverage, release-preflight, metrics), "
            "harness-convention-monitor.yml, npm-audit.yml (tool-lockfile-tests) "
            "and, through reusable-python-setup.yml, ci-matrix.yml"
        ),
        sources=("pyproject.toml",),
        extras=("dev",),
    ),
    Lock(
        filename="requirements-ci-runtime.txt",
        purpose="the runtime dependencies of pyproject.toml, with no extras",
        installed_by=(
            "ci.yml (docs-build), clean-install-gate.yml (installer and shim smokes), "
            "docs-drift.yml, license-audit.yml and publish-static-site.yml"
        ),
        sources=("pyproject.toml",),
    ),
    Lock(
        filename="requirements-ci-test.txt",
        purpose=(
            "the runtime dependencies of pyproject.toml plus pytest, pytest-xdist "
            "and build"
        ),
        installed_by="clean-install-gate.yml (clean-install-gate and wheel-smoke)",
        sources=("pyproject.toml", "-"),
        stdin_requirements=("pytest", "pytest-xdist", "build"),
        note=(
            "Those jobs run the tests against src/ without installing the package, "
            "so they need the test tools but not the rest of the dev extra."
        ),
    ),
    Lock(
        filename="requirements-ci-prereqs.txt",
        purpose=(
            "the host prerequisites of the engine (click and rich), exactly as "
            "the installers pin them"
        ),
        installed_by="channel-smoke.yml",
        sources=("-",),
        stdin_requirements=("click==8.4.2", "rich>=15.0.0"),
        note=(
            "src/apothem/__main__.py (HOST_PREREQUISITES) and the installers pin "
            "these two specs and vendor every other runtime dependency, so the "
            "channel smoke installs only this closure and a broken vendored copy "
            "is not masked by a package in site-packages."
        ),
    ),
    Lock(
        filename="requirements-ci-ruff.txt",
        purpose="ruff, the linter and formatter, at the exact version of the dev extra",
        installed_by="conformity.yml (conformity-fixture-sweep)",
        sources=("-",),
        stdin_requirements=("ruff==0.17.1",),
        tool=True,
        note=(
            "ruff is pinned exactly in five places that must agree: the dev extra "
            "of pyproject.toml, the ruff-pre-commit rev in .pre-commit-config.yaml, "
            "the spec in scripts/dev/ci_lock_table.py, the dev lock and this lock; "
            "tests/scripts/test_ci_tool_locks.py fails when they differ. To move "
            "ruff, change the first three together, then refresh every lock."
        ),
    ),
    Lock(
        filename="requirements-ci-bandit.txt",
        purpose="bandit with its toml extra, the security linter, and its closure",
        installed_by="ci.yml (security-scan)",
        sources=("-",),
        stdin_requirements=("bandit[toml]==1.9.4",),
        tool=True,
        note=(
            "The security extra of pyproject.toml sets only a floor for "
            "contributors; CI runs the exact version below."
        ),
    ),
    Lock(
        filename="requirements-ci-pip-audit.txt",
        purpose="pip-audit, the vulnerability scanner, and its closure without pip",
        installed_by="ci.yml (supply-chain-scan) and pip-audit.yml",
        sources=("-",),
        stdin_requirements=("pip-audit==2.10.1",),
        tool=True,
        python_floor="3.11",
        note=(
            "pip is not in this file. requirements-ci-pip.txt installs it first and "
            "Dependabot keeps that pin current; a second pip pin here would replace "
            "it and escape Dependabot. The lock is compiled for Python 3.11 because "
            "filelock 4.1.0, the newest release that supports 3.10, has published "
            "advisories that only filelock 4.2.1, which needs 3.11 or later, fixes. "
            "The jobs that install it run Python 3.12."
        ),
    ),
    Lock(
        filename="requirements-ci-pip-licenses.txt",
        purpose="pip-licenses, the licence inventory tool, and its closure",
        installed_by="license-audit.yml",
        sources=("-",),
        stdin_requirements=("pip-licenses==5.5.5",),
        tool=True,
    ),
    Lock(
        filename="requirements-ci-pre-commit.txt",
        purpose="pre-commit, the hook runner, and its closure (Python 3.11 or later)",
        installed_by="markdown-lint.yml",
        sources=("-",),
        stdin_requirements=("pre-commit==4.7.0",),
        python_floor="3.11",
        tool=True,
        # virtualenv 21.14.12, the newest release before the 2026-10-22 cutoff, is
        # in GHSA-cx6f-vjhg-g3cc (high). 21.14.13 fixes it and was uploaded at
        # 2026-10-22T20:10Z. Dependabot's cooldown does not apply to its security
        # updates, so neither does this lock's for virtualenv. Delete the entry at
        # the first refresh whose cutoff passes the timestamp: the refresh says so.
        cooldown_exceptions=(("virtualenv", "2026-10-23T00:00:00Z"),),
        note=(
            "pre-commit 4.7.0 requires Python 3.11 or later, so this lock is "
            "compiled for 3.11 and does not install on Python 3.10. virtualenv is "
            "locked past the cutoff, as the Cooldown exception line below records: "
            "21.14.12, the newest release before it, is in GHSA-cx6f-vjhg-g3cc "
            "(high), which 21.14.13 fixes."
        ),
    ),
)


def lock_by_filename(filename: str) -> Lock:
    """Return the table row for ``filename``; raise ``KeyError`` when absent."""
    for lock in LOCKS:
        if lock.filename == filename:
            return lock
    raise KeyError(filename)
