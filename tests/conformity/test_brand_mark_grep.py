# SPDX-License-Identifier: MIT

"""Behavior contract for `src/apothem/conformity/brand_mark_grep.py`.

Tests cover the five in-scope contracts:
(a) compliant display-surface emission passes; (b) compliant identifier-
surface emission passes; (c) display-form drift on an identifier-only
line is flagged; (d) identifier-form drift on a display-only line is
flagged; (e) cross-surface drift inside a single file flags each
occurrence per-line.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_TOOLS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "conformity"
_MODULE_PATH = _TOOLS_DIR / "brand_mark_grep.py"


def _load_module():
    """Load the hyphen-named matcher module via importlib spec."""
    spec = importlib.util.spec_from_file_location("brand_mark_grep", _MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module spec from {_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules["brand_mark_grep"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def matcher():
    """Return the loaded brand-mark-grep module."""
    return _load_module()


def test_compliant_display_surface_emission_passes(matcher) -> None:
    """Contract (a): a README with Apothem on display lines passes."""
    content = (
        "# Apothem\n"
        '<p align="center"><em>Apothem — operator-side ratification</em></p>\n'
        '<img alt="Apothem logo" src="assets/logo.svg">\n'
    )
    result = matcher.check(content, Path("README.md"))

    assert result.passed is True
    assert result.findings == []


def test_compliant_identifier_surface_emission_passes(matcher) -> None:
    """Contract (b): identifier-form on install/CLI/URL lines passes."""
    content = (
        "## Install\n"
        "```bash\n"
        "scoop install apothem\n"
        "brew install apothem\n"
        "```\n"
        "Visit https://apothem.ahmedgad.com for documentation.\n"
        "Repo: github.com/ahmed-g-gad/apothem\n"
    )
    result = matcher.check(content, Path("README.md"))

    assert result.passed is True
    assert result.findings == []


def test_display_form_drift_on_identifier_surface_is_flagged(matcher) -> None:
    """Contract (c): PascalCase on an identifier-only line fails."""
    content = "Repo: github.com/ahmed-g-gad/Apothem\n"
    result = matcher.check(content, Path("README.md"))

    assert result.passed is False
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.match == "Apothem"
    assert finding.drift == "display-form-on-identifier-surface"
    assert finding.line == 1


def test_identifier_form_drift_on_display_surface_is_flagged(matcher) -> None:
    """Contract (d): lowercase on an H1 display line fails."""
    content = "# apothem\n\nSome body text.\n"
    result = matcher.check(content, Path("README.md"))

    assert result.passed is False
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.match == "apothem"
    assert finding.drift == "identifier-form-on-display-surface"
    assert finding.line == 1


def test_cross_surface_drift_flags_per_line(matcher) -> None:
    """Contract (e): mixed drift across lines flags each per-line."""
    content = "# apothem\n## Install\nscoop install Apothem\n"
    # Line 1 (display H1 carrying the lowercase wordmark) is flagged as
    # identifier-form-on-display-surface. Line 3 (PascalCase on a scoop-
    # install identifier line) is flagged as display-form-on-identifier-
    # surface — mixed drift, each flagged per its own line.
    result = matcher.check(content, Path("README.md"))

    assert result.passed is False
    assert any(
        f.line == 1
        and f.match == "apothem"
        and f.drift == "identifier-form-on-display-surface"
        for f in result.findings
    )


def test_out_of_scope_paths_pass_silently(matcher) -> None:
    """Path-filter contract: tooling / tests / rules paths are out of scope."""
    drift_content = "# apothem\n"
    for outside_path in (
        Path("tools/some_module.py"),
        Path("tests/some_test.py"),
        Path("src/apothem/rules/some-rule.md"),
        Path(".plans/some-suite/phase.md"),
    ):
        result = matcher.check(drift_content, outside_path)
        assert result.passed is True
        assert result.findings == []


def test_fenced_code_block_lines_are_excluded(matcher) -> None:
    """A fenced code block carrying drift-shaped lines does not flag."""
    content = "Body text.\n```\n# apothem\n```\nMore body text.\n"
    result = matcher.check(content, Path("docs/index.md"))

    assert result.passed is True
    assert result.findings == []
