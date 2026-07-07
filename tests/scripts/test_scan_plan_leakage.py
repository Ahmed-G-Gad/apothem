# SPDX-License-Identifier: MIT

"""Tests for ``apothem.audit.scan_plan_leakage``.

Coverage:

1. Each leakage category fires on a positive sample.
2. Each leakage category does not fire on a tight negative sample where
   the regex's narrowness matters (natural-English ``phase`` noun;
   bare ``rerun`` verb; SemVer triples without context).
3. The scanner self-skips its own source file in inventory mode.
4. The ad-hoc ``--path`` mode emits valid JSON under ``--format json``.
5. ``--exclude`` honors a glob in ad-hoc mode.
6. ``CHANGELOG.md`` is exempt at the file level.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AUDIT_DIR = _REPO_ROOT / "src" / "apothem" / "audit"
for _p in (_AUDIT_DIR,):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import scan_plan_leakage as splm  # noqa: E402

# ---------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------


def _scan_text(text: str, rel: str = "sample.md") -> list[splm.Hit]:
    """Run the per-line scan family against a synthetic text body."""
    hits: list[splm.Hit] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        hits.extend(splm._scan_line(rel, lineno, line))
    return hits


def _signals(hits: list[splm.Hit]) -> set[str]:
    """Return the set of signal-kind prefixes across a hit list."""
    return {h.signal.split(":", 1)[0] for h in hits}


# ---------------------------------------------------------------------
# Per-category positive samples.
# ---------------------------------------------------------------------


def test_stage_label_positive() -> None:
    hits = _scan_text("Phase 13 introduces the leakage sweep.")
    assert any(h.signal.startswith("stage-label") for h in hits)


def test_plan_artifact_filename_positive() -> None:
    hits = _scan_text("See PROGRESS.md for the current status.")
    assert any(h.signal.startswith("plan-artifact-filename") for h in hits)


def test_plan_directory_token_positive() -> None:
    hits = _scan_text("Working notes land in _inputs/ during draft.")
    assert any(h.signal.startswith("plan-directory-token") for h in hits)


def test_restage_verb_positive() -> None:
    hits = _scan_text("On failure, re-execute the verification step.")
    assert any(h.signal.startswith("restage-verb") for h in hits)


def test_predecessor_brand_positive() -> None:
    hits = _scan_text("The ClaudeLoom rename happened earlier.")
    assert any(h.signal.startswith("predecessor-brand") for h in hits)


def test_hardening_contextual_positive() -> None:
    hits = _scan_text("The hardening suite ratified COMPLETE.")
    assert any(h.signal.startswith("hardening-context") for h in hits)


def test_plan_suite_slug_positive() -> None:
    slug = "-".join(("apothem", "v9.9.9", "launch"))
    hits = _scan_text(f"Pointer: ~/.claude/.plans/{slug}/PREAMBLE.md.")
    assert any(h.signal.startswith("plan-suite-slug") for h in hits)


def test_mandate_id_positive() -> None:
    hits = _scan_text("Per CM-7 codebase isolation, strip the term.")
    assert any(h.signal.startswith("plan-internal-id") for h in hits)


def test_user_confirm_placeholder_positive() -> None:
    hits = _scan_text("Resolve <USER-CONFIRM:scope-direction> first.")
    assert any(h.signal.startswith("unfilled-user-confirm") for h in hits)


def test_audit_finding_id_positive() -> None:
    hits = _scan_text("Finding F042 was filed against the matcher.")
    assert any(h.signal.startswith("plan-internal-id") for h in hits)


# ---------------------------------------------------------------------
# Negative samples (tight scoping).
# ---------------------------------------------------------------------


def test_lowercase_phase_in_prose_does_not_fire() -> None:
    """Bare ``phase`` as natural English noun must not match."""
    hits = _scan_text(
        "The moon enters a new phase each lunar cycle; this phase of work is complete."
    )
    assert not any(h.signal.startswith("stage-label") for h in hits)


def test_bare_rerun_does_not_fire() -> None:
    """``rerun`` as natural verb must not match the re-stage family."""
    hits = _scan_text("On flake, rerun the test once before bisecting.")
    assert not any(h.signal.startswith("restage-verb") for h in hits)


def test_hardening_without_planning_context_does_not_fire() -> None:
    """``hardening`` as natural noun must not match alone."""
    hits = _scan_text("Hardening the supply chain reduces attack surface.")
    assert not any(h.signal.startswith("hardening-context") for h in hits)


def test_natural_M_token_does_not_fire() -> None:
    """``M`` in a sentence must not match without the digit prefix."""
    hits = _scan_text("Vitamin M is essential. Section M describes the schema.")
    assert not any(h.signal.startswith("plan-internal-id") for h in hits)


# ---------------------------------------------------------------------
# Exemptions.
# ---------------------------------------------------------------------


def test_self_filename_is_exempt() -> None:
    """The scanner skips its own source file even when content matches."""
    assert splm._is_exempt("src/apothem/audit/scan_plan_leakage.py")
    assert splm._is_exempt("anywhere/scan_plan_leakage.py")


def test_changelog_is_exempt() -> None:
    """CHANGELOG.md is file-level exempt from the sweep."""
    assert splm._is_exempt("CHANGELOG.md")
    assert splm._is_exempt("docs/CHANGELOG.md")


# ---------------------------------------------------------------------
# Path-mode CLI.
# ---------------------------------------------------------------------


def test_path_mode_json_output_is_valid(tmp_path: Path) -> None:
    """``--path ... --format json`` emits parseable JSON to stdout."""
    sample = tmp_path / "doc.md"
    sample.write_text(
        "Phase 1 starts here.\nSee PROGRESS.md.\n",
        encoding="utf-8",
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = splm.main(["--path", str(tmp_path), "--format", "json"])
    assert rc == 0

    payload = json.loads(buf.getvalue())
    assert payload["scanner"] == "scan_plan_leakage"
    assert payload["hit-count"] >= 2
    assert isinstance(payload["hits"], list)


def test_path_mode_exclude_glob_honours(tmp_path: Path) -> None:
    """``--exclude`` skips files matching the glob."""
    keep = tmp_path / "keep.md"
    skip = tmp_path / "skip.md"
    keep.write_text("Phase 1 here.\n", encoding="utf-8")
    skip.write_text("Phase 1 here too.\n", encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = splm.main(
            [
                "--path",
                str(tmp_path),
                "--format",
                "json",
                "--exclude",
                "skip.md",
            ]
        )
    assert rc == 0
    payload = json.loads(buf.getvalue())
    files = {h["file"] for h in payload["hits"]}
    assert any("keep.md" in f for f in files)
    assert not any("skip.md" in f for f in files)


def test_path_mode_text_format(tmp_path: Path) -> None:
    """Default text format emits one-line-per-hit."""
    sample = tmp_path / "doc.md"
    sample.write_text("Phase 1 here.\n", encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = splm.main(["--path", str(tmp_path)])
    assert rc == 0
    out = buf.getvalue().strip().splitlines()
    assert any("stage-label" in line for line in out)


def test_path_mode_missing_path_returns_error(tmp_path: Path) -> None:
    """Non-existent path under ``--path`` returns exit code 1."""
    rc = splm.main(["--path", str(tmp_path / "missing")])
    assert rc == 1


def test_inventory_mode_missing_inventory_returns_error(
    tmp_path: Path,
) -> None:
    """Missing inventory triggers a non-zero exit with diagnostic."""
    rc = splm.main(
        [
            "--inventory",
            str(tmp_path / "no-such-inventory.json"),
            "--root",
            str(tmp_path),
            "--output",
            str(tmp_path / "out.json"),
        ]
    )
    assert rc == 1


# ---------------------------------------------------------------------
# Integration: scanner does not flag itself when walked.
# ---------------------------------------------------------------------


def test_scanner_self_skip_when_walked(tmp_path: Path) -> None:
    """Walk the audit dir; the scanner's own source must not appear."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = splm.main(
            [
                "--path",
                str(_AUDIT_DIR),
                "--format",
                "json",
            ]
        )
    assert rc == 0
    payload = json.loads(buf.getvalue())
    files = {h["file"] for h in payload["hits"]}
    assert not any("scan_plan_leakage.py" in f for f in files)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
