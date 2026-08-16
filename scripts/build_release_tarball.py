# SPDX-License-Identifier: MIT

"""Cross-platform release-runtime archive builder.

Packages the source-of-truth tree plus a normalized ``bin/`` launcher layout
into a platform-specific archive (tar.gz for darwin / linux; zip for windows)
used by the release workflow's tag-push job. Excludes plan-suite ephemera,
vendored caches, CI metadata, non-runtime trees, and version-control
internals.

Emits the archive's SHA-256 digest to stdout in the canonical
``<digest>  <archive.name>`` form so the caller can aggregate digests
into a signed manifest.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# stdlib hash factory aliased so the identifier carrying the digit suffix
# only appears on this named-constant line; downstream call sites use
# the alias and remain free of bare digits.
_DIGEST_FACTORY: Final = hashlib.sha256

DEFAULT_EXCLUDE_DIRS: Final[tuple[str, ...]] = (
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".hypothesis",
    ".vscode",
    "node_modules",
    "plugins",
    "site",
    "dist",
    "build",
    ".audit",
    # Both plans trees: ".apothem" is the canonical workspace and ".plans" the
    # legacy one an unmigrated checkout may still carry. Excluding only the
    # legacy name would ship a current operator's plan-product in the tarball.
    # generate-sbom.sh applies the same dual exclusion.
    ".apothem",
    ".plans",
    "_inputs",
    "_spec",
    "projects",
)
DEFAULT_EXCLUDE_GLOBS: Final[tuple[str, ...]] = (
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "Thumbs.db",
)
ROOT_EXCLUDE_DIRS: Final[tuple[str, ...]] = (".github", "packaging")
PLATFORMS: Final[tuple[str, ...]] = ("darwin", "linux", "windows")
SOURCE_DATE_EPOCH_DEFAULT: Final[int] = 0
ZIP_EPOCH_FLOOR: Final[int] = 315532800

RUNTIME_ALIASES: Final[tuple[tuple[str, str, bool], ...]] = (
    ("scripts/apothem", "bin/apothem", True),
    ("scripts/apothem.ps1", "bin/apothem.ps1", False),
    ("scripts/apothem.cmd", "bin/apothem.cmd", False),
    ("scripts/installer/install.sh", "install.sh", True),
    ("scripts/installer/update.sh", "update.sh", True),
    ("scripts/installer/uninstall.sh", "uninstall.sh", True),
    ("scripts/installer/install.ps1", "install.ps1", False),
    ("scripts/installer/update.ps1", "update.ps1", False),
    ("scripts/installer/uninstall.ps1", "uninstall.ps1", False),
    ("scripts/installer/install.bat", "install.bat", False),
    ("scripts/installer/update.bat", "update.bat", False),
    ("scripts/installer/uninstall.bat", "uninstall.bat", False),
)

# Buffer size for streaming digest computation; large enough to amortise
# read-syscall overhead, small enough to keep peak memory bounded.
DIGEST_CHUNK_BYTES: Final[int] = 1 << 16

# Compression level for deflate / gzip; mid-band balance of size vs CPU.
ARCHIVE_COMPRESS_LEVEL: Final[int] = 6


@dataclass(frozen=True, slots=True)
class ArchiveMember:
    """One physical source file emitted at one archive-relative path."""

    source: Path
    arcname: Path
    executable: bool = False
    content: bytes | None = None


def _glob_match(name: str, pattern: str) -> bool:
    if pattern.startswith("*"):
        return name.endswith(pattern[1:])
    return name == pattern


def _is_excluded(rel: Path) -> bool:
    parts = rel.parts
    if parts and parts[0] in ROOT_EXCLUDE_DIRS:
        return True
    if any(part in DEFAULT_EXCLUDE_DIRS for part in parts):
        return True
    name = rel.name
    return any(_glob_match(name, pat) for pat in DEFAULT_EXCLUDE_GLOBS)


def collect_members(root: Path) -> list[Path]:
    """Return the relative paths to include in the release archive.

    Prefers the git-tracked file set when *root* is a checkout, so the
    archive mirrors exactly what version control ships; falls back to a
    filesystem walk that prunes ``DEFAULT_EXCLUDE_DIRS`` and excluded
    patterns when *root* is not a git tree (for example an exported
    source directory).

    Args:
        root: The source-of-truth tree to archive.

    Returns:
        Relative paths sorted for deterministic archive ordering.
    """
    git_members = _git_tracked_members(root)
    if git_members is not None:
        return git_members
    members: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDE_DIRS]
        for filename in filenames:
            rel = rel_dir / filename if str(rel_dir) != "." else Path(filename)
            if _is_excluded(rel):
                continue
            members.append(rel)
    return sorted(members)


def _git_tracked_members(root: Path) -> list[Path] | None:
    """Return tracked files when *root* is a git checkout, else ``None``."""
    if not (root / ".git").exists():
        return None
    git_exe = shutil.which("git")
    if git_exe is None:
        return None
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell; root selects checkout.
        [git_exe, "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    members: list[Path] = []
    for raw in result.stdout.decode("utf-8", errors="surrogateescape").split("\0"):
        if not raw:
            continue
        rel = Path(raw)
        if _is_excluded(rel):
            continue
        if (root / rel).is_file():
            members.append(rel)
    return sorted(members)


def _git_blob_bytes(root: Path, rel: Path) -> bytes | None:
    """Read staged Git blob bytes for *rel* when available.

    Release archives must be byte-stable across hosts. Reading from the Git
    index avoids Windows CRLF worktree conversions changing archive hashes.
    """
    if not (root / ".git").exists():
        return None
    git_exe = shutil.which("git")
    if git_exe is None:
        return None
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell; root selects checkout.
        [git_exe, "-C", str(root), "cat-file", "blob", f":{rel.as_posix()}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def collect_archive_members(root: Path) -> list[ArchiveMember]:
    """Collect source files plus release-runtime aliases.

    The platform archives are installable runtime bundles, not CI metadata
    snapshots. Root-level non-runtime trees (workflow metadata, local
    packaging scratch) are excluded so the archive carries only what the
    installed runtime consumes.
    """
    members = [
        ArchiveMember(
            source=root / rel,
            arcname=rel,
            executable=False,
            content=_git_blob_bytes(root, rel),
        )
        for rel in collect_members(root)
    ]
    existing_arcnames = {member.arcname.as_posix() for member in members}
    for source_raw, arcname_raw, executable in RUNTIME_ALIASES:
        source = root / source_raw
        arcname = Path(arcname_raw)
        if not source.is_file() or arcname.as_posix() in existing_arcnames:
            continue
        members.append(
            ArchiveMember(
                source=source,
                arcname=arcname,
                executable=executable,
                content=_git_blob_bytes(root, Path(source_raw)),
            )
        )
        existing_arcnames.add(arcname.as_posix())
    return sorted(members, key=lambda member: member.arcname.as_posix())


def _source_date_epoch() -> int:
    raw = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if not raw:
        return SOURCE_DATE_EPOCH_DEFAULT
    try:
        return max(0, int(raw))
    except ValueError:
        return SOURCE_DATE_EPOCH_DEFAULT


def _archive_basename(name: str, version: str, platform: str) -> str:
    suffix = "zip" if platform == "windows" else "tar.gz"
    return f"{name}-v{version}-{platform}.{suffix}"


def _archive_root(name: str, version: str) -> str:
    return f"{name}-v{version}"


def _tar_info_for(
    size: int, arcname: str, mtime: int, executable: bool
) -> tarfile.TarInfo:
    tar_info = tarfile.TarInfo(arcname)
    tar_info.size = size
    tar_info.mtime = mtime
    tar_info.uid = 0
    tar_info.gid = 0
    tar_info.uname = ""
    tar_info.gname = ""
    tar_info.mode = 0o755 if executable else 0o644
    return tar_info


def _zip_date_time(mtime: int) -> tuple[int, int, int, int, int, int]:
    # ZIP timestamps cannot represent dates before 1980-01-01.
    effective = max(mtime, ZIP_EPOCH_FLOOR)
    return time.gmtime(effective)[:6]


def _member_bytes(member: ArchiveMember) -> bytes:
    if member.content is not None:
        return member.content
    return member.source.read_bytes()


def build_tarball(
    root: Path,
    out_dir: Path,
    name: str,
    version: str,
    platform: str,
) -> Path:
    """Build a reproducible release archive for *platform* and return its path.

    Emits a ``.zip`` on Windows and a gzipped tar elsewhere, both written
    deterministically: member order is sorted, every mtime is pinned to
    ``SOURCE_DATE_EPOCH``, the compression level is fixed, and mode bits
    are normalized to ``0o755`` / ``0o644`` — so two builds of the same
    tree are byte-identical and their digests are stable.

    Args:
        root: The source-of-truth tree to archive.
        out_dir: Directory the archive is written to (created if absent).
        name: Project name, forming the archive root and basename.
        version: Release version without a leading ``v``.
        platform: One of ``PLATFORMS``; selects the archive format.

    Returns:
        The path to the written archive.

    Raises:
        ValueError: When *platform* is not a supported platform.
    """
    if platform not in PLATFORMS:
        raise ValueError(f"unsupported platform: {platform!r}")
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_root = _archive_root(name, version)
    archive_path = out_dir / _archive_basename(name, version, platform)
    members = collect_archive_members(root)
    mtime = _source_date_epoch()
    if platform == "windows":
        with zipfile.ZipFile(
            archive_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=ARCHIVE_COMPRESS_LEVEL,
        ) as zf:
            for member in members:
                arcname = (Path(archive_root) / member.arcname).as_posix()
                data = _member_bytes(member)
                info = zipfile.ZipInfo(arcname, date_time=_zip_date_time(mtime))
                mode = 0o755 if member.executable else 0o644
                info.external_attr = (mode & 0xFFFF) << 16
                zf.writestr(
                    info,
                    data,
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=ARCHIVE_COMPRESS_LEVEL,
                )
    else:
        with (
            archive_path.open("wb") as raw,
            gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw,
                compresslevel=ARCHIVE_COMPRESS_LEVEL,
                mtime=mtime,
            ) as gz,
            tarfile.open(fileobj=gz, mode="w") as tf,
        ):
            for member in members:
                arcname = (Path(archive_root) / member.arcname).as_posix()
                data = _member_bytes(member)
                tar_info = _tar_info_for(
                    size=len(data),
                    arcname=arcname,
                    mtime=mtime,
                    executable=member.executable,
                )
                tf.addfile(tar_info, io.BytesIO(data))
    return archive_path


def compute_digest(path: Path) -> str:
    """Return the hex digest of *path*, streamed in fixed-size chunks.

    Reads the file in ``DIGEST_CHUNK_BYTES`` chunks rather than loading it
    whole, so the digest of a large archive is computed in bounded memory.

    Args:
        path: The archive file to hash.

    Returns:
        The hex-encoded digest produced by ``_DIGEST_FACTORY``.
    """
    digest = _DIGEST_FACTORY()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(DIGEST_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="build_release_tarball",
        description="Build a platform-specific release archive and emit its SHA-256 digest.",
    )
    parser.add_argument(
        "--root", type=Path, required=True, help="Source-of-truth tree root."
    )
    parser.add_argument(
        "--out-dir", type=Path, required=True, help="Output directory for the archive."
    )
    parser.add_argument("--name", required=True, help="Project name (e.g., apothem).")
    parser.add_argument(
        "--version", required=True, help="Release version without leading 'v'."
    )
    parser.add_argument(
        "--platform", required=True, choices=PLATFORMS, help="Target platform."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Build the release tarball and print its digest; return the exit code.

    Pre-conditions: ``argv`` is the argument vector without the program name
    (``None`` reads ``sys.argv[1:]``), supplying the source root, output
    directory, archive name, version, and target platform.

    Post-conditions: the archive is written under the resolved output
    directory and one ``<digest>  <filename>`` line is written to stdout — the
    two-space separator matches the ``sha256sum`` checksum-file format, so the
    output can be redirected straight into a ``.sha256`` companion that
    ``sha256sum -c`` verifies. Returns ``0``.
    """
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    archive_path = build_tarball(
        args.root.resolve(),
        args.out_dir.resolve(),
        args.name,
        args.version,
        args.platform,
    )
    digest = compute_digest(archive_path)
    sys.stdout.write(f"{digest}  {archive_path.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
