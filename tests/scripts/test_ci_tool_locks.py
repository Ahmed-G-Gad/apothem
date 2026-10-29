# SPDX-License-Identifier: MIT

"""The CI tool locks are wired into the workflows, and ruff has one version.

Five CI tools install from their own hash-locked files in ``scripts/ci/``
(``requirements-ci-ruff.txt``, ``-bandit.txt``, ``-pip-audit.txt``,
``-pip-licenses.txt``, ``-pre-commit.txt``), compiled by
``scripts/dev/refresh_ci_locks.py`` from the specs in
``scripts/dev/ci_lock_table.py``. This module keeps three things from drifting:

* ruff is pinned exactly in five places that must agree: the dev extra of
  ``pyproject.toml``, the ``ruff-pre-commit`` rev in ``.pre-commit-config.yaml``,
  the spec in the table, the ruff lock and the dev lock. A Dependabot security
  pull request edits only ``pyproject.toml``, and fails here until the rest follow.
* The workflows that install a tool lock do it with ``--require-hashes``, carry no
  tool version of their own, install the pip lock first, run on a Python the lock
  supports, start when the lock changes and key their pip cache on it.
* ``pip-audit.yml`` audits every lock with the OSV service on one Python that
  every lock supports, each audit step carries ``continue-on-error`` so that
  every audit reports, and Dependabot's ``/scripts/ci`` entry stays limited to the
  one dependency it maintains, pip.

PyYAML is a runtime dependency of the package; ``tomllib`` (or ``tomli`` on Python
3.10) and ``packaging`` come with the dev environment.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

if sys.version_info >= (3, 11):
    import tomllib
else:  # Python 3.10: tomli is in the dev lock for python_full_version < 3.11.
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import refresh_ci_locks  # noqa: E402

CI_DIR = REPO_ROOT / "scripts" / "ci"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
REFRESH = "scripts/dev/refresh_ci_locks.py"
PIP_LOCK = "scripts/ci/requirements-ci-pip.txt"
TOOL_LOCKS = [lock for lock in refresh_ci_locks.LOCKS if lock.tool]

# Which workflow installs which tool lock. The table's `installed_by` prose names
# the same workflows; this is the checked form.
CONSUMERS = {
    "requirements-ci-ruff.txt": ["conformity.yml"],
    "requirements-ci-bandit.txt": ["ci.yml"],
    "requirements-ci-pip-audit.txt": ["ci.yml", "pip-audit.yml"],
    "requirements-ci-pip-licenses.txt": ["license-audit.yml"],
    "requirements-ci-pre-commit.txt": ["markdown-lint.yml"],
}
_LOCK_INSTALL_RE = re.compile(
    r"--require-hashes\s+-r\s+\"?(scripts/ci/requirements-ci-[a-z-]+\.txt)\"?"
)


def _workflow_text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _workflow(name: str) -> dict[str, Any]:
    document = yaml.safe_load(_workflow_text(name))
    assert isinstance(document, dict), name
    return document


def _triggers(document: dict[str, Any]) -> dict[str, Any]:
    # YAML 1.1 reads the bare `on:` key as the boolean True.
    triggers = document.get("on", document.get(True))
    assert isinstance(triggers, dict)
    return triggers


def _jobs(name: str) -> dict[str, dict[str, Any]]:
    jobs = _workflow(name)["jobs"]
    assert isinstance(jobs, dict)
    return jobs


def _run_text(job: dict[str, Any]) -> str:
    """Return the `run` text of every step of ``job``, in step order."""
    return "\n".join(str(step["run"]) for step in job["steps"] if "run" in step)


def _jobs_installing(name: str, relpath: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (job_id, job)
        for job_id, job in _jobs(name).items()
        if f"--require-hashes -r {relpath}" in _run_text(job)
    ]


def _setup_python_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        step
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/setup-python@")
    ]


# --- ruff has one version -------------------------------------------------------


def _pyproject_ruff_pin() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = data["project"]["optional-dependencies"]["dev"]
    requirements = [Requirement(text) for text in dev]
    ruff = [r for r in requirements if canonicalize_name(r.name) == "ruff"]
    assert len(ruff) == 1, "the dev extra must name ruff exactly once"
    operators = [item.operator for item in ruff[0].specifier]
    assert operators == ["=="], f"the dev extra must pin ruff with ==, not {ruff[0]}"
    return next(iter(ruff[0].specifier)).version


def _hook_rev() -> str:
    config = yaml.safe_load(
        (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    revs = [
        repo["rev"]
        for repo in config["repos"]
        if str(repo["repo"]).endswith("/astral-sh/ruff-pre-commit")
    ]
    assert len(revs) == 1, "expected one astral-sh/ruff-pre-commit repo"
    assert revs[0].startswith("v"), revs[0]
    return str(revs[0])[1:]


def _locked_version(filename: str) -> str:
    text = (CI_DIR / filename).read_bytes().decode("utf-8")
    found = re.findall(r"^ruff==(\S+)(?= |$)", text, flags=re.MULTILINE)
    assert len(found) == 1, f"{filename} must pin ruff once, found {found}"
    return found[0]


def _table_version() -> str:
    lock = refresh_ci_locks.lock_by_filename("requirements-ci-ruff.txt")
    (spec,) = lock.stdin_requirements
    name, _, version = spec.partition("==")
    assert name == "ruff", spec
    return version


def assert_one_ruff_version(versions: dict[str, str]) -> None:
    """Fail naming each place, and the fix, unless all places carry one version."""
    if len(set(versions.values())) == 1:
        return
    listing = "\n".join(
        f"  - {place}: {version}" for place, version in versions.items()
    )
    raise AssertionError(
        "ruff must be one version in every place it is pinned:\n"
        f"{listing}\n"
        "Move them together: the exact pin in pyproject.toml (dev extra), the "
        "ruff-pre-commit rev in .pre-commit-config.yaml (vX.Y.Z), the spec in "
        f"scripts/dev/ci_lock_table.py, then run `python {REFRESH}` to regenerate "
        "the locks. The release must be older than the lock cooldown."
    )


def test_ruff_has_one_version_in_pyproject_the_hook_the_table_and_both_locks() -> None:
    assert_one_ruff_version(
        {
            "pyproject.toml dev extra": _pyproject_ruff_pin(),
            ".pre-commit-config.yaml ruff-pre-commit rev": _hook_rev(),
            "scripts/dev/ci_lock_table.py ruff spec": _table_version(),
            "scripts/ci/requirements-ci-ruff.txt": _locked_version(
                "requirements-ci-ruff.txt"
            ),
            "scripts/ci/requirements-ci-dev.txt": _locked_version(
                "requirements-ci-dev.txt"
            ),
        }
    )


def test_a_ruff_version_that_differs_in_one_place_is_reported() -> None:
    skewed = {
        "pyproject.toml dev extra": "0.17.2",
        ".pre-commit-config.yaml ruff-pre-commit rev": "0.17.1",
        "scripts/ci/requirements-ci-ruff.txt": "0.17.1",
    }
    with pytest.raises(AssertionError) as raised:
        assert_one_ruff_version(skewed)
    message = str(raised.value)
    assert "pyproject.toml dev extra: 0.17.2" in message
    assert "ruff-pre-commit rev: 0.17.1" in message
    assert REFRESH in message
    assert_one_ruff_version({"a": "0.17.1", "b": "0.17.1"})


def test_the_dev_extra_pins_ruff_exactly_and_no_floor_is_left() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", _pyproject_ruff_pin())


def test_dependabot_leaves_the_ruff_hook_to_the_lockstep() -> None:
    document = yaml.safe_load(
        (REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    )
    hooks = [e for e in document["updates"] if e["package-ecosystem"] == "pre-commit"]
    assert len(hooks) == 1
    ignored = [item["dependency-name"] for item in hooks[0]["ignore"]]
    assert "*ruff-pre-commit" in ignored


# --- the workflows install each lock the way the lock expects -------------------


@pytest.mark.parametrize("filename", [lock.filename for lock in TOOL_LOCKS])
def test_each_consumer_installs_the_tool_lock_with_hashes(filename: str) -> None:
    relpath = f"scripts/ci/{filename}"
    for workflow in CONSUMERS[filename]:
        assert _jobs_installing(workflow, relpath), (
            f"{workflow} must install {relpath} with "
            f"`python -m pip install --require-hashes -r {relpath}`"
        )


def test_the_consumers_table_covers_every_tool_lock() -> None:
    assert sorted(CONSUMERS) == sorted(lock.filename for lock in TOOL_LOCKS)


def test_no_workflow_installs_a_tool_lock_it_is_not_listed_for() -> None:
    for path in sorted(WORKFLOWS.glob("*.yml")):
        installed = set(_LOCK_INSTALL_RE.findall(path.read_text(encoding="utf-8")))
        for lock in TOOL_LOCKS:
            if lock.relpath in installed:
                assert path.name in CONSUMERS[lock.filename], (
                    f"{path.name} installs {lock.relpath}; add it to CONSUMERS "
                    "here, to `installed_by` in scripts/dev/ci_lock_table.py and "
                    "to scripts/ci/README.md"
                )


def test_every_table_lock_is_named_by_some_workflow() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(WORKFLOWS.glob("*.yml"))
    )
    for lock in refresh_ci_locks.LOCKS:
        assert lock.relpath in text, f"no workflow names {lock.relpath}"


def test_no_workflow_carries_a_tool_version_of_its_own() -> None:
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for lock in TOOL_LOCKS:
            (spec,) = lock.stdin_requirements
            assert spec not in text, (
                f"{path.name} spells `{spec}`; the version lives in "
                "scripts/dev/ci_lock_table.py and the workflow installs the lock"
            )


@pytest.mark.parametrize("filename", [lock.filename for lock in TOOL_LOCKS])
def test_the_pip_lock_is_installed_before_a_tool_lock_in_the_same_job(
    filename: str,
) -> None:
    relpath = f"scripts/ci/{filename}"
    for workflow in CONSUMERS[filename]:
        for job_id, job in _jobs_installing(workflow, relpath):
            text = _run_text(job)
            if PIP_LOCK not in text:
                continue  # ci.yml security-scan keeps the runner's pip
            assert text.index(f"-r {PIP_LOCK}") < text.index(f"-r {relpath}"), (
                f"{workflow} job {job_id} installs {relpath} before the pip lock; "
                "the pip lock goes first so the tool lock cannot replace its pip"
            )


@pytest.mark.parametrize("filename", [lock.filename for lock in TOOL_LOCKS])
def test_each_job_sets_up_a_python_the_lock_supports(filename: str) -> None:
    lock = refresh_ci_locks.lock_by_filename(filename)
    floor = tuple(int(part) for part in lock.python_floor.split("."))
    for workflow in CONSUMERS[filename]:
        for job_id, job in _jobs_installing(workflow, lock.relpath):
            versions: list[str] = []
            for step in _setup_python_steps(job):
                value = str(step["with"]["python-version"])
                if "matrix.python-version" in value:
                    versions.extend(
                        map(str, job["strategy"]["matrix"]["python-version"])
                    )
                else:
                    versions.append(value)
            assert versions, f"{workflow} job {job_id} has no setup-python step"
            for version in versions:
                parsed = tuple(int(part) for part in version.split(".")[:2])
                assert parsed >= floor, (
                    f"{workflow} job {job_id} runs Python {version}, below the "
                    f"{lock.python_floor} floor of {lock.relpath}"
                )


def test_markdown_lint_stays_on_a_python_that_pre_commit_supports() -> None:
    job = _jobs("markdown-lint.yml")["markdownlint"]
    (step,) = _setup_python_steps(job)
    version = tuple(
        int(part) for part in str(step["with"]["python-version"]).split(".")
    )
    assert version >= (3, 11)


# --- a change to a lock starts the workflow that installs it -------------------


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a GitHub Actions path filter to a regular expression."""
    out: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            out.append(".*")
            index += 2
        elif pattern[index] == "*":
            out.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(out) + r"\Z")


