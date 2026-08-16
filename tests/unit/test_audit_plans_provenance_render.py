# SPDX-License-Identifier: MIT

"""Characterization coverage for the provenance rendering tail.

Two emitters turn the resolved records into documents: a JSON envelope that
downstream passes read, and a markdown mirror a human reads. Both were dark —
about a third of the builder's body, executing only when the CLI ran end to
end, which the suite never did.

Rendering code is where silent breakage hides, because a malformed document
still *is* a document. The tests below therefore assert on structure the
consumers actually depend on — the kebab-case key names in the JSON contract,
the table escaping in the markdown — rather than on the prose around it.

The timestamps both emitters stamp are deliberately never asserted: they come
from the wall clock, and a test that pinned them would pin the clock.
"""

from __future__ import annotations

import json
from pathlib import Path

from apothem.audit.plans_provenance_model import (
    ProvenanceRecord,
    Signals,
    SuiteVerdict,
)
from apothem.audit.plans_provenance_render import (
    emit_json,
    emit_markdown,
    record_to_dict,
)
from apothem.audit.plans_provenance_vocabulary import (
    ALL_CONFIDENCES,
    CONFIDENCE_HIGH,
    CONFIDENCE_RECURSIVE_SELF,
    CONFIDENCE_UNMAPPABLE,
)


def record(
    path: str = ".plans/s/f.md",
    suite: str = "s",
    confidence: str = CONFIDENCE_HIGH,
    proposed: str = "2026-01-15--f.md",
) -> ProvenanceRecord:
    """Build a record with only the fields a rendering test varies."""
    return ProvenanceRecord(
        path=path,
        suite=suite,
        mtime="2026-01-15T00:00:00",
        sha256="abc123",
        line_count=10,
        frontmatter_project=None,
        signals=Signals(),
        inferred_destination="dc-kit",
        confidence=confidence,
        proposed_destination_filename=proposed,
        notes=[],
    )


def verdict(
    suite: str = "s",
    confidence: str = CONFIDENCE_HIGH,
    destination: str = "dc-kit",
    rationale: list[str] | None = None,
) -> SuiteVerdict:
    """Build a suite verdict with only the fields a rendering test varies."""
    return SuiteVerdict(
        suite=suite,
        file_count=1,
        destination=destination,
        confidence=confidence,
        rationale=rationale if rationale is not None else ["because"],
        aggregate_repo_urls=[],
        aggregate_abs_paths=[],
        eco_signal_density=0.0,
    )


# --- JSON envelope ----------------------------------------------------------


def test_emit_json_creates_its_own_output_directory(tmp_path: Path) -> None:
    """The emitter makes the parent tree rather than requiring one.

    The output lands under ``.audit/``, which is generated state and may not
    exist on a clean checkout.
    """
    out = tmp_path / "nested" / "deeper" / "provenance.json"

    emit_json([record()], {"s": verdict()}, "sha", out)

    assert out.exists()


def test_emit_json_writes_the_kebab_case_contract_keys(tmp_path: Path) -> None:
    """Downstream passes read these key names; they are the contract."""
    out = tmp_path / "provenance.json"

    emit_json([record()], {"s": verdict()}, "inventory-sha", out)
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["scanner"] == "build_plans_provenance"
    assert payload["inventory-source-sha256"] == "inventory-sha"
    assert payload["suite-count"] == 1
    assert payload["file-count"] == 1
    assert payload["suites"]["s"]["file-count"] == 1
    assert payload["suites"]["s"]["aggregate-repo-urls"] == []
    assert payload["files"][0]["proposed-destination-filename"] == "2026-01-15--f.md"


def test_emit_json_counts_every_confidence_tier_including_the_empty_ones(
    tmp_path: Path,
) -> None:
    """The tally carries a zero for each unused tier rather than omitting it.

    A consumer can index every tier without a presence check, which is why
    the counter is seeded from the full vocabulary instead of the records.
    """
    out = tmp_path / "provenance.json"

    emit_json([record()], {"s": verdict()}, "sha", out)
    tally = json.loads(out.read_text(encoding="utf-8"))["by-confidence"]

    assert set(tally) == set(ALL_CONFIDENCES)
    assert tally[CONFIDENCE_HIGH] == 1
    assert tally[CONFIDENCE_UNMAPPABLE] == 0


def test_emit_json_rounds_the_density_to_three_places(tmp_path: Path) -> None:
    """The density is a derived ratio; full float precision is noise."""
    out = tmp_path / "provenance.json"
    dense = verdict()
    dense.eco_signal_density = 1 / 3

    emit_json([record()], {"s": dense}, "sha", out)
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["suites"]["s"]["eco-signal-density"] == 0.333


def test_emit_json_orders_suites_deterministically(tmp_path: Path) -> None:
    """Suites are sorted, so the output diffs cleanly between runs."""
    out = tmp_path / "provenance.json"
    verdicts = {
        "zeta": verdict(suite="zeta"),
        "alpha": verdict(suite="alpha"),
    }

    emit_json([], verdicts, "sha", out)
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert list(payload["suites"]) == ["alpha", "zeta"]


