# SPDX-License-Identifier: MIT

"""Coverage for the conformity operating-posture statusline renderer.

``src/apothem/statuslines/render.py`` is a shipped runtime surface — the
harness installs it and invokes it to paint the statusline. These tests
exercise every public branch: the harness-payload parser, the project-local
plans-root resolver, the PROGRESS.md / PHASE.md field extractors, the inquiry
counter, the suite walker, the ASCII transliterator, the line composer, and
the never-raise ``main`` boundary. Filesystem-walking helpers pass a tmp tree
as the ``plans_dir`` argument so no real plan suite is touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.statuslines import render

# --- _extract_phase_pointer -------------------------------------------------


def test_extract_phase_pointer_active_phase_field() -> None:
    """The active-phase field yields the phase id without its prose."""
    text = "- **Active phase:** Phase 03A-discovery — mapping the surface\n"
    assert render._extract_phase_pointer(text) == "Phase 03A-discovery"


def test_extract_phase_pointer_in_progress_fallback() -> None:
    """The in-progress field is read when the active-phase field is absent."""
    text = "- **Phase in progress:** Phase 07-release\n"
    assert render._extract_phase_pointer(text) == "Phase 07-release"


def test_extract_phase_pointer_truncates_overlong() -> None:
    """An overlong pointer truncates to the exact width limit.

    The ASCII-rendered width lands on the limit, never over it.
    """
    long_topic = "x" * 100
    text = f"- **Active phase:** {long_topic}\n"
    out = render._extract_phase_pointer(text)
    assert out is not None
    assert out.endswith("…")
    # The raw (pre-ASCII) form reserves three characters for the ``…`` marker,
    # which ``_ascii_safe`` expands to ``...`` — so the FINAL rendered width is
    # exactly the char limit, never over it (the prior +2 overshoot is gone).
    assert len(render._ascii_safe(out)) == render._PHASE_POINTER_CHARLIMIT


def test_extract_phase_pointer_absent_returns_none() -> None:
    """Text carrying no phase field yields none."""
    assert render._extract_phase_pointer("no phase field here\n") is None


# --- _extract_sprint_goal ---------------------------------------------------


def _suite_with_phase(tmp_path: Path, *, phase_dir: str, phase_md_body: str) -> Path:
    """Build a one-phase suite tree and return its root.

    Post-conditions: ``<tmp_path>/phases/<phase_dir>/PHASE.md`` holds
    ``phase_md_body``; no other suite file is created, so a test that
    exercises an absent-file path stays isolated.
    """
    phases = tmp_path / "phases" / phase_dir
    phases.mkdir(parents=True)
    (phases / "PHASE.md").write_text(phase_md_body, encoding="utf-8")
    return tmp_path


def test_extract_sprint_goal_none_pointer() -> None:
    """A none pointer yields no goal without touching the filesystem."""
    assert render._extract_sprint_goal(Path("/nonexistent"), None) is None


def test_extract_sprint_goal_non_phase_pointer() -> None:
    """A pointer that names no phase yields no goal."""
    assert render._extract_sprint_goal(Path("/nonexistent"), "Ad-hoc work") is None


def test_extract_sprint_goal_no_phases_dir(tmp_path: Path) -> None:
    """A suite with no phases directory yields no goal."""
    assert render._extract_sprint_goal(tmp_path, "Phase 01-foo") is None


def test_extract_sprint_goal_no_matching_phase_dir(tmp_path: Path) -> None:
    """A phases directory holding only other phases yields no goal."""
    (tmp_path / "phases" / "99-other").mkdir(parents=True)
    assert render._extract_sprint_goal(tmp_path, "Phase 01-foo") is None


def test_extract_sprint_goal_phase_md_missing(tmp_path: Path) -> None:
    """A matching phase directory with no phase file yields no goal."""
    (tmp_path / "phases" / "01-foo").mkdir(parents=True)
    assert render._extract_sprint_goal(tmp_path, "Phase 01-foo") is None


def test_extract_sprint_goal_extracted(tmp_path: Path) -> None:
    """The goal sentence is extracted from its marked line."""
    suite = _suite_with_phase(
        tmp_path,
        phase_dir="01-foo",
        phase_md_body="> **Sprint Goal.** Users can authenticate with OAuth.\n",
    )
    assert (
        render._extract_sprint_goal(suite, "Phase 01-foo")
        == "Users can authenticate with OAuth."
    )


def test_extract_sprint_goal_truncates(tmp_path: Path) -> None:
    """An overlong goal truncates to exactly the ASCII-rendered char limit."""
    goal = "G" * 200
    suite = _suite_with_phase(
        tmp_path, phase_dir="01-foo", phase_md_body=f"> **Sprint Goal.** {goal}\n"
    )
    out = render._extract_sprint_goal(suite, "Phase 01-foo")
    assert out is not None
    assert out.endswith("…")
    # Final ASCII-safe render stays within the char limit (no +2 overshoot).
    assert len(render._ascii_safe(out)) == render._SPRINT_GOAL_CHARLIMIT


def test_extract_sprint_goal_no_goal_line(tmp_path: Path) -> None:
    """A phase file carrying no goal line yields none."""
    suite = _suite_with_phase(
        tmp_path, phase_dir="01-foo", phase_md_body="## Tasks\n- do the thing\n"
    )
    assert render._extract_sprint_goal(suite, "Phase 01-foo") is None


# --- _count_unresolved_inquiries -------------------------------------------


def test_count_unresolved_inquiries_counts_concrete_only(tmp_path: Path) -> None:
    """Only concrete placeholders count.

    The ellipsis template and citation forms are excluded by the negative
    lookahead.
    """
    (tmp_path / "a.md").write_text(
        "Pick one <USER-CONFIRM:choose-formatter> and <USER-CONFIRM:choose-license>.\n",
        encoding="utf-8",
    )
    # Template/citation forms with ellipsis are excluded by the negative lookahead.
    (tmp_path / "b.md").write_text(
        "Syntax is <USER-CONFIRM:…> or <USER-CONFIRM:kind=...; ...>.\n",
        encoding="utf-8",
    )
    assert render._count_unresolved_inquiries(tmp_path) == 2


def test_count_unresolved_inquiries_empty(tmp_path: Path) -> None:
    """A tree carrying no placeholders counts zero."""
    (tmp_path / "x.md").write_text("nothing to confirm here\n", encoding="utf-8")
    assert render._count_unresolved_inquiries(tmp_path) == 0


# --- _most_recent_suite -----------------------------------------------------


def test_most_recent_suite_no_plans_dir(tmp_path: Path) -> None:
    """An absent plans directory yields no suite."""
    assert render._most_recent_suite(tmp_path / "absent") is None


def test_most_recent_suite_empty(tmp_path: Path) -> None:
    """An empty plans directory yields no suite."""
    assert render._most_recent_suite(tmp_path) is None


def test_most_recent_suite_returns_newest(tmp_path: Path) -> None:
    """The most recently modified suite wins."""
    older = tmp_path / "older-suite"
    newer = tmp_path / "newer-suite"
    older.mkdir()
    newer.mkdir()
    import os

    os.utime(older, (1_000, 1_000))
    os.utime(newer, (2_000, 2_000))
    assert render._most_recent_suite(tmp_path) == newer


# --- gather -----------------------------------------------------------------


def test_gather_no_suite(tmp_path: Path) -> None:
    """With no suite present the whole gather yields none."""
    assert render.gather(tmp_path) is None


def test_gather_suite_without_progress(tmp_path: Path) -> None:
    """A suite with no progress file yields empty parts, not none.

    The suite exists; it simply has nothing to report.
    """
    (tmp_path / "suite").mkdir()
    parts = render.gather(tmp_path)
    assert parts == render.StatuslineParts(
        phase_pointer=None, sprint_goal=None, inquiry_count=0
    )


def test_gather_full_suite(tmp_path: Path) -> None:
    """A full suite yields all three fields together.

    The phase pointer, the sprint goal, and the inquiry count.
    """
    suite = tmp_path / "suite"
    phase = suite / "phases" / "02-auth"
    phase.mkdir(parents=True)
    (suite / "PROGRESS.md").write_text(
        "- **Active phase:** Phase 02-auth — wiring\n", encoding="utf-8"
    )
    (phase / "PHASE.md").write_text(
        "> **Sprint Goal.** Ship the login flow.\n", encoding="utf-8"
    )
    (suite / "PLAN-NOTES.md").write_text(
        "Open: <USER-CONFIRM:pick-db>\n", encoding="utf-8"
    )
    parts = render.gather(tmp_path)
    assert parts is not None
    assert parts.phase_pointer == "Phase 02-auth"
    assert parts.sprint_goal == "Ship the login flow."
    assert parts.inquiry_count == 1


# --- _ascii_safe ------------------------------------------------------------


def test_ascii_safe_transliterates_typography() -> None:
    """Mapped typographic characters fold to their ASCII equivalents."""
    raw = "Phase 1 — “Goal” … done·now"
    assert render._ascii_safe(raw) == 'Phase 1 - "Goal" ... done*now'


def test_ascii_safe_drops_unmapped_non_ascii() -> None:
    # é and 中文 are unmapped → dropped; the surrounding ASCII spaces survive.
    """Unmapped non-ASCII is dropped; surrounding ASCII survives.

    Spaces survive too. The statusline is a fixed-width ASCII surface.
    """
    assert render._ascii_safe("café 中文 x") == "caf  x"


# --- render -----------------------------------------------------------------


def test_render_none_parts() -> None:
    """Absent parts render the no-suite placeholder."""
    assert render.render(None) == "[no active suite]"


def test_render_full_parts_plural() -> None:
    """All three fields render in order, with the plural inquiry noun."""
    parts = render.StatuslineParts(
        phase_pointer="Phase 02-auth", sprint_goal="Ship login", inquiry_count=3
    )
    assert render.render(parts) == "[Phase 02-auth | Ship login | 3 inquiries]"


def test_render_singular_inquiry() -> None:
    """A single inquiry renders the singular noun; empty fields drop."""
    parts = render.StatuslineParts(
        phase_pointer=None, sprint_goal=None, inquiry_count=1
    )
    assert render.render(parts) == "[1 inquiry]"


def test_render_zero_inquiries_only() -> None:
    """Zero inquiries still render, using the plural noun."""
    parts = render.StatuslineParts(
        phase_pointer=None, sprint_goal=None, inquiry_count=0
    )
    assert render.render(parts) == "[0 inquiries]"


# --- main -------------------------------------------------------------------


def test_main_no_suite_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no suite the entry point prints the placeholder.

    It exits zero: a statusline never fails the shell.
    """
    monkeypatch.setattr(render, "_read_payload", lambda: {})
    monkeypatch.setattr(render, "_resolve_plans_dir", lambda payload: tmp_path)
    assert render.main() == 0
    assert capsys.readouterr().out.strip() == "[no active suite]"


