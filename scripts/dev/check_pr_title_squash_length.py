# SPDX-License-Identifier: MIT

"""Reject a PR title that the squash-merge suffix would push over the limit.

GitHub's squash merge composes the merge-commit subject as
``<pr title> (#<number>)``. The repository's Conventional Commits rule caps a
subject at ``MAX_SUBJECT_LEN`` characters and the conformity gate enforces it
against HEAD, so a title that fits on its own can still produce a
non-conforming commit the moment it lands: PR #6's title was 68 characters,
the merge commit was 73, and every ``quality`` job on ``main`` failed at the
conformity step while the branch had been green.

The branch cannot catch this by inspecting its own commits — the offending
subject does not exist until the merge. This check evaluates the prospective
merge subject instead, so the failure surfaces on the PR that causes it.

The limit is imported from the validator rather than restated, so the two can
never disagree.

Usage::

    python scripts/dev/check_pr_title_squash_length.py --title "..." --number 6

In CI the values come from the pull_request event payload.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Vendored dependencies first, then the engine — the same order bin/apothem.mjs
# uses, so this runs before any toolchain install (see assemble_plugin_tree.py).
for _path in (_REPO_ROOT / "src" / "apothem" / "_vendor", _REPO_ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from apothem.conformity.conventional_commit_grep import (  # noqa: E402
    MAX_SUBJECT_LEN,
)


def squash_subject(title: str, number: int) -> str:
    """Return the subject GitHub composes for a squash merge of this PR."""
    return f"{title} (#{number})"


def check(title: str, number: int) -> int:
    """Report whether the prospective squash subject fits the limit.

    Args:
        title: The pull-request title.
        number: The pull-request number.

    Returns:
        ``0`` when the composed subject fits, ``1`` when it is too long.
    """
    subject = squash_subject(title, number)
    if len(subject) <= MAX_SUBJECT_LEN:
        print(
            f"pr-title-squash-length: OK — merge subject is {len(subject)} "
            f"of {MAX_SUBJECT_LEN} chars"
        )
        return 0

    budget = MAX_SUBJECT_LEN - (len(subject) - len(title))
    print(
        f"error: the squash-merge subject would be {len(subject)} characters, "
        f"over the {MAX_SUBJECT_LEN}-character limit.\n"
        f"  merge subject: {subject}\n"
        f"  GitHub appends ' (#{number})' to the PR title on squash merge, so\n"
        f"  the title itself must be at most {budget} characters "
        f"(currently {len(title)}).\n"
        f"  Shorten the PR title by {len(title) - budget} character(s) and "
        f"re-run this check.",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--title", required=True, help="Pull-request title")
    parser.add_argument("--number", required=True, type=int, help="PR number")
    args = parser.parse_args(argv)
    return check(args.title, args.number)


if __name__ == "__main__":
    raise SystemExit(main())
