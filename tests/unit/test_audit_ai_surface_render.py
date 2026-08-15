# SPDX-License-Identifier: MIT

"""Characterization coverage for the AI-surface rendering tail.

``scan_ai_surfaces`` ends in three functions that turn scans, coherence
verdicts, and the authoring plan into documents. Together they were the
darkest region of the module — ``render_markdown`` alone is 168 lines and not
one of them ran under the suite.

The markdown renderer is worth pinning carefully because almost every branch
in it is a *fallback*: an absent surface, a surface with no level-two
headings, an empty coherence map, an empty plan, no contradictions. Those are
the paths a real run takes least often and a reader checks least carefully,
and each one writes prose that a consumer reads as a finding. The tests below
exercise the fallbacks at least as hard as the populated cases.

``render_markdown`` takes its timestamp as a parameter rather than reading the
clock, so unlike the provenance emitters its output is fully deterministic and
can be asserted whole.
"""

from __future__ import annotations

import json
from pathlib import Path

from apothem.audit.ai_surface_catalog import (
    ALL_SECTIONS_FOR_PRESENCE,
    COHERENCE_COHERENT,
    COHERENCE_CONTRADICTS,
    PRESENCE_ABSENT,
    PRESENCE_PRESENT,
    PRESENCE_RENAMED_PREFIX,
    SURFACE_ABSENT,
    SURFACE_PRESENT,
    SurfaceDescriptor,
)
from apothem.audit.ai_surface_model import PlanAction, SurfaceScan
from apothem.audit.ai_surface_parsing import HeadingBlock
from apothem.audit.ai_surface_render import (
    emit_json,
    render_markdown,
    serialise_scan,
)

ALL_PRESENT = dict.fromkeys(
    (s.slug for s in ALL_SECTIONS_FOR_PRESENCE), PRESENCE_PRESENT
)


def scan(
    path: str = "AGENTS.md",
    presence: str = SURFACE_PRESENT,
    mandatory: bool = True,
    sha256: str | None = "0123456789abcdef0123",
    headings: list[HeadingBlock] | None = None,
    section_presence: dict[str, str] | None = None,
) -> SurfaceScan:
    """Build a surface scan with only the fields a rendering test varies."""
    return SurfaceScan(
        descriptor=SurfaceDescriptor(path=path, role="canon", mandatory=mandatory),
        presence=presence,
        sha256=sha256,
        line_count=42,
        headings=headings if headings is not None else [],
        section_presence=(
            section_presence if section_presence is not None else dict(ALL_PRESENT)
        ),
        raw_content="",
    )


def render(
    scans: list[SurfaceScan] | None = None,
    coherence_map: dict[str, list[dict[str, str]]] | None = None,
    plan: list[PlanAction] | None = None,
    coarse_sha: str | None = "coarse-sha",
) -> str:
    """Render with a fixed timestamp so the output is byte-deterministic."""
    return render_markdown(
        scans if scans is not None else [scan()],
        coherence_map or {},
        plan or [],
        "inventory-sha",
        coarse_sha,
        "2026-01-15T00:00:00+00:00",
    )


# --- JSON envelope ----------------------------------------------------------


def test_serialise_scan_writes_the_kebab_case_contract_keys() -> None:
    """The dataclass field names are Python's; these are the contract's."""
    heading = HeadingBlock(level=2, text="Scope", line_start=3, line_end=9, body="x")

    payload = serialise_scan(scan(headings=[heading]))

    assert payload["line-count"] == 42
    assert payload["section-presence"] == ALL_PRESENT
    assert payload["headings"] == [
        {"level": 2, "text": "Scope", "line-start": 3, "line-end": 9}
    ]


def test_serialise_scan_drops_the_heading_body_and_the_raw_content() -> None:
    """The envelope carries structure, not the file it came from.

    Both fields exist on the scan so later passes can read them in memory;
    writing them out would balloon the document and duplicate the source.
    """
    heading = HeadingBlock(level=2, text="Scope", line_start=3, line_end=9, body="x")

    payload = serialise_scan(scan(headings=[heading]))

    assert "body" not in payload["headings"][0]
    assert "raw_content" not in payload
    assert "raw-content" not in payload


def test_emit_json_creates_its_own_output_directory(tmp_path: Path) -> None:
    """The output lands in generated state a clean checkout does not carry."""
    out = tmp_path / "nested" / "deeper" / "ai-surfaces.json"

    emit_json(out, [scan()], {}, [], "sha", None)

    assert out.exists()


