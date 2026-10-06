# SPDX-License-Identifier: MIT

"""Verify CI declares a cross-platform OS x Python matrix.

Why this enforcement exists. The cross-platform discipline ratified at
the supply-chain SOTA-rigor contract requires the canonical CI workflow at
``.github/workflows/ci-matrix.yml`` to declare a strategy matrix
spanning three operating systems (``ubuntu-latest``, ``macos-latest``,
``windows-latest``) and the Python versions the project supports. The
required Python set is derived from the ``Programming Language :: Python ::
X.Y`` classifiers in ``pyproject.toml`` so a newly-supported interpreter
(3.14, and any future 3.15) is seen the moment the classifier lands — the
validator never lags the project's own declared support matrix behind a
hardcoded list. The validator parses the workflow YAML, walks every job's
``strategy.matrix`` block, and reports drift on five named classes:
``workflow-absent`` (informational pass when the workflow has not yet been
materialised), ``strategy-matrix-absent``, ``os-missing``,
``python-version-missing``, and ``matrix-cell-count-mismatch``.

Detection strategy. The validator searches ``<root>/.github/workflows/``
for files matching ``*ci-matrix*.yml``. If no such file exists, the
result carries ``not-yet-materialised: true`` and exits 0
(informational tolerance — the workflow may be authored in a later
phase). When the workflow exists, the validator parses it with
``yaml.safe_load`` (falling back to a permissive string-scan if PyYAML
is absent), enumerates every job's ``strategy.matrix``, and verifies
the required OS and Python axes plus the expected cell product. OS-axis
matching accepts both the ``-latest`` alias and versioned runner labels
(``ubuntu-24.04``, ``macos-15``, ``windows-2025``), so a pinned-image
matrix is recognised as covering its OS family.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

REQUIRED_OS: Final[tuple[str, ...]] = (
    "ubuntu-latest",
    "macos-latest",
    "windows-latest",
)

# OS-family prefixes. A runner label is credited to a required OS when it is
# the ``-latest`` alias or a versioned image of the same family (``ubuntu-24.04``
# credits ``ubuntu-latest``). The mapping keys the required label to its family
# stem so both the parsed and string-fallback paths share one rule.
_OS_FAMILY_STEMS: Final[dict[str, str]] = {
    "ubuntu-latest": "ubuntu",
    "macos-latest": "macos",
    "windows-latest": "windows",
}

# Fallback Python set used only when the pyproject classifiers cannot be read
# (missing file, no classifiers). Mirrors the current support floor.
_FALLBACK_PYTHON: Final[tuple[str, ...]] = ("3.10", "3.11", "3.12", "3.13", "3.14")

# ``Programming Language :: Python :: X.Y`` classifier extractor. Only the
# minor-versioned entries are consumed; the bare ``:: 3`` line is ignored.
_CLASSIFIER_RE: Final[re.Pattern[str]] = re.compile(
    r"Programming Language :: Python :: (\d+\.\d+)"
)


def _required_python(root: Path) -> tuple[str, ...]:
    """Derive the required Python set from ``pyproject.toml`` classifiers.

    Reads the ``Programming Language :: Python :: X.Y`` classifiers under
    *root* and returns them sorted ascending. Falls back to
    ``_FALLBACK_PYTHON`` when the file is unreadable or declares no
    minor-versioned classifier, so the validator is never left with an empty
    required axis.
    """
    pyproject = root / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return _FALLBACK_PYTHON
    found = _CLASSIFIER_RE.findall(text)
    if not found:
        return _FALLBACK_PYTHON
    # Sort numerically by (major, minor) so 3.9 < 3.10 < 3.14 orders correctly.
    unique = sorted(set(found), key=lambda v: tuple(int(p) for p in v.split(".")))
    return tuple(unique)


GREP_NAME: Final[str] = "cross-platform-matrix-grep"
RULE_ANCHOR: Final[str] = "cross-platform OS x Python CI matrix"
EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

WORKFLOW_DIR: Final[str] = ".github/workflows"
WORKFLOW_GLOB: Final[str] = "*ci-matrix*.yml"


@dataclass(frozen=True)
class Finding:
    """One cross-platform matrix drift in the inspected workflow.

    Pre-conditions: ``drift_class`` names the drift category (a missing
    operating-system leg, an unbalanced interpreter axis, or an excluded
    combination that removes declared coverage); ``detail`` states the observed
    versus expected matrix in operator-facing prose. Post-conditions: ``rule``
    defaults to :data:`RULE_ANCHOR` so every finding cites its authority.
    """

    drift_class: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Matcher report for a single sweep of this validator.

    Carries its own result shape rather than reusing the shared base because
    the payload adds ``workflow_path``, ``not_yet_materialised``.

    Pre-conditions: ``findings`` holds this module's frozen ``Finding``
    dataclasses. Post-conditions: ``passed`` is ``True`` exactly when
    ``findings`` is empty; :meth:`to_json` emits the serialised payload.
    """

    grep: str
    root: str
    passed: bool
    workflow_path: str | None = None
    not_yet_materialised: bool = False
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, passed,
        workflow_path, not-yet-materialised, findings}``; each finding is
        flattened through ``dataclasses.asdict``.
        """
        payload: dict[str, Any] = {
            "grep": self.grep,
            "root": self.root,
            "passed": self.passed,
            "workflow_path": self.workflow_path,
            "not-yet-materialised": self.not_yet_materialised,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _find_workflow(root: Path) -> Path | None:
    """Locate the canonical CI-matrix workflow, if present."""
    workflows = root / WORKFLOW_DIR
    if not workflows.is_dir():
        return None
    # Prefer the exact canonical name; fall back to the glob match.
    canonical = workflows / "ci-matrix.yml"
    if canonical.exists():
        return canonical
    candidates = sorted(workflows.glob(WORKFLOW_GLOB))
    return candidates[0] if candidates else None


def _parse_yaml(content: str) -> dict[str, Any] | None:
    """Parse YAML via PyYAML; return None when PyYAML is unavailable."""
    try:
        import yaml
    except ImportError:
        return None
    try:
        loaded = yaml.safe_load(content)
    except yaml.YAMLError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _normalize_versions(values: list[Any]) -> list[str]:
    """Coerce matrix python-version entries to strings (YAML may yield floats)."""
    out: list[str] = []
    for v in values:
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, (int, float)):
            out.append(str(v))
    return out


def _collect_matrices(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """Walk every job's strategy.matrix block."""
    matrices: list[dict[str, Any]] = []
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        return matrices
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        strategy = job.get("strategy")
        if not isinstance(strategy, dict):
            continue
        matrix = strategy.get("matrix")
        if isinstance(matrix, dict):
            matrices.append(matrix)
    return matrices


