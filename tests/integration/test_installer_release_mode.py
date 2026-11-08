# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The POSIX installer's cosign release mode (``APOTHEM_VERIFY=release``/``auto``).

The release mode requires two checks before it trusts the release's
``SHA256SUMS``: the release tag carries the maintainer key's signature and
its signed tag object names itself as that release, and cosign confirms that
the release workflow at that tag signed ``SHA256SUMS`` in a run on the tag's
commit. cosign checks the commit itself: the installer passes it with
``--certificate-github-workflow-sha`` and reads nothing from the bundle. The
archive's SHA-256 is checked last. ``auto``, the default, takes this path
whenever cosign is on PATH.

A stub ``cosign`` records its arguments and succeeds or fails on request, and
a stub gpg replays a canned GnuPG result for the fixture repository's tag
(see ``tests/_shared/release_fixture.py``). The bundle is placeholder text,
since only cosign reads it. The fake release is served from a ``file://``
base, as in ``test_installer_checksum_mode.py``.

The swap tests cover how the archive replaces what is at ``APOTHEM_HOME``:
an earlier Apothem install keeps the entries that are not part of its source
(the engine's ``backups/`` and ``state/`` among them), a folder that holds
no Apothem install is moved aside unchanged with ``--yes``, a symbolic link
is refused, and a failure or an interrupt during the swap puts the earlier
install back. A stub ``mv`` placed first on PATH fails, or interrupts the
installer, on a chosen rename.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
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
SOURCE_MANIFEST = ".apothem-source-entries"
COSIGN_OK_MARKER = "cosign: SHA256SUMS is signed by the v9.9.9 release workflow"
COSIGN_COMMIT_MARKER = "in a run on the tag's commit"
COSIGN_FAIL_MARKER = "cosign could not confirm that the v9.9.9 release workflow"
CHECKSUM_CAVEAT = "Checksum mode does not verify the release"
MISMATCH_MARKER = "does not match the release's SHA256SUMS"
TAG_OK_MARKER = "carries a valid signature from the maintainer key"
REPOINTED_MARKER = (
    "the signed tag object is not the v9.9.9 release tag (it names another "
    "tag, or no commit), so it was re-pointed (possible tampering)"
)
LINK_MARKER = "is a symbolic link. Point APOTHEM_HOME at the folder it links to"
NOT_APOTHEM_MARKER = "is not empty and holds no Apothem install; refusing to replace it"
CLONE_REFUSED_MARKER = "is a git clone; refusing to replace it"
BACK_IN_PLACE = "is back in place and unchanged"

# Permission bits for the stub programs (owner rwx, others rx).
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

# What every fixture archive ships, under ARCHIVE_ROOT.
BASE_MEMBERS: dict[str, bytes] = {
    "src/apothem/__init__.py": b"# SPDX-License-Identifier: MIT\n",
    "pyproject.toml": b'[project]\nname = "fixture"\nversion = "9.9.9"\n',
}


def _archive_bytes(members: dict[str, bytes]) -> bytes:
    """An apothem-shaped runtime archive laid out like a real release."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, body in members.items():
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
    extra: dict[str, bytes] | None = None,
) -> Path:
    """Write a fake release for TAG under ``<base>/<tag>/`` and return the
    base, making the fixture repository tagged TAG on the first call.

    The archive ships BASE_MEMBERS plus EXTRA. A later call rewrites the
    release in place, as a re-published release would.
    """
    if not (tmp_path / "fixture-repo").exists():
        make_tagged_repo(tmp_path, TAG)
    base = tmp_path / "releases"
    folder = base / TAG
    folder.mkdir(parents=True, exist_ok=True)
    for stale in folder.iterdir():
        stale.unlink()
    name = f"apothem-{TAG}-{_platform()}.tar.gz"
    data = _archive_bytes({**BASE_MEMBERS, **(extra or {})})
    (folder / name).write_bytes(data + (b"tampered" if tamper else b""))
    digest = hashlib.sha256(data).hexdigest()
    (folder / "SHA256SUMS").write_text(f"{digest}  {name}\n", encoding="utf-8")
    if bundle:
        # Only cosign reads the bundle, and the stub cosign ignores it.
        (folder / bundle).write_text("{}\n", encoding="utf-8")
    return base


def _tag_commit(tmp_path: Path) -> str:
    """The commit the fixture repository's TAG points at."""
    return git(
        ["rev-parse", f"refs/tags/{TAG}^{{commit}}"], tmp_path / "fixture-repo"
    ).strip()


def _stub_cosign(tmp_path: Path, *, succeed: bool = True) -> Path:
    """Write a stub ``cosign`` and return the directory that holds it.

    The stub writes one argument per line to ``cosign-args.txt`` beside it
    and exits 0, or prints a cosign-style error and exits 1.
    """
    stub_dir = tmp_path / "stub-cosign"
    stub_dir.mkdir(exist_ok=True)
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


def _cosign_args(cosign_dir: Path) -> list[str] | None:
    """The arguments the stub cosign was given, or None when it never ran."""
    args_file = cosign_dir / "cosign-args.txt"
    if not args_file.exists():
        return None
    return args_file.read_text(encoding="utf-8").splitlines()


def _stub_mv(tmp_path: Path, rules: list[tuple[str, str, str]]) -> Path:
    """Write a stub ``mv`` and return the directory that holds it.

    Each rule is (source pattern, destination pattern, action), the patterns
    being shell globs matched against the stub's two arguments. ``fail``
    prints an error and exits 1 without moving; ``interrupt`` makes the move
    and then sends SIGTERM to the installer that ran it. Any other call goes
    to the real ``mv``. A signal name (``QUIT``, ``INT``, ``HUP``, ``PIPE``)
    works like ``interrupt`` with that signal. Every call is logged to
    ``mv-calls.txt``.
    """
    real = shutil.which("mv")
    assert real is not None
    stub_dir = tmp_path / "stub-mv"
    stub_dir.mkdir()
    (stub_dir / "rules.txt").write_text(
        "".join(f"{src}|{dst}|{action}\n" for src, dst, action in rules),
        encoding="utf-8",
        newline="\n",
    )
    stub = stub_dir / "mv"
    stub.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> '{stub_dir / 'mv-calls.txt'}'\n"
        "while IFS='|' read -r src dst action; do\n"
        '    case "$1" in $src) ;; *) continue ;; esac\n'
        '    case "$2" in $dst) ;; *) continue ;; esac\n'
        '    if [ "$action" = fail ]; then\n'
        '        echo "mv: simulated failure moving $1" >&2\n'
        "        exit 1\n"
        "    fi\n"
        f"    '{real}' \"$@\" || exit 1\n"
        '    [ "$action" = interrupt ] && action=TERM\n'
        '    kill -"$action" "$PPID"\n'
        "    exit 0\n"
        f"done < '{stub_dir / 'rules.txt'}'\n"
        f"exec '{real}' \"$@\"\n",
        encoding="utf-8",
        newline="\n",
    )
    stub.chmod(EXECUTABLE_MODE)
    return stub_dir


