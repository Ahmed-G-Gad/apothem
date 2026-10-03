# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The POSIX installer's checksum-only mode (``APOTHEM_VERIFY=checksum``).

The default mode verifies the release tag's GPG signature, which needs the
maintainer's public key. Until a user has that key, the checksum mode offers a
documented, weaker path: it downloads the release's platform archive and its
``SHA256SUMS``, refuses a digest mismatch, and warns that a matching digest
proves integrity against the release listing, not who published it.

These tests serve a fake release from a ``file://`` base so they run offline.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "installer" / "install.sh"
TAG = "v9.9.9"

_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import build_release_tarball as brt  # noqa: E402

# The directory every member of a real release archive sits under.
ARCHIVE_ROOT = brt._archive_root("apothem", TAG.removeprefix("v"))
INTEGRITY_WARNING = "does not prove who published it"
MISMATCH_MARKER = "does not match the release's SHA256SUMS"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None
    or shutil.which("curl") is None
    or sys.platform == "win32",
    reason="exercises the POSIX install.sh with curl; install.ps1 is the Windows path",
)


def _archive_bytes(*, root: str | None = ARCHIVE_ROOT) -> bytes:
    """A minimal apothem-shaped runtime archive laid out like a real release.

    Every member sits under *root*, the directory scripts/build_release_tarball.py
    puts at the top of each release archive; ``root=None`` builds a flat archive.
    """
    prefix = f"{root}/" if root else ""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, body in (
            ("src/apothem/__init__.py", b"# SPDX-License-Identifier: MIT\n"),
            ("pyproject.toml", b'[project]\nname = "fixture"\nversion = "9.9.9"\n'),
        ):
            info = tarfile.TarInfo(prefix + name)
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


def _platform() -> str:
    return "darwin" if sys.platform == "darwin" else "linux"


def _release(
    tmp_path: Path, *, tamper: bool = False, root: str | None = ARCHIVE_ROOT
) -> Path:
    """Write a fake release under ``<base>/<tag>/`` and return the base."""
    base = tmp_path / "releases"
    folder = base / TAG
    folder.mkdir(parents=True)
    name = f"apothem-{TAG}-{_platform()}.tar.gz"
    data = _archive_bytes(root=root)
    (folder / name).write_bytes(data + (b"tampered" if tamper else b""))
    digest = hashlib.sha256(data).hexdigest()
    (folder / "SHA256SUMS").write_text(f"{digest}  {name}\n", encoding="utf-8")
    return base


def _run(
    tmp_path: Path, base: Path, ref: str = TAG
) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("APOTHEM_")}
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "HOME": str(home),
            "APOTHEM_VERIFY": "checksum",
            "APOTHEM_RELEASE_BASE": base.as_uri(),
            "APOTHEM_REF": ref,
            "APOTHEM_HOME": str(tmp_path / "apothem-home"),
        }
    )
    staging = tmp_path / "installer-under-test"
    staging.mkdir(exist_ok=True)
    installer = staging / "install.sh"
    shutil.copy2(INSTALLER, installer)
    return subprocess.run(
        ["bash", str(installer), "--yes", "--dry-run"],
        cwd=str(staging),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_matching_archive_is_installed_with_an_integrity_warning(
    tmp_path: Path,
) -> None:
    result = _run(tmp_path, _release(tmp_path))
    combined = result.stdout + result.stderr
    assert INTEGRITY_WARNING in combined, combined
    assert (tmp_path / "apothem-home" / "src" / "apothem" / "__init__.py").is_file()


def test_tampered_archive_aborts_before_extraction(tmp_path: Path) -> None:
    result = _run(tmp_path, _release(tmp_path, tamper=True))
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert MISMATCH_MARKER in combined, combined
    assert not (tmp_path / "apothem-home" / "src").exists()


def test_checksum_mode_needs_a_release_tag(tmp_path: Path) -> None:
    result = _run(tmp_path, _release(tmp_path), ref="main")
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "needs a vMAJOR.MINOR.PATCH release tag" in combined, combined


def test_archive_without_the_release_root_is_refused(tmp_path: Path) -> None:
    result = _run(tmp_path, _release(tmp_path, root=None))
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert f"does not hold an apothem source under {ARCHIVE_ROOT}/" in combined, (
        combined
    )
    assert not (tmp_path / "apothem-home" / "src").exists()


# REUSE-IgnoreEnd
