# SPDX-License-Identifier: MIT

"""Self-tests for the no-global-plans-grep validator."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "no_global_plans_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("no_global_plans_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["no_global_plans_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def _git_init(repo: Path) -> None:
    """Create a minimal git repo at repo with a deterministic identity."""
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)


def _commit_all(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", message, "--no-verify"], cwd=repo, check=True
    )


def test_clean_repo_with_no_plans_passes(tmp_path: Path) -> None:
    """A repo without any tracked .plans/ path returns passed=True."""
    _git_init(tmp_path)
    (tmp_path / "README.md").write_text("# repo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    _commit_all(tmp_path, "init")
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []
    assert result.tracked_count == 2


def test_gitignored_plans_directory_passes(tmp_path: Path) -> None:
    """The recursion case: the canonical .apothem/plans/ tree exists on disk but
    is gitignored, so git ls-files returns empty for it → validator passes.
    """
    _git_init(tmp_path)
    (tmp_path / ".gitignore").write_text(".apothem/\n", encoding="utf-8")
    plans_dir = tmp_path / ".apothem" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "draft.md").write_text("# draft plan\n", encoding="utf-8")
    (plans_dir / "notes.md").write_text("notes\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# repo\n", encoding="utf-8")
    _commit_all(tmp_path, "init with gitignored .apothem/plans/")
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []
    # Only .gitignore + README.md are tracked; .apothem/* is ignored.
    assert result.tracked_count == 2


def test_tracked_top_level_plans_path_fails(tmp_path: Path) -> None:
    """A .plans/ directory committed at the root is a finding."""
    _git_init(tmp_path)
    plans_dir = tmp_path / ".plans"
    plans_dir.mkdir()
    (plans_dir / "draft.md").write_text("# leaked plan\n", encoding="utf-8")
    _commit_all(tmp_path, "init with leaked .plans/")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].path == ".plans/draft.md"
    assert "tracked in git" in result.findings[0].detail


def test_tracked_nested_plans_path_fails(tmp_path: Path) -> None:
    """A nested .plans/ path (subdir/.plans/foo) is also a finding."""
    _git_init(tmp_path)
    nested = tmp_path / "subdir" / ".plans"
    nested.mkdir(parents=True)
    (nested / "draft.md").write_text("# nested leaked plan\n", encoding="utf-8")
    _commit_all(tmp_path, "init with nested leaked .plans/")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].path == "subdir/.plans/draft.md"


def test_lookalike_paths_do_not_match(tmp_path: Path) -> None:
    """Paths like docs/plans-discipline.md or my.plans/x are NOT
    findings — the path-segment regex requires `.plans/` as a full
    directory name.
    """
    _git_init(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "plans-discipline.md").write_text(
        "# plans discipline\n", encoding="utf-8"
    )
    (tmp_path / "myplans").mkdir()
    (tmp_path / "myplans" / "x.md").write_text("# not .plans\n", encoding="utf-8")
    _commit_all(tmp_path, "init with lookalike paths")
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []


def test_multiple_tracked_plans_paths_all_flagged(tmp_path: Path) -> None:
    """Every tracked .plans/ path is reported; counts are accurate."""
    _git_init(tmp_path)
    plans_dir = tmp_path / ".plans"
    plans_dir.mkdir()
    (plans_dir / "a.md").write_text("a\n", encoding="utf-8")
    (plans_dir / "b.md").write_text("b\n", encoding="utf-8")
    nested = tmp_path / "modules" / ".plans"
    nested.mkdir(parents=True)
    (nested / "c.md").write_text("c\n", encoding="utf-8")
    _commit_all(tmp_path, "init with three leaked .plans/")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 3
    flagged = {f.path for f in result.findings}
    assert flagged == {".plans/a.md", ".plans/b.md", "modules/.plans/c.md"}


def test_main_cli_returns_exit_zero_on_pass(tmp_path: Path) -> None:
    """The CLI entry point returns EXIT_PASS (0) on a clean repo."""
    _git_init(tmp_path)
    (tmp_path / "README.md").write_text("# repo\n", encoding="utf-8")
    _commit_all(tmp_path, "init")
    rc = _MOD._main([str(_GREP_PATH), str(tmp_path)])
    assert rc == _MOD.EXIT_PASS


def test_main_cli_returns_exit_two_on_findings(tmp_path: Path) -> None:
    """The CLI entry point returns EXIT_FAIL (2) when .plans/ is tracked."""
    _git_init(tmp_path)
    (tmp_path / ".plans").mkdir()
    (tmp_path / ".plans" / "x.md").write_text("x\n", encoding="utf-8")
    _commit_all(tmp_path, "init with .plans/")
    rc = _MOD._main([str(_GREP_PATH), str(tmp_path)])
    assert rc == _MOD.EXIT_FAIL
