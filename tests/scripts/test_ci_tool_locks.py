# SPDX-License-Identifier: MIT

"""The CI tool locks are wired into the workflows, and ruff and mypy have one version.

Five CI tools install from their own hash-locked files in ``scripts/ci/``
(``requirements-ci-ruff.txt``, ``-bandit.txt``, ``-pip-audit.txt``,
``-pip-licenses.txt``, ``-pre-commit.txt``), compiled by
``scripts/dev/refresh_ci_locks.py`` from the specs in
``scripts/dev/ci_lock_table.py``. This module keeps four things from drifting:

* ruff is pinned exactly in five places that must agree: the dev extra of
  ``pyproject.toml``, the ``ruff-pre-commit`` rev in ``.pre-commit-config.yaml``,
  the spec in the table, the ruff lock and the dev lock. A Dependabot security
  pull request edits only ``pyproject.toml``, and fails here until the rest follow.
* mypy is pinned exactly in the dev extra and in the ``mirrors-mypy`` rev, and
  both equal the mypy of the dev lock. The mypy hook runs with CI's flags and
  lists each runtime dependency and dev ``types-*`` stub at the dev lock's
  version, once per lock line. A lock refresh that moves one of them fails here
  until the hook follows.
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

import fnmatch
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


# --- where ruff and mypy are pinned ---------------------------------------------

RUFF_HOOK = "/astral-sh/ruff-pre-commit"
MYPY_HOOK = "/pre-commit/mirrors-mypy"
DEV_LOCK = "requirements-ci-dev.txt"
# A requirement line of a lock: `name==version`, then ` ;` and a marker or ` \`.
_LOCK_PIN_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[^\s;\\]+)", re.MULTILINE
)


def _dev_extra_pin(name: str) -> str:
    """Return the version that the dev extra of pyproject.toml pins with ==."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = data["project"]["optional-dependencies"]["dev"]
    requirements = [Requirement(text) for text in dev]
    named = [r for r in requirements if canonicalize_name(r.name) == name]
    assert len(named) == 1, f"the dev extra must name {name} exactly once"
    operators = [item.operator for item in named[0].specifier]
    assert operators == ["=="], f"the dev extra must pin {name} with ==, not {named[0]}"
    return next(iter(named[0].specifier)).version


