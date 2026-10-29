# SPDX-License-Identifier: MIT

"""Regenerate, or verify, the hash-locked requirement files CI installs.

CI installs its Python dependencies from the files in ``scripts/ci/`` with
``python -m pip install --require-hashes -r <lock>``. OpenSSF Scorecard counts a
``pip install`` as pinned only when it carries ``--require-hashes``, and a
hash-locked file also makes pip verify every download. The files are produced by
``uv pip compile`` from ``pyproject.toml`` and are never edited by hand.

Default mode compiles every lock against the package index as of a lock date
(today at 00:00 UTC unless ``--date`` names another day) and rewrites the files.
Run it weekly and whenever ``pyproject.toml`` changes a dependency. ``--check``
compiles every lock again in a temporary directory, with the date recorded in
the committed file, and exits 1 with a summary of the differing packages when a
committed file does not match. ``--check`` needs uv and network access, so it is
an operator command and does not run in the required CI jobs.
``tests/scripts/test_ci_locks_fresh.py`` is the offline test that holds each
lock to ``pyproject.toml``.

Each lock records ``Locked as of:`` (the ``--exclude-newer`` timestamp) and the
uv version that wrote it. A different uv version can normalise environment
markers differently, so ``--check`` compares the requirement lines only and says
when the uv version differs.

The script needs only the standard library and ``uv`` on ``PATH``.

Exit codes: 0 success (or every lock matches under ``--check``), 1 a lock
differs under ``--check`` or a compile failed, 2 a usage error (uv missing,
bad date).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
CI_DIR = "scripts/ci"
SCRIPT_RELPATH = "scripts/dev/refresh_ci_locks.py"

# The oldest supported Python. The locks are universal (one file for every
# interpreter and platform) and keep the lines that older interpreters need.
PYTHON_FLOOR = "3.10"

_SPDX = "SPDX-License-" + "Identifier: MIT"
_LOCKED_AS_OF_PREFIX = "# Locked as of: "
_UV_PREFIX = "# Compiled with: uv "
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T00:00:00Z$")
_UV_VERSION_RE = re.compile(r"^uv (?P<version>\S+)")


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

    @property
    def relpath(self) -> str:
        return f"{CI_DIR}/{self.filename}"


# One row per lock. The test lock reads its extra requirements from stdin, so no
# `.in` file exists for Dependabot to find (Dependabot's pip support rewrites a
# universal lock for one platform when it finds a sibling `.in` file).
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
)


def lock_by_filename(filename: str) -> Lock:
    """Return the table row for ``filename``; raise ``KeyError`` when absent."""
    for lock in LOCKS:
        if lock.filename == filename:
            return lock
    raise KeyError(filename)


# --- pure helpers -------------------------------------------------------------


def timestamp_for_date(date_text: str) -> str:
    """Return the ``--exclude-newer`` timestamp for ``YYYY-MM-DD`` (midnight UTC).

    A full UTC timestamp is recorded because uv reads a bare date in the host's
    local time zone.
    """
    if not _DATE_RE.match(date_text):
        raise ValueError(f"lock date {date_text!r} is not YYYY-MM-DD")
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"lock date {date_text!r} is not a calendar date") from exc
    return f"{date_text}T00:00:00Z"


def today_utc() -> str:
    """Return today's date in UTC as ``YYYY-MM-DD``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def uv_version_from_output(output: str) -> str:
    """Return the version in ``uv --version`` output such as ``uv 0.11.14 (...)``."""
    match = _UV_VERSION_RE.match(output.strip())
    if match is None:
        raise ValueError(f"cannot read a uv version from {output!r}")
    return match.group("version")


def render_header(lock: Lock, timestamp: str, uv_version: str) -> str:
    """Return the comment header written above the compiled requirements."""
    lines = [
        f"# {_SPDX}",
        "",
        *_wrap_comment(f"Hash-locked requirements for CI: {lock.purpose}."),
        *_wrap_comment(f"Installed by {lock.installed_by}. Install command:"),
        f"#   python -m pip install --require-hashes -r {lock.relpath}",
    ]
    if lock.note:
        lines.append("#")
        lines.extend(_wrap_comment(lock.note))
    lines.extend(
        [
            "#",
            "# One universal lock for every supported interpreter and platform: a line",
            "# that carries an environment marker applies only where the marker is true.",
            "# Every package carries the hashes of all its files, wheels and sdist, so an",
            "# interpreter without a wheel yet (the advisory pre-release cell) builds",
            "# from the hashed sdist; pip prefers a wheel wherever one exists. pip",
            "# checks hashes only when it downloads: a runner that already has a version",
            '# reports "Requirement already satisfied" and verifies nothing. The lock',
            "# holds only files uploaded before the lock date, so a release newer than",
            "# that date is not installed until the next refresh.",
            "#",
            "# Do not edit by hand and do not bump a single pin: every lock in this folder",
            "# is a closure, regenerated whole. To refresh them all:",
            f"#   python {SCRIPT_RELPATH}",
            "# To verify a committed lock against its recorded date (needs uv and network):",
            f"#   python {SCRIPT_RELPATH} --check",
            "# tests/scripts/test_ci_locks_fresh.py fails when pyproject.toml asks for a",
            "# version this lock does not pin.",
            "#",
            f"{_LOCKED_AS_OF_PREFIX}{timestamp}",
            f"{_UV_PREFIX}{uv_version}",
        ]
    )
    return "\n".join(lines) + "\n"


