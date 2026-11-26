# SPDX-License-Identifier: MIT

"""Fail when a change edits a released section of CHANGELOG.md.

Why this check exists. A release renames ``## [Unreleased]`` to
``## [x.y.z] - date``. A branch cut before the release has its entry in the
old ``[Unreleased]`` section, and when the branch later merges the release
in, git can apply that entry without a conflict inside the released section.
Nothing failed: after v1.6.0, five open pull requests would have put their
entries in the 1.6.0 notes this way.

The check compares ``CHANGELOG.md`` at a base revision with the working
tree. Every ``## [x.y.z]`` section the base already has must be present and
unchanged; new entries belong under ``[Unreleased]``. A release passes,
because the new version's heading is not in the base yet. Only the block of
link definitions at the end of the file is left out, since
``check_changelog_links.py`` checks it and a release changes it. Headings
that are not plain ``x.y.z`` versions (a pre-release, for example) are not
protected.

In CI the base is ``HEAD^1``: for a pull request, the base branch commit
GitHub merged the pull request into; for a push to main, the commit before
it. A deliberate edit of released notes passes when a commit in
``<base>..HEAD`` carries the trailer
``Changelog-Released-Edit: <version> <reason>``; it allows that version's
section only, and the check still prints what changed.

Exit codes: ``0`` when clean or allowed, ``1`` on any finding, ``2`` when the
base or the file cannot be read.
"""

from __future__ import annotations

import argparse
import difflib
import os
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
_ALLOWED = re.compile(r"^v?(\d+\.\d+\.\d+)[:,]?(?:\s+(.*))?$")
_DIFF_LINES = 12
# Variables that would point git at another repository than REPO_ROOT.
_GIT_LOCATION = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")


def _strip_link_block(lines: list[str]) -> list[str]:
    """Drop the link definitions (and blank lines) that end the file."""
    end = len(lines)
    while end and (not lines[end - 1].strip() or _DEFINITION.match(lines[end - 1])):
        end -= 1
    return lines[:end]


def released_sections(text: str) -> dict[str, list[str]]:
    """Map each ``x.y.z`` heading to its lines, without the closing links."""
    lines = _strip_link_block(text.replace("\r\n", "\n").split("\n"))
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in lines:
        match = _HEADING.match(line)
        if match is not None:
            label = match.group(1)
            current = sections.setdefault(label, []) if _VERSION.match(label) else None
        if current is not None:
            current.append(line)
    for section in sections.values():
        while section and not section[-1].strip():
            section.pop()
    return sections


def changed_sections(base_text: str, head_text: str) -> dict[str, str]:
    """Map each changed or removed released version to a short report."""
    base = released_sections(base_text)
    head = released_sections(head_text)
    changed: dict[str, str] = {}
    for version, old in base.items():
        new = head.get(version)
        if new is None:
            changed[version] = f"[{version}]: the released section was removed"
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
        changed[version] = (
            f"[{version}]: the released section changed; move new entries "
            f"under [Unreleased]\n{shown}{tail}"
        )
    return changed


def find_problems(base_text: str, head_text: str) -> list[str]:
    """Return one message, with a short diff, per changed released section."""
    return list(changed_sections(base_text, head_text).values())


def _git(*args: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is not on PATH")
    env = {k: v for k, v in os.environ.items() if k not in _GIT_LOCATION}
    result = subprocess.run(  # noqa: S603 - fixed git argv, no shell
        [git, "-c", "log.showSignature=false", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {message}")
    return result.stdout.decode("utf-8")


def allowed_versions(base: str) -> dict[str, str]:
    """Map each version a ``base..HEAD`` trailer allows to its reason."""
    out = _git("log", f"{base}..HEAD", f"--format=%(trailers:key={TRAILER},valueonly)")
    allowed: dict[str, str] = {}
    for line in out.splitlines():
        match = _ALLOWED.match(line.strip())
        if match is not None:
            allowed[match.group(1)] = (match.group(2) or "").strip()
    return allowed


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base",
        required=True,
        help="Revision to compare with, such as HEAD^1 or origin/main.",
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
        changed = changed_sections(base_text, head_text)
        allowed = allowed_versions(args.base) if changed else {}
    except (OSError, RuntimeError, UnicodeDecodeError) as exc:
        print(f"{name}: {exc}", file=sys.stderr)
        return 2

    failing = {v: report for v, report in changed.items() if v not in allowed}
    for version, report in changed.items():
        if version in allowed:
            print(
                f"{name}: [{version}] changed, allowed by {TRAILER}: {allowed[version]}"
            )
            print(report)
    if failing:
        print(f"{name}: {len(failing)} finding(s) against {args.base}")
        for report in failing.values():
            print(f"  {report}")
        print(
            f"  To change released notes on purpose, add the trailer "
            f"'{TRAILER}: <version> <reason>' to a commit."
        )
        return 1
    if not changed:
        print(f"{name}: OK - no released section changed against {args.base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
