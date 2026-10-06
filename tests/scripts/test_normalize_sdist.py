# SPDX-License-Identifier: MIT

"""Tests for scripts/release/normalize_sdist.py and the build-backend pin.

The wheel already rebuilt bit-for-bit, but two sdist builds of the same commit
differed: the gzip header carries the wall-clock build time and the tar
entries carry checkout mtimes, owners and modes. The normalizer rewrites the
archive so identical sources give identical bytes. The release also used to
build in an isolated environment that fetched whatever setuptools PyPI served,
bypassing the hash-locked toolchain; the backend is now pinned to that
toolchain's version.
"""

from __future__ import annotations

import gzip
import io
import re
import struct
import sys
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "release"))

import normalize_sdist  # noqa: E402

EPOCH = 1_790_000_000
FILES = {
    "apothem-9.9.9/PKG-INFO": b"Metadata-Version: 2.4\nName: apothem\n",
    "apothem-9.9.9/src/apothem/__init__.py": b"x = 1\n",
    "apothem-9.9.9/scripts/run.sh": b"#!/bin/sh\necho hi\n",
}


def _sdist(
    path: Path, *, mtime: int, uid: int, order: list[str], gzip_mtime: int
) -> None:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
        directory = tarfile.TarInfo("apothem-9.9.9")
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o775
        directory.mtime = mtime
        archive.addfile(directory)
        for name in order:
            data = FILES[name]
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = mtime
            info.uid = info.gid = uid
            info.uname = info.gname = f"user{uid}"
            info.mode = 0o775 if name.endswith(".sh") else 0o664
            archive.addfile(info, io.BytesIO(data))
    with (
        path.open("wb") as handle,
        gzip.GzipFile(
            filename=path.name, mode="wb", fileobj=handle, mtime=gzip_mtime
        ) as compressed,
    ):
        compressed.write(raw.getvalue())


def _gzip_mtime(path: Path) -> int:
    return int(struct.unpack("<I", path.read_bytes()[4:8])[0])


def test_two_builds_of_the_same_sources_become_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(EPOCH))
    first, second = tmp_path / "a.tar.gz", tmp_path / "b.tar.gz"
    _sdist(
        first, mtime=EPOCH + 500, uid=1000, order=sorted(FILES), gzip_mtime=EPOCH + 900
    )
    _sdist(
        second,
        mtime=EPOCH + 7000,
        uid=0,
        order=sorted(FILES, reverse=True),
        gzip_mtime=EPOCH + 9000,
    )
    assert first.read_bytes() != second.read_bytes()
    assert normalize_sdist.main([str(first), str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()


def test_metadata_is_normalized_and_content_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(EPOCH))
    sdist = tmp_path / "apothem-9.9.9.tar.gz"
    _sdist(sdist, mtime=EPOCH + 500, uid=1000, order=list(FILES), gzip_mtime=EPOCH + 1)
    assert normalize_sdist.main([str(sdist)]) == 0
    assert _gzip_mtime(sdist) == EPOCH
    with tarfile.open(sdist) as archive:
        members = archive.getmembers()
        assert [m.name for m in members] == sorted(m.name for m in members)
        for member in members:
            assert member.mtime == EPOCH
            assert (member.uid, member.gid, member.uname, member.gname) == (
                0,
                0,
                "",
                "",
            )
            if member.isdir() or member.name.endswith(".sh"):
                assert member.mode == 0o755
            else:
                assert member.mode == 0o644
            if member.isfile():
                handle = archive.extractfile(member)
                assert handle is not None
                assert handle.read() == FILES[member.name]


def test_older_mtimes_are_kept_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Clamping only lowers times; an entry older than the epoch keeps its time."""
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(EPOCH))
    sdist = tmp_path / "s.tar.gz"
    _sdist(sdist, mtime=EPOCH - 100, uid=0, order=list(FILES), gzip_mtime=EPOCH)
    assert normalize_sdist.main([str(sdist)]) == 0
    with tarfile.open(sdist) as archive:
        assert {m.mtime for m in archive.getmembers()} == {EPOCH - 100}


def test_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(EPOCH))
    sdist = tmp_path / "s.tar.gz"
    _sdist(sdist, mtime=EPOCH + 5, uid=7, order=list(FILES), gzip_mtime=EPOCH + 5)
    assert normalize_sdist.main([str(sdist)]) == 0
    once = sdist.read_bytes()
    assert normalize_sdist.main([str(sdist)]) == 0
    assert sdist.read_bytes() == once


def test_requires_source_date_epoch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    sdist = tmp_path / "s.tar.gz"
    _sdist(sdist, mtime=EPOCH, uid=0, order=list(FILES), gzip_mtime=EPOCH)
    assert normalize_sdist.main([str(sdist)]) == 2


def test_refuses_unsafe_member_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(EPOCH))
    sdist = tmp_path / "s.tar.gz"
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as archive:
        info = tarfile.TarInfo("../escape")
        info.size = 0
        archive.addfile(info, io.BytesIO(b""))
    sdist.write_bytes(gzip.compress(raw.getvalue()))
    assert normalize_sdist.main([str(sdist)]) == 1


# --- build-backend pin ----------------------------------------------------------


def _toolchain_setuptools() -> str:
    text = (
        REPO_ROOT / "scripts" / "release" / "requirements-build-linux.txt"
    ).read_text(encoding="utf-8")
    match = re.search(r"^setuptools==(\S+)", text, re.MULTILINE)
    assert match, "requirements-build-linux.txt pins no setuptools"
    return match.group(1)


def test_build_backend_is_pinned_to_the_hash_locked_toolchain() -> None:
    tomllib = pytest.importorskip("tomllib")
    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    requires = pyproject["build-system"]["requires"]
    assert requires == [f"setuptools=={_toolchain_setuptools()}"], (
        "build-system.requires must pin the setuptools version that "
        "scripts/release/requirements-build-linux.txt hash-locks"
    )


def test_release_build_uses_the_locked_toolchain_and_normalizes_the_sdist() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert "python -m build --no-isolation" in workflow
    assert "scripts/release/normalize_sdist.py" in workflow
    assert workflow.index("normalize_sdist.py") < workflow.index("generate_sbom.py"), (
        "normalize the sdist before the SBOM records its digest"
    )
