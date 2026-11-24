# SPDX-License-Identifier: MIT

"""Files on which following a printed marker fix, or the run after it, went wrong.

Each test is one class of break the change-only advice property run found
(``test_advice_change_only_property.py``), cut down to its smallest file and
run through the library function the caller uses.
"""

from __future__ import annotations

import threading

from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    merge_managed_block,
    remove_managed_block,
)

B = APOTHEM_BLOCK_BEGIN
E = APOTHEM_BLOCK_END


def _lines(*lines: str) -> str:
    """Return *lines* as an LF text that ends in a newline."""
    return "".join(f"{line}\n" for line in lines)


def _strip_within(text: str, seconds: float = 5.0) -> str | None:
    """Return :func:`remove_managed_block` of *text*, or ``None`` when it does not return.

    The strip runs in a daemon thread, so a strip that never returns fails
    the test instead of hanging the run.
    """
    found: list[str] = []
    thread = threading.Thread(
        target=lambda: found.append(remove_managed_block(text)), daemon=True
    )
    thread.start()
    thread.join(seconds)
    return found[0] if found else None


# -- strip-hangs -------------------------------------------------------------


def test_the_strip_returns_when_a_copy_of_the_block_sits_after_frontmatter() -> None:
    """Two whole blocks, each followed by a ``---`` line, then a BEGIN marker.

    Once the first block is out, the file opens with what reads as
    frontmatter right before the copy, and the strip's loop over the copies
    took nothing out and never ended. It must return, and keep both ``---``
    lines and the BEGIN marker line at the end.
    """
    text = _lines(B, "r", E, "---", B, "r", E, "---", B)
    removed = _strip_within(text)
    assert removed is not None, "remove_managed_block never returned"
    lines = removed.split("\n")
    assert lines.count("---") == 2
    assert lines[-2] == B


# -- line-gone ---------------------------------------------------------------


def test_the_strip_keeps_your_opening_lines_that_are_no_frontmatter_mapping() -> None:
    """A file that opens with ``---``, a list item and ``---``, right above the block.

    That reads as frontmatter followed by the BEGIN marker, the shape a
    frontmatter-first rule file has, so the strip took the three lines for
    Apothem's frontmatter and deleted the file. Apothem's own frontmatter is
    a YAML mapping (``alwaysApply: true``, say); these lines are not one, so
    they stay.
    """
    text = _lines("---", "- item", "---", B, "x", E)
    assert remove_managed_block(text) == _lines("---", "- item", "---")


def test_the_strip_still_takes_out_apothem_s_own_frontmatter() -> None:
    """Apothem's frontmatter, a YAML mapping right above its block, goes with it."""
    body = _lines("---", "alwaysApply: true", "---", "Apothem rules.")
    merged = merge_managed_block(_lines("My notes."), body)
    assert merged.startswith(_lines("---", "alwaysApply: true", "---", B))
    assert remove_managed_block(merged) == _lines("My notes.")
