# SPDX-License-Identifier: MIT

"""Semver stability matcher (M15 mechanical fraction).

Why this enforcement exists. A breaking change to the public package surface
shipped without a MAJOR bump silently breaks every downstream importer that
pinned a compatible range; SemVer is the contract that lets consumers upgrade
safely, and this matcher is its mechanical floor.

Detects public-API surface changes that would constitute a breaking change
under semantic versioning without a corresponding MAJOR version bump in
`src/apothem/__init__.py`. Operates on Python source files in the public
package surface (`src/apothem/`, excluding `_*.py` private modules and
`conformity/` internals).

Breaking-change signals implemented (`compare_surfaces`):

  1. Removed public function / class / method (declaration disappeared
     between the staged content and the on-disk content).
  2. Added required parameter to existing public function / method.
  3. Removed entry from `__all__`.

Signals declared by the discipline but NOT yet implemented (tracked
follow-up — the mechanical fraction ships the three above first):

  * Removed public module entirely (module-level disappearance is not yet
    diffed; only symbol-level removals within a module are).
  * Changed function signature (parameter renamed at the same position;
    return-type annotation tightened from broader to narrower; default
    value removed from a previously-defaulted parameter).
  * Removed entry-point declared in `pyproject.toml` `[project.scripts]`.

The matcher fires in two modes:

* `--hook` (per-Write): runs against the staged Write/Edit content for a
  Python file under `src/apothem/`; checks the staged content against the
  on-disk version for the implemented breaking-change signals.
* `--staged` (per-change-set): runs `git diff --cached` against
  `src/apothem/`; aggregates the implemented signals across the whole staged
  change-set; cross-references the staged version bump in `__init__.py` to
  determine MAJOR-bump presence.

When breaking-change signals are detected without a corresponding MAJOR
bump, the matcher returns a HIGH-severity finding the orchestrator surfaces
as a gate FAIL.

The matcher does NOT block v0.x changes (semver permits breaking changes
at any non-MAJOR bump in 0.x). The check fires from v1.0.0 onward only.

Posture. On the change-set path (`--staged`) the matcher emits a JSON
``GrepResult`` payload and follows the package exit contract: ``EXIT_PASS``
(0) on a clean surface, ``EXIT_FAIL`` (2) when breaking-change findings
stand without a MAJOR bump. A git command on that path that runs past
``GIT_TIMEOUT_SECONDS``, or a git that refuses the checkout it runs in, leaves
the change set unread, so the payload then carries ``check_error`` and
``passed: false`` and the exit is ``EXIT_FAIL``.
The per-Write hook path emits the same payload.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

# Bound every gate-path git invocation so a hung `git cat-file`/`git diff`
# (filesystem lock, slow network-backed repo, large object, or a repository
# configuration that makes git wait) cannot block a commit indefinitely.
# Mirrors the convention in production_ready_pr_grep.py: a timeout does not
# pass, because the change set was not read, so the limit leaves room for a
# large index or object on a slow or busy machine.
GIT_TIMEOUT_SECONDS: Final[int] = 60

GREP_NAME: Final[str] = "semver-stability-grep"
RULE_ANCHOR: Final[str] = "M15 semver-stability"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2
STDIN_FLAG: Final[str] = "--stdin"
STAGED_FLAG: Final[str] = "--staged"

PUBLIC_PACKAGE = "src/apothem"
PRIVATE_PATTERN = re.compile(r"(^|/)_[^/]*\.py$")
CONFORMITY_INTERNAL = re.compile(r"/conformity/")
INIT_PATH = Path("src/apothem/__init__.py")


@dataclass(frozen=True)
class Finding:
    """One public-surface change weighed against the declared version bump.

    Pre-conditions: ``severity`` grades the break; ``bar`` names the stability
    bar the change crossed (a removed or renamed public symbol, a narrowed
    signature, a changed default); ``path`` locates the surface; ``message``
    states the observed break in operator-facing prose. Post-conditions: the
    finding is frozen and serialised through :meth:`as_dict`.
    """

    severity: str
    bar: str
    path: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        """Return this finding as a plain mapping.

        Carries an explicit serialiser rather than relying on
        ``dataclasses.asdict`` because the enclosing report composes findings
        into a bespoke payload.

        Post-conditions: the mapping carries ``{severity, bar, path,
        message}``.
        """
        return {
            "severity": self.severity,
            "bar": self.bar,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class GrepResult:
    """Aggregated breaking-change verdict for a single semver-stability sweep."""

    grep: str
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    # Why the change-set check could not finish (a git command ran past
    # ``GIT_TIMEOUT_SECONDS``, or git refused the checkout); None otherwise.
    check_error: str | None = None

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, passed, findings}``,
        plus ``check_error`` when it is set.
        """
        payload: dict[str, object] = {
            "grep": self.grep,
            "passed": self.passed,
            "findings": [f.as_dict() for f in self.findings],
        }
        if self.check_error is not None:
            # The same key as ``_grep_base.CHECK_ERROR_KEY``, spelled out so
            # the module stays stdlib-only at import.
            payload["check_error"] = self.check_error
        return json.dumps(payload, indent=2)


