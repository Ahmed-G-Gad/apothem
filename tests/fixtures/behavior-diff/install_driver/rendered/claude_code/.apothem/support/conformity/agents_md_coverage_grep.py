# SPDX-License-Identifier: MIT

"""Flag stale agent-companion files under the root-only AGENTS.md convention.

Why this enforcement exists. The repository carries a single agent-facing
canon at the root ``AGENTS.md``; per-folder operating guidance lives in each
folder's ``README.md``, which serves both the human reader and the agent
reader. Per-folder ``AGENTS.md`` companions are no longer required — a
meaningful folder without one passes. The one defect this sweep still guards
is staleness: a per-folder companion that an author kept (the rare standalone
companion the convention permits) must not fall behind its folder after the
folder's artifacts or conventions changed. An absent companion is never a
finding; only a present, committed-but-stale companion is.

The meaningful-folder set. A folder is *meaningful* when it is navigable —
a contributor or an agent reasons about it as a unit — and load-bearing. The
enumeration is the navigable-folder set the README convention applies to; it
is retained here as the source-of-truth for the freshness check's
folder-ownership map and is reported as ``folders_inspected`` for information.
The set is the union of two reproducible rules, minus a fixed exclusion list:

- **(A) Companion-anchored.** Any folder that already carries a contributor
  ``README.md`` directly. Test-fixture leaf dirs (whose README is itself the
  subject of a presence check) and single-artifact example scaffolds are
  excluded — their README documents a fixture, not a navigable subsystem.
- **(B) Source-package.** Any ``src/apothem`` folder that directly contains a
  Python source file but carries no README — the harness adapter packages,
  the shared adapter helpers, the hook library. An agent operating inside one
  of these packages needs the same orientation a README-bearing folder gives.

Constant exclusions across both rules: vendored trees, generated trees, the
git/cache/ephemera directories, rendered harness-output template leaves, and
the plan-suite scratch. Including any of those would pollute fixtures or
describe machinery no contributor navigates by hand. Materialized
harness-output ``AGENTS.md`` files under ``src/apothem/harnesses/*/templates/``
are product surfaces, not companions, and are excluded by the same rule.

Freshness. A *present* per-folder companion is *stale* when its folder's
directly-contained artifacts were last committed more recently than the
companion itself. The signal is the git commit timestamp, not the filesystem
mtime: a checkout rewrites mtimes, so only commit history carries the truth of
"what changed when". A single ``git log`` pass buckets every tracked file to
its nearest meaningful-folder ancestor; a folder is stale when its newest
content commit postdates its committed companion's commit. Folders with no
companion on disk are skipped entirely, including one that was deleted —
absence is not a finding under the root-only convention. A companion whose
newest commit deleted it and that is on disk again has not been committed
since, so it is fresh like any other uncommitted companion. The
``AGENTS.md`` at the top of the repository is that canon, not a per-folder
companion, so it is never checked against the root folder's content. The log
names paths relative to the checked root and covers only history under it, so
a subtree root checks its own folders; the ``AGENTS.md`` of a subtree root is
a per-folder companion there, as it is in a run on the whole repository, so
both runs report it alike when that root carries a README (a source folder
without one is a meaningful folder only in a run on the repository, never as
a root). The log is read as text: a name with a control character comes in
git's quoted form and a byte that is not UTF-8 as U+FFFD, so a folder with
such a name is not matched. Where git history is unavailable (a shallow clone,
a non-git tree), freshness is skipped and the sweep reports a clean pass — it
never blocks a fresh clone. A git command that runs past its time limit (the
repository's own configuration can make git wait for ever), or a git that
refuses a checkout it found (another owner, a bad configuration line), is
different: the history is there but was not read, so the sweep reports a
``check_error`` and does not pass. The read of the whole history gets a long
limit of its own, so a large history is slow rather than a failure.

Posture. The result is advisory: the sweep surfaces findings and never
silent-blocks by default, honoring the agnostic gate posture. The orchestrator
reads the JSON ``advisory: true`` flag plus the inner ``passed`` field — a
stale-companion finding surfaces as ``advisory_findings_present`` without
gating the ``gate --all`` run. CI opts into strict enforcement separately.
``_main`` exits 0 on findings so the advisory posture holds; the verdict
travels in the JSON, not the exit code. It exits 2 only when the sweep did not
earn a verdict: it inspected no folder, or its ``git log`` ran past its limit.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

from apothem.conformity._git import run_git
from apothem.conformity._grep_base import (
    CHECK_ERROR_KEY,
    GitCheckError,
    GitFailedError,
    GitTimeoutError,
    finish_root_report,
    in_checkout,
    iter_tree_files,
    parse_root_args,
)

GREP_NAME: Final[str] = "agents-md-coverage-grep"
RULE_ANCHOR: Final[str] = "rules/agents-md-convention.md"

# Advisory posture: the sweep exits 0 on findings (the verdict travels in the
# JSON ``advisory`` / ``passed`` fields). ``finish_root_report`` returns the
# failure code itself for a sweep that inspected nothing or could not finish,
# so only the pass code is needed here.
EXIT_PASS: Final[int] = 0

# The agent-companion filename and its human-facing sibling.
COMPANION_NAME: Final[str] = "AGENTS.md"
README_NAME: Final[str] = "README.md"

# Bound the git invocations so a hung git cannot stall the sweep. A timeout is
# not missing history: the history is there but was not read, so the sweep
# reports a check error and does not pass. A quick ``git rev-parse`` gets the
# short limit: a repository whose own configuration makes git wait stops there.
GIT_TIMEOUT_SECONDS: Final[int] = 10
# The one read of the whole history gets a long limit, because its cost grows
# with the history: about 18 seconds for 200,000 commits on a test machine.
GIT_HISTORY_TIMEOUT_SECONDS: Final[int] = 300

# Path segments that mark a directory as out of scope wherever they appear.
# Vendored trees, generated output, caches, and ephemera are never navigable
# subsystems an agent reasons about by hand.
_EXCLUDED_SEGMENTS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        "node_modules",
        "_vendor",
        "dist",
        ".audit",
        ".plans",
        ".hypothesis",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "__pycache__",
    }
)

# Relative-path prefixes whose subtree is excluded as a whole.
_EXCLUDED_PREFIXES: Final[tuple[str, ...]] = (
    "site/dist",
    "site/node_modules",
)

# Rule-(A) carve-outs: a README under one of these is a fixture/example
# README, not a navigable-subsystem README. Matched as path substrings on the
# POSIX-relative folder path.
_FIXTURE_FOLDER_MARKERS: Final[tuple[str, ...]] = (
    "tests/scripts/inject-header/fixtures",
    "examples/minimal-",
)

# Rule-(B) scope: source-package folders live under this prefix.
_SOURCE_PACKAGE_PREFIX: Final[str] = "src/apothem"
_PYTHON_SUFFIX: Final[str] = ".py"


@dataclass(frozen=True)
class Finding:
    """One stale present per-folder agent-companion file."""

    surface: str
    kind: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated coverage result for a single sweep."""

    grep: str
    root: str
    folders_inspected: int
    freshness_checked: bool
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    # Why the freshness check could not finish (``git log`` ran past
    # ``GIT_TIMEOUT_SECONDS``); None otherwise.
    check_error: str | None = None

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, folders_inspected,
        freshness_checked, passed, findings, advisory}``, plus
        ``check_error`` when it is set; each finding is flattened through
        ``dataclasses.asdict``.
        """
        payload: dict[str, object] = {
            "grep": self.grep,
            "root": self.root,
            "folders_inspected": self.folders_inspected,
            "freshness_checked": self.freshness_checked,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
            "advisory": True,
        }
        if self.check_error is not None:
            payload[CHECK_ERROR_KEY] = self.check_error
        return json.dumps(payload, indent=2)


def _has_excluded_segment(rel_posix: str) -> bool:
    """Return True iff any path segment marks the path out of scope."""
    if not rel_posix or rel_posix == ".":
        return False
    if any(rel_posix == p or rel_posix.startswith(p + "/") for p in _EXCLUDED_PREFIXES):
        return True
    return any(segment in _EXCLUDED_SEGMENTS for segment in rel_posix.split("/"))


def _is_fixture_folder(rel_posix: str) -> bool:
    """Return True iff a folder is a test-fixture or single-artifact example leaf."""
    if "/" in rel_posix:
        parent, _, leaf = rel_posix.rpartition("/")
        # tests/conformity/<matcher>/{fail,pass} — the README is the grep subject.
        if leaf in {"fail", "pass"} and parent.startswith("tests/conformity/"):
            return True
    return any(marker in rel_posix for marker in _FIXTURE_FOLDER_MARKERS)


def _is_harness_template_leaf(rel_posix: str) -> bool:
    """Return True iff a folder is a rendered harness-output template leaf."""
    parts = rel_posix.split("/")
    # src/apothem/harnesses/<name>/templates[/...]
    return (
        len(parts) >= 5
        and parts[:3] == ["src", "apothem", "harnesses"]
        and "templates" in parts[4:5]
    )


def _rel_posix(path: Path, root_resolved: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(root_resolved).as_posix()
    except ValueError:
        return None
    return "." if rel == "" else rel


def meaningful_folders(root: Path) -> list[str]:
    """Enumerate the meaningful-folder set under ``root``.

    Pre-conditions: ``root`` is the repository root (or a subtree).
    Post-conditions: returns the sorted, deduplicated POSIX-relative folder
    paths (``.`` denotes the root) that satisfy rule (A) or rule (B) and pass
    the constant exclusions. A folder inside a nested git checkout (a
    worktree, a submodule, a nested clone) belongs to another repository and is
    never listed. Re-running over an unchanged tree yields the identical set —
    the enumeration is the single source of truth the presence/freshness check
    and the documentation convention both consume.
    """
    root_resolved = root.resolve()
    folders: set[str] = set()

    # Rule (A): folders carrying a contributor README, minus fixture/example leaves.
    for readme in iter_tree_files(
        root, names=(README_NAME,), extra_prune=_EXCLUDED_SEGMENTS
    ):
        rel = _rel_posix(readme.parent, root_resolved)
        if rel is None or _has_excluded_segment(rel):
            continue
        if _is_fixture_folder(rel):
            continue
        folders.add(rel)

    # Rule (B): src/apothem source-package folders without a README, minus
    # vendored trees and rendered harness-template leaves.
    for py_file in iter_tree_files(
        root, (_PYTHON_SUFFIX,), extra_prune=_EXCLUDED_SEGMENTS
    ):
        rel = _rel_posix(py_file.parent, root_resolved)
        if rel is None or rel == ".":
            continue
        if not (
            rel == _SOURCE_PACKAGE_PREFIX
            or rel.startswith(_SOURCE_PACKAGE_PREFIX + "/")
        ):
            continue
        if _has_excluded_segment(rel) or _is_harness_template_leaf(rel):
            continue
        if (py_file.parent / README_NAME).is_file():
            continue
        folders.add(rel)

    return sorted(folders)


@dataclass(frozen=True)
class _History:
    """What one read of the history under a root found.

    ``times`` maps each path, relative to the root, to the commit time of the
    newest commit that touched it. ``deleted`` holds the paths that commit
    deleted. ``root_is_top`` is True when the root is the top folder of the
    repository's work tree.
    """

    times: dict[str, int]
    deleted: frozenset[str]
    root_is_top: bool


def _read_history(root: Path) -> _History | None:
    """Read the commit history under *root* in one ``git log`` pass.

    First ``git rev-parse --show-prefix --verify --quiet HEAD`` within
    ``GIT_TIMEOUT_SECONDS`` finds out whether there is a history to read, and
    its first output line (the path of *root* below the top of the work tree,
    empty at the top) says whether *root* is that top. Then one ``git log``
    pass within ``GIT_HISTORY_TIMEOUT_SECONDS``, newest commit first: the
    first time a path is seen is its last-touching commit, and
    ``--name-status`` says whether that commit deleted it.
    ``--relative -- .`` limits the pass to history under *root* and names
    paths relative to it, so they match :func:`meaningful_folders` when *root*
    is a subtree of the repository. git runs through :func:`run_git`, which
    turns off the repository's program-running settings (a signature check,
    say) and prints non-ASCII path names as they are, decoded as UTF-8.
    Returns None when git history is unavailable (no repository, no commit
    yet, or git absent) so the caller degrades to a presence-only sweep.
    Raises :class:`~apothem.conformity._grep_base.GitTimeoutError` when a git
    command runs past its limit, and
    :class:`~apothem.conformity._grep_base.GitFailedError` when git fails
    although *root* is inside a checkout (git refused the repository) or
    after it found the history: in both cases the history is there but was
    not read.
    """
    try:
        head = run_git(
            ["rev-parse", "--show-prefix", "--verify", "--quiet", "HEAD"],
            cwd=root,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitTimeoutError("git rev-parse", GIT_TIMEOUT_SECONDS) from exc
    except OSError:
        return None
    if head.returncode != 0:
        # Exit 1: HEAD names no commit yet. Any other failure outside a
        # checkout is the no-repository case; in a checkout git refused it.
        if head.returncode != 1 and in_checkout(root):
            raise GitFailedError("git rev-parse", head.returncode)
        return None
    try:
        completed = run_git(
            [
                "log",
                "--format=%x1e%ct",
                "--name-status",
                "--no-renames",
                "--relative",
                "--",
                ".",
            ],
            cwd=root,
            timeout=GIT_HISTORY_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitTimeoutError("git log", GIT_HISTORY_TIMEOUT_SECONDS) from exc
    except OSError:
        return None
    if completed.returncode != 0:
        raise GitFailedError("git log", completed.returncode)
    if not completed.stdout:
        return None

    times: dict[str, int] = {}
    deleted: set[str] = set()
    current_ct: int | None = None
    # Split on "\n" only: str.splitlines() also breaks at the \x1e record
    # marker, which would strip it from every header line.
    for raw_line in completed.stdout.split("\n"):
        if raw_line.startswith("\x1e"):
            stamp = raw_line[1:].strip()
            current_ct = int(stamp) if stamp.isdigit() else None
            continue
        # A change line is "<status>\t<name>". The name is as git printed it:
        # core.quotePath=false keeps a non-ASCII name unquoted, and stripping
        # would change a name that starts or ends with a space.
        status, tab, path = raw_line.partition("\t")
        if not tab or not path or current_ct is None:
            continue
        # Newest-first: keep only the first (most recent) commit per path.
        if path not in times:
            times[path] = current_ct
            if status == "D":
                deleted.add(path)
    # The first line of the rev-parse output is the path of the root below the
    # top of the work tree; it is empty when the root is that top.
    prefix = head.stdout.split("\n", 1)[0]
    return _History(times=times, deleted=frozenset(deleted), root_is_top=not prefix)


def _owning_folder(file_posix: str, folder_set: frozenset[str]) -> str:
    """Map a tracked file to its nearest meaningful-folder ancestor.

    A top-level file maps to ``.``. A file under a non-meaningful subdir walks
    up to the nearest meaningful ancestor; a file under a child meaningful
    folder is owned by that child, never the parent — ownership is disjoint.
    """
    parent = file_posix.rpartition("/")[0]
    while parent:
        if parent in folder_set:
            return parent
        parent = parent.rpartition("/")[0]
    return "."


def check(root: Path) -> GrepResult:
    """Enumerate meaningful folders; flag only present, stale companions.

    Pre-conditions: ``root`` is the repository root (or an arbitrary subtree).
    Post-conditions: under the root-only convention, a meaningful folder
    without a per-folder ``AGENTS.md`` is never a finding — absence passes.
    ``result.passed`` is True iff (when git history is available) no *present*,
    committed per-folder companion is stale relative to its folder's
    directly-contained artifacts; it is always True when git history is
    unavailable. A git command past its time limit, or a git that refused the
    repository, is not missing history: ``passed`` is False and
    ``check_error`` names the command.
    """
    folders = meaningful_folders(root)
    folder_set = frozenset(folders)
    findings: list[Finding] = []

    # Freshness — git-commit truth; skipped when history is unavailable.
    check_error: str | None = None
    try:
        history = _read_history(root)
    except GitCheckError as exc:
        history, check_error = None, str(exc)
    freshness_checked = history is not None
    if history is not None:
        content_ct: dict[str, int] = {}
        companion_ct: dict[str, int] = {}
        for path, ct in history.times.items():
            if _has_excluded_segment(path):
                continue
            owner = _owning_folder(path, folder_set)
            if path.rpartition("/")[2] == COMPANION_NAME:
                companion_folder = path.rpartition("/")[0] or "."
                # The AGENTS.md at the top of the repository is its canon, not
                # a per-folder companion, so it has no folder to fall behind.
                # The AGENTS.md of a subtree root is a per-folder companion,
                # as a run on the whole repository sees it.
                is_canon = companion_folder == "." and history.root_is_top
                # A companion whose newest commit deleted it is absent, and
                # absence passes; one that is on disk again has not been
                # committed since, so it is fresh. A committed companion that
                # is gone from disk is absent too.
                if (
                    not is_canon
                    and path not in history.deleted
                    and companion_folder in folder_set
                    and (root / path).is_file()
                ):
                    companion_ct[companion_folder] = ct
                continue
            content_ct[owner] = max(content_ct.get(owner, 0), ct)
        for folder in folders:
            # Only committed companions can be stale; an uncommitted one is fresh.
            if folder not in companion_ct:
                continue
            newest_content = content_ct.get(folder, 0)
            if newest_content > companion_ct[folder]:
                surface = (
                    COMPANION_NAME if folder == "." else f"{folder}/{COMPANION_NAME}"
                )
                findings.append(
                    Finding(
                        surface=surface,
                        kind="stale-companion",
                        detail=(
                            f"'{folder}' content changed after its {COMPANION_NAME} was "
                            "last updated; refresh the companion in the same change-set"
                        ),
                    )
                )

    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        folders_inspected=len(folders),
        freshness_checked=freshness_checked,
        passed=not findings and check_error is None,
        findings=findings,
        check_error=check_error,
    )


def _main(argv: list[str]) -> int:
    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    result = check(root)
    # Advisory posture: exit 0 on findings so the sweep never silent-blocks by
    # default. The verdict travels in the JSON — the orchestrator reads the
    # ``advisory: true`` flag plus the inner ``passed`` field (via
    # ``gate._advisory_verdict``) and surfaces a stale-companion finding as
    # ``advisory_findings_present`` without failing the ``gate --all`` run.
    # CI opts into strict enforcement separately. A sweep that inspected no
    # folder fails: that is a misconfiguration, not advisory drift. So does a
    # sweep whose ``git log`` ran past its limit: it did not finish.
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=result.folders_inspected,
        advisory=True,
        check_error=result.check_error,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
