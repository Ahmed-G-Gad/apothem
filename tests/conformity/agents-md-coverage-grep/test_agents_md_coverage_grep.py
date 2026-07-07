# SPDX-License-Identifier: MIT

"""Unit tests for the AGENTS.md coverage matcher under the root-only convention.

Under the root-only convention the repository carries a single agent-facing
canon at the root ``AGENTS.md``; per-folder operating guidance lives in each
folder's ``README.md``. Per-folder ``AGENTS.md`` companions are no longer
required — a meaningful folder without one passes. The matcher still
enumerates the meaningful-folder set (the navigable-folder set the README
convention applies to, and the freshness check's folder-ownership map) and
flags only a *present*, committed companion that fell stale relative to its
folder (freshness). The enumerator and the absence-passes semantics are
exercised here against a synthetic tree; freshness (git-commit-time based) is
exercised end-to-end by the in-process repo-root test, which runs inside the
real git history.
"""

from __future__ import annotations

from pathlib import Path

from apothem.conformity.agents_md_coverage_grep import check, meaningful_folders


def _write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_enumerator_includes_readme_folders_and_excludes_fixtures(
    tmp_path: Path,
) -> None:
    """Rule (A): a README folder is meaningful; a conformity fixture leaf is not."""
    _write(tmp_path / "pkg" / "README.md")
    _write(tmp_path / "tests" / "conformity" / "demo-grep" / "pass" / "README.md")
    _write(tmp_path / "examples" / "minimal-thing" / "README.md")

    folders = meaningful_folders(tmp_path)

    assert "pkg" in folders
    assert "tests/conformity/demo-grep/pass" not in folders
    assert "examples/minimal-thing" not in folders


def test_enumerator_includes_source_packages_and_excludes_vendored(
    tmp_path: Path,
) -> None:
    """Rule (B): a src/apothem python package without a README is meaningful;
    a vendored tree and a harness template leaf are excluded."""
    _write(tmp_path / "src" / "apothem" / "harnesses" / "demo" / "__init__.py")
    _write(
        tmp_path / "src" / "apothem" / "harnesses" / "demo" / "templates" / "render.py"
    )
    _write(tmp_path / "src" / "apothem" / "_vendor" / "dep" / "mod.py")

    folders = meaningful_folders(tmp_path)

    assert "src/apothem/harnesses/demo" in folders
    assert "src/apothem/harnesses/demo/templates" not in folders
    assert "src/apothem/_vendor/dep" not in folders


def test_meaningful_folder_without_companion_passes(tmp_path: Path) -> None:
    """Root-only convention: a meaningful folder lacking AGENTS.md passes.

    A per-folder ``AGENTS.md`` companion is no longer required — folder
    operating guidance lives in the folder's ``README.md``. The matcher must
    not emit a ``missing-companion`` finding for the absence, and authoring a
    companion does not change the verdict (it stays a clean pass).
    """
    _write(tmp_path / "pkg" / "README.md")

    before = check(tmp_path)
    assert before.passed is True
    assert before.findings == []
    # The retired finding class must no longer surface for absent companions.
    assert all(f.kind != "missing-companion" for f in before.findings)

    _write(tmp_path / "pkg" / "AGENTS.md", "---\nname: pkg\n---\n\ncompanion\n")

    after = check(tmp_path)
    assert after.passed is True
    assert after.findings == []


def test_freshness_skipped_without_git_history(tmp_path: Path) -> None:
    """Outside a git repository, freshness degrades to presence-only."""
    _write(tmp_path / "pkg" / "README.md")
    _write(tmp_path / "pkg" / "AGENTS.md")

    result = check(tmp_path)

    assert result.freshness_checked is False
    assert result.passed is True