def test_record_to_dict_renames_fields_to_the_json_envelope_keys() -> None:
    """Python's snake_case becomes the kebab-case the JSON contract uses.

    This rename is the whole reason the function exists: the dataclass field
    names are Python's, and the envelope's are the contract's.
    """
    payload = record_to_dict(record())

    assert payload["line-count"] == 10
    assert payload["frontmatter-project"] is None
    assert payload["proposed-destination-filename"] == "2026-01-15--f.md"
    assert payload["signals"]["eco_path_hits"] == 0


# --- markdown mirror --------------------------------------------------------


def test_emit_markdown_creates_its_own_output_directory(tmp_path: Path) -> None:
    """Same as the JSON emitter: the parent tree is generated state."""
    out = tmp_path / "nested" / "provenance.md"

    emit_markdown([record()], {"s": verdict()}, out)

    assert out.exists()


def test_emit_markdown_escapes_pipes_in_every_table_cell(tmp_path: Path) -> None:
    """A pipe in a value must not split the markdown table row."""
    out = tmp_path / "provenance.md"
    piped = record(path=".plans/s/a|b.md", proposed="2026-01-15--a|b.md")

    emit_markdown([piped], {"s": verdict(destination="dc|kit")}, out)
    text = out.read_text(encoding="utf-8")

    assert "dc\\|kit" in text
    assert "`.plans/s/a\\|b.md`" in text
    assert "`2026-01-15--a\\|b.md`" in text


def test_emit_markdown_does_not_escape_pipes_in_rationale_fragments(
    tmp_path: Path,
) -> None:
    """Rationale is emitted as a bullet list, so it is not escaped.

    Pinned as current, not endorsed. The four table cells are escaped and
    this one field is not; it is safe only because rationale text happens to
    be authored in this module and never contains a pipe. A rationale
    fragment that quoted a user-supplied value would render unescaped.
    """
    out = tmp_path / "provenance.md"

    emit_markdown([record()], {"s": verdict(rationale=["a|b"])}, out)

    assert "- a|b" in out.read_text(encoding="utf-8")


def test_emit_markdown_files_a_suiteless_record_under_a_root_bucket(
    tmp_path: Path,
) -> None:
    """A record with no suite is bucketed as ``<root>`` rather than dropped.

    No verdict can match that bucket — the verdict map is keyed by real suite
    names — so the section renders its file table with no confidence line
    above it. Pinned as current: the record stays visible, which is the point.
    """
    out = tmp_path / "provenance.md"

    emit_markdown([record(suite="")], {}, out)
    text = out.read_text(encoding="utf-8")

    assert "### `<root>`" in text
    assert "_Confidence:" not in text


def test_emit_markdown_annotates_only_the_first_recursive_suite(
    tmp_path: Path,
) -> None:
    """With two recursive suites the annotation names one of them.

    Pinned as current, not endorsed. The recursive case is meant to be a
    single suite by design, so the second would itself be the defect — but
    the renderer would not say so, it would silently describe only one.
    """
    out = tmp_path / "provenance.md"
    verdicts = {
        "alpha": verdict(suite="alpha", confidence=CONFIDENCE_RECURSIVE_SELF),
        "beta": verdict(suite="beta", confidence=CONFIDENCE_RECURSIVE_SELF),
    }

    emit_markdown([], verdicts, out)
    text = out.read_text(encoding="utf-8")

    assert ("The suite `alpha`" in text) != ("The suite `beta`" in text)


def test_emit_markdown_states_the_absence_of_recursive_and_orphan_cases(
    tmp_path: Path,
) -> None:
    """Empty sections say so rather than rendering as blank headings."""
    out = tmp_path / "provenance.md"

    emit_markdown([record()], {"s": verdict()}, out)
    text = out.read_text(encoding="utf-8")

    assert "_No recursive-self records._" in text
    assert "_No orphan candidates surfaced._" in text


def test_emit_markdown_lists_unmappable_records_as_orphan_candidates(
    tmp_path: Path,
) -> None:
    """Unmappable files are named individually for operator disposition."""
    out = tmp_path / "provenance.md"
    orphan = record(path=".plans/s/lost.md", confidence=CONFIDENCE_UNMAPPABLE)

    emit_markdown([orphan], {"s": verdict(confidence=CONFIDENCE_UNMAPPABLE)}, out)
    text = out.read_text(encoding="utf-8")

    assert "1 file(s) with `confidence: unmappable`." in text
    assert "- `.plans/s/lost.md`" in text


def test_emit_markdown_sorts_suites_and_the_files_within_them(
    tmp_path: Path,
) -> None:
    """Both levels are ordered, so the document diffs cleanly between runs."""
    out = tmp_path / "provenance.md"
    records = [
        record(path=".plans/zeta/b.md", suite="zeta"),
        record(path=".plans/alpha/z.md", suite="alpha"),
        record(path=".plans/alpha/a.md", suite="alpha"),
    ]

    emit_markdown(records, {}, out)
    text = out.read_text(encoding="utf-8")

    assert text.index("### `alpha`") < text.index("### `zeta`")
    assert text.index(".plans/alpha/a.md") < text.index(".plans/alpha/z.md")
