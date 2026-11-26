# SPDX-License-Identifier: MIT

"""Unit tests for scripts/dev/check_changelog_released_sections.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import check_changelog_released_sections as check  # noqa: E402,I001


BASE = """\
# Changelog

## [Unreleased]

## [1.1.0] - 2026-02-01

### Fixed

- **Old fix.** Text.

## [1.0.0] - 2026-01-01

### Added

- **First.** Text.

[Unreleased]: https://example.com/compare/v1.1.0...HEAD
[1.1.0]: https://example.com/releases/tag/v1.1.0
[1.0.0]: https://example.com/releases/tag/v1.0.0
"""


def test_an_entry_under_unreleased_passes() -> None:
    head = BASE.replace(
        "## [Unreleased]\n", "## [Unreleased]\n\n### Fixed\n\n- **New.** Text.\n"
    )
    assert check.find_problems(BASE, head) == []


def test_an_entry_that_lands_in_a_released_section_fails() -> None:
    head = BASE.replace(
        "- **Old fix.** Text.\n", "- **Old fix.** Text.\n- **New.** Text.\n"
    )
    problems = check.find_problems(BASE, head)
    assert len(problems) == 1
    assert problems[0].startswith("[1.1.0]: the released section changed")
    assert "+- **New.** Text." in problems[0]


def test_a_removed_released_section_fails() -> None:
    head = BASE.replace(
        "## [1.0.0] - 2026-01-01\n\n### Added\n\n- **First.** Text.\n\n", ""
    )
    assert check.find_problems(BASE, head) == [
        "[1.0.0]: the released section was removed"
    ]


def test_a_release_that_renames_unreleased_passes() -> None:
    base = BASE.replace(
        "## [Unreleased]\n", "## [Unreleased]\n\n### Fixed\n\n- **New.** Text.\n"
    )
    head = BASE.replace(
        "## [Unreleased]\n",
        "## [Unreleased]\n\n## [1.2.0] - 2026-03-01\n\n### Fixed\n\n- **New.** Text.\n",
    ).replace(
        "[Unreleased]: https://example.com/compare/v1.1.0...HEAD\n",
        "[Unreleased]: https://example.com/compare/v1.2.0...HEAD\n"
        "[1.2.0]: https://example.com/releases/tag/v1.2.0\n",
    )
    assert check.find_problems(base, head) == []


def test_line_endings_and_trailing_blank_lines_do_not_count() -> None:
    head = BASE.replace("\n", "\r\n").replace(
        "- **First.** Text.\r\n", "- **First.** Text.\r\n\r\n\r\n"
    )
    assert check.find_problems(BASE, head) == []


def test_a_long_diff_is_cut_short() -> None:
    extra = "".join(f"- **Entry {n}.** Text.\n" for n in range(40))
    head = BASE.replace("- **Old fix.** Text.\n", "- **Old fix.** Text.\n" + extra)
    (problem,) = check.find_problems(BASE, head)
    assert "more diff lines" in problem


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "CHANGELOG.md").write_text(BASE, encoding="utf-8", newline="\n")
    _git(root, "add", "CHANGELOG.md")
    _git(root, "commit", "-q", "-m", "base")
    _git(root, "tag", "base")
    monkeypatch.setattr(check, "REPO_ROOT", root)
    return root


def _commit_edit(repo: Path, message: str) -> None:
    path = repo / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("- **Old fix.** Text.\n", "- **Old fix.** Better text.\n"),
        encoding="utf-8",
        newline="\n",
    )
    _git(repo, "commit", "-q", "-am", message)


def test_main_fails_on_a_released_edit(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _commit_edit(repo, "edit old notes")
    rc = check.main(["--base", "base", "--changelog", str(repo / "CHANGELOG.md")])
    assert rc == 1
    out = capsys.readouterr().out
    assert "[1.1.0]: the released section changed" in out
    assert check.TRAILER in out


def test_main_passes_a_released_edit_with_the_trailer(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _commit_edit(repo, f"edit old notes\n\n{check.TRAILER}: fix a wrong command")
    rc = check.main(["--base", "base", "--changelog", str(repo / "CHANGELOG.md")])
    assert rc == 0
    assert "fix a wrong command" in capsys.readouterr().out


def test_main_passes_when_nothing_released_changed(repo: Path) -> None:
    rc = check.main(["--base", "base", "--changelog", str(repo / "CHANGELOG.md")])
    assert rc == 0


def test_main_reports_an_unknown_base(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = check.main(
        ["--base", "no-such-ref", "--changelog", str(repo / "CHANGELOG.md")]
    )
    assert rc == 2
    assert "failed" in capsys.readouterr().err


def test_the_repository_changelog_passes_against_itself() -> None:
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert check.find_problems(text, text) == []
    assert "1.5.0" in check.released_sections(text)
