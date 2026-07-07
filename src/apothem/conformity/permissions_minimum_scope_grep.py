# SPDX-License-Identifier: MIT

"""Verify every GitHub Actions workflow declares a minimum-scope ``permissions:`` block.

Why this enforcement exists. GitHub Actions workflows inherit a
default-broad permissions surface (``write-all`` on the repository
token) unless they explicitly narrow it. A workflow that silently
consumes the default scope hands every job the keys to the repository
- contents write, packages write, deployments write, issues write -
regardless of whether the job's actual work requires any of them. The
minimum-scope discipline requires each workflow to declare a top-level
``permissions:`` block enumerating only the scopes its jobs need; the
default-broad surface is replaced with an audit-friendly,
least-privilege grant.

Detection. Walks ``<root>/.github/workflows/*.yml`` (and ``.yaml``).
For each workflow:

1. Verify a top-level ``permissions:`` key exists.
2. Verify the block is NOT ``permissions: write-all`` (the over-scoped
   default).
3. Surface an advisory when ``contents: write`` is granted but no
   push-style step is detected (heuristic for undocumented permission
   elevation).

Drift classes:

- ``missing-top-level-permissions-block``
- ``overscoped-permission`` (``write-all`` declared)
- ``undocumented-permission-elevation`` (advisory; ``contents: write``
  declared without an observable push step)

Special case. When ``<root>/.github/workflows/`` does not exist, the
validator exits 0 with ``not-yet-materialised: true`` so projects that
have not yet introduced CI workflows are not blocked by the gate.

Exit semantics. Exits 0 when every workflow carries a conformant
permissions block; exits 2 with a JSON report listing per-workflow
drift classes otherwise. Advisory-severity findings (the
``undocumented-permission-elevation`` class) do NOT trigger exit 2 on
their own — they surface in the JSON for operator review without
blocking the gate.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

GREP_NAME: Final[str] = "permissions-minimum-scope-grep"
RULE_ANCHOR: Final[str] = "minimum-scope workflow permissions"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

SEVERITY_BLOCKING: Final[str] = "blocking"
SEVERITY_ADVISORY: Final[str] = "advisory"

# Drift class identifiers surfaced in finding payloads.
DRIFT_MISSING: Final[str] = "missing-top-level-permissions-block"
DRIFT_OVERSCOPED: Final[str] = "overscoped-permission"
DRIFT_UNDOCUMENTED_ELEVATION: Final[str] = "undocumented-permission-elevation"

# Heuristic tokens that suggest a workflow performs a push-style write to
# the repository — when any of these appears in a step's ``run`` body or
# in a third-party action ``uses:`` reference, the ``contents: write``
# grant is considered justified and the advisory does not fire.
_PUSH_STEP_TOKENS: Final[tuple[str, ...]] = (
    "git push",
    "git commit",
    "git tag",
    "peter-evans/create-pull-request",
    "stefanzweifel/git-auto-commit-action",
    "ad-m/github-push-action",
    "softprops/action-gh-release",
    "actions/create-release",
    "ncipollo/release-action",
)


@dataclass(frozen=True)
class Finding:
    """One workflow-level permissions drift."""

    workflow: str
    drift_class: str
    severity: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result for a single workflows-directory sweep."""

    grep: str
    root: str
    workflows_dir: str
    workflow_count: int
    passed: bool
    not_yet_materialised: bool = False
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        payload = {
            "grep": self.grep,
            "root": self.root,
            "workflows_dir": self.workflows_dir,
            "workflow_count": self.workflow_count,
            "not_yet_materialised": self.not_yet_materialised,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _iter_workflow_files(workflows_dir: Path) -> list[Path]:
    """Return every ``*.yml`` / ``*.yaml`` file at the workflows root.

    The walk is non-recursive: GitHub Actions only picks up workflows
    that sit directly under ``.github/workflows/``; nested directories
    are ignored by the platform and so by this validator.
    """
    files: list[Path] = []
    for pattern in ("*.yml", "*.yaml"):
        files.extend(workflows_dir.glob(pattern))
    return sorted(files)


def _has_push_step(parsed: dict[str, Any]) -> bool:
    """Heuristic: does any job step suggest a push-style write?

    Inspects every job's ``steps`` list for a ``run:`` body containing
    a push-style command, or a ``uses:`` reference to a known
    push-style action. The heuristic is intentionally permissive — a
    false negative (advisory fires when push is actually present)
    surfaces in the JSON for operator triage rather than blocking.
    """
    jobs = parsed.get("jobs")
    if not isinstance(jobs, dict):
        return False
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            run_body = step.get("run")
            uses_ref = step.get("uses")
            haystack_parts: list[str] = []
            if isinstance(run_body, str):
                haystack_parts.append(run_body)
            if isinstance(uses_ref, str):
                haystack_parts.append(uses_ref)
            haystack = "\n".join(haystack_parts).lower()
            if any(token.lower() in haystack for token in _PUSH_STEP_TOKENS):
                return True
    return False


def _grants_contents_write(permissions: object) -> bool:
    """Return True when the ``permissions:`` block grants ``contents: write``."""
    if not isinstance(permissions, dict):
        return False
    contents = permissions.get("contents")
    return isinstance(contents, str) and contents.strip().lower() == "write"


def _classify_workflow(
    workflow: Path,
    parsed: dict[str, Any] | None,
) -> list[Finding]:
    """Classify a single workflow's permissions surface.

    Returns the per-workflow finding list. An unparseable workflow
    (YAML error, non-mapping root) yields a blocking finding under
    ``missing-top-level-permissions-block`` because the validator
    cannot prove the block exists.
    """
    rel = workflow.name
    if parsed is None or not isinstance(parsed, dict):
        return [
            Finding(
                workflow=rel,
                drift_class=DRIFT_MISSING,
                severity=SEVERITY_BLOCKING,
                detail=(
                    "workflow YAML did not parse as a mapping; cannot verify "
                    "top-level permissions block"
                ),
            )
        ]
    if "permissions" not in parsed:
        return [
            Finding(
                workflow=rel,
                drift_class=DRIFT_MISSING,
                severity=SEVERITY_BLOCKING,
                detail=(
                    "no top-level `permissions:` key; workflow inherits the "
                    "default-broad GitHub Actions permissions surface "
                    "(equivalent to write-all)"
                ),
            )
        ]
    permissions = parsed["permissions"]
    findings: list[Finding] = []
    if isinstance(permissions, str) and permissions.strip().lower() == "write-all":
        findings.append(
            Finding(
                workflow=rel,
                drift_class=DRIFT_OVERSCOPED,
                severity=SEVERITY_BLOCKING,
                detail=(
                    "`permissions: write-all` grants the default-broad surface; "
                    "replace with explicit per-scope grants (e.g. `contents: read`)"
                ),
            )
        )
    if _grants_contents_write(permissions) and not _has_push_step(parsed):
        findings.append(
            Finding(
                workflow=rel,
                drift_class=DRIFT_UNDOCUMENTED_ELEVATION,
                severity=SEVERITY_ADVISORY,
                detail=(
                    "`contents: write` granted but no push-style step "
                    "(git push / release-action / create-pull-request) "
                    "was detected; verify the elevation is required"
                ),
            )
        )
    return findings


def check(root: Path) -> GrepResult:
    """Walk every workflow under ``<root>/.github/workflows/``.

    Pre-conditions: ``root`` is the project root containing a
    ``.github/workflows/`` directory (or not — the absence case is
    tolerated). Post-conditions: ``result.passed`` is True iff every
    workflow carries a top-level ``permissions:`` block that is not
    ``write-all``; advisory findings do not affect ``passed``.
    """
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return GrepResult(
            grep=GREP_NAME,
            root=str(root),
            workflows_dir=str(workflows_dir),
            workflow_count=0,
            passed=True,
            not_yet_materialised=True,
            findings=[],
        )
    workflows = _iter_workflow_files(workflows_dir)
    findings: list[Finding] = []
    for workflow in workflows:
        try:
            raw = workflow.read_text(encoding="utf-8")
            parsed = yaml.safe_load(raw)
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            parsed = None
        findings.extend(_classify_workflow(workflow, parsed))
    blocking = [f for f in findings if f.severity == SEVERITY_BLOCKING]
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        workflows_dir=str(workflows_dir),
        workflow_count=len(workflows),
        passed=not blocking,
        not_yet_materialised=False,
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
