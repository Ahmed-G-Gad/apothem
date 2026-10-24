# SPDX-License-Identifier: MIT

"""Split a command into a slim ``SKILL.md`` plus on-demand reference files.

Claude Code re-attaches only the first 5,000 tokens of an invoked skill after a
context compaction, and its documentation recommends a ``SKILL.md`` of roughly
500 lines or fewer with detail in sibling files loaded on demand
(https://code.claude.com/docs/en/skills, retrieved 2026-10-24). The Apothem
commands run to 67 KB, so the Claude Code emission of a command-derived skill
passes the command through :func:`split_command_skill`.

The pipeline is fold, split, then append the note:

1. The caller folds the frontmatter (:func:`fold_apothem_metadata`).
2. :func:`split_command_skill` drops ``## Bindings`` (maintainer-only text),
   moves maintainer- and reference-shaped sections behind one-line pointers,
   and, while the file is over :data:`SPLIT_BUDGET_BYTES`, moves the largest
   Workflow steps and then the last-resort sections.
3. The caller appends the engine's ``## Installed Reference Paths`` note. The
   budget leaves :data:`NOTE_RESERVE_BYTES` for it, so the structure of the
   split never depends on the install root.

Everything here is a pure function of the source text. The pointer grammar is
regular and reversible: :func:`restore_command_skill` rebuilds the source minus
Bindings from ``SKILL.md`` plus the reference files, and the splitter refuses a
source that already contains a line of that grammar.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Final

from apothem.lib.frontmatter import split_frontmatter

#: Claude Code's post-compaction allowance per invoked skill, in tokens.
WINDOW_TOKENS: Final[int] = 5_000
#: Estimated bytes per token; no tokenizer is available to the build.
BYTES_PER_TOKEN: Final[float] = 3.4
#: Cap on the whole emitted ``SKILL.md`` (frontmatter, body and note): the
#: window at :data:`BYTES_PER_TOKEN`.
SKILL_MD_CAP_BYTES: Final[int] = int(WINDOW_TOKENS * BYTES_PER_TOKEN)
#: Room kept for the ``## Installed Reference Paths`` note appended after the
#: split (599 bytes at a 20-character install root, 1,199 at 140).
NOTE_RESERVE_BYTES: Final[int] = 1_200
#: Size the split itself targets: the cap minus the note reserve.
SPLIT_BUDGET_BYTES: Final[int] = SKILL_MD_CAP_BYTES - NOTE_RESERVE_BYTES
#: A Workflow step smaller than this never moves.
STEP_MOVE_MIN_BYTES: Final[int] = 600
#: The Claude Code documentation's line guidance for ``SKILL.md``.
SKILL_MD_MAX_LINES: Final[int] = 500
#: Limits of a pointer's ``Covers:`` list.
DIGEST_MAX_ITEMS: Final[int] = 8
DIGEST_MAX_BYTES: Final[int] = 320
#: Longest slug in a reference file name.
SLUG_MAX: Final[int] = 40

#: Native skills the cap does not cover yet, with the ceiling each may reach.
#: The source of a native skill is not split, so ``research-suite`` stays above
#: the cap until its source is restructured; the ceiling stops it growing.
NATIVE_SKILL_CEILINGS: Final[Mapping[str, int]] = {"research-suite": 24_000}

#: First lines of every reference file: the SPDX line and a blank line.
REFERENCE_HEADER: Final[str] = "<!-- SPDX-License-Identifier: MIT -->\n\n"


class SkillSplitError(ValueError):
    """Raised when a command cannot be split or restored safely."""


# --------------------------------------------------------------------------
# Section classes
# --------------------------------------------------------------------------

#: Removed from the emission (maintainer and conformity-gate text).
DROP_KINDS: Final[frozenset[str]] = frozenset({"Bindings"})

#: Moved to a reference file whatever the size: kind -> (file stem, trigger).
#: A ``None`` stem takes the slug of the kind (``Mode`` is named by its flag).
ALWAYS_MOVE: Final[Mapping[str, tuple[str | None, str]]] = {
    "Pipeline Contract": ("pipeline-contract", "pipeline"),
    "Foundational Stanzas": ("foundational-stanzas", "binding"),
    "Decision Tree": ("decision-tree", "tree"),
    "Example": ("examples", "example"),
    "Examples": ("examples", "example"),
    "Mode": (None, "mode"),
    "Cross-Dimension Critique Axes": (None, "cited"),
    "Per-Nuance Stop Inventory": (None, "cited"),
    "Remediation Action Vocabulary": (None, "cited"),
}

#: Moved only while the file is over budget, in this order; the first
#: occurrence of a kind moves.
LAST_RESORT: Final[tuple[str, ...]] = (
    "Output",
    "Mandates",
    "Critical Rules",
    "Instructions",
)
_LAST_RESORT_TRIGGER: Final[Mapping[str, str]] = {
    "Output": "output",
    "Mandates": "binding",
    "Critical Rules": "binding",
    "Instructions": "binding",
}

#: Always inline.
KEEP_KINDS: Final[frozenset[str]] = frozenset(
    {
        "Role",
        "Inputs",
        "Sequence Gate",
        "Workflow",
        "Recommended Next Step",
        "Failure Modes",
        "Verification Recipe",
        "Disciplines",
        "Amendment Modes",
        "Blind Review Mandate",
        "Current-SOTA Source-Consultation Mandate",
        "Beyond-Mission Remediation Grant",
        "Beyond-Mission Recommendation Grant",
        "Four-Discipline Operational Invariant",
        "Report-Only Boundary",
        "Self-Application Attestation",
    }
)

#: Every kind the splitter classifies; an unknown kind stays inline.
CLASSIFIED_KINDS: Final[frozenset[str]] = (
    DROP_KINDS | frozenset(ALWAYS_MOVE) | frozenset(LAST_RESORT) | KEEP_KINDS
)

_TRIGGERS: Final[Mapping[str, str]] = {
    "pipeline": (
        "MUST read it before the first step, after any context compaction, and "
        "before the final step or any handoff."
    ),
    "binding": (
        "MUST read it before the first step and after any context compaction; "
        "it binds every step."
    ),
    "tree": "SHOULD read it when a branch, gate failure, or state transition is unclear.",
    "example": "SHOULD read it before composing the final output.",
    "cited": "MUST read it before the first step; later steps cite it by name.",
    "output": (
        "MUST read it before the first step, because the steps write into the "
        "output, and again before producing the final output."
    ),
    "step": "MUST read it in full before executing this step.",
}

#: Inserted after the preamble when at least one reference file exists.
LEGEND: Final[str] = (
    "> **Reference files.** This skill's reference files sit in the "
    "`references/` directory next to this SKILL.md "
    "(`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names "
    "one of them and says when to read it. A context compaction discards file "
    "content you read earlier: after one, you MUST re-read the reference files "
    "that govern your current step."
)

#: The two pointer grammars. A source line matching either is refused, so a
#: pointer in the output is always one the splitter wrote.
BLOCK_STUB: Final[re.Pattern[str]] = re.compile(
    r"^> Moved to `references/[^`\n]+`\. ", re.MULTILINE
)
ITEM_STUB: Final[re.Pattern[str]] = re.compile(
    r"^\d+\. \*\*.+?\*\* Moved to `references/[^`\n]+`\. ", re.MULTILINE
)

# --------------------------------------------------------------------------
# Markdown scanning
# --------------------------------------------------------------------------

_OPEN_FENCE: Final[re.Pattern[str]] = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_CLOSE_FENCE: Final[re.Pattern[str]] = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")
_TRAILER: Final[re.Pattern[str]] = re.compile(r"(?:\n{2,}---)?\n*\Z")
_BLANKS: Final[re.Pattern[str]] = re.compile(r"\n*\Z")
_KIND_CUT: Final[re.Pattern[str]] = re.compile(r"\s+[\u2014\u2013]\s+|\s*[(:]")
_ITEM: Final[re.Pattern[str]] = re.compile(r"^(\d+\. \*\*.+?\*\*)")
#: A trailing parenthesised catalog id (``(CM-16)``, ``(D6)``) in a step title.
_TRAILING_ID: Final[re.Pattern[str]] = re.compile(
    r"\s*\((?:(?:CM|TM|CP)-\d+[A-Z]?|[DM]\d{1,2})\)\s*$"
)


def _lines(text: str) -> Iterator[tuple[int, str, bool]]:
    """Yield ``(offset, line, in_fence)`` for every line of *text*.

    Fences follow CommonMark: an opening run of at least three backticks or
    tildes after at most three spaces (a backtick fence's info string may not
    hold a backtick), closed by a run of the same character at least as long.
    """
    fence: tuple[str, int] | None = None
    offset = 0
    for line in text.split("\n"):
        inside = fence is not None
        if fence is None:
            opened = _OPEN_FENCE.match(line)
            if opened and not (opened.group(1)[0] == "`" and "`" in opened.group(2)):
                fence = (opened.group(1)[0], len(opened.group(1)))
                inside = True
        else:
            closed = _CLOSE_FENCE.match(line)
            if (
                closed
                and closed.group(1)[0] == fence[0]
                and len(closed.group(1)) >= fence[1]
            ):
                fence = None
        yield offset, line, inside
        offset += len(line) + 1
    if fence is not None:
        raise SkillSplitError("unterminated code fence")


def _starts(text: str, prefix: str) -> list[int]:
    """Return the offsets of the lines outside fences that begin with *prefix*."""
    return [
        o for o, line, inside in _lines(text) if not inside and line.startswith(prefix)
    ]


def _cut(text: str, offsets: list[int]) -> tuple[str, list[str]]:
    """Cut *text* at *offsets* into the text before the first cut and the parts."""
    if not offsets:
        return text, []
    parts = [text[a:b] for a, b in zip(offsets, [*offsets[1:], len(text)], strict=True)]
    return text[: offsets[0]], parts


def _tail_split(pattern: re.Pattern[str], text: str) -> tuple[str, str]:
    """Split *text* before the match of an end-anchored *pattern*."""
    match = pattern.search(text)
    if match is None:  # pragma: no cover - both patterns match at the end
        raise SkillSplitError("internal error: tail pattern did not match")
    return text[: match.start()], text[match.start() :]


def _kind(title: str) -> str:
    """Return the section kind: the H2 title up to its first separator."""
    return _KIND_CUT.split(title, maxsplit=1)[0].strip()


def _slug(text: str, limit: int = SLUG_MAX) -> str:
    """Return an ASCII file-name slug of at most *limit* characters."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    if len(slug) > limit:
        cut = slug[:limit]
        if slug[limit] != "-" and "-" in cut:
            cut = cut.rsplit("-", 1)[0]
        slug = cut
    return slug.strip("-") or "section"


