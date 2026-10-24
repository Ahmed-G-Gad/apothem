# SPDX-License-Identifier: MIT

"""The command-to-skill splitter: synthetic edge cases and the 45-command corpus."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from functools import cache
from pathlib import Path

import pytest

from apothem.harnesses._shared.install_driver_converters import claude_code_skill_text
from apothem.lib import claude_skill_split as split_mod
from apothem.lib.claude_skill_split import (
    ALWAYS_MOVE,
    BLOCK_STUB,
    CLASSIFIED_KINDS,
    DIGEST_MAX_BYTES,
    DIGEST_MAX_ITEMS,
    DROP_KINDS,
    ITEM_STUB,
    KEEP_KINDS,
    LAST_RESORT,
    LEGEND,
    NOTE_RESERVE_BYTES,
    REFERENCE_HEADER,
    SKILL_MD_CAP_BYTES,
    SKILL_MD_MAX_LINES,
    SPLIT_BUDGET_BYTES,
    STEP_MOVE_MIN_BYTES,
    SkillSplitError,
    restore_command_skill,
    split_command_skill,
    without_bindings,
)

_COMMANDS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "commands"
_COMMANDS = sorted(p for p in _COMMANDS_DIR.glob("*.md") if p.name != "README.md")
_REFERENCE_MAX_BYTES = 12_000
_FRONTMATTER = 'name: "x"\ndescription: "d"\nmetadata:\n  version: "1"\n'
_EN_DASH = chr(0x2013)
_EM_DASH = chr(0x2014)


def _doc(body: str) -> str:
    return f"---\n{_FRONTMATTER}---\n{body}"


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


def _stub_lines(skill: str) -> list[str]:
    return [line for line in skill.split("\n") if line.startswith("> Moved to")]


def _step(number: int, size: int, title: str = "Step") -> str:
    return f"### Step {number}: {title} {number}\n\n{'y' * size}\n\n"


def _workflow_doc(sizes: list[int]) -> str:
    steps = "".join(_step(i, size) for i, size in enumerate(sizes, 1))
    return _doc(
        f"\n# H\n\n## Role\n\nr\n\n---\n\n## Workflow\n\nIntro.\n\n{steps}---\n\n"
        "## Recommended Next Step\n\nn\n"
    )


def _step_ordinals(result: split_mod.SplitSkill) -> list[int]:
    return sorted(
        int(re.search(r"step-(\d+)-", p).group(1)) for p in result.moved_steps
    )  # type: ignore[union-attr]


# --------------------------------------------------------------------------
# Classification, names, digests
# --------------------------------------------------------------------------


def test_kind_is_cut_at_the_first_separator() -> None:
    kind = split_mod._kind
    assert kind(f"Mode {_EM_DASH} `--quick`") == "Mode"
    assert kind(f"Mode {_EN_DASH} `--quick`") == "Mode"
    assert kind("Mode: `--quick` (Lightweight)") == "Mode"
    assert kind("Bindings (maintainers)") == "Bindings"
    assert kind("Cross-Dimension Critique Axes") == "Cross-Dimension Critique Axes"
    assert kind("Example " + _EM_DASH + " Standard run") == "Example"


def test_section_classes_are_disjoint_and_triggers_resolve() -> None:
    classes = [DROP_KINDS, frozenset(ALWAYS_MOVE), frozenset(LAST_RESORT), KEEP_KINDS]
    assert sum(len(c) for c in classes) == len(CLASSIFIED_KINDS)
    for _stem, trigger in ALWAYS_MOVE.values():
        assert trigger in split_mod._TRIGGERS or trigger == "mode"
    for kind in LAST_RESORT:
        assert split_mod._LAST_RESORT_TRIGGER[kind] in split_mod._TRIGGERS


def test_constants_are_consistent() -> None:
    assert SPLIT_BUDGET_BYTES == SKILL_MD_CAP_BYTES - NOTE_RESERVE_BYTES == 15_800
    assert STEP_MOVE_MIN_BYTES == 600
    assert REFERENCE_HEADER.startswith("<!-- ")
    assert REFERENCE_HEADER.endswith(" -->" + chr(10) * 2)


def test_slug_is_ascii_bounded_and_cut_at_a_word() -> None:
    slug = split_mod._slug(
        "remediation-with-the-most-appropriate-action-extra words here"
    )
    assert slug == "remediation-with-the-most-appropriate"
    assert len(slug) <= split_mod.SLUG_MAX
    assert split_mod._slug("Café Über résumé") == "cafe-uber-resume"
    assert split_mod._slug(_EM_DASH) == "section"
    assert split_mod._slug("x" * 80) == "x" * split_mod.SLUG_MAX


def test_block_stub_text_is_exact() -> None:
    doc = _doc(
        "\n# H\n\n## Role\n\nr\n\n## Pipeline Contract\n\n**Alpha.** a\n\n"
        "**Beta:** b\n\n## Decision Tree\n\nt\n\n## Examples\n\ne\n"
    )
    result = split_command_skill(doc)
    assert _stub_lines(result.skill) == [
        "> Moved to `references/pipeline-contract.md`. MUST read it before the "
        "first step, and again before the final step or any handoff. "
        "Covers: Alpha; Beta.",
        "> Moved to `references/decision-tree.md`. SHOULD read it when a "
        "branch, gate failure, or state transition is unclear.",
        "> Moved to `references/examples.md`. SHOULD read it before composing "
        "the final output.",
    ]
    assert "## Pipeline Contract\n\n> Moved to" in result.skill
    assert result.moved_sections == ("Pipeline Contract", "Decision Tree", "Examples")
    assert result.moved_steps == ()


def test_legend_sits_after_the_preamble_and_only_with_references() -> None:
    doc = _doc("\n# H\n\nIntro.\n\n## Role\n\nr\n\n## Decision Tree\n\nt\n")
    skill = split_command_skill(doc).skill
    assert skill.index("Intro.") < skill.index(LEGEND) < skill.index("## Role")
    assert "${CLAUDE_SKILL_DIR}/references/" in LEGEND
    plain = split_command_skill(_doc("\n# H\n\n## Role\n\nr\n"))
    assert LEGEND not in plain.skill
    assert plain.references == {}


def test_legend_needs_a_blank_line_before_the_first_h2() -> None:
    with pytest.raises(SkillSplitError, match="blank line"):
        split_command_skill(_doc("# H\n## Decision Tree\n\nt\n"))


def test_digest_lists_at_most_eight_items_and_320_bytes() -> None:
    labels = [f"Label{i}" for i in range(12)]
    body = "".join(f"**{label}.** text\n\n" for label in labels)
    covers = split_mod._digest("Pipeline Contract", f"## Pipeline Contract\n\n{body}")
    assert covers == " Covers: " + "; ".join(labels[:DIGEST_MAX_ITEMS]) + "."
    long_labels = "".join(f"**{'w' * 60}{i}.** t\n\n" for i in range(8))
    capped = split_mod._digest(
        "Pipeline Contract", f"## Pipeline Contract\n\n{long_labels}"
    )
    assert 0 < _size(capped) - len(" ") <= DIGEST_MAX_BYTES
    assert capped.count(";") < 7
    assert split_mod._digest("Output", "## Output\n\n- **A.** b\n") == ""
    assert (
        split_mod._digest("Pipeline Contract", "## Pipeline Contract\n\nplain\n") == ""
    )


def test_digest_sources_per_kind() -> None:
    stanzas = "## Foundational Stanzas\n\n### Alpha:\n\nx\n\n### Beta.\n\ny\n"
    assert split_mod._digest("Foundational Stanzas", stanzas) == " Covers: Alpha; Beta."
    rules = "## Critical Rules\n\n- **NEVER guess.** x\n2. **ALWAYS ask:** y\n  - **nested** z\n"
    assert (
        split_mod._digest("Critical Rules", rules)
        == " Covers: NEVER guess; ALWAYS ask."
    )
    assert (
        split_mod._digest("Instructions", rules) == " Covers: NEVER guess; ALWAYS ask."
    )


def test_mode_sections_are_named_by_flag_and_collisions_get_a_suffix() -> None:
    doc = _doc(
        "\n# H\n\n## Mode: `--quick` (Lightweight)\n\nq\n\n## Mode\n\nm\n\n"
        "## Mode\n\nn\n\n## Example " + _EM_DASH + " One\n\no\n\n## Examples\n\ne\n"
    )
    result = split_command_skill(doc)
    assert sorted(result.references) == [
        "references/examples-2.md",
        "references/examples.md",
        "references/mode-2.md",
        "references/mode-quick.md",
        "references/mode.md",
    ]
    quick = next(line for line in _stub_lines(result.skill) if "mode-quick" in line)
    assert quick.endswith(
        "MUST read it when invoked with `--quick`; otherwise skip it."
    )
    plain = next(line for line in _stub_lines(result.skill) if "mode.md" in line)
    assert plain.endswith(
        "MUST read it when this mode is requested; otherwise skip it."
    )


def test_seed_sections_move_with_the_cited_trigger() -> None:
    doc = _doc(
        "\n# H\n\n## Cross-Dimension Critique Axes\n\na\n\n"
        "## Per-Nuance Stop Inventory\n\nb\n\n## Remediation Action Vocabulary\n\nc\n"
    )
    result = split_command_skill(doc)
    assert sorted(result.references) == [
        "references/cross-dimension-critique-axes.md",
        "references/per-nuance-stop-inventory.md",
        "references/remediation-action-vocabulary.md",
    ]
    assert all(
        line.endswith("before applying it.") for line in _stub_lines(result.skill)
    )


# --------------------------------------------------------------------------
# Markdown scanning
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fence",
    [
        "```text\n## not a heading\n### nor this\n```",
        "~~~\n## not a heading\n### nor this\n~~~",
        "   ```\n   ## not a heading\n   ### nor this\n   ```",
        "````\n```\n## not a heading\n### nor this\n```\n````",
        "~~~~\n~~~\n## not a heading\n### nor this\n~~~~",
    ],
    ids=["backtick", "tilde", "indented", "longer", "longer-tilde"],
)
def test_headings_inside_fences_are_not_structure(fence: str) -> None:
    body = f"\n# H\n\n## Role\n\nr\n\n## Workflow\n\n### Step 1: A\n\n{fence}\n\ntext\n\n### Step 2: B\n\nmore\n"
    _pre, sections = split_mod._parse(body)
    assert [s.kind for s in sections] == ["Role", "Workflow"]
    assert len(sections[1].units) == 2
    result = split_command_skill(_doc(body), budget=0)
    assert restore_command_skill(result.skill, result.references) == without_bindings(
        _doc(body)
    )


def test_a_backtick_fence_info_string_may_not_hold_a_backtick() -> None:
    body = "\n## Role\n\n``` a`b\n## Real heading\n\nx\n"
    _pre, sections = split_mod._parse(body)
    assert [s.kind for s in sections] == ["Role", "Real heading"]


def test_unterminated_fence_raises() -> None:
    with pytest.raises(SkillSplitError, match="unterminated"):
        split_command_skill(_doc("\n## Role\n\n```\nnever closed\n"))


def test_trailer_needs_a_blank_line_before_the_rule() -> None:
    _pre, sections = split_mod._parse("\n## A\n\ntext\n\n---\n\n## B\n\ntext\n---\n")
    assert sections[0].trailer == "\n\n---\n\n"
    assert sections[0].content == "## A\n\ntext"
    assert sections[1].trailer == "\n"
    assert sections[1].content.endswith("text\n---")


def test_the_rule_after_a_moved_step_stays_in_skill_md() -> None:
    result = split_command_skill(_workflow_doc([2000]), budget=0)
    assert result.moved_steps
    workflow = result.skill[result.skill.index("## Workflow") :]
    assert (
        workflow.index("> Moved to")
        < workflow.index("\n---\n")
        < workflow.index("## Recommended")
    )
    reference = result.references[result.moved_steps[0]]
    assert "---" not in reference


# --------------------------------------------------------------------------
# Workflow steps
# --------------------------------------------------------------------------


def test_steps_move_largest_first_until_the_file_fits() -> None:
    sizes = [1200, 900, 900, 700, 300, 650]
    doc = _workflow_doc(sizes)
    expected = [
        i
        for i, size in sorted(enumerate(sizes, 1), key=lambda t: (-t[1], t[0]))
        if size >= STEP_MOVE_MIN_BYTES
    ]
    by_moved: dict[int, int] = {}
    for budget in range(_size(doc) + 800, 0, -50):
        result = split_command_skill(doc, budget=budget)
        ordinals = _step_ordinals(result)
        assert sorted(expected[: len(ordinals)]) == ordinals, budget
        by_moved[len(ordinals)] = _size(result.skill)
    assert sorted(by_moved) == list(range(len(expected) + 1))
    for budget in range(_size(doc) + 800, 0, -50):
        moved = len(_step_ordinals(split_command_skill(doc, budget=budget)))
        assert moved == len(expected) or by_moved[moved] <= budget
        assert moved == 0 or by_moved[moved - 1] > budget


def test_tied_steps_move_in_source_order_and_the_floor_holds() -> None:
    doc = _workflow_doc([700, 700, 700, 560, 300])
    assert _step_ordinals(split_command_skill(doc, budget=0)) == [1, 2, 3]
    one = split_command_skill(
        doc, budget=_size(split_command_skill(doc, budget=10**9).skill) - 1
    )
    assert _step_ordinals(one) == [1]
    assert split_command_skill(doc, budget=10**9).moved_steps == ()


def test_step_files_are_named_by_ordinal_and_title() -> None:
    doc = _workflow_doc([800, 800, 800])
    paths = split_command_skill(doc, budget=0).moved_steps
    assert paths == (
        "references/step-01-step-1.md",
        "references/step-02-step-2.md",
        "references/step-03-step-3.md",
    )


def test_ordinals_count_unmoved_steps() -> None:
    doc = _workflow_doc([300, 900, 300])
    assert split_command_skill(doc, budget=0).moved_steps == (
        "references/step-02-step-2.md",
    )


def test_step_title_prefixes_are_stripped_from_the_slug() -> None:
    body = (
        "\n## Workflow\n\n"
        + f"### Phase 2.1 {_EN_DASH} Load context\n\n{'a' * 700}\n\n"
        + f"### Stanza 3 {_EM_DASH} Verify results\n\n{'b' * 700}\n\n"
        + f"### Plain heading\n\n{'c' * 700}\n"
    )
    paths = split_command_skill(_doc(body), budget=0).moved_steps
    assert paths == (
        "references/step-01-load-context.md",
        "references/step-02-verify-results.md",
        "references/step-03-plain-heading.md",
    )


_NUMBERED_BODY = """
# H

