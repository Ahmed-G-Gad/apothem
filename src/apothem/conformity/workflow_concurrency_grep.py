# SPDX-License-Identifier: MIT

"""Enforce concurrency + per-job timeout discipline on GitHub workflows.

Why this validator exists. The workflow reliability contract requires
every push- or pull_request-triggered workflow to declare a top-level
``concurrency:`` block (to coalesce redundant runs on the same ref)
AND every job declares a
``timeout-minutes:`` ceiling (to prevent runaway jobs from monopolising
the runner pool). Deployment-class workflows (release / publish /
deploy) reverse the cancellation polarity: mid-deploy cancellation
risks partial-state hazards, so ``cancel-in-progress: false`` is
mandatory.

Detection. Walk ``<root>/.github/workflows/*.yml``. For each workflow:

1. Inspect ``on:`` for ``push`` or ``pull_request`` triggers; skip
   workflows without either (manual / scheduled workflows are out of
   scope for concurrency discipline).
2. Require a top-level ``concurrency:`` mapping with a ``group:`` key
   and a ``cancel-in-progress:`` flag.
3. For deployment workflows (filename matches ``*release*`` /
   ``*publish*`` / ``*deploy*``) require ``cancel-in-progress: false``;
   for all others require ``cancel-in-progress: true``.
4. For every job in ``jobs:``, require ``timeout-minutes:`` with
   ``N <= 30`` (short jobs) or ``N <= 90`` (full-matrix jobs — detected
   heuristically via the presence of a ``strategy.matrix`` block). A
   full-matrix job may instead declare exactly
   ``${{ matrix.os == 'windows-latest' && N || M }}``: the Windows cells
   get ``N <= 120`` and every other cell ``M <= 90``. An integer limit,
   ``N`` and ``M`` must each be at least 1: GitHub reads 0 as false, so
   ``&& 0 || 90`` would give the Windows cells 90, and a negative limit
   means nothing. Any other value is drift.
5. A job that calls a reusable workflow (``uses:`` and no ``steps:``)
   declares no ``timeout-minutes:`` of its own; when it passes one to the
   callee through ``with: timeout-minutes:``, that value meets the same
   rules. The caller's ``strategy.matrix`` decides the ceiling, because
   the fan-out usually lives on the caller: each matrix cell runs the
   callee once. When the caller has no matrix and calls a workflow in the
   same folder (``./.github/workflows/<file>``), the validator reads that
   file, and an integer limit gets the full-matrix ceiling when a job there
   carries its own ``strategy.matrix`` and sets ``timeout-minutes`` to
   exactly ``${{ inputs.timeout-minutes }}``. The ``matrix.os`` conditional still needs
   the caller's own matrix, because GitHub evaluates ``with:`` in the
   caller's context. The limit of this check: the validator does not read
   a callee in another repository or one it cannot find or parse, and it
   does not recognise a callee job that reads the input in another way,
   such as ``inputs['timeout-minutes']``; for those, the caller's matrix
   alone sets the ceiling, the stricter reading.

Drift classes. ``missing-concurrency-block``,
``missing-cancel-in-progress-flag``, ``cancel-in-progress-wrong-value``,
``missing-job-timeout``, ``job-timeout-exceeds-ceiling``.

Tolerance. When ``<root>/.github/workflows/`` does not exist, exit 0 with
``not-yet-materialised: true`` — the workflows tree has not been
authored yet and the discipline does not yet apply.

Exit semantics. Exits 0 when every inspected workflow is conformant;
exits 2 with a JSON enumeration of per-workflow + per-job drift when
any drift is detected.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

GREP_NAME: Final[str] = "workflow-concurrency-grep"
RULE_ANCHOR: Final[str] = "workflow concurrency + per-job timeouts"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

SHORT_JOB_CEILING_MINUTES: Final[int] = 30
FULL_MATRIX_JOB_CEILING_MINUTES: Final[int] = 90
WINDOWS_FULL_MATRIX_JOB_CEILING_MINUTES: Final[int] = 120

# The one expression a full-matrix job may give as its limit: a longer limit
# for the Windows cells, which run the same suite more slowly, and the usual
# one for the rest. GitHub expression strings take single quotes only.
# re.ASCII keeps \d to 0-9, so full-width or other Unicode digits fail.
# Each limit takes one to five digits, so int() never meets a digit string
# past Python's 4,300-digit conversion limit.
_WINDOWS_CONDITIONAL_TIMEOUT: Final[re.Pattern[str]] = re.compile(
    r"\s*\$\{\{\s*matrix\.os\s*==\s*'windows-latest'\s*&&\s*(\d{1,5})"
    r"\s*\|\|\s*(\d{1,5})\s*\}\}\s*",
    re.ASCII,
)

# A local reusable workflow sits directly in .github/workflows/; GitHub
# accepts no subfolder there, so the part after the prefix is a bare file
# name. The name pattern also keeps out "..", path separators and a Windows
# drive prefix, so the lookup cannot leave the workflows folder.
_LOCAL_CALLEE_PREFIX: Final[str] = "./.github/workflows/"
_LOCAL_CALLEE_NAME: Final[re.Pattern[str]] = re.compile(r"[\w-][\w.-]*", re.ASCII)
# The callee's limit must be exactly the passed input; an expression that
# only mentions it (a Windows override, github.event.inputs) does not count.
_TIMEOUT_INPUT: Final[re.Pattern[str]] = re.compile(
    r"\s*\$\{\{\s*inputs\.timeout-minutes\s*\}\}\s*", re.ASCII
)

DEPLOYMENT_NAME_MARKERS: Final[tuple[str, ...]] = ("release", "publish", "deploy")


@dataclass(frozen=True)
class Finding:
    """One concurrency / timeout drift instance inside a workflow."""

    workflow: str
    job: str | None
    drift_class: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Matcher report for a single sweep of this validator.

    Carries its own result shape rather than reusing the shared base because
    the payload adds ``not_yet_materialised``, ``workflow_count``.

    Pre-conditions: ``findings`` holds this module's frozen ``Finding``
    dataclasses. Post-conditions: ``passed`` is ``True`` exactly when
    ``findings`` is empty; :meth:`to_json` emits the serialised payload.
    """

    grep: str
    root: str
    not_yet_materialised: bool
    workflow_count: int
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root,
        not-yet-materialised, workflow-count, passed, findings}``; each finding
        is flattened through ``dataclasses.asdict``.
        """
        payload: dict[str, Any] = {
            "grep": self.grep,
            "root": self.root,
            "not-yet-materialised": self.not_yet_materialised,
            "workflow-count": self.workflow_count,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _is_deployment_workflow(path: Path) -> bool:
    """Detect deployment-class workflows by filename marker."""
    stem = path.stem.lower()
    return any(marker in stem for marker in DEPLOYMENT_NAME_MARKERS)


def _has_push_or_pr_trigger(on_block: object) -> bool:
    """Return True iff ``on:`` declares a push or pull_request trigger.

    The ``on:`` key admits multiple shapes — a string (``on: push``), a
    list (``on: [push, pull_request]``), or a mapping (``on: {push: {...}}``).
    """
    if isinstance(on_block, str):
        return on_block in ("push", "pull_request")
    if isinstance(on_block, list):
        return any(t in ("push", "pull_request") for t in on_block)
    if isinstance(on_block, dict):
        return "push" in on_block or "pull_request" in on_block
    return False


def _job_is_full_matrix(job: dict[str, Any]) -> bool:
    """Heuristic: a job carrying ``strategy.matrix`` is a full-matrix job."""
    strategy = job.get("strategy")
    if not isinstance(strategy, dict):
        return False
    return "matrix" in strategy


def _parse_windows_conditional(value: str) -> tuple[int, int] | None:
    """Return ``(windows, other)`` minutes for the Windows conditional form.

    Returns ``None`` unless ``value`` is exactly
    ``${{ matrix.os == 'windows-latest' && N || M }}`` (whitespace aside)
    with ASCII digits and ``N`` and ``M`` both at least 1.
    """
    match = _WINDOWS_CONDITIONAL_TIMEOUT.fullmatch(value)
    if match is None:
        return None
    windows, other = int(match.group(1)), int(match.group(2))
    if windows < 1 or other < 1:
        return None
    return windows, other


def _callee_runs_matrix(workflows_dir: Path, uses: object) -> bool:
    """Return True when a local callee's matrix job takes the passed limit.

    ``uses`` counts only as ``./.github/workflows/<file>`` naming a file
    directly in ``workflows_dir``. The callee must hold a job that carries
    ``strategy.matrix`` and sets its ``timeout-minutes`` to exactly
    ``${{ inputs.timeout-minutes }}``. Any other reference, and a callee that is
    missing or does not parse, returns False, so the caller's own matrix
    alone decides the ceiling.
    """
    if not isinstance(uses, str) or not uses.startswith(_LOCAL_CALLEE_PREFIX):
        return False
    name = uses[len(_LOCAL_CALLEE_PREFIX) :]
    if _LOCAL_CALLEE_NAME.fullmatch(name) is None:
        return False
    try:
        doc = yaml.safe_load((workflows_dir / name).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError):
        # ValueError: PyYAML's int() refuses an integer past 4,300 digits.
        return False
    jobs = doc.get("jobs") if isinstance(doc, dict) else None
    if not isinstance(jobs, dict):
        return False
    for job in jobs.values():
        if not isinstance(job, dict) or not _job_is_full_matrix(job):
            continue
        timeout = job.get("timeout-minutes")
        if isinstance(timeout, str) and _TIMEOUT_INPUT.fullmatch(timeout):
            return True
    return False


def _timeout_drift(
    timeout: object,
    *,
    full_matrix: bool,
    label: str,
    matrix_os_in_scope: bool | None = None,
) -> tuple[str, str] | None:
    """Return ``(drift_class, detail)`` for a declared limit, or ``None``.

    ``timeout`` is an integer of at least 1, checked against the short or
    full-matrix ceiling, or, where ``matrix.os`` is in scope, the Windows
    conditional form, whose branches are checked against the Windows and
    full-matrix ceilings. ``matrix_os_in_scope`` defaults to
    ``full_matrix``; a caller whose matrix lives only in the callee passes
    False. Anything else is drift. ``label`` names the key in the detail.
    """
    if matrix_os_in_scope is None:
        matrix_os_in_scope = full_matrix
    if isinstance(timeout, int) and not isinstance(timeout, bool):
        if timeout < 1:
            return ("missing-job-timeout", f"{label}={timeout} is below 1")
        ceiling = (
            FULL_MATRIX_JOB_CEILING_MINUTES
            if full_matrix
            else SHORT_JOB_CEILING_MINUTES
        )
        if timeout > ceiling:
            return (
                "job-timeout-exceeds-ceiling",
                f"{label}={timeout} exceeds ceiling={ceiling}",
            )
        return None
    branches = _parse_windows_conditional(timeout) if isinstance(timeout, str) else None
    if branches is None:
        return ("missing-job-timeout", f"{label} is not an integer: {timeout!r}")
    if not matrix_os_in_scope:
        return (
            "missing-job-timeout",
            f"{label} uses the matrix.os conditional on a job without "
            f"strategy.matrix: {timeout!r}",
        )
    windows, other = branches
    excess: list[str] = []
    if windows > WINDOWS_FULL_MATRIX_JOB_CEILING_MINUTES:
        excess.append(
            f"Windows limit {windows} exceeds ceiling="
            f"{WINDOWS_FULL_MATRIX_JOB_CEILING_MINUTES}"
        )
    if other > FULL_MATRIX_JOB_CEILING_MINUTES:
        excess.append(
            f"other limit {other} exceeds ceiling={FULL_MATRIX_JOB_CEILING_MINUTES}"
        )
    if excess:
        return ("job-timeout-exceeds-ceiling", f"{label}: " + "; ".join(excess))
    return None


def _check_workflow(path: Path) -> list[Finding]:
    """Inspect one workflow file; return its drift findings."""
    findings: list[Finding] = []
    workflow_name = path.name
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (ValueError, yaml.YAMLError) as exc:
        # ValueError: PyYAML's int() refuses an integer past 4,300 digits.
        findings.append(
            Finding(
                workflow=workflow_name,
                job=None,
                drift_class="yaml-parse-error",
                detail=f"failed to parse workflow: {exc}",
            )
        )
        return findings
    if not isinstance(doc, dict):
        return findings
    # PyYAML coerces the bare key `on` to boolean True (the YAML 1.1
    # legacy-bool surface). Inspect both forms.
    on_block = doc.get("on") if "on" in doc else doc.get(True)
    if not _has_push_or_pr_trigger(on_block):
        return findings
    is_deploy = _is_deployment_workflow(path)
    concurrency = doc.get("concurrency")
    if concurrency is None:
        findings.append(
            Finding(
                workflow=workflow_name,
                job=None,
                drift_class="missing-concurrency-block",
                detail="top-level concurrency: block absent",
            )
        )
    elif isinstance(concurrency, dict):
        if "cancel-in-progress" not in concurrency:
            findings.append(
                Finding(
                    workflow=workflow_name,
                    job=None,
                    drift_class="missing-cancel-in-progress-flag",
                    detail="concurrency block lacks cancel-in-progress key",
                )
            )
        else:
            cip = concurrency["cancel-in-progress"]
            expected = not is_deploy
            if cip is not expected:
                findings.append(
                    Finding(
                        workflow=workflow_name,
                        job=None,
                        drift_class="cancel-in-progress-wrong-value",
                        detail=(
                            f"deployment workflow requires cancel-in-progress: false (got {cip!r})"
                            if is_deploy
                            else f"non-deployment workflow requires cancel-in-progress: true (got {cip!r})"
                        ),
                    )
                )
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        return findings
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        full_matrix = _job_is_full_matrix(job)
        # Reusable-workflow callers declare `uses:` at job level with no
        # inline `steps:` sequence. GitHub rejects a job-level
        # timeout-minutes there, so the called workflow owns the limit; a
        # caller that passes one through `with: timeout-minutes` is held to
        # the same ceilings as a job with its own steps, and a local callee
        # whose job runs a matrix on that input lifts an integer to the
        # full-matrix ceiling. A caller that passes none leaves the callee's
        # default in force.
        if "uses" in job and "steps" not in job:
            with_block = job.get("with")
            if isinstance(with_block, dict) and "timeout-minutes" in with_block:
                drift = _timeout_drift(
                    with_block["timeout-minutes"],
                    full_matrix=full_matrix
                    or _callee_runs_matrix(path.parent, job["uses"]),
                    label="with: timeout-minutes",
                    matrix_os_in_scope=full_matrix,
                )
                if drift is not None:
                    findings.append(
                        Finding(
                            workflow=workflow_name,
                            job=str(job_name),
                            drift_class=drift[0],
                            detail=drift[1],
                        )
                    )
            continue
        timeout = job.get("timeout-minutes")
        if timeout is None:
            findings.append(
                Finding(
                    workflow=workflow_name,
                    job=str(job_name),
                    drift_class="missing-job-timeout",
                    detail="job declares no timeout-minutes ceiling",
                )
            )
            continue
        drift = _timeout_drift(
            timeout, full_matrix=full_matrix, label="timeout-minutes"
        )
        if drift is not None:
            findings.append(
                Finding(
                    workflow=workflow_name,
                    job=str(job_name),
                    drift_class=drift[0],
                    detail=drift[1],
                )
            )
    return findings


def check(root: Path) -> GrepResult:
    """Walk ``<root>/.github/workflows/*.yml``; return aggregated result.

    Pre-conditions: ``root`` is a directory path.
    Post-conditions: ``result.passed`` is True iff every push-/PR-
    triggered workflow declares conformant concurrency + per-job
    timeouts, OR the workflows directory does not yet exist.
    """
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return GrepResult(
            grep=GREP_NAME,
            root=str(root),
            not_yet_materialised=True,
            workflow_count=0,
            passed=True,
            findings=[],
        )
    workflow_files = sorted(
        list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    )
    findings: list[Finding] = []
    for path in workflow_files:
        findings.extend(_check_workflow(path))
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        not_yet_materialised=False,
        workflow_count=len(workflow_files),
        passed=not findings,
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
        inspected=result.workflow_count,
        empty_scope_expected=result.not_yet_materialised,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