def _seed_earlier_install(home: Path) -> None:
    """Lay out what an earlier archive install leaves at APOTHEM_HOME: a
    source tree, plus the engine's rollback backups and install ledgers."""
    (home / "src" / "apothem").mkdir(parents=True)
    (home / "src" / "apothem" / "removed_module.py").write_text(
        "old\n", encoding="utf-8"
    )
    (home / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    _seed_engine_data(home)


def _seed_engine_data(home: Path) -> None:
    (home / "backups" / "claude-code").mkdir(parents=True)
    (home / "backups" / "claude-code" / "set.json").write_text(
        '{"set": 1}\n', encoding="utf-8"
    )
    (home / "state").mkdir()
    (home / "state" / "ledger.json").write_text('{"ledger": 1}\n', encoding="utf-8")
    (home / "plans").mkdir()
    (home / "plans" / "plan.md").write_text("# plan\n", encoding="utf-8")


def _clone_into(tmp_path: Path, home: Path, *args: str) -> None:
    """Clone the fixture repository to HOME, as the clone path leaves it;
    ARGS go to git clone."""
    git(
        ["clone", "--quiet", *args, str(tmp_path / "fixture-repo"), str(home)],
        tmp_path,
    )


# maintenance.auto and gc.auto off: newer git (macOS runners) starts
# background maintenance after a commit, and its maintenance.lock comes and
# goes while a test snapshots the clone.
_COMMIT_AS = [
    "-c",
    "user.name=Fixture",
    "-c",
    "user.email=fixture@example.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "maintenance.auto=false",
    "-c",
    "gc.auto=0",
]


def _commit(repo: Path, files: dict[str, str], message: str = "change") -> None:
    """Write FILES (relative path: text) in REPO and commit them."""
    for rel, text in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    git(["add", "-A"], repo)
    git([*_COMMIT_AS, "commit", "--quiet", "-m", message], repo)


def _commit_upstream(tmp_path: Path, files: dict[str, str]) -> None:
    """Commit FILES to the fixture repository's main, after the tag."""
    _commit(tmp_path / "fixture-repo", files, "upstream change")


def _snapshot(root: Path) -> dict[str, bytes | str]:
    """Every entry under ROOT: a file's bytes, a link's target, or "dir"."""
    entries: dict[str, bytes | str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries[rel] = f"link:{path.readlink()}"
        elif path.is_dir():
            entries[rel] = "dir"
        else:
            entries[rel] = path.read_bytes()
    return entries


ENGINE_DATA = {"backups", "state", "plans"}


def _engine_data(home: Path) -> dict[str, bytes | str]:
    """The snapshot entries under backups/, state/ and plans/."""
    return {
        rel: body
        for rel, body in _snapshot(home).items()
        if rel.split("/")[0] in ENGINE_DATA
    }


def _assert_engine_data_kept(home: Path) -> None:
    assert (home / "backups" / "claude-code" / "set.json").read_text(
        encoding="utf-8"
    ) == '{"set": 1}\n'
    assert (home / "state" / "ledger.json").read_text(
        encoding="utf-8"
    ) == '{"ledger": 1}\n'
    assert (home / "plans" / "plan.md").read_text(encoding="utf-8") == "# plan\n"


def _assert_no_staging(tmp_path: Path) -> None:
    left = sorted(path.name for path in tmp_path.glob(".apothem-*"))
    assert left == [], f"staging left beside APOTHEM_HOME: {left}"


def _run(
    tmp_path: Path,
    base: Path,
    *,
    mode: str | None = "release",
    cosign_dir: Path | None = None,
    yes: bool = True,
    apothem_home: Path | None = None,
    ref: str = TAG,
    dry_run: bool = False,
    gpg_status: str | None = None,
    gpg_program: str | None = None,
    extra_env: dict[str, str] | None = None,
    path_first: list[Path] | None = None,
    prelude: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run install.sh against the fixture release.

    PRELUDE is sh run first in the process that then becomes the installer,
    so its ``$$`` is the installer's process ID.

    The tag check reads GPG_STATUS from a stub gpg (a good signature by the
    maintainer key by default); GPG_PROGRAM names another gpg.program.
    PATH_FIRST lists stub directories to put ahead of everything on PATH.
    """
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (tmp_path / "temp").mkdir(exist_ok=True)
    env = {k: v for k, v in hermetic_git_env().items() if not k.startswith("APOTHEM_")}
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
            "APOTHEM_REPO": str(tmp_path / "fixture-repo"),
            "APOTHEM_HOME": str(apothem_home or tmp_path / "apothem-home"),
        }
    )
    if gpg_program is None:
        status = gpg_status
        if status is None:
            status = good_signature_status(MAINTAINER_FINGERPRINT)
        env["GIT_CONFIG_GLOBAL"] = str(write_stub_gpg(tmp_path / "stub-gpg", status))
    else:
        gitconfig = tmp_path / "gitconfig"
        gitconfig.write_text(f"[gpg]\n\tprogram = {gpg_program}\n", encoding="utf-8")
        env["GIT_CONFIG_GLOBAL"] = str(gitconfig)
    env.update(extra_env or {})
    if mode is not None:
        env["APOTHEM_VERIFY"] = mode
    first = list(path_first or [])
    if cosign_dir is not None:
        first.append(cosign_dir)
    if first:
        prefix = os.pathsep.join(str(entry) for entry in first)
        env["PATH"] = f"{prefix}{os.pathsep}{env.get('PATH', os.defpath)}"
    staging = tmp_path / "installer-under-test"
    staging.mkdir(exist_ok=True)
    installer = staging / "install.sh"
    shutil.copy2(INSTALLER, installer)
    args = ["bash", str(installer)]
    if dry_run:
        args.append("--dry-run")
    if yes:
        args.append("--yes")
    if prelude is not None:
        args = ["sh", "-c", f'{prelude}\nexec "$@"', "sh", *args]
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


# --- the cosign check -------------------------------------------------------


def test_release_mode_has_cosign_check_the_identity_and_the_tag_commit(
    tmp_path: Path,
) -> None:
    """cosign is asked to verify SHA256SUMS against the release workflow at
    this tag, by exact identity and issuer, and to require that its verified
    certificate was issued to a run on the signed tag's commit. The archive
    is installed with no checksum-mode caveat."""
    base = _release(tmp_path)
    commit = _tag_commit(tmp_path)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir)

    combined = result.stdout + result.stderr
    assert TAG_OK_MARKER in combined, combined
    assert f"{COSIGN_OK_MARKER}, {COSIGN_COMMIT_MARKER} {commit}" in combined, combined
    assert CHECKSUM_CAVEAT not in combined, combined
    assert (tmp_path / "apothem-home" / "src" / "apothem" / "__init__.py").is_file()
    args = _cosign_args(cosign_dir)
    assert args is not None, combined
    assert args[0] == "verify-blob", args
    assert args[args.index("--certificate-identity") + 1] == IDENTITY, args
    assert args[args.index("--certificate-oidc-issuer") + 1] == ISSUER, args
    assert args[args.index("--certificate-github-workflow-sha") + 1] == commit, args
    assert args.count("--certificate-github-workflow-sha") == 1, args
    assert "--certificate-identity-regexp" not in args, args
    assert "--certificate-oidc-issuer-regexp" not in args, args
    assert args[args.index("--bundle") + 1].endswith("SHA256SUMS.cosign.bundle"), args
    assert args[-1].endswith("SHA256SUMS"), args
    _assert_no_staging(tmp_path)


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
    commit = _tag_commit(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path, succeed=False))

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert COSIGN_FAIL_MARKER in combined, combined
    assert f"in a run on the signed tag's commit {commit}" in combined, combined
    assert "none of the expected identities matched" in combined, combined
    assert not (tmp_path / "apothem-home").exists(), combined
    assert list((tmp_path / "temp").iterdir()) == [], "the download was left behind"
    _assert_no_staging(tmp_path)


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
    assert not (tmp_path / "apothem-home").exists(), combined


def test_missing_bundle_aborts_with_guidance(tmp_path: Path) -> None:
    base = _release(tmp_path, bundle=None)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "Could not download SHA256SUMS.cosign.bundle" in combined, combined
    assert "APOTHEM_VERIFY=signature" in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert not (tmp_path / "apothem-home").exists(), combined


def test_the_early_bundle_name_is_read_when_the_current_one_is_absent(
    tmp_path: Path,
) -> None:
    """Early releases name the SHA256SUMS bundle ``SHA256SUMS.sig``."""
    base = _release(tmp_path, bundle="SHA256SUMS.sig")
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir)

    combined = result.stdout + result.stderr
    assert COSIGN_OK_MARKER in combined, combined
    args = _cosign_args(cosign_dir)
    assert args is not None, combined
    assert args[args.index("--certificate-github-workflow-sha") + 1] == _tag_commit(
        tmp_path
    ), args
    assert (tmp_path / "apothem-home" / "src" / "apothem" / "__init__.py").is_file()


@requires_no_host_cosign
def test_release_mode_without_cosign_fails_before_downloading(tmp_path: Path) -> None:
    base = _release(tmp_path)

    result = _run(tmp_path, base)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "APOTHEM_VERIFY=release needs cosign on PATH" in combined, combined
    assert list((tmp_path / "temp").iterdir()) == [], combined


# --- the tag check ----------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "marker"),
    [
        pytest.param(
            good_signature_status(OTHER_FINGERPRINT),
            "not from the maintainer key",
            id="another-key",
        ),
        pytest.param("", "is unsigned or its signature did not verify", id="unsigned"),
    ],
)
def test_a_cosign_valid_release_without_the_maintainer_tag_is_refused(
    tmp_path: Path, status: str, marker: str
) -> None:
    """Anyone who can push a tag can make the release workflow sign a
    release; without the maintainer key's tag signature it is refused before
    cosign runs, and APOTHEM_ALLOW_UNVERIFIED does not change that."""
    base = _release(tmp_path)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(
        tmp_path,
        base,
        cosign_dir=cosign_dir,
        gpg_status=status,
        extra_env={"APOTHEM_ALLOW_UNVERIFIED": "1"},
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert marker in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert not (tmp_path / "apothem-home").exists(), combined


@pytest.mark.parametrize("allow_unverified", ["0", "1"])
def test_a_repointed_signed_tag_is_refused_before_cosign_runs(
    tmp_path: Path, allow_unverified: str
) -> None:
    """refs/tags/v9.9.9 points at a maintainer-signed tag object that names
    itself v9.9.8: the signature is good, but it is another release's tag.
    The installer refuses it before cosign runs or anything downloads, and
    APOTHEM_ALLOW_UNVERIFIED=1 does not change that."""
    base = _release(tmp_path)
    repoint_tag(tmp_path / "fixture-repo", "v9.9.8", TAG)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(
        tmp_path,
        base,
        cosign_dir=cosign_dir,
        extra_env={"APOTHEM_ALLOW_UNVERIFIED": allow_unverified},
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert REPOINTED_MARKER in combined, combined
    assert TAG_OK_MARKER not in combined, combined
    assert "Downloading" not in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert not (tmp_path / "apothem-home").exists(), combined
    assert list((tmp_path / "temp").iterdir()) == [], combined


def test_a_missing_gpg_is_named(tmp_path: Path) -> None:
    base = _release(tmp_path)

    result = _run(
        tmp_path,
        base,
        cosign_dir=_stub_cosign(tmp_path),
        gpg_program=str(tmp_path / "no-such-gpg"),
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "gpg not found" in combined, combined


# --- mode selection ---------------------------------------------------------


def test_auto_mode_keeps_an_existing_clone_on_the_clone_path(tmp_path: Path) -> None:
    """With cosign present, auto still updates an existing clone through the
    tag check instead of replacing it with the archive."""
    base = _release(tmp_path)
    home = tmp_path / "apothem-home"
    _clone_into(tmp_path, home)
    (home / "notes.txt").write_text("mine\n", encoding="utf-8")
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, mode=None, cosign_dir=cosign_dir)

    combined = result.stdout + result.stderr
    assert "is a git clone — updating it" in combined, combined
    assert "cosign found" not in combined, combined
    assert TAG_OK_MARKER in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert (home / ".git").is_dir(), combined
    assert git(["rev-parse", "HEAD"], home).strip() == _tag_commit(tmp_path)
    assert (home / "notes.txt").read_text(encoding="utf-8") == "mine\n"
    assert not (home / SOURCE_MANIFEST).exists(), combined


def test_auto_mode_sends_a_branch_ref_to_the_clone_path(tmp_path: Path) -> None:
    base = _release(tmp_path)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, mode=None, cosign_dir=cosign_dir, ref="main")

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "cosign found" not in combined, combined
    assert "Ref main is not a signed release tag" in combined, combined
    assert _cosign_args(cosign_dir) is None, combined


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


# --- what happens to APOTHEM_HOME -------------------------------------------


def test_an_archive_install_records_its_source_entries(tmp_path: Path) -> None:
    """The manifest lists the archive's top-level entries and itself, so a
    later swap can tell them from the engine's data."""
    base = _release(tmp_path, extra={"legacy/tool.py": b"tool\n"})

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path))

    combined = result.stdout + result.stderr
    manifest = tmp_path / "apothem-home" / SOURCE_MANIFEST
    assert manifest.is_file(), combined
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert sorted(lines) == sorted(
        [SOURCE_MANIFEST, "legacy", "pyproject.toml", "src"]
    ), lines
    assert len(lines) == len(set(lines)), lines


def test_an_earlier_install_is_updated_without_yes_and_keeps_engine_data(
    tmp_path: Path,
) -> None:
    """An earlier archive install is updated in place without --yes. Its
    source is replaced whole, so a module the new release dropped goes, and
    the engine's backups/ and state/ move into the new tree."""
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=False)

    combined = result.stdout + result.stderr
    assert "Updating the earlier install" in combined, combined
    assert (home / "src" / "apothem" / "__init__.py").is_file(), combined
    assert not (home / "src" / "apothem" / "removed_module.py").exists(), combined
    _assert_engine_data_kept(home)
    _assert_no_staging(tmp_path)


