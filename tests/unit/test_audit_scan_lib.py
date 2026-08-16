# SPDX-License-Identifier: MIT

"""Unit tests for the shared drift/classification scan scaffolding.

``apothem.audit._scan_lib`` is the foundation every drift scanner, the
classification pass, and the synthesis pass build on: load the inventory,
filter to narrative surfaces, fail-soft text read, walk the surfaces, and emit
the canonical JSON envelope. Covering its public surface directly catches a
regression in the shared scaffolding once, rather than only through the
(otherwise untested) consumer scanners.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from apothem.audit._scan_lib import (
    CONTENT_ROOT,
    NARRATIVE_CLASSES,
    Hit,
    emit_json,
    load_inventory,
    narrative_surface_filter,
    read_text_safely,
    walk_narrative_surfaces,
)


class TestLoadInventory:
    """Loading the inventory the scan walks.

    Covers the records and content digest being returned, and a payload missing
    the files key yielding empty records rather than raising.
    """

    def test_returns_records_and_content_sha(self, tmp_path: Path) -> None:
        inv = tmp_path / "inventory.json"
        payload = {"files": [{"path": "a.md", "class": "docs"}]}
        raw = json.dumps(payload).encode("utf-8")
        inv.write_bytes(raw)

        records, sha = load_inventory(inv)

        assert records == payload["files"]
        assert sha == hashlib.sha256(raw).hexdigest()

    def test_missing_files_key_yields_empty_records(self, tmp_path: Path) -> None:
        inv = tmp_path / "inventory.json"
        inv.write_text("{}", encoding="utf-8")

        records, _ = load_inventory(inv)

        assert records == []


class TestNarrativeSurfaceFilter:
    """Selecting which records count as narrative surfaces.

    Covers inclusion of every narrative class against the exclusions: state
    artifacts, unknown classes, and a record carrying no class at all.
    """

    def test_includes_every_narrative_class(self) -> None:
        for cls in NARRATIVE_CLASSES:
            assert narrative_surface_filter({"class": cls}) is True

    def test_excludes_state_artifact_and_unknown(self) -> None:
        for cls in ("memory", "plan-artifact", "unknown", ""):
            assert narrative_surface_filter({"class": cls}) is False

    def test_excludes_record_without_a_class(self) -> None:
        assert narrative_surface_filter({}) is False


class TestReadTextSafely:
    """Defensive text read of a scanned file.

    Covers the normal UTF-8 read, the two empty results (missing file, oversize
    file), and invalid UTF-8 falling back to replacement characters so one
    undecodable file cannot abort the sweep.
    """

    def test_reads_utf8_content(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_text("hello", encoding="utf-8")

        assert read_text_safely(f) == "hello"

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert read_text_safely(tmp_path / "absent.txt") == ""

    def test_oversize_file_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("xxxxxx", encoding="utf-8")

        assert read_text_safely(f, max_bytes=3) == ""

    def test_invalid_utf8_falls_back_to_replacement(self, tmp_path: Path) -> None:
        f = tmp_path / "bin.txt"
        f.write_bytes(b"ab\xff\xfecd")  # not valid UTF-8

        out = read_text_safely(f)

        # Decoded with the replacement codec — surrounding text survives, no crash.
        assert "ab" in out
        assert "cd" in out


class TestWalkNarrativeSurfaces:
    """Walking the narrative surfaces.

    Covers that only narrative files carrying content are visited.
    """

    def test_walks_only_narrative_files_that_have_content(self, tmp_path: Path) -> None:
        (tmp_path / "doc.md").write_text("body", encoding="utf-8")
        (tmp_path / "state.md").write_text("body", encoding="utf-8")
        # 'empty.md' is deliberately not written -> read_text_safely returns "".
        records: list[dict[str, Any]] = [
            {"path": "doc.md", "class": "docs"},
            {"path": "state.md", "class": "memory"},  # non-narrative -> skipped
            {"path": "empty.md", "class": "docs"},  # missing file -> skipped
        ]
        visited: list[str] = []

        def callback(path: Path, record: dict[str, Any], content: str) -> list[Hit]:
            visited.append(str(record["path"]))
            return [
                Hit(
                    file=str(record["path"]),
                    line=1,
                    signal="x",
                    severity="LOW",
                    remediation="y",
                )
            ]

        hits = walk_narrative_surfaces(records, tmp_path, callback)

        assert visited == ["doc.md"]
        assert len(hits) == 1
        assert hits[0].file == "doc.md"


class TestEmitJson:
    """Writing the scan envelope.

    Covers the canonical envelope shape and the creation of missing parent
    directories.
    """

    def test_writes_canonical_envelope_and_creates_parents(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "nested" / "scan.json"
        hit = Hit(file="a.md", line=3, signal="sig", severity="HIGH", remediation="fix")

        emit_json(out, "my-scan", [hit], "abc123")

        doc = json.loads(out.read_text(encoding="utf-8"))
        assert doc["scanner"] == "my-scan"
        assert doc["inventory-source-sha256"] == "abc123"
        assert doc["hit-count"] == 1
        assert doc["hits"][0]["file"] == "a.md"
        assert doc["hits"][0]["severity"] == "HIGH"
        assert "generated" in doc  # ISO timestamp present


class TestHit:
    """The per-hit record.

    Covers that the extra field defaults to an empty mapping, so a consumer can
    index it without a presence check.
    """

    def test_extra_defaults_to_empty_dict(self) -> None:
        h = Hit(file="f", line=1, signal="s", severity="LOW", remediation="r")
        assert h.extra == {}


class TestContentRoot:
    """Resolving the content root the scan is anchored to."""

    def test_resolves_to_the_apothem_content_root(self) -> None:
        # CONTENT_ROOT is the default --root for inventory-record-resolving
        # scanners: the src/apothem package directory the inventory is built
        # against. Its enumerated artifact directories must exist on disk.
        assert CONTENT_ROOT.name == "apothem"
        assert (CONTENT_ROOT / "rules").is_dir()
        assert (CONTENT_ROOT / "audit").is_dir()
