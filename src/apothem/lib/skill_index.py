# SPDX-License-Identifier: MIT

"""Session-start skill index: a compact, build-time list of the shipped skills.

Claude Code lists every skill name in its context but drops descriptions once
the listing outgrows its character budget, starting with the least-invoked
skills. A model that no longer sees a description may not know the skill exists
for its task. The index closes that gap: one short line per domain group, naming
the skills and a few words on what each group is for, delivered once at session
start so discovery survives listing truncation.

The index is generated, not scanned at hook time. :func:`build_index_message`
reads the catalog (``skills/*/SKILL.md`` and ``commands/*.md`` frontmatter) and
renders ``hooks/messages/skill-index.md``; the committed file is held to this
generator by a drift test, and ``scripts/dev/generate_skill_index.py`` rewrites
it. The SessionStart bootstrap reads the file when it exists and injects the
model-facing text; nothing is computed in the session.

Cues come from :data:`CATALOG_CUES`, a curated map of name to domain and cue,
not from descriptions: descriptions are rewritten often, and the index must not
change when they do. A catalog name with no entry fails generation, so a new
skill cannot ship undiscoverable by omission. Stdlib-only apart from the
frontmatter probe, so the generator runs from a bare checkout.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.lib.frontmatter import field_value_in_text

__all__ = [
    "CATALOG_CUES",
    "DOMAINS",
    "INDEX_MAX_CHARS",
    "INDEX_MESSAGE_REL",
    "IndexEntry",
    "SkillIndexError",
    "build_index_message",
    "collect_entries",
    "render_index_body",
]

#: Source-package-relative path of the generated message file.
INDEX_MESSAGE_REL: Final[Path] = Path("hooks") / "messages" / "skill-index.md"

#: Ceiling on the model-facing index text, in characters. The index costs its
#: size on every session start, so it stays near 400 tokens.
INDEX_MAX_CHARS: Final[int] = 1600

#: Prefix a plugin-installed manual skill is typed with. The bootstrap rewrites
#: it to a bare ``/`` when Apothem is installed through the engine, where the
#: skills carry no plugin namespace.
MANUAL_PREFIX: Final[str] = "/apothem:"

#: Domain groups in render order: ``(key, label, cue)``. The cue is the 3-6
#: word statement of what the group is for.
DOMAINS: Final[tuple[tuple[str, str, str], ...]] = (
    ("planning", "Planning", "specs and phased plans"),
    ("research", "Research", "question to paper"),
    ("review", "Review and audit", "find and rank defects"),
    ("engineering", "Engineering", "build, test, refactor code"),
    ("authoring", "Authoring and design", "documents, diagrams, UI"),
    ("operations", "Operations and release", "ship, repair, rotate safely"),
)

#: Curated cue map: catalog name to ``(domain key, short cue)``. An empty cue
#: means the name states its own purpose. Every shipped name needs an entry.
#: Cues stay to a few words: the whole index shares a 1,600 character cap
#: across more than sixty names, so only names that do not explain themselves
#: carry one.
CATALOG_CUES: Final[dict[str, tuple[str, str]]] = {
    # Planning
    "plan": ("planning", "full pipeline"),
    "plan-spec": ("planning", ""),
    "plan-generate": ("planning", ""),
    "plan-review": ("planning", ""),
    "plan-design": ("planning", ""),
    "plan-audit": ("planning", ""),
    "plan-amend": ("planning", ""),
    "plan-status": ("planning", ""),
    "plan-execute": ("planning", "one phase"),
    # Research
    "research": ("research", "full pipeline"),
    "research-ideate": ("research", ""),
    "research-spec": ("research", ""),
    "research-theory": ("research", ""),
    "research-sources": ("research", ""),
    "research-synthesis": ("research", ""),
    "research-design": ("research", ""),
    "research-experiment": ("research", ""),
    "research-analysis": ("research", ""),
    "research-paper": ("research", ""),
    "research-review": ("research", ""),
    "research-proposal": ("research", ""),
    "research-publish": ("research", ""),
    "research-disseminate": ("research", ""),
    "multi-source-research": ("research", ""),
    "source-synthesis": ("research", "given documents"),
    "knowledge-wiki": ("research", ""),
    "decision-matrix": ("research", ""),
    # Review and audit
    "audit": ("review", "all dimensions"),
    "code-audit": ("review", "cross-file"),
    "code-review": ("review", "per file"),
    "architecture-review": ("review", ""),
    "a11y-audit": ("review", ""),
    "dependency-audit": ("review", ""),
    "docs-review": ("review", ""),
    "perf-audit": ("review", ""),
    "security-audit": ("review", ""),
    "supply-chain-audit": ("review", ""),
    "threat-model-audit": ("review", ""),
    "ux-review": ("review", "CLI and DX"),
    "ecosystem-audit": ("review", "config tree"),
    "vuln-triage": ("review", "one CVE"),
    # Engineering
    "dev-toolkit": ("engineering", "debug, TDD"),
    "test-suite": ("engineering", ""),
    "test-authoring": ("engineering", ""),
    "surgical-guard": ("engineering", "minimal edit"),
    "refactor-extract": ("engineering", ""),
    "eval": ("engineering", "run model eval"),
    "eval-harness": ("engineering", ""),
    "prompt-engineering": ("engineering", ""),
    "dependency-upgrade": ("engineering", ""),
    # Authoring and design
    "document-authoring": ("authoring", ""),
    "diagram-authoring": ("authoring", ""),
    "ui-design": ("authoring", ""),
    "projectify": ("authoring", "chat Projects"),
    # Operations and release
    "release-readiness": ("operations", ""),
    "github-deploy-fresh": ("operations", "first release"),
    "github-deploy-next": ("operations", "next release"),
    "freshify": ("operations", "clean repo"),
    "fortress": ("operations", "harden repo"),
    "elevate": ("operations", "audit, critique"),
    "incident-runbook": ("operations", ""),
    "issue-lifecycle": ("operations", ""),
    "secret-rotation": ("operations", "leaked key"),
    "workflow": ("operations", "parallel, verified"),
}


class SkillIndexError(RuntimeError):
    """Raised when the index cannot be generated from the catalog."""


@dataclass(frozen=True)
class IndexEntry:
    """One shipped skill as the index sees it."""

    name: str
    manual: bool


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() == "true"


def collect_entries(src_root: Path) -> list[IndexEntry]:
    """Return the shipped, listable skills in name order.

    A command ships as a skill, so the set is the union of ``skills/*/SKILL.md``
    and ``commands/*.md``. A command sharing a name with a skill is the same
    shipped skill, and the skill's frontmatter wins, as in the install. A member
    that is not user-invocable is a reference template read by path and is not
    listed. ``manual`` is true when the member sets
    ``disable-model-invocation: true``.

    Raises:
        SkillIndexError: When a catalog directory is absent.
    """
    skills_dir = src_root / "skills"
    commands_dir = src_root / "commands"
    for directory in (skills_dir, commands_dir):
        if not directory.is_dir():
            raise SkillIndexError(f"catalog directory missing: {directory}")

    found: dict[str, IndexEntry | None] = {}
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        name = skill_md.parent.name
        if field_value_in_text(text, "userInvocable") == "false":
            found[name] = None
            continue
        found[name] = IndexEntry(
            name, _is_true(field_value_in_text(text, "disable-model-invocation"))
        )
    for command_md in sorted(commands_dir.glob("*.md")):
        if command_md.name == "README.md" or command_md.stem in found:
            continue
        text = command_md.read_text(encoding="utf-8")
        found[command_md.stem] = IndexEntry(
            command_md.stem,
            _is_true(field_value_in_text(text, "disable-model-invocation")),
        )
    return sorted(
        (entry for entry in found.values() if entry is not None),
        key=lambda entry: entry.name,
    )


def _item(entry: IndexEntry, cue: str) -> str:
    label = f"{MANUAL_PREFIX}{entry.name}" if entry.manual else entry.name
    return f"{label} ({cue})" if cue else label


def _group_items(members: list[IndexEntry]) -> list[str]:
    """Return the rendered items of one group.

    Model-invocable names with no cue that share a ``<family>-`` prefix, three
    or more of them, collapse to ``family-{a,b,c}``: the prefix is the longest
    repeated text in the index. Everything else renders one item per name, with
    manual names last.
    """
    plain = [e for e in members if not e.manual and not CATALOG_CUES[e.name][1]]
    families: dict[str, list[str]] = {}
    for entry in plain:
        family, sep, rest = entry.name.partition("-")
        if sep:
            families.setdefault(family, []).append(rest)
    collapsed = {
        family: sorted(tails) for family, tails in families.items() if len(tails) >= 3
    }
    items: list[str] = []
    emitted: set[str] = set()
    for entry in sorted(members, key=lambda e: (e.manual, e.name)):
        family, sep, _ = entry.name.partition("-")
        if sep and family in collapsed and entry in plain:
            if family not in emitted:
                emitted.add(family)
                items.append(f"{family}-{{{','.join(collapsed[family])}}}")
            continue
        items.append(_item(entry, CATALOG_CUES[entry.name][1]))
    return items


def render_index_body(entries: list[IndexEntry]) -> str:
    """Render the model-facing index text for *entries*.

    One line per domain group: the group label and cue, then its names with a
    short cue where the name does not explain itself. Manual names come last.

    Raises:
        SkillIndexError: When a name has no cue-map entry, or the text exceeds
            :data:`INDEX_MAX_CHARS`.
    """
    unmapped = sorted(e.name for e in entries if e.name not in CATALOG_CUES)
    if unmapped:
        raise SkillIndexError(
            "skills missing from CATALOG_CUES in apothem/lib/skill_index.py: "
            + ", ".join(unmapped)
        )
    # The blank line keeps the header alone in the first paragraph, which the
    # reference inventory uses as the message's one-line description.
    lines = [f"Skills by task. {MANUAL_PREFIX}name = manual, run only on request.", ""]
    for key, label, group_cue in DOMAINS:
        members = [e for e in entries if CATALOG_CUES[e.name][0] == key]
        if members:
            lines.append(f"{label} ({group_cue}): {', '.join(_group_items(members))}")
    body = "\n".join(lines)
    if len(body) > INDEX_MAX_CHARS:
        raise SkillIndexError(
            f"skill index is {len(body)} characters; the cap is {INDEX_MAX_CHARS}"
        )
    return body


def build_index_message(src_root: Path) -> str:
    """Return the full text of ``hooks/messages/skill-index.md``.

    The message keeps the file shape of the other hook messages: the license
    line, the model-facing body, and a closing ``## Bindings`` section, with a
    generated-file notice between body and Bindings. The notice follows the body
    because the reference inventory takes a message's description from its first
    line after the license comment. The emitters strip the comments and the
    Bindings section before the text reaches the model.
    """
    body = render_index_body(collect_entries(src_root))
    # Split so REUSE does not parse this literal as a license expression.
    header = "<!-- SPDX" + "-License-Identifier: MIT -->\n"
    return (
        header + "\n"
        f"{body}\n"
        "\n"
        "<!-- Generated by scripts/dev/generate_skill_index.py from the skill and"
        " command catalog; do not edit by hand. -->\n"
        "\n"
        "## Bindings (§0.j five-direction)\n"
        "\n"
        "- **Drives →** The session-start skill index: the shipped skills"
        " grouped by task, so discovery survives skill-listing truncation."
        " `hooks/session_start_bootstrap.py` (the handler that injects it).\n"
        "- **Established by ↑** `lib/skill_index.py` (the generator and its"
        " curated cue map) and the SessionStart registration in"
        " `hooks/hooks.json`.\n"
        "- **Cross-bound with ↔** `hooks/messages/sessionstart.md` (the"
        " standing posture this index travels beside).\n"
    )