def test_an_archive_update_drops_entries_the_new_release_no_longer_ships(
    tmp_path: Path,
) -> None:
    """An archive-to-archive update removes the top-level entries the
    earlier install's manifest lists and the new release does not ship, and
    keeps everything the manifest does not list."""
    home = tmp_path / "apothem-home"
    cosign_dir = _stub_cosign(tmp_path)
    first = _run(
        tmp_path,
        _release(tmp_path, extra={"legacy/tool.py": b"tool\n"}),
        cosign_dir=cosign_dir,
    )
    assert (home / "legacy" / "tool.py").is_file(), first.stdout + first.stderr
    _seed_engine_data(home)
    (home / "notes.txt").write_text("mine\n", encoding="utf-8")

    result = _run(tmp_path, _release(tmp_path), cosign_dir=cosign_dir, yes=False)

    combined = result.stdout + result.stderr
    assert "Updating the earlier install" in combined, combined
    assert not (home / "legacy").exists(), combined
    assert (home / "src" / "apothem" / "__init__.py").is_file(), combined
    assert (home / "notes.txt").read_text(encoding="utf-8") == "mine\n"
    _assert_engine_data_kept(home)
    lines = (home / SOURCE_MANIFEST).read_text(encoding="utf-8").splitlines()
    assert "legacy" not in lines, lines
    assert "notes.txt" not in lines, lines
    _assert_no_staging(tmp_path)


