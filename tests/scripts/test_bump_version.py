# SPDX-License-Identifier: MIT

"""Tests for scripts/release/bump_version.py.

A release bump touches every version-bearing manifest at once. These tests run
the bumper against a scratch copy of the repository's real anchor files and
assert three things: every anchor moves to the new version, nothing else in
those files changes, and the anchor list never falls behind the parity tests
that guard the same files.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "release"))
sys.path.insert(0, str(REPO_ROOT / "tests" / "unit"))

import bump_version  # noqa: E402
import test_manifest_version_sync  # noqa: E402

NEW = "9.8.7"
DATE = "2030-01-02"


def _scratch_repo(tmp_path: Path) -> Path:
    """Copy every file the bumper rewrites into a scratch root."""
    root = tmp_path / "repo"
    for rel in bump_version.anchor_files():
        src = REPO_ROOT / rel
        if not src.is_file():
            continue
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return root


def _get(data: object, keys: tuple[str, ...]) -> dict[str, Any]:
    node = data
    for key in keys:
        node = cast("dict[str, Any]", node)[key]
    return cast("dict[str, Any]", node)


def _run(root: Path, *extra: str) -> int:
    return bump_version.main(
        [NEW, "--root", str(root), "--no-regen", "--date", DATE, *extra]
    )


def test_anchor_list_covers_every_parity_tested_manifest() -> None:
    """Reuse the parity suite's list so the two cannot diverge."""
    anchors = set(bump_version.JSON_ANCHORS)
    for rel, keys in test_manifest_version_sync._JSON_MANIFESTS:
        assert (rel, keys) in anchors, (
            f"{rel} {keys} is parity-tested but bump_version skips it"
        )


def test_bump_rewrites_every_anchor(tmp_path: Path) -> None:
    root = _scratch_repo(tmp_path)
    assert _run(root) == 0

    for rel, keys in bump_version.JSON_ANCHORS:
        path = root / rel
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        assert _get(data, keys)["version"] == NEW, f"{rel} {keys} not bumped"

    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert f'\nversion = "{NEW}"\n' in pyproject

    citation = (root / "CITATION.cff").read_text(encoding="utf-8")
    assert citation.count(f'version: "{NEW}"') == 2
    assert citation.count(f'date-released: "{DATE}"') == 2


def test_bump_changes_nothing_but_the_version_fields(tmp_path: Path) -> None:
    """A semantic diff of each JSON anchor shows only the version keys moved."""
    root = _scratch_repo(tmp_path)

    def load(rel: str) -> object:
        # An engine pin in a JSON anchor is a version field too.
        text = (root / rel).read_text(encoding="utf-8")
        return json.loads(bump_version.NPX_PIN.sub("X.Y.Z", text))

    before = {
        rel: load(rel) for rel, _ in bump_version.JSON_ANCHORS if (root / rel).is_file()
    }
    assert _run(root) == 0
    for rel, original in before.items():
        after = load(rel)
        for anchor_rel, keys in bump_version.JSON_ANCHORS:
            if anchor_rel == rel:
                _get(after, keys)["version"] = _get(original, keys)["version"]
        assert after == original, f"{rel} changed beyond its version fields"


def test_bump_moves_every_wrapper_engine_pin(tmp_path: Path) -> None:
    """Each wrapper's npx call moves to the new version, and nothing else does."""
    root = _scratch_repo(tmp_path)
    before = {
        rel: (root / rel).read_text(encoding="utf-8")
        for rel in bump_version.NPX_PIN_ANCHORS
    }
    assert _run(root) == 0
    json_anchors = {rel for rel, _ in bump_version.JSON_ANCHORS}
    for rel, original in before.items():
        after = (root / rel).read_text(encoding="utf-8")
        assert bump_version.NPX_PIN.findall(after), rel
        assert set(bump_version.NPX_PIN.findall(after)) == {NEW}, rel
        if rel in json_anchors:
            continue  # its version field moves too; the JSON test covers it
        assert bump_version.NPX_PIN.sub("X", after) == bump_version.NPX_PIN.sub(
            "X", original
        ), f"{rel} changed beyond its npx pins"


