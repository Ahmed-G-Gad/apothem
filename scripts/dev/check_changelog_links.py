# SPDX-License-Identifier: MIT

"""Fail when a CHANGELOG version heading has no matching link definition.

Why this check exists. Keep a Changelog renders each ``## [x.y.z]`` heading
as a link through a reference definition at the foot of the file, and the
``[Unreleased]`` link compares the latest release with ``HEAD``. Both are
hand-kept. After 1.1.0 shipped, the ``[1.1.0]`` definition was never added
(the docs site rendered a literal ``[1.1.0]``) and ``[Unreleased]`` still
compared from v1.0.2, so readers and release tooling saw the wrong diff.
Nothing failed, because nothing looked.

Checks:

- every bracketed version heading has a ``[x.y.z]: <url>`` definition, and
  that URL names the tag ``vx.y.z`` exactly;
- ``[Unreleased]`` has a definition that compares from ``v<latest>`` to
  ``HEAD``, where ``<latest>`` is the first version heading below it;
- no version definition is left without a heading.

Exit codes: ``0`` when clean, ``1`` on any finding, ``2`` when the file
cannot be read.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_HEADING = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)
_DEFINITION = re.compile(r"^\[([^\]]+)\]:\s*(\S+)\s*$", re.MULTILINE)
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def _names_tag(url: str, version: str) -> bool:
    """True when *url* references the tag ``v<version>`` and no longer tag."""
    return re.search(rf"(?<![\w.])v{re.escape(version)}(?![\w.])", url) is not None


def find_problems(text: str) -> list[str]:
    """Return one human-readable message per link-definition defect."""
    headings = _HEADING.findall(text)
    definitions = dict(_DEFINITION.findall(text))
    versions = [h for h in headings if _VERSION.match(h)]
    problems: list[str] = []

    for version in versions:
        url = definitions.get(version)
        if url is None:
            problems.append(f"[{version}]: heading has no link definition")
        elif not _names_tag(url, version):
            problems.append(f"[{version}]: link {url} does not point at v{version}")

    if "Unreleased" in headings:
        url = definitions.get("Unreleased")
        if url is None:
            problems.append("[Unreleased]: heading has no link definition")
        elif versions:
            latest = versions[0]
            expected = f"/compare/v{latest}...HEAD"
            if not url.endswith(expected):
                problems.append(
                    f"[Unreleased]: link {url} must compare from v{latest} "
                    f"(the latest heading) and end with {expected}"
                )

    for label in definitions:
        if _VERSION.match(label) and label not in versions:
            problems.append(f"[{label}]: link definition has no heading")
    return problems


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--changelog",
        type=Path,
        default=REPO_ROOT / "CHANGELOG.md",
        help="Path to the changelog (default: the repository CHANGELOG.md).",
    )
    args = parser.parse_args(argv)
    try:
        text = args.changelog.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"check-changelog-links: cannot read {args.changelog}: {exc}",
            file=sys.stderr,
        )
        return 2

    problems = find_problems(text)
    if problems:
        print(f"check-changelog-links: {len(problems)} finding(s) in {args.changelog}")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("check-changelog-links: OK — every version heading has a link definition")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