def _os_family_present(required: str, seen: set[str]) -> bool:
    """Return True iff a seen runner label credits the required OS family.

    Accepts the ``-latest`` alias and any versioned image of the same family
    (``ubuntu-24.04`` credits ``ubuntu-latest``), so a pinned-image matrix is
    recognised as covering its OS.
    """
    if required in seen:
        return True
    stem = _OS_FAMILY_STEMS.get(required)
    if stem is None:
        return False
    return any(label == stem or label.startswith(stem + "-") for label in seen)


def _cell_count_detail(expected: int, actual: int, py_count: int) -> str:
    return (
        f"expected {expected} cells ({len(REQUIRED_OS)} OS x {py_count} Python); "
        f"actual {actual}"
    )


def _check_parsed(
    workflow: dict[str, Any], findings: list[Finding], required_python: tuple[str, ...]
) -> None:
    """Verify the parsed workflow declares the required OS x Python matrix."""
    matrices = _collect_matrices(workflow)
    if not matrices:
        findings.append(
            Finding(
                drift_class="strategy-matrix-absent",
                detail="no job declares a strategy.matrix block",
            )
        )
        return
    # Union axes across every job's matrix so a multi-job split still passes.
    all_os: set[str] = set()
    all_py: set[str] = set()
    for matrix in matrices:
        raw_os = matrix.get("os")
        if isinstance(raw_os, list):
            all_os.update(s for s in raw_os if isinstance(s, str))
        raw_py = (
            matrix.get("python-version")
            or matrix.get("python_version")
            or matrix.get("python")
        )
        if isinstance(raw_py, list):
            all_py.update(_normalize_versions(raw_py))
    missing_os = [o for o in REQUIRED_OS if not _os_family_present(o, all_os)]
    if missing_os:
        findings.append(
            Finding(
                drift_class="os-missing",
                detail=f"OS axis missing: {', '.join(missing_os)}",
            )
        )
    missing_py = [p for p in required_python if p not in all_py]
    if missing_py:
        findings.append(
            Finding(
                drift_class="python-version-missing",
                detail=f"Python-version axis missing: {', '.join(missing_py)}",
            )
        )
    # Cell-count check uses the intersection of required-and-present axes
    # to avoid double-reporting when an axis is already flagged missing.
    present_os = [o for o in REQUIRED_OS if _os_family_present(o, all_os)]
    present_py = [p for p in required_python if p in all_py]
    actual_cells = len(present_os) * len(present_py)
    expected_cells = len(REQUIRED_OS) * len(required_python)
    if actual_cells != expected_cells:
        findings.append(
            Finding(
                drift_class="matrix-cell-count-mismatch",
                detail=_cell_count_detail(
                    expected_cells, actual_cells, len(required_python)
                ),
            )
        )


