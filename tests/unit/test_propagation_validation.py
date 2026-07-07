# SPDX-License-Identifier: MIT

"""Unit tests for propagation-manifest schema validation.

_parse_manifest_text is the schema gate every propagation manifest passes
through. The install-driver / manifest suites exercise the valid manifest end
to end; these target the validation error branches directly: a non-mapping
'harnesses' block, a null harness body (skipped, not an error), a non-mapping
harness body, a non-mapping install entry, and an unknown ownership_class.
"""

from __future__ import annotations

import pytest

from apothem.lib import propagation as prop


def _parse(text: str) -> object:
    return prop._parse_manifest_text(text)


def test_missing_harnesses_key_raises() -> None:
    with pytest.raises(ValueError, match="missing the top-level 'harnesses'"):
        _parse("other: {}\n")


def test_harnesses_not_a_mapping_raises() -> None:
    with pytest.raises(ValueError, match="'harnesses' must be a mapping"):
        _parse("harnesses:\n  - a\n  - b\n")


def test_null_harness_body_is_skipped() -> None:
    # A harness mapped to null is skipped, not an error -> empty rule set.
    assert _parse("harnesses:\n  claude_code:\n") == {}


def test_non_mapping_harness_body_raises() -> None:
    with pytest.raises(ValueError, match="entry must be a mapping"):
        _parse("harnesses:\n  claude_code: just-a-string\n")


def test_non_mapping_install_entry_raises() -> None:
    with pytest.raises(ValueError, match="install entry must be a mapping"):
        _parse("harnesses:\n  claude_code:\n    install:\n      - just-a-string\n")


def test_install_entry_missing_source_raises_value_error_with_harness() -> None:
    # The documented malformed-manifest contract: ValueError carrying the
    # harness name, never a bare KeyError.
    text = "harnesses:\n  claude_code:\n    install:\n      - target: .claude/rules/\n"
    with pytest.raises(
        ValueError, match="harness 'claude_code' install entry is missing"
    ) as excinfo:
        _parse(text)
    assert "source" in str(excinfo.value)


def test_install_entry_missing_target_raises_value_error_with_harness() -> None:
    text = "harnesses:\n  claude_code:\n    install:\n      - source: rules/\n"
    with pytest.raises(
        ValueError, match="harness 'claude_code' install entry is missing"
    ) as excinfo:
        _parse(text)
    assert "target" in str(excinfo.value)


def test_unknown_ownership_class_raises() -> None:
    text = (
        "harnesses:\n"
        "  claude_code:\n"
        "    install:\n"
        "      - source: rules/\n"
        "        target: .claude/rules/\n"
        "        ownership_class: bogus-class\n"
    )
    with pytest.raises(ValueError, match="unknown ownership_class 'bogus-class'"):
        _parse(text)


def test_resolve_target_rejects_unknown_placeholder() -> None:
    from pathlib import Path

    with pytest.raises(ValueError, match="HARNES_ROOT"):
        prop.resolve_target("${HARNES_ROOT}/x", harness_root=Path("/r"))


def test_resolve_target_keeps_documented_placeholder_when_root_absent() -> None:
    resolved = prop.resolve_target("${PROJECT_ROOT}/x")
    assert "${PROJECT_ROOT}" in str(resolved)


def test_load_manifest_reads_within_extraction_context(tmp_path, monkeypatch) -> None:
    """The manifest text is read while the as_file extraction is alive.

    Simulates a zipfile distribution: the extracted file exists only inside
    the context manager and is deleted on exit. load_manifest must have
    parsed the content by then.
    """
    import contextlib
    import shutil
    from pathlib import Path

    real = Path(prop.__file__).parent / "propagation-manifest.yaml"

    @contextlib.contextmanager
    def fake_as_file(_traversable):
        temp = tmp_path / "extracted-manifest.yaml"
        shutil.copyfile(real, temp)
        try:
            yield temp
        finally:
            temp.unlink()

    monkeypatch.setattr(prop, "as_file", fake_as_file)
    prop._load_manifest_cached.cache_clear()
    try:
        rules = prop.load_manifest()
    finally:
        prop._load_manifest_cached.cache_clear()
    assert "claude_code" in rules