def test_emit_json_bundles_the_catalog_alongside_the_scans(tmp_path: Path) -> None:
    """The document is self-describing: it carries the catalog it scanned by.

    A consumer reading the envelope a year later can tell which surfaces were
    candidates and which sections were canonical at the time, without having
    to find the matching version of this module.
    """
    out = tmp_path / "ai-surfaces.json"

    emit_json(out, [scan()], {}, [], "sha", None)
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["candidate-surfaces"]
    assert payload["canonical-sections"]
    assert payload["shared-sections-for-coherence"]
    assert {"slug", "display", "is-shared"} == set(payload["canonical-sections"][0])


def test_emit_json_summary_counts_presence_and_flags_mandatory_absences(
    tmp_path: Path,
) -> None:
    """``mandatory-absent`` is the actionable subset, not every absence.

    An optional surface that is absent is a choice; a mandatory one that is
    absent is a finding, and only the second belongs in the list a reader
    acts on.
    """
    out = tmp_path / "ai-surfaces.json"
    scans = [
        scan(path="AGENTS.md", presence=SURFACE_PRESENT, mandatory=True),
        scan(path="CLAUDE.md", presence=SURFACE_ABSENT, mandatory=True),
        scan(path=".cursorrules", presence=SURFACE_ABSENT, mandatory=False),
    ]

    emit_json(out, scans, {}, [], "sha", None)
    summary = json.loads(out.read_text(encoding="utf-8"))["summary"]

    assert summary["candidate-count"] == 3
    assert summary["present-count"] == 1
    assert summary["absent-count"] == 2
    assert summary["mandatory-absent"] == ["CLAUDE.md"]


def test_emit_json_records_a_null_coarse_sha_rather_than_omitting_it(
    tmp_path: Path,
) -> None:
    """The key is always present, so a consumer need not check for it."""
    out = tmp_path / "ai-surfaces.json"

    emit_json(out, [scan()], {}, [], "sha", None)
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["coarse-source-sha256"] is None


# --- markdown mirror: headers and presence ----------------------------------


def test_render_markdown_omits_the_coarse_sha_line_when_there_is_none() -> None:
    """Markdown drops the line entirely where the JSON writes a null.

    The two documents diverge deliberately: a null reads fine in a machine
    envelope and reads as noise in a document a person is scanning.
    """
    assert "Coarse-scan SHA-256" in render()
    assert "Coarse-scan SHA-256" not in render(coarse_sha=None)


def test_render_markdown_truncates_the_digest_and_dashes_an_absent_one() -> None:
    """Twelve characters is enough to match a digest by eye."""
    present = render(scans=[scan(sha256="0123456789abcdef0123")])
    absent = render(scans=[scan(presence=SURFACE_ABSENT, sha256=None)])

    assert "`0123456789ab…`" in present
    assert "| `—` |" in absent


def test_render_markdown_marks_mandatory_surfaces_in_the_presence_table() -> None:
    """The mandatory flag is bolded so a reader's eye catches it."""
    text = render(
        scans=[
            scan(path="AGENTS.md", mandatory=True),
            scan(path=".cursorrules", mandatory=False),
        ]
    )

    assert "| `AGENTS.md` | canon | **MUST** |" in text
    assert "| `.cursorrules` | canon | opt-in |" in text


# --- markdown mirror: section presence --------------------------------------


def test_render_markdown_fills_an_absent_surfaces_section_row_with_dashes() -> None:
    """An absent surface has no sections to report, and says so per cell.

    The row is emitted rather than skipped so the table's surface list stays
    aligned with the presence table above it.
    """
    text = render(scans=[scan(presence=SURFACE_ABSENT, section_presence={})])
    cells = " | ".join("—" for _ in ALL_SECTIONS_FOR_PRESENCE)

    assert f"| `AGENTS.md` | {cells} |" in text


def test_render_markdown_bolds_an_absent_section_but_not_a_present_one() -> None:
    """Absence is the finding, so absence is what gets the emphasis."""
    slugs = [s.slug for s in ALL_SECTIONS_FOR_PRESENCE]
    presence = dict(ALL_PRESENT)
    presence[slugs[0]] = PRESENCE_ABSENT

    text = render(scans=[scan(section_presence=presence)])

    assert "**absent**" in text


