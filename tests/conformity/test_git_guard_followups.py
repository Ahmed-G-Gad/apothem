# SPDX-License-Identifier: MIT

"""Follow-ups to the rule that a link never hides a file or a tree.

Why these tests exist. The conformity validators refuse to run git through a
``.git`` entry that is a link, and they note every link they leave out under
``skipped_links``. These tests pin the places that rule reached late:

- the two ``--staged`` checks run git in the current folder, so they look at
  the ``.git`` entries on git's search path first, as the ``--all`` checks do;
- a nested folder whose ``.git`` is a link is left out of every walk, and the
  report names that ``.git`` entry;
- a folder the walk cannot list is named in the report, not read as empty;
- the history read of ``agents-md-coverage-grep`` keeps the time of a file
  whose name git would quote;
- what ``agents-md-coverage-grep`` and ``conventional-commit-grep`` report
  from the command line when a ``.git`` on git's search path is a link.

Windows junctions need no privilege, so the folder-link tests run everywhere.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import NoReturn

import pytest

from apothem.conformity import (
    _bounded_run,
    _project_paths,
    agents_md_coverage_grep,
    conventional_commit_grep,
    no_global_plans_grep,
    production_ready_pr_grep,
    semver_stability_grep,
)
from apothem.conformity._grep_base import iter_tree_files
from apothem.conformity._project_paths import start_skip_log, take_skipped_paths
from tests._shared.git_env import hermetic_git_env

_LINKED_GIT_MESSAGE = "the .git entry is a link, so git would read another repository"


def _write(path: Path, text: str = "x\n") -> Path:
    """Write *text* to *path*, making its folders first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _link_folder(link: Path, target: Path) -> None:
    """Make *link* a folder link to *target*: a junction on Windows."""
    if os.name == "nt":
        winapi = pytest.importorskip("_winapi")
        winapi.CreateJunction(str(target), str(link))
        return
    link.symlink_to(target, target_is_directory=True)


def _git(cwd: Path, *args: str, stdin: bytes | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=hermetic_git_env(),
        check=True,
        capture_output=True,
        input=stdin,
    )
    return completed.stdout.decode("utf-8")


