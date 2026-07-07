# SPDX-License-Identifier: MIT

"""Self-tests for the no-toplevel-docs-grep validator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "no_toplevel_docs_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("no_toplevel_docs_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["no_toplevel_docs_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def test_clean_root_without_docs_passes(tmp_path: Path) -> None:
    """A root with no docs/ directory returns passed=True."""
    (tmp_path / "README.md").write_text("# repo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []
    assert result.advisory is False


def test_canonical_site_tree_passes(tmp_path: Path) -> None:
    """The canonical documentation tree under site/ is fine; only a root
    docs/ is forbidden."""
    docs_tree = tmp_path / "site" / "content" / "docs"
    docs_tree.mkdir(parents=True)
    (docs_tree / "index.mdx").write_text("# home\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []


def test_nested_docs_directory_passes(tmp_path: Path) -> None:
    """A docs/ directory nested under another tree (not the root) is fine."""
    nested = tmp_path / "vendor" / "somepkg" / "docs"
    nested.mkdir(parents=True)
    (nested / "guide.md").write_text("# vendored docs\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []


def test_root_docs_directory_fails(tmp_path: Path) -> None:
    """A docs/ directory directly under the root is a finding."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "stray.md").write_text("# stray doc\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].path == "docs/"
    assert "site/" in result.findings[0].detail


def test_empty_root_docs_directory_fails(tmp_path: Path) -> None:
    """Even an empty root docs/ directory is a finding (the invariant is the
    directory's existence, not its contents)."""
    (tmp_path / "docs").mkdir()
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1


def test_main_cli_returns_exit_zero_on_pass(tmp_path: Path) -> None:
    """The CLI entry point returns EXIT_PASS (0) when no root docs/ exists."""
    (tmp_path / "README.md").write_text("# repo\n", encoding="utf-8")
    rc = _MOD._main([str(_GREP_PATH), str(tmp_path)])
    assert rc == _MOD.EXIT_PASS


def test_main_cli_returns_exit_two_on_findings(tmp_path: Path) -> None:
    """The CLI entry point returns EXIT_FAIL (2) when a root docs/ exists."""
    (tmp_path / "docs").mkdir()
    rc = _MOD._main([str(_GREP_PATH), str(tmp_path)])
    assert rc == _MOD.EXIT_FAIL
