# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""Unit tests for the ecosystem inventory builder.

``apothem.audit.build_inventory`` walks a working tree and emits one
``inventory.json`` record per file — class, header status, header variant,
SHA-256, line count — plus aggregate stats. It is the root of the audit
pipeline the graph builder and the renderers consume. Its classification,
variant resolution, banner scan, hashing, aggregation, and serialization are
pure transforms over paths and on-disk bytes, so they are covered directly;
``main`` and ``walk_root`` run end-to-end against a fixture tree in ``tmp_path``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from apothem.audit.build_inventory import (
    CLASS_AGENT,
    CLASS_DOCS,
    CLASS_SCAFFOLDING,
    CLASS_SETTINGS,
    CLASS_UNKNOWN,
    EXIT_ERROR,
    EXIT_OK,
    HEADER_ABSENT,
    HEADER_NOT_APPLICABLE,
    HEADER_PRESENT_CANONICAL,
    HEADER_PRESENT_MALFORMED,
    HEADER_VARIANT_C_BLOCK,
    HEADER_VARIANT_DOUBLE_DASH,
    HEADER_VARIANT_DOUBLE_SLASH,
    HEADER_VARIANT_HASH,
    HEADER_VARIANT_HTML,
    HEADER_VARIANT_NONE,
    HEADER_VARIANT_SEMICOLON,
    ROOT_DOCS_FILES,
    ROOT_SCAFFOLDING_FILES,
    ROOT_SETTINGS_FILES,
    FileRecord,
    InventoryStats,
    aggregate_stats,
    classify_file,
    compute_sha256,
    count_lines,
    emit_inventory,
    header_variant_for,
    is_binary_file,
    main,
    parse_arguments,
    scan_banner,
    walk_root,
)


class TestClassifyFile:
    def test_path_prefix_directories_map_to_their_class(self) -> None:
        assert classify_file(Path("agents/explorer.md")) == CLASS_AGENT
        assert classify_file(Path("rules/naturalism.md")) == CLASS_DOCS
        assert classify_file(Path(".plans/suite/PHASE.md")) == "plan-artifact"

    def test_root_level_files_map_via_their_membership_sets(self) -> None:
        for name in ROOT_SETTINGS_FILES:
            assert classify_file(Path(name)) == CLASS_SETTINGS
        for name in ROOT_SCAFFOLDING_FILES:
            assert classify_file(Path(name)) == CLASS_SCAFFOLDING
        for name in ROOT_DOCS_FILES:
            assert classify_file(Path(name)) == CLASS_DOCS

    def test_unknown_root_file_and_unknown_prefix(self) -> None:
        assert classify_file(Path("mystery.xyz")) == CLASS_UNKNOWN
        assert classify_file(Path("unrecognized/deep/file.txt")) == CLASS_UNKNOWN


class TestHeaderVariantFor:
    def test_extension_maps_to_its_comment_family(self) -> None:
        assert header_variant_for(Path("a.py")) == HEADER_VARIANT_HASH
        assert header_variant_for(Path("a.md")) == HEADER_VARIANT_HTML
        assert header_variant_for(Path("a.js")) == HEADER_VARIANT_DOUBLE_SLASH
        assert header_variant_for(Path("a.c")) == HEADER_VARIANT_C_BLOCK
        assert header_variant_for(Path("a.ini")) == HEADER_VARIANT_SEMICOLON
        assert header_variant_for(Path("a.sql")) == HEADER_VARIANT_DOUBLE_DASH

    def test_binary_and_unknown_extensions_resolve_to_none(self) -> None:
        assert header_variant_for(Path("logo.png")) == HEADER_VARIANT_NONE
        assert header_variant_for(Path("data.unknownext")) == HEADER_VARIANT_NONE

    def test_not_applicable_basename_resolves_to_none(self) -> None:
        # A lockfile basename is in NOT_APPLICABLE_NAMES regardless of suffix.
        assert header_variant_for(Path("uv.lock")) == HEADER_VARIANT_NONE

    def test_not_applicable_extension_resolves_to_none(self) -> None:
        # .json carries no comment syntax -> not-applicable for a banner.
        assert header_variant_for(Path("config.json")) == HEADER_VARIANT_NONE


class TestIsBinaryFile:
    def test_known_binary_extension_is_binary(self) -> None:
        assert is_binary_file(Path("logo.png")) is True

    def test_text_extension_is_not_binary(self) -> None:
        assert is_binary_file(Path("a.py")) is False


