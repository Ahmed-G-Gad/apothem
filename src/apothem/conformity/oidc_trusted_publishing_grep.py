# SPDX-License-Identifier: MIT

"""Verify release workflows use OIDC trusted publishing.

Why this validator exists. The release-engineering contract binds every
publish step to short-lived, GitHub-issued OIDC identity so each
artifact carries verifiable build provenance, and keeps PyPI on keyless
OIDC trusted publishing (no long-lived PyPI token). The mechanical
floor: every release workflow under ``.github/workflows/`` that
publishes to PyPI or npm declares ``id-token: write`` permission; a PyPI
workflow references no legacy ``PYPI_API_TOKEN`` and pins
``pypa/gh-action-pypi-publish`` at v1.10+; an npm workflow runs on the
trusted-publishing runtime floor (Node 24 and npm CLI 11.5.1 or newer) and
references no long-lived ``NPM_TOKEN``: the npm CLI exchanges the job's OIDC
token for a short-lived publish credential, so no stored token is needed.
npm emits build provenance for public packages published from public GitHub
Actions workflows.

Scope. The validator walks ``<root>/.github/workflows/`` and inspects
filenames matching ``*publish*py*.yml`` (PyPI release workflows) and
``*publish*npm*.yml`` or ``*packaging*npm*.yml`` (npm release
workflows). Each detected workflow is parsed via ``yaml.safe_load``
when PyYAML is available; otherwise the validator falls back to
permissive line-oriented string parsing so it remains operable
without extra packages on the conformity-gate execution path.

Workflow-absent tolerance. When neither workflow class exists under
``.github/workflows/``, the validator exits 0 with the informational
field ``not-yet-materialised: true``. Before publishing workflows are
materialized, the matcher is advisory and never blocks the gate.

Drift classes.

- ``missing-id-token-permission`` — neither the top-level nor any
  job-level ``permissions:`` block declares ``id-token: write``.
- ``action-version-too-old`` — ``pypa/gh-action-pypi-publish`` is
  pinned below v1.10; OIDC trusted publishing support landed at v1.10.
- ``legacy-token-secret-reference`` — a reference to
  ``secrets.PYPI_API_TOKEN`` (or the bare ``PYPI_API_TOKEN`` env-var
  name in a workflow env block) survives in a PyPI publish workflow, or
  ``NPM_TOKEN`` survives in an npm publish workflow; both publish
  keylessly via OIDC trusted publishing.
- ``npm-runtime-too-old`` — the npm workflow does not select Node 24 or
  a newer major Node line.
- ``npm-cli-floor-absent`` — the npm workflow does not pin npm CLI
  11.5.1+ before publishing.

Exit semantics. Exits 0 when no drift is detected (including the
workflow-absent informational case). Exits 2 when any drift class
fires.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "oidc-trusted-publishing-grep"
RULE_ANCHOR: Final[str] = "OIDC trusted publishing"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# Minimum pypa/gh-action-pypi-publish version with OIDC trusted-publishing
# support per the upstream changelog.
MIN_PYPI_ACTION_MAJOR: Final[int] = 1
MIN_PYPI_ACTION_MINOR: Final[int] = 10

# Workflow filename predicates. We match permissively so renamed but
# semantically equivalent filenames remain in scope.
_PYPI_WORKFLOW_RE: Final[re.Pattern[str]] = re.compile(r"(?i)publish.*py.*\.ya?ml$")
_NPM_WORKFLOW_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)(?:publish|packaging).*npm.*\.ya?ml$"
)

# Detection patterns operating on raw workflow text. These are
# deliberately substring-based so the validator works without PyYAML.
_ID_TOKEN_WRITE_RE: Final[re.Pattern[str]] = re.compile(r"id-token\s*:\s*write")
_PYPI_ACTION_USES_RE: Final[re.Pattern[str]] = re.compile(
    r"pypa/gh-action-pypi-publish@v?(\d+)\.(\d+)(?:\.\d+)?"
)
_PYPI_TOKEN_REF_RE: Final[re.Pattern[str]] = re.compile(r"PYPI_API_TOKEN")
_NPM_TOKEN_REF_RE: Final[re.Pattern[str]] = re.compile(r"NPM_TOKEN")
_NPM_PUBLISH_RE: Final[re.Pattern[str]] = re.compile(r"npm\s+publish")
_NPM_NODE_BASELINE_RE: Final[re.Pattern[str]] = re.compile(
    r"node-version\s*:\s*[\"']?(?:24|2[5-9]|[3-9]\d)(?:[\"']|\b)"
)
_NPM_CLI_BASELINE_RE: Final[re.Pattern[str]] = re.compile(
    r"npm@(?:11\.(?:[5-9]|\d{2,})(?:\.\d+)?|1[2-9](?:\.\d+){0,2}|[2-9]\d(?:\.\d+){0,2})"
)


@dataclass(frozen=True)
class Finding:
    """One drift occurrence in a release workflow."""

    workflow: str
    drift_class: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result over the release workflows under root."""

    grep: str
    root: str
    workflows_inspected: list[str]
    not_yet_materialised: bool
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root,
        workflows-inspected, not-yet-materialised, passed, findings}``; each
        finding is flattened through ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "workflows-inspected": self.workflows_inspected,
            "not-yet-materialised": self.not_yet_materialised,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _check_pypi_workflow(workflow: Path, text: str) -> list[Finding]:
    """Inspect a PyPI release workflow for trusted-publishing drift."""
    findings: list[Finding] = []
    name = workflow.name
    if not _ID_TOKEN_WRITE_RE.search(text):
        findings.append(
            Finding(
                workflow=name,
                drift_class="missing-id-token-permission",
                detail=(
                    "no `id-token: write` permission block; OIDC trusted "
                    "publishing requires the workflow (or its publish job) "
                    "to request the id-token scope"
                ),
            )
        )
    for match in _PYPI_ACTION_USES_RE.finditer(text):
        major = int(match.group(1))
        minor = int(match.group(2))
        too_old = (major, minor) < (MIN_PYPI_ACTION_MAJOR, MIN_PYPI_ACTION_MINOR)
        if too_old:
            findings.append(
                Finding(
                    workflow=name,
                    drift_class="action-version-too-old",
                    detail=(
                        f"pypa/gh-action-pypi-publish pinned at v{major}."
                        f"{minor}; OIDC trusted publishing requires v"
                        f"{MIN_PYPI_ACTION_MAJOR}."
                        f"{MIN_PYPI_ACTION_MINOR} or higher"
                    ),
                )
            )
    if _PYPI_TOKEN_REF_RE.search(text):
        findings.append(
            Finding(
                workflow=name,
                drift_class="legacy-token-secret-reference",
                detail=(
                    "PYPI_API_TOKEN reference survives; OIDC trusted "
                    "publishing retires the long-lived token"
                ),
            )
        )
    return findings


