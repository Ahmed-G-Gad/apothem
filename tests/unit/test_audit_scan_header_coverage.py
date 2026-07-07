# SPDX-License-Identifier: MIT

"""Unit tests for the authorship-header coverage scanner.

``apothem.audit.scan_header_coverage`` reads an ``inventory.json`` snapshot,
classifies every listed file against the canonical SPDX header for its comment
family, honours the exception-glob fixture, and emits per-file coverage rows
plus aggregate counts (``header-coverage.json`` and ``header-coverage.md``). The
variant resolution, exception matching, head reading, banner scan, injection
plan, and serialisation are pure transforms over paths and on-disk bytes, so
they are covered directly; ``scan_inventory`` and ``main`` run end-to-end against
a fixture tree paired with an inventory in ``tmp_path``.

Contract note: the scanner is a *reporting* pipeline stage, not a gate. ``main``
returns ``EXIT_OK`` whether or not coverage gaps exist; it returns ``EXIT_ERROR``
only when the inventory snapshot is absent. The gap-vs-clean distinction lives in
the emitted summary, not the exit code — the tests lock that real contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.audit.scan_header_coverage import (
    BOM_PREFIX,
    EXIT_ERROR,
    EXIT_OK,
    HEADER_ABSENT,
    HEADER_NOT_APPLICABLE,
    HEADER_PRESENT_CANONICAL,
    HEADER_PRESENT_MALFORMED,
    LEGACY_AUTHOR_MARK,
    MALFORM_BOM_PREFIX,
    MALFORM_MIXED,
    MALFORM_SMART_QUOTE,
    MALFORM_TRAILING_WHITESPACE,
    MALFORM_WRONG_LINE_COUNT,
    MALFORM_WRONG_VARIANT,
    VARIANT_C_BLOCK,
    VARIANT_DOUBLE_DASH,
    VARIANT_DOUBLE_SLASH,
    VARIANT_EXEMPT,
    VARIANT_HASH,
    VARIANT_HTML,
    VARIANT_SEMICOLON,
    CoverageSummary,
    FileCoverage,
    build_injection_plan,
    canonical_banner_lines,
    canonical_banner_text,
    has_shebang,
    insertion_line,
    load_exception_globs,
    main,
    matches_exception,
    parse_args,
    read_head,
    render_markdown,
    resolve_path,
    scan_for_banner,
    scan_inventory,
    variant_family_for,
)

# The canonical one-line header for each comment family is sourced from the
# scanner's own renderer so the fixtures stay byte-exact against whatever the
# shipped authorship-header fixture says — never a hard-coded duplicate.
_HASH_LINE = canonical_banner_lines(VARIANT_HASH)[0]
_SLASH_LINE = canonical_banner_lines(VARIANT_DOUBLE_SLASH)[0]


def _canonical_file(variant: str, body: str = "body\n") -> str:
    """Render a file whose head carries the canonical banner block."""
    # canonical_banner_text == "<line>\n"; the extra "\n" supplies the
    # mandatory trailing blank that completes the canonical block.
    return canonical_banner_text(variant) + "\n" + body


def _make_tree(root: Path, files: dict[str, str]) -> Path:
    """Write ``files`` under ``root`` and emit an inventory listing them.

    Returns the inventory path. Insertion order of ``files`` is preserved in
    the inventory's ``files`` array.
    """
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    inventory = root / ".audit" / "inventory.json"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(
        json.dumps({"files": [{"path": rel} for rel in files]}),
        encoding="utf-8",
    )
    return inventory


class TestVariantFamilyFor:
    def test_suffix_resolves_to_its_comment_family(self) -> None:
        assert variant_family_for(Path("a.py")) == VARIANT_HASH
        assert variant_family_for(Path("a.md")) == VARIANT_HTML
        assert variant_family_for(Path("a.ts")) == VARIANT_DOUBLE_SLASH
        assert variant_family_for(Path("a.css")) == VARIANT_C_BLOCK
        assert variant_family_for(Path("a.ini")) == VARIANT_SEMICOLON
        assert variant_family_for(Path("a.sql")) == VARIANT_DOUBLE_DASH

    def test_basename_override_resolves_suffixless_files(self) -> None:
        assert variant_family_for(Path("Makefile")) == VARIANT_HASH
        assert variant_family_for(Path("nested/Dockerfile")) == VARIANT_HASH

    def test_unknown_extension_falls_through_to_exempt(self) -> None:
        assert variant_family_for(Path("data.xyz")) == VARIANT_EXEMPT
        assert variant_family_for(Path("mystery")) == VARIANT_EXEMPT


class TestLoadExceptionGlobs:
    def test_strips_comments_and_blank_lines(self, tmp_path: Path) -> None:
        fixture = tmp_path / "exc.txt"
        fixture.write_text(
            "# comment\n\nvendored/**\nLICENSE\n   # indented comment\n",
            encoding="utf-8",
        )
        assert load_exception_globs(fixture) == ["vendored/**", "LICENSE"]

    def test_missing_fixture_returns_empty(self, tmp_path: Path) -> None:
        assert load_exception_globs(tmp_path / "absent.txt") == []


class TestMatchesException:
    def test_exact_literal_match(self) -> None:
        assert matches_exception("LICENSE", ["LICENSE"]) == "LICENSE"

    def test_globstar_crosses_path_segments(self) -> None:
        globs = ["**/*.json", "dist/**"]
        assert matches_exception("a/b/c.json", globs) == "**/*.json"
        assert matches_exception("top.json", globs) == "**/*.json"
        assert matches_exception("dist/sub/bundle.bin", globs) == "dist/**"

    def test_returns_first_match_in_order(self) -> None:
        # Both patterns match; first-match semantics return the earlier one.
        globs = ["dist/**", "dist/sub/*.bin"]
        assert matches_exception("dist/sub/x.bin", globs) == "dist/**"

    def test_no_match_returns_none(self) -> None:
        assert matches_exception("src/a.py", ["dist/**", "LICENSE"]) is None

    def test_backslash_paths_are_normalised(self) -> None:
        assert matches_exception("dist\\sub\\f.bin", ["dist/**"]) == "dist/**"


class TestReadHead:
    def test_returns_lines_without_terminators(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_text("one\ntwo\nthree\n", encoding="utf-8")
        assert read_head(f) == ["one", "two", "three"]

    def test_honours_the_line_budget(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("".join(f"line{i}\n" for i in range(100)), encoding="utf-8")
        head = read_head(f, line_budget=5)
        assert head == ["line0", "line1", "line2", "line3", "line4"]

    def test_unreadable_path_returns_empty(self, tmp_path: Path) -> None:
        # Opening a directory as a file raises OSError -> empty head.
        assert read_head(tmp_path) == []


class TestHasShebang:
    def test_detects_leading_shebang(self) -> None:
        assert has_shebang(["#!/usr/bin/env bash", "x"]) is True

    def test_no_shebang_and_empty_head(self) -> None:
        assert has_shebang(["x = 1"]) is False
        assert has_shebang([]) is False


class TestInsertionLine:
    def test_shebang_pushes_banner_to_line_two(self) -> None:
        assert insertion_line(["#!/bin/sh", "x"]) == 2

    def test_no_shebang_inserts_at_line_one(self) -> None:
        assert insertion_line(["x = 1"]) == 1
        assert insertion_line([]) == 1


class TestScanForBanner:
    def test_byte_exact_block_is_present_canonical(self) -> None:
        head = [_HASH_LINE, "", "x = 1"]
        status, rng, malform, detail = scan_for_banner(head, VARIANT_HASH)
        assert status == HEADER_PRESENT_CANONICAL
        assert rng == (1, 1)
        assert malform is None
        assert detail is None

    def test_canonical_after_shebang_reports_line_two(self) -> None:
        head = ["#!/usr/bin/env python3", _HASH_LINE, "", "x = 1"]
        status, rng, _malform, _detail = scan_for_banner(head, VARIANT_HASH)
        assert status == HEADER_PRESENT_CANONICAL
        assert rng == (2, 2)

    def test_no_marker_is_absent(self) -> None:
        status, rng, _malform, _detail = scan_for_banner(["x = 1"], VARIANT_HASH)
        assert status == HEADER_ABSENT
        assert rng is None

    def test_empty_head_is_absent(self) -> None:
        assert scan_for_banner([], VARIANT_HASH)[0] == HEADER_ABSENT

    def test_trailing_whitespace_is_malformed(self) -> None:
        head = [_HASH_LINE + "  ", "", "x = 1"]
        status, _rng, malform, _detail = scan_for_banner(head, VARIANT_HASH)
        assert status == HEADER_PRESENT_MALFORMED
        assert malform == MALFORM_TRAILING_WHITESPACE

    def test_wrong_comment_marker_is_malformed_wrong_variant(self) -> None:
        # A double-slash SPDX line in a hash-family file is the wrong variant.
        head = [_SLASH_LINE, "", "x = 1"]
        status, _rng, malform, detail = scan_for_banner(head, VARIANT_HASH)
        assert status == HEADER_PRESENT_MALFORMED
        assert malform == MALFORM_WRONG_VARIANT
        assert detail is not None

    def test_missing_html_wrapper_is_wrong_variant(self) -> None:
        # A hash-style SPDX line in a Markdown (html) file lacks the wrapper.
        head = [_HASH_LINE, "", "text"]
        status, _rng, malform, _detail = scan_for_banner(head, VARIANT_HTML)
        assert status == HEADER_PRESENT_MALFORMED
        assert malform == MALFORM_WRONG_VARIANT

    def test_leading_bom_alone_is_malformed_bom_prefix(self) -> None:
        # A BOM before non-header content is itself a malformation: it is the
        # sole detection, so it does not collapse to `mixed`.
        head = [BOM_PREFIX + "random first line", "more"]
        status, _rng, malform, _detail = scan_for_banner(head, VARIANT_HASH)
        assert status == HEADER_PRESENT_MALFORMED
        assert malform == MALFORM_BOM_PREFIX

    def test_multiple_defects_collapse_to_mixed(self) -> None:
        # A BOM in front of an otherwise-canonical hash line trips both
        # bom-prefix AND wrong-variant (the `#` is no longer at the edge),
        # so the two detections collapse to `mixed`.
        head = [BOM_PREFIX + _HASH_LINE, "", "x = 1"]
        status, _rng, malform, detail = scan_for_banner(head, VARIANT_HASH)
        assert status == HEADER_PRESENT_MALFORMED
        assert malform == MALFORM_MIXED
        # The collapsed detail enumerates both contributing classes.
        assert detail is not None
        assert MALFORM_BOM_PREFIX in detail
        assert MALFORM_WRONG_VARIANT in detail

    def test_smart_quote_in_header_is_malformed(self) -> None:
        # A curly apostrophe (U+2019) on an otherwise-correct hash line.
        # Built via chr() so the test's own source bytes stay ASCII-clean.
        head = [_HASH_LINE + chr(0x2019), "", "x = 1"]
        status, _rng, malform, _detail = scan_for_banner(head, VARIANT_HASH)
        assert status == HEADER_PRESENT_MALFORMED
        assert malform == MALFORM_SMART_QUOTE

    def test_shebang_only_file_is_absent(self) -> None:
        # The insertion site (line 2) is past the end of a shebang-only file,
        # so the short-file guard reports the header absent.
        assert scan_for_banner(["#!/usr/bin/env bash"], VARIANT_HASH)[0] == (
            HEADER_ABSENT
        )

    def test_canonical_line_without_trailing_blank_is_wrong_line_count(self) -> None:
        # The SPDX line is present and correct, but content follows it with no
        # mandatory trailing blank — the generic wrong-line-count fall-through.
        head = [_HASH_LINE, "x = 1"]
        status, _rng, malform, _detail = scan_for_banner(head, VARIANT_HASH)
        assert status == HEADER_PRESENT_MALFORMED
        assert malform == MALFORM_WRONG_LINE_COUNT

    def test_retired_legacy_banner_is_wrong_line_count(self) -> None:
        # The retired branded-banner author line (no narrowed SPDX line) is a
        # not-yet-narrowed header — the legacy fall-through branch.
        head = [f"# {LEGACY_AUTHOR_MARK}", "", "x = 1"]
        status, _rng, malform, detail = scan_for_banner(head, VARIANT_HASH)
        assert status == HEADER_PRESENT_MALFORMED
        assert malform == MALFORM_WRONG_LINE_COUNT
        assert detail is not None
        assert "branded-banner" in detail


class TestBuildInjectionPlan:
    def test_canonical_needs_no_plan(self) -> None:
        plan = build_injection_plan(
            "a.py",
            [_HASH_LINE, "", "x"],
            HEADER_PRESENT_CANONICAL,
            VARIANT_HASH,
            (1, 1),
        )
        assert plan is None

    def test_not_applicable_needs_no_plan(self) -> None:
        assert (
            build_injection_plan("x", [], HEADER_NOT_APPLICABLE, VARIANT_HASH, None)
            is None
        )

    def test_exempt_variant_needs_no_plan(self) -> None:
        assert (
            build_injection_plan("x.bin", ["data"], HEADER_ABSENT, VARIANT_EXEMPT, None)
            is None
        )

    def test_absent_plans_an_insert(self) -> None:
        plan = build_injection_plan(
            "a.py", ["x = 1"], HEADER_ABSENT, VARIANT_HASH, None
        )
        assert plan is not None
        assert plan["needed"] is True
        assert plan["action"] == "insert"
        assert plan["insertion-line"] == 1
        assert _HASH_LINE in str(plan["diff"])

    def test_malformed_plans_a_replace(self) -> None:
        plan = build_injection_plan(
            "a.py",
            [_SLASH_LINE, "", "x"],
            HEADER_PRESENT_MALFORMED,
            VARIANT_HASH,
            (1, 1),
        )
        assert plan is not None
        assert plan["action"] == "replace"
        assert plan["replacement-lines"] == [1, 1]

    def test_malformed_without_range_returns_none(self) -> None:
        plan = build_injection_plan(
            "a.py", ["x"], HEADER_PRESENT_MALFORMED, VARIANT_HASH, None
        )
        assert plan is None

    def test_absent_empty_file_plans_an_insert(self) -> None:
        # The empty-head branch overrides after_lines to the canonical block.
        plan = build_injection_plan("empty.py", [], HEADER_ABSENT, VARIANT_HASH, None)
        assert plan is not None
        assert plan["action"] == "insert"
        assert _HASH_LINE in str(plan["diff"])

    def test_absent_after_shebang_inserts_at_line_two(self) -> None:
        # A shebang is preserved at line 1; the banner is inserted below it.
        plan = build_injection_plan(
            "run.sh",
            ["#!/usr/bin/env bash", "echo hi"],
            HEADER_ABSENT,
            VARIANT_HASH,
            None,
        )
        assert plan is not None
        assert plan["action"] == "insert"
        assert plan["insertion-line"] == 2
        assert _HASH_LINE in str(plan["diff"])


class TestScanInventory:
    def test_all_canonical_tree_reports_full_coverage(self, tmp_path: Path) -> None:
        inventory = _make_tree(
            tmp_path,
            {
                "a.py": _canonical_file(VARIANT_HASH),
                "docs/b.md": _canonical_file(VARIANT_HTML),
            },
        )
        rows, summary, _prov = scan_inventory(
            inventory, tmp_path / "noexc.txt", tmp_path
        )

        assert summary.applicable_total == 2
        assert summary.present_canonical == 2
        assert summary.absent == 0
        assert summary.present_malformed == 0
        assert summary.coverage_pct == 100.0
        assert all(r.header_status == HEADER_PRESENT_CANONICAL for r in rows)

    def test_absent_header_is_reported_with_its_path(self, tmp_path: Path) -> None:
        inventory = _make_tree(
            tmp_path,
            {"good.py": _canonical_file(VARIANT_HASH), "bad.py": "x = 1\n"},
        )
        rows, summary, _prov = scan_inventory(
            inventory, tmp_path / "noexc.txt", tmp_path
        )

        assert summary.present_canonical == 1
        assert summary.absent == 1
        bad = next(r for r in rows if r.path == "bad.py")
        assert bad.applicable is True
        assert bad.header_status == HEADER_ABSENT
        # The gap carries an injection plan so the downstream injector can act.
        assert bad.injection_plan is not None

    def test_malformed_header_is_classified(self, tmp_path: Path) -> None:
        inventory = _make_tree(tmp_path, {"weird.py": f"{_SLASH_LINE}\n\nx = 1\n"})
        rows, summary, _prov = scan_inventory(
            inventory, tmp_path / "noexc.txt", tmp_path
        )

        assert summary.present_malformed == 1
        assert summary.by_malformation_class[MALFORM_WRONG_VARIANT] == 1
        row = rows[0]
        assert row.header_status == HEADER_PRESENT_MALFORMED
        assert row.malformation_class == MALFORM_WRONG_VARIANT

    def test_exception_fixture_and_unknown_suffix_are_not_applicable(
        self, tmp_path: Path
    ) -> None:
        fixture = tmp_path / "exc.txt"
        fixture.write_text("# comment\nvendored/**\nLICENSE\n", encoding="utf-8")
        inventory = _make_tree(
            tmp_path,
            {
                "src.py": _canonical_file(VARIANT_HASH),
                "vendored/lib.py": "no header\n",  # fixture match -> exempt
                "data.xyz": "unknown ext\n",  # unknown suffix -> exempt
            },
        )
        rows, summary, prov = scan_inventory(inventory, fixture, tmp_path)
        by_path = {r.path: r for r in rows}

        # Fixture-matched exemption carries the matching glob as its class.
        vendored = by_path["vendored/lib.py"]
        assert vendored.applicable is False
        assert vendored.header_status == HEADER_NOT_APPLICABLE
        assert vendored.exception_class == "vendored/**"

        # Unknown-suffix exemption is labelled unsupported-extension.
        unknown = by_path["data.xyz"]
        assert unknown.applicable is False
        assert unknown.variant_family == VARIANT_EXEMPT
        assert unknown.exception_class == "unsupported-extension"

        # Only the in-scope file is scanned for coverage.
        assert by_path["src.py"].applicable is True
        assert by_path["src.py"].header_status == HEADER_PRESENT_CANONICAL
        assert summary.applicable_total == 1
        assert summary.not_applicable == 2
        # Provenance records both source SHAs.
        assert prov["inventory-sha256"]
        assert prov["exception-fixture-sha256"]

    def test_blank_path_records_are_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text(_canonical_file(VARIANT_HASH), encoding="utf-8")
        inventory = tmp_path / "inv.json"
        inventory.write_text(
            json.dumps({"files": [{"path": ""}, {"path": "a.py"}]}),
            encoding="utf-8",
        )
        rows, summary, _prov = scan_inventory(
            inventory, tmp_path / "noexc.txt", tmp_path
        )

        # Both records are counted in the total, but the blank path is skipped.
        assert summary.total_files == 2
        assert len(rows) == 1
        assert rows[0].path == "a.py"

    def test_malformations_bucket_into_distinct_classes(self, tmp_path: Path) -> None:
        # Two files with different malformations must tally into separate
        # by_malformation_class buckets, not collapse into one.
        inventory = _make_tree(
            tmp_path,
            {
                "variant.py": f"{_SLASH_LINE}\n\nx = 1\n",  # wrong-variant
                "space.py": f"{_HASH_LINE}  \n\nx = 1\n",  # trailing-whitespace
            },
        )
        _rows, summary, _prov = scan_inventory(
            inventory, tmp_path / "noexc.txt", tmp_path
        )

        assert summary.present_malformed == 2
        assert summary.by_malformation_class[MALFORM_WRONG_VARIANT] == 1
        assert summary.by_malformation_class[MALFORM_TRAILING_WHITESPACE] == 1


class TestRenderMarkdown:
    def test_renders_each_status_section(self) -> None:
        rows = [
            FileCoverage(
                "good.py",
                True,
                None,
                HEADER_PRESENT_CANONICAL,
                VARIANT_HASH,
                (1, 1),
                None,
                None,
                None,
            ),
            FileCoverage(
                "weird.py",
                True,
                None,
                HEADER_PRESENT_MALFORMED,
                VARIANT_HASH,
                (1, 1),
                MALFORM_WRONG_VARIANT,
                "uses '//' marker",
                {"needed": True, "action": "replace", "diff": "--- a\n+++ b\n"},
            ),
            FileCoverage(
                "bad.py",
                True,
                None,
                HEADER_ABSENT,
                VARIANT_HASH,
                None,
                None,
                None,
                {"needed": True, "action": "insert", "insertion-line": 1, "diff": "+x"},
            ),
        ]
        summary = CoverageSummary(
            total_files=3,
            applicable_total=3,
            present_canonical=1,
            present_malformed=1,
            absent=1,
            coverage_pct=33.33,
        )
        prov = {
            "inventory-source": "inv.json",
            "inventory-sha256": "abc",
            "exception-fixture-source": "exc.txt",
            "exception-fixture-sha256": "def",
        }

        md = render_markdown(rows, summary, prov, "2026-06-23T00:00:00+00:00")

        assert "# Authorship-Header Coverage Map" in md
        assert "## Aggregate Statistics" in md
        assert "33.33%" in md
        assert "Files with Canonical Banner (1)" in md
        assert "Files with Malformed Banner (1)" in md
        assert "Files Missing the Banner (1)" in md
        assert "good.py" in md
        assert "weird.py" in md
        assert "bad.py" in md
        assert "wrong-variant" in md
        # Malformed/absent rows with injection plans drive the sample-diff
        # section and its fenced ```diff blocks.
        assert "## Sample Injection-Plan Diffs" in md
        assert "```diff" in md

    def test_renders_not_applicable_section(self) -> None:
        rows = [
            FileCoverage(
                "vendored/lib.py",
                False,
                "vendored/**",
                HEADER_NOT_APPLICABLE,
                VARIANT_HASH,
                None,
                None,
                None,
                None,
            ),
            FileCoverage(
                "data.xyz",
                False,
                "unsupported-extension",
                HEADER_NOT_APPLICABLE,
                VARIANT_EXEMPT,
                None,
                None,
                None,
                None,
            ),
        ]
        summary = CoverageSummary(total_files=2, not_applicable=2)
        prov = {
            "inventory-source": "inv.json",
            "inventory-sha256": "abc",
            "exception-fixture-source": "exc.txt",
            "exception-fixture-sha256": "def",
        }

        md = render_markdown(rows, summary, prov, "2026-06-23T00:00:00+00:00")

        assert "Files Marked Not Applicable (2)" in md
        # The exception-class breakdown tallies each class.
        assert "vendored/**" in md
        assert "unsupported-extension" in md


class TestFileCoverageToJson:
    def test_uses_hyphenated_keys_and_lists_the_range(self) -> None:
        record = FileCoverage(
            path="a.py",
            applicable=True,
            exception_class=None,
            header_status=HEADER_ABSENT,
            variant_family=VARIANT_HASH,
            header_line_range=(1, 1),
            malformation_class=None,
            malformation_detail=None,
            injection_plan=None,
        )
        doc = record.to_json()
        assert doc["header-status"] == HEADER_ABSENT
        assert doc["variant-family"] == VARIANT_HASH
        assert doc["header-line-range"] == [1, 1]
        assert doc["exception-class"] is None

    def test_none_range_serialises_to_null(self) -> None:
        record = FileCoverage(
            "a.py", True, None, HEADER_ABSENT, VARIANT_HASH, None, None, None, None
        )
        assert record.to_json()["header-line-range"] is None


class TestCoverageSummaryToJson:
    def test_emits_hyphenated_keys_and_rounds_coverage(self) -> None:
        summary = CoverageSummary(
            total_files=3,
            applicable_total=2,
            present_canonical=1,
            present_malformed=1,
            absent=0,
            not_applicable=1,
            coverage_pct=49.999,
        )
        doc = summary.to_json()
        assert doc["total-files"] == 3
        assert doc["applicable-total"] == 2
        assert doc["present-canonical"] == 1
        assert doc["coverage-pct"] == 50.0
        assert doc["by-variant-family"] == {}


class TestCanonicalBanner:
    def test_lines_and_text_render_the_spdx_marker(self) -> None:
        lines = canonical_banner_lines(VARIANT_HASH)
        assert len(lines) == 1
        assert "SPDX-License-Identifier" in lines[0]
        assert canonical_banner_text(VARIANT_HTML).startswith("<!--")
        assert canonical_banner_text(VARIANT_HASH).endswith("\n")

    def test_exempt_variant_is_not_renderable(self) -> None:
        with pytest.raises(ValueError, match="not renderable"):
            canonical_banner_lines(VARIANT_EXEMPT)


class TestResolvePath:
    def test_relative_resolves_against_root(self, tmp_path: Path) -> None:
        assert resolve_path(tmp_path, Path("a/b.json")) == tmp_path / "a/b.json"

    def test_absolute_passes_through(self, tmp_path: Path) -> None:
        absolute = tmp_path / "abs.json"
        assert resolve_path(tmp_path, absolute) == absolute


class TestParseArgs:
    def test_defaults(self) -> None:
        args = parse_args([])
        assert args.root == Path.cwd()
        assert args.inventory == Path(".audit/inventory.json")
        assert args.exception_fixture == Path(
            "src/apothem/schemas/header-exceptions.txt"
        )
        assert args.out_json == Path(".audit/header-coverage.json")
        assert args.out_md == Path(".audit/header-coverage.md")

    def test_overrides(self) -> None:
        args = parse_args(
            [
                "--root",
                "r",
                "--inventory",
                "i.json",
                "--exception-fixture",
                "e.txt",
                "--out-json",
                "o.json",
                "--out-md",
                "o.md",
            ]
        )
        assert args.root == Path("r")
        assert args.inventory == Path("i.json")
        assert args.exception_fixture == Path("e.txt")
        assert args.out_json == Path("o.json")
        assert args.out_md == Path("o.md")


class TestMain:
    def test_missing_inventory_returns_error(self, tmp_path: Path) -> None:
        code = main(["--root", str(tmp_path), "--inventory", ".audit/none.json"])
        assert code == EXIT_ERROR

    def test_clean_tree_writes_outputs_and_returns_ok(self, tmp_path: Path) -> None:
        _make_tree(tmp_path, {"a.py": _canonical_file(VARIANT_HASH)})

        code = main(
            [
                "--root",
                str(tmp_path),
                "--inventory",
                ".audit/inventory.json",
                "--exception-fixture",
                "noexc.txt",
                "--out-json",
                ".audit/header-coverage.json",
                "--out-md",
                ".audit/header-coverage.md",
            ]
        )

        assert code == EXIT_OK
        out_json = tmp_path / ".audit" / "header-coverage.json"
        out_md = tmp_path / ".audit" / "header-coverage.md"
        assert out_json.is_file()
        assert out_md.is_file()
        payload = json.loads(out_json.read_text(encoding="utf-8"))
        assert payload["scanner"] == "scan_header_coverage"
        assert payload["summary"]["coverage-pct"] == 100.0
        assert payload["files"][0]["path"] == "a.py"

    def test_coverage_gap_still_returns_ok(self, tmp_path: Path) -> None:
        # The scanner reports; it does not gate. A missing header is named in
        # the mirror but does NOT change the exit code.
        _make_tree(tmp_path, {"bad.py": "x = 1\n"})

        code = main(
            [
                "--root",
                str(tmp_path),
                "--inventory",
                ".audit/inventory.json",
                "--exception-fixture",
                "noexc.txt",
                "--out-json",
                ".audit/header-coverage.json",
                "--out-md",
                ".audit/header-coverage.md",
            ]
        )

        assert code == EXIT_OK
        md = (tmp_path / ".audit" / "header-coverage.md").read_text(encoding="utf-8")
        assert "Files Missing the Banner" in md
        assert "bad.py" in md
