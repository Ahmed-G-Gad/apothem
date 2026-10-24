# SPDX-License-Identifier: MIT

"""Translate a source skill's tool allow-list to the key Qwen Code reads.

Qwen Code reads a skill's tool allow-list from the camelCase ``allowedTools``
frontmatter key, and the value must be a YAML array: any other shape throws
``"allowedTools" must be an array``. The hyphenated ``allowed-tools`` key that
other agents use is ignored
(``parseAllowedToolsField`` in ``packages/core/src/skills/types.ts`` at v0.26.0,
https://raw.githubusercontent.com/QwenLM/qwen-code/v0.26.0/packages/core/src/skills/types.ts;
https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/; both
retrieved 2026-10-24).

The source corpus writes ``allowed-tools`` as one comma-separated string, so
renaming the key alone would produce a value Qwen Code rejects. The Qwen Code
emission renames the key and rewrites the string as a block list, one entry per
line.

The rewrite is line-based, like :mod:`apothem.lib.claude_skill_frontmatter`: it
touches only the unindented ``allowed-tools:`` line inside the byte-0
frontmatter block and leaves every other line, and the body, byte-identical.
"""

from __future__ import annotations

import json
import re
from typing import Final

from apothem.lib.frontmatter import split_frontmatter

#: The source corpus's key and the spelling Qwen Code reads.
SOURCE_KEY: Final[str] = "allowed-tools"
QWEN_KEY: Final[str] = "allowedTools"

# TODO(clarify): the Qwen Code docs and source read on 2026-10-24 show the key
# and the array shape but not how Qwen Code parses one entry. Entries are
# carried as the source writes them, including a pattern entry such as
# ``Bash(git status *)``; the vendor hooks page says permission rules accept
# Claude Code's ``Bash``, ``Read`` and ``Write`` names, which was not checked
# against the skills parser.
# TODO(clarify): Qwen Code's types.ts also names ``user-invocable`` (hyphenated)
# where the source corpus writes ``userInvocable``. That key was not checked
# against the vendor docs, so this module does not rename it.

_QUOTED_SCALAR: Final[re.Pattern[str]] = re.compile(
    r"""("(?:[^"\\]|\\.)*"|'(?:[^']|'')*')[ \t]*(?:\#.*)?"""
)
_TRAILING_COMMENT: Final[re.Pattern[str]] = re.compile(r"[ \t]+#.*")


def _scalar_text(raw: str) -> str:
    """Return the string a one-line YAML scalar *raw* holds.

    Quoted scalars are unquoted (a double-quoted one is read as JSON would read
    it); a plain scalar loses a trailing ``# comment``.
    """
    match = _QUOTED_SCALAR.fullmatch(raw)
    if match is None:
        return _TRAILING_COMMENT.sub("", raw)
    quoted = match.group(1)
    if quoted[0] == "'":
        return quoted[1:-1].replace("''", "'")
    try:
        return str(json.loads(quoted))
    except ValueError:
        return quoted[1:-1]


def _split_entries(value: str) -> list[str]:
    """Split *value* on the commas that sit outside parentheses.

    A comma inside ``Bash(...)`` belongs to the pattern, not to the list.
    """
    entries: list[str] = []
    current: list[str] = []
    depth = 0
    for char in value:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            entries.append("".join(current))
            current = []
        else:
            current.append(char)
    entries.append("".join(current))
    return [entry.strip() for entry in entries if entry.strip()]


def translate_allowed_tools(text: str) -> str:
    """Return *text* with its ``allowed-tools`` key as Qwen Code's ``allowedTools``.

    A one-line scalar value (quoted or plain, entries separated by commas)
    becomes a block list of double-quoted entries. A value that is already a
    YAML list (a flow list, or a block list on the following lines) keeps its
    form and only the key changes. A block-scalar value (``>``, ``>-``, ``|``)
    is returned unchanged: its text sits on the following lines, which this
    one-line rewrite does not read, and Qwen Code ignores the hyphenated key
    where it would reject a scalar ``allowedTools``. Text with no top-level
    ``allowed-tools`` key, or one that already has an ``allowedTools`` key, is
    returned unchanged, so the translation is idempotent.
    """
    parts = split_frontmatter(text)
    if parts is None:
        return text
    block, rest = parts
    lines = block.split("\n")
    keys = [line.partition(":") for line in lines]
    if any(sep and key == QWEN_KEY for key, sep, _ in keys):
        return text
    index = next(
        (i for i, (key, sep, _) in enumerate(keys) if sep and key == SOURCE_KEY),
        None,
    )
    if index is None:
        return text
    value = keys[index][2]
    raw = value.strip()
    if raw.startswith((">", "|")):
        return text
    if not raw or raw.startswith("["):
        lines[index] = f"{QWEN_KEY}:{value}"
        return "\n".join(lines) + rest
    eol = "\r" if lines[index].endswith("\r") else ""
    entries = _split_entries(_scalar_text(raw))
    if entries:
        replacement = [f"{QWEN_KEY}:{eol}"] + [
            f"  - {json.dumps(entry, ensure_ascii=False)}{eol}" for entry in entries
        ]
    else:
        replacement = [f"{QWEN_KEY}: []{eol}"]
    lines[index : index + 1] = replacement
    return "\n".join(lines) + rest