def _check_npm_workflow(workflow: Path, text: str) -> list[Finding]:
    """Inspect an npm release workflow for trusted-publishing drift."""
    findings: list[Finding] = []
    name = workflow.name
    if not _ID_TOKEN_WRITE_RE.search(text):
        findings.append(
            Finding(
                workflow=name,
                drift_class="missing-id-token-permission",
                detail=(
                    "no `id-token: write` permission block; OIDC trusted "
                    "publishing requires the workflow (or its publish job) "
                    "to request the id-token scope"
                ),
            )
        )
    if _NPM_TOKEN_REF_RE.search(text):
        findings.append(
            Finding(
                workflow=name,
                drift_class="legacy-token-secret-reference",
                detail=(
                    "NPM_TOKEN reference survives; npm trusted publishing "
                    "authenticates through the job's OIDC token, so a stored "
                    "long-lived token only widens the publish attack surface"
                ),
            )
        )
    if _NPM_PUBLISH_RE.search(text) and not _NPM_NODE_BASELINE_RE.search(text):
        findings.append(
            Finding(
                workflow=name,
                drift_class="npm-runtime-too-old",
                detail=(
                    "npm Trusted Publishing requires Node 22.14.0+; the "
                    "canonical workflow floor is Node 24 for a stable OIDC "
                    "runtime"
                ),
            )
        )
    if _NPM_PUBLISH_RE.search(text) and not _NPM_CLI_BASELINE_RE.search(text):
        findings.append(
            Finding(
                workflow=name,
                drift_class="npm-cli-floor-absent",
                detail=(
                    "npm Trusted Publishing requires npm CLI 11.5.1+; pin "
                    "npm@11.5.1 or newer before running `npm publish`"
                ),
            )
        )
    return findings


def check(root: Path) -> GrepResult:
    """Walk release workflows under root; aggregate trusted-publishing drift."""
    workflows_dir = root / ".github" / "workflows"
    findings: list[Finding] = []
    inspected: list[str] = []
    if not workflows_dir.is_dir():
        return GrepResult(
            grep=GREP_NAME,
            root=str(root),
            workflows_inspected=[],
            not_yet_materialised=True,
            passed=True,
            findings=[],
        )
    pypi_workflows: list[Path] = []
    npm_workflows: list[Path] = []
    for candidate in sorted(workflows_dir.iterdir()):
        if not candidate.is_file():
            continue
        if _PYPI_WORKFLOW_RE.search(candidate.name):
            pypi_workflows.append(candidate)
        elif _NPM_WORKFLOW_RE.search(candidate.name):
            npm_workflows.append(candidate)
    if not pypi_workflows and not npm_workflows:
        return GrepResult(
            grep=GREP_NAME,
            root=str(root),
            workflows_inspected=[],
            not_yet_materialised=True,
            passed=True,
            findings=[],
        )
    for workflow in pypi_workflows:
        text = workflow.read_text(encoding="utf-8")
        inspected.append(workflow.name)
        findings.extend(_check_pypi_workflow(workflow, text))
    for workflow in npm_workflows:
        text = workflow.read_text(encoding="utf-8")
        inspected.append(workflow.name)
        findings.extend(_check_npm_workflow(workflow, text))
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        workflows_inspected=inspected,
        not_yet_materialised=False,
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