def _matches(patterns: list[str], path: str) -> bool:
    positive = [p for p in patterns if not p.startswith("!")]
    return any(_glob_to_regex(p).match(path) for p in positive)


def test_the_glob_translation_follows_github_path_filters() -> None:
    assert _matches(["scripts/**"], "scripts/ci/requirements-ci-ruff.txt")
    assert _matches(["scripts/ci/requirements-ci-*.txt"], PIP_LOCK)
    assert _matches(["**/*.md"], "README.md")
    assert _matches(["**/*.md"], "docs/a/b.md")
    assert not _matches(["scripts/*"], "scripts/ci/requirements-ci-ruff.txt")
    assert not _matches(["scripts/ci/requirements-ci-runtime.txt"], PIP_LOCK)


@pytest.mark.parametrize("filename", [lock.filename for lock in TOOL_LOCKS])
def test_a_tool_lock_change_starts_each_workflow_that_installs_it(
    filename: str,
) -> None:
    relpath = f"scripts/ci/{filename}"
    for workflow in CONSUMERS[filename]:
        for event in ("push", "pull_request"):
            trigger = _triggers(_workflow(workflow)).get(event)
            if not isinstance(trigger, dict) or "paths" not in trigger:
                continue  # no path filter: the event always starts the workflow
            assert _matches(trigger["paths"], relpath), (
                f"{workflow} `{event}` paths do not match {relpath}; a refresh that "
                "changes only that lock would merge without the job running"
            )