def _wrap_comment(text: str, width: int = 80) -> list[str]:
    """Wrap ``text`` into ``# `` comment lines no wider than ``width``."""
    words = text.split()
    lines: list[str] = []
    current = "#"
    for word in words:
        if len(current) + 1 + len(word) > width and current != "#":
            lines.append(current)
            current = "#"
        current = f"{current} {word}"
    lines.append(current)
    return lines


def parse_header(text: str) -> tuple[str | None, str | None]:
    """Return ``(timestamp, uv version)`` recorded in a lock header, or ``None``."""
    timestamp: str | None = None
    uv_version: str | None = None
    for line in text.splitlines():
        if line.startswith(_LOCKED_AS_OF_PREFIX):
            candidate = line[len(_LOCKED_AS_OF_PREFIX) :].strip()
            if _TIMESTAMP_RE.match(candidate):
                timestamp = candidate
        elif line.startswith(_UV_PREFIX):
            uv_version = line[len(_UV_PREFIX) :].strip() or None
    return timestamp, uv_version


def requirement_entries(text: str) -> dict[str, tuple[str, ...]]:
    """Map each requirement line (name, version, marker) to its sorted hashes.

    Comments and blank lines are ignored and ``\\`` continuations are joined, so
    two files with the same requirements compare equal whatever their header.
    The key is the text before the first ``--hash``, whitespace-normalised.
    """
    entries: dict[str, tuple[str, ...]] = {}
    pending: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not pending and (not stripped or stripped.startswith("#")):
            continue
        continued = stripped.endswith("\\")
        pending.append(stripped[:-1].strip() if continued else stripped)
        if continued:
            continue
        logical = " ".join(part for part in pending if part)
        pending = []
        head, *hashes = logical.split("--hash=")
        key = " ".join(head.split())
        entries[key] = tuple(sorted(hash_.strip() for hash_ in hashes))
    return entries


def _split_key(key: str) -> tuple[str, str, str]:
    """Split ``name==version ; marker`` into ``(name, version, marker)``."""
    requirement, _, marker = key.partition(";")
    name, _, version = requirement.partition("==")
    return name.strip(), version.strip(), marker.strip()


def diff_summary(committed: str, fresh: str) -> list[str]:
    """Describe how the requirements of ``committed`` differ from ``fresh``.

    Returns an empty list when the requirement lines and their hashes agree.
    A package is identified by its name and marker, so a version change reads as
    one line and a package present on one side only reads as added or removed.
    """
    old = {
        _slot(key): (key, hashes)
        for key, hashes in requirement_entries(committed).items()
    }
    new = {
        _slot(key): (key, hashes) for key, hashes in requirement_entries(fresh).items()
    }
    messages: list[str] = []
    for slot in sorted(old.keys() | new.keys()):
        name, marker = slot
        suffix = f" ; {marker}" if marker else ""
        if slot not in new:
            messages.append(f"{name}{suffix}: only in the committed lock")
        elif slot not in old:
            messages.append(f"{name}{suffix}: only in the fresh compile")
        else:
            old_key, old_hashes = old[slot]
            new_key, new_hashes = new[slot]
            old_version = _split_key(old_key)[1]
            new_version = _split_key(new_key)[1]
            if old_version != new_version:
                messages.append(
                    f"{name}{suffix}: committed {old_version}, fresh {new_version}"
                )
            elif old_hashes != new_hashes:
                messages.append(f"{name}{suffix}: the hashes differ at {old_version}")
    return messages


def _slot(key: str) -> tuple[str, str]:
    name, _, marker = _split_key(key)
    return name, marker


def compose_lock(lock: Lock, body: str, timestamp: str, uv_version: str) -> str:
    """Return the full file text: the header, a blank line and the requirements."""
    normalised = body.replace("\r\n", "\n").lstrip("\n")
    if not normalised.endswith("\n"):
        normalised += "\n"
    return render_header(lock, timestamp, uv_version) + normalised


def compile_command(
    lock: Lock, timestamp: str, output: Path, *, uv: str = "uv"
) -> list[str]:
    """Return the ``uv pip compile`` command line for ``lock``."""
    command = [
        uv,
        "pip",
        "compile",
        *lock.sources,
        "--universal",
        "--python-version",
        PYTHON_FLOOR,
        "--generate-hashes",
        "--no-annotate",
        "--no-header",
        "--upgrade",
        "--exclude-newer",
        timestamp,
        "-o",
        str(output),
    ]
    for extra in lock.extras:
        command.extend(["--extra", extra])
    return command


# --- uv and the file system --------------------------------------------------