# --------------------------------------------------------------------------
# Digest
# --------------------------------------------------------------------------

_DIGEST_MODE: Final[Mapping[str, str]] = {
    "Foundational Stanzas": "outline",
    "Pipeline Contract": "outline",
    "Critical Rules": "list",
    "Instructions": "list",
}


def _digest(kind: str, content: str) -> str:
    """Return the `` Covers: a; b.`` suffix of a pointer, or an empty string."""
    mode = _DIGEST_MODE.get(kind)
    if mode is None:
        return ""
    body = content.split("\n", 1)[1] if "\n" in content else ""
    if mode == "outline":
        # H3 titles, bold paragraph leads and bold sentence leads inside a
        # paragraph, in source order, so a standing obligation inside a
        # stanza is advertised as well as the stanza.
        items = [
            (m.group(1) or m.group(2) or m.group(3)).strip()
            for m in re.finditer(
                r"^(?:### (.{2,80}?)[ \t]*$|\*\*([^*\n]{2,80}?)\*\*)"
                r"|(?<=[.!?] )\*\*([^*\n]{2,80}?\.)\*\*",
                body,
                re.MULTILINE,
            )
        ]
    else:
        items = re.findall(
            r"^(?:\d+\.|[-*]) \*\*([^*\n]{2,80}?)\*\*", body, re.MULTILINE
        )
    items = [re.sub(r"[.:]+$", "", item).strip() for item in items]
    label = " Covers: "
    kept: list[str] = []
    for item in items[:DIGEST_MAX_ITEMS]:
        candidate = label + "; ".join([*kept, item]) + "."
        if len(candidate.encode("utf-8")) > DIGEST_MAX_BYTES:
            break
        kept.append(item)
    return f"{label}{'; '.join(kept)}." if kept else ""


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Unit:
    """One Workflow step: an H3 section or a numbered bold item."""

    text: str  # the step, without trailing blank lines
    gap: str  # what follows it up to the next unit; always stays inline
    title: str  # the H3 title, or the numbered lead
    numbered: bool
    ordinal: int  # 1-based position among all units of the Workflow

    @property
    def size(self) -> int:
        return len(self.text.encode("utf-8"))


