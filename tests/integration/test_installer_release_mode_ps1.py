# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The PowerShell installer's cosign release mode (``APOTHEM_VERIFY=release``/``auto``),
its clone path's tag gate and swap, and the PowerShell updater's tag gate.

The Windows counterpart of ``test_installer_release_mode.py``. A stub
``cosign`` (a ``.cmd`` file on Windows, a ``sh`` script elsewhere) records its
arguments and succeeds or fails on request; a stub gpg (a ``sh`` script, which
Git for Windows runs through its own sh) replays a canned GnuPG result for the
fixture repository's tags. The installers read nothing from the bundle, so
any bundle text serves; what matters is that cosign is asked to check the
signed tag's commit (``--certificate-github-workflow-sha``). The fake release
is served from a local HTTP server because ``Invoke-WebRequest`` does not
read ``file://`` URLs.
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
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from tests._shared.git_env import hermetic_git_env
from tests._shared.release_fixture import (
    MAINTAINER_FINGERPRINT,
    OTHER_FINGERPRINT,
    git,
    good_signature_status,
    make_tagged_repo,
    repoint_tag,
    write_stub_gpg,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "installer" / "install.ps1"
UPDATER = REPO_ROOT / "scripts" / "installer" / "update.ps1"
TAG = "v9.9.9"
OLD_TAG = "v9.9.8"

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
CHECKSUM_CAVEAT = "Checksum mode does not verify the release."
MISMATCH_MARKER = "does not match the release's SHA256SUMS"
TAG_OK_MARKER = "carries a valid signature from the maintainer key"
BAD_SIGNATURE_MARKER = "is unsigned or its signature did not verify"
REPOINT_MARKER = (
    "the signed tag object is not the v9.9.9 release tag (it names another tag, "
    "or no commit), so it was re-pointed (possible tampering)"
)
LOCAL_CHANGES_MARKER = "If it has local changes, commit or stash them, then re-run."
TRACKED_CHANGES_MARKER = (
    "has changes to tracked files. Commit or stash them, then re-run."
)
LOCAL_WORK_MARKER = (
    "is a git clone with local work that replacing it would lose (changes, "
    "stashes, unpushed commits, or untracked files in its source tree). Commit "
    "and push that work, or move it elsewhere, then re-run."
)
WORK_TREE_MARKER = (
    "is not the work tree of its git clone (core.worktree is set, or its .git "
    "points elsewhere). Remove that setting, then re-run."
)
TRUSTED_CONFIG_MARKER = ", which the update would trust. Remove it from"
KEPT_TREE_MARKER = "The earlier clone's tree is kept at"
NO_HOME_MARKER = "holds no Apothem install; refusing to replace it"
ROLLBACK_FAILED_MARKER = "and putting the earlier install back also failed: it is at"
LINK_MARKER = (
    "is a symbolic link. Point APOTHEM_HOME at the folder it links to, then re-run."
)
ASIDE_MARKER = "were moved, unchanged, to"
ROLLED_BACK_MARKER = "is back in place and unchanged"
DRY_RUN_MARKER = "dry run, so"
SOURCE_MANIFEST = ".apothem-source-entries"
# Any text serves as the bundle: the installer hands it to cosign unread.
BUNDLE_TEXT = "{}\n"
# A release base no test that takes the clone path downloads from.
UNUSED_BASE = "http://127.0.0.1:9"

# Permission bits for the stub cosign on POSIX hosts (owner rwx, others rx).
EXECUTABLE_MODE = 0o755

_PWSH = shutil.which("pwsh") or shutil.which("powershell")
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

pytestmark = pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host")
requires_no_host_cosign = pytest.mark.skipif(
    shutil.which("cosign") is not None,
    reason="a cosign on the host PATH would be found instead of none",
)
requires_windows = pytest.mark.skipif(
    sys.platform != "win32",
    reason="holds a file open to make a Windows rename fail",
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
) -> str:
    """Write a fixture repository tagged TAG beside the release tree and the
    release files into FOLDER; return the tag's commit."""
    _, commit = make_tagged_repo(folder.parent.parent, TAG)
    name = f"apothem-{TAG}-windows.zip"
    data = _zip_bytes()
    (folder / name).write_bytes(data + (b"tampered" if tamper else b""))
    digest = hashlib.sha256(data).hexdigest()
    (folder / "SHA256SUMS").write_bytes(f"{digest}  {name}\n".encode("ascii"))
    if bundle:
        (folder / bundle).write_text(BUNDLE_TEXT, encoding="utf-8")
    return commit


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
            "echo Error: expected GitHub Workflow SHA not found in certificate 1>&2\r\n"
            "exit /b 1\r\n"
        )
        (stub_dir / "cosign.cmd").write_text(
            "@echo off\r\n"
            f'(for %%a in (%*) do @echo %%~a) > "{args_file}"\r\n'
            + ("exit /b 0\r\n" if succeed else failure),
            encoding="utf-8",
            newline="",
        )
    else:
        failure = (
            'echo "Error: expected GitHub Workflow SHA not found in certificate" >&2\n'
            "exit 1\n"
        )
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


def _cosign_args(cosign_dir: Path) -> list[str]:
    """The arguments the stub cosign was called with, one per element."""
    lines = (cosign_dir / "cosign-args.txt").read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines]


