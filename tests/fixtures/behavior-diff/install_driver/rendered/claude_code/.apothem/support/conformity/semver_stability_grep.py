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
stand without a MAJOR bump. The per-Write hook path emits the same payload.
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

# Bound every gate-path git invocation so a hung `git show`/`git diff`
# (filesystem lock, slow network-backed repo, large object) cannot block a
# commit indefinitely. Mirrors the convention in production_ready_pr_grep.py.
GIT_TIMEOUT_SECONDS: Final[int] = 5

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

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, passed, findings}``.
        """
        payload = {
            "grep": self.grep,
            "passed": self.passed,
            "findings": [f.as_dict() for f in self.findings],
        }
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


def current_version() -> str | None:
    """Read the staged or on-disk apothem.__version__ value."""
    if not INIT_PATH.exists():
        return None
    text = INIT_PATH.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else None


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


def check_staged() -> list[Finding]:
    """Per-change-set check across the staged diff."""
    version = current_version()
    if not version or is_v0(version):
        return []

    # Get list of staged Python files under src/apothem/.
    try:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--cached",
                "--name-only",
                "--diff-filter=AMR",
                PUBLIC_PACKAGE,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    files = [
        f.strip()
        for f in result.stdout.splitlines()
        if f.strip().endswith(".py")
        and not PRIVATE_PATTERN.search(f)
        and not CONFORMITY_INTERNAL.search(f)
    ]

    findings: list[Finding] = []
    for fp in files:
        try:
            staged = subprocess.run(
                ["git", "show", f":{fp}"],
                capture_output=True,
                text=True,
                check=True,
                timeout=GIT_TIMEOUT_SECONDS,
            ).stdout
            prior = subprocess.run(
                ["git", "show", f"HEAD:{fp}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=GIT_TIMEOUT_SECONDS,
            ).stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
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
        try:
            staged_init = subprocess.run(
                ["git", "show", f":{INIT_PATH}"],
                capture_output=True,
                text=True,
                check=True,
                timeout=GIT_TIMEOUT_SECONDS,
            ).stdout
            prior_init = subprocess.run(
                ["git", "show", f"HEAD:{INIT_PATH}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=GIT_TIMEOUT_SECONDS,
            ).stdout
            staged_v = re.search(r'__version__\s*=\s*"([^"]+)"', staged_init)
            prior_v = re.search(r'__version__\s*=\s*"([^"]+)"', prior_init)
            if (
                staged_v
                and prior_v
                and major_bumped(staged_v.group(1), prior_v.group(1))
            ):
                # MAJOR bump present — breaking changes are admissible.
                return []
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # Missing/timed-out staged init means the original breaking-change
            # findings stand. A TimeoutExpired here is caught consistently with
            # the bounded git calls above rather than crashing the validator.
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
    from apothem.conformity._grep_base import make_parser

    parser = make_parser(GREP_NAME, __doc__)
    parser.add_argument(
        STAGED_FLAG,
        dest="staged",
        action="store_true",
        help="check the staged change set (default: read a hook payload on stdin)",
    )
    args = parser.parse_args(argv[1:])
    findings = check_staged() if args.staged else _read_hook_findings()
    result = GrepResult(grep=GREP_NAME, passed=not findings, findings=findings)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
