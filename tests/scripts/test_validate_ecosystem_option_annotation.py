# SPDX-License-Identifier: MIT

"""Tests for validate_ecosystem option-annotation per-option Recommended bind.

The canonical postfix is capital ``(Recommended)`` per
``rules/interactive-questions-canonical-shapes.md`` §2.1; the lowercase form is
the banned variant. The validator enforces the per-option bidirectional bind
(label↔body) plus single-select cardinality (heuristic H6).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "dev" / "validate_ecosystem.py"


def _run_option_annotation(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--root",
            str(root),
            "--check",
            "option-annotation",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _write_commands(tmp_path: Path, name: str, lines: list[str]) -> None:
    commands = tmp_path / "commands"
    commands.mkdir(exist_ok=True)
    (commands / name).write_text("\n".join(lines), encoding="utf-8")


def test_multiselect_allows_multiple_recommended_options(tmp_path: Path) -> None:
    """A non-exclusive question can recommend multiple independent options."""
    _write_commands(
        tmp_path,
        "multi.md",
        [
            "structured inquiry: question `Which add-ons should ship?`",
            "- `Exporter (Recommended)`: rationale: Adds metrics.",
            "  recommendation: recommended — observed-state: metrics are enabled.",
            "  default-pointer: no-default: user decision required.",
            "- `Audit trail (Recommended)`: rationale: Adds event retention.",
            "  recommendation: recommended — observed-state: audit is required.",
            "  default-pointer: no-default: user decision required.",
            "multiSelect: true",
        ],
    )

    result = _run_option_annotation(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Option annotation clean" in result.stdout


def test_single_select_rejects_multiple_recommended_options(tmp_path: Path) -> None:
    """A mutually exclusive question keeps the one-recommended cap."""
    _write_commands(
        tmp_path,
        "single.md",
        [
            "structured inquiry: question `Which path should execute?`",
            "- `Patch (Recommended)`: rationale: Applies a narrow edit.",
            "  recommendation: recommended — observed-state: patch is small.",
            "  default-pointer: Patch — reversible change.",
            "- `Rewrite (Recommended)`: rationale: Replaces the module.",
            "  recommendation: recommended — observed-state: rewrite is complete.",
            "  default-pointer: Patch — reversible change.",
            "multiSelect: false",
        ],
    )

    result = _run_option_annotation(tmp_path)

    assert result.returncode == 1
    assert "H6 (label-postfix mismatch)" in result.stdout


def test_lowercase_postfix_is_rejected(tmp_path: Path) -> None:
    """The lowercase (recommended) variant is no longer canonical."""
    _write_commands(
        tmp_path,
        "lower.md",
        [
            "structured inquiry: question `Which path should execute?`",
            "- `Patch (recommended)`: rationale: Applies a narrow edit.",
            "  recommendation: recommended — observed-state: patch is small.",
            "  default-pointer: Patch — reversible change.",
            "- `Rewrite`: rationale: Replaces the module.",
            "  recommendation: discouraged — observed-state: rewrite is large.",
            "  default-pointer: Patch — reversible change.",
            "multiSelect: false",
        ],
    )

    result = _run_option_annotation(tmp_path)

    assert result.returncode == 1
    assert "H6 (label-postfix mismatch)" in result.stdout


def test_spurious_postfix_on_non_recommended_body_is_rejected(
    tmp_path: Path,
) -> None:
    """A capital postfix on a non-recommended option is a bind violation."""
    _write_commands(
        tmp_path,
        "spurious.md",
        [
            "structured inquiry: question `Which path should execute?`",
            "- `Patch (Recommended)`: rationale: Applies a narrow edit.",
            "  recommendation: recommended — observed-state: patch is small.",
            "  default-pointer: Patch — reversible change.",
            "- `Override (Recommended)`: rationale: Proceeds despite the gap.",
            "  recommendation: discouraged — observed-state: dependency unmet.",
            "  default-pointer: Patch — reversible change.",
            "multiSelect: false",
        ],
    )

    result = _run_option_annotation(tmp_path)

    assert result.returncode == 1
    assert "H6 (label-postfix mismatch)" in result.stdout


def test_canonical_single_recommended_passes(tmp_path: Path) -> None:
    """One capital-postfix recommended option in a single-select set passes."""
    _write_commands(
        tmp_path,
        "clean.md",
        [
            "structured inquiry: question `Which path should execute?`",
            "- `Patch (Recommended)`: rationale: Applies a narrow edit.",
            "  recommendation: recommended — observed-state: patch is small.",
            "  default-pointer: Patch — reversible change.",
            "- `Rewrite`: rationale: Replaces the module.",
            "  recommendation: discouraged — observed-state: rewrite is large.",
            "  default-pointer: Patch — reversible change.",
            "multiSelect: false",
        ],
    )

    result = _run_option_annotation(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Option annotation clean" in result.stdout
