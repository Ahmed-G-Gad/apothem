# SPDX-License-Identifier: MIT

"""Verify every workflow job opens with a conformant harden-runner step.

Why this enforcement exists. The workflow hardening contract requires
every GitHub Actions workflow at ``.github/workflows/*.yml`` to invoke
``step-security/harden-runner@v2`` as the FIRST step of every job and
configure ``egress-policy: block`` (steady-state) or ``egress-policy:
audit`` (initial deployment phase). The action installs network-egress
controls before any user-supplied step runs; placing it second leaves a
window where checkout / dependency-fetch / arbitrary action steps can
exfiltrate before the egress policy engages.

Detection strategy. The validator walks ``<root>/.github/workflows/`` for
``*.yml`` and ``*.yaml`` files, parses each via ``yaml.safe_load``, and
for every job in ``jobs:`` inspects the ``steps[]`` sequence. Three drift
classes surface:

- ``harden-runner-action-absent`` — no step in the job uses
  ``step-security/harden-runner``.
- ``harden-runner-not-first-step`` — the action is present but not
  ``steps[0]``.
- ``egress-policy-too-permissive`` — the step's ``with:`` block omits
  ``egress-policy`` or sets it to a value other than ``block`` / ``audit``
  (``log`` and any other free-form value are rejected; the canonical
  taxonomy is closed).

Workflows-absent tolerance. When ``<root>/.github/workflows/`` does not
exist (a repository in its earliest scaffold state), the validator exits
0 with ``not-yet-materialised: true`` so the gate does not block bootstrap
work that hasn't yet authored CI.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

import yaml

# A bare ``${{ inputs.<name> }}`` expression — the reusable-workflow shape
# where egress-policy is parameterized by a workflow_call input.
_INPUTS_EXPR: Final[re.Pattern[str]] = re.compile(
    r"^\$\{\{\s*inputs\.([A-Za-z_][\w-]*)\s*\}\}$"
)

GREP_NAME: Final[str] = "harden-runner-grep"
RULE_ANCHOR: Final[str] = "harden-runner egress baseline"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

WORKFLOWS_SUBPATH: Final[str] = ".github/workflows"
ACTION_NAME: Final[str] = "step-security/harden-runner"
CONFORMANT_EGRESS_POLICIES: Final[frozenset[str]] = frozenset({"block", "audit"})

DRIFT_ABSENT: Final[str] = "harden-runner-action-absent"
DRIFT_NOT_FIRST: Final[str] = "harden-runner-not-first-step"
DRIFT_PERMISSIVE: Final[str] = "egress-policy-too-permissive"


@dataclass(frozen=True)
class Finding:
    """One job's harden-runner drift."""

    workflow: str
    job: str
    drift: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    grep: str
    root: str
    passed: bool
    not_yet_materialised: bool = False
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        payload = {
            "grep": self.grep,
            "root": self.root,
            "passed": self.passed,
            "not-yet-materialised": self.not_yet_materialised,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _uses_harden_runner(uses_value: object) -> bool:
    """Return True iff a ``uses:`` value references step-security/harden-runner."""
    if not isinstance(uses_value, str):
        return False
    # Strip any ``@<ref>`` suffix so ``@v2``, ``@v2.10``, and a 40-char SHA
    # pin all match identically.
    name = uses_value.split("@", 1)[0].strip()
    return name == ACTION_NAME


def _workflow_call_inputs(document: dict[object, object]) -> dict[object, object]:
    """Return the ``on.workflow_call.inputs`` mapping, or empty when absent.

    GitHub Actions ``on:`` is coerced by PyYAML (YAML 1.1) to the boolean
    key ``True``; handle both the string ``"on"`` and boolean ``True`` keys.
    """
    on_block = document.get("on", document.get(True))
    if not isinstance(on_block, dict):
        return {}
    workflow_call = on_block.get("workflow_call")
    if not isinstance(workflow_call, dict):
        return {}
    inputs = workflow_call.get("inputs")
    return inputs if isinstance(inputs, dict) else {}


def _resolve_egress(egress: object, inputs: dict[object, object]) -> object:
    """Resolve a ``${{ inputs.<name> }}`` egress-policy to the input default.

    A reusable workflow may parameterize egress-policy via a ``workflow_call``
    input; the conformant value is then the input's declared ``default``. A
    literal egress value (not an inputs expression) is returned unchanged.
    """
    if not isinstance(egress, str):
        return egress
    match = _INPUTS_EXPR.match(egress.strip())
    if match is None:
        return egress
    spec = inputs.get(match.group(1))
    if isinstance(spec, dict) and "default" in spec:
        return spec["default"]
    return egress


def _inspect_job(
    workflow: str,
    job_name: str,
    job: object,
    workflow_inputs: dict[object, object] | None = None,
) -> list[Finding]:
    """Return drift findings for one job; empty list when conformant."""
    if not isinstance(job, dict):
        return []
    # Reusable-workflow callers have no inline steps; harden-runner is
    # step-level and cannot apply. A job declaring a top-level ``uses:``
    # field and lacking a ``steps:`` field is structurally exempt.
    if "uses" in job and "steps" not in job:
        return []
    steps = job.get("steps")
    if not isinstance(steps, list) or not steps:
        return [
            Finding(
                workflow=workflow,
                job=job_name,
                drift=DRIFT_ABSENT,
                detail="job has no steps[] sequence",
            )
        ]
    # Locate harden-runner step(s).
    hr_indices = [
        i
        for i, step in enumerate(steps)
        if isinstance(step, dict) and _uses_harden_runner(step.get("uses"))
    ]
    if not hr_indices:
        return [
            Finding(
                workflow=workflow,
                job=job_name,
                drift=DRIFT_ABSENT,
                detail=f"no step uses {ACTION_NAME}",
            )
        ]
    first_idx = hr_indices[0]
    findings: list[Finding] = []
    if first_idx != 0:
        first_step = steps[0]
        first_uses = first_step.get("uses") if isinstance(first_step, dict) else None
        findings.append(
            Finding(
                workflow=workflow,
                job=job_name,
                drift=DRIFT_NOT_FIRST,
                detail=(
                    f"{ACTION_NAME} appears at steps[{first_idx}]; "
                    f"steps[0] uses={first_uses!r}"
                ),
            )
        )
    # Inspect the egress-policy on the first harden-runner step.
    hr_step = steps[first_idx]
    with_block = hr_step.get("with") if isinstance(hr_step, dict) else None
    egress = with_block.get("egress-policy") if isinstance(with_block, dict) else None
    # A reusable workflow may parameterize egress-policy via a workflow_call
    # input (``${{ inputs.<name> }}``); resolve it to the input's declared
    # default so a conformant default is not flagged as too-permissive.
    egress = _resolve_egress(egress, workflow_inputs or {})
    if egress is None:
        findings.append(
            Finding(
                workflow=workflow,
                job=job_name,
                drift=DRIFT_PERMISSIVE,
                detail="egress-policy key absent from with: block",
            )
        )
    elif not isinstance(egress, str) or egress not in CONFORMANT_EGRESS_POLICIES:
        findings.append(
            Finding(
                workflow=workflow,
                job=job_name,
                drift=DRIFT_PERMISSIVE,
                detail=(
                    f"egress-policy={egress!r}; expected one of "
                    f"{sorted(CONFORMANT_EGRESS_POLICIES)}"
                ),
            )
        )
    return findings


def _inspect_workflow(path: Path, root: Path) -> list[Finding]:
    """Parse a workflow file; return drift findings across all its jobs."""
    rel = str(path.relative_to(root)).replace("\\", "/")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [
            Finding(
                workflow=rel,
                job="<workflow>",
                drift=DRIFT_ABSENT,
                detail=f"unreadable workflow: {exc}",
            )
        ]
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [
            Finding(
                workflow=rel,
                job="<workflow>",
                drift=DRIFT_ABSENT,
                detail=f"YAML parse error: {exc}",
            )
        ]
    if not isinstance(document, dict):
        return [
            Finding(
                workflow=rel,
                job="<workflow>",
                drift=DRIFT_ABSENT,
                detail="workflow root is not a mapping",
            )
        ]
    jobs = document.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        # A workflow with no jobs has nothing to harden; skip silently.
        return []
    workflow_inputs = _workflow_call_inputs(document)
    findings: list[Finding] = []
    for job_name, job in jobs.items():
        findings.extend(_inspect_workflow_job(rel, job_name, job, workflow_inputs))
    return findings


def _inspect_workflow_job(
    workflow: str,
    job_name: object,
    job: object,
    workflow_inputs: dict[object, object] | None = None,
) -> list[Finding]:
    name = str(job_name) if not isinstance(job_name, str) else job_name
    return _inspect_job(workflow, name, job, workflow_inputs)


def check_root(root: Path) -> GrepResult:
    """Walk ``<root>/.github/workflows/`` and audit every workflow.

    Pre-conditions: ``root`` is the repository root.
    Post-conditions: ``result.passed`` is True iff every job in every
    discovered workflow opens with ``step-security/harden-runner@v2`` (or
    a pinned variant) and declares ``egress-policy: block`` / ``audit``.
    When the workflows directory is absent, returns passed=True with
    ``not_yet_materialised=True``.
    """
    workflows_dir = root / WORKFLOWS_SUBPATH
    if not workflows_dir.is_dir():
        return GrepResult(
            grep=GREP_NAME,
            root=str(root),
            passed=True,
            not_yet_materialised=True,
        )
    findings: list[Finding] = []
    candidates = sorted([*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")])
    for workflow_path in candidates:
        findings.extend(_inspect_workflow(workflow_path, root))
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        passed=not findings,
        findings=findings,
    )


def _main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) >= 2 else Path.cwd()
    result = check_root(root)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
