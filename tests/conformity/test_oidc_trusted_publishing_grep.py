# SPDX-License-Identifier: MIT

"""oidc-trusted-publishing-grep against its documented fixtures.

The fail fixture's README documents four drift classes for the npm workflow,
including ``legacy-token-secret-reference`` for ``secrets.NPM_TOKEN``, but the
validator only implemented the token check for PyPI, and no test ran the
fixtures, so the gap went unnoticed while the live npm workflow kept a
``NODE_AUTH_TOKEN`` path beside OIDC trusted publishing.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from apothem.conformity import oidc_trusted_publishing_grep as grep

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).resolve().parent / "oidc-trusted-publishing-grep"


def _root_with(tmp_path: Path, variant: str) -> Path:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    for source in (_FIXTURES / variant).glob("*.yml"):
        shutil.copyfile(source, workflows / source.name)
    return tmp_path


def _classes(result: grep.GrepResult, workflow: str) -> set[str]:
    return {f.drift_class for f in result.findings if f.workflow == workflow}


def test_fail_fixture_reports_every_documented_npm_drift(tmp_path: Path) -> None:
    result = grep.check(_root_with(tmp_path, "fail"))
    assert not result.passed
    assert _classes(result, "packaging-npm.yml") == {
        "missing-id-token-permission",
        "legacy-token-secret-reference",
        "npm-runtime-too-old",
        "npm-cli-floor-absent",
    }


def test_fail_fixture_reports_every_documented_pypi_drift(tmp_path: Path) -> None:
    result = grep.check(_root_with(tmp_path, "fail"))
    assert _classes(result, "publish-pypi.yml") == {
        "missing-id-token-permission",
        "action-version-too-old",
        "legacy-token-secret-reference",
    }


def test_pass_fixture_is_clean(tmp_path: Path) -> None:
    result = grep.check(_root_with(tmp_path, "pass"))
    assert result.passed, result.findings


def test_repository_release_workflows_pass() -> None:
    result = grep.check(_REPO_ROOT)
    assert "publish-npm.yml" in result.workflows_inspected
    assert result.passed, result.findings
