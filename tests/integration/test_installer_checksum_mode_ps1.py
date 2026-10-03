# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The PowerShell installer's checksum-only mode (``APOTHEM_VERIFY=checksum``).

The Windows counterpart of ``test_installer_checksum_mode.py``. A fake release
holds a zip laid out the way ``scripts/build_release_tarball.py`` writes it,
with every member under ``apothem-<tag>/``, and is served from a local HTTP
server because ``Invoke-WebRequest`` does not read ``file://`` URLs. The tests
run wherever PowerShell 7 or Windows PowerShell is on PATH.
"""

from __future__ import annotations

import functools
import hashlib
import http.server
import io
import os
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
_PWSH = shutil.which("pwsh") or shutil.which("powershell")

pytestmark = pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host")


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


@pytest.fixture
def release(tmp_path: Path) -> Iterator[tuple[Path, str]]:
    """Serve ``<tmp>/releases`` over HTTP; yield (release folder, base URL)."""
    base = tmp_path / "releases"
    folder = base / TAG
    folder.mkdir(parents=True)
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(base)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield folder, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _publish(folder: Path, data: bytes) -> None:
    name = f"apothem-{TAG}-windows.zip"
    (folder / name).write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (folder / "SHA256SUMS").write_bytes(f"{digest}  {name}\n".encode("ascii"))


def _run(tmp_path: Path, base_url: str) -> subprocess.CompletedProcess[str]:
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
            "APOTHEM_REF": TAG,
            "APOTHEM_HOME": str(tmp_path / "apothem-home"),
        }
    )
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
            "-DryRun",
        ],
        cwd=str(staging),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _leftovers(tmp_path: Path) -> list[str]:
    """Return any download or staging folder the installer left behind."""
    temp = [
        p.name for p in (tmp_path / "temp").iterdir() if p.name.startswith("apothem-")
    ]
    staged = [
        p.name for p in tmp_path.iterdir() if p.name.startswith(".apothem-extract-")
    ]
    return temp + staged


def test_release_root_is_moved_into_apothem_home(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder, _zip_bytes(root=ARCHIVE_ROOT))

    result = _run(tmp_path, base_url)

    combined = result.stdout + result.stderr
    assert "does not prove who published it" in combined, combined
    home = tmp_path / "apothem-home"
    assert (home / "src" / "apothem" / "__init__.py").is_file(), combined
    assert (home / "pyproject.toml").is_file(), combined
    assert _leftovers(tmp_path) == []


def test_archive_without_the_release_root_is_refused(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder, _zip_bytes(root=None))

    result = _run(tmp_path, base_url)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert f"does not hold an apothem source under {ARCHIVE_ROOT}" in combined, combined
    assert not (tmp_path / "apothem-home" / "src").exists()
    assert _leftovers(tmp_path) == []


# REUSE-IgnoreEnd
