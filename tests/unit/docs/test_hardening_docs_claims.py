# SPDX-License-Identifier: MIT

"""Keep the docs' security and Windows claims in line with what the code does.

Each check takes the text of a page, so a page that drifts back to an old
claim fails here: running the gate by path keeps Python modules out but not
the project's git config; the statusline command a user copied by hand is not
updated; the update stops on more than the old deny-list; the installers keep
GIT_CONFIG_NOSYSTEM; and Windows PowerShell 5.1 and cmd do not expand `~`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "site" / "content" / "docs"
LOCALES = {"ar", "de", "es", "fr", "hi", "id", "ja", "ko", "pt-br", "ru", "zh-cn"}
GATE_BY_PATH = "~/.apothem/src/apothem/conformity/gate.py"

GIT_CAVEAT_PAGES = (
    "SECURITY.md",
    "CHANGELOG.md",
    "site/content/docs/usage/conformity-gate.mdx",
    "site/content/docs/conformity-gate/index.mdx",
)
STATUSLINE_PAGES = (
    "SECURITY.md",
    "CHANGELOG.md",
    "site/content/docs/harnesses/claude-code.mdx",
)
NOSYSTEM_PAGES = ("site/content/docs/install/index.mdx",)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return " ".join(text.split())


def check_gate_git_caveat(text: str) -> None:
    flat = _flat(text)
    assert "a project you do not control" not in flat
    assert "`.git/config`" in flat
    assert "`--all-perwrite`" in flat


def check_statusline_upgrade_note(text: str) -> None:
    assert "add `-E -s` after the interpreter yourself" in _flat(text)


def check_nosystem_not_ignored(text: str) -> None:
    flat = _flat(text)
    lists = re.findall(r"another config file \(([^)]*)\)", flat)
    assert lists, "the sentence naming the ignored config variables is missing"
    for listed in lists:
        assert "GIT_CONFIG_NOSYSTEM" not in listed, listed


def check_updating_page(text: str) -> None:
    flat = _flat(text)
    for needle in (
        "`.git/config.worktree`",
        "`filter=`",
        "submodule",
        "`<APOTHEM_HOME>.lock`",
        "`pull.ff`",
    ):
        assert needle in flat, needle


def check_windows_gate_path(text: str) -> None:
    if GATE_BY_PATH not in text:
        return
    flat = _flat(text)
    assert "%USERPROFILE%\\.apothem\\" in flat, "no cmd form of the gate path"
    assert "in place of `python3`)." not in flat


def _gate_by_path_pages() -> list[str]:
    pages = [
        p for p in DOCS.rglob("*.mdx") if p.relative_to(DOCS).parts[0] not in LOCALES
    ]
    pages.append(ROOT / "src" / "apothem" / "skills" / "secret-rotation" / "SKILL.md")
    return sorted(
        str(p.relative_to(ROOT)).replace("\\", "/")
        for p in pages
        if GATE_BY_PATH in p.read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("rel", GIT_CAVEAT_PAGES)
def test_gate_pages_say_git_reads_the_project_config(rel: str) -> None:
    check_gate_git_caveat(_read(rel))


@pytest.mark.parametrize("rel", STATUSLINE_PAGES)
def test_pages_tell_users_to_fix_a_copied_statusline(rel: str) -> None:
    check_statusline_upgrade_note(_read(rel))


@pytest.mark.parametrize("rel", NOSYSTEM_PAGES)
def test_git_config_nosystem_is_not_listed_as_ignored(rel: str) -> None:
    check_nosystem_not_ignored(_read(rel))


def test_updating_page_describes_the_allow_list_and_lock() -> None:
    check_updating_page(_read("site/content/docs/install/updating.mdx"))


def test_gate_by_path_pages_found() -> None:
    assert len(_gate_by_path_pages()) >= 19


@pytest.mark.parametrize("rel", _gate_by_path_pages())
def test_gate_by_path_pages_give_a_windows_path(rel: str) -> None:
    check_windows_gate_path(_read(rel))