def _hook_repo(suffix: str) -> dict[str, Any]:
    config = yaml.safe_load(
        (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    repos = [repo for repo in config["repos"] if str(repo["repo"]).endswith(suffix)]
    assert len(repos) == 1, f"expected one {suffix.lstrip('/')} repo"
    return repos[0]


def _hook_rev(suffix: str) -> str:
    rev = str(_hook_repo(suffix)["rev"])
    assert rev.startswith("v"), rev
    return rev[1:]


def _mypy_hook_pins(entries: list[str] | None = None) -> dict[str, list[str]]:
    """Map each mypy hook dependency to its versions, one per marked entry."""
    if entries is None:
        (hook,) = [h for h in _hook_repo(MYPY_HOOK)["hooks"] if h["id"] == "mypy"]
        entries = hook.get("additional_dependencies", [])
    found: dict[str, list[Requirement]] = {}
    for text in entries:
        requirement = Requirement(str(text))
        operators = [item.operator for item in requirement.specifier]
        assert operators == ["=="], f"the mypy hook must pin {text} with =="
        found.setdefault(canonicalize_name(requirement.name), []).append(requirement)
    for name, listed in found.items():
        assert len(listed) == 1 or all(r.marker for r in listed), (
            f"the mypy hook lists {name} twice without a marker on each entry"
        )
    return {
        name: sorted(next(iter(r.specifier)).version for r in listed)
        for name, listed in found.items()
    }


def _locked_versions(filename: str) -> dict[str, list[str]]:
    """Map each package a lock pins, by canonical name, to its pinned versions.

    A package that the lock splits by environment marker has one version per line.
    """
    text = (CI_DIR / filename).read_bytes().decode("utf-8")
    versions: dict[str, list[str]] = {}
    for match in _LOCK_PIN_RE.finditer(text):
        versions.setdefault(canonicalize_name(match["name"]), []).append(
            match["version"]
        )
    return versions


def _locked_version(filename: str, name: str) -> str:
    found = _locked_versions(filename).get(name, [])
    assert len(found) == 1, f"{filename} must pin {name} once, found {found}"
    return found[0]


def test_the_dev_extra_pins_ruff_and_mypy_exactly_and_no_floor_is_left() -> None:
    for name in ("ruff", "mypy"):
        assert re.fullmatch(r"\d+\.\d+\.\d+", _dev_extra_pin(name)), name


def test_dependabot_leaves_the_ruff_and_mypy_hooks_to_the_lockstep() -> None:
    document = yaml.safe_load(
        (REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    )
    hooks = [e for e in document["updates"] if e["package-ecosystem"] == "pre-commit"]
    assert len(hooks) == 1
    ignored = [str(item["dependency-name"]).lower() for item in hooks[0]["ignore"]]
    assert "*ruff-pre-commit" in ignored
    assert "*mirrors-mypy" in ignored
    # A mypy hook dependency that Dependabot bumped alone would leave the dev lock.
    for name in _mypy_hook_pins():
        assert any(fnmatch.fnmatchcase(name, pattern) for pattern in ignored), (
            f"dependabot.yml must ignore {name}, a mypy hook dependency"
        )


# --- ruff has one version -------------------------------------------------------


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
            "pyproject.toml dev extra": _dev_extra_pin("ruff"),
            ".pre-commit-config.yaml ruff-pre-commit rev": _hook_rev(RUFF_HOOK),
            "scripts/dev/ci_lock_table.py ruff spec": _table_version(),
            "scripts/ci/requirements-ci-ruff.txt": _locked_version(
                "requirements-ci-ruff.txt", "ruff"
            ),
            "scripts/ci/requirements-ci-dev.txt": _locked_version(DEV_LOCK, "ruff"),
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


# --- mypy and its hook dependencies match the dev lock --------------------------

MYPY_FIX = (
    "The dev lock is the reference. To move mypy, change the exact pin in "
    "pyproject.toml (dev extra) and the mirrors-mypy rev in .pre-commit-config.yaml "
    f"(vX.Y.Z) together, then run `python {REFRESH}`. After any refresh, set each "
    "additional_dependencies entry of the mypy hook to the version that "
    "scripts/ci/requirements-ci-dev.txt pins; where the lock pins a library once "
    "per Python version, list it once per lock line, with that line's marker."
)


def assert_matches_the_dev_lock(
    pins: list[tuple[str, str, list[str]]], locked: dict[str, list[str]]
) -> None:
    """Fail naming each (place, package, versions) that differs from the dev lock."""
    wrong = [
        f"  - {place}: {name} {' and '.join(versions)}, the dev lock has "
        f"{' and '.join(locked.get(name, [])) or 'no pin'}"
        for place, name, versions in pins
        if sorted(versions) != sorted(locked.get(name, []))
    ]
    if wrong:
        raise AssertionError(
            "mypy and the libraries its pre-commit hook lists must carry the "
            "versions in scripts/ci/requirements-ci-dev.txt:\n"
            + "\n".join(wrong)
            + f"\n{MYPY_FIX}"
        )


def test_mypy_and_the_mypy_hook_dependencies_carry_the_dev_lock_versions() -> None:
    hook_pins = _mypy_hook_pins()
    assert hook_pins, "the mypy hook lists no additional_dependencies"
    hook = ".pre-commit-config.yaml mypy additional_dependencies"
    rev = ".pre-commit-config.yaml mirrors-mypy rev"
    assert_matches_the_dev_lock(
        [
            ("pyproject.toml dev extra", "mypy", [_dev_extra_pin("mypy")]),
            (rev, "mypy", [_hook_rev(MYPY_HOOK)]),
            *((hook, name, versions) for name, versions in hook_pins.items()),
        ],
        _locked_versions(DEV_LOCK),
    )


def test_the_mypy_hook_has_ci_flags_and_every_runtime_dependency_and_stub() -> None:
    # With CI's flags the hook fails on a library it lacks; name it here first.
    (hook,) = [h for h in _hook_repo(MYPY_HOOK)["hooks"] if h["id"] == "mypy"]
    assert hook.get("args") == [], "the mypy hook must keep `args: []`"
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = tomllib.loads(text)["project"]
    runtime = [Requirement(t).name for t in project["dependencies"]]
    dev = [Requirement(t).name for t in project["optional-dependencies"]["dev"]]
    names = runtime + [name for name in dev if name.lower().startswith("types-")]
    missing = sorted({canonicalize_name(n) for n in names} - set(_mypy_hook_pins()))
    assert not missing, f"the mypy hook's additional_dependencies lack {missing}"


def test_a_mypy_pin_that_differs_from_the_dev_lock_is_reported() -> None:
    locked = {"mypy": ["2.4.0"], "rich": ["15.0.0"], "tomli": ["2.5.0", "2.4.0"]}
    with pytest.raises(AssertionError) as raised:
        assert_matches_the_dev_lock(
            [
                ("pyproject.toml dev extra", "mypy", ["2.4.0"]),
                (".pre-commit-config.yaml mirrors-mypy rev", "mypy", ["2.3.0"]),
                ("hook", "rich", ["15.0.0"]),
                ("hook", "attrs", ["26.1.0"]),
                ("hook", "tomli", ["2.5.0"]),
            ],
            locked,
        )
    message = str(raised.value)
    assert "mirrors-mypy rev: mypy 2.3.0, the dev lock has 2.4.0" in message
    assert "hook: attrs 26.1.0, the dev lock has no pin" in message
    assert "hook: tomli 2.5.0, the dev lock has 2.5.0 and 2.4.0" in message
    assert "dev extra: mypy" not in message
    assert "rich" not in message
    assert REFRESH in message
    assert_matches_the_dev_lock([("a", "mypy", ["2.4.0"])], locked)
    assert_matches_the_dev_lock([("hook", "tomli", ["2.4.0", "2.5.0"])], locked)


def test_a_mypy_hook_library_repeats_only_with_a_marker_on_each_entry() -> None:
    old, new = "rpds-py==0.30.0", "rpds-py==2026.9.1"
    split = [f"{old} ; python_version < '3.11'", f"{new} ; python_version >= '3.11'"]
    assert _mypy_hook_pins(split) == {"rpds-py": ["0.30.0", "2026.9.1"]}
    with pytest.raises(AssertionError, match="lists rpds-py twice without a marker"):
        _mypy_hook_pins([old, split[1]])


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
