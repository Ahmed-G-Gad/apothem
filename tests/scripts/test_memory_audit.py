# SPDX-License-Identifier: MIT

"""Unit tests for the memory-tier health auditor.

``scripts/dev/memory_audit.py`` walks the project/global memory tiers and
reports each ``MEMORY.md`` index's health: line budget, topic-index integrity,
orphan topic files, and frontmatter-date freshness. ``--fix`` is the only
mutating path (it truncates an over-budget index, nothing else), so it gets
explicit on-disk verification. Every fixture tree is built under ``tmp_path``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import memory_audit as ma  # noqa: E402


def _tree(root: Path, name: str, files: dict[str, str]) -> Path:
    """Create a memory tree ``root/name`` from {relative: text}."""
    tree = root / name
    for rel, text in files.items():
        p = tree / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tree


class TestDiscoverMemoryTrees:
    def test_finds_global_and_project_trees_sorted(self, tmp_path: Path) -> None:
        (tmp_path / "memory").mkdir()
        (tmp_path / "projects" / "b" / "memory").mkdir(parents=True)
        (tmp_path / "projects" / "a" / "memory").mkdir(parents=True)
        # A project dir without a memory subtree is skipped.
        (tmp_path / "projects" / "c").mkdir()

        trees = ma.discover_memory_trees(tmp_path)
        rels = [t.relative_to(tmp_path).as_posix() for t in trees]

        assert rels[0] == "memory"  # global first
        # Project trees follow, sorted by project dir name.
        assert rels[1:] == ["projects/a/memory", "projects/b/memory"]

    def test_empty_when_no_memory_dirs(self, tmp_path: Path) -> None:
        assert ma.discover_memory_trees(tmp_path) == []


class TestTopicReferences:
    def test_extracts_markdown_md_links_only(self) -> None:
        text = "- [Topic A](a.md) — hook\n- [Site](https://x) — not md\n- [B](sub/b.md)"
        assert ma._topic_references(text) == ["a.md", "sub/b.md"]


class TestUpdatedValue:
    def test_reads_frontmatter_updated(self, tmp_path: Path) -> None:
        f = tmp_path / "t.md"
        f.write_text("---\nname: t\nupdated: 2026-06-22\n---\nbody", encoding="utf-8")
        assert ma._updated_value(f) == "2026-06-22"

    def test_none_when_no_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "t.md"
        f.write_text("no frontmatter here", encoding="utf-8")
        assert ma._updated_value(f) is None

    def test_none_when_frontmatter_lacks_updated(self, tmp_path: Path) -> None:
        f = tmp_path / "t.md"
        f.write_text("---\nname: t\n---\nbody", encoding="utf-8")
        assert ma._updated_value(f) is None


class TestCheckIsoDate:
    def test_accepts_valid_iso(self) -> None:
        assert ma._check_iso_date("2026-06-22") is True

    def test_rejects_wrong_shape(self) -> None:
        assert ma._check_iso_date("2026/06/22") is False
        assert ma._check_iso_date("June 22 2026") is False

    def test_rejects_well_shaped_but_invalid_calendar_date(self) -> None:
        # Matches the regex but is not a real date -> fromisoformat rejects.
        assert ma._check_iso_date("2026-13-01") is False


class TestAuditTree:
    def test_missing_index_with_topics_fails(self, tmp_path: Path) -> None:
        tree = _tree(tmp_path, "memory", {"topic.md": "body"})
        rep = ma.audit_tree(tree, apply_fix=False)
        assert rep.fails == 1
        assert "MEMORY.md missing" in rep.findings[0].message

    def test_empty_tree_is_info(self, tmp_path: Path) -> None:
        tree = tmp_path / "memory"
        tree.mkdir()
        rep = ma.audit_tree(tree, apply_fix=False)
        assert rep.fails == 0
        assert rep.findings[0].severity == "info"

    def test_clean_tree_has_no_findings(self, tmp_path: Path) -> None:
        tree = _tree(
            tmp_path,
            "memory",
            {
                "MEMORY.md": "# Index\n\n- [Topic A](a.md) — hook\n",
                "a.md": "---\nupdated: 2026-06-22\n---\nbody",
            },
        )
        rep = ma.audit_tree(tree, apply_fix=False)
        assert rep.findings == []

    def test_referenced_but_missing_topic_fails(self, tmp_path: Path) -> None:
        tree = _tree(tmp_path, "memory", {"MEMORY.md": "- [Gone](ghost.md)\n"})
        rep = ma.audit_tree(tree, apply_fix=False)
        assert rep.fails == 1
        assert "referenced but missing" in rep.findings[0].message

    def test_orphan_topic_warns(self, tmp_path: Path) -> None:
        tree = _tree(
            tmp_path,
            "memory",
            {"MEMORY.md": "# Index, no links\n", "orphan.md": "unindexed body"},
        )
        rep = ma.audit_tree(tree, apply_fix=False)
        assert rep.warns == 1
        assert "not indexed" in rep.findings[0].message

    def test_malformed_updated_date_fails(self, tmp_path: Path) -> None:
        tree = _tree(
            tmp_path,
            "memory",
            {
                "MEMORY.md": "- [A](a.md)\n",
                "a.md": "---\nupdated: 22-06-2026\n---\nbody",
            },
        )
        rep = ma.audit_tree(tree, apply_fix=False)
        assert rep.fails == 1
        assert "malformed updated" in rep.findings[0].message

    def test_escaping_topic_reference_warns(self, tmp_path: Path) -> None:
        tree = _tree(tmp_path, "memory", {"MEMORY.md": "- [Out](../escape.md)\n"})
        rep = ma.audit_tree(tree, apply_fix=False)
        assert rep.warns == 1
        assert "escapes tree" in rep.findings[0].message

    def test_over_budget_without_fix_fails(self, tmp_path: Path) -> None:
        body = "\n".join(f"line {i}" for i in range(250))
        tree = _tree(tmp_path, "memory", {"MEMORY.md": body})
        rep = ma.audit_tree(tree, apply_fix=False)
        assert rep.fails == 1
        assert "limit 200" in rep.findings[0].message

    def test_over_budget_with_fix_truncates_file_on_disk(self, tmp_path: Path) -> None:
        body = "\n".join(f"line {i}" for i in range(250))
        tree = _tree(tmp_path, "memory", {"MEMORY.md": body})

        rep = ma.audit_tree(tree, apply_fix=True)

        # --fix downgrades the over-budget fail to a warn and truncates on disk.
        assert rep.fails == 0
        assert rep.warns == 1
        assert "trimmed" in rep.findings[0].message
        after = (tree / "MEMORY.md").read_text(encoding="utf-8").splitlines()
        assert len(after) == ma._LINE_LIMIT


class TestFormatFinding:
    def test_renders_marker_and_relative_path(self, tmp_path: Path) -> None:
        finding = ma.Finding("fail", tmp_path / "memory", "broken")
        line = ma.format_finding(finding, tmp_path)
        assert line == "[FAIL] memory: broken"


class TestReport:
    def test_exit_zero_on_clean(self, tmp_path: Path) -> None:
        rep = ma.TreeReport(root=tmp_path)
        rep.info("ok")
        assert ma.report([rep], ecosystem_root=tmp_path) == 0

    def test_exit_one_on_warnings(self, tmp_path: Path) -> None:
        rep = ma.TreeReport(root=tmp_path)
        rep.warn("soft")
        assert ma.report([rep], ecosystem_root=tmp_path) == 1

    def test_exit_two_on_failures(self, tmp_path: Path) -> None:
        rep = ma.TreeReport(root=tmp_path)
        rep.fail("hard")
        assert ma.report([rep], ecosystem_root=tmp_path) == 2


class TestMain:
    def test_no_trees_returns_zero(self, tmp_path: Path) -> None:
        assert ma.main(["--root", str(tmp_path)]) == 0

    def test_failure_tree_returns_two(self, tmp_path: Path) -> None:
        # A global memory tree with topics but no MEMORY.md -> fail -> exit 2.
        _tree(tmp_path, "memory", {"topic.md": "body"})
        assert ma.main(["--root", str(tmp_path)]) == 2