class TestComputeSha256:
    def test_matches_hashlib(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_bytes(b"hello world")
        assert compute_sha256(f) == hashlib.sha256(b"hello world").hexdigest()


class TestCountLines:
    def test_counts_newline_terminated_lines(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_bytes(b"one\ntwo\nthree\n")
        assert count_lines(f) == 3

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert count_lines(tmp_path / "absent.txt") is None


class TestScanBanner:
    def test_none_variant_short_circuits_to_not_applicable(
        self, tmp_path: Path
    ) -> None:
        # The file is never opened when the variant is 'none'.
        assert scan_banner(tmp_path / "absent.bin", HEADER_VARIANT_NONE) == (
            HEADER_NOT_APPLICABLE
        )

    def test_spdx_line_is_present_canonical(self, tmp_path: Path) -> None:
        f = tmp_path / "a.py"
        f.write_text("# SPDX-License-Identifier: MIT\n\nx = 1\n", encoding="utf-8")
        assert scan_banner(f, HEADER_VARIANT_HASH) == HEADER_PRESENT_CANONICAL

    def test_legacy_copyright_without_spdx_is_present_malformed(
        self, tmp_path: Path
    ) -> None:
        f = tmp_path / "a.py"
        f.write_text("# Copyright (c) Ahmed G. Gad\n\nx = 1\n", encoding="utf-8")
        assert scan_banner(f, HEADER_VARIANT_HASH) == HEADER_PRESENT_MALFORMED

    def test_no_marker_is_absent(self, tmp_path: Path) -> None:
        f = tmp_path / "a.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert scan_banner(f, HEADER_VARIANT_HASH) == HEADER_ABSENT

    def test_unreadable_path_is_absent(self, tmp_path: Path) -> None:
        # Opening a directory as a file raises OSError -> reported absent.
        assert scan_banner(tmp_path, HEADER_VARIANT_HASH) == HEADER_ABSENT


class TestFileRecord:
    def test_to_json_renames_to_hyphenated_keys(self) -> None:
        record = FileRecord(
            path="a.py",
            size=10,
            mtime="2026-06-22T00:00:00+00:00",
            sha256="abc",
            line_count=3,
            file_class="scaffolding",
            header_status="present-canonical",
            header_variant="hash",
        )
        doc = record.to_json()
        assert doc["line-count"] == 3
        assert doc["class"] == "scaffolding"
        assert doc["header-status"] == "present-canonical"
        assert doc["header-variant"] == "hash"


class TestAggregateStats:
    def test_counts_by_class_status_and_variant(self) -> None:
        records = [
            FileRecord(
                "a.py", 1, "t", "s", 1, CLASS_SCAFFOLDING, "present-canonical", "hash"
            ),
            FileRecord("b.py", 1, "t", "s", 1, CLASS_SCAFFOLDING, "absent", "hash"),
            FileRecord("c.md", 1, "t", "s", 1, CLASS_DOCS, "present-canonical", "html"),
        ]
        stats = aggregate_stats(records, ["dist", "dist"])

        assert isinstance(stats, InventoryStats)
        assert stats.total_files == 3
        assert stats.by_class[CLASS_SCAFFOLDING] == 2
        assert stats.by_class[CLASS_DOCS] == 1
        assert stats.by_header_status["present-canonical"] == 2
        assert stats.by_header_status["absent"] == 1
        assert stats.by_header_variant["hash"] == 2
        assert stats.by_header_variant["html"] == 1
        # Skipped directories are deduplicated and sorted.
        assert stats.skipped_directories == ["dist"]


class TestEmitInventory:
    def test_serialises_payload_with_files_and_stats(self, tmp_path: Path) -> None:
        records = [
            FileRecord("a.py", 1, "t", "sha", 1, CLASS_SCAFFOLDING, "absent", "hash"),
        ]
        stats = aggregate_stats(records, [])
        out = tmp_path / "nested" / "inventory.json"

        emit_inventory(Path("/repo"), records, stats, out)

        doc = json.loads(out.read_text(encoding="utf-8"))
        assert doc["total-files"] == 1
        assert doc["files"][0]["path"] == "a.py"
        assert doc["files"][0]["header-variant"] == "hash"
        assert "by-class" in doc
        assert "skipped-directories" in doc


class TestWalkRoot:
    def test_records_files_and_skips_ignored_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "agents").mkdir()
        (tmp_path / "agents/explorer.md").write_text(
            "<!-- SPDX-License-Identifier: MIT -->\n", encoding="utf-8"
        )
        # 'node_modules' is a SKIPPED_DIRS member -> pruned from the walk.
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules/bundle.js").write_text("x", encoding="utf-8")

        records, skipped = walk_root(tmp_path)

        paths = {r.path for r in records}
        assert "agents/explorer.md" in paths
        assert "node_modules/bundle.js" not in paths
        assert "node_modules" in skipped
        # The agent file carries the canonical SPDX header.
        agent = next(r for r in records if r.path == "agents/explorer.md")
        assert agent.file_class == CLASS_AGENT
        assert agent.header_status == HEADER_PRESENT_CANONICAL


class TestParseArguments:
    def test_requires_root_and_output(self) -> None:
        args = parse_arguments(["--root", "r", "--output", "o.json"])
        assert args.root == Path("r")
        assert args.output == Path("o.json")


class TestMain:
    def test_missing_root_directory_returns_error(self, tmp_path: Path) -> None:
        code = main(
            [
                "--root",
                str(tmp_path / "absent"),
                "--output",
                str(tmp_path / "o.json"),
            ]
        )
        assert code == EXIT_ERROR

    def test_walks_the_tree_and_writes_inventory(self, tmp_path: Path) -> None:
        (tmp_path / "rules").mkdir()
        (tmp_path / "rules/naturalism.md").write_text(
            "<!-- SPDX-License-Identifier: MIT -->\n", encoding="utf-8"
        )
        out = tmp_path / "inventory.json"

        code = main(["--root", str(tmp_path), "--output", str(out)])

        assert code == EXIT_OK
        doc = json.loads(out.read_text(encoding="utf-8"))
        assert doc["total-files"] >= 1
        rule = next(r for r in doc["files"] if r["path"] == "rules/naturalism.md")
        assert rule["class"] == CLASS_DOCS
        assert rule["header-status"] == HEADER_PRESENT_CANONICAL


# REUSE-IgnoreEnd
