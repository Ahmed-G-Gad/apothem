# SPDX-License-Identifier: MIT

"""The commands README records every command's model-invocation setting.

``disable-model-invocation: true`` makes a command operator-invoked only. The
README's invocation table is the reviewable record of which commands the model
may run on its own; this test keeps it equal to the command files, and keeps
the developer guide from stating a blanket rule the corpus does not follow.
"""

from __future__ import annotations

import re
from pathlib import Path

from apothem.lib.frontmatter import field_value

_REPO = Path(__file__).resolve().parents[2]
_COMMANDS = _REPO / "src" / "apothem" / "commands"
_ROW = re.compile(r"^\| `/([a-z0-9-]+)` \| `(true|false)` \|", re.MULTILINE)


def _table() -> dict[str, str]:
    readme = (_COMMANDS / "README.md").read_text(encoding="utf-8")
    start = readme.index("## Model invocation")
    end = readme.find("\n## ", start + 1)
    section = readme[start : end if end != -1 else None]
    rows = _ROW.findall(section)
    table = dict(rows)
    assert len(table) == len(rows), "a command is listed twice"
    return table


def _actual() -> dict[str, str]:
    return {
        path.stem: (field_value(path, "disable-model-invocation") or "").strip()
        for path in sorted(_COMMANDS.glob("*.md"))
        if path.name not in {"README.md", "AGENTS.md"}
    }


def test_table_lists_every_command_once() -> None:
    assert set(_table()) == set(_actual())


def test_table_matches_each_command_flag() -> None:
    actual = _actual()
    mismatched = {
        name: (flag, actual[name])
        for name, flag in _table().items()
        if actual.get(name) != flag
    }
    assert not mismatched


def test_developer_guide_states_no_blanket_rule() -> None:
    guide = (_REPO / "site" / "content" / "docs" / "developer-guide.mdx").read_text(
        encoding="utf-8"
    )
    assert "Always set `disable-model-invocation: true` for commands" not in guide
    assert "src/apothem/commands/README.md" in guide
