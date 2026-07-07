# SPDX-License-Identifier: MIT

"""Specification-contract tests for the ``/plan-spec --quick`` mode.

Slash commands are markdown specifications interpreted by the Claude Code
runtime; they have no separate Python entry point, so a true end-to-end
invocation cannot be exercised from a unit test. These tests instead
verify the contract surface: every behavior the phase brief enumerates
for ``--quick`` is declared in the command file's spec, and the YAML
frontmatter ratifies the flag in its ``argument-hint``.

When the runtime later grows a programmatic invocation surface, this
file is the natural home for the corresponding end-to-end fixture
(temp-git-repo bootstrap, invocation, filesystem-state assertions); the
contract assertions below remain valid as a fast pre-flight gate.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
# The spec stage is a first-class top-level command, independently invocable
# as /plan-spec (the /plan decomposition).
COMMAND_FILE = PROJECT_ROOT / "src" / "apothem" / "commands" / "plan-spec.md"


@pytest.fixture(scope="module")
def command_text() -> str:
    """The full command-file body, read once per test module."""
    assert COMMAND_FILE.is_file(), f"command file missing at {COMMAND_FILE}"
    return COMMAND_FILE.read_text(encoding="utf-8")


def test_argument_hint_declares_quick_flag(command_text: str) -> None:
    """The ``argument-hint`` frontmatter field carries ``--quick``."""
    match = re.search(r'^argument-hint:\s*"([^"]+)"', command_text, re.MULTILINE)
    assert match is not None, "argument-hint field missing from frontmatter"
    hint = match.group(1)
    assert "--quick" in hint, f"--quick flag absent from argument-hint: {hint!r}"
    assert "--tag" in hint, f"--tag flag absent from argument-hint: {hint!r}"


def test_inputs_table_lists_quick_and_tag_rows(command_text: str) -> None:
    """The Inputs table carries dedicated ``--quick`` and ``--tag`` rows."""
    assert re.search(r"\|\s*`--quick <slug>`\s*\|", command_text), (
        "Inputs table missing the --quick row"
    )
    assert re.search(r"\|\s*`--tag <tag>`\s*\|", command_text), (
        "Inputs table missing the --tag row"
    )


def test_quick_mode_section_present(command_text: str) -> None:
    """A dedicated section spells out the ``--quick`` mode behavior."""
    assert "## Mode: `--quick` (Lightweight Plan-Local Write)" in command_text, (
        "Mode section heading absent"
    )
    assert "### Behavior" in command_text, "Behavior subsection absent"
    assert "### Mutual Exclusivity" in command_text, (
        "Mutual Exclusivity subsection absent"
    )


def test_quick_mode_specifies_project_root_walk(command_text: str) -> None:
    """The mode section names the upward ``.git/`` walk discipline."""
    assert ".git/" in command_text, ".git/ marker absent from --quick spec"
    assert "walk upward" in command_text.lower(), "upward-walk discipline not specified"


def test_quick_mode_refuses_global_paths(command_text: str) -> None:
    """The mode section refuses paths under ``~/.claude/`` and global locations."""
    refusal_markers = ("~/.claude/", "global-ecosystem")
    for marker in refusal_markers:
        assert marker in command_text, (
            f"global-path refusal marker {marker!r} absent from --quick spec"
        )


def test_quick_mode_specifies_filename_pattern(command_text: str) -> None:
    """The mode section codifies the ``YYYY-MM-DD--<kebab-slug>.md`` pattern."""
    assert "<YYYY-MM-DD>--<kebab-slug>.md" in command_text, (
        "filename pattern not specified verbatim"
    )
    assert "kebab-case" in command_text, "kebab-case slug validation not declared"


def test_quick_mode_specifies_gitignore_augmentation(command_text: str) -> None:
    """The mode section declares the canonical ``.gitignore`` snippet append."""
    assert ".gitignore" in command_text, ".gitignore augmentation not specified"
    assert "canonical snippet" in command_text, "canonical-snippet wording absent"


def test_quick_mode_declares_frontmatter_required_fields(command_text: str) -> None:
    """The mode section enumerates the required plan-file frontmatter fields."""
    required = ("name", "created", "project", "status", "tags")
    for field in required:
        assert f"`{field}`" in command_text, (
            f"required frontmatter field `{field}` not declared in --quick spec"
        )


def test_quick_mode_declares_banner_exemption(command_text: str) -> None:
    """The mode section affirms that ``--quick`` plan files are banner-exempt."""
    assert "banner-exempt" in command_text.lower() or "banner-exempt" in command_text
    assert "src/apothem/schemas/header-exceptions.txt" in command_text, (
        "banner-exemption rationale path absent"
    )


def test_quick_mode_declares_metadata_only_output(command_text: str) -> None:
    """The mode section confirms metadata-only stdout (no body echo)."""
    assert "metadata-only" in command_text.lower() or (
        "absolute destination path" in command_text
        and "resolved project root" in command_text
        and "chosen filename" in command_text
    ), "metadata-only output contract not specified"


def test_quick_mode_mutual_exclusivity_with_forge(command_text: str) -> None:
    """The mode section declares mutual exclusivity with Forge mode."""
    assert "mutually exclusive" in command_text.lower(), (
        "mutual-exclusivity wording absent"
    )
    assert "--refine-existing" in command_text, (
        "mutual exclusivity with --refine-existing not declared"
    )


def test_foundational_stanzas_present(command_text: str) -> None:
    """All four foundational stanzas inherited from CLAUDE.md §5 are present."""
    stanzas = (
        "### Refusal & Escalation",
        "### Output Surface",
        "### File-Authoring Contract",
        "### Structured Inquiry on Ambiguity",
    )
    for stanza in stanzas:
        assert stanza in command_text, f"foundational stanza missing: {stanza!r}"


def test_frontmatter_version_bumped(command_text: str) -> None:
    """The frontmatter carries the release version and a current date."""
    assert re.search(r'^version:\s*"0\.1\.0"', command_text, re.MULTILINE), (
        "version field does not carry the release version 0.1.0"
    )
    assert re.search(r'^updated:\s*"2026-06-10"', command_text, re.MULTILINE), (
        "updated field not refreshed to 2026-06-10"
    )


def test_canonical_authorship_banner_intact(command_text: str) -> None:
    """The canonical SPDX header survives below command frontmatter."""
    assert command_text.startswith("---\n"), (
        "command frontmatter must remain byte-first"
    )
    frontmatter_end = command_text.index("\n---\n", 4)
    near_head = command_text[frontmatter_end : frontmatter_end + 300]
    assert "\n\n<!-- SPDX-License-Identifier: MIT -->" in near_head, (
        "HTML-form SPDX header missing below frontmatter"
    )
