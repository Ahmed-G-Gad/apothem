# SPDX-License-Identifier: MIT

"""Regenerate, or verify, the hash-locked requirement files CI installs.

CI installs its Python dependencies from the files in ``scripts/ci/`` with
``python -m pip install --require-hashes -r <lock>``. OpenSSF Scorecard counts a
``pip install`` as pinned only when it carries ``--require-hashes``, and a
hash-locked file also makes pip verify every download. The files are produced by
``uv pip compile`` and are never edited by hand. The table of files, with their
inputs and Python floors, is ``scripts/dev/ci_lock_table.py``: four project locks
(``dev``, ``runtime``, ``test``, ``prereqs``) and one lock per CI tool
(``ruff``, ``bandit``, ``pip-audit``, ``pip-licenses``, ``pre-commit``).

Default mode compiles every lock against the package index as of a lock date
(today at 00:00 UTC unless ``--date`` names another day) minus a cooldown, and
rewrites the files. The cooldown is 7 days, the same as Dependabot's, so a
release is not locked until it has been public for a week; ``--cooldown-days N``
changes it. ``--cooldown-days 0`` locks every file uploaded before 00:00 UTC of
the lock date, for an urgent security fix; a fix uploaded that day needs a
cooldown exception, an entry in ``cooldown_exceptions`` of the lock's row that
lets one package take files up to its timestamp (``--exclude-newer-package``; see
the table). The refresh refuses an exception the cutoff has already passed. The
cutoff handed to uv (``--exclude-newer``) is the lock date minus the cooldown at
00:00 UTC. Run the script weekly and whenever ``pyproject.toml`` changes a
dependency. ``--check`` compiles every lock again in a temporary directory, with
the cutoff recorded in the committed file, and exits 1 with a summary of the
differing packages when a committed file does not match. It also reports a header
whose cutoff is not its lock date minus its cooldown, or whose cooldown
exceptions differ from the table's. ``--check`` needs uv and network access, so
it is an operator command and does not run in the required CI jobs.
``tests/scripts/test_ci_locks_fresh.py`` is the offline test that holds each
lock to its inputs.

Each lock records ``Locked as of:`` (the lock date), ``Cooldown:``, ``Cutoff:``
(the ``--exclude-newer`` timestamp), one ``Cooldown exception:`` line per
exception and the uv version that wrote it. A different uv version can normalise
environment markers differently, so ``--check`` compares the requirement lines
only and says when the uv version differs. Every compile passes
``--no-emit-package pip``: only ``requirements-ci-pip.txt`` pins pip, so
Dependabot owns the one pip pin.

The script needs only the standard library and ``uv`` on ``PATH``.

Exit codes: 0 success (or every lock matches under ``--check``), 1 a lock
differs under ``--check`` or a compile failed, 2 a usage error (uv missing,
bad date, bad cooldown).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ci_lock_table import (
    CI_DIR,
    EXCEPTION_PREFIX,
    LOCKS,
    PYTHON_FLOOR,
    Lock,
    lock_by_filename,
)

__all__ = [
    "CI_DIR",
    "DEFAULT_COOLDOWN_DAYS",
    "EXCEPTION_PREFIX",
    "LOCKS",
    "PYTHON_FLOOR",
    "Lock",
    "ParsedHeader",
    "Stamp",
    "lock_by_filename",
]

_REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_RELPATH = "scripts/dev/refresh_ci_locks.py"
TABLE_RELPATH = "scripts/dev/ci_lock_table.py"

# Dependabot's cooldown in .github/dependabot.yml (`default-days: 7`): a locked
# release has been public at least this long.
DEFAULT_COOLDOWN_DAYS = 7

_SPDX = "SPDX-License-" + "Identifier: MIT"
_LOCKED_AS_OF_PREFIX = "# Locked as of: "
_COOLDOWN_PREFIX = "# Cooldown: "
_CUTOFF_PREFIX = "# Cutoff: "
_UV_PREFIX = "# Compiled with: uv "
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T00:00:00Z$")
_COOLDOWN_RE = re.compile(r"^(?P<days>\d+) days?$")
_UV_VERSION_RE = re.compile(r"^uv (?P<version>\S+)")


@dataclass(frozen=True)
class Stamp:
    """When and how a lock was compiled: the facts its header records."""

    locked_as_of: str
    cooldown_days: int
    cutoff: str
    uv_version: str


@dataclass(frozen=True)
class ParsedHeader:
    """The header facts read back from a lock file; ``None`` marks a missing line."""

    locked_as_of: str | None = None
    cooldown_days: int | None = None
    cutoff: str | None = None
    uv_version: str | None = None

    def missing(self) -> list[str]:
        """Return the labels of the header lines the file does not carry."""
        found = {
            "Locked as of": self.locked_as_of,
            "Cooldown": self.cooldown_days,
            "Cutoff": self.cutoff,
            "Compiled with": self.uv_version,
        }
        return [label for label, value in found.items() if value is None]


# --- pure helpers -------------------------------------------------------------


def timestamp_for_date(date_text: str) -> str:
    """Return the lock-date timestamp for ``YYYY-MM-DD`` (midnight UTC).

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


