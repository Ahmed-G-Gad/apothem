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
companion on disk are skipped entirely — absence is not a finding under the
root-only convention. Where git history is unavailable (a shallow clone, a
non-git tree), freshness is skipped and the sweep reports a clean pass — it
never blocks a fresh clone.

Posture. The result is advisory: the sweep surfaces findings and never
silent-blocks by default, honoring the agnostic gate posture. The orchestrator
reads the JSON ``advisory: true`` flag plus the inner ``passed`` field — a
stale-companion finding surfaces as ``advisory_findings_present`` without
gating the ``gate --all`` run. CI opts into strict enforcement separately.
``_main`` always exits 0 so the advisory posture holds regardless of findings;
the verdict travels in the JSON, not the exit code.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "agents-md-coverage-grep"
RULE_ANCHOR: Final[str] = "rules/agents-md-convention.md"

# Advisory posture: the sweep always exits 0 (the verdict travels in the JSON
# ``advisory`` / ``passed`` fields), so only the pass code is needed here.
EXIT_PASS: Final[int] = 0

# The agent-companion filename and its human-facing sibling.
COMPANION_NAME: Final[str] = "AGENTS.md"
README_NAME: Final[str] = "README.md"

# Bound the git invocation so a hung `git log` cannot stall the sweep; a
# timeout is treated as a transient git error and degrades to a clean pass.
GIT_TIMEOUT_SECONDS: Final[int] = 10

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

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, folders_inspected,
        freshness_checked, passed, findings, advisory}``; each finding is
        flattened through ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "folders_inspected": self.folders_inspected,
            "freshness_checked": self.freshness_checked,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
            "advisory": True,
        }
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
    the constant exclusions. Re-running over an unchanged tree yields the
    identical set — the enumeration is the single source of truth the
    presence/freshness check and the documentation convention both consume.
    """
    root_resolved = root.resolve()
    folders: set[str] = set()

    # Rule (A): folders carrying a contributor README, minus fixture/example leaves.
    for readme in root.rglob(README_NAME):
        if not readme.is_file():
            continue
        rel = _rel_posix(readme.parent, root_resolved)
        if rel is None or _has_excluded_segment(rel):
            continue
        if _is_fixture_folder(rel):
            continue
        folders.add(rel)

    # Rule (B): src/apothem source-package folders without a README, minus
    # vendored trees and rendered harness-template leaves.
    for py_file in root.rglob(f"*{_PYTHON_SUFFIX}"):
        if not py_file.is_file():
            continue
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


def _last_commit_times(root: Path) -> dict[str, int] | None:
    """Return a map of tracked-file POSIX path → last-commit unix timestamp.

    One ``git log`` pass, newest commit first: the first time a path is seen
    is its last-touching commit. Returns None when git history is unavailable
    (no repository, shallow clone with no log, git absent, or timeout) so the
    caller degrades to a presence-only sweep.
    """
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "log",
                "--format=%x1e%ct",
                "--name-only",
                "--no-renames",
            ],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0 or not completed.stdout:
        return None

    times: dict[str, int] = {}
    current_ct: int | None = None
    for raw_line in completed.stdout.splitlines():
        if raw_line.startswith("\x1e"):
            stamp = raw_line[1:].strip()
            current_ct = int(stamp) if stamp.isdigit() else None
            continue
        path = raw_line.strip()
        if not path or current_ct is None:
            continue
        # Newest-first: keep only the first (most recent) commit per path.
        if path not in times:
            times[path] = current_ct
    return times


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
    unavailable.
    """
    folders = meaningful_folders(root)
    folder_set = frozenset(folders)
    findings: list[Finding] = []

    # Freshness — git-commit truth; skipped when history is unavailable.
    commit_times = _last_commit_times(root)
    freshness_checked = commit_times is not None
    if commit_times is not None:
        content_ct: dict[str, int] = {}
        companion_ct: dict[str, int] = {}
        for path, ct in commit_times.items():
            if _has_excluded_segment(path):
                continue
            owner = _owning_folder(path, folder_set)
            if path.rpartition("/")[2] == COMPANION_NAME:
                companion_folder = path.rpartition("/")[0] or "."
                if companion_folder in folder_set:
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
        passed=not findings,
        findings=findings,
    )


def _main(argv: list[str]) -> int:
    # Imported here, not at module top: ``check()`` stays stdlib-only; only
    # the command-line entry needs the shared parser and report stamp.
    from apothem.conformity._grep_base import finish_root_report, parse_root_args

    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    result = check(root)
    # Advisory posture: exit 0 on findings so the sweep never silent-blocks by
    # default. The verdict travels in the JSON — the orchestrator reads the
    # ``advisory: true`` flag plus the inner ``passed`` field (via
    # ``gate._advisory_verdict``) and surfaces a stale-companion finding as
    # ``advisory_findings_present`` without failing the ``gate --all`` run.
    # CI opts into strict enforcement separately. A sweep that inspected no
    # folder fails: that is a misconfiguration, not advisory drift.
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=result.folders_inspected,
        advisory=True,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
