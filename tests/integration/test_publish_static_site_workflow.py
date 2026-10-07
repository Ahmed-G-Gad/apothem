# SPDX-License-Identifier: MIT

"""Only a run on main can publish the static site.

These assertions read the in-tree workflow, not live GitHub. The workflow runs
on ``workflow_dispatch``, which can start on any branch, and its per-ref
concurrency group does not queue such a run behind main's deploy. Every job
that can publish to GitHub Pages must therefore carry the job-level guard
``if: github.ref == 'refs/heads/main'``. The build job stays unguarded, so a
dispatch on any other branch is a dry run that builds without deploying.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "publish-static-site.yml"
)
_MAIN_ONLY = "github.ref == 'refs/heads/main'"


def _jobs() -> dict:
    assert _WORKFLOW.is_file(), f"missing workflow: {_WORKFLOW}"
    doc = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    # A job without its own `permissions:` inherits the workflow-level grant.
    root = doc.get("permissions")
    return {
        name: job if "permissions" in job else {**job, "permissions": root}
        for name, job in doc["jobs"].items()
    }


def _condition(job: dict) -> str | None:
    raw = job.get("if")
    if raw is None:
        return None
    # A job-level `if:` may wrap its expression in `${{ }}`. Both forms are equal.
    text = str(raw).strip()
    wrapped = re.fullmatch(r"\$\{\{(.*)\}\}", text, flags=re.DOTALL)
    if wrapped:
        text = wrapped.group(1)
    return " ".join(text.split())


def _publishes_to_pages(job: dict) -> bool:
    environment = job.get("environment")
    if isinstance(environment, dict):
        environment = environment.get("name")
    permissions = job.get("permissions")
    return (
        # GitHub environment names are not case sensitive.
        str(environment).lower() == "github-pages"
        or permissions == "write-all"
        or (isinstance(permissions, dict) and permissions.get("pages") == "write")
        or any(
            str(step.get("uses", "")).startswith("actions/deploy-pages@")
            for step in job.get("steps", [])
        )
    )


def test_every_pages_deploy_job_runs_from_main_only() -> None:
    publishers = {
        name: job for name, job in _jobs().items() if _publishes_to_pages(job)
    }
    assert publishers, "expected at least one job that publishes to Pages"
    for name, job in publishers.items():
        assert _condition(job) == _MAIN_ONLY, (
            f"job {name!r} can publish to Pages, so it must carry "
            f"`if: {_MAIN_ONLY}`, found {job.get('if')!r}"
        )


def test_build_job_still_runs_on_any_branch_as_a_dry_run() -> None:
    build = _jobs()["build"]
    assert "if" not in build, "the build job must run on a dispatch from any branch"
    assert not _publishes_to_pages(build), (
        "the build job must not hold deploy authority"
    )