def test_explicit_release_mode_refuses_a_git_clone_without_yes(tmp_path: Path) -> None:
    base = _release(tmp_path)
    home = tmp_path / "apothem-home"
    _clone_into(tmp_path, home)
    before = _snapshot(home)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir, yes=False)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert CLONE_REFUSED_MARKER in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert _snapshot(home) == before, combined


def test_yes_replaces_a_clone_with_the_archive_and_keeps_untracked_data(
    tmp_path: Path,
) -> None:
    """--yes replaces a real clone with the archive: the entries the clone
    does not track (the engine's backups/ and state/, a user's notes) move
    into the new install, and the clone's own tree (.git and every entry it
    tracks, .github here) is moved to <home>.before-apothem-<time> instead
    of being deleted, and the installer says where."""
    base = _release(tmp_path)
    home = tmp_path / "apothem-home"
    _commit_upstream(tmp_path, {".github/workflows/ci.yml": "name: ci\n"})
    _clone_into(tmp_path, home)
    _seed_engine_data(home)
    (home / "notes.txt").write_text("mine\n", encoding="utf-8")

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True)

    combined = result.stdout + result.stderr
    assert "Replacing the git clone at" in combined, combined
    assert "the clone's own tree will be moved to a sibling folder" in combined
    assert not (home / ".git").exists(), combined
    assert not (home / ".github").exists(), combined
    assert (home / "src" / "apothem" / "__init__.py").is_file(), combined
    assert (home / "notes.txt").read_text(encoding="utf-8") == "mine\n"
    _assert_engine_data_kept(home)
    assert (home / SOURCE_MANIFEST).is_file(), combined
    kept = sorted(tmp_path.glob("apothem-home.before-apothem-*"))
    assert len(kept) == 1, combined
    assert (
        f"The earlier clone's tree is kept at {kept[0]}; delete it once you no "
        "longer need it."
    ) in combined, combined
    assert (kept[0] / ".git").is_dir(), combined
    assert (kept[0] / ".github" / "workflows" / "ci.yml").is_file(), combined
    assert (
        git(["rev-parse", "HEAD"], kept[0]).strip()
        == git(["rev-parse", "main"], tmp_path / "fixture-repo").strip()
    )
    assert not ENGINE_DATA & {p.name for p in kept[0].iterdir()}, combined
    assert not (kept[0] / "notes.txt").exists(), combined
    _assert_no_staging(tmp_path)


def test_other_content_at_apothem_home_is_refused_without_yes(tmp_path: Path) -> None:
    home = tmp_path / "apothem-home"
    home.mkdir()
    (home / "keep.txt").write_text("not apothem's to delete\n", encoding="utf-8")
    before = _snapshot(home)
    base = _release(tmp_path)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir, yes=False)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert NOT_APOTHEM_MARKER in combined, combined
    assert "re-run with --yes to have it moved aside for you" in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert _snapshot(home) == before
    assert not list(tmp_path.glob("apothem-home.before-apothem-*")), combined


def test_yes_moves_a_non_apothem_folder_aside_unchanged(tmp_path: Path) -> None:
    """--yes moves a folder that holds no Apothem install, whole and
    unchanged, to a sibling <home>.before-apothem-<time> folder, says where,
    and installs fresh. Entries that share a name with the source tree
    (src/, README.md) are not mixed into the new install."""
    home = tmp_path / "apothem-home"
    (home / "src").mkdir(parents=True)
    (home / "src" / "mine.py").write_text("print('mine')\n", encoding="utf-8")
    (home / "README.md").write_text("my notes\n", encoding="utf-8")
    (home / ".hidden").write_text("hidden\n", encoding="utf-8")
    before = _snapshot(home)
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True)

    combined = result.stdout + result.stderr
    asides = sorted(tmp_path.glob("apothem-home.before-apothem-*"))
    assert len(asides) == 1, combined
    aside = asides[0]
    assert re.fullmatch(r"apothem-home\.before-apothem-\d{14}(-\d+)?", aside.name)
    assert _snapshot(aside) == before, combined
    assert f"were moved, unchanged, to {aside}" in combined, combined
    assert (home / "src" / "apothem" / "__init__.py").is_file(), combined
    assert not (home / "src" / "mine.py").exists(), combined
    assert not (home / "README.md").exists(), combined
    assert not (home / ".hidden").exists(), combined
    _assert_no_staging(tmp_path)


@pytest.mark.parametrize("dry_run", [False, True], ids=["install", "dry-run"])
@pytest.mark.parametrize("target", ["earlier-install", "empty"])
def test_a_symlinked_apothem_home_is_refused(
    tmp_path: Path, dry_run: bool, target: str
) -> None:
    """A swap would replace the link itself, so the installer refuses an
    APOTHEM_HOME that is a symbolic link, even with --yes and in a dry run,
    before the tag check or any download."""
    real = tmp_path / "real-home"
    if target == "earlier-install":
        _seed_earlier_install(real)
    else:
        real.mkdir()
    home = tmp_path / "apothem-home"
    home.symlink_to(real, target_is_directory=True)
    before = _snapshot(real)
    base = _release(tmp_path)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir, yes=True, dry_run=dry_run)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert f"Destination {home} {LINK_MARKER}" in combined, combined
    assert TAG_OK_MARKER not in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert home.is_symlink(), combined
    assert home.readlink() == real
    assert _snapshot(real) == before, combined
    assert list((tmp_path / "temp").iterdir()) == [], combined
    _assert_no_staging(tmp_path)


# --- the dry run ------------------------------------------------------------