def _seed_earlier_install(home: Path, *, clone: bool = False) -> None:
    """Lay out what an earlier install leaves at APOTHEM_HOME: a source tree,
    plus the engine's rollback backups and install ledgers beside it."""
    (home / "src" / "apothem").mkdir(parents=True)
    (home / "src" / "apothem" / "removed_module.py").write_text(
        "old\n", encoding="utf-8"
    )
    (home / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    _seed_engine_data(home)
    if clone:
        (home / ".git").mkdir()
        (home / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")


def _seed_engine_data(home: Path) -> None:
    """Write the engine's rollback backups and install ledger into HOME."""
    (home / "backups" / "claude-code").mkdir(parents=True)
    (home / "backups" / "claude-code" / "set.json").write_text("{}\n", encoding="utf-8")
    (home / "state").mkdir()
    (home / "state" / "ledger.json").write_text("{}\n", encoding="utf-8")


def _assert_engine_data_kept(home: Path) -> None:
    assert (home / "backups" / "claude-code" / "set.json").is_file()
    assert (home / "state" / "ledger.json").is_file()


def _snapshot(root: Path) -> dict[str, str]:
    """Every file under ROOT, by relative path, with its text."""
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _env(
    tmp_path: Path,
    *,
    gpg_status: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """The scripts' environment: an isolated HOME and temp folder, the
    fixture repository as the remote, and a stub gpg that replays GPG_STATUS
    (a good maintainer signature by default)."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    temp = tmp_path / "temp"
    temp.mkdir(exist_ok=True)
    env = {
        key: value
        for key, value in hermetic_git_env().items()
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
            "APOTHEM_REF": TAG,
            "APOTHEM_REPO": str(tmp_path / "fixture-repo"),
            "APOTHEM_HOME": str(tmp_path / "apothem-home"),
            # -Yes lets the installer pip-install a missing click or rich;
            # with no package index that fails instead of changing the host.
            "PIP_NO_INDEX": "1",
            "PIP_CONFIG_FILE": os.devnull,
        }
    )
    status = gpg_status
    if status is None:
        status = good_signature_status(MAINTAINER_FINGERPRINT)
    env["GIT_CONFIG_GLOBAL"] = str(write_stub_gpg(tmp_path / "stub-gpg", status))
    env.update(extra_env or {})
    return env


def _run(
    tmp_path: Path,
    base_url: str,
    *,
    mode: str | None = "release",
    cosign_dir: Path | None = None,
    yes: bool = True,
    dry_run: bool = False,
    gpg_status: str | None = None,
    extra_env: dict[str, str] | None = None,
    patch: Callable[[str], str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run install.ps1 against the fixture release; the tag check reads
    GPG_STATUS from a stub gpg (a good maintainer signature by default).
    PATCH, when given, rewrites the copy of the script that runs (fault
    injection)."""
    env = _env(tmp_path, gpg_status=gpg_status, extra_env=extra_env)
    env["APOTHEM_RELEASE_BASE"] = base_url
    if mode is not None:
        env["APOTHEM_VERIFY"] = mode
    if cosign_dir is not None:
        path_key = next((k for k in env if k.upper() == "PATH"), "PATH")
        env[path_key] = f"{cosign_dir}{os.pathsep}{env.get(path_key, os.defpath)}"
    staging = tmp_path / "installer-under-test"
    staging.mkdir(exist_ok=True)
    installer = staging / "install.ps1"
    shutil.copy2(INSTALLER, installer)
    if patch is not None:
        text = installer.read_bytes().decode("ascii")
        installer.write_bytes(patch(text).encode("ascii"))
    assert _PWSH is not None
    args = [_PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(installer)]
    args += (["-DryRun"] if dry_run else []) + (["-Yes"] if yes else [])
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


def _run_updater(
    tmp_path: Path,
    *,
    gpg_status: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run update.ps1 against the clone at APOTHEM_HOME."""
    env = _env(tmp_path, gpg_status=gpg_status, extra_env=extra_env)
    assert _PWSH is not None
    return subprocess.run(
        [_PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(UPDATER)],
        cwd=env["HOME"],
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


def _squashed(text: str) -> str:
    """TEXT without whitespace. Windows PowerShell 5.1 wraps an error record
    at the console width, which can split a long path; compare a message that
    holds one this way."""
    return re.sub(r"\s+", "", text)


def _leftovers(tmp_path: Path) -> list[str]:
    """Return any download or staging folder the installer left behind."""
    temp = [
        p.name for p in (tmp_path / "temp").iterdir() if p.name.startswith("apothem-")
    ]
    staged = [p.name for p in tmp_path.iterdir() if p.name.startswith(".apothem-")]
    return temp + staged


def _head(repo: Path) -> str:
    return git(["rev-parse", "HEAD"], repo).strip()


def _clone_at_old_tag(tmp_path: Path) -> tuple[Path, Path, str]:
    """Make a fixture repository tagged OLD_TAG and a clone of it at
    APOTHEM_HOME checked out at that tag, then add a commit to the fixture
    that changes pyproject.toml and adds new-file.txt. Return (fixture,
    clone, the old tag's commit); the caller tags the new commit."""
    repo, old_commit = make_tagged_repo(tmp_path, OLD_TAG)
    home = tmp_path / "apothem-home"
    git(["clone", "--quiet", str(repo), str(home)], tmp_path)
    git(["checkout", "--quiet", f"refs/tags/{OLD_TAG}"], home)
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "9.9.9"\n', encoding="utf-8"
    )
    (repo / "new-file.txt").write_text("from the new release\n", encoding="utf-8")
    git(["add", "-A"], repo)
    git(["commit", "--quiet", "-m", "next release"], repo)
    return repo, home, old_commit


def _make_junction(link: Path, target: Path) -> None:
    """Make LINK a junction to TARGET on Windows, a symbolic link elsewhere."""
    if sys.platform != "win32":
        link.symlink_to(target, target_is_directory=True)
        return
    assert _PWSH is not None
    subprocess.run(
        [
            _PWSH,
            "-NoProfile",
            "-Command",
            "New-Item -ItemType Junction -Path $env:LINK -Target $env:TARGET | Out-Null",
        ],
        env={**os.environ, "LINK": str(link), "TARGET": str(target)},
        check=True,
        capture_output=True,
        timeout=60,
    )


# Release mode ---------------------------------------------------------------


def test_release_mode_checks_the_exact_workflow_identity_and_the_tag_commit(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    commit = _publish(folder)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base_url, cosign_dir=cosign_dir)

    plain = _plain(result.stdout + result.stderr)
    assert TAG_OK_MARKER in plain, plain
    assert f"{COSIGN_OK_MARKER}, in a run on the tag's commit {commit}" in plain, plain
    assert CHECKSUM_CAVEAT not in plain, plain
    assert (tmp_path / "apothem-home" / "src" / "apothem" / "__init__.py").is_file()
    args = _cosign_args(cosign_dir)
    assert args[0] == "verify-blob", args
    assert args[args.index("--certificate-identity") + 1] == IDENTITY, args
    assert args[args.index("--certificate-oidc-issuer") + 1] == ISSUER, args
    assert args[args.index("--certificate-github-workflow-sha") + 1] == commit, args
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
    commit = _publish(folder)

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path, succeed=False))

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert COSIGN_FAIL_MARKER in plain, plain
    assert f"in a run on the signed tag's commit {commit} (possible tampering)" in plain
    assert "expected GitHub Workflow SHA not found in certificate" in plain, plain
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
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base_url, cosign_dir=cosign_dir)

    plain = _plain(result.stdout + result.stderr)
    assert COSIGN_OK_MARKER in plain, plain
    assert "--certificate-github-workflow-sha" in _cosign_args(cosign_dir)
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


@pytest.mark.parametrize(
    ("status", "marker"),
    [
        pytest.param(
            good_signature_status(OTHER_FINGERPRINT),
            "not from the maintainer key",
            id="another-key",
        ),
        pytest.param("", BAD_SIGNATURE_MARKER, id="unsigned"),
    ],
)
def test_a_cosign_valid_release_without_the_maintainer_tag_is_refused(
    tmp_path: Path, release: tuple[Path, str], status: str, marker: str
) -> None:
    """The release path never downgrades the tag check, even with
    APOTHEM_ALLOW_UNVERIFIED=1, and cosign is never asked."""
    folder, base_url = release
    _publish(folder)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(
        tmp_path,
        base_url,
        cosign_dir=cosign_dir,
        gpg_status=status,
        extra_env={"APOTHEM_ALLOW_UNVERIFIED": "1"},
    )

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert marker in plain, plain
    assert not (cosign_dir / "cosign-args.txt").exists(), plain
    assert not (tmp_path / "apothem-home").exists(), plain


@pytest.mark.parametrize("allow", [False, True], ids=["default", "allow-unverified"])
def test_release_mode_refuses_a_re_pointed_signed_tag(
    tmp_path: Path, release: tuple[Path, str], allow: bool
) -> None:
    """A maintainer-signed tag object that names another release, moved onto
    refs/tags/TAG, is refused before cosign runs or anything downloads,
    APOTHEM_ALLOW_UNVERIFIED=1 or not."""
    folder, base_url = release
    _publish(folder)
    repoint_tag(tmp_path / "fixture-repo", OLD_TAG, TAG)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(
        tmp_path,
        base_url,
        cosign_dir=cosign_dir,
        extra_env={"APOTHEM_ALLOW_UNVERIFIED": "1"} if allow else None,
    )

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert REPOINT_MARKER in plain, plain
    assert TAG_OK_MARKER not in plain, plain
    assert "Downloading" not in plain, plain
    assert not (cosign_dir / "cosign-args.txt").exists(), plain
    assert not (tmp_path / "apothem-home").exists(), plain
    assert _leftovers(tmp_path) == []


def test_dry_run_leaves_apothem_home_alone(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    before = _snapshot(home)

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path), dry_run=True)

    plain = _plain(result.stdout + result.stderr)
    assert COSIGN_OK_MARKER in plain, plain
    assert DRY_RUN_MARKER in plain, plain
    assert _snapshot(home) == before, plain
    assert _leftovers(tmp_path) == []


