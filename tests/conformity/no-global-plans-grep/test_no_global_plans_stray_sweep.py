# SPDX-License-Identifier: MIT

"""Self-tests for the no-global-plans-grep filesystem stray-suite sweep (G5).

The git-index check in ``no_global_plans_grep`` catches a *tracked* ``.plans/``
path. The additive filesystem sweep catches an *untracked stray* ``.plans/``
directory the index check is blind to: any on-disk plans directory that is not
the canonical ``<root>/.apothem/plans``. These tests exercise the sweep against
tmp_path fixtures with no git involvement so the stray detection is isolated
from the git-index path.
"""

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
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)


def test_sweep_helper_clean_when_only_canonical_plans(tmp_path: Path) -> None:
    """The sweep flags nothing when only the canonical <root>/.apothem/plans exists."""
    (tmp_path / ".apothem" / "plans").mkdir(parents=True)
    (tmp_path / ".apothem" / "plans" / "suite").mkdir()
    findings = _MOD._sweep_stray_plans_dirs(tmp_path, frozenset())
    assert findings == []


def test_sweep_helper_flags_nested_stray_plans(tmp_path: Path) -> None:
    """A nested stray .plans/ (e.g. under src/) is flagged by the sweep."""
    (tmp_path / ".apothem" / "plans").mkdir(parents=True)
    stray = tmp_path / "src" / "nested" / ".plans"
    stray.mkdir(parents=True)
    findings = _MOD._sweep_stray_plans_dirs(tmp_path, frozenset())
    assert len(findings) == 1
    assert findings[0].path == "src/nested/.plans/"
    assert "stray" in findings[0].detail


def test_sweep_helper_flags_sibling_stray_plans(tmp_path: Path) -> None:
    """A sibling-tree stray .plans/ is flagged even with no canonical one."""
    stray = tmp_path / "workspace" / ".plans"
    stray.mkdir(parents=True)
    findings = _MOD._sweep_stray_plans_dirs(tmp_path, frozenset())
    assert len(findings) == 1
    assert findings[0].path == "workspace/.plans/"


def test_sweep_helper_skips_vendored_and_cache_trees(tmp_path: Path) -> None:
    """A .plans/ inside _vendor/ or node_modules/ is NOT a stray apothem suite."""
    (tmp_path / "_vendor" / "pkg" / ".plans").mkdir(parents=True)
    (tmp_path / "node_modules" / "dep" / ".plans").mkdir(parents=True)
    findings = _MOD._sweep_stray_plans_dirs(tmp_path, frozenset())
    assert findings == []


def test_check_flags_stray_plans_with_count(tmp_path: Path) -> None:
    """check() surfaces the stray as a finding and records stray_plans_count."""
    _git_init(tmp_path)
    # Canonical project-local tree present; the stray sits in a sub-tree.
    (tmp_path / ".apothem" / "plans").mkdir(parents=True)
    stray = tmp_path / "sub" / ".plans"
    stray.mkdir(parents=True)
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert result.stray_plans_count == 1
    assert any("stray" in f.detail for f in result.findings)


def test_check_clean_with_only_canonical_plans(tmp_path: Path) -> None:
    """check() passes when only the canonical .apothem/plans exists, nothing tracked."""
    _git_init(tmp_path)
    (tmp_path / ".gitignore").write_text(".apothem/\n", encoding="utf-8")
    (tmp_path / ".apothem" / "plans").mkdir(parents=True)
    (tmp_path / ".apothem" / "plans" / "draft.md").write_text("# d\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init", "--no-verify"], cwd=tmp_path, check=True
    )
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.stray_plans_count == 0
    assert result.findings == []


def test_check_main_exit_two_on_stray(tmp_path: Path) -> None:
    """The CLI entry point exits EXIT_FAIL (2) when a stray .plans/ is on disk."""
    _git_init(tmp_path)
    stray = tmp_path / "elsewhere" / ".plans"
    stray.mkdir(parents=True)
    rc = _MOD._main([str(_GREP_PATH), str(tmp_path)])
    assert rc == _MOD.EXIT_FAIL