def test_dry_run_leaves_apothem_home_and_its_parent_alone(tmp_path: Path) -> None:
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    before = _snapshot(home)
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), dry_run=True)

    combined = result.stdout + result.stderr
    assert COSIGN_OK_MARKER in combined, combined
    assert "dry run, so" in combined, combined
    assert _snapshot(home) == before, combined
    _assert_no_staging(tmp_path)
    assert list((tmp_path / "temp").iterdir()) == [], "the scratch copy was left behind"


def test_a_dry_run_with_yes_does_not_move_a_folder_aside(tmp_path: Path) -> None:
    home = tmp_path / "apothem-home"
    home.mkdir()
    (home / "keep.txt").write_text("mine\n", encoding="utf-8")
    before = _snapshot(home)
    base = _release(tmp_path)

    result = _run(
        tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True, dry_run=True
    )

    combined = result.stdout + result.stderr
    assert "dry run, so" in combined, combined
    assert "holds no Apothem install; it would be moved, unchanged" in combined
    assert "will be moved" not in combined, combined
    assert _snapshot(home) == before, combined
    assert not list(tmp_path.glob("apothem-home.before-apothem-*")), combined
    _assert_no_staging(tmp_path)


@pytest.mark.parametrize(
    ("layout", "marker"),
    [
        pytest.param("other-content", NOT_APOTHEM_MARKER, id="other-content"),
        pytest.param("clone", CLONE_REFUSED_MARKER, id="git-clone"),
    ],
)
def test_a_dry_run_refuses_what_the_real_run_refuses(
    tmp_path: Path, layout: str, marker: str
) -> None:
    """Without --yes, a dry run stops where the real run would: before the
    tag check, cosign, or any download, with APOTHEM_HOME left alone."""
    base = _release(tmp_path)
    home = tmp_path / "apothem-home"
    if layout == "clone":
        _clone_into(tmp_path, home)
    else:
        home.mkdir()
        (home / "keep.txt").write_text("mine\n", encoding="utf-8")
    before = _snapshot(home)
    cosign_dir = _stub_cosign(tmp_path)

    real = _run(tmp_path, base, cosign_dir=cosign_dir, yes=False)
    dry = _run(tmp_path, base, cosign_dir=cosign_dir, yes=False, dry_run=True)

    for result in (real, dry):
        combined = result.stdout + result.stderr
        assert result.returncode != 0, combined
        assert marker in combined, combined
        assert TAG_OK_MARKER not in combined, combined
    assert _cosign_args(cosign_dir) is None
    assert _snapshot(home) == before
    assert list((tmp_path / "temp").iterdir()) == []


# --- a failed swap ----------------------------------------------------------

# The new tree, as it sits in its staging folder beside APOTHEM_HOME.
_NEW_TREE = f"*/.apothem-extract.*/{ARCHIVE_ROOT}"


@pytest.mark.parametrize(
    ("step", "message"),
    [
        pytest.param(
            "carry", "Could not move state into the new install", id="carry-data"
        ),
        pytest.param(
            "aside", "Could not move the existing {home} aside", id="move-home-aside"
        ),
        pytest.param(
            "new-into-home",
            "Could not move the new source to {home}",
            id="move-new-tree-in",
        ),
        pytest.param(
            "interrupt", "Interrupted while replacing {home}", id="interrupted"
        ),
        pytest.param(
            "interrupt-carry",
            "Interrupted while replacing {home}",
            id="interrupted-while-carrying",
        ),
        pytest.param(
            "quit-carry",
            "Interrupted while replacing {home}",
            id="quit-while-carrying",
        ),
        pytest.param(
            "pipe-aside",
            "Interrupted while replacing {home}",
            id="sigpipe-after-moving-home-aside",
        ),
        pytest.param(
            "hup-moved-in",
            "Interrupted while replacing {home}",
            id="hangup-after-moving-new-tree-in",
        ),
    ],
)
def test_a_failed_swap_puts_the_earlier_install_back(
    tmp_path: Path, step: str, message: str
) -> None:
    """Whichever rename of the swap fails, or is interrupted (by SIGTERM,
    SIGINT, SIGQUIT, SIGPIPE or SIGHUP, between any two renames), the
    earlier install is put back byte for byte with its backups/, state/ and
    plans/ inside it, the installer says so, and no staging folder is left
    holding data. The carry moves backups, plans, state in that order, so
    an interrupt after plans leaves the data split between the two trees."""
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    before = _snapshot(home)
    base = _release(tmp_path)
    rules = {
        "carry": [(f"{home}/state", "*", "fail")],
        "aside": [(str(home), "*/.apothem-old.*/home", "fail")],
        "new-into-home": [(_NEW_TREE, str(home), "fail")],
        "interrupt": [(_NEW_TREE, str(home), "interrupt")],
        "interrupt-carry": [(f"{home}/plans", "*", "INT")],
        "quit-carry": [(f"{home}/plans", "*", "QUIT")],
        "pipe-aside": [(str(home), "*/.apothem-old.*/home", "PIPE")],
        "hup-moved-in": [(_NEW_TREE, str(home), "HUP")],
    }[step]
    mv_dir = _stub_mv(tmp_path, rules)

    result = _run(
        tmp_path,
        base,
        cosign_dir=_stub_cosign(tmp_path),
        yes=False,
        path_first=[mv_dir],
    )

    combined = result.stdout + result.stderr
    calls = (mv_dir / "mv-calls.txt").read_text(encoding="utf-8")
    assert result.returncode != 0, combined
    expected = (
        f"{message.format(home=home)}; the earlier install at {home} {BACK_IN_PLACE}"
    )
    assert expected in combined, combined + calls
    assert _snapshot(home) == before, combined + calls
    _assert_no_staging(tmp_path)
    assert list((tmp_path / "temp").iterdir()) == [], combined


