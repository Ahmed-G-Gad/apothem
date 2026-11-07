# SPDX-License-Identifier: MIT

"""A Python port of github-slugger 2.0.0, the heading-id maker the docs site uses.

Why this module exists. Every heading on the docs site gets its id from
github-slugger (Fumadocs' ``remarkHeading`` runs one slugger per page), so the
fragment of an anchored link only works when it equals an id that package
produces. ``check_site_anchor_links.py`` checks that in the required Python CI
job, which has no ``site/node_modules``. This port computes the ids from the
page sources instead.

github-slugger lower-cases the text, deletes every code point in a table that
its ``regex.js`` holds, turns each space into ``-``, and suffixes ``-1``, ``-2``
and so on when a page repeats an id. The table is Unicode data, so it is not
re-derived here: ``github-slugger-removed.txt`` records it as ranges, written
from the installed package by ``site/scripts/github-slugger-table.mjs`` and
compared with that package by ``npm test``.

The port works on code points where the JavaScript regex works on UTF-16 code
units. The two agree for well-formed text, because the regex removes an astral
character whole or not at all (checked over every code point when the table was
generated).
"""

from __future__ import annotations

import bisect
from functools import cache, lru_cache
from pathlib import Path

TABLE_PATH = Path(__file__).with_name("github-slugger-removed.txt")


@lru_cache(maxsize=1)
def _removed_ranges() -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return the first and last code point of each removed range, in order."""
    firsts: list[int] = []
    lasts: list[int] = []
    for line in TABLE_PATH.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        first, _, last = entry.partition("-")
        firsts.append(int(first, 16))
        lasts.append(int(last or first, 16))
    return tuple(firsts), tuple(lasts)


@cache
def is_removed(code_point: int) -> bool:
    """True when github-slugger deletes *code_point* from a heading."""
    firsts, lasts = _removed_ranges()
    index = bisect.bisect_right(firsts, code_point) - 1
    return index >= 0 and code_point <= lasts[index]


def slug(value: str) -> str:
    """Return the id github-slugger makes from *value*, ignoring repeats."""
    kept = "".join(char for char in value.lower() if not is_removed(ord(char)))
    return kept.replace(" ", "-")


class Slugger:
    """One page's slugger: repeated headings get ``-1``, ``-2`` suffixes."""

    def __init__(self) -> None:
        self._occurrences: dict[str, int] = {}

    def slug(self, value: str) -> str:
        """Return the id for the next heading whose text is *value*."""
        base = slug(value)
        result = base
        while result in self._occurrences:
            self._occurrences[base] += 1
            result = f"{base}-{self._occurrences[base]}"
        self._occurrences[result] = 0
        return result
