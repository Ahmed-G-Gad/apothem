# SPDX-License-Identifier: MIT

"""The write-boundary check is case-fold-aware on case-insensitive volumes.

On a case-insensitive filesystem (the macOS default; Windows), a target that
differs from the allowed root only in case (``~/.Claude`` vs ``~/.claude``)
resolves to the *same* location and must be classified as inside the root —
neither falsely rejected as an escape nor used to widen the boundary on a
case-sensitive volume, where such a variant is a genuinely different directory.

These tests probe the actual filesystem case-sensitivity and assert the boundary
check agrees with it, so they pass on case-insensitive and case-sensitive
filesystems alike (every OS matrix cell, including macos-latest).
"""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared.install_driver import (
    _filesystem_is_case_insensitive,
    _validate_target_path,
    _within_allowed_root,
)


def _fs_folds_case(tmp_path: Path) -> bool:
    """Return True when *tmp_path*'s filesystem is case-insensitive."""
    probe = tmp_path / "ApothemCaseProbe"
    probe.mkdir()
    folds = (tmp_path / "apothemcaseprobe").exists()
    probe.rmdir()
    return folds


def test_exact_containment_is_within(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    assert _within_allowed_root(root / "sub" / "config.json", root) is True


def test_genuine_escape_is_rejected_regardless_of_case(tmp_path: Path) -> None:
    """Case-folding never turns an out-of-root path into an in-root one."""
    root = tmp_path / "root"
    root.mkdir()
    # A sibling that is not the same location, even though it shares a prefix.
    assert _within_allowed_root(tmp_path / "elsewhere" / "f.json", root) is False
    assert _within_allowed_root(tmp_path / "ROOT_evil" / "f.json", root) is False


def test_filesystem_probe_matches_reality(tmp_path: Path) -> None:
    assert _filesystem_is_case_insensitive(tmp_path) is _fs_folds_case(tmp_path)


def test_case_variant_within_root_classified_per_filesystem(tmp_path: Path) -> None:
    """A case variant of the root is in-root iff the filesystem folds case."""
    root = tmp_path / "AllowedRoot"
    root.mkdir()
    variant = tmp_path / "allowedroot" / "config.json"  # same letters, lower-cased
    folds = _fs_folds_case(tmp_path)

    # The pure containment helper agrees with the filesystem.
    assert _within_allowed_root(variant, root) is folds

    # ... and so does the full guard: on a case-insensitive volume the variant
    # resolves to the same location (allowed); on a case-sensitive volume it is a
    # different directory (an escape).
    result = _validate_target_path(variant, allowed_root=root, operation="write_text")
    if folds:
        assert result is None
    else:
        assert result is not None
        assert result.outcome == "error"
        assert "escapes the allowed materialization root" in result.message
