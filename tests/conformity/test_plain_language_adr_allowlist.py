# SPDX-License-Identifier: MIT

"""Tests for the plain-language matcher's decision-record allowlist.

A page under ``site/content/docs/adr/`` is in scope for the matcher, with a
narrow per-term allowlist: the instruction-file names it decides about
(``copilot`` in ``.github/copilot-instructions.md``, ``agents`` in
``agents-md-wins``) and the ``AI Surface Canon`` section name clear, while every
other forbidden token is still flagged. The same allowlist holds on a locale
mirror of the page.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.conformity import plain_language_grep as plg

_ADR_REL = Path("site") / "content" / "docs" / "adr" / "0009-example.mdx"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _matches(root: Path, rel: Path) -> list[str]:
    return [finding.match for finding in plg._scan_file(root / rel, root)]


def test_adr_page_is_in_scope(tmp_path: Path) -> None:
    _write(tmp_path / _ADR_REL, "Plain prose.\n")
    assert plg._is_user_facing(tmp_path / _ADR_REL, tmp_path)


@pytest.mark.parametrize(
    "line",
    [
        "The shared claims mirror `.github/copilot-instructions.md`.",
        "The reconciliation strategy `agents-md-wins` decides conflicts.",
        "The AI Surface Canon section of `AGENTS.md` lists the claims.",
    ],
)
def test_adr_page_allows_instruction_file_names(tmp_path: Path, line: str) -> None:
    _write(tmp_path / _ADR_REL, line + "\n")
    assert _matches(tmp_path, _ADR_REL) == []


@pytest.mark.parametrize(
    ("line", "token"),
    [
        ("The decision was ratified in review.", "ratified"),
        ("The cursor adapter writes one file.", "cursor"),
        ("Each agent reads the file.", "agent"),
        ("This landed in phase 3.", "phase 3"),
    ],
)
def test_adr_page_still_flags_other_tokens(
    tmp_path: Path, line: str, token: str
) -> None:
    _write(tmp_path / _ADR_REL, line + "\n")
    assert [m.lower() for m in _matches(tmp_path, _ADR_REL)] == [token]


def test_locale_adr_page_shares_the_allowlist(tmp_path: Path) -> None:
    rel = Path("site") / "content" / "docs" / "ru" / "adr" / "0009-example.mdx"
    _write(tmp_path / rel, "`.github/copilot-instructions.md` was ratified.\n")
    assert [m.lower() for m in _matches(tmp_path, rel)] == ["ratified"]