@dataclass(frozen=True)
class _Section:
    """One H2 section of the body, with its trailing ``---`` rule apart."""

    heading: str
    kind: str
    content: str
    trailer: str
    head: str = ""  # Workflow only: heading plus the text before the first unit
    units: tuple[_Unit, ...] = ()


@dataclass(frozen=True)
class SplitSkill:
    """The result of splitting one command.

    Attributes:
        skill: ``SKILL.md`` text before the engine's note is appended.
        references: Reference file text by skill-relative POSIX path.
        moved: Every reference path, sorted.
        moved_sections: Kinds of the H2 sections moved, in source order.
        moved_steps: Reference paths of the Workflow steps moved, in order.
    """

    skill: str
    references: dict[str, str]
    moved: tuple[str, ...]
    moved_sections: tuple[str, ...]
    moved_steps: tuple[str, ...]


def _units_h3(content: str) -> tuple[str, list[_Unit]]:
    pre, parts = _cut(content, _starts(content, "### "))
    units: list[_Unit] = []
    for ordinal, part in enumerate(parts, 1):
        text, gap = _tail_split(_BLANKS, part)
        title = text.split("\n", 1)[0][4:].strip()
        units.append(_Unit(text, gap, title, False, ordinal))
    return pre, units


def _units_numbered(content: str) -> tuple[str, list[_Unit]]:
    """Find top-level numbered bold items outside fences.

    An item runs until the first following line that is neither blank nor
    indented; whatever lies between that point and the next item (blank lines,
    a trailing paragraph) stays inline as the item's gap.
    """
    lines = content.split("\n")
    offsets: list[int] = []
    position = 0
    for line in lines:
        offsets.append(position)
        position += len(line) + 1
    starts = [
        index
        for index, (_o, line, inside) in enumerate(_lines(content))
        if not inside and _ITEM.match(line)
    ]
    if not starts:
        return content, []
    units: list[_Unit] = []
    for n, first in enumerate(starts):
        limit = starts[n + 1] if n + 1 < len(starts) else len(lines)
        end = limit
        for j in range(first + 1, limit):
            line = lines[j]
            if line.strip() and not line.startswith((" ", "\t")):
                end = j
                break
        seg_start = offsets[first]
        seg_end = offsets[limit] if limit < len(lines) else len(content)
        item_end = offsets[end] if end < len(lines) else len(content)
        text, _ = _tail_split(_BLANKS, content[seg_start:item_end])
        lead = _ITEM.match(lines[first])
        if lead is None:  # pragma: no cover - ``starts`` holds only matches
            raise SkillSplitError("internal error: numbered item lost its lead")
        units.append(
            _Unit(
                text,
                content[seg_start + len(text) : seg_end],
                lead.group(1),
                True,
                n + 1,
            )
        )
    return content[: offsets[starts[0]]], units