def test_main_never_raises_on_internal_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An internal error renders as a statusline and still exits zero.

    Post-conditions: the shell prompt never breaks on a gather failure; the
    exception class name is all that surfaces.
    """

    def _boom(plans_dir: Path) -> render.StatuslineParts | None:
        raise RuntimeError("synthetic")

    monkeypatch.setattr(render, "_read_payload", lambda: {})
    monkeypatch.setattr(render, "gather", _boom)
    assert render.main() == 0
    assert capsys.readouterr().out.strip() == "[statusline error: RuntimeError]"


# --- _parse_payload / _payload_project_dir / _resolve_plans_dir -------------


def test_parse_payload_blank_returns_empty() -> None:
    """Blank input parses to an empty payload."""
    assert render._parse_payload("   \n") == {}


def test_parse_payload_malformed_returns_empty() -> None:
    """Malformed JSON parses to an empty payload rather than raising."""
    assert render._parse_payload("{not json") == {}


def test_parse_payload_non_object_returns_empty() -> None:
    """Valid JSON that is not an object parses to an empty payload."""
    assert render._parse_payload("[1, 2, 3]") == {}


def test_parse_payload_valid_object() -> None:
    """A valid object parses through unchanged."""
    assert render._parse_payload('{"workspace": {"project_dir": "/x"}}') == {
        "workspace": {"project_dir": "/x"}
    }


def test_payload_project_dir_present() -> None:
    """The project directory is read from the workspace block."""
    payload = {"workspace": {"project_dir": "/repo"}}
    assert render._payload_project_dir(payload) == "/repo"


def test_payload_project_dir_absent() -> None:
    """An empty payload yields no project directory."""
    assert render._payload_project_dir({}) is None


def test_payload_project_dir_non_dict_workspace() -> None:
    """A non-object workspace yields none rather than raising."""
    assert render._payload_project_dir({"workspace": "oops"}) is None


def test_payload_project_dir_empty_string() -> None:
    """An empty project directory reads as absent, not as the cwd."""
    assert render._payload_project_dir({"workspace": {"project_dir": ""}}) is None


def test_resolve_plans_dir_env_override_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The environment override beats the payload's project dir."""
    monkeypatch.setenv(render._PLANS_DIR_ENV, str(tmp_path / "override"))
    payload = {"workspace": {"project_dir": str(tmp_path / "ignored")}}
    assert render._resolve_plans_dir(payload) == tmp_path / "override"