# What a swap does with what is at APOTHEM_HOME ------------------------------


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


def test_an_archive_install_records_its_source_entries(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    """The archive install writes the manifest of the names it shipped, its
    own name included, before the swap, so the engine data carried in later
    is not listed."""
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path), yes=False)

    plain = _plain(result.stdout + result.stderr)
    manifest = home / SOURCE_MANIFEST
    assert manifest.is_file(), plain
    data = manifest.read_bytes()
    assert b"\r" not in data, data
    assert data.decode("ascii").splitlines() == sorted(
        [SOURCE_MANIFEST, "pyproject.toml", "src"]
    ), data
    _assert_engine_data_kept(home)


def test_an_archive_update_drops_what_the_earlier_release_shipped(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    """An earlier archive install's manifest says which top-level names were
    its source: one the new release no longer ships goes, while names the
    manifest does not list (engine or user data) stay."""
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    (home / "retired.txt").write_text("shipped by the earlier release\n", "utf-8")
    (home / "notes").mkdir()
    (home / "notes" / "mine.txt").write_text("the user's\n", encoding="utf-8")
    (home / SOURCE_MANIFEST).write_text(
        f"{SOURCE_MANIFEST}\npyproject.toml\nretired.txt\nsrc\n", encoding="utf-8"
    )

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path), yes=False)

    plain = _plain(result.stdout + result.stderr)
    assert (home / "src" / "apothem" / "__init__.py").is_file(), plain
    assert not (home / "retired.txt").exists(), plain
    assert (home / "notes" / "mine.txt").is_file(), plain
    _assert_engine_data_kept(home)
    lines = (home / SOURCE_MANIFEST).read_text(encoding="utf-8").splitlines()
    assert "retired.txt" not in lines, lines
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
    assert (home / "src" / "apothem" / "removed_module.py").is_file()


def test_yes_switches_a_clone_to_the_archive_and_keeps_only_untracked_data(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    """With -Yes the archive replaces a real clone: .git and every top-level
    entry the clone tracks go, even one the archive does not ship, while what
    the clone does not track (the engine's backups and state) stays."""
    folder, base_url = release
    _publish(folder)
    repo = tmp_path / "fixture-repo"
    (repo / "tracked-only.md").write_text("tracked by the clone\n", encoding="utf-8")
    git(["add", "-A"], repo)
    git(["commit", "--quiet", "-m", "a file only the clone has"], repo)
    home = tmp_path / "apothem-home"
    git(["clone", "--quiet", str(repo), str(home)], tmp_path)
    _seed_engine_data(home)

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path), yes=True)

    plain = _plain(result.stdout + result.stderr)
    assert "the clone's own tree will be moved to a sibling folder named" in plain, (
        plain
    )
    assert not (home / ".git").exists(), plain
    assert not (home / "tracked-only.md").exists(), plain
    assert (home / "src" / "apothem" / "__init__.py").is_file(), plain
    assert (home / SOURCE_MANIFEST).is_file(), plain
    _assert_engine_data_kept(home)
    # The clone's tree is not deleted: it is kept beside APOTHEM_HOME, its
    # data aside, and the run says where.
    kept = sorted(tmp_path.glob("apothem-home.before-apothem-*"))
    assert len(kept) == 1, plain
    assert (kept[0] / ".git").is_dir(), plain
    assert (kept[0] / "tracked-only.md").is_file(), plain
    assert not (kept[0] / "state").exists(), plain
    message = f"{KEPT_TREE_MARKER} {kept[0]}; delete it once you no longer need it."
    assert _squashed(message) in _squashed(plain), plain
    assert _leftovers(tmp_path) == []


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
    assert "re-run with -Yes to have it moved aside for you" in plain, plain
    assert sentinel.is_file()
    assert _leftovers(tmp_path) == []


@pytest.mark.parametrize("mode", ["release", "signature"])
def test_yes_moves_other_content_aside_unchanged(
    tmp_path: Path, release: tuple[Path, str], mode: str
) -> None:
    """-Yes on a folder that holds no Apothem install moves the whole folder,
    unchanged, to a sibling <home>.before-apothem-<time>, says where, and
    installs fresh, from the archive or a clone."""
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    (home / "sub").mkdir(parents=True)
    (home / "keep.txt").write_text("not apothem's to delete\n", encoding="utf-8")
    (home / "sub" / "deeper.txt").write_text("nested\n", encoding="utf-8")
    before = _snapshot(home)

    result = _run(
        tmp_path, base_url, mode=mode, cosign_dir=_stub_cosign(tmp_path), yes=True
    )

    plain = _plain(result.stdout + result.stderr)
    asides = sorted(tmp_path.glob("apothem-home.before-apothem-*"))
    assert len(asides) == 1, plain
    aside = asides[0]
    assert re.fullmatch(r"apothem-home\.before-apothem-\d{14}", aside.name), aside
    assert _snapshot(aside) == before, plain
    assert f"{ASIDE_MARKER} {aside}" in plain, plain
    assert (home / "src" / "apothem" / "__init__.py").is_file(), plain
    assert not (home / "keep.txt").exists(), plain
    assert _leftovers(tmp_path) == []


@pytest.mark.parametrize(
    ("mode", "dry_run"),
    [
        pytest.param("release", False, id="release"),
        pytest.param("signature", False, id="clone"),
        pytest.param("release", True, id="release-dry-run"),
        pytest.param("signature", True, id="clone-dry-run"),
    ],
)
def test_a_linked_apothem_home_is_refused(
    tmp_path: Path, release: tuple[Path, str], mode: str, dry_run: bool
) -> None:
    """APOTHEM_HOME as a junction (a symbolic link off Windows) is refused
    before anything is fetched, in a dry run too, and its target is left as
    it was: a swap would replace the link, not the folder it points at."""
    folder, base_url = release
    _publish(folder)
    target = tmp_path / "real-home"
    _seed_earlier_install(target)
    before = _snapshot(target)
    home = tmp_path / "apothem-home"
    _make_junction(home, target)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base_url, mode=mode, cosign_dir=cosign_dir, dry_run=dry_run)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert f"Destination {home} {LINK_MARKER}" in plain, plain
    assert "Cloning" not in plain, plain
    assert "Downloading" not in plain, plain
    assert _snapshot(target) == before, plain
    assert os.path.lexists(home), plain
    assert _leftovers(tmp_path) == []


@requires_windows
@pytest.mark.parametrize(
    ("held_open", "reason"),
    [
        pytest.param(
            "state/ledger.json",
            "Could not move state into the new install",
            id="carry-fails",
        ),
        pytest.param(
            "pyproject.toml",
            "Could not move the existing",
            id="move-aside-fails",
        ),
    ],
)
def test_a_failed_swap_puts_the_earlier_install_back(
    tmp_path: Path, release: tuple[Path, str], held_open: str, reason: str
) -> None:
    """A rename Windows refuses (a file held open inside the folder) stops
    the swap partway; every entry already moved goes back, and the run says
    the earlier install is back in place and unchanged."""
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    before = _snapshot(home)

    with (home / held_open).open("rb"):
        result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path), yes=False)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert reason in plain, plain
    assert f"the earlier install at {home} {ROLLED_BACK_MARKER}" in plain, plain
    assert _snapshot(home) == before, plain
    assert _leftovers(tmp_path) == []


# The clone path -------------------------------------------------------------