def _repository(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    _git(folder, "init", "-q")
    _git(folder, "config", "user.email", "test@apothem.invalid")
    _git(folder, "config", "user.name", "apothem-test")
    _git(folder, "config", "commit.gpgsign", "false")
    return folder


def _project_with_linked_git(tmp_path: Path) -> Path:
    """Return a project whose ``.git`` links to another repository with a staged file."""
    other = _repository(tmp_path / "other")
    _write(other / "src" / "apothem" / "mod.py", "def f():\n    pass\n")
    _git(other, "add", "-A")
    root = (tmp_path / "project").resolve()
    root.mkdir()
    _link_folder(root / ".git", other / ".git")
    return root


def _no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any program start fail the test, git through ``run_git`` or not."""

    def no_program(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError(f"a program started: {args!r}")

    monkeypatch.setattr(_bounded_run, "_POPEN", no_program)
    monkeypatch.setattr(subprocess, "Popen", no_program)


# ---------------------------------------------------------------------------
# The --staged checks look at the .git entries before git runs
# ---------------------------------------------------------------------------


def test_the_staged_class_check_refuses_a_linked_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project_with_linked_git(tmp_path)
    monkeypatch.chdir(root)
    _no_git(monkeypatch)
    result = production_ready_pr_grep._check_staged()
    assert result.passed is False
    assert result.check_error == _LINKED_GIT_MESSAGE


def test_the_staged_class_check_refuses_a_linked_git_above(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project_with_linked_git(tmp_path)
    inner = root / "pkg"
    inner.mkdir()
    monkeypatch.chdir(inner)
    _no_git(monkeypatch)
    result = production_ready_pr_grep._check_staged()
    assert result.passed is False
    assert result.check_error == (
        f"the .git entry {(root / '.git').as_posix()} on git's search path "
        "is a link, so the gate does not run git below it"
    )


def test_the_staged_surface_check_refuses_a_linked_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project_with_linked_git(tmp_path)
    _write(root / "src" / "apothem" / "__init__.py", '__version__ = "1.2.0"\n')
    monkeypatch.chdir(root)
    _no_git(monkeypatch)
    code = semver_stability_grep._main(["semver-stability-grep", "--staged"])
    payload = json.loads(capsys.readouterr().out)
    assert code != 0
    assert payload["passed"] is False
    assert payload["check_error"] == _LINKED_GIT_MESSAGE


def test_the_staged_class_check_still_runs_in_a_plain_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repository(tmp_path / "plain")
    _write(root / "CHANGELOG.md")
    _git(root, "add", "-A")
    monkeypatch.chdir(root)
    assert production_ready_pr_grep._staged_paths() == ["CHANGELOG.md"]


# ---------------------------------------------------------------------------
# A nested .git link is named, not dropped silently
# ---------------------------------------------------------------------------


def _folder_with_linked_git(tmp_path: Path) -> Path:
    """Return a project whose ``docs`` folder holds a ``.git`` junction."""
    outside = tmp_path / "outside"
    outside.mkdir()
    root = (tmp_path / "project").resolve()
    _write(root / "README.md")
    _write(root / "docs" / "guide.md")
    _link_folder(root / "docs" / ".git", outside)
    return root


def test_the_walk_names_a_nested_linked_git(tmp_path: Path) -> None:
    root = _folder_with_linked_git(tmp_path)
    start_skip_log(root)
    walked = [p.relative_to(root).as_posix() for p in iter_tree_files(root, (".md",))]
    assert walked == ["README.md"]
    assert take_skipped_paths() == ["docs/.git"]


def test_the_walk_names_a_dangling_nested_linked_git(tmp_path: Path) -> None:
    root = _folder_with_linked_git(tmp_path)
    (tmp_path / "outside").rmdir()
    start_skip_log(root)
    assert [p.name for p in iter_tree_files(root, (".md",))] == ["README.md"]
    assert take_skipped_paths() == ["docs/.git"]


def test_the_walk_still_skips_a_real_nested_checkout_quietly(tmp_path: Path) -> None:
    root = (tmp_path / "project").resolve()
    _write(root / "README.md")
    _write(root / "nested" / "guide.md")
    (root / "nested" / ".git").mkdir()
    start_skip_log(root)
    assert [p.name for p in iter_tree_files(root, (".md",))] == ["README.md"]
    assert take_skipped_paths() == []


def test_the_stray_plans_sweep_names_a_nested_linked_git(tmp_path: Path) -> None:
    root = _folder_with_linked_git(tmp_path)
    (root / "docs" / ".plans").mkdir()
    start_skip_log(root)
    findings = no_global_plans_grep._sweep_stray_plans_dirs(root, frozenset())
    assert findings == []
    assert take_skipped_paths() == ["docs/.git"]


# ---------------------------------------------------------------------------
# A folder that cannot be listed is named
# ---------------------------------------------------------------------------


def _refuse_listing(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    """Make ``os.scandir`` refuse *folder*, as a denied listing would."""
    real = os.scandir

    def scandir(path: os.PathLike[str] | str) -> object:
        if Path(path) == folder:
            raise PermissionError(13, "denied", os.fspath(path))
        return real(path)

    monkeypatch.setattr(_project_paths.os, "scandir", scandir)


def test_the_walk_names_a_folder_it_cannot_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = (tmp_path / "project").resolve()
    _write(root / "README.md")
    _write(root / "docs" / "guide.md")
    _refuse_listing(monkeypatch, root / "docs")
    start_skip_log(root)
    assert [p.name for p in iter_tree_files(root, (".md",))] == ["README.md"]
    assert take_skipped_paths() == ["docs"]


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError(2, "not found"),
        NotADirectoryError(20, "not a folder"),
    ],
    ids=["missing", "not-a-folder"],
)
def test_a_folder_that_is_not_there_is_not_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: OSError
) -> None:
    def scandir(path: object) -> NoReturn:
        raise error

    monkeypatch.setattr(_project_paths.os, "scandir", scandir)
    start_skip_log(tmp_path)
    assert _project_paths.scan_entries(tmp_path / "gone") == []
    assert take_skipped_paths() == []


def test_a_path_too_long_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = FileNotFoundError(2, "not found")
    error.winerror = 206  # type: ignore[attr-defined]

    def scandir(path: object) -> NoReturn:
        raise error

    monkeypatch.setattr(_project_paths.os, "scandir", scandir)
    start_skip_log(tmp_path)
    assert _project_paths.scan_entries(tmp_path / "deep") == []
    assert take_skipped_paths() == ["deep"]


# ---------------------------------------------------------------------------
# The history read keeps a name git would quote
# ---------------------------------------------------------------------------


def test_the_history_keeps_a_name_git_would_quote(tmp_path: Path) -> None:
    """A tracked name with a quote, a backslash or a tab keeps its time.

    Such names cannot be made in a Windows folder, so they enter the index
    straight from a blob (Git for Windows refuses them unless
    ``core.protectNTFS`` is off); the history read never opens them.
    """
    root = _repository(tmp_path / "repo")
    _git(root, "config", "core.protectNTFS", "false")
    blob = _git(root, "hash-object", "-w", "--stdin", stdin=b"x\n").strip()
    names = ['a"b.md', "c\\d.md", "e\tf.md", "plain.md"]
    for name in names:
        _git(root, "update-index", "--add", "--cacheinfo", f"100644,{blob},{name}")
    _git(root, "commit", "-qm", "docs: names git quotes")
    history = agents_md_coverage_grep._read_history(root)
    assert history is not None
    assert set(history.times) == set(names)
    assert history.deleted == frozenset()


def test_the_history_marks_a_deleted_name(tmp_path: Path) -> None:
    root = _repository(tmp_path / "repo")
    _write(root / "kept.md")
    _write(root / "gone.md")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "docs: two files")
    _git(root, "rm", "-q", "gone.md")
    _git(root, "commit", "-qm", "docs: drop one")
    history = agents_md_coverage_grep._read_history(root)
    assert history is not None
    assert set(history.times) == {"kept.md", "gone.md"}
    assert history.deleted == frozenset({"gone.md"})
    assert history.root_is_top is True


# ---------------------------------------------------------------------------
# What the commands report for a linked .git
# ---------------------------------------------------------------------------


def _project_with_history_and_linked_git(tmp_path: Path) -> Path:
    """Return a project with its own repository below a folder whose .git is a link.

    git would use the project's own repository first; the gate refuses the
    whole search path all the same.
    """
    other = _repository(tmp_path / "dotfiles")
    home = (tmp_path / "home").resolve()
    home.mkdir()
    _link_folder(home / ".git", other / ".git")
    project = _repository(home / "proj")
    _write(project / "src" / "apothem" / "foo" / "AGENTS.md")
    _write(project / "src" / "apothem" / "foo" / "README.md")
    _write(project / "src" / "apothem" / "foo" / "mod.py")
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "feat: foo")
    return project


def test_the_coverage_command_skips_freshness_below_a_linked_git(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _project_with_history_and_linked_git(tmp_path)
    home_git = (project.parent / ".git").as_posix()
    code = agents_md_coverage_grep._main(["agents-md-coverage-grep", str(project)])
    payload = json.loads(capsys.readouterr().out)
    # Freshness is skipped, as with no history; the run is advisory and the
    # link is named.
    assert code == 0
    assert payload["passed"] is True
    assert payload["freshness_checked"] is False
    assert payload["skipped_links"] == [home_git]
    assert "check_error" not in payload or payload["check_error"] is None


def test_the_coverage_command_skips_freshness_for_a_linked_git_at_the_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project_with_linked_git(tmp_path)
    _write(root / "src" / "apothem" / "foo" / "README.md")
    _write(root / "src" / "apothem" / "foo" / "mod.py")
    code = agents_md_coverage_grep._main(["agents-md-coverage-grep", str(root)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["passed"] is True
    assert payload["freshness_checked"] is False
    assert payload["skipped_links"] == [".git"]


def test_the_commit_command_names_a_linked_git_above_its_own_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _project_with_history_and_linked_git(tmp_path)
    home_git = (project.parent / ".git").as_posix()
    code = conventional_commit_grep._main(["conventional-commit-grep", str(project)])
    payload = json.loads(capsys.readouterr().out)
    assert code != 0
    assert payload["status"] == "not-a-git-repo"
    assert payload["passed"] is False
    assert payload["check_error"] == (
        f"the .git entry {home_git} on git's search path is a link, so the "
        "gate does not run git below it"
    )
    assert payload["skipped_links"] == [home_git]


def test_the_commit_command_names_a_linked_git_at_the_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project_with_linked_git(tmp_path)
    code = conventional_commit_grep._main(["conventional-commit-grep", str(root)])
    payload = json.loads(capsys.readouterr().out)
    assert code != 0
    assert payload["status"] == "not-a-git-repo"
    assert payload["passed"] is False
    assert payload["check_error"] == _LINKED_GIT_MESSAGE
    assert payload["skipped_links"] == [".git"]