def _parse(body: str) -> tuple[str, list[_Section]]:
    """Split a body into the text before the first H2 and its H2 sections."""
    pre, parts = _cut(body, _starts(body, "## "))
    sections: list[_Section] = []
    for part in parts:
        content, trailer = _tail_split(_TRAILER, part)
        heading = content.split("\n", 1)[0]
        kind = _kind(heading[3:].strip())
        head = ""
        units: tuple[_Unit, ...] = ()
        if kind == "Workflow" and "\n" in content:
            workflow_body = content.split("\n", 1)[1]
            before, found = _units_h3(workflow_body)
            if not found:
                before, found = _units_numbered(workflow_body)
            head = heading + "\n" + before
            units = tuple(found)
        sections.append(_Section(heading, kind, content, trailer, head, units))
    return pre, sections


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _unit_path(unit: _Unit) -> str:
    title = unit.title
    if unit.numbered:
        title = re.sub(r"^\d+\.\s+", "", title).strip("*")
    else:
        title = re.sub(
            r"^(?:Step|Phase|Stanza)\s+[\w.]+\s*[:\-\u2014\u2013]*\s*", "", title
        )
    title = _TRAILING_ID.sub("", title)
    return f"references/step-{unit.ordinal:02d}-{_slug(title)}.md"