@pytest.mark.parametrize("allow", [False, True], ids=["default", "allow-unverified"])
def test_the_clone_path_refuses_a_re_pointed_signed_tag(
    tmp_path: Path, allow: bool
) -> None:
    """A fresh clone whose TAG is a re-pointed maintainer-signed tag object is
    refused before anything is checked out or placed, even with
    APOTHEM_ALLOW_UNVERIFIED=1, and the staging clone is removed."""
    repo, _ = make_tagged_repo(tmp_path, TAG)
    repoint_tag(repo, OLD_TAG, TAG)

    result = _run(
        tmp_path,
        UNUSED_BASE,
        mode="signature",
        extra_env={"APOTHEM_ALLOW_UNVERIFIED": "1"} if allow else None,
    )

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert REPOINT_MARKER in plain, plain
    assert not (tmp_path / "apothem-home").exists(), plain
    assert _leftovers(tmp_path) == []


def test_the_clone_path_checks_out_the_tag_after_the_gate(tmp_path: Path) -> None:
    _, commit = make_tagged_repo(tmp_path, TAG)

    result = _run(tmp_path, UNUSED_BASE, mode="signature")

    plain = _plain(result.stdout + result.stderr)
    home = tmp_path / "apothem-home"
    assert TAG_OK_MARKER in plain, plain
    assert _head(home) == commit, plain
    assert (home / "src" / "apothem" / "__init__.py").is_file(), plain
    assert git(["status", "--porcelain"], home) == "", plain
    assert _leftovers(tmp_path) == []


def test_a_non_release_ref_with_allow_unverified_is_cloned(tmp_path: Path) -> None:
    """APOTHEM_REF=main with APOTHEM_ALLOW_UNVERIFIED=1 warns and checks the
    branch out in the fresh clone, made without a checkout."""
    repo, _ = make_tagged_repo(tmp_path, TAG)
    (repo / "new-file.txt").write_text("on main\n", encoding="utf-8")
    git(["add", "-A"], repo)
    git(["commit", "--quiet", "-m", "main moves on"], repo)

    result = _run(
        tmp_path,
        UNUSED_BASE,
        mode="signature",
        extra_env={"APOTHEM_REF": "main", "APOTHEM_ALLOW_UNVERIFIED": "1"},
    )

    plain = _plain(result.stdout + result.stderr)
    home = tmp_path / "apothem-home"
    assert "Ref main is not a signed release tag - proceeding" in plain, plain
    assert _head(home) == _head(repo), plain
    assert (home / "new-file.txt").is_file(), plain
    assert git(["status", "--porcelain"], home) == "", plain
    assert _leftovers(tmp_path) == []


@pytest.mark.parametrize("git_env", [False, True], ids=["plain", "git-env-set"])
def test_an_existing_clone_is_updated_in_place_to_a_good_tag(
    tmp_path: Path, git_env: bool
) -> None:
    """The clone at APOTHEM_HOME moves to the new tag and keeps what it does
    not track. A GIT_DIR / GIT_WORK_TREE / GIT_INDEX_FILE set in the calling
    shell, naming another repository, is cleared first, so git still works
    on the clone."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    new_commit = _head(repo)
    (home / "untracked-data").mkdir()
    (home / "untracked-data" / "x.json").write_text("{}\n", encoding="utf-8")
    extra: dict[str, str] = {}
    if git_env:
        decoy = tmp_path / "decoy"
        git(["init", "--quiet", str(decoy)], tmp_path)
        extra = {
            "GIT_DIR": str(decoy / ".git"),
            "GIT_WORK_TREE": str(decoy),
            "GIT_INDEX_FILE": str(decoy / ".git" / "index"),
        }

    result = _run(tmp_path, UNUSED_BASE, mode="signature", extra_env=extra)

    plain = _plain(result.stdout + result.stderr)
    assert "Updating existing clone" in plain, plain
    assert TAG_OK_MARKER in plain, plain
    assert _head(home) == new_commit, plain
    assert (home / "new-file.txt").is_file(), plain
    assert (home / "untracked-data" / "x.json").is_file(), plain
    assert _leftovers(tmp_path) == []


@pytest.mark.parametrize(
    ("gpg_status", "extra_env", "marker"),
    [
        pytest.param("", None, BAD_SIGNATURE_MARKER, id="unsigned"),
        pytest.param(
            None,
            {"APOTHEM_ALLOW_UNVERIFIED": "1"},
            REPOINT_MARKER,
            id="re-pointed-with-allow-unverified",
        ),
    ],
)
def test_an_existing_clone_stays_put_when_the_new_tag_fails_the_gate(
    tmp_path: Path,
    gpg_status: str | None,
    extra_env: dict[str, str] | None,
    marker: str,
) -> None:
    """The clone is fetched and the new tag checked before anything is
    checked out, so a failed check leaves HEAD and the working tree as they
    were: no file of the new commit appears."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    if marker == REPOINT_MARKER:
        repoint_tag(repo, OLD_TAG, TAG)
    else:
        repoint_tag(repo, TAG, TAG)
    before = _snapshot(home / "src")

    result = _run(
        tmp_path,
        UNUSED_BASE,
        mode="signature",
        gpg_status=gpg_status,
        extra_env=extra_env,
    )

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert marker in plain, plain
    assert _head(home) == old_commit, plain
    assert not (home / "new-file.txt").exists(), plain
    assert "9.9.9" not in (home / "pyproject.toml").read_text(encoding="utf-8")
    assert _snapshot(home / "src") == before, plain


