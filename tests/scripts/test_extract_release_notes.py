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


def _long_body(entries_per_section: int) -> str:
    """A release body with three sections of numbered, equal-size entries."""
    parts = []
    for name in ("Added", "Fixed", "Security"):
        parts.append(f"### {name}\n")
        for n in range(entries_per_section):
            parts.append(f"- {name} entry {n:03d}.\n  " + "x" * 200 + "\n")
    return "\n".join(parts)


def test_fit_to_limit_keeps_a_body_within_the_limit_unchanged() -> None:
    body = _long_body(3)
    assert (
        extract_release_notes.fit_to_limit(
            body, "1.2.3", limit=extract_release_notes._github_length(body)
        )
        == body
    )


def test_fit_to_limit_shortens_a_long_body_and_links_the_full_notes() -> None:
    body = _long_body(20)
    limit = len(body) // 2
    fitted = extract_release_notes.fit_to_limit(body, "1.2.3", limit=limit)

    assert len(fitted) <= limit
    # Every section heading stays, in its order.
    headings = [line for line in fitted.splitlines() if line.startswith("### ")]
    assert headings == ["### Added", "### Fixed", "### Security"]
    # Entries leave from the end of a section; the first ones stay.
    for name in ("Added", "Fixed", "Security"):
        assert f"- {name} entry 000." in fitted
    # Each shortened section counts what it left out, and the counts add up.
    counts = [
        int(line.split()[1])
        for line in fitted.splitlines()
        if line.endswith("in the full notes.") and line.startswith("- ")
    ]
    kept = sum(1 for line in fitted.splitlines() if " entry " in line)
    assert counts
    assert kept + sum(counts) == 60
    assert fitted.rstrip().endswith(
        "[CHANGELOG.md](https://github.com/ahmed-g-gad/apothem/blob/v1.2.3/CHANGELOG.md)."
    )


def test_fit_to_limit_raises_when_nothing_more_can_be_left_out() -> None:
    with pytest.raises(ValueError, match="do not fit"):
        extract_release_notes.fit_to_limit(_long_body(2), "1.2.3", limit=10)


def test_every_release_in_the_changelog_fits_a_github_release_page() -> None:
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    versions = [
        line[len("## [") :].split("]", 1)[0]
        for line in text.splitlines()
        if line.startswith("## [") and not line.startswith("## [Unreleased]")
    ]
    assert versions
    for version in versions:
        body = extract_release_notes.fit_to_limit(
            extract_release_notes.extract_section(text, version), version
        )
        length = extract_release_notes._github_length(body)
        assert length <= extract_release_notes.MAX_BODY_CHARS < 125_000


def _titled_body(sections: tuple[str, ...], entries: int) -> str:
    """A release body whose entries have bold titles and long bodies."""
    parts = []
    for name in sections:
        parts.append(f"### {name}\n")
        for n in range(entries):
            parts.append(f"- **{name} title {n:03d}.** " + "y" * 300 + "\n")
    return "\n".join(parts)


def test_fit_to_limit_cuts_entries_to_their_titles_before_dropping_any() -> None:
    body = _titled_body(("Added", "Fixed"), 20)
    fitted = extract_release_notes.fit_to_limit(body, "1.2.3", limit=len(body) // 2)
    for name in ("Added", "Fixed"):
        for n in range(20):
            assert f"- **{name} title {n:03d}.**" in fitted
    assert "in the full notes." not in fitted.split("---")[0]


def test_fit_to_limit_shortens_security_only_after_every_other_section() -> None:
    body = _titled_body(("Fixed", "Security"), 20)
    # Room for Security whole and the Fixed titles, not for more.
    limit = len(body) // 2 + 1500
    fitted = extract_release_notes.fit_to_limit(body, "1.2.3", limit=limit)
    security = fitted.split("### Security", 1)[1]
    assert security.count("y" * 300) == 20
    fixed = fitted.split("### Security", 1)[0]
    assert fixed.count("y" * 300) < 20


@pytest.mark.parametrize(
    ("extra", "why"),
    [
        ("  ```sh\n  ### not a heading\n  ```\n", "code fence"),
        ("```sh\nmake\n```\n", "code fence"),
        ("#### A sub-heading\n", "not a '- ' entry"),
        ("A closing paragraph.\n", "not a '- ' entry"),
        ("1. **Numbered.** x\n2. **Next.** y\n", "not a '- ' entry"),
        ("* **Star.** x\n", "not a '- ' entry"),
        (" ### Indented heading\n", "not a '- ' entry"),
        (" - **Sibling.** x\n", "not a '- ' entry"),
        ("-   **Wide.** x\n", "not a '- ' entry"),
        (chr(0xA0) + "Paragraph after a no-break space.\n", "not a '- ' entry"),
        ("\tTabbed.\n", "not a '- ' entry"),
        ("  <!-- a comment\n", "HTML block"),
        ("  <div>\n", "HTML block"),
        ("  [ref]: https://example.com\n", "link reference definition"),
    ],
)
def test_fit_to_limit_refuses_a_shape_it_cannot_shorten_safely(
    extra: str, why: str
) -> None:
    body = _titled_body(("Fixed",), 10) + "\n" + extra + _titled_body(("Security",), 5)
    with pytest.raises(ValueError, match=why):
        extract_release_notes.fit_to_limit(body, "1.2.3", limit=len(body) // 2)


def test_fit_to_limit_leaves_any_shape_alone_when_it_fits() -> None:
    body = _titled_body(("Fixed",), 2) + "\n```sh\nmake\n```\n\n1. one\n"
    assert (
        extract_release_notes.fit_to_limit(body, "1.2.3", limit=10 * len(body)) == body
    )


def test_fit_to_limit_refuses_text_before_the_first_heading() -> None:
    body = "Intro.\n\n" + _titled_body(("Fixed",), 10)
    with pytest.raises(ValueError, match="before the first ### heading"):
        extract_release_notes.fit_to_limit(body, "1.2.3", limit=len(body) // 2)


def test_a_wrapped_line_that_starts_with_an_unknown_tag_stays_in_its_entry() -> None:
    _lead, sections = extract_release_notes._split_sections(
        "### Fixed\n\n- **One.** `apothem remove\n  <file>` now works.\n"
    )
    assert [len(e.lines) for e in sections[0].entries] == [2]
