# SPDX-License-Identifier: MIT

"""The CI tool lockfiles live where Dependabot can update them, and stay wired.

The vsce packager and the channel-smoke harness CLIs are npm lockfiles under
``tools/``. They moved out of ``.github/`` because Dependabot never opened a
pull request for them there. This module keeps the move from regressing and
keeps the consumers of the directory list in step: ``.github/dependabot.yml``,
the ``npm-audit.yml`` matrix, its ``paths:`` filters, and the ``npm ci --prefix``
installs in the workflows.

A pull request that changes only ``tools/`` runs no ``ci.yml`` job, so the
checks that make such a pull request test itself are pinned here too:
``npm-audit.yml`` runs the vsce release tests and this module, and packages the
extension for ``tools/vsce``; ``channel-smoke.yml`` runs on a pull request that
changes ``tools/channel-smoke``.
"""

from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml

_REPO = Path(__file__).resolve().parents[2]
_DEPENDABOT = _REPO / ".github" / "dependabot.yml"
_WORKFLOWS = _REPO / ".github" / "workflows"
_NPM_AUDIT = _WORKFLOWS / "npm-audit.yml"
_CHANNEL_SMOKE = _WORKFLOWS / "channel-smoke.yml"

_ACTIONS = "github-actions"
_GLOB_CHARS = frozenset("*?[")
# `npm ci` with the prefix after it (`npm ci --prefix X`) or before it
# (`npm --prefix X ci`).
_NPM_CI = re.compile(r"\bnpm\s+(?:--prefix[=\s]+\S+\s+)?ci\b")
_PREFIX = re.compile(r"--prefix(?:=|\s+)(\S+)")


@lru_cache(maxsize=1)
def _tracked() -> frozenset[str]:
    """Return every tracked path, repo-relative with forward slashes."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is required to list tracked files")
    result = subprocess.run(
        [git, "-C", str(_REPO), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        pytest.skip("not a git checkout, so there are no tracked files to list")
    names = result.stdout.decode("utf-8").split("\0")
    return frozenset(name for name in names if name)


def _tracked_dirs() -> frozenset[str]:
    dirs: set[str] = set()
    for name in _tracked():
        dirs.update(str(parent) for parent in PurePosixPath(name).parents)
    dirs.discard(".")
    return frozenset(dirs)


def _files_in(directory: str) -> list[str]:
    """Return the tracked file names directly inside *directory* ("" = root)."""
    names: list[str] = []
    for path in _tracked():
        parent, _, name = path.rpartition("/")
        if parent == directory:
            names.append(name)
    return sorted(names)


def _normalize(directory: str) -> str:
    """Return *directory* repo-relative: no leading ``/`` or ``./``, "" = root."""
    value = directory.strip()
    while value.startswith("./"):
        value = value[2:]
    return value.strip("/")


def _entries() -> list[dict[str, Any]]:
    data = yaml.safe_load(_DEPENDABOT.read_text(encoding="utf-8"))
    updates = data["updates"]
    assert isinstance(updates, list), "dependabot.yml `updates` must be a list"
    assert updates, ".github/dependabot.yml has no `updates` entries; restore them"
    return [entry for entry in updates if isinstance(entry, dict)]


def _entry_directories(entry: dict[str, Any]) -> list[str]:
    """Return an entry's directories, from `directory` and from `directories`."""
    found: list[str] = []
    if "directory" in entry:
        found.append(str(entry["directory"]))
    found.extend(str(item) for item in entry.get("directories") or [])
    return found


def _expand(directory: str) -> list[str]:
    """Return the tracked directories a Dependabot directory names.

    A literal directory names itself; a glob (Dependabot allows ``*``)
    names every tracked directory that matches.
    """
    wanted = _normalize(directory)
    if not _GLOB_CHARS.intersection(wanted):
        return [wanted]
    return sorted(d for d in _tracked_dirs() if fnmatch.fnmatchcase(d, wanted))


def _targets() -> Iterator[tuple[str, str]]:
    """Yield (package-ecosystem, directory as written) for every target."""
    for entry in _entries():
        ecosystem = str(entry.get("package-ecosystem"))
        for directory in _entry_directories(entry):
            yield ecosystem, directory