@pytest.mark.parametrize(
    ("changed", "staged", "marker"),
    [
        pytest.param("pyproject.toml", False, TRACKED_CHANGES_MARKER, id="edited"),
        pytest.param("pyproject.toml", True, TRACKED_CHANGES_MARKER, id="staged"),
        pytest.param(
            "src/apothem/__init__.py", False, TRACKED_CHANGES_MARKER, id="untouched"
        ),
        pytest.param("new-file.txt", False, LOCAL_CHANGES_MARKER, id="untracked"),
    ],
)
def test_local_changes_in_an_existing_clone_are_not_discarded(
    tmp_path: Path, changed: str, staged: bool, marker: str
) -> None:
    """A change to a tracked file, in the working tree or staged, stops the
    update before anything is checked out, even where the new tag would not
    touch the file; an untracked file where the new tag adds one stops the
    checkout, which runs without --force. Either way the change survives and
    HEAD stays put."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    edited = "my local change\n"
    target = home / changed
    target.write_text(edited, encoding="utf-8")
    if staged:
        git(["add", changed], home)

    result = _run(tmp_path, UNUSED_BASE, mode="signature")

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert TAG_OK_MARKER in plain, plain
    assert marker in plain, plain
    if marker == TRACKED_CHANGES_MARKER:
        assert _squashed(f"{home} {TRACKED_CHANGES_MARKER}") in _squashed(plain)
    assert target.read_text(encoding="utf-8") == edited
    assert _head(home) == old_commit, plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_a_ref_that_reads_as_an_option_is_not_passed_to_git_as_one(
    tmp_path: Path, script: str
) -> None:
    """--end-of-options keeps a ref such as ``--orphan=planted`` from being
    read by git checkout as an option: the checkout fails as an unknown ref,
    and the clone keeps its branch and commit."""
    repo, _ = make_tagged_repo(tmp_path, TAG)
    home = tmp_path / "apothem-home"
    git(["clone", "--quiet", str(repo), str(home)], tmp_path)
    old_head = _head(home)
    extra = {"APOTHEM_REF": "--orphan=planted", "APOTHEM_ALLOW_UNVERIFIED": "1"}

    if script == "install.ps1":
        result = _run(tmp_path, UNUSED_BASE, mode="signature", extra_env=extra)
    else:
        result = _run_updater(tmp_path, extra_env=extra)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert "Could not check out --orphan=planted" in plain, plain
    assert _head(home) == old_head, plain
    assert git(["symbolic-ref", "--short", "HEAD"], home).strip() == "main", plain
    assert "planted" not in git(["branch", "--list"], home), plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize(
    "ref_kind", ["commit", "remote-only-branch", "stale-local-branch"]
)
def test_a_non_release_ref_with_allow_unverified_updates_a_clone(
    tmp_path: Path, script: str, ref_kind: str
) -> None:
    """With APOTHEM_ALLOW_UNVERIFIED=1, a ref that is not a release tag (a
    commit, a branch the clone has not seen, or a branch whose local copy is
    behind origin's) is fetched and checked out in the existing clone after a
    warning. A branch follows origin, not the stale local branch."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    tip = _head(repo)
    if ref_kind == "commit":
        ref = tip
    elif ref_kind == "remote-only-branch":
        git(["branch", "feature"], repo)
        ref = "feature"
    else:
        assert git(["rev-parse", "refs/heads/main"], home).strip() == old_commit
        ref = "main"
    extra = {"APOTHEM_REF": ref, "APOTHEM_ALLOW_UNVERIFIED": "1"}

    if script == "install.ps1":
        result = _run(tmp_path, UNUSED_BASE, mode="signature", extra_env=extra)
    else:
        result = _run_updater(tmp_path, extra_env=extra)

    plain = _plain(result.stdout + result.stderr)
    assert (
        f"Ref {ref} is not a signed release tag - proceeding because "
        "APOTHEM_ALLOW_UNVERIFIED=1"
    ) in plain, plain
    assert _head(home) == tip, plain
    assert (home / "new-file.txt").is_file(), plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_a_clone_reached_through_a_link_is_updated_in_place(
    tmp_path: Path, script: str
) -> None:
    """An in-place update renames nothing, so a junction (a symbolic link off
    Windows) to a clone is fine: the clone behind it moves to the new tag and
    the link stays."""
    repo, real, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    new_commit = _head(repo)
    home = tmp_path / "linked-home"
    _make_junction(home, real)
    extra = {"APOTHEM_HOME": str(home)}

    if script == "install.ps1":
        result = _run(tmp_path, UNUSED_BASE, mode="signature", extra_env=extra)
    else:
        result = _run_updater(tmp_path, extra_env=extra)

    plain = _plain(result.stdout + result.stderr)
    assert TAG_OK_MARKER in plain, plain
    assert LINK_MARKER not in plain, plain
    assert os.path.lexists(home), plain
    assert _head(real) == new_commit, plain
    assert (real / "new-file.txt").is_file(), plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_the_clones_own_hooks_do_not_run(tmp_path: Path, script: str) -> None:
    """The in-place git calls point core.hooksPath at an empty folder, so a
    post-checkout (or any other) hook in the clone does not run: here one
    that would leave a marker."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    new_commit = _head(repo)
    marker = tmp_path / "hook-ran"
    for name in ("post-checkout", "reference-transaction"):
        hook = home / ".git" / "hooks" / name
        hook.write_text(
            f"#!/bin/sh\ntouch '{marker.as_posix()}'\n",
            encoding="utf-8",
            newline="\n",
        )
        hook.chmod(EXECUTABLE_MODE)

    if script == "install.ps1":
        result = _run(tmp_path, UNUSED_BASE, mode="signature")
    else:
        result = _run_updater(tmp_path)

    plain = _plain(result.stdout + result.stderr)
    assert TAG_OK_MARKER in plain, plain
    assert not marker.exists(), plain
    assert _head(home) == new_commit, plain
    assert not [
        p for p in (tmp_path / "temp").iterdir() if p.name.startswith("apothem-")
    ], plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_a_checkout_that_does_not_match_the_ref_aborts(
    tmp_path: Path, script: str
) -> None:
    """After the checkout the tracked files must match the ref. A smudge
    filter that, while git writes one file, changes another tracked file
    leaves the work tree off the ref, and the scripts stop before anything
    materializes."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    (home / ".git" / "info").mkdir(exist_ok=True)
    (home / ".git" / "info" / "attributes").write_text(
        "pyproject.toml filter=tamper\n", encoding="utf-8", newline="\n"
    )
    git(["config", "filter.tamper.clean", "cat"], home)
    git(
        [
            "config",
            "filter.tamper.smudge",
            "cat; echo tampered >> src/apothem/__init__.py",
        ],
        home,
    )

    if script == "install.ps1":
        result = _run(tmp_path, UNUSED_BASE, mode="signature")
    else:
        result = _run_updater(tmp_path)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    message = (
        f"The checkout in {home} does not match {TAG} after the update. "
        "Aborting before re-materialization."
    )
    assert _squashed(message) in _squashed(plain), plain
    assert "Source ready at" not in plain, plain
    assert "Source updated at" not in plain, plain


def test_a_dry_run_on_the_clone_path_leaves_apothem_home_alone(
    tmp_path: Path,
) -> None:
    make_tagged_repo(tmp_path, TAG)
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    before = _snapshot(home)

    result = _run(tmp_path, UNUSED_BASE, mode="signature", dry_run=True)

    plain = _plain(result.stdout + result.stderr)
    assert TAG_OK_MARKER in plain, plain
    assert DRY_RUN_MARKER in plain, plain
    assert _snapshot(home) == before, plain
    assert not (home / ".git").exists(), plain
    assert _leftovers(tmp_path) == []


def test_the_clone_path_refuses_an_archive_install_without_yes(
    tmp_path: Path,
) -> None:
    make_tagged_repo(tmp_path, TAG)
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    before = _snapshot(home)

    result = _run(tmp_path, UNUSED_BASE, mode="signature", yes=False)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert "is a release-archive install, not a git clone" in plain, plain
    assert "Cloning" not in plain, plain
    assert _snapshot(home) == before, plain
    assert _leftovers(tmp_path) == []


def test_yes_switches_an_archive_install_to_a_clone_and_keeps_engine_data(
    tmp_path: Path,
) -> None:
    make_tagged_repo(tmp_path, TAG)
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)

    result = _run(tmp_path, UNUSED_BASE, mode="signature", yes=True)

    plain = _plain(result.stdout + result.stderr)
    assert "Switching the release-archive install" in plain, plain
    assert (home / ".git").is_dir(), plain
    assert not (home / "src" / "apothem" / "removed_module.py").exists(), plain
    _assert_engine_data_kept(home)
    assert _leftovers(tmp_path) == []


# The updater ----------------------------------------------------------------


def test_the_updater_checks_out_the_tag_not_a_branch_of_the_same_name(
    tmp_path: Path,
) -> None:
    """update.ps1 checks out refs/tags/TAG and checks HEAD is the tag's
    commit, so a local branch named like the tag cannot stand in for it."""
    repo, tagged = make_tagged_repo(tmp_path, TAG)
    git(["checkout", "--quiet", "-b", TAG], repo)
    (repo / "planted.txt").write_text("not in the release\n", encoding="utf-8")
    git(["add", "planted.txt"], repo)
    git(["commit", "--quiet", "-m", "branch named like the tag"], repo)
    git(["checkout", "--quiet", "main"], repo)
    home = tmp_path / "apothem-home"
    git(["clone", "--quiet", str(repo), str(home)], tmp_path)
    git(["checkout", "--quiet", "-b", TAG, f"origin/{TAG}"], home)
    assert (home / "planted.txt").is_file()

    result = _run_updater(tmp_path)

    plain = _plain(result.stdout + result.stderr)
    assert TAG_OK_MARKER in plain, plain
    assert "Source updated at" in plain, plain
    assert _head(home) == tagged, plain
    assert not (home / "planted.txt").exists(), plain


