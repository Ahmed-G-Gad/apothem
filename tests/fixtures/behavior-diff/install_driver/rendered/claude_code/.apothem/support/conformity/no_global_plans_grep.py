# SPDX-License-Identifier: MIT

"""Walk the git index for tracked plans paths; fail when found.

Why this validator exists. The Plans Discipline at spec section 3
forbids planning artifacts at any global location and at the
ecosystem root. Plans live at the sole canonical
``<project-root>/.apothem/plans/`` tree and are gitignored — they
never enter a git history. A plans path (under ``.apothem/plans/`` or
a legacy ``.plans/``) appearing in ``git ls-files`` is direct evidence
that the discipline has lapsed: either the gitignore is missing the
pattern, the ``.gitignore`` has been bypassed via ``git add --force``,
or a nested project's plans directory has been tracked by mistake.

Why git-index, not filesystem. The recursion case at spec section 3
(the apothem source repository itself contains a plans tree while it is
being authored — and, for the Claude Code harness specifically, that
working tree lives under ``~/.claude/``) is resolved precisely because
the on-disk plans tree is gitignored. Walking the filesystem would flag
the in-flight suite as a violation; walking the git index returns clean
by construction. The validator's surface IS the git index — the
source-of-truth for "what ships with this repository."

Detection strategy. The validator runs ``git ls-files`` from the
root, filters the output for entries under any plans directory
(``.apothem/plans/`` or a legacy ``.plans/``, top-level or nested), and
excludes the documented anti-pattern references inside
``site/content/docs/reference/plans-discipline.mdx`` (the file is allow-
listed wholesale because the validator inspects path entries, not
file contents — and the file's path itself does not match the plans
pattern).

Filesystem stray-suite sweep (additive). The git-index check above is
blind to a plans directory that exists on disk but is untracked — a
stray suite materialized at a non-canonical location (a nested sub-tree,
a sibling tree, or a legacy ``<root>/.plans`` that has not yet been
upgraded) escapes ``git ls-files`` entirely because it is gitignored or
simply not yet added. The suite-locality invariant fixes exactly one
canonical plans tree per project: ``<root>/.apothem/plans/``. Any other
on-disk plans directory under the root — including a legacy
``<root>/.plans`` an operator upgrades via ``apothem migrate-workspace``
— is a stray suite and a Plans-Locality violation. The sweep walks the
filesystem (skipping the vendored / generated / VCS trees that carry
upstream conventions or machine state) and flags every plans directory
that is not the canonical ``<root>/.apothem/plans``. The two checks are
complementary: the git-index check catches a *tracked* plans path; the
filesystem sweep catches an *untracked stray* plans directory the index
check is blind to.

Exit semantics. Exits 0 when no findings; exits 2 on any finding.
The exit-2 convention matches the conformity-gate orchestrator's
EXIT_FAIL constant.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "no-global-plans-grep"
RULE_ANCHOR: Final[str] = "CLAUDE.md Plans Discipline (no global plans)"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# Pattern for any path containing a plans-suite directory segment. The sole
# canonical project-local plans location is `.apothem/plans/` (the shared
# Apothem working directory's plans child); the legacy `.plans/` layout is no
# longer canonical — operators upgrade an existing `.plans` tree via
# `apothem migrate-workspace`. Both layouts are gitignored, so a tracked path
# under EITHER is the same discipline lapse and is flagged for leak detection.
#
# Matches `.plans/foo`, `subdir/.plans/bar`, `.apothem/plans/foo`,
# `subdir/.apothem/plans/bar`, but does NOT match `plans-discipline.md` (no
# trailing slash), `my.plans/x.md` (no leading boundary), or a non-`plans`
# child of `.apothem/` such as `.apothem/memory/` (operator data, not a plan).
_PLANS_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|/)(?:\.plans|\.apothem/plans)/"
)

# Directory names the filesystem stray-suite sweep does NOT descend into.
# Vendored / generated / VCS / cache trees carry upstream or machine state, not
# apothem-authored content; a `.plans/` directory inside any of them is not a
# stray apothem plan suite. Pruning them also keeps the walk fast.
_SWEEP_SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        "_vendor",
        "node_modules",
        "dist",
        "site/dist",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        "__pycache__",
        ".venv",
        "venv",
    }
)


@dataclass(frozen=True)
class Finding:
    """One tracked-in-git path under a .plans/ directory."""

    path: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result for a single git-index + filesystem sweep."""

    grep: str
    root: str
    tracked_count: int
    passed: bool
    stray_plans_count: int = 0
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, tracked_count,
        stray_plans_count, passed, findings}``; each finding is flattened
        through ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "tracked_count": self.tracked_count,
            "stray_plans_count": self.stray_plans_count,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _git_ls_files(root: Path) -> list[str]:
    """Return the git-tracked file list under root.

    Raises ``RuntimeError`` when ``git`` is unavailable or root is not
    a git repository — both are operator errors the caller surfaces.
    """
    try:
        completed = subprocess.run(  # noqa: S603 — trusted invocation: literal argv against git
            ["git", "-C", str(root), "ls-files"],  # noqa: S607 — PATH-resolved git is acceptable for a developer-tool validator; full-path resolution would require host-discovery and breaks portability across operator setups.
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            f"git ls-files failed under {root!s}: {stderr or 'no stderr'}"
        ) from exc
    return [line for line in completed.stdout.splitlines() if line]


