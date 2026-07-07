# SPDX-License-Identifier: MIT

"""Intent-level guarantees for the ``diff`` preview renderer.

The behavior-diff golden freezes the exact default-mode text byte-for-byte; this
test pins the *intent* the renderer must keep across any future regen: plain-
language action labels in place of internal op-kind tokens, a coherent
prospective status word ("would create" for a fresh target, never the
contradictory "skipped"), no-op targets hidden by default and restored under
``--verbose``, and the raw machine vocabulary preserved unchanged in the
``--json`` channel.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import _cli_oracle as oracle

_HARNESS = "claude-code"
_RAW_KINDS = ("sweep_stale", "write_text", "merge_tree_entries", "command_skills")


def _capture(tmp_path: Path, slug: str, argv: list[str]) -> dict[str, Any]:
    """Capture one ``diff`` invocation in an isolated home and return its record."""
    oracle.capture_one(tmp_path, slug, argv, seed_profile=True)
    record: dict[str, Any] = json.loads(
        (tmp_path / f"{slug}.json").read_text(encoding="utf-8")
    )
    assert record["exit_code"] == 0, record["stdout"]
    return record


def test_default_uses_human_labels_not_raw_kinds(tmp_path: Path) -> None:
    out = _capture(tmp_path, "default", ["diff", "--harness", _HARNESS])["stdout"]
    assert "Write file" in out
    assert "Merge directory" in out
    assert "Install skills" in out
    for kind in _RAW_KINDS:
        assert kind not in out, f"raw op-kind {kind!r} leaked into the default preview"


def test_default_status_is_coherent_not_skipped(tmp_path: Path) -> None:
    out = _capture(tmp_path, "status", ["diff", "--harness", _HARNESS])["stdout"]
    # An isolated home has no prior install, so every target would be created.
    assert "would create" in out
    assert "(skipped)" not in out
    assert "(unchanged)" not in out


def test_default_hides_no_op_targets(tmp_path: Path) -> None:
    out = _capture(tmp_path, "noop", ["diff", "--harness", _HARNESS])["stdout"]
    # On a fresh install every stale-sweep target is a no-op; none should show.
    assert "Prune stale files" not in out
    assert "no change" not in out


def test_verbose_restores_full_plan_and_raw_kinds(tmp_path: Path) -> None:
    out = _capture(tmp_path, "verbose", ["diff", "--harness", _HARNESS, "--verbose"])[
        "stdout"
    ]
    assert "Prune stale files" in out
    assert "(no change)" in out
    assert "[sweep_stale/unchanged]" in out
    assert "[write_text/created]" in out


def test_json_channel_keeps_raw_operation_and_outcome(tmp_path: Path) -> None:
    record = _capture(tmp_path, "json", ["diff", "--harness", _HARNESS, "--json"])
    results = record["json"]["results"]
    operations = {row["operation"] for row in results}
    outcomes = {row["outcome"] for row in results}
    assert "write_text" in operations
    assert "sweep_stale" in operations
    # An isolated home prospects every install entry as "created" (raw outcome
    # preserved in the contract); the renderer maps it to "would create".
    assert "created" in outcomes
    # The friendly labels are a presentation concern only — never in the contract.
    assert "Write file" not in operations