# --- the pip cache is keyed on the locks the job installs -----------------------


def _cache_paths(step: dict[str, Any]) -> list[str]:
    value = str(step["with"].get("cache-dependency-path", ""))
    return [line.strip() for line in value.splitlines() if line.strip()]


@pytest.mark.parametrize("filename", [lock.filename for lock in TOOL_LOCKS])
def test_a_pip_cache_is_keyed_on_the_tool_lock_the_job_installs(filename: str) -> None:
    relpath = f"scripts/ci/{filename}"
    for workflow in CONSUMERS[filename]:
        for job_id, job in _jobs_installing(workflow, relpath):
            cached = [
                step
                for step in _setup_python_steps(job)
                if str(step["with"].get("cache")) == "pip"
            ]
            for step in cached:
                assert relpath in _cache_paths(step), (
                    f"{workflow} job {job_id} caches pip without keying on {relpath}; "
                    "list it in cache-dependency-path (one path per line)"
                )


def test_the_pip_audit_cache_is_keyed_on_the_pip_and_pip_audit_locks() -> None:
    (step,) = _setup_python_steps(_jobs("pip-audit.yml")["audit"])
    assert _cache_paths(step) == [PIP_LOCK, "scripts/ci/requirements-ci-pip-audit.txt"]


def test_the_license_audit_cache_is_keyed_on_both_locks_it_installs() -> None:
    (step,) = _setup_python_steps(_jobs("license-audit.yml")["audit"])
    assert _cache_paths(step) == [
        "scripts/ci/requirements-ci-runtime.txt",
        "scripts/ci/requirements-ci-pip-licenses.txt",
    ]


