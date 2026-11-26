# SPDX-License-Identifier: MIT

"""Fail when a change edits a released section of CHANGELOG.md.

Why this check exists. A release renames ``## [Unreleased]`` to
``## [x.y.z] - date``. A branch cut before the release adds its entry
right below that heading, so when the branch later merges the release in,
git applies the entry without a conflict and it lands inside the released
section. Nothing failed: after v1.6.0, five open pull requests would have
put their entries in the 1.6.0 notes this way.

The check compares ``CHANGELOG.md`` at a base revision with the working
tree. Every ``## [x.y.z]`` section the base already has must be present and
unchanged; new entries belong under ``[Unreleased]``. A release pull
request passes, because the new version's heading is not in the base yet.
Link definitions at the foot of the file are ignored here, since
``check_changelog_links.py`` checks them and a release changes them.

A deliberate edit of released notes (a correction, or the release-facade
clean-up) passes when a commit in ``<base>..HEAD`` carries the trailer
``Changelog-Released-Edit: <reason>``.

Exit codes: ``0`` when clean or opted out, ``1`` on any finding, ``2`` when
the base or the file cannot be read.
"""

from __future__ import annotations

import argparse
import difflib
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAILER = "Changelog-Released-Edit"

_HEADING = re.compile(r"^## \[([^\]]+)\]")
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
_DEFINITION = re.compile(r"^\[[^\]]+\]:\s*\S+\s*$")
_DIFF_LINES = 12


def released_sections(text: str) -> dict[str, list[str]]:
    """Map each ``x.y.z`` heading to its lines, link definitions left out."""
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.replace("\r\n", "\n").split("\n"):
        match = _HEADING.match(line)
        if match is not None:
            label = match.group(1)
            current = sections.setdefault(label, []) if _VERSION.match(label) else None
            if current is not None:
                current.append(line)
            continue
        if current is not None and not _DEFINITION.match(line):
            current.append(line)
    for lines in sections.values():
        while lines and not lines[-1].strip():
            lines.pop()
    return sections


def find_problems(base_text: str, head_text: str) -> list[str]:
    """Return one message, with a short diff, per changed released section."""
    base = released_sections(base_text)
    head = released_sections(head_text)
    problems: list[str] = []
    for version, old in base.items():
        new = head.get(version)
        if new is None:
            problems.append(f"[{version}]: the released section was removed")
            continue
        if new == old:
            continue
        diff = list(
            difflib.unified_diff(
                old, new, f"base [{version}]", f"head [{version}]", lineterm="", n=1
            )
        )
        shown = "\n".join(f"    {line}" for line in diff[:_DIFF_LINES])
        more = len(diff) - _DIFF_LINES
        tail = f"\n    ... {more} more diff lines" if more > 0 else ""
        problems.append(
            f"[{version}]: the released section changed; move new entries "
            f"under [Unreleased]\n{shown}{tail}"
        )
    return problems


def _git(*args: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is not on PATH")
    result = subprocess.run(  # noqa: S603 - fixed git argv, no shell
        [git, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def opted_out(base: str) -> list[str]:
    """Return the reasons given by the opt-out trailer in ``base..HEAD``."""
    out = _git("log", f"{base}..HEAD", f"--format=%(trailers:key={TRAILER},valueonly)")
    return [line.strip() for line in out.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base",
        required=True,
        help="Revision to compare with, such as origin/main.",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=REPO_ROOT / "CHANGELOG.md",
        help="Path to the working-tree changelog (default: CHANGELOG.md).",
    )
    args = parser.parse_args(argv)
    name = "check-changelog-released-sections"
    try:
        head_text = args.changelog.read_text(encoding="utf-8")
        base_text = _git("show", f"{args.base}:CHANGELOG.md")
        reasons = opted_out(args.base)
    except (OSError, RuntimeError) as exc:
        print(f"{name}: {exc}", file=sys.stderr)
        return 2

    problems = find_problems(base_text, head_text)
    if problems and reasons:
        print(f"{name}: released sections changed, allowed by {TRAILER}:")
        for reason in reasons:
            print(f"  {reason}")
        return 0
    if problems:
        print(f"{name}: {len(problems)} finding(s) against {args.base}")
        for problem in problems:
            print(f"  {problem}")
        print(
            f"  To change released notes on purpose, add the trailer "
            f"'{TRAILER}: <reason>' to a commit."
        )
        return 1
    print(f"{name}: OK - no released section changed against {args.base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
