# SPDX-License-Identifier: MIT

"""Unit tests for scripts/release/extract_release_notes.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "release"))

import extract_release_notes  # noqa: E402,I001


SAMPLE_CHANGELOG = """\
# Changelog

All notable changes recorded here.

## [Unreleased]

### Added

- Pending features.

## [1.2.3] - 2026-04-28

### Added

- New CI pipeline with ten check classes.
- Documentation site under docs/.

### Fixed

- Workflow SHA-pinning audit doc.

## [1.2.2] - 2026-04-15

### Added

- Earlier release content.
"""


def test_extract_section_returns_body_between_headers() -> None:
    body = extract_release_notes.extract_section(SAMPLE_CHANGELOG, "1.2.3")
    assert "New CI pipeline with ten check classes." in body
    assert "Documentation site under docs/." in body
    assert "Workflow SHA-pinning audit doc." in body
    # Boundary discipline.
    assert "Earlier release content." not in body
    assert "Pending features." not in body
    # Header line itself is not part of the body.
    assert "## [1.2.3]" not in body


def test_extract_section_strips_outer_whitespace() -> None:
    body = extract_release_notes.extract_section(SAMPLE_CHANGELOG, "1.2.3")
    assert body.endswith("\n")
    assert not body.startswith("\n")


def test_extract_section_unknown_version_raises() -> None:
    with pytest.raises(ValueError, match=r"no '## \[9\.9\.9\]' section"):
        extract_release_notes.extract_section(SAMPLE_CHANGELOG, "9.9.9")


def test_main_writes_output_file(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(SAMPLE_CHANGELOG, encoding="utf-8")
    output = tmp_path / "release-notes.md"

    rc = extract_release_notes.main(
        [
            "--version",
            "1.2.3",
            "--changelog",
            str(changelog),
            "--output",
            str(output),
        ]
    )

    assert rc == 0
    assert output.exists()
    body = output.read_text(encoding="utf-8")
    assert "New CI pipeline with ten check classes." in body


def test_main_returns_nonzero_when_changelog_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = extract_release_notes.main(
        [
            "--version",
            "1.0.0",
            "--changelog",
            str(tmp_path / "missing.md"),
            "--output",
            str(tmp_path / "out.md"),
        ]
    )
    assert rc == 2
    assert "changelog not found" in capsys.readouterr().err


def test_main_returns_nonzero_when_version_absent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(SAMPLE_CHANGELOG, encoding="utf-8")
    output = tmp_path / "out.md"

    rc = extract_release_notes.main(
        [
            "--version",
            "9.9.9",
            "--changelog",
            str(changelog),
            "--output",
            str(output),
        ]
    )
    assert rc == 1
    assert "no '## [9.9.9]'" in capsys.readouterr().err
    assert not output.exists()
