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
    text = "- **Active phase:** Phase 03A-discovery — mapping the surface\n"
    assert render._extract_phase_pointer(text) == "Phase 03A-discovery"


def test_extract_phase_pointer_in_progress_fallback() -> None:
    text = "- **Phase in progress:** Phase 07-release\n"
    assert render._extract_phase_pointer(text) == "Phase 07-release"


def test_extract_phase_pointer_truncates_overlong() -> None:
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
    assert render._extract_phase_pointer("no phase field here\n") is None


# --- _extract_sprint_goal ---------------------------------------------------


def _suite_with_phase(tmp_path: Path, *, phase_dir: str, phase_md_body: str) -> Path:
    phases = tmp_path / "phases" / phase_dir
    phases.mkdir(parents=True)
    (phases / "PHASE.md").write_text(phase_md_body, encoding="utf-8")
    return tmp_path


def test_extract_sprint_goal_none_pointer() -> None:
    assert render._extract_sprint_goal(Path("/nonexistent"), None) is None


def test_extract_sprint_goal_non_phase_pointer() -> None:
    assert render._extract_sprint_goal(Path("/nonexistent"), "Ad-hoc work") is None


def test_extract_sprint_goal_no_phases_dir(tmp_path: Path) -> None:
    assert render._extract_sprint_goal(tmp_path, "Phase 01-foo") is None


def test_extract_sprint_goal_no_matching_phase_dir(tmp_path: Path) -> None:
    (tmp_path / "phases" / "99-other").mkdir(parents=True)
    assert render._extract_sprint_goal(tmp_path, "Phase 01-foo") is None


def test_extract_sprint_goal_phase_md_missing(tmp_path: Path) -> None:
    (tmp_path / "phases" / "01-foo").mkdir(parents=True)
    assert render._extract_sprint_goal(tmp_path, "Phase 01-foo") is None


def test_extract_sprint_goal_extracted(tmp_path: Path) -> None:
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
    suite = _suite_with_phase(
        tmp_path, phase_dir="01-foo", phase_md_body="## Tasks\n- do the thing\n"
    )
    assert render._extract_sprint_goal(suite, "Phase 01-foo") is None


# --- _count_unresolved_inquiries -------------------------------------------


def test_count_unresolved_inquiries_counts_concrete_only(tmp_path: Path) -> None:
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
    (tmp_path / "x.md").write_text("nothing to confirm here\n", encoding="utf-8")
    assert render._count_unresolved_inquiries(tmp_path) == 0


# --- _most_recent_suite -----------------------------------------------------


def test_most_recent_suite_no_plans_dir(tmp_path: Path) -> None:
    assert render._most_recent_suite(tmp_path / "absent") is None


def test_most_recent_suite_empty(tmp_path: Path) -> None:
    assert render._most_recent_suite(tmp_path) is None


def test_most_recent_suite_returns_newest(tmp_path: Path) -> None:
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
    assert render.gather(tmp_path) is None


def test_gather_suite_without_progress(tmp_path: Path) -> None:
    (tmp_path / "suite").mkdir()
    parts = render.gather(tmp_path)
    assert parts == render.StatuslineParts(
        phase_pointer=None, sprint_goal=None, inquiry_count=0
    )


def test_gather_full_suite(tmp_path: Path) -> None:
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
    raw = "Phase 1 — “Goal” … done·now"
    assert render._ascii_safe(raw) == 'Phase 1 - "Goal" ... done*now'


def test_ascii_safe_drops_unmapped_non_ascii() -> None:
    # é and 中文 are unmapped → dropped; the surrounding ASCII spaces survive.
    assert render._ascii_safe("café 中文 x") == "caf  x"


# --- render -----------------------------------------------------------------


def test_render_none_parts() -> None:
    assert render.render(None) == "[no active suite]"


def test_render_full_parts_plural() -> None:
    parts = render.StatuslineParts(
        phase_pointer="Phase 02-auth", sprint_goal="Ship login", inquiry_count=3
    )
    assert render.render(parts) == "[Phase 02-auth | Ship login | 3 inquiries]"


