# SPDX-License-Identifier: MIT

"""Behavioral pass+fail coverage for the conventional-commit matcher.

The matcher inspects the HEAD commit subject via ``check_repo(root)``.
The pure classifier ``_classify_drift(subject)`` is driven directly with
synthetic subject strings for deterministic pass+fail, and ``check_repo``
is exercised against a tmp git repository so the git-read path is covered
end to end. A final test confirms the git-read bounds its subprocess with
``GIT_TIMEOUT_SECONDS`` and that a timeout does not pass: the HEAD subject
was never read, so the status is ``git-timeout`` with a ``check_error``.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Final, NoReturn

import pytest

from tests._shared.git_env import hermetic_git_env

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "conventional_commit_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "conventional_commit_grep", _GREP_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["conventional_commit_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def test_conformant_subject_passes() -> None:
    drifts = _MOD._classify_drift("feat(harness): wire the codex adapter cohort")
    assert drifts == []


def test_conformant_subject_without_scope_passes() -> None:
    drifts = _MOD._classify_drift("docs: add the naming-conventions reference page")
    assert drifts == []


def test_missing_type_fails() -> None:
    drifts = _MOD._classify_drift("just a plain sentence without a type prefix")
    assert drifts
    assert any(d.klass == "missing-type" for d in drifts)


def test_invalid_type_fails() -> None:
    drifts = _MOD._classify_drift("frobnicate(scope): do a thing")
    assert any(d.klass == "invalid-type" for d in drifts)


def test_subject_over_72_chars_fails() -> None:
    long_subject = "feat: " + ("x" * 80)
    assert len(long_subject) > _MOD.MAX_SUBJECT_LEN
    drifts = _MOD._classify_drift(long_subject)
    assert any(d.klass == "subject-too-long" for d in drifts)


@pytest.mark.parametrize(
    "subject",
    [
        "feat: embed the schema into the manifest",
        "fix: shed the dead code paths",
        "feat: bring the adapter online",
        "chore: ping the registry health endpoint",
        "docs: feed the pipeline a fixture",
        "feat: ring the retry buffer",
        "fix: string the tokens together",
    ],
)
def test_imperative_allow_list_not_flagged(subject: str) -> None:
    # Imperative verbs that merely end in -ed/-ing letters must pass.
    drifts = _MOD._classify_drift(subject)
    assert not any(d.klass == "non-imperative-verb" for d in drifts), subject


@pytest.mark.parametrize(
    "subject",
    [
        "feat: added the adapter cohort",
        "fix: removing the memory leak",
        "chore: adds a helper function",
        "docs: updated the reference page",
        "refactor: implementing the new flow",
    ],
)
def test_genuine_non_imperative_still_flagged(subject: str) -> None:
    drifts = _MOD._classify_drift(subject)
    assert any(d.klass == "non-imperative-verb" for d in drifts), subject


def _init_git_repo(root: Path, subject: str) -> None:
    # Host git config stays out: a signing setting or a global commit-msg
    # hook would break the commit, the drifting subjects most of all.
    def _git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=str(root),
            env=hermetic_git_env(),
            check=True,
            capture_output=True,
            text=True,
        )

    _git("init")
    _git("config", "user.email", "me@ahmedgad.com")
    _git("config", "user.name", "Ahmed G. Gad")
    (root / "file.txt").write_text("body\n", encoding="utf-8")
    _git("add", "file.txt")
    _git("commit", "-m", subject)


def test_check_repo_passes_on_conformant_head(tmp_path: Path) -> None:
    if not _git_available():
        pytest.skip("git not available")
    _init_git_repo(tmp_path, "fix(cli): handle the missing-profile path")
    result = _MOD.check_repo(tmp_path)
    assert result.passed, result.to_json()
    assert result.status == "ok"


def test_check_repo_fails_on_drifting_head(tmp_path: Path) -> None:
    if not _git_available():
        pytest.skip("git not available")
    _init_git_repo(tmp_path, "Added a feature without a conventional prefix")
    result = _MOD.check_repo(tmp_path)
    assert not result.passed
    assert result.drifts


def _hermetic_check_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # git in the check reads os.environ: give it the shared hermetic
    # environment, so the host's git configuration cannot change the result.
    env = hermetic_git_env()
    for name in list(os.environ):
        if name not in env:
            monkeypatch.delenv(name)
    for name, value in env.items():
        monkeypatch.setenv(name, value)


def _git_in(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(root),
        env=hermetic_git_env(),
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("commit", [True, False], ids=["committed", "staged"])
def test_subfolder_of_a_checkout_reads_the_checkout_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, commit: bool
) -> None:
    # git finds the repository above a subfolder that holds a tracked file,
    # so the check does too: a drifting HEAD is reported, not taken for a
    # folder outside a checkout. A file only in the index counts as tracked.
    if not _git_available():
        pytest.skip("git not available")
    _init_git_repo(tmp_path, "Added a feature without a conventional prefix")
    sub = tmp_path / "pkg" / "inner"
    sub.mkdir(parents=True)
    (sub / "mod.txt").write_text("body\n", encoding="utf-8")
    _git_in(tmp_path, "add", "pkg/inner/mod.txt")
    if commit:
        _git_in(tmp_path, "commit", "-m", "Added the inner module")
    _hermetic_check_env(monkeypatch)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    result = _MOD.check_repo(sub)
    assert result.status == "ok", result.to_json()
    assert not result.passed
    assert result.drifts


@pytest.mark.parametrize("spelling", ["pkg", "Pkg"], ids=["disk case", "index case"])
def test_subfolder_renamed_only_in_case_reads_the_checkout_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spelling: str
) -> None:
    # A tracked folder renamed on disk only in case: git ignores case here,
    # so git status shows no change and the folder's files stay tracked. The
    # check reads HEAD, as for any tracked subfolder, whichever case names
    # the folder.
    if not _git_available():
        pytest.skip("git not available")
    probe = tmp_path / "CaseProbe"
    probe.mkdir()
    if not (tmp_path / "caseprobe").exists():
        pytest.skip("the file system tells names apart by case")
    probe.rmdir()
    _init_git_repo(tmp_path, "Added a feature without a conventional prefix")
    sub = tmp_path / "Pkg" / "inner"
    sub.mkdir(parents=True)
    (sub / "mod.txt").write_text("body\n", encoding="utf-8")
    _git_in(tmp_path, "add", "Pkg/inner/mod.txt")
    _git_in(tmp_path, "commit", "-m", "Added the inner module")
    # Two renames, as a case-only rename in one step may be refused.
    (tmp_path / "Pkg").rename(tmp_path / "pkg-moving")
    (tmp_path / "pkg-moving").rename(tmp_path / "pkg")
    _hermetic_check_env(monkeypatch)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    result = _MOD.check_repo(tmp_path / spelling / "inner")
    assert result.status == "ok", result.to_json()
    assert not result.passed
    assert result.drifts


@pytest.mark.parametrize(
    ("ignored", "empty_git"),
    [(False, False), (True, False), (False, True)],
    ids=["untracked", "ignored", "empty .git in the project"],
)
def test_folder_an_enclosing_repository_does_not_track_is_exempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ignored: bool, empty_git: bool
) -> None:
    # A new project inside a home-folder dotfiles repository: the enclosing
    # repository tracks nothing in the project, so its drifting HEAD is not
    # the project's history and the check stays exempt. An empty .git folder
    # in the project (a git init that stopped) is one git looks past, so it
    # changes nothing.
    if not _git_available():
        pytest.skip("git not available")
    home = tmp_path / "home"
    home.mkdir()
    _init_git_repo(home, "update bashrc")
    if ignored:
        (home / ".gitignore").write_text("projects/\n", encoding="utf-8")
    project = home / "projects" / "foo"
    project.mkdir(parents=True)
    (project / "main.py").write_text("print()\n", encoding="utf-8")
    if empty_git:
        (project / ".git").mkdir()
    _hermetic_check_env(monkeypatch)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    result = _MOD.check_repo(project)
    assert result.passed, result.to_json()
    assert result.status == "not-a-git-repo"
    assert result.check_error is None


def test_repository_top_reads_head_without_a_tracked_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # At the repository's own top the history is the folder's, so the check
    # reads HEAD even when the index is empty.
    if not _git_available():
        pytest.skip("git not available")
    _init_git_repo(tmp_path, "Added a feature without a conventional prefix")
    _git_in(tmp_path, "rm", "--cached", "-q", "file.txt")
    _hermetic_check_env(monkeypatch)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    result = _MOD.check_repo(tmp_path)
    assert result.status == "ok", result.to_json()
    assert not result.passed


def test_empty_git_folder_above_fails_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An empty .git folder above is a .git entry git cannot open. It counts
    # as a checkout, git finds no repository and refuses the folder, so the
    # check fails rather than passing as a folder outside any checkout.
    if not _git_available():
        pytest.skip("git not available")
    (tmp_path / ".git").mkdir()
    sub = tmp_path / "proj"
    sub.mkdir()
    _hermetic_check_env(monkeypatch)
    # git's search stops at tmp_path, so a repository above it cannot count.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    result = _MOD.check_repo(sub)
    assert not result.passed, result.to_json()
    assert result.status == "git-failed"
    assert result.check_error is not None


def test_no_git_repo_is_informational_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No .git/ directory: never block a fresh clone or non-git tree. The
    # search does not go above tmp_path, so a repository above the temp
    # folder cannot count.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    result = _MOD.check_repo(tmp_path)
    assert result.passed
    assert result.status == "not-a-git-repo"


def test_git_timeout_does_not_pass(tmp_path: Path, monkeypatch) -> None:
    from apothem.conformity import _bounded_run

    (tmp_path / ".git").mkdir()

    def _raise_timeout(*args: object, **kwargs: object) -> NoReturn:
        assert kwargs.get("timeout") == _MOD.GIT_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(cmd="git", timeout=_MOD.GIT_TIMEOUT_SECONDS)

    monkeypatch.setattr(_bounded_run, "run_bounded", _raise_timeout)
    result = _MOD.check_repo(tmp_path)
    assert not result.passed
    assert result.status == "git-timeout"
    assert result.check_error == (
        f"git log did not finish within {_MOD.GIT_TIMEOUT_SECONDS} seconds"
    )


def test_git_that_cannot_start_stays_exempt(tmp_path: Path, monkeypatch) -> None:
    # git missing from the host is unchanged: the history cannot be read
    # at all, so the check stays informational, as before.
    from apothem.conformity import _bounded_run

    (tmp_path / ".git").mkdir()

    def _raise_missing(*args: object, **kwargs: object) -> NoReturn:
        raise FileNotFoundError("git")

    monkeypatch.setattr(_bounded_run, "run_bounded", _raise_missing)
    result = _MOD.check_repo(tmp_path)
    assert result.passed
    assert result.status == "git-unavailable"
    assert result.check_error is None


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True