@dataclass(frozen=True)
class PublicSurface:
    """Public-API symbol inventory for a single Python module."""

    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = field(
        default_factory=dict
    )
    classes: dict[str, ast.ClassDef] = field(default_factory=dict)
    all_list: list[str] = field(default_factory=list)


def _is_public_name(name: str) -> bool:
    return not name.startswith("_")


def extract_public_surface(src: str) -> PublicSurface | None:
    """Parse Python source and extract the public-API symbol inventory."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    # The inventory is built in locals and the frozen ``PublicSurface`` is
    # constructed once at the end — the dataclass is a value container per the
    # cohort's frozen convention, so it is never mutated in place.
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    classes: dict[str, ast.ClassDef] = {}
    all_list: list[str] = []
    for node in tree.body:
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and _is_public_name(node.name):
            functions[node.name] = node
        elif isinstance(node, ast.ClassDef) and _is_public_name(node.name):
            classes[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, (ast.List, ast.Tuple))
                ):
                    all_list = [
                        elt.value
                        for elt in node.value.elts
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    ]
    return PublicSurface(functions=functions, classes=classes, all_list=all_list)


def _signature_required_params(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    """Return required (non-defaulted) positional parameter names."""
    args = func.args
    pos = args.posonlyargs + args.args
    defaults = list(args.defaults)
    # Defaults apply right-to-left across pos.
    n_required = len(pos) - len(defaults)
    return [a.arg for a in pos[:n_required]]


def compare_surfaces(
    old: PublicSurface, new: PublicSurface, path: str
) -> list[Finding]:
    """Return findings for public functions or classes removed between *old* and *new* (breaking changes)."""
    findings: list[Finding] = []

    # Removed public functions.
    for name in old.functions:
        if name not in new.functions:
            findings.append(
                Finding(
                    "HIGH",
                    "M15",
                    path,
                    f"public function `{name}` removed (breaking change)",
                )
            )

    # Removed public classes.
    for name in old.classes:
        if name not in new.classes:
            findings.append(
                Finding(
                    "HIGH",
                    "M15",
                    path,
                    f"public class `{name}` removed (breaking change)",
                )
            )

    # Added required parameter to existing function.
    for name, new_fn in new.functions.items():
        if name in old.functions:
            old_fn = old.functions[name]
            old_req = set(_signature_required_params(old_fn))
            new_req = set(_signature_required_params(new_fn))
            added = new_req - old_req
            if added:
                findings.append(
                    Finding(
                        "HIGH",
                        "M15",
                        path,
                        f"public function `{name}` gained required parameter(s) "
                        f"{sorted(added)} (breaking change)",
                    )
                )

    # __all__ entries removed.
    if old.all_list and new.all_list:
        removed = set(old.all_list) - set(new.all_list)
        if removed:
            findings.append(
                Finding(
                    "HIGH",
                    "M15",
                    path,
                    f"`__all__` entries removed: {sorted(removed)} (breaking change)",
                )
            )

    return findings


def _version_in(folder: Path) -> str | None:
    """Read ``apothem.__version__`` from the package below *folder*, or None."""
    init = folder / INIT_PATH
    if not init.exists():
        return None
    text = init.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else None


def current_version() -> str | None:
    """Read the on-disk apothem.__version__ value below the current folder."""
    return _version_in(Path())


def is_v0(version: str) -> bool:
    """Return True when *version* is in the ``0.x`` initial-development series.

    Pre-conditions: ``version`` is a dotted SemVer string. Post-conditions:
    returns ``True`` iff the major component is ``0``. Callers use this to relax
    the breaking-change bars, because SemVer §4 exempts ``0.y.z`` from the
    stability guarantee that governs ``1.0.0`` and later.
    """
    parts = version.split(".")
    return parts[0] == "0"


def major_bumped(staged_version: str, prior_version: str) -> bool:
    """Return True when *staged_version*'s major component exceeds *prior_version*'s."""
    s_major = int(staged_version.split(".")[0])
    p_major = int(prior_version.split(".")[0])
    return s_major > p_major


def check_hook(file_path: str, staged_content: str) -> list[Finding]:
    """Per-file PreToolUse check against the on-disk version."""
    p = Path(file_path)
    if not str(p).replace("\\", "/").startswith(PUBLIC_PACKAGE):
        return []
    if PRIVATE_PATTERN.search(str(p).replace("\\", "/")):
        return []
    if CONFORMITY_INTERNAL.search(str(p).replace("\\", "/")):
        return []

    version = current_version()
    if not version or is_v0(version):
        # v0.x permits breaking changes; M15 semver-stability does not fire.
        return []

    if not p.exists():
        return []  # new file — no prior surface to compare against.

    old_text = p.read_text(encoding="utf-8")
    old_surface = extract_public_surface(old_text)
    new_surface = extract_public_surface(staged_content)
    if old_surface is None or new_surface is None:
        return []
    return compare_surfaces(old_surface, new_surface, str(p))


def _git(
    label: str,
    *args: str,
    check: bool = False,
    file_names: bool = False,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` within ``GIT_TIMEOUT_SECONDS``.

    git runs in *cwd*, or in the current folder when it is None, through
    :func:`~apothem.conformity._git.run_git`, which turns off
    the repository's program-running settings; *file_names* reads a ``-z``
    list with every byte of each name kept. Raises
    :class:`~apothem.conformity._grep_base.GitTimeoutError`, naming the
    command as *label*, past the limit; :class:`OSError` when git cannot be
    started; and, with *check*, :class:`subprocess.CalledProcessError` on a
    non-zero exit.
    """
    # Imported here, not at module top, so the module stays stdlib-only for
    # every caller except the change-set check.
    from apothem.conformity._git import run_git
    from apothem.conformity._grep_base import GitTimeoutError

    try:
        return run_git(
            list(args),
            cwd=cwd,
            timeout=GIT_TIMEOUT_SECONDS,
            check=check,
            file_names=file_names,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitTimeoutError(label, GIT_TIMEOUT_SECONDS) from exc


def _package_folder_above() -> tuple[Path, bool] | None:
    """Find the nearest folder above the current one that holds the package.

    The search runs without git, over the folders git itself would search for
    the repository (see
    :func:`~apothem.conformity._grep_base.checkout_search_folders`), with
    links resolved. It ends where git's search ends, at the first folder
    whose ``.git`` entry is a repository git would use: a ``.git`` folder
    that holds one, or a ``.git`` file that names one (a linked work tree, a
    submodule). An entry git looks past does not end it: an empty ``.git``
    folder, a ``.git`` link that leads nowhere.

    Returns None when no folder up to there holds ``src/apothem/__init__.py``
    (or the current folder is gone). Then the project has no package to
    check, whatever state its repository is in, and no git command is needed
    to say so. Otherwise returns the folder and whether a ``.git`` file that
    git refuses (one that names no repository, is malformed or too large, or
    names a network or device path on Windows) lies between it and the
    current folder. git stops with an error at such a file, so the caller
    must not read the package's
    change set as if the run had started in the package's folder.
    """
    from apothem.conformity._grep_base import (
        GIT_ENTRY_BROKEN,
        GIT_ENTRY_REPOSITORY,
        checkout_search_folders,
        git_entry_state,
    )

    try:
        start = Path.cwd()
    except OSError:
        return None
    below_broken_entry = False
    for folder in checkout_search_folders(start):
        if (folder / INIT_PATH).exists():
            return folder, below_broken_entry
        state = git_entry_state(folder)
        if state == GIT_ENTRY_REPOSITORY:
            return None
        if state == GIT_ENTRY_BROKEN:
            below_broken_entry = True
    return None


def check_staged() -> list[Finding]:
    """Per-change-set check across the staged diff.

    The package is looked for below the current folder first. When it is not
    there, it is looked for in the folders above, up to the nearest folder
    that holds a repository. The search also stops where git's own search
    stops: below a folder ``GIT_CEILING_DIRECTORIES`` names, and, outside
    Windows, at a file-system boundary. git then runs in the nearest folder
    that holds the package, so a run from a subfolder of the checkout checks
    the same change set as a run from that folder. A project with no package
    there has nothing to check: the list of findings is empty and no git
    command runs. Where a ``.git`` file that git refuses (see
    :func:`_package_folder_above`) lies between the current folder and the
    package, git runs in the current folder, stops
    at that file, and the failure is reported. ``GIT_WORK_TREE`` in the
    environment is not read by the search.

    git runs through :func:`~apothem.conformity._git.run_git`, which turns off
    the repository's program-running settings. File contents are read with
    ``git cat-file blob``, never ``git show``: the staged list can name a
    gitlink (a submodule entry), which ``show`` would display as a commit,
    signature check and submodule diff included, while ``cat-file blob``
    refuses it.

    Raises :class:`~apothem.conformity._grep_base.GitTimeoutError` when the
    staged list, or a staged or committed file, is not read within
    ``GIT_TIMEOUT_SECONDS``, and
    :class:`~apothem.conformity._grep_base.GitFailedError` when git fails to
    list the change set inside a checkout (a ``.git`` entry in the package's
    folder or one above it): a change set that was not read is not a clean
    one. Raises :class:`~apothem.conformity._grep_base.GitNameError` when a
    staged file's name cannot be given back to git to read its content (a
    name that is not UTF-8, on Windows). Raises
    :class:`~apothem.conformity._grep_base.GitEntryLinkedError`, without
    running git, when a ``.git`` entry in the folder git runs in or one above
    it that git searches is a link, and
    :class:`~apothem.conformity._grep_base.GitEntryUnreadableError` when one
    could not be looked at (see
    :func:`~apothem.conformity._grep_base.refuse_linked_git`). Outside a
    checkout, or without git, there is no change set and the list of findings
    is empty.
    """
    from apothem.conformity._git import reaches_git_unchanged, split_names
    from apothem.conformity._grep_base import (
        GitFailedError,
        GitNameError,
        GitTimeoutError,
        in_checkout,
        refuse_linked_git,
    )

    version = current_version()
    # The folder git runs in: None is the current folder, where the package
    # usually is. Otherwise the folder above that holds it, so git reads
    # ``src/apothem`` from there exactly as in a run from that folder.
    home: Path | None = None
    if version is None:
        found = _package_folder_above()
        if found is None:
            return []
        package_folder, below_broken_entry = found
        version = _version_in(package_folder)
        # Below a ``.git`` file that names no repository, git runs where the
        # check was started and reports that file itself.
        home = None if below_broken_entry else package_folder
    if not version or is_v0(version):
        return []

    def blob(spec: str, *, check: bool) -> str:
        return _git(
            "git cat-file", "cat-file", "blob", spec, check=check, cwd=home
        ).stdout

    # Get list of staged Python files under src/apothem/. -z ends each name
    # with NUL, unquoted, and the list is read as file names, so each name
    # comes back with every byte it holds. ``run_git`` turns
    # ``diff.relative`` off, so git prints each name from the top of the work
    # tree even when the user's setting is on, which is how
    # ``cat-file blob :<name>`` reads it. ``--`` marks the package as a path:
    # without it git stops with "ambiguous argument" in a work tree where the
    # folder is gone. Before any git runs, a ``.git`` link on git's search
    # path from the folder it runs in refuses the check.
    refuse_linked_git(home or Path.cwd())
    try:
        result = _git(
            "git diff --cached",
            "diff",
            "--cached",
            "--name-only",
            "-z",
            "--diff-filter=AMR",
            "--",
            PUBLIC_PACKAGE,
            file_names=True,
            cwd=home,
        )
    except FileNotFoundError:
        return []
    if result.returncode != 0:
        # Outside a checkout there is no change set; in one, git refused it.
        if in_checkout(home or Path.cwd()):
            raise GitFailedError("git diff --cached", result.returncode)
        return []
    files = [
        f
        for f in split_names(result.stdout)
        if f.endswith(".py")
        and not PRIVATE_PATTERN.search(f)
        and not CONFORMITY_INTERNAL.search(f)
    ]

    findings: list[Finding] = []
    for fp in files:
        # The name goes back to git as an argument. One that cannot arrive
        # unchanged would read as a missing file and be skipped below, which
        # would pass a change that was never compared.
        if not reaches_git_unchanged(fp):
            raise GitNameError("git cat-file")
        # A GitTimeoutError goes on to the caller: skipping the file would
        # pass a change that was never compared.
        try:
            staged = blob(f":{fp}", check=True)
            prior = blob(f"HEAD:{fp}", check=False)
        except subprocess.CalledProcessError:
            continue
        if not prior:
            continue  # newly-added file
        old_surface = extract_public_surface(prior)
        new_surface = extract_public_surface(staged)
        if old_surface is None or new_surface is None:
            continue
        findings.extend(compare_surfaces(old_surface, new_surface, fp))

    if findings:
        # Cross-reference: did the staged change include a MAJOR bump?
        # git names a path with forward slashes on every platform. The
        # leading ``./`` makes git read the path from the folder it runs in,
        # the package's folder, which can sit below the top of the work tree.
        init_spec = f"./{INIT_PATH.as_posix()}"
        try:
            staged_init = blob(f":{init_spec}", check=True)
            prior_init = blob(f"HEAD:{init_spec}", check=False)
            staged_v = re.search(r'__version__\s*=\s*"([^"]+)"', staged_init)
            prior_v = re.search(r'__version__\s*=\s*"([^"]+)"', prior_init)
            if (
                staged_v
                and prior_v
                and major_bumped(staged_v.group(1), prior_v.group(1))
            ):
                # MAJOR bump present — breaking changes are admissible.
                return []
        except (subprocess.CalledProcessError, GitTimeoutError):
            # Missing/timed-out staged init means the original breaking-change
            # findings stand, so the check does not pass either way.
            pass

    return findings


def _read_hook_findings() -> list[Finding]:
    """Hook mode: read tool-input JSON from stdin, return breaking-change findings."""
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return []
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    content = tool_input.get("content") or tool_input.get("new_string", "")
    return check_hook(file_path, content) if file_path and content else []


def _main(argv: list[str]) -> int:
    # Imported here, not at module top, so the module stays stdlib-only for
    # every caller except the command-line entry.
    from apothem.conformity._grep_base import GitCheckError, make_parser

    parser = make_parser(GREP_NAME, __doc__)
    parser.add_argument(
        STAGED_FLAG,
        dest="staged",
        action="store_true",
        help="check the staged change set (default: read a hook payload on stdin)",
    )
    args = parser.parse_args(argv[1:])
    check_error: str | None = None
    if args.staged:
        try:
            findings = check_staged()
        except GitCheckError as exc:
            findings, check_error = [], str(exc)
    else:
        findings = _read_hook_findings()
    result = GrepResult(
        grep=GREP_NAME,
        passed=not findings and check_error is None,
        findings=findings,
        check_error=check_error,
    )
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
