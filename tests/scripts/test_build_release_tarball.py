# SPDX-License-Identifier: MIT

"""Unit tests for the release-runtime archive builder.

``scripts/build_release_tarball.py`` packages the source tree (plus the
normalized ``bin/`` launcher aliases) into the platform archive the release
workflow signs and publishes. Its correctness is load-bearing: a wrong
exclusion ships the wrong files to every downloader, and a non-reproducible
build breaks the signed-digest guarantee. These tests exercise the exclusion
logic, deterministic naming/timestamps, member collection, and an end-to-end
build whose byte output is asserted reproducible. The fixture trees carry no
``.git``, so the git-blob and git-ls-files fast paths fall back to the
filesystem walk — covered directly, no real repository required.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from tests._shared.git_env import hermetic_git_env

_GIT = shutil.which("git")
requires_git = pytest.mark.skipif(_GIT is None, reason="git not available")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import build_release_tarball as brt  # noqa: E402


def _make_tree(root: Path, files: dict[str, bytes]) -> None:
    """Materialize a fixture tree from {relative-path: content}."""
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)


class TestGlobMatch:
    """Glob matching for exclusion patterns.

    Covers the star pattern matching a suffix and the exact pattern matching a
    full name.
    """

    def test_star_pattern_matches_suffix(self) -> None:
        assert brt._glob_match("module.pyc", "*.pyc") is True
        assert brt._glob_match("module.py", "*.pyc") is False

    def test_exact_pattern_matches_full_name(self) -> None:
        assert brt._glob_match(".DS_Store", ".DS_Store") is True
        assert brt._glob_match("DS_Store", ".DS_Store") is False


class TestIsExcluded:
    """Deciding whether a path is excluded from the archive.

    Covers the root-anchored exclusion that applies only at the top level, the
    default exclusion that applies at any depth, name-based glob exclusion, and
    the ordinary source file that survives.
    """

    def test_root_exclude_dir_at_top_level(self) -> None:
        assert brt._is_excluded(Path(".github/workflows/ci.yml")) is True
        assert brt._is_excluded(Path("packaging/spec.in")) is True

    def test_root_exclude_dir_only_at_top_level(self) -> None:
        # '.github' nested below the top level is NOT a root-exclude match.
        assert brt._is_excluded(Path("src/.github/x.py")) is False

    def test_default_exclude_dir_anywhere_in_path(self) -> None:
        assert brt._is_excluded(Path("src/__pycache__/m.pyc")) is True
        assert brt._is_excluded(Path("a/b/.git/config")) is True

    def test_glob_excluded_by_name(self) -> None:
        assert brt._is_excluded(Path("src/m.pyc")) is True
        assert brt._is_excluded(Path("nested/.DS_Store")) is True

    def test_ordinary_source_file_is_included(self) -> None:
        assert brt._is_excluded(Path("src/apothem/cli/install.py")) is False


class TestCollectMembers:
    """Collecting archive members by walking the tree.

    Covers the non-git tree, where the walk and the exclusion rules are the only
    source of membership.
    """

    def test_walks_and_excludes_on_a_non_git_tree(self, tmp_path: Path) -> None:
        _make_tree(
            tmp_path,
            {
                "src/apothem/__init__.py": b"x",
                "README.md": b"readme",
                ".github/workflows/ci.yml": b"ci",  # root-excluded
                "src/__pycache__/m.pyc": b"cache",  # dir-excluded
                "src/m.pyc": b"bytecode",  # glob-excluded
            },
        )
        members = brt.collect_members(tmp_path)
        rels = {m.as_posix() for m in members}

        assert "src/apothem/__init__.py" in rels
        assert "README.md" in rels
        assert ".github/workflows/ci.yml" not in rels
        assert "src/__pycache__/m.pyc" not in rels
        assert "src/m.pyc" not in rels
        # Output is sorted and deterministic.
        assert members == sorted(members)


def _init_git_repo(root: Path, files: dict[str, bytes]) -> None:
    """Create a committed git repo at *root* with the given files, without
    host git config (a signing or hook setting would break the commit)."""
    _make_tree(root, files)
    run = lambda *a: subprocess.run(  # noqa: E731
        [_GIT, "-C", str(root), *a],
        check=True,
        capture_output=True,
        env=hermetic_git_env(),
    )
    run("init", "-q")
    run("config", "user.email", "test@example.invalid")
    run("config", "user.name", "Test")
    run("add", "-A")
    run("commit", "-q", "-m", "fixture")


@requires_git
class TestGitTrackedPath:
    """Sourcing archive members from git rather than the worktree.

    Covers member collection through ``git ls-files`` with exclusions applied,
    reading staged blob bytes, the non-git tree returning none from the git
    helpers, and the checkout build sourcing its bytes from blobs — so the
    archive reflects tracked content, not stray worktree files.
    """

    def test_collect_members_uses_git_ls_files_and_excludes(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(
            tmp_path,
            {
                "src/apothem/__init__.py": b"pkg",
                "README.md": b"r",
                "notes.pyc": b"cache",  # tracked but glob-excluded
            },
        )
        rels = {m.as_posix() for m in brt.collect_members(tmp_path)}
        assert "src/apothem/__init__.py" in rels
        assert "README.md" in rels
        # Even a *tracked* file matching an exclusion glob is dropped.
        assert "notes.pyc" not in rels

    def test_git_blob_bytes_reads_staged_content(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path, {"a.txt": b"committed-bytes"})
        assert brt._git_blob_bytes(tmp_path, Path("a.txt")) == b"committed-bytes"

    def test_non_git_tree_returns_none_from_git_helpers(self, tmp_path: Path) -> None:
        # No .git -> both git helpers decline and the filesystem path is used.
        assert brt._git_tracked_members(tmp_path) is None
        assert brt._git_blob_bytes(tmp_path, Path("a.txt")) is None

    def test_build_from_git_checkout_sources_blob_bytes(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path, {"README.md": b"from-commit"})
        archive = brt.build_tarball(
            tmp_path, tmp_path / "out", "apothem", "0.1.0", "linux"
        )
        with tarfile.open(archive, "r:gz") as tf:
            extracted = tf.extractfile("apothem-v0.1.0/README.md")
            assert extracted is not None
            assert extracted.read() == b"from-commit"


class TestNamingAndEpoch:
    """Archive naming and reproducible timestamps.

    Covers the per-platform basename, the archive root prefix, parsing of the
    source-date epoch, and the ZIP timestamp flooring at 1980 — the earliest
    date the ZIP format can represent.
    """

    def test_archive_basename_per_platform(self) -> None:
        assert brt._archive_basename("apothem", "0.1.0", "windows") == (
            "apothem-v0.1.0-windows.zip"
        )
        assert brt._archive_basename("apothem", "0.1.0", "linux") == (
            "apothem-v0.1.0-linux.tar.gz"
        )

    def test_archive_root(self) -> None:
        assert brt._archive_root("apothem", "0.1.0") == "apothem-v0.1.0"

    def test_source_date_epoch_parsing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
        assert brt._source_date_epoch() == brt.SOURCE_DATE_EPOCH_DEFAULT

        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
        assert brt._source_date_epoch() == 1700000000

        monkeypatch.setenv("SOURCE_DATE_EPOCH", "not-a-number")
        assert brt._source_date_epoch() == brt.SOURCE_DATE_EPOCH_DEFAULT

        monkeypatch.setenv("SOURCE_DATE_EPOCH", "-5")
        assert brt._source_date_epoch() == 0  # clamped to non-negative

    def test_zip_date_time_floors_at_1980(self) -> None:
        # ZIP cannot represent pre-1980 timestamps; mtime 0 floors to 1980.
        assert brt._zip_date_time(0)[0] == 1980


class TestMemberBytes:
    """Resolving the bytes for one archive member.

    Covers the precedence: explicit content wins, and the source file is read
    only when no content was supplied.
    """

    def test_prefers_content_over_source(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_bytes(b"on-disk")
        member = brt.ArchiveMember(source=f, arcname=Path("a.txt"), content=b"from-git")
        assert brt._member_bytes(member) == b"from-git"

    def test_reads_source_when_content_absent(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_bytes(b"on-disk")
        member = brt.ArchiveMember(source=f, arcname=Path("a.txt"), content=None)
        assert brt._member_bytes(member) == b"on-disk"


class TestComputeDigest:
    """Archive digest computation.

    Covers that the digest matches the stdlib implementation, so a consumer can
    verify it without this tool.
    """

    def test_matches_hashlib(self, tmp_path: Path) -> None:
        f = tmp_path / "blob.bin"
        payload = b"release-artifact-bytes" * 5000  # exceeds one read chunk
        f.write_bytes(payload)
        assert brt.compute_digest(f) == hashlib.sha256(payload).hexdigest()


class TestBuildTarball:
    """Building the release archive end to end.

    Covers the unknown-platform rejection, the Linux archive prefixing its root
    and honouring exclusions, the alias carrying its executable mode, the
    Windows path producing a valid ZIP, and — the property the release posture
    depends on — that two builds of the same tree are byte-identical.
    """

    def test_unknown_platform_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="unsupported platform"):
            brt.build_tarball(tmp_path, tmp_path / "out", "apothem", "0.1.0", "solaris")

    def test_linux_archive_prefixes_root_and_honors_exclusions(
        self, tmp_path: Path
    ) -> None:
        src = tmp_path / "src-tree"
        out = tmp_path / "out"
        _make_tree(
            src,
            {
                "src/apothem/__init__.py": b"pkg",
                "README.md": b"readme",
                ".github/workflows/ci.yml": b"ci",  # excluded
                "scripts/installer/install.sh": b"#!/bin/sh\n",  # alias source
            },
        )

        archive = brt.build_tarball(src, out, "apothem", "0.1.0", "linux")

        assert archive.name == "apothem-v0.1.0-linux.tar.gz"
        with tarfile.open(archive, "r:gz") as tf:
            names = set(tf.getnames())
        # Every member is prefixed with the versioned archive root.
        assert "apothem-v0.1.0/src/apothem/__init__.py" in names
        assert "apothem-v0.1.0/README.md" in names
        # Excluded surfaces never ship.
        assert "apothem-v0.1.0/.github/workflows/ci.yml" not in names
        # The bin/ launcher alias is added at the archive top.
        assert "apothem-v0.1.0/install.sh" in names

    def test_alias_carries_executable_mode(self, tmp_path: Path) -> None:
        src = tmp_path / "src-tree"
        out = tmp_path / "out"
        _make_tree(src, {"scripts/installer/install.sh": b"#!/bin/sh\n"})

        archive = brt.build_tarball(src, out, "apothem", "0.1.0", "linux")

        with tarfile.open(archive, "r:gz") as tf:
            member = tf.getmember("apothem-v0.1.0/install.sh")
        # install.sh is declared executable in RUNTIME_ALIASES -> 0o755.
        assert member.mode == 0o755

    def test_build_is_reproducible(self, tmp_path: Path) -> None:
        src = tmp_path / "src-tree"
        _make_tree(src, {"a.py": b"a", "b/c.py": b"c", "README.md": b"r"})

        first = brt.build_tarball(src, tmp_path / "o1", "apothem", "0.1.0", "linux")
        second = brt.build_tarball(src, tmp_path / "o2", "apothem", "0.1.0", "linux")

        # Identical inputs -> byte-identical archive -> identical digest.
        assert brt.compute_digest(first) == brt.compute_digest(second)

    def test_windows_produces_a_valid_zip(self, tmp_path: Path) -> None:
        src = tmp_path / "src-tree"
        out = tmp_path / "out"
        _make_tree(src, {"README.md": b"readme"})

        archive = brt.build_tarball(src, out, "apothem", "0.1.0", "windows")

        assert archive.name == "apothem-v0.1.0-windows.zip"
        with zipfile.ZipFile(archive) as zf:
            assert zf.testzip() is None  # no corrupt entries
            assert "apothem-v0.1.0/README.md" in zf.namelist()


class TestMain:
    """Process-level entry point behaviour.

    Covers that the digest line is emitted and the exit code is zero.
    """

    def test_emits_digest_line_and_returns_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        src = tmp_path / "src-tree"
        out = tmp_path / "out"
        _make_tree(src, {"README.md": b"readme"})

        rc = brt.main(
            [
                "--root",
                str(src),
                "--out-dir",
                str(out),
                "--name",
                "apothem",
                "--version",
                "0.1.0",
                "--platform",
                "linux",
            ]
        )

        assert rc == 0
        line = capsys.readouterr().out.strip()
        digest, _, archive_name = line.partition("  ")
        assert archive_name == "apothem-v0.1.0-linux.tar.gz"
        # The emitted digest matches the archive on disk.
        assert digest == brt.compute_digest(out / archive_name)
