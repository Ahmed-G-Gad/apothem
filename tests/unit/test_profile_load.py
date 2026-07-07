# SPDX-License-Identifier: MIT

"""Unit tests for profile-file loading error and edge paths.

The model / migration / projection suites cover the happy path and schema
validation; these target the file-loading branches in ``load_profile_file`` that
those suites do not reach: a missing file, an unreadable path (OSError), invalid
YAML, an empty document (``None`` coerced to ``{}``), and a non-mapping top-level
document. Each asserts the specific actionable diagnostic code the loader emits.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.lib.profile import ProfileValidationError, load_profile_file


def _write(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "profile.yaml"
    target.write_text(body, encoding="utf-8")
    return target


def test_missing_file_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(ProfileValidationError) as exc:
        load_profile_file(tmp_path / "absent.yaml")
    assert exc.value.diagnostic.code == "profile.not_found"


def test_unreadable_path_raises_read_failed(tmp_path: Path) -> None:
    # A directory at the profile path exists but cannot be read_text()'d ->
    # OSError (IsADirectoryError / PermissionError) -> profile.read_failed.
    directory = tmp_path / "profile.yaml"
    directory.mkdir()
    with pytest.raises(ProfileValidationError) as exc:
        load_profile_file(directory)
    assert exc.value.diagnostic.code == "profile.read_failed"


def test_invalid_yaml_raises_yaml_invalid(tmp_path: Path) -> None:
    path = _write(tmp_path, "identity: [unclosed\n")
    with pytest.raises(ProfileValidationError) as exc:
        load_profile_file(path)
    assert exc.value.diagnostic.code == "profile.yaml_invalid"


def test_empty_document_coerced_to_mapping_then_fails_validation(
    tmp_path: Path,
) -> None:
    # An empty file parses to None and is coerced to {}; that empty mapping then
    # fails schema validation for the missing required identity rather than
    # crashing on the None document.
    path = _write(tmp_path, "")
    with pytest.raises(ProfileValidationError):
        load_profile_file(path)


def test_non_mapping_document_raises_type_invalid(tmp_path: Path) -> None:
    path = _write(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(ProfileValidationError) as exc:
        load_profile_file(path)
    assert exc.value.diagnostic.code == "profile.type_invalid"
    # The non-mapping document is redacted into the diagnostic's safe_value.
    assert exc.value.diagnostic.safe_value is not None