def _find_uv() -> str:
    uv = shutil.which("uv")
    if uv is None:
        print(
            "uv is not on PATH. Install uv (https://docs.astral.sh/uv/) and run "
            f"`python {SCRIPT_RELPATH}` again; the locks are compiled with "
            "`uv pip compile`.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return uv


def read_uv_version(uv: str) -> str:
    """Return the version of the ``uv`` executable."""
    result = subprocess.run(  # noqa: S603 - fixed argv: uv resolved by shutil.which
        [uv, "--version"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"`uv --version` failed: {result.stderr.strip()}")
    return uv_version_from_output(result.stdout)


def compile_lock(
    lock: Lock, timestamp: str, uv: str, work_dir: Path, repo_root: Path
) -> str:
    """Compile ``lock`` into a fresh file under ``work_dir`` and return its text.

    The output path is new on every call, so uv has no earlier pins to reuse as
    preferences and resolves every package to the newest release as of the date.
    """
    output = work_dir / lock.filename
    command = compile_command(lock, timestamp, output, uv=uv)
    stdin = "\n".join(lock.stdin_requirements) + "\n" if "-" in lock.sources else None
    result = subprocess.run(  # noqa: S603 - argv built from the LOCKS table
        command,
        cwd=repo_root,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"uv failed for {lock.relpath} (exit {result.returncode}):\n"
            f"{result.stderr.strip()}"
        )
    return output.read_bytes().decode("utf-8")


def write_lf(path: Path, text: str) -> None:
    """Write ``text`` as UTF-8 with LF line endings, whatever the platform."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def refresh(repo_root: Path, date_text: str, uv: str) -> list[Path]:
    """Compile every lock as of ``date_text`` and write it; return the paths."""
    timestamp = timestamp_for_date(date_text)
    uv_version = read_uv_version(uv)
    # Compile every lock before writing any: a uv failure part-way leaves the
    # working tree untouched instead of holding locks from two different dates.
    texts: list[tuple[Path, str]] = []
    with tempfile.TemporaryDirectory(prefix="apothem-ci-locks-") as tmp:
        for lock in LOCKS:
            body = compile_lock(lock, timestamp, uv, Path(tmp), repo_root)
            texts.append(
                (
                    repo_root / lock.relpath,
                    compose_lock(lock, body, timestamp, uv_version),
                )
            )
    for target, text in texts:
        write_lf(target, text)
    return [target for target, _ in texts]


def check(repo_root: Path, uv: str) -> list[str]:
    """Return one message per committed lock that differs from a fresh compile."""
    problems: list[str] = []
    uv_version = read_uv_version(uv)
    with tempfile.TemporaryDirectory(prefix="apothem-ci-locks-") as tmp:
        for lock in LOCKS:
            target = repo_root / lock.relpath
            if not target.is_file():
                problems.append(
                    f"{lock.relpath} is missing; run `python {SCRIPT_RELPATH}`"
                )
                continue
            committed = target.read_bytes().decode("utf-8")
            if "\r" in committed:
                problems.append(
                    f"{lock.relpath} has CRLF line endings; rewrite it with LF "
                    f"(`python {SCRIPT_RELPATH}` writes LF)"
                )
            timestamp, recorded_uv = parse_header(committed)
            if timestamp is None:
                problems.append(
                    f"{lock.relpath} records no `Locked as of:` timestamp; "
                    f"run `python {SCRIPT_RELPATH}`"
                )
                continue
            body = compile_lock(lock, timestamp, uv, Path(tmp), repo_root)
            differences = diff_summary(committed, body)
            if differences:
                note = ""
                if recorded_uv != uv_version:
                    note = (
                        f" (written by uv {recorded_uv}, compared with uv "
                        f"{uv_version}; a different uv can normalise markers "
                        "differently)"
                    )
                detail = "\n".join(f"    - {line}" for line in differences[:20])
                more = (
                    f"\n    - ... and {len(differences) - 20} more"
                    if len(differences) > 20
                    else ""
                )
                problems.append(
                    f"{lock.relpath} differs from a fresh compile as of "
                    f"{timestamp}{note}:\n{detail}{more}"
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    """Run the refresh (default) or the ``--check`` comparison."""
    parser = argparse.ArgumentParser(
        description="Regenerate the hash-locked CI requirement files in scripts/ci/.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compile into a temporary directory with each recorded lock date and "
        "exit 1 when a committed lock differs (needs uv and network access)",
    )
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="lock date for a refresh: only releases uploaded before this day "
        "(00:00 UTC) are used; default today (UTC). Ignored by --check.",
    )
    args = parser.parse_args(argv)

    if args.check and args.date:
        parser.error("--date does not apply to --check, which reads each lock's date")
    date_text = args.date or today_utc()
    try:
        timestamp_for_date(date_text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    uv = _find_uv()
    try:
        if args.check:
            problems = check(_REPO_ROOT, uv)
            if problems:
                print("CI lock drift detected:", file=sys.stderr)
                for problem in problems:
                    print(f"  - {problem}", file=sys.stderr)
                print(
                    f"Run `python {SCRIPT_RELPATH}` to regenerate every lock.",
                    file=sys.stderr,
                )
                return 1
            print(f"{len(LOCKS)} CI lock(s) match a fresh compile")
            return 0
        written = refresh(_REPO_ROOT, date_text, uv)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(f"wrote {path.relative_to(_REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
