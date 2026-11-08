# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The PowerShell installer's checksum-only mode (``APOTHEM_VERIFY=checksum``).

The Windows counterpart of ``test_installer_checksum_mode.py``. A fake release
holds a zip laid out the way ``scripts/build_release_tarball.py`` writes it,
with every member under ``apothem-<tag>/``, and is served from a local HTTP
server because ``Invoke-WebRequest`` does not read ``file://`` URLs. The
server records each request, so a test can tell whether anything was
downloaded. The mode verifies nothing about who published the release, so it
runs only with ``APOTHEM_ALLOW_UNVERIFIED=1``: without it the installer stops
before downloading anything, and with it the installer says so before the
download starts. The tests run wherever PowerShell 7 or Windows PowerShell is
on PATH.
"""

from __future__ import annotations

import functools
import hashlib
import http.server
import io
import os
import re
import shutil
import subprocess
import sys
import threading
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "installer" / "install.ps1"
TAG = "v9.9.9"

_SCRIPTS = REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import build_release_tarball as brt  # noqa: E402

ARCHIVE_ROOT = brt._archive_root("apothem", TAG.removeprefix("v"))
# The caveat install.ps1 prints for checksum mode, before downloading; the
# same words as install.sh's.
CHECKSUM_CAVEAT = (
    "Checksum mode does not verify the release. SHA256SUMS comes from the same "
    "release as the archive, so a match only shows the download isn't damaged; "
    "anyone who can change the release's files can change both."
)
GATE_MARKER = "Set APOTHEM_ALLOW_UNVERIFIED=1 as well to install this way anyway"
PROCEEDING_MARKER = "Proceeding because APOTHEM_ALLOW_UNVERIFIED=1."
DOWNLOAD_MARKER = "Downloading apothem-"
MISMATCH_MARKER = "does not match the release's SHA256SUMS"

_PWSH = shutil.which("pwsh") or shutil.which("powershell")

pytestmark = pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host")

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _zip_bytes(*, root: str | None) -> bytes:
    prefix = f"{root}/" if root else ""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{prefix}src/apothem/__init__.py", "# SPDX-License-Identifier: MIT\n"
        )
        archive.writestr(
            f"{prefix}pyproject.toml",
            '[project]\nname = "fixture"\nversion = "9.9.9"\n',
        )
    return buffer.getvalue()


def _recording_handler(
    requests: list[str],
) -> type[http.server.SimpleHTTPRequestHandler]:
    """A file-serving handler that records each requested path in REQUESTS."""

    class RecordingHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            super().do_GET()

    return RecordingHandler


class Release:
    """A fake release served over HTTP: its folder, base URL and requests."""

    def __init__(self, folder: Path, base_url: str, requests: list[str]) -> None:
        self.folder = folder
        self.base_url = base_url
        self.requests = requests


@pytest.fixture
def release(tmp_path: Path) -> Iterator[Release]:
    """Serve ``<tmp>/releases`` over HTTP and yield the fake release."""
    base = tmp_path / "releases"
    folder = base / TAG
    folder.mkdir(parents=True)
    requests: list[str] = []
    handler = functools.partial(_recording_handler(requests), directory=str(base))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Release(folder, f"http://127.0.0.1:{server.server_address[1]}", requests)
    finally:
        server.shutdown()
        server.server_close()


def _publish(folder: Path, data: bytes, *, tamper: bool = False) -> None:
    name = f"apothem-{TAG}-windows.zip"
    (folder / name).write_bytes(data + (b"tampered" if tamper else b""))
    digest = hashlib.sha256(data).hexdigest()
    (folder / "SHA256SUMS").write_bytes(f"{digest}  {name}\n".encode("ascii"))


def _run(
    tmp_path: Path,
    base_url: str,
    apothem_home: Path | None = None,
    *,
    ref: str = TAG,
    allow_unverified: bool = True,
    dry_run: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run install.ps1 -Yes in checksum mode against the fake release, with
    APOTHEM_ALLOW_UNVERIFIED=1 unless ALLOW_UNVERIFIED is false."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    temp = tmp_path / "temp"
    temp.mkdir(exist_ok=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("APOTHEM_")
        and key.upper() not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "PYTHONPATH"}
    }
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "TMPDIR": str(temp),
            "TEMP": str(temp),
            "TMP": str(temp),
            "NO_PROXY": "127.0.0.1,localhost",
            "APOTHEM_VERIFY": "checksum",
            "APOTHEM_RELEASE_BASE": base_url,
            "APOTHEM_REF": ref,
            "APOTHEM_HOME": str(apothem_home or tmp_path / "apothem-home"),
            # -Yes lets the installer pip-install a missing click or rich;
            # with no package index that fails instead of changing the host.
            "PIP_NO_INDEX": "1",
            "PIP_CONFIG_FILE": os.devnull,
        }
    )
    if allow_unverified:
        env["APOTHEM_ALLOW_UNVERIFIED"] = "1"
    staging = tmp_path / "installer-under-test"
    staging.mkdir(exist_ok=True)
    installer = staging / "install.ps1"
    shutil.copy2(INSTALLER, installer)
    assert _PWSH is not None
    return subprocess.run(
        [
            _PWSH,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(installer),
            "-Yes",
            *(["-DryRun"] if dry_run else []),
        ],
        cwd=str(staging),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _plain(output: str) -> str:
    """Return installer output as single-spaced words, as a reader sees them.

    ``Write-Fail`` writes an error record. PowerShell renders it in its concise
    error view, which colours the text and wraps it at the console width behind
    a ``|`` gutter, so a long message can be split across lines (the macOS
    runner wraps at 80 columns).
    """
    words = _ANSI_ESCAPE.sub("", output).split()
    return " ".join(word for word in words if word != "|")


def _leftovers(tmp_path: Path) -> list[str]:
    """Return any download or staging folder the installer left behind."""
    temp = [
        p.name for p in (tmp_path / "temp").iterdir() if p.name.startswith("apothem-")
    ]
    staged = [p.name for p in tmp_path.iterdir() if p.name.startswith(".apothem-")]
    return temp + staged


@pytest.mark.parametrize("dry_run", [False, True], ids=["install", "dry-run"])
def test_checksum_mode_is_refused_without_allow_unverified(
    tmp_path: Path, release: Release, dry_run: bool
) -> None:
    """Without APOTHEM_ALLOW_UNVERIFIED=1 the mode stops with the caveat
    before anything is downloaded or placed, in a dry run too."""
    _publish(release.folder, _zip_bytes(root=ARCHIVE_ROOT))

    result = _run(tmp_path, release.base_url, allow_unverified=False, dry_run=dry_run)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert CHECKSUM_CAVEAT in plain, plain
    assert GATE_MARKER in plain, plain
    assert DOWNLOAD_MARKER not in plain, plain
    assert release.requests == [], plain
    assert not (tmp_path / "apothem-home").exists(), plain
    assert _leftovers(tmp_path) == []


def test_allow_unverified_warns_before_downloading(
    tmp_path: Path, release: Release
) -> None:
    """With APOTHEM_ALLOW_UNVERIFIED=1 the caveat comes first, as a warning,
    and only then the download starts."""
    _publish(release.folder, _zip_bytes(root=ARCHIVE_ROOT))

    result = _run(tmp_path, release.base_url)

    plain = _plain(result.stdout + result.stderr)
    assert plain.count(CHECKSUM_CAVEAT) == 1, plain
    warning = plain.index(CHECKSUM_CAVEAT)
    assert plain.index(PROCEEDING_MARKER) > warning, plain
    assert plain.index(DOWNLOAD_MARKER) > warning, plain
    assert GATE_MARKER not in plain, plain
    assert release.requests, "the archive was never downloaded"


def test_release_root_is_moved_into_apothem_home(
    tmp_path: Path, release: Release
) -> None:
    _publish(release.folder, _zip_bytes(root=ARCHIVE_ROOT))

    result = _run(tmp_path, release.base_url)

    plain = _plain(result.stdout + result.stderr)
    assert CHECKSUM_CAVEAT in plain, plain
    assert "matches the release's SHA256SUMS" in plain, plain
    home = tmp_path / "apothem-home"
    assert (home / "src" / "apothem" / "__init__.py").is_file(), plain
    assert (home / "pyproject.toml").is_file(), plain
    assert _leftovers(tmp_path) == []


def test_tampered_archive_aborts_before_extraction(
    tmp_path: Path, release: Release
) -> None:
    _publish(release.folder, _zip_bytes(root=ARCHIVE_ROOT), tamper=True)

    result = _run(tmp_path, release.base_url)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert MISMATCH_MARKER in plain, plain
    assert not (tmp_path / "apothem-home" / "src").exists()
    assert _leftovers(tmp_path) == []


def test_checksum_mode_needs_a_release_tag(tmp_path: Path, release: Release) -> None:
    _publish(release.folder, _zip_bytes(root=ARCHIVE_ROOT))

    result = _run(tmp_path, release.base_url, ref="main")

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert "needs a vMAJOR.MINOR.PATCH release tag" in plain, plain
    assert release.requests == [], plain


def test_archive_without_the_release_root_is_refused(
    tmp_path: Path, release: Release
) -> None:
    _publish(release.folder, _zip_bytes(root=None))

    result = _run(tmp_path, release.base_url)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    expected = f"does not hold an apothem source under {ARCHIVE_ROOT}"
    assert expected in plain, plain
    assert not (tmp_path / "apothem-home" / "src").exists()
    assert _leftovers(tmp_path) == []


def test_a_destination_that_cannot_be_created_leaves_no_download(
    tmp_path: Path, release: Release
) -> None:
    _publish(release.folder, _zip_bytes(root=ARCHIVE_ROOT))
    blocker = tmp_path / "a-file"
    blocker.write_text("", encoding="utf-8")

    result = _run(tmp_path, release.base_url, apothem_home=blocker / "apothem")

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert "Could not create the parent directory of" in plain, plain
    assert _leftovers(tmp_path) == []


# REUSE-IgnoreEnd
