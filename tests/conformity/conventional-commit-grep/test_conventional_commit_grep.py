# SPDX-License-Identifier: MIT

"""Behavioral pass+fail coverage for the conventional-commit matcher.

The matcher inspects the HEAD commit subject via ``check_repo(root)``.
The pure classifier ``_classify_drift(subject)`` is driven directly with
synthetic subject strings for deterministic pass+fail, and ``check_repo``
is exercised against a tmp git repository so the git-read path is covered
end to end. A final test confirms the git-read bounds its subprocess with
``GIT_TIMEOUT_SECONDS`` and degrades to an informational pass on timeout.
"""

from __future__ import annotations

import importlib.util
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


def test_no_git_repo_is_informational_pass(tmp_path: Path) -> None:
    # No .git/ directory: never block a fresh clone or non-git tree.
    result = _MOD.check_repo(tmp_path)
    assert result.passed
    assert result.status == "not-a-git-repo"


def test_git_timeout_degrades_to_pass(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()

    def _raise_timeout(*args: object, **kwargs: object) -> NoReturn:
        assert kwargs.get("timeout") == _MOD.GIT_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(cmd="git", timeout=_MOD.GIT_TIMEOUT_SECONDS)

    monkeypatch.setattr(_MOD.subprocess, "run", _raise_timeout)
    result = _MOD.check_repo(tmp_path)
    assert result.passed
    assert result.status == "git-unavailable"


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True