@pytest.mark.parametrize(
    ("case", "marker"),
    [
        pytest.param("re-pointed", REPOINT_MARKER, id="re-pointed"),
        pytest.param("unsigned", BAD_SIGNATURE_MARKER, id="unsigned"),
        pytest.param("local-changes", TRACKED_CHANGES_MARKER, id="local-changes"),
        pytest.param("staged-changes", TRACKED_CHANGES_MARKER, id="staged-changes"),
        pytest.param("untracked", LOCAL_CHANGES_MARKER, id="untracked"),
        pytest.param("no-commit", REPOINT_MARKER, id="tag-names-no-commit"),
    ],
)
def test_the_updater_leaves_the_clone_put_when_it_cannot_update(
    tmp_path: Path, case: str, marker: str
) -> None:
    """update.ps1 fetches and checks the tag before it checks anything out:
    a re-pointed tag (even with APOTHEM_ALLOW_UNVERIFIED=1) or a failed
    signature, or a signed tag object that names no commit, leaves HEAD where
    it was; a change to a tracked file (edited or staged) stops the update
    before the checkout, and an untracked file where the new tag adds one
    stops the checkout, instead of either being overwritten."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    if case == "no-commit":
        _tag_a_tree(repo)
    else:
        repoint_tag(repo, OLD_TAG if case == "re-pointed" else TAG, TAG)
    edited = '[project]\nname = "my local edit"\n'
    if case in {"local-changes", "staged-changes"}:
        (home / "pyproject.toml").write_text(edited, encoding="utf-8")
    if case == "staged-changes":
        git(["add", "pyproject.toml"], home)
    if case == "untracked":
        (home / "new-file.txt").write_text(edited, encoding="utf-8")

    result = _run_updater(
        tmp_path,
        gpg_status="" if case == "unsigned" else None,
        extra_env={"APOTHEM_ALLOW_UNVERIFIED": "1"} if case == "re-pointed" else None,
    )

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert marker in plain, plain
    assert _head(home) == old_commit, plain
    if case != "untracked":
        assert not (home / "new-file.txt").exists(), plain
    if case in {"local-changes", "staged-changes"}:
        assert (home / "pyproject.toml").read_text(encoding="utf-8") == edited
        assert _squashed(f"{home} {TRACKED_CHANGES_MARKER}") in _squashed(plain)
    if case == "untracked":
        assert (home / "new-file.txt").read_text(encoding="utf-8") == edited


# Round-three checks ---------------------------------------------------------


def _tag_a_tree(repo: Path) -> None:
    """Point refs/tags/TAG at a signed-looking tag object that names itself
    TAG but points at the commit's tree, not at a commit."""
    tree = git(["rev-parse", "HEAD^{tree}"], repo).strip()
    tag_file = repo.parent / f"{TAG}-tree.tag"
    tag_file.write_text(
        f"object {tree}\n"
        "type tree\n"
        f"tag {TAG}\n"
        "tagger Fixture <fixture@example.invalid> 1700000000 +0000\n"
        "\n"
        "signed release\n"
        "-----BEGIN PGP SIGNATURE-----\n"
        "\n"
        "c3R1Yg==\n"
        "-----END PGP SIGNATURE-----\n",
        encoding="utf-8",
        newline="\n",
    )
    tag_sha = git(["hash-object", "-t", "tag", "-w", str(tag_file)], repo).strip()
    git(["update-ref", f"refs/tags/{TAG}", tag_sha], repo)


def _worktree_snapshot(root: Path) -> dict[str, str]:
    """Every file under ROOT outside its .git folder (whose index git may
    refresh while it reads the status), by relative path, with its text."""
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def _commit_in(repo: Path, message: str) -> None:
    git(
        [
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-a",
            "-m",
            message,
        ],
        repo,
    )


@pytest.mark.parametrize("mode", ["release", "signature"])
def test_a_signed_tag_object_that_names_no_commit_is_refused(
    tmp_path: Path, release: tuple[Path, str], mode: str
) -> None:
    """A maintainer-signed tag object named TAG whose type is not commit (here
    a tree) is refused before anything is placed, on the release path and the
    clone path alike."""
    folder, base_url = release
    _publish(folder)
    _tag_a_tree(tmp_path / "fixture-repo")
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base_url, mode=mode, cosign_dir=cosign_dir)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert REPOINT_MARKER in plain, plain
    assert "Downloading" not in plain, plain
    assert not (tmp_path / "apothem-home").exists(), plain
    assert _leftovers(tmp_path) == []


def _separate_git_dir_clone(tmp_path: Path) -> tuple[Path, Path, str]:
    """Clone the fixture at OLD_TAG into APOTHEM_HOME with its git directory
    elsewhere, so APOTHEM_HOME holds a .git file, then add the next commit to
    the fixture and tag it TAG. Return (fixture, clone, the new commit)."""
    repo, old_commit = make_tagged_repo(tmp_path, OLD_TAG)
    home = tmp_path / "apothem-home"
    git(
        [
            "clone",
            "--quiet",
            "--separate-git-dir",
            str(tmp_path / "separate.git"),
            str(repo),
            str(home),
        ],
        tmp_path,
    )
    git(["checkout", "--quiet", f"refs/tags/{OLD_TAG}"], home)
    assert (home / ".git").is_file()
    (repo / "new-file.txt").write_text("from the new release\n", encoding="utf-8")
    git(["add", "-A"], repo)
    git(["commit", "--quiet", "-m", "next release"], repo)
    repoint_tag(repo, TAG, TAG)
    assert _head(home) == old_commit
    return repo, home, _head(repo)


def test_a_git_file_at_apothem_home_is_updated_as_a_clone(tmp_path: Path) -> None:
    """A .git file (a worktree, or a clone made with --separate-git-dir) makes
    APOTHEM_HOME a clone: auto mode updates it in place instead of replacing
    it with the archive."""
    _, home, new_commit = _separate_git_dir_clone(tmp_path)

    result = _run(
        tmp_path, UNUSED_BASE, mode=None, cosign_dir=_stub_cosign(tmp_path), yes=False
    )

    plain = _plain(result.stdout + result.stderr)
    assert "is a git clone - updating it" in plain, plain
    assert "Updating existing clone" in plain, plain
    assert (home / ".git").is_file(), plain
    assert _head(home) == new_commit, plain
    assert (home / "new-file.txt").is_file(), plain


def test_a_git_file_at_apothem_home_is_not_replaced_without_yes(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    repo, home, _ = _separate_git_dir_clone(tmp_path)
    name = f"apothem-{TAG}-windows.zip"
    data = _zip_bytes()
    (folder / name).write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (folder / "SHA256SUMS").write_bytes(f"{digest}  {name}\n".encode("ascii"))
    (folder / "SHA256SUMS.cosign.bundle").write_text(BUNDLE_TEXT, encoding="utf-8")
    assert repo == tmp_path / "fixture-repo"

    result = _run(tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path), yes=False)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert "is a git clone; refusing to replace it" in plain, plain
    assert (home / ".git").is_file(), plain


