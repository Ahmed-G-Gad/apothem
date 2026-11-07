# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The PowerShell installer's cosign release mode (``APOTHEM_VERIFY=release``/``auto``).

The Windows counterpart of ``test_installer_release_mode.py``. A stub
``cosign`` (a ``.cmd`` file on Windows, a ``sh`` script elsewhere) records its
arguments and succeeds or fails on request; the fake release is served from a
local HTTP server because ``Invoke-WebRequest`` does not read ``file://`` URLs.
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
IDENTITY = (
    "https://github.com/Ahmed-G-Gad/apothem/.github/workflows/release.yml"
    f"@refs/tags/{TAG}"
)
ISSUER = "https://token.actions.githubusercontent.com"
COSIGN_OK_MARKER = "cosign: SHA256SUMS is signed by the v9.9.9 release workflow"
COSIGN_FAIL_MARKER = "cosign could not confirm that the v9.9.9 release workflow"
INTEGRITY_WARNING = "does not prove who published it"
MISMATCH_MARKER = "does not match the release's SHA256SUMS"

# Permission bits for the stub cosign on POSIX hosts (owner rwx, others rx).
EXECUTABLE_MODE = 0o755

_PWSH = shutil.which("pwsh") or shutil.which("powershell")
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

pytestmark = pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host")
requires_no_host_cosign = pytest.mark.skipif(
    shutil.which("cosign") is not None,
    reason="a cosign on the host PATH would be found instead of none",
)