def test_render_markdown_truncates_a_long_renamed_target_at_24_chars() -> None:
    """A renamed heading is reported, but cannot widen the table unboundedly."""
    slugs = [s.slug for s in ALL_SECTIONS_FOR_PRESENCE]
    presence = dict(ALL_PRESENT)
    presence[slugs[0]] = PRESENCE_RENAMED_PREFIX + "A" * 60

    text = render(scans=[scan(section_presence=presence)])

    assert "renamed-to `" + "A" * 24 + "`" in text
    assert "A" * 25 not in text


# --- markdown mirror: heading inventory -------------------------------------


def test_render_markdown_lists_level_two_headings_only() -> None:
    """The inventory is a table of contents, not a full heading dump."""
    headings = [
        HeadingBlock(level=1, text="Title", line_start=1, line_end=2, body=""),
        HeadingBlock(level=2, text="Scope", line_start=3, line_end=9, body=""),
        HeadingBlock(level=3, text="Detail", line_start=10, line_end=12, body=""),
    ]

    text = render(scans=[scan(headings=headings)])

    assert "| 1 | Scope | 3-9 |" in text
    assert "Detail" not in text


def test_render_markdown_notes_a_surface_with_no_level_two_headings() -> None:
    """An empty inventory says why it is empty rather than showing a blank."""
    assert "_No level-two headings detected" in render(scans=[scan(headings=[])])


def test_render_markdown_skips_the_inventory_for_a_non_present_surface() -> None:
    """Only a present surface gets a heading section at all."""
    text = render(scans=[scan(presence=SURFACE_ABSENT)])

    assert "### `AGENTS.md`" not in text


# --- markdown mirror: coherence and plan ------------------------------------


def test_render_markdown_explains_an_empty_coherence_map() -> None:
    """The empty map is explained as structural, not reported as a failure."""
    assert "_No pairs of present surfaces" in render(coherence_map={})


def test_render_markdown_splits_a_pair_key_into_its_two_surfaces() -> None:
    """The map is keyed by a joined pair; the heading shows both sides."""
    text = render(
        coherence_map={
            "AGENTS.md__vs__CLAUDE.md": [
                {
                    "section_display": "Plans",
                    "verdict": COHERENCE_COHERENT,
                    "rationale": "both agree",
                }
            ]
        }
    )

    assert "### `AGENTS.md` ↔ `CLAUDE.md`" in text


def test_render_markdown_escapes_pipes_in_rationale_and_plan_detail() -> None:
    """Both free-text cells are escaped, so neither can split its row."""
    text = render(
        coherence_map={
            "a__vs__b": [
                {
                    "section_display": "Plans",
                    "verdict": COHERENCE_COHERENT,
                    "rationale": "a|b",
                }
            ]
        },
        plan=[
            PlanAction(
                surface="AGENTS.md",
                action="add",
                target_phase_hint="later",
                detail="c|d",
            )
        ],
    )

    assert "a\\|b" in text
    assert "c\\|d" in text


def test_render_markdown_states_when_no_authoring_actions_were_emitted() -> None:
    """An empty plan is a clean bill of health, and says so."""
    assert "_No authoring / refinement actions emitted" in render(plan=[])


# --- markdown mirror: reconciliation ----------------------------------------


def test_render_markdown_reports_no_contradictions_as_a_clean_result() -> None:
    """A coherent map produces the clean-result note, not an empty section."""
    text = render(
        coherence_map={
            "a__vs__b": [
                {
                    "section_display": "Plans",
                    "verdict": COHERENCE_COHERENT,
                    "rationale": "ok",
                }
            ]
        }
    )

    assert "_No candidate contradictions detected" in text


def test_render_markdown_names_agents_md_as_the_reconciliation_default() -> None:
    """A contradiction routes to the canonical voice, with an escape hatch.

    Naming the override marker in the same paragraph is what keeps the
    default from reading as an absolute: a surface may diverge, but only
    with a marker pointing at a recorded decision.
    """
    text = render(
        coherence_map={
            "a__vs__b": [
                {
                    "section_display": "Plans",
                    "verdict": COHERENCE_CONTRADICTS,
                    "rationale": "they differ",
                }
            ]
        }
    )

    assert "`AGENTS.md` is the canonical project voice" in text
    assert "coherence-override:" in text
    assert "| Plans | (see plan) |" in text