def test_a_failed_swap_puts_a_folder_moved_aside_back(tmp_path: Path) -> None:
    """With --yes on a non-Apothem folder, a failure to move the new tree in
    moves the folder back from beside APOTHEM_HOME, unchanged."""
    home = tmp_path / "apothem-home"
    home.mkdir()
    (home / "keep.txt").write_text("mine\n", encoding="utf-8")
    before = _snapshot(home)
    base = _release(tmp_path)
    mv_dir = _stub_mv(tmp_path, [(_NEW_TREE, str(home), "fail")])

    result = _run(
        tmp_path, base, cosign_dir=_stub_cosign(tmp_path), path_first=[mv_dir]
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "the earlier folder is back in place and unchanged" in combined, combined
    assert _snapshot(home) == before, combined
    assert not list(tmp_path.glob("apothem-home.before-apothem-*")), combined
    _assert_no_staging(tmp_path)


def test_a_failed_rollback_keeps_and_names_every_copy(tmp_path: Path) -> None:
    """When moving the new tree in fails and moving the earlier install back
    fails too, nothing is deleted: the message names where the earlier tree
    and the moved data are, and between them they hold every byte."""
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    before = _snapshot(home)
    base = _release(tmp_path)
    mv_dir = _stub_mv(
        tmp_path,
        [
            (_NEW_TREE, str(home), "fail"),
            ("*/.apothem-old.*/home", str(home), "fail"),
        ],
    )

    result = _run(
        tmp_path,
        base,
        cosign_dir=_stub_cosign(tmp_path),
        yes=False,
        path_first=[mv_dir],
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "putting the earlier install back also failed" in combined, combined
    assert BACK_IN_PLACE not in combined, combined
    assert not home.exists(), combined
    olds = sorted(tmp_path.glob(".apothem-old.*"))
    news = sorted(tmp_path.glob(f".apothem-extract.*/{ARCHIVE_ROOT}"))
    assert len(olds) == 1, combined
    assert len(news) == 1, combined
    assert f"it is at {olds[0]}/home" in combined, combined
    assert f"(with any moved data under {news[0]})" in combined, combined
    kept = _snapshot(olds[0] / "home")
    moved = _engine_data(news[0])
    assert {**kept, **moved} == before, combined
    assert moved == {
        rel: body for rel, body in before.items() if rel.split("/")[0] in ENGINE_DATA
    }, combined


@pytest.mark.parametrize(
    "rule",
    [
        pytest.param(("{home}", "*.before-apothem-*", "TERM"), id="after-set-aside"),
        pytest.param((_NEW_TREE, "{home}", "INT"), id="after-move-in"),
    ],
)
def test_an_interrupted_set_aside_puts_the_folder_back(
    tmp_path: Path, rule: tuple[str, str, str]
) -> None:
    """With --yes on a non-Apothem folder, an interrupt after the folder was
    set aside, or after the new tree moved in, puts the folder back
    unchanged and leaves no set-aside copy or staging folder."""
    home = tmp_path / "apothem-home"
    home.mkdir()
    (home / "keep.txt").write_text("mine\n", encoding="utf-8")
    before = _snapshot(home)
    base = _release(tmp_path)
    src, dst, action = rule
    mv_dir = _stub_mv(
        tmp_path, [(src.format(home=home), dst.format(home=home), action)]
    )

    result = _run(
        tmp_path, base, cosign_dir=_stub_cosign(tmp_path), path_first=[mv_dir]
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        f"Interrupted while replacing {home}; the earlier folder is back in place "
        "and unchanged"
    ) in combined, combined
    assert _snapshot(home) == before, combined
    assert not list(tmp_path.glob("apothem-home.before-apothem-*")), combined
    _assert_no_staging(tmp_path)


# --- engine data, local work, and names -------------------------------------

LOCAL_WORK_MARKER = (
    "is a git clone with local work that replacing it would lose (changes, "
    "stashes, unpushed commits, or untracked files in its source tree). Commit "
    "and push that work, or move it elsewhere, then re-run."
)


def test_a_home_with_only_engine_data_is_updated_without_yes(tmp_path: Path) -> None:
    """A folder that holds nothing but the engine's data (an install whose
    source was removed) is updated like an empty one, without --yes, and the
    data moves into the new install."""
    home = tmp_path / "apothem-home"
    home.mkdir()
    _seed_engine_data(home)
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=False)

    combined = result.stdout + result.stderr
    assert f"Source ready at {home}" in combined, combined
    assert NOT_APOTHEM_MARKER not in combined, combined
    assert (home / "src" / "apothem" / "__init__.py").is_file(), combined
    _assert_engine_data_kept(home)
    manifest = (home / SOURCE_MANIFEST).read_text(encoding="utf-8").splitlines()
    assert not ENGINE_DATA & set(manifest), manifest
    _assert_no_staging(tmp_path)


@pytest.mark.parametrize("dry_run", [False, True], ids=["install", "dry-run"])
@pytest.mark.parametrize(
    "work",
    ["tracked-change", "staged-file", "stash", "unpushed-commit", "untracked-in-src"],
)
def test_yes_does_not_replace_a_clone_that_holds_local_work(
    tmp_path: Path, work: str, dry_run: bool
) -> None:
    """--yes allows replacing a clean clone with the archive, but not one
    holding work the replacement would lose: a change to a tracked file, a
    staged new file, a stash, a commit no remote branch holds, or an
    untracked file inside a folder the clone tracks. A dry run refuses the
    same way, and the clone is left as it was."""
    base = _release(tmp_path)
    home = tmp_path / "apothem-home"
    _clone_into(tmp_path, home)
    if work == "tracked-change":
        (home / "pyproject.toml").write_text("# mine\n", encoding="utf-8")
    elif work == "staged-file":
        (home / "src" / "apothem" / "mine.py").write_text("x = 1\n", encoding="utf-8")
        git(["add", "src/apothem/mine.py"], home)
    elif work == "stash":
        (home / "pyproject.toml").write_text("# mine\n", encoding="utf-8")
        git([*_COMMIT_AS, "stash", "--quiet"], home)
    elif work == "unpushed-commit":
        _commit(home, {"src/apothem/mine.py": "x = 1\n"}, "local work")
    else:
        (home / "src" / "apothem" / "my-skill.md").write_text(
            "mine\n", encoding="utf-8"
        )
    before = _snapshot(home)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir, yes=True, dry_run=dry_run)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert f"{home} {LOCAL_WORK_MARKER}" in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert _snapshot(home) == before, combined
    _assert_no_staging(tmp_path)


@pytest.mark.parametrize("layout", ["separate-git-dir", "worktree"])
def test_a_home_whose_git_is_a_file_is_a_clone(tmp_path: Path, layout: str) -> None:
    """A .git that is a file (a clone made with --separate-git-dir, or a
    worktree) marks a clone: explicit release mode refuses to replace it
    without --yes, and auto mode updates it in place through the tag check."""
    base = _release(tmp_path)
    home = tmp_path / "apothem-home"
    if layout == "separate-git-dir":
        _clone_into(tmp_path, home, "--separate-git-dir", str(tmp_path / "sep.git"))
    else:
        _clone_into(tmp_path, tmp_path / "main-clone")
        git(
            ["worktree", "add", "--quiet", "--detach", str(home), "HEAD"],
            tmp_path / "main-clone",
        )
    assert (home / ".git").is_file()
    before = _snapshot(home)
    cosign_dir = _stub_cosign(tmp_path)

    refused = _run(tmp_path, base, cosign_dir=cosign_dir, yes=False)

    combined = refused.stdout + refused.stderr
    assert refused.returncode != 0, combined
    assert CLONE_REFUSED_MARKER in combined, combined
    assert _snapshot(home) == before, combined

    updated = _run(tmp_path, base, mode=None, cosign_dir=cosign_dir, yes=False)

    combined = updated.stdout + updated.stderr
    assert f"Source ready at {home}" in combined, combined
    assert "is a git clone — updating it" in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert (home / ".git").is_file(), combined
    assert git(["rev-parse", "HEAD"], home).strip() == _tag_commit(tmp_path)