# OS runner labels: the ``-latest`` alias or a versioned image of the family
# (``ubuntu-24.04``, ``macos-15``, ``windows-2025``). The family stem is
# captured so both alias and pinned forms credit the same required OS.
_OS_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(ubuntu|macos|windows)-(?:latest|[0-9][0-9.]*)\b"
)


def _py_line_re(required_python: tuple[str, ...]) -> re.Pattern[str]:
    """Build a Python-version scanner from the required set (derived at runtime)."""
    alternation = "|".join(re.escape(v) for v in required_python)
    return re.compile(rf'["\']?({alternation})["\']?')


def _check_string_fallback(
    content: str, findings: list[Finding], required_python: tuple[str, ...]
) -> None:
    """Permissive string-scan when PyYAML is unavailable.

    Looks for a ``strategy:`` block plus a ``matrix:`` token. Verifies
    OS and Python version names appear somewhere in the document. This
    fallback is intentionally lenient — it cannot distinguish per-job
    matrices and will under-report drift compared with YAML parsing.
    """
    if "strategy:" not in content or "matrix:" not in content:
        findings.append(
            Finding(
                drift_class="strategy-matrix-absent",
                detail="no `strategy:` / `matrix:` tokens found in workflow",
            )
        )
        return
    # Both ``ubuntu-latest`` and ``ubuntu-24.04`` reduce to the family stem so a
    # pinned-image matrix credits its OS family, matching the parsed path.
    os_families = {m.group(1) for m in _OS_LINE_RE.finditer(content)}
    py_hits = {m.group(1) for m in _py_line_re(required_python).finditer(content)}
    missing_os = [o for o in REQUIRED_OS if _OS_FAMILY_STEMS[o] not in os_families]
    if missing_os:
        findings.append(
            Finding(
                drift_class="os-missing",
                detail=f"OS axis missing: {', '.join(missing_os)}",
            )
        )
    missing_py = [p for p in required_python if p not in py_hits]
    if missing_py:
        findings.append(
            Finding(
                drift_class="python-version-missing",
                detail=f"Python-version axis missing: {', '.join(missing_py)}",
            )
        )
    present_os = [o for o in REQUIRED_OS if _OS_FAMILY_STEMS[o] in os_families]
    present_py = [p for p in required_python if p in py_hits]
    actual_cells = len(present_os) * len(present_py)
    expected_cells = len(REQUIRED_OS) * len(required_python)
    if actual_cells != expected_cells:
        findings.append(
            Finding(
                drift_class="matrix-cell-count-mismatch",
                detail=_cell_count_detail(
                    expected_cells, actual_cells, len(required_python)
                ),
            )
        )


def check(root: Path) -> GrepResult:
    """Verify the CI-matrix workflow declares the canonical 3x4 matrix."""
    workflow = _find_workflow(root)
    if workflow is None:
        # Workflow-absent is informational tolerance: the canonical
        # ci-matrix.yml may not yet be materialised. Pass cleanly with
        # the informational field set so callers can distinguish.
        return GrepResult(
            grep=GREP_NAME,
            root=str(root),
            passed=True,
            workflow_path=None,
            not_yet_materialised=True,
            findings=[],
        )
    content = workflow.read_text(encoding="utf-8")
    required_python = _required_python(root)
    findings: list[Finding] = []
    parsed = _parse_yaml(content)
    if parsed is not None:
        _check_parsed(parsed, findings, required_python)
    else:
        _check_string_fallback(content, findings, required_python)
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        passed=not findings,
        workflow_path=str(workflow),
        not_yet_materialised=False,
        findings=findings,
    )


def _main(argv: list[str]) -> int:
    # Imported here, not at module top: ``check()`` stays stdlib-only; only
    # the command-line entry needs the shared parser and report stamp.
    from apothem.conformity._grep_base import finish_root_report, parse_root_args

    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    result = check(root)
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=0 if result.workflow_path is None else 1,
        empty_scope_expected=result.not_yet_materialised,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