def _mode_flag(heading: str) -> str | None:
    match = re.search(r"`(--[a-z][a-z0-9-]*)`", heading)
    return match.group(1) if match else None


def _section_path(section: _Section, used: set[str]) -> str:
    stem = ALWAYS_MOVE.get(section.kind, (None, ""))[0]
    if section.kind == "Mode":
        flag = _mode_flag(section.heading)
        base = "mode-" + _slug(flag.lstrip("-")) if flag else "mode"
    else:
        base = stem or _slug(section.kind)
    name, n = base, 2
    while f"references/{name}.md" in used:
        name = f"{base}-{n}"
        n += 1
    path = f"references/{name}.md"
    used.add(path)
    return path


def _section_trigger(section: _Section) -> str:
    if section.kind == "Mode":
        flag = _mode_flag(section.heading)
        if flag:
            return f"MUST read it when invoked with `{flag}`; otherwise skip it."
        return "MUST read it when this mode is requested; otherwise skip it."
    if section.kind in ALWAYS_MOVE:
        return _TRIGGERS[ALWAYS_MOVE[section.kind][1]]
    return _TRIGGERS[_LAST_RESORT_TRIGGER[section.kind]]


def _block_stub(path: str, trigger: str, digest: str = "") -> str:
    return f"> Moved to `{path}`. {trigger}{digest}"


def _reference_file(content: str) -> str:
    return f"{REFERENCE_HEADER}{content}\n"


@dataclass
class _Plan:
    """Which sections and steps move; the rendering input."""

    moved_sections: set[int]
    moved_units: set[int]


def _render(
    frontmatter: str, pre: str, sections: list[_Section], plan: _Plan
) -> tuple[str, dict[str, str], list[str], list[str]]:
    refs: dict[str, str] = {}
    section_kinds: list[str] = []
    step_paths: list[str] = []
    used: set[str] = set()
    parts: list[str] = []
    for index, section in enumerate(sections):
        if section.kind in DROP_KINDS:
            continue
        if index in plan.moved_sections:
            path = _section_path(section, used)
            refs[path] = _reference_file(section.content)
            section_kinds.append(section.kind)
            stub = _block_stub(
                path, _section_trigger(section), _digest(section.kind, section.content)
            )
            parts.append(f"{section.heading}\n\n{stub}{section.trailer}")
        elif section.kind == "Workflow" and section.units and plan.moved_units:
            chunk = [section.head]
            for unit in section.units:
                if unit.ordinal not in plan.moved_units:
                    chunk.append(unit.text + unit.gap)
                    continue
                path = _unit_path(unit)
                refs[path] = _reference_file(unit.text)
                step_paths.append(path)
                if unit.numbered:
                    chunk.append(
                        f"{unit.title} Moved to `{path}`. {_TRIGGERS['step']}{unit.gap}"
                    )
                else:
                    heading = unit.text.split("\n", 1)[0]
                    chunk.append(
                        f"{heading}\n\n{_block_stub(path, _TRIGGERS['step'])}{unit.gap}"
                    )
            parts.append("".join(chunk) + section.trailer)
        else:
            parts.append(section.content + section.trailer)
    legend = ""
    if refs:
        if not (frontmatter + pre).endswith("\n\n"):
            raise SkillSplitError("expected a blank line before the first H2")
        legend = LEGEND + "\n\n"
    return frontmatter + pre + legend + "".join(parts), refs, section_kinds, step_paths


def _normalize(text: str) -> str:
    """Return *text* with LF newlines, refusing a stray carriage return."""
    text = text.replace("\r\n", "\n")
    if "\r" in text:
        raise SkillSplitError("source holds a bare carriage return")
    return text


