# SPDX-License-Identifier: MIT

"""Cross-cutting mandates carry one title in the registry and in the corpus.

The public mandate registry (``site/content/docs/governance/
cross-cutting-mandates.mdx``) names each mandate; the rules, commands, and
plan template that cite a mandate by id must use the same title, or a reader
looking a mandate up by name cannot find the rule that implements it. The
registry entry for a rule-delegated mandate links to that rule.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_REGISTRY = (
    _REPO / "site" / "content" / "docs" / "governance" / "cross-cutting-mandates.mdx"
)
_CORPUS = _REPO / "src" / "apothem"

_REGISTRY_ENTRY_RE = re.compile(r"^- \*\*CM-(\d+) ([^*:]+?):?\*\*", re.MULTILINE)

# The three ways the corpus titles a mandate it cites by id.
_TITLE_AFTER_ID_RE = re.compile(r"CM-(\d+) \(([A-Z][a-z]+ [A-Z][a-z]+)[;)]")
_TITLE_BEFORE_ID_RE = re.compile(
    r"([A-Z][a-z]+ (?:Teams|Orchestration))\**\s?\((?:TM-\d+/)?CM-(\d+)\)"
)
_TABLE_ROW_RE = re.compile(
    r"\| CM-(\d+) \| [^|]*?([A-Z][a-z]+ (?:Teams|Orchestration)) \|"
)

_CHECKED_IDS = ("17", "25")


def _registry_titles() -> dict[str, str]:
    text = _REGISTRY.read_text(encoding="utf-8")
    return {number: title.strip() for number, title in _REGISTRY_ENTRY_RE.findall(text)}


def _corpus_titles() -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    for path in sorted(_CORPUS.rglob("*.md")):
        if "_vendor" in path.parts:
            continue
        rel = str(path.relative_to(_REPO))
        for line in path.read_text(encoding="utf-8").splitlines():
            found.extend((rel, n, t) for n, t in _TITLE_AFTER_ID_RE.findall(line))
            found.extend((rel, n, t) for t, n in _TITLE_BEFORE_ID_RE.findall(line))
            found.extend((rel, n, t) for n, t in _TABLE_ROW_RE.findall(line))
    return found


def test_registry_names_the_checked_mandates() -> None:
    titles = _registry_titles()
    for number in _CHECKED_IDS:
        assert titles.get(number), f"CM-{number} has no registry title"


def test_corpus_titles_match_the_registry() -> None:
    titles = _registry_titles()
    mismatches = [
        f"{rel}: CM-{number} titled {title!r}, registry says {titles[number]!r}"
        for rel, number, title in _corpus_titles()
        if number in _CHECKED_IDS and title != titles[number]
    ]
    assert mismatches == []


def test_registry_links_the_orchestration_rule() -> None:
    entry = next(
        line
        for line in _REGISTRY.read_text(encoding="utf-8").splitlines()
        if line.startswith("- **CM-25 ")
    )
    assert "rules/agent-orchestration.md" in entry
    assert "cross-link omitted" not in entry


def test_delegation_claims_name_a_real_delegator() -> None:
    """A rule that says CLAUDE.md delegates CM ids to it needs CM ids in CLAUDE.md."""
    claude_md = (_REPO / "CLAUDE.md").read_text(encoding="utf-8")
    rule = (_CORPUS / "rules" / "operational-mandates.md").read_text(encoding="utf-8")
    if "CM-" not in claude_md:
        assert "CLAUDE.md delegates" not in rule