@pytest.mark.parametrize("dry_run", [False, True], ids=["real", "dry-run"])
@pytest.mark.parametrize(
    "work", ["tracked-change", "staged-change", "stash", "unpushed-commit", "untracked"]
)
def test_yes_does_not_replace_a_clone_that_holds_local_work(
    tmp_path: Path, release: tuple[Path, str], work: str, dry_run: bool
) -> None:
    """-Yes replaces a clean clone with the archive, but not one whose local
    work the swap would lose: a tracked change (edited or staged), a stash, a
    commit no remote has, or an untracked file inside its source tree. The
    check runs in a dry run too, and nothing is downloaded."""
    folder, base_url = release
    _publish(folder)
    repo = tmp_path / "fixture-repo"
    home = tmp_path / "apothem-home"
    git(["clone", "--quiet", str(repo), str(home)], tmp_path)
    _seed_engine_data(home)
    pyproject = home / "pyproject.toml"
    if work in {"tracked-change", "staged-change", "stash", "unpushed-commit"}:
        pyproject.write_text("[project]\nname = 'mine'\n", encoding="utf-8")
    if work == "staged-change":
        git(["add", "pyproject.toml"], home)
    if work == "stash":
        git(
            [
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "stash",
                "--quiet",
            ],
            home,
        )
    if work == "unpushed-commit":
        _commit_in(home, "local work")
    if work == "untracked":
        (home / "src" / "apothem" / "mine.py").write_text("x = 1\n", encoding="utf-8")
    before = _worktree_snapshot(home)

    result = _run(
        tmp_path,
        base_url,
        cosign_dir=_stub_cosign(tmp_path),
        yes=True,
        dry_run=dry_run,
    )

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert _squashed(f"{home} {LOCAL_WORK_MARKER}") in _squashed(plain), plain
    assert "Downloading" not in plain, plain
    assert (home / ".git").is_dir(), plain
    assert _worktree_snapshot(home) == before, plain
    assert _leftovers(tmp_path) == []


@pytest.mark.parametrize("mode", ["release", "signature"])
def test_a_home_with_only_engine_data_is_updated_without_yes(
    tmp_path: Path, release: tuple[Path, str], mode: str
) -> None:
    """A folder that holds only the engine's data folders (what is left once
    the source is gone) is installed into without -Yes, like an empty one,
    and its data is kept."""
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    _seed_engine_data(home)
    (home / "plans").mkdir()
    (home / "plans" / "p.md").write_text("a plan\n", encoding="utf-8")

    result = _run(
        tmp_path, base_url, mode=mode, cosign_dir=_stub_cosign(tmp_path), yes=False
    )

    plain = _plain(result.stdout + result.stderr)
    assert f"Source ready at {home}" in plain, plain
    assert "holds no Apothem install" not in plain, plain
    assert (home / "src" / "apothem" / "__init__.py").is_file(), plain
    _assert_engine_data_kept(home)
    assert (home / "plans" / "p.md").is_file(), plain
    assert not list(tmp_path.glob("apothem-home.before-apothem-*")), plain
    assert _leftovers(tmp_path) == []


def test_a_dry_run_says_other_content_would_be_moved_aside(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    home.mkdir()
    (home / "keep.txt").write_text("not apothem's to delete\n", encoding="utf-8")
    before = _snapshot(home)

    result = _run(
        tmp_path, base_url, cosign_dir=_stub_cosign(tmp_path), yes=True, dry_run=True
    )

    plain = _plain(result.stdout + result.stderr)
    assert "holds no Apothem install; it would be moved, unchanged" in plain, plain
    assert "will be moved" not in plain, plain
    assert _snapshot(home) == before, plain
    assert not list(tmp_path.glob("apothem-home.before-apothem-*")), plain
    assert _leftovers(tmp_path) == []


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_a_repository_that_reads_as_an_option_is_refused(
    tmp_path: Path, script: str
) -> None:
    extra = {"APOTHEM_REPO": "--upload-pack=planted"}

    if script == "install.ps1":
        result = _run(tmp_path, UNUSED_BASE, mode="signature", extra_env=extra)
    else:
        result = _run_updater(tmp_path, extra_env=extra)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert (
        "APOTHEM_REPO must be a repository URL or path, not an option: "
        "--upload-pack=planted"
    ) in plain, plain
    assert "Cloning" not in plain, plain


# Fault injected into the copy of install.ps1 under test: Move-Entry fails
# when it moves APOTHEM_HOME itself, or moves anything into APOTHEM_HOME.
# The engine's data still moves out into the new tree, the earlier tree then
# cannot move aside, and the rollback cannot move the data back.
_MOVE_ENTRY_HEAD = (
    "    $ToFull = $ExecutionContext.SessionState.Path"
    ".GetUnresolvedProviderPathFromPSPath($To)\r\n"
)
_MOVE_ENTRY_FAULT = (
    "    $HomeFull = $ExecutionContext.SessionState.Path"
    ".GetUnresolvedProviderPathFromPSPath($ApothemHome)\r\n"
    "    if ($FromFull -eq $HomeFull -or "
    "[System.IO.Path]::GetDirectoryName($ToFull) -eq $HomeFull) "
    "{ throw 'injected fault' }\r\n"
)


def _fail_moves_at_home(script: str) -> str:
    """Make the script's Move-Entry fail at APOTHEM_HOME (see above)."""
    assert script.count(_MOVE_ENTRY_HEAD) == 1, "Move-Entry changed shape"
    return script.replace(_MOVE_ENTRY_HEAD, _MOVE_ENTRY_HEAD + _MOVE_ENTRY_FAULT)


def test_a_failed_rollback_keeps_the_staging_folder_and_names_it(
    tmp_path: Path, release: tuple[Path, str]
) -> None:
    """When putting the earlier install back fails too, the run names where
    the earlier tree and the moved data are, and keeps the staging folder,
    which holds the only copy of the data it carried.

    The engine's data moves into the new tree first; the injected fault then
    stops the earlier tree moving aside and stops the data moving back."""
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)

    result = _run(
        tmp_path,
        base_url,
        cosign_dir=_stub_cosign(tmp_path),
        yes=False,
        patch=_fail_moves_at_home,
    )

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert "Could not move the existing" in plain, plain
    assert _squashed(f"{ROLLBACK_FAILED_MARKER} {home}") in _squashed(plain), plain
    staged = sorted(tmp_path.glob(".apothem-extract.*"))
    assert len(staged) == 1, plain
    new_tree = staged[0] / ARCHIVE_ROOT
    moved_data = _squashed(f"(with any moved data under {new_tree})")
    assert moved_data in _squashed(plain), plain
    assert (new_tree / "backups" / "claude-code" / "set.json").is_file(), plain
    assert (home / "src" / "apothem" / "removed_module.py").is_file(), plain
    assert (home / "state" / "ledger.json").is_file() or (
        new_tree / "state" / "ledger.json"
    ).is_file(), plain


def _plain_repo(path: Path) -> None:
    """Make PATH a git repository of something other than Apothem."""
    path.mkdir(parents=True)
    (path / "notes.txt").write_text("not apothem\n", encoding="utf-8")
    git(["init", "--quiet", "--initial-branch", "main"], path)
    git(["add", "-A"], path)
    _commit_in(path, "unrelated")


@pytest.mark.parametrize("mode", ["release", "signature", None])
def test_a_clone_of_something_else_is_refused_without_yes(
    tmp_path: Path, release: tuple[Path, str], mode: str | None
) -> None:
    """A git clone that holds no Apothem source is an unrelated folder: no
    clone path takes it, and without -Yes it is refused like any other."""
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    _plain_repo(home)
    before = _worktree_snapshot(home)

    result = _run(
        tmp_path, base_url, mode=mode, cosign_dir=_stub_cosign(tmp_path), yes=False
    )

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert NO_HOME_MARKER in plain, plain
    assert "is a git clone" not in plain, plain
    assert "Updating existing clone" not in plain, plain
    assert _worktree_snapshot(home) == before, plain


@pytest.mark.parametrize("mode", ["release", "signature"])
def test_yes_moves_a_clone_of_something_else_aside(
    tmp_path: Path, release: tuple[Path, str], mode: str
) -> None:
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    _plain_repo(home)
    before = _worktree_snapshot(home)

    result = _run(
        tmp_path, base_url, mode=mode, cosign_dir=_stub_cosign(tmp_path), yes=True
    )

    plain = _plain(result.stdout + result.stderr)
    asides = sorted(tmp_path.glob("apothem-home.before-apothem-*"))
    assert len(asides) == 1, plain
    assert (asides[0] / ".git").is_dir(), plain
    assert _worktree_snapshot(asides[0]) == before, plain
    assert (home / "src" / "apothem" / "__init__.py").is_file(), plain
    assert not (home / "notes.txt").exists(), plain


