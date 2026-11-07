# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The POSIX installer's cosign release mode (``APOTHEM_VERIFY=release``/``auto``).

A signed git tag names its commit by SHA-1. The release mode avoids that: it
downloads the release's platform archive, ``SHA256SUMS`` and
``SHA256SUMS.cosign.bundle``, has cosign confirm that the release workflow at
the installed tag signed ``SHA256SUMS``, and only then checks the archive's
SHA-256. ``auto``, the default, takes this path whenever cosign is on PATH.

A stub ``cosign`` records its arguments and succeeds or fails on request, so
the tests check the exact identity the installer asks cosign to verify
without network access or a real Sigstore bundle. The fake release is served
from a ``file://`` base, as in ``test_installer_checksum_mode.py``.
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

# Permission bits for the stub cosign (owner rwx, others rx).
EXECUTABLE_MODE = 0o755

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None
    or shutil.which("curl") is None
    or sys.platform == "win32",
    reason="exercises the POSIX install.sh with curl; install.ps1 is the Windows path",
)
requires_no_host_cosign = pytest.mark.skipif(
    shutil.which("cosign") is not None,
    reason="a cosign on the host PATH would be found instead of none",
)


def _archive_bytes() -> bytes:
    """A minimal apothem-shaped runtime archive laid out like a real release."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, body in (
            ("src/apothem/__init__.py", b"# SPDX-License-Identifier: MIT\n"),
            ("pyproject.toml", b'[project]\nname = "fixture"\nversion = "9.9.9"\n'),
        ):
            info = tarfile.TarInfo(f"{ARCHIVE_ROOT}/{name}")
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


def _platform() -> str:
    return "darwin" if sys.platform == "darwin" else "linux"


def _release(
    tmp_path: Path,
    *,
    tamper: bool = False,
    bundle: str | None = "SHA256SUMS.cosign.bundle",
) -> Path:
    """Write a fake release under ``<base>/<tag>/`` and return the base."""
    base = tmp_path / "releases"
    folder = base / TAG
    folder.mkdir(parents=True)
    name = f"apothem-{TAG}-{_platform()}.tar.gz"
    data = _archive_bytes()
    (folder / name).write_bytes(data + (b"tampered" if tamper else b""))
    digest = hashlib.sha256(data).hexdigest()
    (folder / "SHA256SUMS").write_text(f"{digest}  {name}\n", encoding="utf-8")
    if bundle:
        (folder / bundle).write_text("{}\n", encoding="utf-8")
    return base


def _stub_cosign(tmp_path: Path, *, succeed: bool = True) -> Path:
    """Write a stub ``cosign`` and return the directory that holds it.

    The stub writes one argument per line to ``cosign-args.txt`` beside it
    and exits 0, or prints a cosign-style error and exits 1.
    """
    stub_dir = tmp_path / "stub-cosign"
    stub_dir.mkdir()
    args_file = stub_dir / "cosign-args.txt"
    outcome = (
        "exit 0\n"
        if succeed
        else 'echo "Error: none of the expected identities matched" >&2\nexit 1\n'
    )
    stub = stub_dir / "cosign"
    stub.write_text(
        "#!/bin/sh\n"
        f"for arg in \"$@\"; do printf '%s\\n' \"$arg\"; done > '{args_file}'\n"
        + outcome,
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
    base: Path,
    *,
    mode: str | None = "release",
    cosign_dir: Path | None = None,
    yes: bool = True,
    apothem_home: Path | None = None,
    ref: str = TAG,
) -> subprocess.CompletedProcess[str]:
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
            "APOTHEM_RELEASE_BASE": base.as_uri(),
            "APOTHEM_REF": ref,
            "APOTHEM_REPO": str(tmp_path / "no-such-repo"),
            "APOTHEM_HOME": str(apothem_home or tmp_path / "apothem-home"),
        }
    )
    if mode is not None:
        env["APOTHEM_VERIFY"] = mode
    if cosign_dir is not None:
        env["PATH"] = f"{cosign_dir}{os.pathsep}{env.get('PATH', os.defpath)}"
    staging = tmp_path / "installer-under-test"
    staging.mkdir(exist_ok=True)
    installer = staging / "install.sh"
    shutil.copy2(INSTALLER, installer)
    args = ["bash", str(installer), "--dry-run"]
    if yes:
        args.append("--yes")
    return subprocess.run(
        args,
        cwd=str(staging),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_release_mode_checks_the_exact_workflow_identity(tmp_path: Path) -> None:
    """cosign is asked to verify SHA256SUMS against the release workflow at
    this tag, by exact identity and issuer, and the archive is installed with
    no integrity-only warning."""
    base = _release(tmp_path)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir)

    combined = result.stdout + result.stderr
    assert COSIGN_OK_MARKER in combined, combined
    assert INTEGRITY_WARNING not in combined, combined
    assert (tmp_path / "apothem-home" / "src" / "apothem" / "__init__.py").is_file()
    args = (cosign_dir / "cosign-args.txt").read_text(encoding="utf-8").splitlines()
    assert args[0] == "verify-blob", args
    assert args[args.index("--certificate-identity") + 1] == IDENTITY, args
    assert args[args.index("--certificate-oidc-issuer") + 1] == ISSUER, args
    assert "--certificate-identity-regexp" not in args, args
    assert args[args.index("--bundle") + 1].endswith("SHA256SUMS.cosign.bundle"), args
    assert args[-1].endswith("SHA256SUMS"), args


def test_auto_mode_takes_the_release_path_when_cosign_is_present(
    tmp_path: Path,
) -> None:
    """With APOTHEM_VERIFY unset, a cosign on PATH selects the release path."""
    base = _release(tmp_path)

    result = _run(tmp_path, base, mode=None, cosign_dir=_stub_cosign(tmp_path))

    combined = result.stdout + result.stderr
    assert "cosign found" in combined, combined
    assert COSIGN_OK_MARKER in combined, combined
    assert (tmp_path / "apothem-home" / "src" / "apothem" / "__init__.py").is_file()


def test_failed_cosign_check_aborts_before_extraction(tmp_path: Path) -> None:
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path, succeed=False))

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert COSIGN_FAIL_MARKER in combined, combined
    assert "none of the expected identities matched" in combined, combined
    assert not (tmp_path / "apothem-home" / "src").exists()
    assert list((tmp_path / "temp").iterdir()) == [], "the download was left behind"


def test_digest_mismatch_still_aborts_after_a_good_cosign_check(
    tmp_path: Path,
) -> None:
    """A signed SHA256SUMS does not excuse an archive that does not match it."""
    base = _release(tmp_path, tamper=True)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path))

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert COSIGN_OK_MARKER in combined, combined
    assert MISMATCH_MARKER in combined, combined
    assert not (tmp_path / "apothem-home" / "src").exists()


def test_missing_bundle_aborts_with_guidance(tmp_path: Path) -> None:
    base = _release(tmp_path, bundle=None)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path))

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "Could not download SHA256SUMS.cosign.bundle" in combined, combined
    assert "APOTHEM_VERIFY=signature" in combined, combined
    assert not (tmp_path / "apothem-home" / "src").exists()


def test_the_early_bundle_name_is_read_when_the_current_one_is_absent(
    tmp_path: Path,
) -> None:
    """Early releases name the SHA256SUMS bundle ``SHA256SUMS.sig``."""
    base = _release(tmp_path, bundle="SHA256SUMS.sig")

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path))

    combined = result.stdout + result.stderr
    assert COSIGN_OK_MARKER in combined, combined
    assert (tmp_path / "apothem-home" / "src" / "apothem" / "__init__.py").is_file()


@requires_no_host_cosign
def test_release_mode_without_cosign_fails_before_downloading(tmp_path: Path) -> None:
    base = _release(tmp_path)

    result = _run(tmp_path, base)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "APOTHEM_VERIFY=release needs cosign on PATH" in combined, combined
    assert list((tmp_path / "temp").iterdir()) == [], combined


def test_an_earlier_install_is_updated_without_yes_and_keeps_engine_data(
    tmp_path: Path,
) -> None:
    """An earlier archive install is updated in place without --yes. Only the
    entries the archive ships are replaced, so the engine's backups/ and
    state/ survive, and a module the new release dropped goes with src/."""
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=False)

    combined = result.stdout + result.stderr
    assert "Updating the earlier install" in combined, combined
    assert (home / "src" / "apothem" / "__init__.py").is_file(), combined
    assert not (home / "src" / "apothem" / "removed_module.py").exists(), combined
    _assert_engine_data_kept(home)
    assert not list(tmp_path.glob(".apothem-extract-*")), "staging left behind"


def test_explicit_release_mode_refuses_a_git_clone_without_yes(tmp_path: Path) -> None:
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home, clone=True)
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=False)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "is a git clone; refusing to replace it" in combined, combined
    assert (home / ".git" / "HEAD").is_file()
    assert (home / "src" / "apothem" / "removed_module.py").is_file()


def test_yes_replaces_a_clone_source_and_keeps_engine_data(tmp_path: Path) -> None:
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home, clone=True)
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True)

    combined = result.stdout + result.stderr
    assert "its git history is removed" in combined, combined
    assert not (home / ".git").exists(), combined
    assert (home / "src" / "apothem" / "__init__.py").is_file(), combined
    _assert_engine_data_kept(home)


def test_auto_mode_keeps_an_existing_clone_on_the_clone_path(tmp_path: Path) -> None:
    """With cosign present, auto still updates an existing clone through the
    tag check instead of replacing it with the archive."""
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home, clone=True)
    base = _release(tmp_path)

    result = _run(tmp_path, base, mode=None, cosign_dir=_stub_cosign(tmp_path))

    combined = result.stdout + result.stderr
    assert "is a git clone — updating it" in combined, combined
    assert "cosign found" not in combined, combined
    assert (home / ".git" / "HEAD").is_file()
    assert (home / "src" / "apothem" / "removed_module.py").is_file()


def test_auto_mode_sends_a_branch_ref_to_the_clone_path(tmp_path: Path) -> None:
    base = _release(tmp_path)

    result = _run(
        tmp_path, base, mode=None, cosign_dir=_stub_cosign(tmp_path), ref="main"
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "cosign found" not in combined, combined
    assert not (tmp_path / "stub-cosign" / "cosign-args.txt").exists(), combined


@requires_no_host_cosign
def test_auto_mode_without_cosign_takes_the_tag_check(tmp_path: Path) -> None:
    base = _release(tmp_path)

    result = _run(tmp_path, base, mode=None)

    combined = result.stdout + result.stderr
    assert "cosign not found — checking the release tag's signature" in combined
    assert (
        not (tmp_path / "apothem-home" / "src").exists()
        or (tmp_path / "apothem-home" / ".git").exists()
    ), combined


def test_other_content_at_apothem_home_is_refused_without_yes(tmp_path: Path) -> None:
    home = tmp_path / "apothem-home"
    home.mkdir()
    sentinel = home / "keep.txt"
    sentinel.write_text("not apothem's to delete\n", encoding="utf-8")
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=False)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "holds no Apothem install; refusing to replace it" in combined, combined
    assert sentinel.is_file()


# REUSE-IgnoreEnd
