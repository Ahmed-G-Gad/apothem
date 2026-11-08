# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The POSIX installer's checksum-only mode (``APOTHEM_VERIFY=checksum``).

The default mode verifies the release tag's GPG signature, which needs the
maintainer's public key. Until a user has that key, the checksum mode offers a
documented, weaker path: it downloads the release's platform archive and its
``SHA256SUMS`` and refuses a digest mismatch. A match shows only that the
download is not damaged, since anyone who can change the release's files can
change both, so the mode runs only with ``APOTHEM_ALLOW_UNVERIFIED=1`` as well:
without it the installer stops before downloading anything, and with it the
installer says so before the download starts.

These tests serve a fake release from a ``file://`` base so they run offline.
A stub ``curl`` placed first on PATH records each call and hands it to the
real ``curl``, so a test can tell whether anything was downloaded.
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
# The caveat install.sh prints for checksum mode, before downloading.
CHECKSUM_CAVEAT = (
    "Checksum mode does not verify the release. SHA256SUMS comes from the same "
    "release as the archive, so a match only shows the download isn't damaged; "
    "anyone who can change the release's files can change both."
)
GATE_MARKER = "Set APOTHEM_ALLOW_UNVERIFIED=1 as well to install this way anyway"
PROCEEDING_MARKER = "Proceeding because APOTHEM_ALLOW_UNVERIFIED=1."
DOWNLOAD_MARKER = "Downloading apothem-"
MISMATCH_MARKER = "does not match the release's SHA256SUMS"

# Permission bits for the stub curl (owner rwx, others rx).
EXECUTABLE_MODE = 0o755

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


def _curl_calls(tmp_path: Path) -> list[str]:
    """The calls the stub curl recorded, one line of arguments per call."""
    log = tmp_path / "stub-curl" / "calls.txt"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def _stub_curl(tmp_path: Path) -> Path:
    """Write a stub ``curl`` that logs its arguments and runs the real one;
    return the directory that holds it."""
    real = shutil.which("curl")
    assert real is not None
    stub_dir = tmp_path / "stub-curl"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "curl"
    stub.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> '{stub_dir / 'calls.txt'}'\n"
        f"exec '{real}' \"$@\"\n",
        encoding="utf-8",
        newline="\n",
    )
    stub.chmod(EXECUTABLE_MODE)
    return stub_dir


def _run(
    tmp_path: Path,
    base: Path,
    ref: str = TAG,
    apothem_home: Path | None = None,
    *,
    allow_unverified: bool = True,
    dry_run: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run install.sh --yes in checksum mode against the fake release, with
    APOTHEM_ALLOW_UNVERIFIED=1 unless ALLOW_UNVERIFIED is false."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (tmp_path / "temp").mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("APOTHEM_")}
    env.pop("PYTHONPATH", None)
    # --yes lets the installer pip-install a missing click or rich; with no
    # package index that install fails instead of changing the host Python.
    for key in [k for k in env if k.startswith("PIP_")]:
        del env[key]
    env["PIP_NO_INDEX"] = "1"
    env["PIP_CONFIG_FILE"] = os.devnull
    env.update(
        {
            "HOME": str(home),
            "TMPDIR": str(tmp_path / "temp"),
            "APOTHEM_VERIFY": "checksum",
            "APOTHEM_RELEASE_BASE": base.as_uri(),
            "APOTHEM_REF": ref,
            "APOTHEM_HOME": str(apothem_home or tmp_path / "apothem-home"),
        }
    )
    if allow_unverified:
        env["APOTHEM_ALLOW_UNVERIFIED"] = "1"
    env["PATH"] = f"{_stub_curl(tmp_path)}{os.pathsep}{env.get('PATH', os.defpath)}"
    staging = tmp_path / "installer-under-test"
    staging.mkdir(exist_ok=True)
    installer = staging / "install.sh"
    shutil.copy2(INSTALLER, installer)
    return subprocess.run(
        ["bash", str(installer), "--yes", *(["--dry-run"] if dry_run else [])],
        cwd=str(staging),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_checksum_mode_is_refused_without_allow_unverified(tmp_path: Path) -> None:
    """Without APOTHEM_ALLOW_UNVERIFIED=1 the mode stops with the caveat
    before anything is downloaded or placed."""
    result = _run(tmp_path, _release(tmp_path), allow_unverified=False)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert CHECKSUM_CAVEAT in result.stderr, combined
    assert GATE_MARKER in result.stderr, combined
    assert DOWNLOAD_MARKER not in combined, combined
    assert _curl_calls(tmp_path) == [], combined
    assert list((tmp_path / "temp").iterdir()) == [], combined
    assert not (tmp_path / "apothem-home").exists(), combined


def test_a_dry_run_is_refused_the_same_way(tmp_path: Path) -> None:
    result = _run(tmp_path, _release(tmp_path), allow_unverified=False, dry_run=True)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert GATE_MARKER in result.stderr, combined
    assert _curl_calls(tmp_path) == [], combined


def test_allow_unverified_warns_before_downloading(tmp_path: Path) -> None:
    """With APOTHEM_ALLOW_UNVERIFIED=1 the caveat comes first, as a warning,
    and only then the download starts."""
    result = _run(tmp_path, _release(tmp_path))

    combined = result.stdout + result.stderr
    assert result.stdout.count(CHECKSUM_CAVEAT) == 1, combined
    warning = result.stdout.index(CHECKSUM_CAVEAT)
    assert result.stdout.index(PROCEEDING_MARKER) > warning, combined
    assert result.stdout.index(DOWNLOAD_MARKER) > warning, combined
    assert GATE_MARKER not in combined, combined
    assert _curl_calls(tmp_path), "the archive was never downloaded"


def test_matching_archive_is_installed_after_the_caveat(tmp_path: Path) -> None:
    result = _run(tmp_path, _release(tmp_path))
    combined = result.stdout + result.stderr
    assert CHECKSUM_CAVEAT in combined, combined
    assert "matches the release's SHA256SUMS" in combined, combined
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
    assert list((tmp_path / "temp").iterdir()) == [], "the download was left behind"


def test_a_destination_that_cannot_be_created_leaves_no_download(
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "a-file"
    blocker.write_text("", encoding="utf-8")

    result = _run(tmp_path, _release(tmp_path), apothem_home=blocker / "apothem")

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "Could not create the parent directory" in combined, combined
    assert list((tmp_path / "temp").iterdir()) == [], "the download was left behind"


# REUSE-IgnoreEnd
