# SPDX-License-Identifier: MIT

"""Verify the cross-platform release-runtime archive builder.

Three behavioral contracts: build-artifact existence per platform;
canonical filename pattern; SHA-256 digest equality between the
builder's stdout report and a fresh hash over the archive bytes (the
equality the workflow's SHA256SUMS manifest relies on).
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_release_tarball as builder  # noqa: E402  -- requires sys.path mutation above

PLATFORMS: Final[tuple[str, ...]] = ("darwin", "linux", "windows")
PROJECT_NAME: Final[str] = "apothem"
TEST_VERSION: Final[str] = "0.0.0-test"
HEX_DIGITS: Final[int] = 64
ENCODING: Final[str] = "utf-8"
NEWLINE: Final[str] = chr(10)


@pytest.fixture
def source_tree(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    root.mkdir()
    (root / "README.md").write_text("# fixture" + NEWLINE, encoding=ENCODING)
    (root / "VERSION").write_text(TEST_VERSION + NEWLINE, encoding=ENCODING)
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "apothem").write_text("#!/usr/bin/env bash\n", encoding=ENCODING)
    (scripts / "apothem.ps1").write_text("#Requires -Version 5.1\n", encoding=ENCODING)
    (scripts / "apothem.cmd").write_text("@echo off\n", encoding=ENCODING)
    installer = scripts / "installer"
    installer.mkdir()
    for name in ("install", "update", "uninstall"):
        (installer / f"{name}.sh").write_text(
            "#!/usr/bin/env bash\n", encoding=ENCODING
        )
        (installer / f"{name}.ps1").write_text(
            "#Requires -Version 5.1\n", encoding=ENCODING
        )
        (installer / f"{name}.bat").write_text("@echo off\n", encoding=ENCODING)
    non_runtime = root / "packaging" / "local"
    non_runtime.mkdir(parents=True)
    (non_runtime / "dummy.txt").write_text(
        "# excluded from runtime archive\n", encoding=ENCODING
    )
    workflow = root / ".github" / "workflows"
    workflow.mkdir(parents=True)
    (workflow / "release.yml").write_text(
        "# excluded from runtime archive\n", encoding=ENCODING
    )
    sub = root / "subdir"
    sub.mkdir()
    (sub / "alpha.txt").write_text("alpha" + NEWLINE, encoding=ENCODING)
    (sub / "beta.txt").write_text("beta" + NEWLINE, encoding=ENCODING)
    excluded = root / ".git"
    excluded.mkdir()
    (excluded / "HEAD").write_text("excluded" + NEWLINE, encoding=ENCODING)
    return root


@pytest.mark.parametrize("platform", PLATFORMS)
def test_archive_exists_with_canonical_name(
    source_tree: Path, tmp_path: Path, platform: str
) -> None:
    archive = builder.build_tarball(
        root=source_tree,
        out_dir=tmp_path / "out",
        name=PROJECT_NAME,
        version=TEST_VERSION,
        platform=platform,
    )
    suffix = "zip" if platform == "windows" else "tar.gz"
    expected_name = f"{PROJECT_NAME}-v{TEST_VERSION}-{platform}.{suffix}"
    assert archive.exists()
    assert archive.is_file()
    assert archive.name == expected_name


@pytest.mark.parametrize("platform", PLATFORMS)
def test_digest_matches_archive_bytes(
    source_tree: Path, tmp_path: Path, platform: str
) -> None:
    archive = builder.build_tarball(
        root=source_tree,
        out_dir=tmp_path / "out",
        name=PROJECT_NAME,
        version=TEST_VERSION,
        platform=platform,
    )
    reported = builder.compute_digest(archive)
    expected = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert reported == expected
    assert len(reported) == HEX_DIGITS


def _archive_names(archive: Path, platform: str) -> set[str]:
    if platform == "windows":
        with zipfile.ZipFile(archive) as zf:
            return set(zf.namelist())
    with tarfile.open(archive, "r:gz") as tf:
        return set(tf.getnames())


@pytest.mark.parametrize("platform", PLATFORMS)
def test_archive_contains_installable_runtime_layout(
    source_tree: Path, tmp_path: Path, platform: str
) -> None:
    archive = builder.build_tarball(
        root=source_tree,
        out_dir=tmp_path / "out",
        name=PROJECT_NAME,
        version=TEST_VERSION,
        platform=platform,
    )
    root = f"{PROJECT_NAME}-v{TEST_VERSION}"
    names = _archive_names(archive, platform)
    assert f"{root}/bin/apothem" in names
    assert f"{root}/bin/apothem.ps1" in names
    assert f"{root}/bin/apothem.cmd" in names
    assert f"{root}/install.sh" in names
    assert f"{root}/install.ps1" in names
    assert not any(name.startswith(f"{root}/.github/") for name in names)
    assert not any(name.startswith(f"{root}/packaging/") for name in names)


def test_git_checkout_uses_index_blob_bytes(tmp_path: Path) -> None:
    git_exe = shutil.which("git")
    if git_exe is None:
        pytest.skip("git required for index-byte archive test")

    root = tmp_path / "git-src"
    root.mkdir()
    tracked = root / "README.md"
    tracked.write_bytes(b"line one\nline two\n")
    subprocess.run([git_exe, "-C", str(root), "init"], check=True)
    subprocess.run(
        [git_exe, "-C", str(root), "config", "core.autocrlf", "false"],
        check=True,
    )
    subprocess.run([git_exe, "-C", str(root), "add", "README.md"], check=True)
    tracked.write_bytes(b"line one\r\nline two\r\n")

    archive = builder.build_tarball(
        root=root,
        out_dir=tmp_path / "out",
        name=PROJECT_NAME,
        version=TEST_VERSION,
        platform="linux",
    )

    with tarfile.open(archive, "r:gz") as tf:
        member = tf.extractfile(f"{PROJECT_NAME}-v{TEST_VERSION}/README.md")
        assert member is not None
        assert member.read() == b"line one\nline two\n"
