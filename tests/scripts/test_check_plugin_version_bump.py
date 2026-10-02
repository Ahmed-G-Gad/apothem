# SPDX-License-Identifier: MIT

"""Tests for scripts/release/check_plugin_version_bump.py.

Claude Code keeps a plugin user on the cached copy until the manifest
``version`` string changes. These tests build throwaway git repositories that
model a marketplace plus a plugin package, tag a release, change things, and
assert the checker's verdict: content that moved after the last tag without a
version change fails; everything else passes or skips with a reason.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "release"))

import check_plugin_version_bump as check  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")

_GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        env=_GIT_ENV,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _layout(root: Path, *, source: str, version: str) -> None:
    """Write a marketplace pointing at *source* and a manifest at *version*."""
    _write_json(
        root / ".claude-plugin" / "marketplace.json",
        {"name": "m", "plugins": [{"name": "apothem", "source": source}]},
    )
    plugin_root = root / source
    _write_json(
        plugin_root / ".claude-plugin" / "plugin.json",
        {"name": "apothem", "version": version},
    )
    (plugin_root / "commands").mkdir(parents=True, exist_ok=True)


def _commit(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "--no-gpg-sign", "-m", message)


def _set_version(root: Path, source: str, version: str) -> None:
    manifest = root / source / ".claude-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["version"] = version
    _write_json(manifest, data)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _layout(root, source="./plugins/claude-code", version="1.0.0")
    (root / "plugins" / "claude-code" / "commands" / "a.md").write_text("a\n")
    (root / "README.md").write_text("readme\n")
    _commit(root, "initial")
    return root


def _run(root: Path, *extra: str) -> int:
    return check.main(["--root", str(root), *extra])


def test_skips_without_a_release_tag(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(repo) == 0
    assert "skipped" in capsys.readouterr().out


def test_passes_when_plugin_content_is_unchanged(repo: Path) -> None:
    _git(repo, "tag", "v1.0.0")
    (repo / "README.md").write_text("changed outside the plugin\n")
    _commit(repo, "docs")
    assert _run(repo) == 0


def test_fails_when_content_changes_under_the_same_version(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _git(repo, "tag", "v1.0.0")
    (repo / "plugins" / "claude-code" / "commands" / "a.md").write_text("a2\n")
    _commit(repo, "change a command")
    assert _run(repo) == 1
    out = capsys.readouterr().out
    assert "v1.0.0" in out
    assert "1.0.0" in out


def test_uncommitted_change_counts(repo: Path) -> None:
    _git(repo, "tag", "v1.0.0")
    (repo / "README.md").write_text("changed outside the plugin\n")
    _commit(repo, "docs")
    (repo / "plugins" / "claude-code" / "commands" / "b.md").write_text("b\n")
    _git(repo, "add", "-A")
    assert _run(repo) == 1


def test_passes_when_content_changes_with_a_new_version(repo: Path) -> None:
    _git(repo, "tag", "v1.0.0")
    (repo / "plugins" / "claude-code" / "commands" / "a.md").write_text("a2\n")
    _set_version(repo, "plugins/claude-code", "1.0.1")
    _commit(repo, "change a command and bump")
    assert _run(repo) == 0


def test_fails_when_the_source_moves_under_the_same_version(tmp_path: Path) -> None:
    """The v1.1.0 case: source "./" moved to "./plugins/claude-code"."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _layout(root, source="./", version="1.1.0")
    _commit(root, "root-sourced plugin")
    _git(root, "tag", "v1.1.0")
    _layout(root, source="./plugins/claude-code", version="1.1.0")
    _commit(root, "scope the package")
    assert _run(root) == 1


def test_tagged_head_compares_with_the_previous_tag(repo: Path) -> None:
    """On a tag push HEAD carries the new tag; the base is the one before."""
    _git(repo, "tag", "v1.0.0")
    (repo / "plugins" / "claude-code" / "commands" / "a.md").write_text("a2\n")
    _set_version(repo, "plugins/claude-code", "1.1.0")
    _commit(repo, "release 1.1.0")
    _git(repo, "tag", "v1.1.0")
    assert _run(repo) == 0


def test_tagged_head_without_a_bump_fails(repo: Path) -> None:
    _git(repo, "tag", "v1.0.0")
    (repo / "plugins" / "claude-code" / "commands" / "a.md").write_text("a2\n")
    _commit(repo, "forgot the bump")
    _git(repo, "tag", "v1.0.1")
    assert _run(repo) == 1


def test_non_release_tags_are_ignored(repo: Path) -> None:
    _git(repo, "tag", "v1.0.0")
    (repo / "plugins" / "claude-code" / "commands" / "a.md").write_text("a2\n")
    _set_version(repo, "plugins/claude-code", "1.0.1")
    _commit(repo, "bump")
    _git(repo, "tag", "nightly")
    _git(repo, "tag", "v2.0.0-rc.1")
    assert _run(repo) == 0


def test_explicit_base_ref(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "plugins" / "claude-code" / "commands" / "a.md").write_text("a2\n")
    _commit(repo, "change")
    assert _run(repo, "--base-ref", base) == 1


def test_not_a_repository_is_an_error(tmp_path: Path) -> None:
    assert _run(tmp_path) == 2