def _under_dot_github(directory: str) -> bool:
    wanted = _normalize(directory)
    return wanted == ".github" or wanted.startswith(".github/")


def test_dependabot_declares_a_directory_for_every_entry() -> None:
    missing = [
        str(entry.get("package-ecosystem"))
        for entry in _entries()
        if not _entry_directories(entry)
    ]
    assert not missing, (
        f"Dependabot entries for {missing} name no `directory` or `directories` "
        "in .github/dependabot.yml; add one to each"
    )


def test_no_non_actions_dependabot_entry_targets_dot_github() -> None:
    """Dependabot cannot open pull requests for manifests under ``.github/``.

    Only the ``github-actions`` ecosystem holds the ``workflows`` token scope
    that a change under ``.github/`` needs, so a version or security update
    for any other ecosystem there fails at pull request creation with
    ``dependency_file_not_supported``
    (https://github.com/dependabot/dependabot-core/issues/15237). The vsce and
    channel-smoke lockfiles sat under ``.github/`` for that reason and never
    received one update.

    Retire this check once dependabot-core#15237 is fixed and Dependabot opens
    such pull requests.
    """
    offenders = [
        f"{ecosystem}: {directory}"
        for ecosystem, directory in _targets()
        if ecosystem != _ACTIONS and _under_dot_github(directory)
    ]
    assert not offenders, (
        f"Dependabot entries target a directory under /.github: {offenders}. "
        "Dependabot cannot open pull requests there "
        "(dependabot-core#15237). Move the manifest and lockfile out of "
        ".github/ (for example into tools/) and point `directory` at the new path."
    )


def _manifest_problem(ecosystem: str, directory: str, files: list[str]) -> str | None:
    """Return what is missing from *directory* for *ecosystem*, or None."""
    names = set(files)
    if ecosystem == "npm":
        absent = sorted({"package.json", "package-lock.json"} - names)
        return f"missing tracked {', '.join(absent)}" if absent else None
    if ecosystem == "pip":
        found = any(
            fnmatch.fnmatchcase(n, "requirements*.txt") or n == "pyproject.toml"
            for n in names
        )
        return (
            None if found else "missing a tracked requirements*.txt or pyproject.toml"
        )
    if ecosystem == "pre-commit":
        found = ".pre-commit-config.yaml" in names
        return None if found else "missing a tracked .pre-commit-config.yaml"
    if ecosystem == _ACTIONS:
        if directory == "":
            workflows = _files_in(".github/workflows")
            found = any(n.endswith((".yml", ".yaml")) for n in workflows)
            return None if found else "missing tracked .github/workflows/*.yml"
        found = any(n.endswith((".yml", ".yaml")) for n in names)
        return None if found else "missing a tracked workflow or action *.yml"
    return None if names else "holds no tracked files"


def test_every_dependabot_directory_holds_its_manifest() -> None:
    problems: list[str] = []
    for ecosystem, written in _targets():
        directories = _expand(written)
        if not directories:
            problems.append(
                f"{ecosystem} {written}: the glob matches no tracked directory"
            )
            continue
        for directory in directories:
            problem = _manifest_problem(ecosystem, directory, _files_in(directory))
            if problem is not None:
                problems.append(f"{ecosystem} /{directory}: {problem}")
    assert not problems, (
        "Dependabot entries in .github/dependabot.yml point at directories "
        f"without their manifest as tracked content: {problems}. Fix the "
        "`directory` value, or restore (and `git add`) the manifest."
    )


def _matrix_dirs(workflow: Path) -> set[str]:
    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    found: set[str] = set()
    for job in (data.get("jobs") or {}).values():
        matrix = ((job or {}).get("strategy") or {}).get("matrix") or {}
        found.update(_normalize(str(item)) for item in matrix.get("dir") or [])
    return found