def test_render_singular_inquiry() -> None:
    parts = render.StatuslineParts(
        phase_pointer=None, sprint_goal=None, inquiry_count=1
    )
    assert render.render(parts) == "[1 inquiry]"


def test_render_zero_inquiries_only() -> None:
    parts = render.StatuslineParts(
        phase_pointer=None, sprint_goal=None, inquiry_count=0
    )
    assert render.render(parts) == "[0 inquiries]"


# --- main -------------------------------------------------------------------


def test_main_no_suite_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(render, "_read_payload", lambda: {})
    monkeypatch.setattr(render, "_resolve_plans_dir", lambda payload: tmp_path)
    assert render.main() == 0
    assert capsys.readouterr().out.strip() == "[no active suite]"


def test_main_never_raises_on_internal_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _boom(plans_dir: Path) -> render.StatuslineParts | None:
        raise RuntimeError("synthetic")

    monkeypatch.setattr(render, "_read_payload", lambda: {})
    monkeypatch.setattr(render, "gather", _boom)
    assert render.main() == 0
    assert capsys.readouterr().out.strip() == "[statusline error: RuntimeError]"


# --- _parse_payload / _payload_project_dir / _resolve_plans_dir -------------


def test_parse_payload_blank_returns_empty() -> None:
    assert render._parse_payload("   \n") == {}


def test_parse_payload_malformed_returns_empty() -> None:
    assert render._parse_payload("{not json") == {}


def test_parse_payload_non_object_returns_empty() -> None:
    assert render._parse_payload("[1, 2, 3]") == {}


def test_parse_payload_valid_object() -> None:
    assert render._parse_payload('{"workspace": {"project_dir": "/x"}}') == {
        "workspace": {"project_dir": "/x"}
    }


def test_payload_project_dir_present() -> None:
    payload = {"workspace": {"project_dir": "/repo"}}
    assert render._payload_project_dir(payload) == "/repo"


def test_payload_project_dir_absent() -> None:
    assert render._payload_project_dir({}) is None


def test_payload_project_dir_non_dict_workspace() -> None:
    assert render._payload_project_dir({"workspace": "oops"}) is None


def test_payload_project_dir_empty_string() -> None:
    assert render._payload_project_dir({"workspace": {"project_dir": ""}}) is None


def test_resolve_plans_dir_env_override_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(render._PLANS_DIR_ENV, str(tmp_path / "override"))
    payload = {"workspace": {"project_dir": str(tmp_path / "ignored")}}
    assert render._resolve_plans_dir(payload) == tmp_path / "override"


def test_resolve_plans_dir_project_local_canonical_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The resolver always points at the sole canonical ``.apothem/plans`` tree,
    # even when nothing exists on disk yet. A legacy ``.plans`` tree is never
    # resolved — operators upgrade it via ``apothem migrate-workspace``.
    monkeypatch.delenv(render._PLANS_DIR_ENV, raising=False)
    payload = {"workspace": {"project_dir": str(tmp_path)}}
    assert render._resolve_plans_dir(payload) == tmp_path / ".apothem" / "plans"


def test_resolve_plans_dir_project_local_canonical_preferred(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # When the canonical ``.apothem/plans`` tree exists on disk, the resolver
    # points at it — the sole canonical project-local plans location.
    monkeypatch.delenv(render._PLANS_DIR_ENV, raising=False)
    (tmp_path / ".apothem" / "plans").mkdir(parents=True)
    payload = {"workspace": {"project_dir": str(tmp_path)}}
    assert render._resolve_plans_dir(payload) == tmp_path / ".apothem" / "plans"


def test_resolve_plans_dir_cwd_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No payload → the current working directory is the base; the resolver
    # points at the canonical ``.apothem/plans`` tree under it.
    monkeypatch.delenv(render._PLANS_DIR_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    assert render._resolve_plans_dir({}) == tmp_path / ".apothem" / "plans"


def test_resolve_plans_dir_never_uses_harness_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Guard the agnosticism fix: no resolution path may reach a harness
    # config root such as ``~/.claude/.plans``.
    monkeypatch.delenv(render._PLANS_DIR_ENV, raising=False)
    resolved = render._resolve_plans_dir({"workspace": {"project_dir": "/p"}})
    assert ".claude" not in resolved.parts