@pytest.mark.parametrize("suffix", ["/", "//", "/.", "/./", "/./."])
def test_a_trailing_slash_does_not_hide_a_symlinked_home(
    tmp_path: Path, suffix: str
) -> None:
    """APOTHEM_HOME given with a trailing "/" or "/." still names the link,
    so a symbolic link is refused rather than looked through."""
    real = tmp_path / "real-home"
    _seed_earlier_install(real)
    home = tmp_path / "apothem-home"
    home.symlink_to(real, target_is_directory=True)
    before = _snapshot(real)
    base = _release(tmp_path)

    result = _run(
        tmp_path,
        base,
        cosign_dir=_stub_cosign(tmp_path),
        extra_env={"APOTHEM_HOME": f"{home}{suffix}"},
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert f"Destination {home} {LINK_MARKER}" in combined, combined
    assert home.is_symlink(), combined
    assert _snapshot(real) == before, combined
    _assert_no_staging(tmp_path)


@pytest.mark.parametrize("dry_run", [False, True], ids=["install", "dry-run"])
def test_an_entry_with_a_special_name_stops_the_update(
    tmp_path: Path, dry_run: bool
) -> None:
    """The swap moves the entries it keeps by name, so one whose name has a
    space stops the update before anything moves, in a dry run as well."""
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    (home / "my notes.txt").write_text("mine\n", encoding="utf-8")
    before = _snapshot(home)
    base = _release(tmp_path)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir, yes=False, dry_run=dry_run)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        f"Cannot carry {home}/my notes.txt over to the new install (its name has "
        "a space or another special character)"
    ) in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert _snapshot(home) == before, combined
    _assert_no_staging(tmp_path)


# --- the tag object and the environment --------------------------------------


def _tag_a_tree(repo: Path, tag: str) -> None:
    """Point refs/tags/TAG at a signed-looking tag object that names itself
    TAG but tags a tree, not a commit."""
    tree = git(["rev-parse", "HEAD^{tree}"], repo).strip()
    tag_file = repo.parent / f"{tag}-tree.tag"
    tag_file.write_text(
        f"object {tree}\n"
        "type tree\n"
        f"tag {tag}\n"
        "tagger Fixture <fixture@example.invalid> 1700000000 +0000\n"
        "\n"
        "a tree, not a release\n"
        "-----BEGIN PGP SIGNATURE-----\n"
        "\n"
        "c3R1Yg==\n"
        "-----END PGP SIGNATURE-----\n",
        encoding="utf-8",
        newline="\n",
    )
    tag_sha = git(["hash-object", "-t", "tag", "-w", str(tag_file)], repo).strip()
    git(["update-ref", f"refs/tags/{tag}", tag_sha], repo)


def test_a_signed_tag_of_a_tree_is_refused(tmp_path: Path) -> None:
    """A maintainer-signed tag object named for the release that tags a tree
    instead of a commit is refused before cosign runs."""
    base = _release(tmp_path)
    _tag_a_tree(tmp_path / "fixture-repo", TAG)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert REPOINTED_MARKER in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert not (tmp_path / "apothem-home").exists(), combined


def test_an_apothem_repo_that_reads_as_an_option_is_refused(tmp_path: Path) -> None:
    base = _release(tmp_path)
    marker = tmp_path / "planted"

    result = _run(
        tmp_path,
        base,
        cosign_dir=_stub_cosign(tmp_path),
        extra_env={"APOTHEM_REPO": f"--upload-pack=touch {marker}"},
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        "APOTHEM_REPO must be a repository URL or path, not an option: "
        f"--upload-pack=touch {marker}"
    ) in combined, combined
    assert not marker.exists(), combined


def test_git_location_variables_do_not_reach_the_installer(tmp_path: Path) -> None:
    """GIT_DIR and its relatives in the caller's environment would point the
    installer's git commands at another repository; they are dropped."""
    base = _release(tmp_path)
    elsewhere = tmp_path / "elsewhere.git"
    git(["init", "--quiet", "--bare", str(elsewhere)], tmp_path)

    result = _run(
        tmp_path,
        base,
        cosign_dir=_stub_cosign(tmp_path),
        extra_env={
            "GIT_DIR": str(elsewhere),
            "GIT_WORK_TREE": str(tmp_path),
            "GIT_OBJECT_DIRECTORY": str(elsewhere / "objects"),
        },
    )

    combined = result.stdout + result.stderr
    assert "Source ready at" in combined, combined
    assert TAG_OK_MARKER in combined, combined
    assert COSIGN_OK_MARKER in combined, combined
    assert git(["for-each-ref"], elsewhere) == "", combined


# --- clones of other things, taken names, and what a failure reports --------


def _foreign_clone(tmp_path: Path, home: Path) -> None:
    """Clone a repository that holds no Apothem source to HOME."""
    other = tmp_path / "other-repo"
    _commit_upstream_to(other, {"notes.txt": "mine\n"})
    git(["clone", "--quiet", str(other), str(home)], tmp_path)


def _commit_upstream_to(repo: Path, files: dict[str, str]) -> None:
    repo.mkdir(parents=True)
    git(["init", "--quiet", "--initial-branch", "main"], repo)
    _commit(repo, files, "not apothem")


def test_a_clone_of_something_else_is_refused_without_yes(tmp_path: Path) -> None:
    """A git clone that holds no Apothem source is an unrelated folder: auto
    mode does not take the clone path for it, and without --yes it is
    refused like any folder with no Apothem install."""
    base = _release(tmp_path)
    home = tmp_path / "apothem-home"
    _foreign_clone(tmp_path, home)
    before = _snapshot(home)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, mode=None, cosign_dir=cosign_dir, yes=False)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert NOT_APOTHEM_MARKER in combined, combined
    assert "is a git clone — updating it" not in combined, combined
    assert CLONE_REFUSED_MARKER not in combined, combined
    assert _snapshot(home) == before, combined


def test_yes_moves_a_clone_of_something_else_aside_whole(tmp_path: Path) -> None:
    """With --yes, a clone that holds no Apothem source is moved aside
    unchanged, .git included, and the archive installs fresh."""
    base = _release(tmp_path)
    home = tmp_path / "apothem-home"
    _foreign_clone(tmp_path, home)
    before = _snapshot(home)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True)

    combined = result.stdout + result.stderr
    asides = sorted(tmp_path.glob("apothem-home.before-apothem-*"))
    assert len(asides) == 1, combined
    assert _snapshot(asides[0]) == before, combined
    assert f"were moved, unchanged, to {asides[0]}" in combined, combined
    assert (home / "src" / "apothem" / "__init__.py").is_file(), combined
    assert not (home / ".git").exists(), combined
    assert not (home / "notes.txt").exists(), combined
    _assert_no_staging(tmp_path)


STAMP = "20261108000000"


def _stub_date(tmp_path: Path) -> Path:
    """A stub ``date`` that always prints STAMP; return its directory."""
    stub_dir = tmp_path / "stub-date"
    stub_dir.mkdir()
    stub = stub_dir / "date"
    stub.write_text(f"#!/bin/sh\necho {STAMP}\n", encoding="utf-8", newline="\n")
    stub.chmod(EXECUTABLE_MODE)
    return stub_dir