def split_command_skill(text: str, *, budget: int = SPLIT_BUDGET_BYTES) -> SplitSkill:
    """Split a folded command into ``SKILL.md`` text and reference files.

    Args:
        text: The command after :func:`fold_apothem_metadata`.
        budget: Size, in UTF-8 bytes, the split aims for. Workflow steps move
            largest first, one at a time, until the file fits; then the
            last-resort kinds move in :data:`LAST_RESORT` order. The split
            never raises on size; the tests enforce the cap.

    Raises:
        SkillSplitError: The text has no frontmatter, holds an unterminated
            code fence or a line of the pointer grammar, or has a bare
            carriage return.
    """
    text = _normalize(text)
    parts = split_frontmatter(text)
    if parts is None:
        raise SkillSplitError("missing frontmatter")
    if BLOCK_STUB.search(text) or ITEM_STUB.search(text):
        raise SkillSplitError("source already contains a reference pointer")
    frontmatter, body = parts
    pre, sections = _parse(body)
    plan = _Plan(
        moved_sections={i for i, s in enumerate(sections) if s.kind in ALWAYS_MOVE},
        moved_units=set(),
    )

    def size() -> int:
        return len(_render(frontmatter, pre, sections, plan)[0].encode("utf-8"))

    workflows = [s for s in sections if s.kind == "Workflow" and s.units]
    if len(workflows) > 1:
        raise SkillSplitError(
            "more than one Workflow section with steps; step files are keyed "
            "by one Workflow's step ordinals"
        )
    workflow = workflows[0] if workflows else None
    if workflow is not None and size() > budget:
        for unit in sorted(workflow.units, key=lambda u: (-u.size, u.ordinal)):
            if size() <= budget:
                break
            if unit.size >= STEP_MOVE_MIN_BYTES:
                plan.moved_units.add(unit.ordinal)
    for kind in LAST_RESORT:
        if size() <= budget:
            break
        for index, section in enumerate(sections):
            if section.kind == kind and index not in plan.moved_sections:
                plan.moved_sections.add(index)
                break
    skill, refs, kinds, steps = _render(frontmatter, pre, sections, plan)
    return SplitSkill(
        skill=skill,
        references=refs,
        moved=tuple(sorted(refs)),
        moved_sections=tuple(kinds),
        moved_steps=tuple(steps),
    )


# --------------------------------------------------------------------------
# Restore
# --------------------------------------------------------------------------

_RESTORE_BLOCK: Final[re.Pattern[str]] = re.compile(
    r"^(#{2,3} [^\n]*)\n\n> Moved to `(references/[^`\n]+)`\. [^\n]*$", re.MULTILINE
)
_RESTORE_ITEM: Final[re.Pattern[str]] = re.compile(
    r"^(\d+\. \*\*.+?\*\*) Moved to `(references/[^`\n]+)`\. [^\n]*$", re.MULTILINE
)


def _unwrap(references: Mapping[str, str], path: str) -> str:
    try:
        ref = references[path]
    except KeyError:
        raise SkillSplitError(
            f"pointer names a missing reference file: {path}"
        ) from None
    if not ref.startswith(REFERENCE_HEADER) or not ref.endswith("\n"):
        raise SkillSplitError(f"malformed reference file: {path}")
    return ref[len(REFERENCE_HEADER) : -1]


def restore_command_skill(skill: str, references: Mapping[str, str]) -> str:
    """Rebuild the command text from ``SKILL.md`` and its reference files.

    The inverse of :func:`split_command_skill` on text before the note is
    appended: it equals :func:`without_bindings` of the split input.

    Raises:
        SkillSplitError: A pointer names a file missing from *references*, or
            a reference file lacks the header or the final newline.
    """
    text = skill.replace(LEGEND + "\n\n", "", 1)
    text = _RESTORE_BLOCK.sub(lambda m: _unwrap(references, m.group(2)), text)
    return _RESTORE_ITEM.sub(lambda m: _unwrap(references, m.group(2)), text)


def without_bindings(text: str) -> str:
    """Return *text* minus its ``## Bindings`` sections: what restore yields."""
    parts = split_frontmatter(_normalize(text))
    if parts is None:
        raise SkillSplitError("missing frontmatter")
    frontmatter, body = parts
    pre, sections = _cut(body, _starts(body, "## "))
    kept = [
        s for s in sections if _kind(s.split("\n", 1)[0][3:].strip()) not in DROP_KINDS
    ]
    return frontmatter + pre + "".join(kept)
