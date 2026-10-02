# SPDX-License-Identifier: MIT

"""The npm shim runs in CI on every Node major in the declared range.

These assertions read the in-tree workflow, not live GitHub. The shim
(``bin/apothem.mjs``) is what every npx, VS Code, Gemini, Qwen and Codex user
runs, and ``package.json`` declares ``engines.node >=18``. The workflow must
exercise that floor and every later even (LTS) major, on the Python floor
``requires-python`` declares, with every action pinned by commit SHA.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "npm-shim.yml"
_SHA_PIN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def _load() -> dict:
    assert _WORKFLOW.is_file(), f"missing workflow: {_WORKFLOW}"
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _job() -> dict:
    jobs = _load()["jobs"]
    assert "shim" in jobs, sorted(jobs)
    return jobs["shim"]


def _run_text(job: dict) -> str:
    return "\n".join(str(step.get("run", "")) for step in job["steps"])


def test_matrix_covers_the_declared_node_floor_and_later_lts_majors() -> None:
    engines = json.loads((_REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    floor = int(re.sub(r"[^0-9]", "", engines["engines"]["node"]))
    nodes = {str(v) for v in _job()["strategy"]["matrix"]["node"]}
    assert {str(floor), "20", "22", "24"} <= nodes


def test_shim_job_runs_on_the_python_floor() -> None:
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'requires-python\s*=\s*">=([0-9.]+)"', pyproject)
    assert match is not None
    python_steps = [
        step
        for step in _job()["steps"]
        if str(step.get("uses", "")).startswith("actions/setup-python@")
    ]
    assert python_steps, "the shim job must set up Python"
    assert str(python_steps[0]["with"]["python-version"]) == match.group(1)


def test_shim_job_runs_version_and_an_isolated_dry_run_install() -> None:
    text = _run_text(_job())
    assert "node bin/apothem.mjs --version" in text
    assert "install --harness claude-code --dry-run" in text
    assert 'HOME="$RUNNER_TEMP' in text


def test_shim_job_checks_the_missing_prerequisite_error() -> None:
    assert "-m pip install" in _run_text(_job())


def test_every_action_is_pinned_by_sha() -> None:
    for step in _job()["steps"]:
        uses = step.get("uses")
        if uses is not None:
            assert _SHA_PIN.match(str(uses).split()[0]), uses


def test_workflow_is_read_only() -> None:
    assert _load()["permissions"] == {"contents": "read"}