def test_resolve_plans_dir_project_local_canonical_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The resolver always points at the sole canonical ``.apothem/plans`` tree,
    # even when nothing exists on disk yet. A legacy ``.plans`` tree is never
    # resolved — operators upgrade it via ``apothem migrate-workspace``.
    """The resolver points at the canonical plans tree.

    It does so even when nothing exists on disk yet, and the legacy tree is
    never resolved.
    """
    monkeypatch.delenv(render._PLANS_DIR_ENV, raising=False)
    payload = {"workspace": {"project_dir": str(tmp_path)}}
    assert render._resolve_plans_dir(payload) == tmp_path / ".apothem" / "plans"


def test_resolve_plans_dir_project_local_canonical_preferred(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # When the canonical ``.apothem/plans`` tree exists on disk, the resolver
    # points at it — the sole canonical project-local plans location.
    """An existing canonical plans tree resolves to itself."""
    monkeypatch.delenv(render._PLANS_DIR_ENV, raising=False)
    (tmp_path / ".apothem" / "plans").mkdir(parents=True)
    payload = {"workspace": {"project_dir": str(tmp_path)}}
    assert render._resolve_plans_dir(payload) == tmp_path / ".apothem" / "plans"


def test_resolve_plans_dir_cwd_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No payload → the current working directory is the base; the resolver
    # points at the canonical ``.apothem/plans`` tree under it.
    """With no payload the working directory is the base.

    The canonical plans tree is resolved beneath it.
    """
    monkeypatch.delenv(render._PLANS_DIR_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    assert render._resolve_plans_dir({}) == tmp_path / ".apothem" / "plans"


def test_resolve_plans_dir_never_uses_harness_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Guard the agnosticism fix: no resolution path may reach a harness
    # config root such as ``~/.claude/.plans``.
    """No resolution path may reach a harness config root."""
    monkeypatch.delenv(render._PLANS_DIR_ENV, raising=False)
    resolved = render._resolve_plans_dir({"workspace": {"project_dir": "/p"}})
    assert ".claude" not in resolved.parts