def cutoff_timestamp(locked_as_of: str, cooldown_days: int) -> str:
    """Return the ``--exclude-newer`` timestamp: the lock date minus the cooldown.

    ``locked_as_of`` is a lock-date timestamp from ``timestamp_for_date``; the
    result is the same kind of timestamp, ``cooldown_days`` earlier.
    """
    if cooldown_days < 0:
        raise ValueError(f"cooldown {cooldown_days} is negative; use 0 or more days")
    if not _TIMESTAMP_RE.match(locked_as_of):
        raise ValueError(f"lock timestamp {locked_as_of!r} is not YYYY-MM-DDT00:00:00Z")
    locked = datetime.strptime(locked_as_of[:10], "%Y-%m-%d")
    try:
        cutoff = locked - timedelta(days=cooldown_days)
    except OverflowError as exc:
        raise ValueError(f"a cooldown of {cooldown_days} days is out of range") from exc
    return f"{cutoff:%Y-%m-%d}T00:00:00Z"


def today_utc() -> str:
    """Return today's date in UTC as ``YYYY-MM-DD``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def uv_version_from_output(output: str) -> str:
    """Return the version in ``uv --version`` output such as ``uv 0.11.14 (...)``."""
    match = _UV_VERSION_RE.match(output.strip())
    if match is None:
        raise ValueError(f"cannot read a uv version from {output!r}")
    return match.group("version")


def render_header(lock: Lock, stamp: Stamp) -> str:
    """Return the comment header written above the compiled requirements."""
    days = f"{stamp.cooldown_days} day" + ("" if stamp.cooldown_days == 1 else "s")
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
    lines.append("#")
    lines.extend(
        _wrap_comment(
            f"One universal lock for Python {lock.python_floor} and later on every "
            "platform: a line that carries an environment marker applies only where "
            "the marker is true. Every package carries the hashes of all its files, "
            "wheels and sdist, so an interpreter without a wheel yet (the advisory "
            "pre-release cell) builds from the hashed sdist; pip prefers a wheel "
            "wherever one exists. pip checks hashes only when it downloads: a runner "
            'that already has a version reports "Requirement already satisfied" and '
            "verifies nothing."
        )
    )
    lines.append("#")
    lines.extend(
        _wrap_comment(
            "The lock holds only files uploaded before the cutoff below, the lock "
            "date minus the cooldown, so a release younger than the cooldown is not "
            "installed until a later refresh. Only requirements-ci-pip.txt pins pip."
        )
    )
    lines.append("#")
    lines.extend(
        _wrap_comment(
            "Do not edit by hand and do not bump a single pin: every lock in this "
            f"folder is a closure, regenerated whole from the table in {TABLE_RELPATH}. "
            "To refresh them all:"
        )
    )
    lines.extend(
        [
            f"#   python {SCRIPT_RELPATH}",
            *_wrap_comment(
                "A security fix younger than the cooldown needs --cooldown-days 0, "
                "which takes files uploaded before 00:00 UTC of the lock date, or, "
                "for a fix uploaded on that day, a cooldown exception for its "
                "package in the table."
            ),
            *_wrap_comment(
                "To verify a committed lock against its recorded dates (needs uv and "
                "network):"
            ),
            f"#   python {SCRIPT_RELPATH} --check",
            *_wrap_comment(
                "tests/scripts/test_ci_locks_fresh.py fails when a lock drifts from "
                "its inputs."
            ),
            "#",
            f"{_LOCKED_AS_OF_PREFIX}{stamp.locked_as_of}",
            f"{_COOLDOWN_PREFIX}{days}",
            f"{_CUTOFF_PREFIX}{stamp.cutoff}",
            *lock.exception_lines,
            f"{_UV_PREFIX}{stamp.uv_version}",
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


def parse_header(text: str) -> ParsedHeader:
    """Return the dates and the uv version recorded in a lock header.

    A line that is missing, or whose value is malformed, reads as ``None``.
    """
    locked_as_of: str | None = None
    cooldown_days: int | None = None
    cutoff: str | None = None
    uv_version: str | None = None
    for line in text.splitlines():
        if line.startswith(_LOCKED_AS_OF_PREFIX):
            candidate = line[len(_LOCKED_AS_OF_PREFIX) :].strip()
            if _TIMESTAMP_RE.match(candidate):
                locked_as_of = candidate
        elif line.startswith(_COOLDOWN_PREFIX):
            match = _COOLDOWN_RE.match(line[len(_COOLDOWN_PREFIX) :].strip())
            if match is not None:
                cooldown_days = int(match.group("days"))
        elif line.startswith(_CUTOFF_PREFIX):
            candidate = line[len(_CUTOFF_PREFIX) :].strip()
            if _TIMESTAMP_RE.match(candidate):
                cutoff = candidate
        elif line.startswith(_UV_PREFIX):
            uv_version = line[len(_UV_PREFIX) :].strip() or None
    return ParsedHeader(locked_as_of, cooldown_days, cutoff, uv_version)


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


def compose_lock(lock: Lock, body: str, stamp: Stamp) -> str:
    """Return the full file text: the header, a blank line and the requirements."""
    normalised = body.replace("\r\n", "\n").lstrip("\n")
    if not normalised.endswith("\n"):
        normalised += "\n"
    return render_header(lock, stamp) + normalised


def compile_command(
    lock: Lock, cutoff: str, output: Path, *, uv: str = "uv"
) -> list[str]:
    """Return the ``uv pip compile`` command line for ``lock``.

    ``--no-emit-package pip`` keeps pip out of every closure: pip-api, a
    dependency of pip-audit, would otherwise pin a pip of its own beside
    ``requirements-ci-pip.txt`` and replace it on install. Each cooldown exception
    of the row goes to uv as ``--exclude-newer-package``; ``refresh`` and ``check``
    refuse one the cutoff has passed before they get here.
    """
    command = [
        uv,
        "pip",
        "compile",
        *lock.sources,
        "--universal",
        "--python-version",
        lock.python_floor,
        "--generate-hashes",
        "--no-annotate",
        "--no-header",
        "--upgrade",
        "--no-emit-package",
        "pip",
        "--exclude-newer",
        cutoff,
        "-o",
        str(output),
    ]
    for extra in lock.extras:
        command.extend(["--extra", extra])
    for name, until in lock.cooldown_exceptions:
        command.extend(["--exclude-newer-package", f"{name}={until}"])
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
    lock: Lock, cutoff: str, uv: str, work_dir: Path, repo_root: Path
) -> str:
    """Compile ``lock`` into a fresh file under ``work_dir`` and return its text.

    The output path is new on every call, so uv has no earlier pins to reuse as
    preferences and resolves every package to the newest release uploaded before
    ``cutoff``.
    """
    output = work_dir / lock.filename
    command = compile_command(lock, cutoff, output, uv=uv)
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
            f"{result.stderr.strip()}\n"
            f"A pinned release uploaded after the cutoff {cutoff} cannot resolve: "
            "wait until it is older than the cooldown, refresh with "
            "--cooldown-days 0, or add a cooldown exception for its package to "
            f"{TABLE_RELPATH}."
        )
    return output.read_bytes().decode("utf-8")


def write_lf(path: Path, text: str) -> None:
    """Write ``text`` as UTF-8 with LF line endings, whatever the platform."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def refresh(
    repo_root: Path,
    date_text: str,
    uv: str,
    cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
) -> list[Path]:
    """Compile every lock as of ``date_text`` less the cooldown and write it."""
    locked_as_of = timestamp_for_date(date_text)
    cutoff = cutoff_timestamp(locked_as_of, cooldown_days)
    for lock in LOCKS:
        if stale := lock.stale_exceptions(cutoff):
            raise RuntimeError(_stale_message(lock, stale, cutoff))
    stamp = Stamp(locked_as_of, cooldown_days, cutoff, read_uv_version(uv))
    # Compile every lock before writing any: a uv failure part-way leaves the
    # working tree untouched instead of holding locks from two different dates.
    texts: list[tuple[Path, str]] = []
    with tempfile.TemporaryDirectory(prefix="apothem-ci-locks-") as tmp:
        for lock in LOCKS:
            body = compile_lock(lock, cutoff, uv, Path(tmp), repo_root)
            texts.append((repo_root / lock.relpath, compose_lock(lock, body, stamp)))
    for target, text in texts:
        write_lf(target, text)
    return [target for target, _ in texts]