def test_npm_audit_matrix_covers_the_dependabot_npm_directories() -> None:
    dependabot = {
        _normalize(directory)
        for ecosystem, directory in _targets()
        if ecosystem == "npm"
    }
    expected = dependabot - {"site"}
    audited = _matrix_dirs(_NPM_AUDIT)
    assert audited == expected, (
        f"the npm-audit.yml matrix `dir` audits {sorted(audited)}, but "
        f"Dependabot keeps {sorted(expected)} current (every npm directory "
        "except /site, which has its own steps). Make the matrix `dir` list in "
        ".github/workflows/npm-audit.yml match the npm directories in "
        ".github/dependabot.yml; the two `paths:` filters are checked by "
        "test_npm_audit_paths_cover_the_dependabot_npm_directories."
    )


def _on_block(workflow: Path) -> dict[str, Any]:
    """Return a workflow's ``on:`` mapping.

    PyYAML loads the bare key ``on`` as the boolean ``True``.
    """
    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    block = data.get("on", data.get(True))
    assert isinstance(block, dict), (
        f"{workflow.name} has no `on:` mapping of triggers; restore it"
    )
    return block


def _trigger_paths(workflow: Path, trigger: str) -> list[str]:
    config = _on_block(workflow).get(trigger)
    assert isinstance(config, dict), (
        f"{workflow.name} declares no `{trigger}:` trigger with a `paths:` "
        f"filter; add `on.{trigger}.paths` to .github/workflows/{workflow.name}"
    )
    return [str(item) for item in config.get("paths") or []]


def test_npm_audit_paths_cover_the_dependabot_npm_directories() -> None:
    expected = {
        _normalize(directory)
        for ecosystem, directory in _targets()
        if ecosystem == "npm"
    } - {"site"}
    problems = [
        f"`on.{trigger}.paths` lacks {directory}/**"
        for trigger in ("push", "pull_request")
        for directory in sorted(expected)
        if f"{directory}/**" not in _trigger_paths(_NPM_AUDIT, trigger)
    ]
    assert not problems, (
        f"npm-audit.yml does not run for a change to a tool lockfile: {problems}. "
        "Add the missing `<dir>/**` entry to that `paths:` filter in "
        ".github/workflows/npm-audit.yml, so a Dependabot lockfile pull request "
        "is audited and tested."
    )


def _join_continuations(lines: list[str]) -> Iterator[str]:
    """Join each line that ends in a backslash with the line after it."""
    pending = ""
    for line in lines:
        if line.rstrip().endswith("\\"):
            pending += line.rstrip()[:-1].strip() + " "
            continue
        yield pending + line.strip() if pending else line
        pending = ""
    if pending:
        yield pending.rstrip()


def _run_lines(workflow: Path) -> Iterator[str]:
    """Yield each shell line of every ``run:`` step, continuations joined."""
    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    for job in (data.get("jobs") or {}).values():
        for step in (job or {}).get("steps") or []:
            run = step.get("run") if isinstance(step, dict) else None
            if isinstance(run, str):
                yield from _join_continuations(run.splitlines())


def _resolve_prefix(prefix: str) -> str:
    """Return the repo-relative directory a workflow's ``--prefix`` names.

    publish-vscode.yml runs inside ``vscode-extension`` and checks the
    lockfile out beside it at ``../vsce-tool``; release.yml names the
    directory from the repository root.
    """
    value = prefix.strip("\"'")
    if value.startswith("../vsce-tool/"):
        value = value[len("../vsce-tool/") :]
    while value.startswith("../"):
        value = value[3:]
    return _normalize(value)


def test_every_workflow_npm_ci_prefix_names_a_tracked_lockfile() -> None:
    installs: list[tuple[str, str]] = []
    for workflow in sorted(_WORKFLOWS.glob("*.yml")):
        for line in _run_lines(workflow):
            if not _NPM_CI.search(line):
                continue
            match = _PREFIX.search(line)
            if match:
                installs.append((workflow.name, match.group(1)))
    assert installs, (
        "found no `npm ci --prefix` install in .github/workflows/*.yml; this "
        "check expects the vsce and channel-smoke installs, so update the "
        "pattern in tests/scripts/test_tool_lockfile_locations.py if the "
        "install command changed shape"
    )
    tracked = _tracked()
    broken = [
        f"{name}: --prefix {prefix} (resolves to {_resolve_prefix(prefix)}/)"
        for name, prefix in installs
        if f"{_resolve_prefix(prefix)}/package-lock.json" not in tracked
    ]
    assert not broken, (
        f"workflow installs run `npm ci --prefix` on a directory with no tracked "
        f"package-lock.json: {broken}. Point `--prefix` at the directory that "
        "holds the lockfile (tools/vsce or tools/channel-smoke)."
    )