def _zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{ARCHIVE_ROOT}/src/apothem/__init__.py",
            "# SPDX-License-Identifier: MIT\n",
        )
        archive.writestr(
            f"{ARCHIVE_ROOT}/pyproject.toml",
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


def _publish(
    folder: Path,
    *,
    tamper: bool = False,
    bundle: str | None = "SHA256SUMS.cosign.bundle",
) -> None:
    name = f"apothem-{TAG}-windows.zip"
    data = _zip_bytes()
    (folder / name).write_bytes(data + (b"tampered" if tamper else b""))
    digest = hashlib.sha256(data).hexdigest()
    (folder / "SHA256SUMS").write_bytes(f"{digest}  {name}\n".encode("ascii"))
    if bundle:
        (folder / bundle).write_bytes(b"{}\n")


def _stub_cosign(tmp_path: Path, *, succeed: bool = True) -> Path:
    """Write a stub ``cosign`` and return the directory that holds it.

    The stub writes one argument per line to ``cosign-args.txt`` beside it and
    exits 0, or prints a cosign-style error and exits 1.
    """
    stub_dir = tmp_path / "stub-cosign"
    stub_dir.mkdir()
    args_file = stub_dir / "cosign-args.txt"
    if sys.platform == "win32":
        failure = (
            "echo Error: none of the expected identities matched 1>&2\r\nexit /b 1\r\n"
        )
        (stub_dir / "cosign.cmd").write_text(
            "@echo off\r\n"
            f'(for %%a in (%*) do @echo %%~a) > "{args_file}"\r\n'
            + ("exit /b 0\r\n" if succeed else failure),
            encoding="utf-8",
            newline="",
        )
    else:
        failure = 'echo "Error: none of the expected identities matched" >&2\nexit 1\n'
        stub = stub_dir / "cosign"
        stub.write_text(
            "#!/bin/sh\n"
            f"for arg in \"$@\"; do printf '%s\\n' \"$arg\"; done > '{args_file}'\n"
            + ("exit 0\n" if succeed else failure),
            encoding="utf-8",
            newline="\n",
        )
        stub.chmod(EXECUTABLE_MODE)
    return stub_dir


def _seed_earlier_install(home: Path, *, clone: bool = False) -> None:
    """Lay out what an earlier install leaves at APOTHEM_HOME: a source tree,
    plus the engine's rollback backups and install ledgers beside it."""
    (home / "src" / "apothem").mkdir(parents=True)
    (home / "src" / "apothem" / "removed_module.py").write_text(
        "old\n", encoding="utf-8"
    )
    (home / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (home / "backups" / "claude-code").mkdir(parents=True)
    (home / "backups" / "claude-code" / "set.json").write_text("{}\n", encoding="utf-8")
    (home / "state").mkdir()
    (home / "state" / "ledger.json").write_text("{}\n", encoding="utf-8")
    if clone:
        (home / ".git").mkdir()
        (home / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")


def _assert_engine_data_kept(home: Path) -> None:
    assert (home / "backups" / "claude-code" / "set.json").is_file()
    assert (home / "state" / "ledger.json").is_file()


def _run(
    tmp_path: Path,
    base_url: str,
    *,
    mode: str | None = "release",
    cosign_dir: Path | None = None,
    yes: bool = True,
) -> subprocess.CompletedProcess[str]:
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
            "APOTHEM_RELEASE_BASE": base_url,
            "APOTHEM_REF": TAG,
            "APOTHEM_REPO": str(tmp_path / "no-such-repo"),
            "APOTHEM_HOME": str(tmp_path / "apothem-home"),
            # -Yes lets the installer pip-install a missing click or rich;
            # with no package index that fails instead of changing the host.
            "PIP_NO_INDEX": "1",
            "PIP_CONFIG_FILE": os.devnull,
        }
    )
    if mode is not None:
        env["APOTHEM_VERIFY"] = mode
    if cosign_dir is not None:
        path_key = next((k for k in env if k.upper() == "PATH"), "PATH")
        env[path_key] = f"{cosign_dir}{os.pathsep}{env.get(path_key, os.defpath)}"
    staging = tmp_path / "installer-under-test"
    staging.mkdir(exist_ok=True)
    installer = staging / "install.ps1"
    shutil.copy2(INSTALLER, installer)
    assert _PWSH is not None
    args = [_PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(installer)]
    args += ["-DryRun"] + (["-Yes"] if yes else [])
    return subprocess.run(
        args,
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

    ``Write-Fail`` writes an error record, which PowerShell may colour and
    wrap behind a ``|`` gutter, so a long message can span lines.
    """
    words = _ANSI_ESCAPE.sub("", output).split()
    return " ".join(word for word in words if word != "|")


def _leftovers(tmp_path: Path) -> list[str]:
    """Return any download or staging folder the installer left behind."""
    temp = [
        p.name for p in (tmp_path / "temp").iterdir() if p.name.startswith("apothem-")
    ]
    staged = [
        p.name for p in tmp_path.iterdir() if p.name.startswith(".apothem-extract-")
    ]
    return temp + staged


def test_release_mode_checks_the_exact_workflow_identity(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base_url, cosign_dir=cosign_dir)

    plain = _plain(result.stdout + result.stderr)
    assert COSIGN_OK_MARKER in plain, plain
    assert INTEGRITY_WARNING not in plain, plain
    assert (tmp_path / "apothem-home" / "src" / "apothem" / "__init__.py").is_file()
    args = (cosign_dir / "cosign-args.txt").read_text(encoding="utf-8").splitlines()
    args = [a.strip() for a in args]
    assert args[0] == "verify-blob", args
    assert args[args.index("--certificate-identity") + 1] == IDENTITY, args
    assert args[args.index("--certificate-oidc-issuer") + 1] == ISSUER, args
    assert "--certificate-identity-regexp" not in args, args
    assert args[args.index("--bundle") + 1].endswith("SHA256SUMS.cosign.bundle"), args
    assert args[-1].endswith("SHA256SUMS"), args
    assert _leftovers(tmp_path) == []


def test_auto_mode_takes_the_release_path_when_cosign_is_present(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder)

    result = _run(tmp_path, base_url, mode=None, cosign_dir=_stub_cosign(tmp_path))

    plain = _plain(result.stdout + result.stderr)
    assert "cosign found" in plain, plain
    assert COSIGN_OK_MARKER in plain, plain
    assert (tmp_path / "apothem-home" / "src" / "apothem" / "__init__.py").is_file()


def test_failed_cosign_check_aborts_before_extraction(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder)

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path, succeed=False))

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert COSIGN_FAIL_MARKER in plain, plain
    assert "none of the expected identities matched" in plain, plain
    assert not (tmp_path / "apothem-home" / "src").exists()
    assert _leftovers(tmp_path) == []


def test_digest_mismatch_still_aborts_after_a_good_cosign_check(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder, tamper=True)

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path))

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert COSIGN_OK_MARKER in plain, plain
    assert MISMATCH_MARKER in plain, plain
    assert not (tmp_path / "apothem-home" / "src").exists()


def test_missing_bundle_aborts_with_guidance(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder, bundle=None)

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path))

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert "Could not download SHA256SUMS.cosign.bundle" in plain, plain
    assert "APOTHEM_VERIFY=signature" in plain, plain
    assert _leftovers(tmp_path) == []


def test_the_early_bundle_name_is_read_when_the_current_one_is_absent(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    """Early releases name the SHA256SUMS bundle ``SHA256SUMS.sig``."""
    folder, base_url = release
    _publish(folder, bundle="SHA256SUMS.sig")

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path))

    plain = _plain(result.stdout + result.stderr)
    assert COSIGN_OK_MARKER in plain, plain
    assert (tmp_path / "apothem-home" / "src" / "apothem" / "__init__.py").is_file()


@requires_no_host_cosign
def test_release_mode_without_cosign_fails_before_downloading(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder)

    result = _run(tmp_path, base_url)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert "APOTHEM_VERIFY=release needs cosign on PATH" in plain, plain
    assert _leftovers(tmp_path) == []


def test_an_earlier_install_is_updated_without_yes_and_keeps_engine_data(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path), yes=False)

    plain = _plain(result.stdout + result.stderr)
    assert "Updating the earlier install" in plain, plain
    assert (home / "src" / "apothem" / "__init__.py").is_file(), plain
    assert not (home / "src" / "apothem" / "removed_module.py").exists(), plain
    _assert_engine_data_kept(home)
    assert _leftovers(tmp_path) == []


def test_explicit_release_mode_refuses_a_git_clone_without_yes(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home, clone=True)

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path), yes=False)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert "is a git clone; refusing to replace it" in plain, plain
    assert (home / ".git" / "HEAD").is_file()


def test_auto_mode_keeps_an_existing_clone_on_the_clone_path(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home, clone=True)

    result = _run(tmp_path, base_url, mode=None, cosign_dir=_stub_cosign(tmp_path))

    plain = _plain(result.stdout + result.stderr)
    assert "is a git clone - updating it" in plain, plain
    assert "cosign found" not in plain, plain
    assert (home / ".git" / "HEAD").is_file()
    assert (home / "src" / "apothem" / "removed_module.py").is_file()


def test_other_content_at_apothem_home_is_refused_without_yes(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    home.mkdir()
    sentinel = home / "keep.txt"
    sentinel.write_text("not apothem's to delete\n", encoding="utf-8")

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path), yes=False)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert "holds no Apothem install; refusing to replace it" in plain, plain
    assert sentinel.is_file()
    assert _leftovers(tmp_path) == []


# REUSE-IgnoreEnd