@pytest.mark.parametrize("dry_run", [False, True], ids=["install", "dry-run"])
@pytest.mark.parametrize("layout", ["other-content", "clone"])
def test_both_set_aside_names_taken_stops_before_anything_moves(
    tmp_path: Path, layout: str, dry_run: bool
) -> None:
    """When <home>.before-apothem-<time> and <home>.before-apothem-<time>-<pid>
    both exist, mv would move the earlier folder into one of them, so the
    installer stops before anything moves, and both are left as they were."""
    base = _release(tmp_path)
    home = tmp_path / "apothem-home"
    if layout == "clone":
        _clone_into(tmp_path, home)
    else:
        home.mkdir()
        (home / "keep.txt").write_text("mine\n", encoding="utf-8")
    before = _snapshot(home)
    taken = tmp_path / f"apothem-home.before-apothem-{STAMP}"
    taken.mkdir()
    (taken / "older.txt").write_text("older\n", encoding="utf-8")
    prelude = f"mkdir '{taken}-'$$ && echo older2 > '{taken}-'$$/older.txt"
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(
        tmp_path,
        base,
        cosign_dir=cosign_dir,
        yes=True,
        dry_run=dry_run,
        path_first=[_stub_date(tmp_path)],
        prelude=prelude,
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        f"Could not move the existing {home} aside; nothing was changed" in combined
    ), combined
    assert _cosign_args(cosign_dir) is None, combined
    assert _snapshot(home) == before, combined
    assert _snapshot(taken) == {"older.txt": b"older\n"}, combined
    pid_taken = sorted(tmp_path.glob(f"apothem-home.before-apothem-{STAMP}-*"))
    assert len(pid_taken) == 1, combined
    assert _snapshot(pid_taken[0]) == {"older.txt": b"older2\n"}, combined
    _assert_no_staging(tmp_path)


def test_a_dry_run_with_yes_says_what_would_happen_to_a_clone(
    tmp_path: Path,
) -> None:
    """A dry run with --yes on a clean clone says what the real run would do,
    in the conditional, and changes nothing."""
    base = _release(tmp_path)
    home = tmp_path / "apothem-home"
    _clone_into(tmp_path, home)
    before = _snapshot(home)

    result = _run(
        tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True, dry_run=True
    )

    combined = result.stdout + result.stderr
    assert f"Would replace the git clone at {home}" in combined, combined
    assert "the clone's own tree would be moved to a sibling folder" in combined
    assert "Replacing the git clone" not in combined, combined
    assert " will be " not in combined, combined
    assert _snapshot(home) == before, combined
    assert not list(tmp_path.glob("apothem-home.before-apothem-*")), combined
    _assert_no_staging(tmp_path)


def test_a_dry_run_says_an_earlier_install_would_be_updated(tmp_path: Path) -> None:
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    base = _release(tmp_path)

    result = _run(
        tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=False, dry_run=True
    )

    combined = result.stdout + result.stderr
    assert f"Would update the earlier install at {home}" in combined, combined
    assert "Updating the earlier install" not in combined, combined


def test_a_failed_carry_rollback_names_home_as_where_the_install_is(
    tmp_path: Path,
) -> None:
    """When carrying the data fails and moving it back fails too, the earlier
    install never left APOTHEM_HOME, so the message names APOTHEM_HOME (not
    a set-aside folder) and where the moved data is, and keeps it."""
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    before = _snapshot(home)
    base = _release(tmp_path)
    mv_dir = _stub_mv(
        tmp_path,
        [
            (f"{home}/state", "*", "fail"),
            (f"{_NEW_TREE}/backups", f"{home}/backups", "fail"),
        ],
    )

    result = _run(
        tmp_path,
        base,
        cosign_dir=_stub_cosign(tmp_path),
        yes=False,
        path_first=[mv_dir],
    )

    combined = result.stdout + result.stderr
    news = sorted(tmp_path.glob(f".apothem-extract.*/{ARCHIVE_ROOT}"))
    assert result.returncode != 0, combined
    assert len(news) == 1, combined
    assert (
        "Could not move state into the new install, and putting the earlier "
        f"install back also failed: it is at {home} (with any moved data under "
        f"{news[0]}). Move it back to {home} by hand."
    ) in combined, combined
    assert ".apothem-old." not in combined, combined
    kept = _snapshot(home)
    moved = _engine_data(news[0])
    assert {**kept, **moved} == before, combined
    assert "backups/claude-code/set.json" in moved, combined


def _swap_functions() -> str:
    """install.sh's swap helpers, with the few top-level names they use."""
    text = INSTALLER.read_text(encoding="utf-8")
    paint = text[text.index("paint() {") :]
    paint = paint[: paint.index("\n}\n") + 3]
    start = text.index("home_is_link() {")
    end = text.index("# Downloads from an https")
    return (
        'COLOR_ERR=0\nDRY_RUN=0\nHOOKS_OFF=""\n'
        + paint
        + "die() { printf '%s\\n' \"$*\" >&2; exit 1; }\n"
        + "warn() { printf '%s\\n' \"$*\" >&2; }\n"
        + "info() { printf '%s\\n' \"$*\" >&2; }\n"
        + 'is_apothem_source() { [ -d "$1/src/apothem" ]; }\n'
        + text[start:end]
    )


def test_the_exit_trap_rolls_back_a_swap_still_under_way(tmp_path: Path) -> None:
    """A command that fails under set -e while a swap is under way ends the
    installer through its EXIT trap, which puts the carried data back into
    the earlier install, says so, and removes the empty set-aside folder."""
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    before = _snapshot(home)
    new = tmp_path / ".apothem-extract.test" / "apothem-new"
    (new / "src" / "apothem").mkdir(parents=True)
    script = tmp_path / "swap-under-way.sh"
    script.write_text(
        "set -eu\n"
        + _swap_functions()
        + f"APOTHEM_HOME='{home}'\n"
        + "trap on_exit EXIT\n"
        + f"_SW_MODE=keep\n_SW_NEW='{new}'\n_SW_KEEP=' backups state'\n"
        + f"_SW_OLD=\"$(mktemp -d '{tmp_path}/.apothem-old.XXXXXX')\"\n"
        + "_SW_PHASE=carry\n"
        + f"mv '{home}/backups' '{new}/backups'\n"
        + f"mv '{home}/state' '{new}/state'\n"
        + "false\n"
        + "echo not reached\n",
        encoding="utf-8",
        newline="\n",
    )

    result = subprocess.run(
        ["sh", str(script)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "not reached" not in combined, combined
    assert (
        f"Stopped while replacing {home}; the earlier install at {home} is back "
        "in place and unchanged"
    ) in combined, combined
    assert _snapshot(home) == before, combined
    assert not list(tmp_path.glob(".apothem-old.*")), combined


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="root reads a folder whatever its mode",
)
def test_an_unreadable_home_is_refused(tmp_path: Path) -> None:
    """A folder at APOTHEM_HOME that cannot be listed is refused by name
    instead of being taken for an empty one."""
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    base = _release(tmp_path)
    home.chmod(0)
    try:
        result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True)
    finally:
        home.chmod(EXECUTABLE_MODE)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert f"Cannot read {home}." in combined, combined
    assert (home / "state" / "ledger.json").is_file(), combined
    _assert_no_staging(tmp_path)


# REUSE-IgnoreEnd
