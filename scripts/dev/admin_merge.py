# SPDX-License-Identifier: MIT

"""Solo-maintainer self-merge ceremony for PRs.

Why this exists. The repository's main-branch protection requires PR
review approval (``required_approving_review_count=1``) and is
admin-enforced (``enforce_admins=true``). This combination intentionally
prevents the maintainer from merging their own PR via plain ``--admin``
override. The canonical resolution is the temp-toggle ceremony documented
at ``site/content/docs/runbooks/solo-maintainer-merge.mdx``: relax the approver-count to 0,
merge with admin override, restore to the original count.

This wrapper executes the toggle-merge-restore sequence atomically with
``try``/``finally`` rollback safety so the protection is never left in
its relaxed state on failure.

Usage::

    python scripts/dev/admin_merge.py <pr-number> [<owner>/<repo>]

The ``owner/repo`` slug defaults to the current ``gh repo view`` value.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Final

_PROTECTION_PATH_TEMPLATE: Final[str] = (
    "repos/{repo}/branches/main/protection/required_pull_request_reviews"
)


class AdminMergeError(RuntimeError):
    """Raised when the temp-toggle ceremony cannot complete."""


def _run(cmd: list[str], *, capture: bool = False) -> str:
    """Invoke ``cmd`` via subprocess; return stdout when ``capture`` is true."""
    result = subprocess.run(  # noqa: S603 (cmd is constructed from typed inputs)
        cmd,
        capture_output=capture,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise AdminMergeError(
            f"command failed (exit {result.returncode}): {' '.join(cmd)}\n{stderr}"
        )
    return result.stdout if capture else ""


def _resolve_repo() -> str:
    """Return the ``owner/repo`` slug for the current working directory."""
    out = _run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        capture=True,
    )
    return out.strip()


def _capture_approver_count(repo: str) -> int:
    """Return the current ``required_approving_review_count`` so restore is exact."""
    path = _PROTECTION_PATH_TEMPLATE.format(repo=repo)
    out = _run(
        ["gh", "api", path, "--jq", ".required_approving_review_count"],
        capture=True,
    )
    return int(out.strip())


def _set_approver_count(repo: str, count: int) -> None:
    """Toggle ``required_approving_review_count`` to ``count``."""
    path = _PROTECTION_PATH_TEMPLATE.format(repo=repo)
    _run(
        [
            "gh",
            "api",
            path,
            "-X",
            "PATCH",
            "-F",
            f"required_approving_review_count={count}",
        ]
    )


def admin_merge(pr_number: int, repo: str | None = None) -> None:
    """Execute the toggle-merge-restore ceremony for ``pr_number``.

    Args:
        pr_number: The pull request to squash-merge.
        repo: Repository slug ``owner/name``. Defaults to the slug ``gh
            repo view`` returns for the current working directory.

    Raises:
        AdminMergeError: When any command in the ceremony fails. The
            ``finally`` clause restores the protection regardless.
    """
    target_repo = repo or _resolve_repo()
    original_count = _capture_approver_count(target_repo)
    print(
        f"Captured original required_approving_review_count={original_count}",
        file=sys.stderr,
    )

    try:
        print("Relaxing required_approving_review_count to 0 ...", file=sys.stderr)
        _set_approver_count(target_repo, 0)

        print(
            f"Squash-merging PR #{pr_number} on {target_repo} ...",
            file=sys.stderr,
        )
        _run(
            [
                "gh",
                "pr",
                "merge",
                str(pr_number),
                "--repo",
                target_repo,
                "--squash",
                "--delete-branch",
                "--admin",
            ]
        )
        print("Merge succeeded.", file=sys.stderr)
    finally:
        print(
            f"Restoring required_approving_review_count to {original_count} ...",
            file=sys.stderr,
        )
        try:
            _set_approver_count(target_repo, original_count)
        except AdminMergeError as exc:
            print(
                f"WARNING: restore failed; manual intervention required: {exc}",
                file=sys.stderr,
            )
            raise


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Solo-maintainer self-merge ceremony (temp-toggle).",
    )
    parser.add_argument("pr_number", type=int, help="PR to merge")
    parser.add_argument(
        "repo",
        nargs="?",
        default=None,
        help="owner/repo slug (default: derived from gh repo view)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 on success, 1 on ceremony failure."""
    args = _parse_args(argv)
    try:
        admin_merge(args.pr_number, args.repo)
    except AdminMergeError as exc:
        print(f"admin_merge failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