def _sweep_stray_plans_dirs(
    root: Path, tracked_plans_dirs: frozenset[str]
) -> list[Finding]:
    """Walk the filesystem under root; flag *untracked* stray plans dirs.

    A stray suite is any on-disk plans directory that is not the sole canonical
    project-local location ``<root>/.apothem/plans`` (the shared Apothem working
    directory's plans child). Any ``.plans`` directory (including a legacy
    ``<root>/.plans`` — operators upgrade it via ``apothem migrate-workspace``),
    or any ``.apothem/plans`` directory under a non-root ``.apothem`` (e.g. a
    nested ``sub/.apothem/plans`` analogous to a global ``~/.apothem/plans``),
    is a stray and a Plans-Locality violation.

    The walk prunes the vendored / generated / VCS / cache trees in
    ``_SWEEP_SKIP_DIRS`` so a plans directory inside one of those (upstream or
    machine state, never an apothem plan suite) is not flagged. It descends into
    ``.apothem`` directories (they hold operator memory/learning/contexts data
    alongside plans) but never descends into a plans tree itself or into the
    ``.apothem`` data children — only the ``plans`` child of an ``.apothem``
    directory is plans-relevant. The check is **additive and non-overlapping**
    with the git-index check: a plans directory whose contents are already
    git-tracked is reported there, so the sweep skips it via
    ``tracked_plans_dirs`` to avoid double-reporting. The sweep's unique value is
    the *untracked* stray. Returns an empty list when the filesystem is
    unreadable (the git-index check still carries the verdict).
    """
    findings: list[Finding] = []
    try:
        resolved_root = root.resolve()
    except (OSError, RuntimeError):
        return findings
    canonical_new = (resolved_root / ".apothem" / "plans").resolve()
    canonical = {canonical_new}

    def _record_stray(entry: Path, rel: str) -> None:
        """Append a stray finding for a plans directory unless it is canonical
        or already covered by the git-index check."""
        already_tracked = rel in tracked_plans_dirs
        if entry.resolve() in canonical or already_tracked:
            return
        findings.append(
            Finding(
                path=f"{rel}/",
                detail=(
                    "an untracked stray plans directory exists on disk outside "
                    "the sole canonical project-local <root>/.apothem/plans tree; "
                    "there is exactly one plans tree per project per the "
                    "suite-locality invariant — relocate the stray suite, or run "
                    "`apothem migrate-workspace` to upgrade a legacy <root>/.plans "
                    "tree"
                ),
            )
        )

    stack: list[Path] = [resolved_root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except (OSError, PermissionError):
            continue
        for entry in entries:
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue
            if not is_dir:
                continue
            name = entry.name
            if name in _SWEEP_SKIP_DIRS:
                continue
            rel = entry.relative_to(resolved_root).as_posix()
            if name == ".plans":
                _record_stray(entry, rel)
                # Do not descend into a .plans/ tree (it is suite content, not a
                # place a nested .plans/ should appear).
                continue
            if name == ".apothem":
                # An ``.apothem`` directory holds operator data
                # (memory/learning/contexts) plus the plans child. Inspect only
                # the ``plans`` child for stray-suite detection; descend no
                # further into the data children.
                plans_child = entry / "plans"
                try:
                    if plans_child.is_dir():
                        _record_stray(plans_child, f"{rel}/plans")
                except OSError:
                    pass
                continue
            stack.append(entry)
    return findings


def _tracked_plans_dirs(tracked: list[str]) -> frozenset[str]:
    """Return the set of plans-segment directory paths the git index covers.

    For each tracked path matching ``(.../)?(.plans|.apothem/plans)/...``,
    extract the directory portion up to and including the plans segment (e.g.
    ``subdir/.plans/x.md`` -> ``subdir/.plans``; ``.plans/a.md`` -> ``.plans``;
    ``sub/.apothem/plans/x.md`` -> ``sub/.apothem/plans``;
    ``.apothem/plans/a.md`` -> ``.apothem/plans``). The sweep uses this set to
    skip already-tracked plans directories so they are not double-counted across
    the git-index check and the filesystem sweep.
    """
    dirs: set[str] = set()
    for path in tracked:
        match = _PLANS_PATH_RE.search(path)
        if not match:
            continue
        # The match spans the leading-boundary slash (when present) plus the
        # plans segment and its trailing slash, e.g. "/.apothem/plans/" or
        # "/.plans/". Trim the trailing slash to leave the directory path up to
        # and including the plans segment.
        end = match.end() - 1  # drop the trailing '/'
        dir_path = path[:end]
        # Strip a leading separator the boundary group may have consumed when the
        # segment was not at the path start.
        dirs.add(dir_path.lstrip("/") if match.start() != 0 else dir_path)
    return frozenset(dirs)


def check(root: Path) -> GrepResult:
    """Walk the git index + filesystem under root; flag stray .plans/ paths.

    Two complementary checks: (1) the git-index check flags any *tracked*
    ``.plans/`` or ``.apothem/plans/`` path (a planning artifact that has
    entered git history); (2) the filesystem stray-suite sweep flags any
    *untracked* on-disk plans directory that is not the sole canonical
    ``<root>/.apothem/plans`` (a stray suite the index check is blind to).
    Either check's finding fails the validator.
    """
    tracked = _git_ls_files(root)
    findings: list[Finding] = []
    for path in tracked:
        if _PLANS_PATH_RE.search(path):
            findings.append(
                Finding(
                    path=path,
                    detail=(
                        "plans path is tracked in git; planning artifacts MUST "
                        "live in the gitignored project-local "
                        "<project-root>/.apothem/plans/ tree per spec section 3"
                    ),
                )
            )
    stray = _sweep_stray_plans_dirs(root, _tracked_plans_dirs(tracked))
    findings.extend(stray)
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        tracked_count=len(tracked),
        stray_plans_count=len(stray),
        passed=not findings,
        findings=findings,
    )


def _main(argv: list[str]) -> int:
    # Imported here, not at module top: ``check()`` stays stdlib-only; only
    # the command-line entry needs the shared parser and report stamp.
    from apothem.conformity._grep_base import finish_root_report, parse_root_args

    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    try:
        result = check(root)
    except RuntimeError as exc:
        sys.stderr.write(f"{GREP_NAME}: {exc}\n")
        return EXIT_FAIL
    return finish_root_report(
        result.to_json(), passed=result.passed, inspected=result.tracked_count
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
