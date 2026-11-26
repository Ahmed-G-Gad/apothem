# SPDX-License-Identifier: MIT

"""Unit tests for scripts/dev/check_changelog_released_sections.py."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import check_changelog_released_sections as check  # noqa: E402

TRAILER_NAME = check.TRAILER


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


def test_a_link_definition_line_inside_a_section_is_still_compared() -> None:
    base = BASE.replace(
        "- **Old fix.** Text.\n", "- **Old fix.** Text.\n\n[ref]: https://a.example\n"
    )
    head = base.replace("[ref]: https://a.example", "[ref]: https://b.example")
    (problem,) = check.find_problems(base, head)
    assert problem.startswith("[1.1.0]")


def test_the_closing_link_block_is_left_out() -> None:
    head = BASE.replace(
        "[1.0.0]: https://example.com/releases/tag/v1.0.0\n",
        "[1.0.0]: https://example.com/releases/tag/v1.0.0\n"
        "[0.9.0]: https://example.com/releases/tag/v0.9.0\n",
    )
    assert check.find_problems(BASE, head) == []


# The fixture's git must not read the user's own git config: a global
# tag.gpgSign or core.editor makes `git tag` open an editor and wait forever.
_CLEAN_ENV = {
    **{
        k: v
        for k, v in os.environ.items()
        if not k.startswith("GIT_") or k in ("GIT_EXEC_PATH",)
    },
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_EDITOR": "false",
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_CLEAN_ENV,
    ).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "config", "core.autocrlf", "false")
    (root / "CHANGELOG.md").write_text(BASE, encoding="utf-8", newline="\n")
    _git(root, "add", "CHANGELOG.md")
    _git(root, "commit", "-q", "-m", "base")
    _git(root, "tag", "base")
    monkeypatch.setattr(check, "REPO_ROOT", root)
    return root


def _commit_edit(repo: Path, message: str, old: str = "- **Old fix.** Text.\n") -> None:
    path = repo / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(old, old.replace("Text.", "Better text.")),
        encoding="utf-8",
        newline="\n",
    )
    _git(repo, "commit", "-q", "-am", message)


def _run(repo: Path, base: str = "base") -> int:
    return check.main(["--base", base, "--changelog", str(repo / "CHANGELOG.md")])


def test_main_fails_on_a_released_edit(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _commit_edit(repo, "edit old notes")
    assert _run(repo) == 1
    out = capsys.readouterr().out
    assert "[1.1.0]: the released section changed" in out
    assert check.TRAILER in out


def test_main_passes_a_released_edit_with_the_trailer_for_that_version(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _commit_edit(repo, f"edit old notes\n\n{check.TRAILER}: 1.1.0 fix a wrong command")
    assert _run(repo) == 0
    out = capsys.readouterr().out
    assert "allowed by" in out
    assert "fix a wrong command" in out
    assert "+- **Old fix.** Better text." in out


def test_a_trailer_for_another_version_does_not_allow_the_edit(repo: Path) -> None:
    _commit_edit(repo, f"edit old notes\n\n{check.TRAILER}: 1.0.0 something else")
    assert _run(repo) == 1


def test_a_trailer_allows_only_its_own_version(repo: Path) -> None:
    _commit_edit(repo, f"edit 1.1.0\n\n{check.TRAILER}: 1.1.0 fix")
    _commit_edit(repo, "edit 1.0.0 too", old="- **First.** Text.\n")
    assert _run(repo) == 1


@pytest.mark.parametrize(
    "trailer",
    [
        "Changelog-Released-Edits: 1.1.0 wrong key",
        "Changelog-Edit: 1.1.0 wrong key",
        f"{TRAILER_NAME}: no version given",
    ],
)
def test_only_the_exact_trailer_with_a_version_counts(repo: Path, trailer: str) -> None:
    _commit_edit(repo, f"edit old notes\n\n{trailer}")
    assert _run(repo) == 1


def test_a_trailer_older_than_the_base_does_not_count(repo: Path) -> None:
    _commit_edit(repo, f"first edit\n\n{check.TRAILER}: 1.0.0 earlier fix")
    _git(repo, "tag", "-f", "base")
    _commit_edit(repo, "second edit", old="- **First.** Text.\n")
    assert _run(repo) == 1


def test_a_wrapped_trailer_allows_only_its_first_version(repo: Path) -> None:
    _commit_edit(
        repo,
        f"edit old notes\n\n{check.TRAILER}: 1.0.0 the command shown for the "
        "upgrade from\n 1.1.0 was wrong",
    )
    assert check.allowed_versions("base") == {
        "1.0.0": "the command shown for the upgrade from 1.1.0 was wrong"
    }
    assert _run(repo) == 1


def test_git_is_asked_not_to_show_signatures(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    real_run = subprocess.run

    def recording_run(argv: list[str], **kwargs: object) -> object:
        calls.append(list(argv))
        return real_run(argv, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(check.subprocess, "run", recording_run)
    _commit_edit(repo, "edit old notes")
    assert _run(repo) == 1
    # The test's own git calls start with a bare "git"; the script's use the
    # full path shutil.which found.
    script_calls = [argv for argv in calls if argv[0] != "git"]
    assert script_calls
    assert all(argv[1:3] == ["-c", "log.showSignature=false"] for argv in script_calls)


def test_a_finding_prints_on_a_console_that_cannot_show_it(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _commit_edit(repo, "edit old notes", old="- **Old fix.** Text.\n")
    path = repo / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("Better text.", "Better text ✓."), "utf-8")
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1256", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    assert _run(repo) == 1
    stream.flush()
    assert b"the released section changed" in raw.getvalue()


def test_main_passes_when_nothing_released_changed(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(repo) == 0
    assert "OK" in capsys.readouterr().out


def test_main_reports_an_unknown_base(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(repo, "no-such-ref") == 2
    assert "failed" in capsys.readouterr().err


def test_main_reports_a_changelog_that_is_not_utf8(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "CHANGELOG.md").write_bytes(b"## [1.1.0]\n\xff\xfe\n")
    assert _run(repo) == 2
    assert capsys.readouterr().err


def test_git_location_variables_do_not_redirect_the_check(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "elsewhere" / ".git"))
    assert _run(repo) == 0


def test_the_repository_changelog_has_released_sections() -> None:
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    sections = check.released_sections(text)
    assert "1.5.0" in sections
    assert all(lines[0].startswith(f"## [{v}]") for v, lines in sections.items())
    assert check.find_problems(text, text) == []