def test_the_updater_does_not_update_a_clone_of_something_else(
    tmp_path: Path,
) -> None:
    make_tagged_repo(tmp_path, TAG)
    home = tmp_path / "apothem-home"
    _plain_repo(home)

    result = _run_updater(tmp_path)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert "No source found at" in plain, plain
    assert "Updating clone" not in plain, plain


def _prepare_unclean_clone(tmp_path: Path, case: str) -> tuple[Path, str, str]:
    """A clone at OLD_TAG that the clean-clone check refuses for CASE; return
    (clone, its HEAD, the message part expected)."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    if case in {"assume-unchanged", "skip-worktree"}:
        (home / "pyproject.toml").write_text("[project]\nname = 'evil'\n", "utf-8")
        git(["update-index", f"--{case}", "pyproject.toml"], home)
        assert git(["status", "--porcelain"], home) == ""
        return home, old_commit, TRACKED_CHANGES_MARKER
    if case == "core.worktree":
        decoy = tmp_path / "decoy"
        shutil.copytree(home, decoy, ignore=shutil.ignore_patterns(".git"))
        git(["config", "core.worktree", decoy.as_posix()], home)
        return home, old_commit, WORK_TREE_MARKER
    key, value = {
        "gpg.program": ("gpg.program", "C:/elsewhere/gpg"),
        "gpg.openpgp.program": ("gpg.openpgp.program", "C:/elsewhere/gpg"),
        "core.fsmonitor": ("core.fsmonitor", "false"),
        "core.hooksPath": ("core.hooksPath", "C:/elsewhere/hooks"),
        "include.path": ("include.path", "C:/elsewhere/config"),
        "includeIf": ("includeIf.gitdir:C:/.path", "C:/elsewhere/config"),
    }[case]
    git(["config", key, value], home)
    printed = key.lower() if case != "includeIf" else "includeif.gitdir:C:/.path"
    return home, old_commit, f"'s own git config sets {printed}{TRUSTED_CONFIG_MARKER}"


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize(
    "case",
    [
        "assume-unchanged",
        "skip-worktree",
        "core.worktree",
        "gpg.program",
        "gpg.openpgp.program",
        "core.fsmonitor",
        "core.hooksPath",
        "include.path",
        "includeIf",
    ],
)
def test_a_clone_the_update_cannot_check_is_refused_before_the_fetch(
    tmp_path: Path, script: str, case: str
) -> None:
    """A tracked file git hides a change to (assume-unchanged, skip-worktree),
    a work tree other than APOTHEM_HOME, or a local git setting the update's
    git calls would run or read stops the update before anything is fetched,
    and HEAD stays put."""
    home, old_commit, expected = _prepare_unclean_clone(tmp_path, case)

    if script == "install.ps1":
        result = _run(tmp_path, UNUSED_BASE, mode="signature")
    else:
        result = _run_updater(tmp_path)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert _squashed(expected) in _squashed(plain), plain
    assert _squashed(str(home)) in _squashed(plain), plain
    assert "Verifying source signature" not in plain, plain
    assert git(["rev-parse", "HEAD"], home).strip() == old_commit, plain
    assert git(["tag", "--list", TAG], home).strip() == "", plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize("variable", ["git-dir", "config-parameters"])
def test_git_variables_in_the_calling_shell_are_cleared(
    tmp_path: Path, script: str, variable: str
) -> None:
    """GIT_DIR / GIT_WORK_TREE / GIT_INDEX_FILE naming another repository,
    or GIT_CONFIG_PARAMETERS naming a gpg that is not there, would redirect
    or break the update; both scripts clear them first."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    new_commit = _head(repo)
    if variable == "git-dir":
        decoy = tmp_path / "decoy"
        git(["init", "--quiet", str(decoy)], tmp_path)
        extra = {
            "GIT_DIR": str(decoy / ".git"),
            "GIT_WORK_TREE": str(decoy),
            "GIT_INDEX_FILE": str(decoy / ".git" / "index"),
        }
    else:
        extra = {"GIT_CONFIG_PARAMETERS": "'gpg.program=C:/nowhere/gpg'"}

    if script == "install.ps1":
        result = _run(tmp_path, UNUSED_BASE, mode="signature", extra_env=extra)
    else:
        result = _run_updater(tmp_path, extra_env=extra)

    plain = _plain(result.stdout + result.stderr)
    assert TAG_OK_MARKER in plain, plain
    assert _head(home) == new_commit, plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_a_branch_named_like_the_tag_ref_is_not_checked_out(
    tmp_path: Path, script: str
) -> None:
    """A local branch literally named refs/tags/TAG (refs/heads/refs/tags/TAG)
    does not stand in for the tag: the scripts check out the tag's commit."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    new_commit = _head(repo)
    git(["checkout", "--quiet", "-b", "planted"], home)
    (home / "planted.txt").write_text("not in the release\n", encoding="utf-8")
    git(["add", "planted.txt"], home)
    _commit_in(home, "planted")
    git(["branch", "-m", "planted", f"refs/tags/{TAG}"], home)
    git(["checkout", "--quiet", "--detach", old_commit], home)
    assert not (home / "planted.txt").exists()

    if script == "install.ps1":
        result = _run(tmp_path, UNUSED_BASE, mode="signature")
    else:
        result = _run_updater(tmp_path)

    plain = _plain(result.stdout + result.stderr)
    assert TAG_OK_MARKER in plain, plain
    assert _head(home) == new_commit, plain
    assert not (home / "planted.txt").exists(), plain


def test_the_updater_updates_a_clone_with_a_git_file(tmp_path: Path) -> None:
    _, home, new_commit = _separate_git_dir_clone(tmp_path)

    result = _run_updater(tmp_path)

    plain = _plain(result.stdout + result.stderr)
    assert "Source updated at" in plain, plain
    assert (home / ".git").is_file(), plain
    assert _head(home) == new_commit, plain


@pytest.mark.parametrize(
    ("seed", "mode", "expected"),
    [
        pytest.param("clone", "release", "Would replace the git clone at", id="clone"),
        pytest.param(
            "archive",
            "signature",
            "Would switch the release-archive install at",
            id="switch",
        ),
        pytest.param(
            "archive", "release", "Would update the earlier install at", id="update"
        ),
    ],
)
def test_a_dry_run_says_what_would_be_done(
    tmp_path: Path, release: tuple[Path, str], seed: str, mode: str, expected: str
) -> None:
    folder, base_url = release
    _publish(folder)
    home = tmp_path / "apothem-home"
    if seed == "clone":
        git(["clone", "--quiet", str(tmp_path / "fixture-repo"), str(home)], tmp_path)
    else:
        _seed_earlier_install(home)
    before = _worktree_snapshot(home)

    result = _run(
        tmp_path,
        base_url,
        mode=mode,
        cosign_dir=_stub_cosign(tmp_path),
        yes=True,
        dry_run=True,
    )

    plain = _plain(result.stdout + result.stderr)
    assert expected in plain, plain
    for present in (
        "will be",
        "Replacing the git clone",
        "Switching the",
        "Updating the",
    ):
        assert present not in plain, plain
    assert _worktree_snapshot(home) == before, plain
    assert not list(tmp_path.glob("apothem-home.before-apothem-*")), plain


# REUSE-IgnoreEnd
