# SPDX-License-Identifier: MIT

"""Matcher-citation resolution guard for shipped Markdown surfaces.

Every ``conformity/<name>.py`` path cited in a shipped Markdown surface under
``src/apothem/`` (rules, hook messages, skills, commands, agents, and any other
``.md``) MUST resolve to a real file under ``src/apothem/conformity/``. Python
modules cannot contain hyphens, so a hyphenated citation
(``conformity/foo-grep.py``) is necessarily a dead path; this guard fails such
drift in CI instead of letting prose ship pointing at a file that does not
exist. The orchestrator ``conformity/gate.py`` and every ``*_grep.py`` matcher
are valid targets; ``gate.py`` resolves matchers by registration, not by these
cited paths, so nothing else catches the drift. The scope is deliberately the
whole shipped Markdown tree, not just ``rules/`` — citations also appear in hook
messages and skill docs.
"""

from __future__ import annotations

import re
from pathlib import Path

_APOTHEM_ROOT = Path(__file__).resolve().parents[2] / "src" / "apothem"
_CONFORMITY_DIR = _APOTHEM_ROOT / "conformity"

# A single ``conformity/`` path segment ending in ``.py`` (e.g.
# ``conformity/orphan_output_grep.py``) that denotes a shipped matcher module
# under ``src/apothem/conformity/``. Globs (``conformity/*_grep.py``) carry a
# ``*`` outside the character class and are intentionally not matched, and bare
# logical labels (```binding-reciprocity-grep```) carry no ``conformity/`` prefix
# or ``.py`` suffix, so they are out of scope by construction. The negative
# lookbehind excludes the sibling ``tests/conformity/`` test-module namespace,
# whose files resolve elsewhere and are not shipped matchers.
_CITATION = re.compile(r"(?<!tests/)conformity/([A-Za-z0-9_-]+)\.py")


def _cited_matchers() -> list[tuple[str, str]]:
    """Return (surface-rel-path, cited-filename) for every conformity/*.py citation."""
    citations: list[tuple[str, str]] = []
    for surface in sorted(_APOTHEM_ROOT.rglob("*.md")):
        text = surface.read_text(encoding="utf-8")
        rel = surface.relative_to(_APOTHEM_ROOT).as_posix()
        for match in _CITATION.finditer(text):
            citations.append((rel, f"{match.group(1)}.py"))
    return citations


def test_every_matcher_citation_resolves() -> None:
    """Each conformity/*.py path cited in a shipped surface resolves on disk."""
    unresolved = sorted(
        f"{surface}: conformity/{filename}"
        for surface, filename in _cited_matchers()
        if not (_CONFORMITY_DIR / filename).is_file()
    )
    assert not unresolved, (
        "shipped surface(s) cite a conformity matcher path that does not resolve "
        f"(hyphenated or stale citation): {unresolved}"
    )


def test_citation_guard_is_not_vacuous() -> None:
    """The scan finds citations — guards against a silently-empty match set."""
    assert _cited_matchers(), (
        "no conformity/*.py citations found under src/apothem/ — the guard would "
        "pass vacuously; check the apothem root path and citation regex"
    )