def _stale_message(lock: Lock, stale: list[str], cutoff: str) -> str:
    return (
        f"{lock.relpath} lists a cooldown exception for {', '.join(stale)}, but the "
        f"cutoff {cutoff} already reaches its timestamp: the exception lifts nothing "
        f"and uv would hold the package back. Remove it from {TABLE_RELPATH} and "
        f"run `python {SCRIPT_RELPATH}`"
    )


def _exception_drift(lock: Lock, text: str, cutoff: str) -> str | None:
    """Return why the cooldown exceptions of ``lock`` cannot be replayed, if so."""
    if stale := lock.stale_exceptions(cutoff):
        return _stale_message(lock, stale, cutoff)
    found = [line for line in text.splitlines() if line.startswith(EXCEPTION_PREFIX)]
    if found == lock.exception_lines:
        return None
    return (
        f"{lock.relpath} records the cooldown exceptions {found or 'none'}, but "
        f"{TABLE_RELPATH} lists {lock.exception_lines or 'none'}; run "
        f"`python {SCRIPT_RELPATH}`"
    )


def _recorded_stamp(lock: Lock, text: str) -> Stamp | str:
    """Return the stamp a lock records, or why the header cannot be trusted.

    A header that lacks a line, or whose cutoff is not its lock date less its
    cooldown, was edited by hand or written by an older script; ``--check``
    reports it instead of normalising it.
    """
    header = parse_header(text)
    if (
        header.locked_as_of is None
        or header.cooldown_days is None
        or header.cutoff is None
        or header.uv_version is None
    ):
        names = ", ".join(f"`{label}:`" for label in header.missing())
        return f"{lock.relpath} records no {names} line; run `python {SCRIPT_RELPATH}`"
    try:
        expected = cutoff_timestamp(header.locked_as_of, header.cooldown_days)
    except ValueError as exc:
        return (
            f"{lock.relpath} records a cooldown it cannot use ({exc}); "
            f"run `python {SCRIPT_RELPATH}`"
        )
    if header.cutoff != expected:
        return (
            f"{lock.relpath} records `Cutoff: {header.cutoff}`, but its lock date "
            f"{header.locked_as_of} less its {header.cooldown_days}-day cooldown is "
            f"{expected}; the header was edited by hand or written by an older "
            f"script; run `python {SCRIPT_RELPATH}`"
        )
    return Stamp(
        header.locked_as_of, header.cooldown_days, header.cutoff, header.uv_version
    )


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
            recorded = _recorded_stamp(lock, committed)
            if isinstance(recorded, str):
                problems.append(recorded)
                continue
            drift = _exception_drift(lock, committed, recorded.cutoff)
            if drift is not None:
                problems.append(drift)
                continue
            # The recorded cutoff goes to uv as written, never recomputed.
            body = compile_lock(lock, recorded.cutoff, uv, Path(tmp), repo_root)
            differences = diff_summary(committed, body)
            if differences:
                note = ""
                if recorded.uv_version != uv_version:
                    note = (
                        f" (written by uv {recorded.uv_version}, compared with uv "
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
                    f"{lock.relpath} differs from a fresh compile with cutoff "
                    f"{recorded.cutoff}{note}:\n{detail}{more}"
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
        help="compile into a temporary directory with each recorded cutoff and "
        "exit 1 when a committed lock differs (needs uv and network access)",
    )
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="lock date for a refresh, recorded in each lock; default today (UTC). "
        "Not used by --check.",
    )
    parser.add_argument(
        "--cooldown-days",
        metavar="N",
        type=int,
        help="days a release must be public before it is locked: the cutoff is the "
        f"lock date minus N days (00:00 UTC); default {DEFAULT_COOLDOWN_DAYS}, "
        "the Dependabot cooldown. 0 locks every file uploaded before 00:00 UTC of "
        "the lock date, for an urgent security fix; a fix uploaded on the lock "
        "date itself needs a cooldown exception in the table. Not used by "
        "--check.",
    )
    args = parser.parse_args(argv)

    if args.check and (args.date is not None or args.cooldown_days is not None):
        parser.error(
            "--date and --cooldown-days do not apply to --check, which reads the "
            "dates each lock records"
        )
    cooldown_days = (
        DEFAULT_COOLDOWN_DAYS if args.cooldown_days is None else args.cooldown_days
    )
    date_text = args.date or today_utc()
    try:
        cutoff = cutoff_timestamp(timestamp_for_date(date_text), cooldown_days)
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
        if cooldown_days == 0:
            print(
                "note: a cooldown of 0 days locks releases younger than the "
                "Dependabot cooldown, up to 00:00 UTC of the lock date; use it for "
                "an urgent security fix, and refresh again with the default "
                "cooldown afterwards. A fix uploaded on the lock date itself needs "
                "a cooldown exception.",
                file=sys.stderr,
            )
        print(
            f"Locking as of {date_text} with a {cooldown_days}-day cooldown: "
            f"only files uploaded before {cutoff} are used"
        )
        written = refresh(_REPO_ROOT, date_text, uv, cooldown_days)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(f"wrote {path.relative_to(_REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
