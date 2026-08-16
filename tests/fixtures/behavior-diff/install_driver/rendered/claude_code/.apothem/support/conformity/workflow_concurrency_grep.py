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
   heuristically via the presence of a ``strategy.matrix`` block).

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


def _check_workflow(path: Path) -> list[Finding]:
    """Inspect one workflow file; return its drift findings."""
    findings: list[Finding] = []
    workflow_name = path.name
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
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
        # Reusable-workflow callers declare `uses:` at job level with no
        # inline `steps:` sequence. The called reusable workflow owns its
        # timeout-minutes ceiling, so the caller cannot declare one. This
        # mirrors the harden-runner reusable-workflow exemption.
        if "uses" in job and "steps" not in job:
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
        if not isinstance(timeout, int):
            findings.append(
                Finding(
                    workflow=workflow_name,
                    job=str(job_name),
                    drift_class="missing-job-timeout",
                    detail=f"timeout-minutes is not an integer: {timeout!r}",
                )
            )
            continue
        ceiling = (
            FULL_MATRIX_JOB_CEILING_MINUTES
            if _job_is_full_matrix(job)
            else SHORT_JOB_CEILING_MINUTES
        )
        if timeout > ceiling:
            findings.append(
                Finding(
                    workflow=workflow_name,
                    job=str(job_name),
                    drift_class="job-timeout-exceeds-ceiling",
                    detail=f"timeout-minutes={timeout} exceeds ceiling={ceiling}",
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


def _read_input(argv: list[str]) -> Path:
    if len(argv) >= 2:
        return Path(argv[1])
    return Path.cwd()


def _main(argv: list[str]) -> int:
    root = _read_input(argv)
    result = check(root)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