## Role

r

---

## Workflow

Intro line.

1. **Alpha step.** {big}
2. **Beta step.** {big}
   - nested bullet continues the item

     indented paragraph continues too
3. **Gamma step.** {big}

**Culmination.** trailing paragraph stays inline.

---

## Recommended Next Step

next
"""


def test_numbered_items_are_the_fallback_units() -> None:
    doc = _doc(_NUMBERED_BODY.format(big="x" * 900))
    result = split_command_skill(doc, budget=0)
    assert sorted(result.references) == [
        "references/step-01-alpha-step.md",
        "references/step-02-beta-step.md",
        "references/step-03-gamma-step.md",
    ]
    assert (
        "1. **Alpha step.** Moved to `references/step-01-alpha-step.md`. "
        "MUST read it in full before executing this step.\n"
    ) in result.skill
    assert "**Culmination.** trailing paragraph stays inline." in result.skill
    beta = result.references["references/step-02-beta-step.md"]
    assert "indented paragraph continues too" in beta
    assert "Culmination" not in beta
    assert restore_command_skill(result.skill, result.references) == without_bindings(
        doc
    )


def test_h3_steps_win_over_numbered_items() -> None:
    body = (
        "\n## Workflow\n\n1. **Not a unit.** x\n\n### Step 1: Real\n\n"
        + "z" * 700
        + "\n"
    )
    _pre, sections = split_mod._parse(body)
    assert [u.title for u in sections[0].units] == ["Step 1: Real"]


def test_numbered_items_inside_fences_are_ignored() -> None:
    body = "\n## Workflow\n\n```\n1. **Fake.** x\n```\n\n1. **Real.** y\n"
    _pre, sections = split_mod._parse(body)
    assert [u.title for u in sections[0].units] == ["1. **Real.**"]


# --------------------------------------------------------------------------
# Last resort
# --------------------------------------------------------------------------

_LAST_RESORT_BODY = (
    "\n# H\n\n## Role\n\nr\n\n## Instructions\n\n- **First.** i\n\n"
    "## Critical Rules\n\n- **NEVER assume.** x\n- **NEVER skip.** y\n\n"
    "## Mandates\n\n| a | b |\n| - | - |\n| CM-1 | s |\n\n"
    "## Output\n\n- o\n\n## Output\n\n- second\n\n## Recommended Next Step\n\nn\n"
)


def test_last_resort_sections_move_in_order_first_occurrence_only() -> None:
    doc = _doc(_LAST_RESORT_BODY)
    full = split_command_skill(doc, budget=0)
    assert full.moved_sections == (
        "Instructions",
        "Critical Rules",
        "Mandates",
        "Output",
    )
    assert full.skill.count("> Moved to") == 4
    assert "- second" in full.skill
    order = list(LAST_RESORT)
    for budget in range(_size(doc) + 200, 0, -20):
        moved = split_command_skill(doc, budget=budget).moved_sections
        in_order = [kind for kind in order if kind in moved]
        assert list(moved) == [
            k
            for k in ("Instructions", "Critical Rules", "Mandates", "Output")
            if k in moved
        ]
        assert in_order == order[: len(in_order)], budget
    assert split_command_skill(doc, budget=10**9).moved_sections == ()


def test_steps_move_before_last_resort_sections() -> None:
    body = _workflow_doc([2000, 2000])[len(f"---\n{_FRONTMATTER}---\n") :]
    doc = _doc(body + "\n## Output\n\n- o\n")
    budget = _size(split_command_skill(doc, budget=10**9).skill) - 100
    result = split_command_skill(doc, budget=budget)
    assert result.moved_steps
    assert "Output" not in result.moved_sections


def test_unclassified_kinds_stay_inline() -> None:
    doc = _doc("\n# H\n\n## Something New\n\nbody\n")
    result = split_command_skill(doc, budget=0)
    assert result.skill == doc
    assert result.references == {}


# --------------------------------------------------------------------------
# Inputs, outputs, reversal
# --------------------------------------------------------------------------


def test_a_minimal_command_passes_through_unchanged() -> None:
    doc = _doc("Body.\n")
    result = split_command_skill(doc)
    assert result.skill == doc
    assert result.references == {}
    assert result.moved == ()


def test_bindings_are_dropped_with_their_trailer_text() -> None:
    doc = _doc("\n# H\n\n## Role\n\nr\n\n---\n\n## Bindings (x)\n\n- **Drives** b\n")
    result = split_command_skill(doc)
    assert "Bindings" not in result.skill
    assert "Drives" not in result.skill
    assert result.skill.endswith("r\n\n---\n\n")


@pytest.mark.parametrize(
    "text",
    [
        "no frontmatter\n",
        _doc("\n## Role\n\n> Moved to `references/x.md`. foo\n"),
        _doc("\n## Workflow\n\n1. **Lead.** Moved to `references/x.md`. foo\n"),
        _doc("\n## Role\n\nstray\rcarriage return\n"),
    ],
    ids=["no-frontmatter", "block-stub", "item-stub", "bare-cr"],
)
def test_bad_sources_raise(text: str) -> None:
    with pytest.raises(SkillSplitError):
        split_command_skill(text)


def test_crlf_input_is_normalized_to_lf() -> None:
    doc = _workflow_doc([900, 900])
    crlf = split_command_skill(doc.replace("\n", "\r\n"), budget=0)
    lf = split_command_skill(doc, budget=0)
    assert crlf == lf
    assert "\r" not in crlf.skill


def test_reference_files_have_the_header_and_one_final_newline() -> None:
    result = split_command_skill(_workflow_doc([900, 900]), budget=0)
    assert result.references
    for text in result.references.values():
        assert text.startswith(REFERENCE_HEADER)
        assert text.endswith("\n")
        assert not text.endswith("\n\n")
        assert "Installed Reference Paths" not in text


def test_restore_rebuilds_the_source_without_bindings() -> None:
    body = (
        _LAST_RESORT_BODY + "\n## Pipeline Contract\n\n**A.** x\n\n## Bindings\n\n- b\n"
    )
    doc = _doc(body)
    for budget in (SPLIT_BUDGET_BYTES, 0, 10**9):
        result = split_command_skill(doc, budget=budget)
        assert restore_command_skill(
            result.skill, result.references
        ) == without_bindings(doc)


def test_restore_rejects_a_missing_or_malformed_reference() -> None:
    result = split_command_skill(_doc("\n## Decision Tree\n\nt\n"))
    with pytest.raises(SkillSplitError, match="missing reference"):
        restore_command_skill(result.skill, {})
    with pytest.raises(SkillSplitError, match="malformed"):
        restore_command_skill(result.skill, {"references/decision-tree.md": "t\n"})


def test_the_split_is_deterministic() -> None:
    doc = _doc(_NUMBERED_BODY.format(big="x" * 900))
    assert split_command_skill(doc, budget=0) == split_command_skill(doc, budget=0)


def test_stub_grammars_match_what_the_splitter_writes() -> None:
    result = split_command_skill(_doc(_NUMBERED_BODY.format(big="x" * 900)), budget=0)
    assert ITEM_STUB.search(result.skill)
    block = split_command_skill(_workflow_doc([900]), budget=0)
    assert BLOCK_STUB.search(block.skill)


# --------------------------------------------------------------------------
# The corpus
# --------------------------------------------------------------------------


@cache
def _folded(name: str) -> str:
    return claude_code_skill_text(
        (_COMMANDS_DIR / f"{name}.md").read_text(encoding="utf-8")
    )


@cache
def _split(name: str, budget: int = SPLIT_BUDGET_BYTES) -> split_mod.SplitSkill:
    return split_command_skill(_folded(name), budget=budget)


def _each_command(test: Callable[[str], None]) -> Callable[[str], None]:
    return pytest.mark.parametrize("name", [p.stem for p in _COMMANDS])(test)


def _h2_outline(text: str) -> list[str]:
    return [
        line
        for _o, line, inside in split_mod._lines(text)
        if not inside and line.startswith("## ")
    ]


def test_the_corpus_is_the_45_commands() -> None:
    assert len(_COMMANDS) == 45


@_each_command
def test_restore_equals_the_source_minus_bindings(name: str) -> None:
    for budget in (SPLIT_BUDGET_BYTES, 0, 10**9):
        result = _split(name, budget)
        assert restore_command_skill(
            result.skill, result.references
        ) == without_bindings(_folded(name)), budget


@_each_command
def test_bindings_never_reach_the_emission(name: str) -> None:
    result = _split(name)
    assert "## Bindings" not in result.skill
    assert all("## Bindings" not in text for text in result.references.values())


@_each_command
def test_h2_outline_is_the_source_minus_bindings(name: str) -> None:
    for budget in (SPLIT_BUDGET_BYTES, 0):
        emitted = _h2_outline(_split(name, budget).skill)
        expected = [
            h
            for h in _h2_outline(_folded(name))
            if split_mod._kind(h[3:].strip()) not in DROP_KINDS
        ]
        assert emitted == expected


@_each_command
def test_kept_sections_appear_verbatim(name: str) -> None:
    result = _split(name)
    body = _folded(name)
    _pre, sections = split_mod._parse(body[len(split_mod.split_frontmatter(body)[0]) :])  # type: ignore[index]
    for section in sections:
        if section.kind in KEEP_KINDS and section.kind != "Workflow":
            assert section.content in result.skill, section.kind
        if section.kind == "Workflow":
            assert section.head in result.skill


@_each_command
def test_every_pointer_maps_to_exactly_one_file(name: str) -> None:
    result = _split(name)
    block = re.findall(
        r"^> Moved to `(references/[^`\n]+)`\. ", result.skill, re.MULTILINE
    )
    item = re.findall(
        r"^\d+\. \*\*.+?\*\* Moved to `(references/[^`\n]+)`\. ",
        result.skill,
        re.MULTILINE,
    )
    pointers = [*block, *item]
    assert sorted(pointers) == sorted(result.references) == sorted(result.moved)
    assert len(set(pointers)) == len(pointers)
    assert len(result.moved_sections) + len(result.moved_steps) == len(
        result.references
    )
    assert (LEGEND in result.skill) == bool(result.references)


@_each_command
def test_reference_files_are_well_formed(name: str) -> None:
    for budget in (SPLIT_BUDGET_BYTES, 0):
        for path, text in _split(name, budget).references.items():
            assert re.fullmatch(r"references/[a-z0-9-]+\.md", path), path
            assert text.startswith(REFERENCE_HEADER), path
            assert text.endswith("\n"), path
            assert not text.endswith("\n\n"), path
            assert _size(text) <= _REFERENCE_MAX_BYTES, path


@_each_command
def test_emitted_text_is_clean(name: str) -> None:
    result = _split(name)
    for text in [result.skill, *result.references.values()]:
        assert "\n\n\n" not in text
        assert "\r" not in text
        assert not re.search(r"[ \t]+$", text, re.MULTILINE)


@_each_command
def test_no_source_line_matches_a_pointer_grammar(name: str) -> None:
    source = (_COMMANDS_DIR / f"{name}.md").read_text(encoding="utf-8")
    assert not BLOCK_STUB.search(source)
    assert not ITEM_STUB.search(source)


@_each_command
def test_skill_md_fits_the_split_budget_and_the_line_guidance(name: str) -> None:
    skill = _split(name).skill
    assert _size(skill.rstrip() + "\n") <= SPLIT_BUDGET_BYTES
    assert len(skill.split("\n")) <= SKILL_MD_MAX_LINES


@_each_command
def test_the_split_is_deterministic_for_every_command(name: str) -> None:
    assert split_command_skill(_folded(name)) == _split(name)


def test_every_corpus_kind_is_classified_and_every_table_entry_is_used() -> None:
    kinds: Counter[str] = Counter()
    for path in _COMMANDS:
        text = _folded(path.stem)
        body = text[len(split_mod.split_frontmatter(text)[0]) :]  # type: ignore[index]
        for _o, line, inside in split_mod._lines(body):
            if not inside and line.startswith("## "):
                kinds[split_mod._kind(line[3:].strip())] += 1
    assert set(kinds) - CLASSIFIED_KINDS == set()
    assert CLASSIFIED_KINDS - set(kinds) == set()
