# SPDX-License-Identifier: MIT

"""Tests for scripts/dev/check_changelog_links.py.

Keep a Changelog expects every version heading to resolve to a link and the
``[Unreleased]`` link to compare from the latest release. The checker holds
CHANGELOG.md to both; these tests pin its verdicts on small samples and on the
committed file.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "release"))

import bump_version  # noqa: E402
import check_changelog_links  # noqa: E402

BASE = "https://github.com/example/project"

GOOD = f"""\
# Changelog

## [Unreleased]

## [1.1.0] - 2026-08-16

- one

## [1.0.2] - 2026-08-14

- two

[Unreleased]: {BASE}/compare/v1.1.0...HEAD
[1.1.0]: {BASE}/releases/tag/v1.1.0
[1.0.2]: {BASE}/releases/tag/v1.0.2
"""


def test_good_changelog_has_no_findings() -> None:
    assert check_changelog_links.find_problems(GOOD) == []


def test_heading_without_link_is_reported() -> None:
    text = GOOD.replace(f"[1.1.0]: {BASE}/releases/tag/v1.1.0\n", "")
    problems = check_changelog_links.find_problems(text)
    assert any("[1.1.0]" in p and "no link definition" in p for p in problems)


def test_stale_unreleased_base_is_reported() -> None:
    text = GOOD.replace("compare/v1.1.0...HEAD", "compare/v1.0.2...HEAD")
    problems = check_changelog_links.find_problems(text)
    assert any("[Unreleased]" in p and "v1.1.0" in p for p in problems)


def test_missing_unreleased_link_is_reported() -> None:
    text = GOOD.replace(f"[Unreleased]: {BASE}/compare/v1.1.0...HEAD\n", "")
    problems = check_changelog_links.find_problems(text)
    assert any("[Unreleased]" in p for p in problems)


def test_link_to_another_version_is_reported() -> None:
    text = GOOD.replace("releases/tag/v1.1.0", "releases/tag/v1.0.2")
    problems = check_changelog_links.find_problems(text)
    assert any("[1.1.0]" in p and "does not point at v1.1.0" in p for p in problems)


def test_prefix_version_does_not_satisfy_the_link() -> None:
    """A link to v1.1.0 must not count as a link to v1.1.0x or v1.1.00."""
    text = GOOD.replace("releases/tag/v1.0.2", "releases/tag/v1.0.20")
    problems = check_changelog_links.find_problems(text)
    assert any("[1.0.2]" in p for p in problems)


def test_link_without_heading_is_reported() -> None:
    text = GOOD + f"[0.9.0]: {BASE}/releases/tag/v0.9.0\n"
    problems = check_changelog_links.find_problems(text)
    assert any("[0.9.0]" in p and "no heading" in p for p in problems)


def test_committed_changelog_passes() -> None:
    assert (
        check_changelog_links.main(["--changelog", str(REPO_ROOT / "CHANGELOG.md")])
        == 0
    )


def test_cli_exit_code_on_findings(tmp_path: Path) -> None:
    bad = tmp_path / "CHANGELOG.md"
    bad.write_text(GOOD.replace("compare/v1.1.0", "compare/v1.0.2"), encoding="utf-8")
    assert check_changelog_links.main(["--changelog", str(bad)]) == 1


@pytest.mark.parametrize("version", ["1.1.1", "1.2.0", "2.0.0"])
def test_bump_version_output_passes(tmp_path: Path, version: str) -> None:
    """The release bumper leaves a changelog this checker accepts."""
    root = tmp_path / "repo"
    for rel in bump_version.anchor_files():
        src = REPO_ROOT / rel
        if src.is_file():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, root / rel)
    assert bump_version.main([version, "--root", str(root), "--no-regen"]) == 0
    assert check_changelog_links.main(["--changelog", str(root / "CHANGELOG.md")]) == 0
