# SPDX-License-Identifier: MIT

"""Bootstrap-context assembly for the SessionStart hook (``hooks.session_start_bootstrap``).

On every session start the hook builds the injected context from inputs that may
be empty or absent — an empty payload, no memory index, no active plan suite.
Each summary builder (session metadata, memory, plan) must tolerate the missing
case and emit a blank section rather than raise, since a bootstrap fault would
fail the first turn of every session. These tests pin the empty-input and
populated-input paths for each builder plus the composed ``main`` output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import session_start_bootstrap as ssb  # noqa: E402


class TestSessionMeta:
    """Extracting session metadata from the hook payload.

    Covers the empty payload yielding blank metadata, extraction from a
    populated payload, bullet-row rendering, and coercion of non-string fields
    to empty rather than propagating the wrong type.
    """

    def test_empty_payload_returns_blank_meta(self) -> None:
        meta = ssb.SessionMeta.from_payload(None)

        assert meta.source == ""
        assert meta.lines() == []

    def test_populated_payload_extracts_fields(self) -> None:
        meta = ssb.SessionMeta.from_payload(
            {"source": "startup", "model": "opus", "agent_type": "general"}
        )

        assert meta.source == "startup"
        assert meta.model == "opus"
        assert meta.agent_type == "general"

    def test_lines_renders_bullet_rows(self) -> None:
        meta = ssb.SessionMeta(source="startup", model="opus", agent_type="")

        lines = meta.lines()

        assert "- Session source: startup" in lines
        assert "- Model: opus" in lines
        assert not any("Agent:" in line for line in lines)

    def test_non_string_fields_coerced_to_empty(self) -> None:
        meta = ssb.SessionMeta.from_payload(
            {"source": 123, "model": None, "agent_type": ["x"]}
        )

        assert meta.source == ""
        assert meta.model == ""
        assert meta.agent_type == ""


class TestMemorySummary:
    """Rendering the memory-tier summary block.

    Covers that an empty summary produces no lines at all, so the bootstrap
    output carries no empty heading, against the populated rendering.
    """

    def test_empty_summary_produces_no_lines(self) -> None:
        assert ssb.MemorySummary().lines() == []

    def test_lines_rendering(self) -> None:
        summary = ssb.MemorySummary(
            overview="A project",
            latest="2026-04-19 note",
            topic_files=["a.md", "b.md", "c.md", "d.md"],
            key_conventions=["rule1", "rule2", "rule3", "rule4"],
        )

        lines = summary.lines()

        assert "- Project overview: A project" in lines
        assert "- Latest memory entry: 2026-04-19 note" in lines
        assert "- Topic files: a.md, b.md, c.md" in lines
        assert sum(1 for line in lines if line.startswith("- Convention:")) == 3


class TestPlanSummary:
    """Rendering the plan-suite summary block.

    Covers that an empty summary produces no lines, against the populated
    rendering of every field.
    """

    def test_empty_summary_produces_no_lines(self) -> None:
        assert ssb.PlanSummary().lines() == []

    def test_lines_renders_all_fields(self) -> None:
        summary = ssb.PlanSummary(
            suite_name="repo-plan",
            status="in-progress",
            phase_in_progress="02",
            task_in_progress="T2.3",
            next_action="Do X",
            blockers="None",
            critical_files=["a.py", "b.py", "c.py", "d.py", "e.py", "f.py"],
        )

        lines = summary.lines()

        assert "- Active suite: repo-plan" in lines
        assert "- Suite status: in-progress" in lines
        assert "- Phase in progress: 02" in lines
        assert "- Next action: Do X" in lines
        assert sum(1 for line in lines if line.startswith("- Critical file:")) == 5


class TestSectionParsing:
    """Primitives for reading values out of a Markdown section.

    Covers first-non-blank content lookup (including the empty section), bold
    field lookup (including the missing key), and heading-value tail
    extraction.
    """

    def test_first_nonblank_finds_first_content_line(self, tmp_path: Path) -> None:
        path = tmp_path / "memory.md"
        path.write_text(
            "# Title\n\n## Project Overview\n\n\nFirst line.\nSecond.\n## Other\n",
            encoding="utf-8",
        )

        assert ssb.first_nonblank(path, "## Project Overview") == "First line."

    def test_first_nonblank_empty_section_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "memory.md"
        path.write_text("## Project Overview\n## Other\n", encoding="utf-8")

        assert ssb.first_nonblank(path, "## Project Overview") == ""

    def test_bold_field_returns_value(self, tmp_path: Path) -> None:
        path = tmp_path / "f.md"
        path.write_text("**Latest:** 2026-04-19 update\n", encoding="utf-8")

        assert ssb.bold_field(path, "Latest") == "2026-04-19 update"

    def test_bold_field_missing_key_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "f.md"
        path.write_text("**Other:** x\n", encoding="utf-8")

        assert ssb.bold_field(path, "Latest") == ""

    def test_heading_value_extracts_tail(self, tmp_path: Path) -> None:
        path = tmp_path / "p.md"
        path.write_text("## Status: in-progress\n", encoding="utf-8")

        assert ssb.heading_value(path, "## Status:") == "in-progress"


class TestTopicFileNames:
    """Collecting topic file names from an index document.

    Covers that only Markdown links are extracted, that non-``.md`` links are
    ignored, and that the limit caps the result count.
    """

    def test_extracts_only_markdown_links(self, tmp_path: Path) -> None:
        path = tmp_path / "MEMORY.md"
        path.write_text(
            "## Topic Files\n"
            "- [Hooks](hooks.md) — inline `dispatch.ps1` mention\n"
            "- [Patterns](patterns.md) with `set -e` snippet\n"
            "## Other\n",
            encoding="utf-8",
        )

        result = ssb.topic_file_names(path, "## Topic Files")

        assert result == ["hooks.md", "patterns.md"]

    def test_limit_caps_results(self, tmp_path: Path) -> None:
        path = tmp_path / "MEMORY.md"
        path.write_text(
            "## Topic Files\n- [A](a.md)\n- [B](b.md)\n- [C](c.md)\n- [D](d.md)\n",
            encoding="utf-8",
        )

        assert ssb.topic_file_names(path, "## Topic Files", limit=2) == [
            "a.md",
            "b.md",
        ]

    def test_ignores_non_md_links(self, tmp_path: Path) -> None:
        path = tmp_path / "MEMORY.md"
        path.write_text(
            "## Topic Files\n- [site](https://example.com)\n- [a](a.md)\n",
            encoding="utf-8",
        )

        assert ssb.topic_file_names(path, "## Topic Files") == ["a.md"]


class TestBulletsUnder:
    """Collecting bullet items beneath a heading.

    Covers extraction of the bullets and the stop boundary at the next
    second-level heading, so one section never absorbs the next.
    """

    def test_extracts_bullets(self, tmp_path: Path) -> None:
        path = tmp_path / "m.md"
        path.write_text(
            "## Key Conventions\n- one\n- two\n- three\n- four\n## Other\n",
            encoding="utf-8",
        )

        assert ssb.bullets_under(path, "## Key Conventions") == [
            "one",
            "two",
            "three",
        ]

    def test_stops_at_next_h2(self, tmp_path: Path) -> None:
        path = tmp_path / "m.md"
        path.write_text(
            "## A\n- x\n## B\n- y\n",
            encoding="utf-8",
        )

        assert ssb.bullets_under(path, "## A") == ["x"]


class TestNumberedUnder:
    """Collecting numbered items beneath a heading.

    Covers extraction of the ordered items.
    """

    def test_extracts_numbered_items(self, tmp_path: Path) -> None:
        path = tmp_path / "p.md"
        path.write_text(
            "### Critical Files for Next Phase\n"
            "1. file_a.py\n2. file_b.py\n3. file_c.py\n"
            "### Other\n",
            encoding="utf-8",
        )

        result = ssb.numbered_under(path, "### Critical Files for Next Phase")

        assert result == ["file_a.py", "file_b.py", "file_c.py"]


class TestProjectSlug:
    """Slugifying a project path into a directory key.

    Covers the Windows-shaped path, whose separators and drive letter must
    survive slugification.
    """

    def test_windows_path_slugified(self) -> None:
        result = ssb.project_slug(Path("C:/Users/test-user/.claude"))

        assert result == "c--users-test-user--claude"


class TestFindMemoryIndex:
    """Locating the memory index for the current project.

    Covers the direct match winning, the missing projects directory returning
    none, and the leaf fallback — which matches on a path-boundary suffix and
    rejects a bare substring, so a similarly-named project cannot be picked.
    """

    def test_direct_match_wins(self, tmp_path: Path) -> None:
        root = tmp_path / ".claude"
        slug = ssb.project_slug(root)
        direct = root / "projects" / slug / "memory" / "MEMORY.md"
        direct.parent.mkdir(parents=True)
        direct.write_text("# m", encoding="utf-8")

        assert ssb.find_memory_index(root) == direct

    def test_missing_projects_dir_returns_none(self, tmp_path: Path) -> None:
        assert ssb.find_memory_index(tmp_path / "empty") is None

    def test_leaf_fallback_matches_boundary_suffix(self, tmp_path: Path) -> None:
        # The leaf is the trailing kebab segment of the project slug, so a
        # slug ending in ``-<leaf>`` is a genuine match for this project.
        root = tmp_path / "my-app"
        fallback = root / "projects" / "c--work-my-app" / "memory" / "MEMORY.md"
        fallback.parent.mkdir(parents=True)
        fallback.write_text("# m", encoding="utf-8")

        assert ssb.find_memory_index(root) == fallback

    def test_leaf_fallback_rejects_bare_substring(self, tmp_path: Path) -> None:
        # A mere substring must NOT cross-match: a project named ``my-app-fork``
        # is NOT this ``my-app`` project's memory — the prior substring test
        # ('app' in 'my-app-fork') would have wrongly resolved it.
        root = tmp_path / "my-app"
        other = root / "projects" / "c--work-my-app-fork" / "memory" / "MEMORY.md"
        other.parent.mkdir(parents=True)
        other.write_text("# m", encoding="utf-8")

        assert ssb.find_memory_index(root) is None


class TestFindActiveSuite:
    """Selecting the active plan suite.

    Covers the no-plans-directory case returning none, selection of the most
    recent suite, and the skipping of incomplete suites.
    """

    def test_returns_none_when_no_plans_dir(self, tmp_path: Path) -> None:
        assert ssb.find_active_suite(tmp_path / ".plans") is None

    def test_picks_most_recent_suite(self, tmp_path: Path) -> None:
        plans = tmp_path / ".plans"
        plans.mkdir()
        older = plans / "suite-a"
        older.mkdir()
        (older / "PROGRESS.md").write_text("a", encoding="utf-8")
        (older / "PLAN-NOTES.md").write_text("a", encoding="utf-8")
        newer = plans / "suite-b"
        newer.mkdir()
        (newer / "PROGRESS.md").write_text("b", encoding="utf-8")
        (newer / "PLAN-NOTES.md").write_text("b", encoding="utf-8")
        import os

        # Deterministic mtime delta via explicit absolute timestamps — no
        # wall-clock sleep, so the ordering holds regardless of filesystem
        # mtime granularity.
        base = 1_700_000_000
        os.utime(older / "PROGRESS.md", (base, base))
        os.utime(newer / "PROGRESS.md", (base + 10, base + 10))

        assert ssb.find_active_suite(plans) == newer

    def test_ignores_incomplete_suites(self, tmp_path: Path) -> None:
        plans = tmp_path / ".plans"
        incomplete = plans / "incomplete"
        incomplete.mkdir(parents=True)
        (incomplete / "PROGRESS.md").write_text("x", encoding="utf-8")

        assert ssb.find_active_suite(plans) is None


class TestBuildContext:
    """Assembling the full bootstrap context block.

    Covers the degraded path, where neither a plan nor memory is present and a
    placeholder is emitted, against the full assembly.
    """

    def test_no_plan_no_memory_emits_placeholder(self, tmp_path: Path) -> None:
        context = ssb.build_context(tmp_path, None)

        assert "Plan summary:" in context
        assert "No active plan suite detected" in context

    def test_full_context_assembly(self, tmp_path: Path) -> None:
        root = tmp_path / ".claude"
        slug = ssb.project_slug(root)
        memory = root / "projects" / slug / "memory" / "MEMORY.md"
        memory.parent.mkdir(parents=True)
        memory.write_text(
            "## Project Overview\nTest project.\n## Other\n",
            encoding="utf-8",
        )
        plans = root / ".plans"
        suite = plans / "test-suite"
        suite.mkdir(parents=True)
        (suite / "PROGRESS.md").write_text(
            "## Status: active\n**Next action:** run tests\n",
            encoding="utf-8",
        )
        (suite / "PLAN-NOTES.md").write_text("", encoding="utf-8")

        payload = {"source": "startup", "model": "opus"}
        context = ssb.build_context(root, payload)

        assert "Session bootstrap:" in context
        assert "- Session source: startup" in context
        assert "Memory summary:" in context
        assert "- Project overview: Test project." in context
        assert "Plan summary:" in context
        assert "- Active suite: test-suite" in context
        assert "- Next action: run tests" in context


class TestMain:
    """Process-level entry point behaviour.

    Covers envelope emission, quiet mode suppressing output, and the failure
    envelope emitted when context assembly raises — the fail-open contract that
    keeps a bootstrap error from blocking the session.
    """

    def test_main_emits_envelope(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import io

        stream = io.StringIO("")
        stream.isatty = lambda: True  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

        ssb.main([])

        envelope = json.loads(capsys.readouterr().out)

        assert envelope["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        assert "additionalContext" in envelope["hookSpecificOutput"]

    def test_main_quiet_suppresses_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import io

        stream = io.StringIO("")
        stream.isatty = lambda: True  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

        ssb.main(["--quiet"])

        assert capsys.readouterr().out == ""

    def test_main_emits_failure_envelope_when_build_context_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import io

        stream = io.StringIO("")
        stream.isatty = lambda: True  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

        def _boom(*_args: object, **_kwargs: object) -> str:
            raise RuntimeError("bootstrap exploded")

        monkeypatch.setattr(ssb, "build_context", _boom)
        # The outermost boundary must emit a structurally valid SessionStart
        # failure envelope, never a traceback.
        ssb.main([])

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        assert (
            "Hook execution failure: bootstrap exploded"
            in envelope["hookSpecificOutput"]["additionalContext"]
        )