def _jobs(workflow: Path) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    return {name: job for name, job in data["jobs"].items() if isinstance(job, dict)}


def _job_run_lines(job: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for step in job.get("steps") or []:
        run = step.get("run") if isinstance(step, dict) else None
        if isinstance(run, str):
            lines.extend(_join_continuations(run.splitlines()))
    return lines


_TOOL_TESTS = (
    "tests/scripts/test_tool_lockfile_locations.py",
    "tests/scripts/test_release_vsix.py",
)


def test_npm_audit_runs_the_tool_lockfile_tests_and_packages_the_extension() -> None:
    jobs = _jobs(_NPM_AUDIT)
    test_jobs = [
        name
        for name, job in jobs.items()
        if any(
            "pytest" in line and all(path in line for path in _TOOL_TESTS)
            for line in _job_run_lines(job)
        )
    ]
    assert test_jobs, (
        "no job in npm-audit.yml runs pytest on both "
        f"{' and '.join(_TOOL_TESTS)}, so a Dependabot vsce pull request is "
        "never tested. Restore the `tool-lockfile-tests` job with a run step "
        "that runs `python -m pytest` on both files."
    )
    node_setups = [
        job
        for name, job in jobs.items()
        if name in test_jobs
        and any(
            isinstance(step, dict)
            and str(step.get("uses", "")).startswith("actions/setup-node@")
            for step in job.get("steps") or []
        )
    ]
    assert node_setups, (
        "the npm-audit.yml job that runs the tool lockfile tests has no "
        "`actions/setup-node` step, so the Trusted Publishing guard test runs "
        "on the runner's preinstalled Node instead of the Node the vsce jobs "
        'use. Restore the `Set up Node` step with `node-version: "24"`.'
    )
    lockfiles_job = jobs.get("tool-lockfiles")
    assert lockfiles_job is not None, (
        "npm-audit.yml has no `tool-lockfiles` job. Restore the matrix job "
        "that audits and installs each tool lockfile and packages the "
        "extension for tools/vsce."
    )
    packaging = [
        step
        for step in lockfiles_job.get("steps") or []
        if isinstance(step, dict) and "vsce package" in str(step.get("run", ""))
    ]
    assert packaging, (
        "the `tool-lockfiles` job in npm-audit.yml has no step that runs "
        "`vsce package`. Add the extension package step from release.yml's "
        "vsix job, guarded with `if: matrix.dir == 'tools/vsce'`."
    )
    assert all("tools/vsce" in str(step.get("if", "")) for step in packaging), (
        "the `vsce package` step in npm-audit.yml must run only for the vsce "
        "directory: guard it with `if: matrix.dir == 'tools/vsce'`, because "
        "the other matrix directory installs no vsce."
    )


def test_channel_smoke_runs_on_a_channel_smoke_lockfile_pull_request() -> None:
    directories = [
        _normalize(directory)
        for ecosystem, directory in _targets()
        if ecosystem == "npm" and _normalize(directory).endswith("channel-smoke")
    ]
    assert directories == ["tools/channel-smoke"], (
        f"expected one Dependabot npm entry for tools/channel-smoke, found "
        f"{directories}; point the entry in .github/dependabot.yml at it"
    )
    paths = _trigger_paths(_CHANNEL_SMOKE, "pull_request")
    assert f"{directories[0]}/**" in paths, (
        f"channel-smoke.yml `on.pull_request.paths` is {paths} and lacks "
        f"{directories[0]}/**, so a Dependabot update to the harness CLIs "
        "merges without the channel smoke. Add that path to the "
        "`pull_request` trigger in .github/workflows/channel-smoke.yml."
    )