def test_the_conformity_cache_is_keyed_on_the_ruff_lock() -> None:
    job = _jobs("conformity.yml")["conformity-fixture-sweep"]
    (step,) = _setup_python_steps(job)
    assert _cache_paths(step) == ["scripts/ci/requirements-ci-ruff.txt"]


# --- pip-audit.yml audits every lock --------------------------------------------

_AUDIT_RE = re.compile(
    r"pip-audit -s osv --desc --disable-pip -r (scripts/ci/requirements-ci-[a-z-]+\.txt)"
)
LOCK_AUDIT_PATHS = [lock.relpath for lock in refresh_ci_locks.LOCKS] + [PIP_LOCK]


def _audit_job() -> dict[str, Any]:
    return _jobs("pip-audit.yml")["audit"]


def _commands(step: dict[str, Any]) -> list[str]:
    """Return the command lines of a `run` step, without comments and blank lines."""
    lines = (line.strip() for line in str(step.get("run", "")).splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def _audit_steps() -> list[dict[str, Any]]:
    return [
        step
        for step in _audit_job()["steps"]
        if str(step.get("id", "")).startswith("audit")
    ]


def _lock_audit_steps() -> list[dict[str, Any]]:
    return [
        step
        for step in _audit_job()["steps"]
        if str(step.get("id", "")).startswith("audit_ci_")
    ]


def _audit_id(relpath: str) -> str:
    stem = relpath.removeprefix("scripts/ci/requirements-ci-").removesuffix(".txt")
    return "audit_ci_" + stem.replace("-", "_")


def test_pip_audit_audits_every_lock_once_without_resolving() -> None:
    audited: dict[str, str] = {}
    for step in _lock_audit_steps():
        (command,) = _commands(step)  # a commented-out command does not count
        match = _AUDIT_RE.fullmatch(command)
        assert match, (
            f"`{step['name']}` must run exactly `pip-audit -s osv --desc "
            f"--disable-pip -r <lock>`, not {command!r}"
        )
        relpath = match.group(1)
        assert relpath not in audited, f"{relpath} is audited twice"
        audited[relpath] = str(step["id"])
    assert sorted(audited) == sorted(LOCK_AUDIT_PATHS)
    # The step id is what the last step tests, so it must name the lock it audits.
    for relpath, step_id in audited.items():
        assert step_id == _audit_id(relpath), (relpath, step_id)


def test_every_pip_audit_command_asks_osv_not_the_pypi_feed() -> None:
    # The PyPI feed lags the GitHub advisories that Dependabot alerts, Dependency
    # review and Scorecard read: virtualenv 21.14.12 (GHSA-cx6f-vjhg-g3cc) was in
    # OSV and not in the PyPI feed days after its publication.
    commands = [
        command
        for step in _jobs("pip-audit.yml")["audit"]["steps"]
        for command in _commands(step)
        if command.startswith("pip-audit")
    ]
    assert len(commands) == 3 + len(LOCK_AUDIT_PATHS)
    for command in commands:
        assert command.startswith("pip-audit -s osv "), command


def test_every_audit_step_continues_on_error_so_each_audit_reports() -> None:
    steps = _audit_steps()
    assert len(steps) == 3 + len(LOCK_AUDIT_PATHS)
    for step in steps:
        # Without it the first failing audit stops the job: the later audits do
        # not run and the step that surfaces the failure is skipped.
        assert step.get("continue-on-error") is True, step["id"]


def test_pip_audit_runs_on_one_python_that_every_lock_supports() -> None:
    job = _audit_job()
    # A matrix would need a lock that installs on its oldest cell. The pip-audit lock
    # is compiled for Python 3.11, so a 3.10 cell cannot install pip-audit from it.
    assert "strategy" not in job
    (step,) = _setup_python_steps(job)
    version = tuple(
        int(part) for part in str(step["with"]["python-version"]).split(".")
    )
    assert version == (3, 12)
    for lock in refresh_ci_locks.LOCKS:
        floor = tuple(int(part) for part in lock.python_floor.split("."))
        assert version >= floor, lock.filename


def test_no_audit_step_or_failure_condition_depends_on_the_python_version() -> None:
    job = _audit_job()
    for step in job["steps"]:
        assert "matrix" not in str(step.get("if", "")), step.get("name")
        assert "matrix" not in str(step.get("with", "")), step.get("name")
    for step in _audit_steps():
        assert "if" not in step, f"`{step['name']}` is conditional; every audit runs"


def test_pip_audit_surfaces_the_failure_of_every_audit_step() -> None:
    job = _audit_job()
    audit_ids = [step["id"] for step in _audit_steps()]
    (surface,) = [
        step
        for step in job["steps"]
        if step.get("name") == "Surface failure as workflow status"
    ]
    condition = " ".join(str(surface["if"]).split())
    for step_id in audit_ids:
        assert f"steps.{step_id}.outcome == 'failure'" in condition, step_id
    assert len(audit_ids) == len(set(audit_ids))
    assert condition.count("== 'failure'") == len(audit_ids)
    assert len(audit_ids) >= 8 + len(TOOL_LOCKS)


# --- Dependabot stays limited to pip --------------------------------------------


def test_dependabot_limits_the_ci_folder_to_the_one_pip_dependency() -> None:
    document = yaml.safe_load(
        (REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    )
    (entry,) = [
        item
        for item in document["updates"]
        if item["package-ecosystem"] == "pip" and item["directory"] == "/scripts/ci"
    ]
    assert entry["allow"] == [{"dependency-name": "pip"}]
    assert entry["cooldown"]["default-days"] == refresh_ci_locks.DEFAULT_COOLDOWN_DAYS
