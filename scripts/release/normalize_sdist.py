# SPDX-License-Identifier: MIT

"""Rewrite sdist archives so identical sources produce identical bytes.

Why this script exists. The release wheel rebuilds bit-for-bit from its tag,
but the sdist did not: setuptools writes the wall-clock build time into the
gzip header, and the tar entries carry the checkout's file mtimes, owner and
group, and the builder's umask. A third party rebuilding a release therefore
could not match the published sdist digest.

For each archive this rewrites, in place:

- entries sorted by name;
- every mtime clamped to ``SOURCE_DATE_EPOCH`` (an older time is kept, as the
  reproducible-builds convention prescribes);
- owner and group cleared (uid and gid 0, empty names) and any extra pax
  records dropped;
- modes normalized: directories and executables 0755, other files 0644;
- the gzip header mtime set to ``SOURCE_DATE_EPOCH`` and no file name stored.

Member names and contents are unchanged. An entry with an absolute path or a
``..`` component is refused. Stdlib only.

Usage::

    SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct) \\
        python scripts/release/normalize_sdist.py dist/apothem-*.tar.gz

Exit codes: ``0`` on success, ``1`` when an archive cannot be rewritten,
``2`` on a usage error (no ``SOURCE_DATE_EPOCH``).
"""

from __future__ import annotations

import gzip
import io
import os
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


class NormalizeError(RuntimeError):
    """An archive cannot be rewritten safely."""


def _safe_name(name: str) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise NormalizeError(f"refusing unsafe member name {name!r}")
    return name


def _normalized(member: tarfile.TarInfo, epoch: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(_safe_name(member.name))
    info.type = member.type
    info.size = member.size if member.isfile() else 0
    info.linkname = member.linkname
    info.mtime = min(int(member.mtime), epoch)
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    if member.isdir() or (member.isfile() and member.mode & 0o111):
        info.mode = 0o755
    elif member.issym():
        info.mode = 0o777
    else:
        info.mode = 0o644
    return info


def normalize(path: Path, epoch: int) -> None:
    """Rewrite the ``.tar.gz`` at *path* deterministically, in place."""
    raw = io.BytesIO()
    with (
        tarfile.open(path, "r:gz") as source,
        tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as target,
    ):
        for member in sorted(source.getmembers(), key=lambda m: m.name):
            info = _normalized(member, epoch)
            if member.isfile():
                handle = source.extractfile(member)
                if handle is None:
                    raise NormalizeError(f"{path.name}: cannot read {member.name}")
                target.addfile(info, handle)
            else:
                target.addfile(info)

    fd, tmp_name = tempfile.mkstemp(prefix=".normalize-", dir=path.parent)
    try:
        with (
            os.fdopen(fd, "wb") as handle,
            gzip.GzipFile(
                filename="", mode="wb", fileobj=handle, mtime=epoch, compresslevel=9
            ) as compressed,
        ):
            compressed.write(raw.getvalue())
        Path(tmp_name).replace(path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] in {"-h", "--help"}:
        print(__doc__)
        return 0 if args else 2
    value = os.environ.get("SOURCE_DATE_EPOCH", "")
    if not value.isdigit():
        print(
            "normalize-sdist: set SOURCE_DATE_EPOCH to the release commit time",
            file=sys.stderr,
        )
        return 2
    epoch = int(value)
    for name in args:
        path = Path(name)
        try:
            normalize(path, epoch)
        except (NormalizeError, OSError, tarfile.TarError, EOFError) as exc:
            print(f"normalize-sdist: {path}: {exc}", file=sys.stderr)
            return 1
        print(f"normalize-sdist: {path} (SOURCE_DATE_EPOCH={epoch})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