def test_shipped_wrappers_pin_the_engine_to_their_own_version() -> None:
    """Wrappers never run an unpinned engine, so they cannot drift apart."""
    version = bump_version.current_version(REPO_ROOT)
    unpinned = re.compile(r"@ahmed-g-gad/apothem(?!@)\b")
    for rel in bump_version.NPX_PIN_ANCHORS:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert not unpinned.search(text), f"{rel} runs an unpinned engine"
        assert set(bump_version.NPX_PIN.findall(text)) == {version}, rel


def test_bump_leaves_dependency_versions_in_lockfile_alone(tmp_path: Path) -> None:
    """site/package-lock.json holds third-party packages at the same version."""
    root = _scratch_repo(tmp_path)
    lock_before = json.loads(
        (root / "site" / "package-lock.json").read_text(encoding="utf-8")
    )
    current = lock_before["version"]
    deps_at_current = sorted(
        name
        for name, meta in lock_before["packages"].items()
        if name and meta.get("version") == current
    )
    assert _run(root) == 0
    lock_after = json.loads(
        (root / "site" / "package-lock.json").read_text(encoding="utf-8")
    )
    assert lock_after["version"] == NEW
    assert lock_after["packages"][""]["version"] == NEW
    for name in deps_at_current:
        assert lock_after["packages"][name]["version"] == current, name


def test_bump_promotes_unreleased_and_updates_links(tmp_path: Path) -> None:
    root = _scratch_repo(tmp_path)
    old = bump_version.current_version(root)
    assert _run(root) == 0
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [Unreleased]\n\n## [{NEW}] - {DATE}\n" in text
    assert f"/compare/v{NEW}...HEAD" in text
    assert (
        f"[{NEW}]: https://github.com/ahmed-g-gad/apothem/releases/tag/v{NEW}" in text
    )
    assert f"/compare/v{old}...HEAD" not in text


def test_bump_adds_supported_minor_row(tmp_path: Path) -> None:
    root = _scratch_repo(tmp_path)
    assert _run(root) == 0
    security = (root / "SECURITY.md").read_text(encoding="utf-8")
    assert "| 9.8.x " in security


def test_bump_is_idempotent(tmp_path: Path) -> None:
    root = _scratch_repo(tmp_path)
    assert _run(root) == 0
    first = {
        rel: (root / rel).read_bytes()
        for rel in bump_version.anchor_files()
        if (root / rel).is_file()
    }
    assert _run(root) == 0
    second = {rel: (root / rel).read_bytes() for rel in first}
    assert first == second


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    root = _scratch_repo(tmp_path)
    before = {
        rel: (root / rel).read_bytes()
        for rel in bump_version.anchor_files()
        if (root / rel).is_file()
    }
    assert _run(root, "--dry-run") == 0
    after = {rel: (root / rel).read_bytes() for rel in before}
    assert before == after


@pytest.mark.parametrize("bad", ["1.2", "v1.2.3", "1.2.3-rc.1", "01.2.3", "1.2.x"])
def test_rejects_non_release_versions(tmp_path: Path, bad: str) -> None:
    root = _scratch_repo(tmp_path)
    assert bump_version.main([bad, "--root", str(root), "--no-regen"]) == 2


def test_rejects_a_downgrade(tmp_path: Path) -> None:
    root = _scratch_repo(tmp_path)
    assert bump_version.main(["0.0.1", "--root", str(root), "--no-regen"]) == 2


def test_rejects_a_bad_date(tmp_path: Path) -> None:
    root = _scratch_repo(tmp_path)
    assert (
        bump_version.main(
            [NEW, "--root", str(root), "--no-regen", "--date", "2030-13-40"]
        )
        == 2
    )
