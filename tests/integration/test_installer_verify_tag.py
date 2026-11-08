# SPDX-License-Identifier: MIT

"""Release-tag verification abort branches (clone path).

Exercises the fail-closed signature gate in ``scripts/installer/install.sh``,
``install.ps1``, ``update.sh`` and ``update.ps1`` against a local fixture
repository — no network. The gate distinguishes two abort classes:

- **missing key** — the tag is signed but the maintainer public key is absent
  from the local keyring; the abort prints key-import guidance (import
  from the published key URL plus a fingerprint check against SECURITY.md).
- **bad / absent signature** — an unsigned or tampered tag; the abort is hard
  and deliberately does not advertise the ``APOTHEM_ALLOW_UNVERIFIED``
  override on a possible-tampering signal.
- **another key** — a valid signature from a key other than the maintainer
  key SECURITY.md publishes. ``git verify-tag`` accepts any key the local
  keyring holds, so each script pins the maintainer fingerprint and aborts on
  any other signer.

The installers' default verification mode, ``auto``, takes a cosign-checked
release archive when cosign is on PATH; these tests set
``APOTHEM_VERIFY=signature`` so they exercise the clone path on every host.

Each abort-class test runs every script against the same fixture, so the
four keep the same classes and messages. Every test asserts the abort happens
before any configuration materializes.
A stub verifier replays GnuPG's German output for both classes, to show the
split rests on GnuPG's status lines rather than its translated messages.
The fixture repository is minimal: the gate runs right after the source-shape
check (``src/apothem`` + ``pyproject.toml``), so no working engine tree is
required.

The tests after the abort classes cover the clone path's order of work on
install.sh and update.sh: an existing clone is fetched, the new tag is
checked (signature, key, and that the signed tag object names itself as the
release, not a re-pointed older one), and only then checked out by its
``refs/tags/`` name without ``--force``, so a failed check or a local change
leaves the clone as it was. They also cover the dry run, which refuses what
the real run refuses and leaves APOTHEM_HOME alone, a symbolic link at
APOTHEM_HOME, ``gpg.format=ssh``, and non-release refs taken with
``APOTHEM_ALLOW_UNVERIFIED=1``.

Every git process here, the fixture setup's and the scripts', runs without
the host's git configuration (``tests._shared.git_env``). A developer's
``gpg.format ssh`` would otherwise turn the fixture's ``git tag -s`` into an
SSH signature, which ``git verify-tag`` rejects for want of an allowed-signers
file instead of reporting the missing OpenPGP key. An autouse fixture plants
such configuration on every layer git reads, so a leak fails on any host.

The scripts run on the interpreter running these tests, never on the host's
``python3``. Given ``--yes``, install.sh pip-installs a missing click or rich
into the first ``python3`` on PATH, and install.ps1 does the same given
``-Yes``, so a host ``python3`` without rich would gain packages from this
file, and the run without ``--yes`` would pass only after a ``--yes`` run had
installed rich. A shim for ``sys.executable`` (``tests._shared.python_shim``)
leads every script's PATH, pip gets no package source, and the tests skip when
that interpreter cannot import click and rich. An autouse fixture puts a
``python3`` without them first on the host PATH, so a leak fails on any host.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests._shared.git_env import hermetic_git_env
from tests._shared.python_shim import write_python_shim
from tests._shared.release_fixture import repoint_tag

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "installer" / "install.sh"
INSTALLER_PS1 = REPO_ROOT / "scripts" / "installer" / "install.ps1"
UPDATER_SH = REPO_ROOT / "scripts" / "installer" / "update.sh"
UPDATER_PS1 = REPO_ROOT / "scripts" / "installer" / "update.ps1"

_PWSH = shutil.which("pwsh")
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# Runs one script's verification gate in the environment it is given.
GateRunner = Callable[[dict[str, str]], subprocess.CompletedProcess[str]]

# Message markers mirrored from the scripts' verification gates.
BAD_SIGNATURE_MARKER = "did not verify (possible tampering)"
MISSING_KEY_MARKER = "public key is not in the local keyring"
KEY_IMPORT_MARKER = "gpg --import"
OVERRIDE_SUGGESTION = "Set APOTHEM_ALLOW_UNVERIFIED=1"
OTHER_KEY_MARKER = "carries a valid signature, but not from the maintainer key"
MAINTAINER_OK_MARKER = "carries a valid signature from the maintainer key"
REPOINTED_MARKER = "so it was re-pointed (possible tampering)"
LOCAL_CHANGES_MARKER = "If it has local changes, commit or stash them, then re-run."
TRACKED_CHANGES_MARKER = (
    "has changes to tracked files. Commit or stash them, then re-run."
)
GPG_MISSING_MARKER = "gpg not found in PATH"
NOT_APOTHEM_MARKER = "is not empty and holds no Apothem install; refusing to replace it"
ARCHIVE_REFUSED_MARKER = (
    "is a release-archive install, not a git clone; refusing to replace it"
)
LINK_MARKER = "is a symbolic link. Point APOTHEM_HOME at the folder it links to"
NOT_RELEASE_WARNING = (
    "is not a signed release tag — proceeding because APOTHEM_ALLOW_UNVERIFIED=1"
)

# The primary-key fingerprint SECURITY.md publishes; every script pins it.
MAINTAINER_FINGERPRINT = "5C8998F9F241720445D3F28B70396FED9C634163"
# The fixture signer's fingerprint in the canned GnuPG results below.
OTHER_FINGERPRINT = "C2CD460ED9DCEF33C51123AE984AE72EA84995CA"


def _good_signature_status(primary: str, signing: str | None = None) -> str:
    """GnuPG's status lines for a good signature whose primary key is PRIMARY.

    The layout copies ``git verify-tag --raw`` on a real Apothem release tag:
    VALIDSIG carries the signing key's fingerprint first and the primary
    key's last. git accepts the signature only when a GOODSIG line follows a
    newline, so NEWSIG comes first.
    """
    if signing == "two-signatures":
        return _good_signature_status(primary) + _good_signature_status(
            OTHER_FINGERPRINT
        )
    signing = signing or primary
    return (
        "[GNUPG:] NEWSIG\n"
        f"[GNUPG:] KEY_CONSIDERED {primary} 0\n"
        f"[GNUPG:] GOODSIG {primary[-16:]} Release Signer <signer@example.invalid>\n"
        f"[GNUPG:] VALIDSIG {signing} 2026-10-28 1793213927 0 4 0 22 10 00 {primary}\n"
        "[GNUPG:] TRUST_ULTIMATE 0 pgp\n"
    )


# Subprocess wall-clock ceiling: local clone + abort, no materialization.
INSTALL_TIMEOUT_SECONDS = 120

# Permission bits for the stub programs the scripts run (owner rwx, others rx).
EXECUTABLE_MODE = 0o755

# GnuPG 2.4.4 verification results under de_DE.UTF-8, abridged:
# (status lines, stderr). git passes --status-fd=1, so the status lines arrive
# on stdout; they read the same in every locale, while the stderr text is
# translated.
LOCALIZED_GPG_RESULTS = {
    "missing-key": (
        "[GNUPG:] NEWSIG signer@example.invalid\n"
        "[GNUPG:] ERRSIG 984AE72EA84995CA 22 10 00 1791351771 9 "
        "C2CD460ED9DCEF33C51123AE984AE72EA84995CA\n"
        "[GNUPG:] NO_PUBKEY 984AE72EA84995CA\n",
        "gpg: Signatur kann nicht geprüft werden: Kein öffentlicher Schlüssel\n",
    ),
    "bad-signature": (
        "[GNUPG:] NEWSIG signer@example.invalid\n"
        "[GNUPG:] BADSIG 984AE72EA84995CA Fixture Signer <signer@example.invalid>\n",
        'gpg: FALSCHE Signatur von "Fixture Signer <signer@example.invalid>"'
        " [ultimativ]\n",
    ),
}

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "runs the scripts with POSIX sh stubs (gpg.program, python3); skipped "
        "on Windows, where `bash` resolves to the WSL launcher, not git-bash"
    ),
)
requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="install.sh runs under bash; no bash on PATH"
)
requires_pwsh = pytest.mark.skipif(
    _PWSH is None,
    reason="install.ps1 and update.ps1 run under PowerShell 7; no pwsh on PATH",
)


@pytest.fixture(autouse=True)
def _host_git_config_that_must_not_leak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plant host git configuration that derails these tests if it leaks in.

    CI runners carry no such configuration, so without this a regression in
    the hermetic environment would pass there. The global and system files,
    the ``git -c`` and ``GIT_CONFIG_COUNT`` environment channels, and the
    legacy ``GIT_CONFIG`` file override all carry ``gpg.format ssh``, which
    makes the fixture's ``git tag -s`` sign with SSH, and a ``gpg.program``
    that does not exist, which makes ``git verify-tag`` fail before gpg can
    report the absent key. A leaked ``GIT_CONFIG`` also sends the fixture's
    ``git config`` writes to that file instead of the fixture repository.
    """
    missing = (tmp_path / "no-such-signing-program").as_posix()
    hostile = tmp_path / "host-gitconfig"
    hostile.write_text(
        f"[gpg]\n\tformat = ssh\n\tprogram = {missing}\n", encoding="utf-8"
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(hostile))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(hostile))
    monkeypatch.delenv("GIT_CONFIG_NOSYSTEM", raising=False)
    monkeypatch.setenv("GIT_CONFIG", str(hostile))
    monkeypatch.setenv(
        "GIT_CONFIG_PARAMETERS", f"'gpg.format'='ssh' 'gpg.program'='{missing}'"
    )
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "gpg.format")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "ssh")
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "gpg.program")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", missing)


@pytest.fixture(autouse=True)
def _host_python3_that_must_not_be_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Put a host ``python3`` without click, rich, or pip first on PATH.

    CI's ``python3`` carries click and rich, so without this an installer run
    that reached the host's ``python3`` would pass there. This one passes the
    installer's version check but starts the interpreter with ``-S``, which
    leaves out site-packages: a run that reaches it stops at the prerequisite
    check, and it has no pip to install with.
    """
    host_bin = tmp_path / "host-python-bin"
    host_bin.mkdir()
    write_python_shim(host_bin / "python3", "-S")
    monkeypatch.setenv(
        "PATH", f"{host_bin}{os.pathsep}{os.environ.get('PATH', os.defpath)}"
    )


def _git(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    """Run a git command in CWD, without host git config, and return stdout,
    failing loudly. ENV (default ``os.environ``) is the base environment."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=hermetic_git_env(env),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (
        f"git {' '.join(args)} failed (code {result.returncode})\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    return result.stdout


def _make_fixture_repo(root: Path) -> Path:
    """Create a minimal apothem-shaped git repository the installer can clone.

    The verification gate fires right after the source-shape check, so the
    fixture needs only ``src/apothem/`` and ``pyproject.toml`` plus one
    commit to tag.
    """
    fixture = root / "fixture-repo"
    (fixture / "src" / "apothem").mkdir(parents=True)
    (fixture / "src" / "apothem" / "__init__.py").write_text(
        "# SPDX-License-Identifier: MIT\n", encoding="utf-8"
    )
    (fixture / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.0.0"\n', encoding="utf-8"
    )
    _git(["init", "--quiet", "--initial-branch", "main"], cwd=fixture)
    _git(["config", "user.name", "Fixture"], cwd=fixture)
    _git(["config", "user.email", "fixture@example.invalid"], cwd=fixture)
    _git(["config", "commit.gpgsign", "false"], cwd=fixture)
    _git(["config", "tag.gpgSign", "false"], cwd=fixture)
    _git(["add", "-A"], cwd=fixture)
    _git(["commit", "--quiet", "-m", "fixture source"], cwd=fixture)
    return fixture


def _installer_env(tmp_path: Path, fixture: Path, ref: str) -> dict[str, str]:
    """Hermetic environment: isolated HOME, no host git config, this test's
    interpreter as the installer's python3, fixture repo as the clone
    remote."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = hermetic_git_env()
    for key in list(env):
        if key.startswith("APOTHEM_"):
            del env[key]
    env.pop("PYTHONPATH", None)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["APOTHEM_REPO"] = str(fixture)
    env["APOTHEM_REF"] = ref
    env["APOTHEM_HOME"] = str(tmp_path / "apothem-home")
    # The clone path, whatever cosign the host has; the updaters ignore it.
    env["APOTHEM_VERIFY"] = "signature"
    _use_test_python(env, tmp_path / "python-shim")
    return env


def _use_test_python(env: dict[str, str], shim_dir: Path) -> None:
    """Make this test's interpreter the installer's ``python3`` and leave pip
    no package source; skip when that interpreter lacks click or rich.

    The scripts run the first ``python3`` on PATH, so a shim for
    ``sys.executable`` goes first. Should a run still reach pip, it inherits
    no ``PIP_*`` setting, reads no configuration file, and uses no index, so
    the install fails instead of changing an interpreter. The probe repeats
    the scripts' import check with the same interpreter and environment.
    """
    shim_dir.mkdir(exist_ok=True)
    shim = shim_dir / "python3"
    write_python_shim(shim)
    env["PATH"] = f"{shim_dir}{os.pathsep}{env.get('PATH', os.defpath)}"
    for key in [name for name in env if name.startswith("PIP_")]:
        del env[key]
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_NO_INDEX"] = "1"
    probe = subprocess.run(
        [str(shim), "-c", "import click, rich"],
        cwd=str(shim_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if probe.returncode != 0:
        lines = probe.stderr.strip().splitlines()
        cause = lines[-1] if lines else f"exit code {probe.returncode}"
        pytest.skip(
            f"the scripts need click and rich, and {sys.executable} cannot "
            "import them with the installer's isolated HOME and no PYTHONPATH "
            f"({cause}); install the dev dependencies into it"
        )


def _stage_installer(env: dict[str, str], installer: Path = INSTALLER) -> Path:
    """Copy INSTALLER OUTSIDE the repo tree and return the staged path.

    The installer's source-detection walks up from its own directory looking
    for a surrounding apothem checkout; run in place (under scripts/installer/)
    it finds this repo and takes the local-source branch, which skips the clone
    path — the clone + signature gate and the non-clone-home guard both live
    there. Staging the copy under the isolated HOME's parent (the pytest tmp
    dir, outside the repo) makes that walk find nothing, so the installer
    deterministically takes the fetch + clone branch on every host.
    """
    assert installer.is_file(), f"installer missing: {installer}"
    staging = Path(env["HOME"]).parent / "installer-under-test"
    staging.mkdir(parents=True, exist_ok=True)
    installer_copy = staging / installer.name
    shutil.copy2(installer, installer_copy)
    return installer_copy


def _run_installer(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    installer_copy = _stage_installer(env)
    return subprocess.run(
        ["bash", str(installer_copy), "--yes"],
        cwd=str(installer_copy.parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
    )


def _run_installer_ps1(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run install.ps1 the way ``_run_installer`` runs install.sh.

    ``-Yes`` mirrors install.sh's ``--yes``. Like ``--yes``, it auto-confirms
    a pip install of a missing click or rich, so the shim and pip lockout
    from ``_installer_env`` matter here as much as for install.sh.
    """
    installer_copy = _stage_installer(env, INSTALLER_PS1)
    assert _PWSH is not None
    return subprocess.run(
        [
            _PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(installer_copy),
            "-Yes",
        ],
        cwd=str(installer_copy.parent),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
        check=False,
    )


def _prepare_update(env: dict[str, str]) -> None:
    """Give an updater what a prior install leaves behind.

    The updaters re-check-out an existing clone at APOTHEM_HOME, so this
    clones the fixture there.
    """
    _git(
        ["clone", "--quiet", env["APOTHEM_REPO"], env["APOTHEM_HOME"]],
        cwd=Path(env["HOME"]),
    )


def _run_updater_sh(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    _prepare_update(env)
    return subprocess.run(
        ["sh", str(UPDATER_SH)],
        cwd=env["HOME"],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
        check=False,
    )


def _run_updater_ps1(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    _prepare_update(env)
    assert _PWSH is not None
    return subprocess.run(
        [
            _PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(UPDATER_PS1),
        ],
        cwd=env["HOME"],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
        check=False,
    )


@pytest.fixture(
    params=[
        pytest.param(_run_installer, id="install.sh", marks=requires_bash),
        pytest.param(_run_installer_ps1, id="install.ps1", marks=requires_pwsh),
        pytest.param(_run_updater_sh, id="update.sh"),
        pytest.param(_run_updater_ps1, id="update.ps1", marks=requires_pwsh),
    ]
)
def run_gate(request: pytest.FixtureRequest) -> GateRunner:
    """Each script whose verification gate the abort-class tests exercise."""
    runner: GateRunner = request.param
    return runner


def _plain(output: str) -> str:
    """Return script output as single-spaced words, as a reader sees them.

    ``install.ps1`` and ``update.ps1`` abort through ``Write-Error``.
    PowerShell renders the record in its concise error view, which can colour
    the text and wrap it at the console width behind a ``|`` gutter, so a
    marker can span lines.
    """
    words = _ANSI_ESCAPE.sub("", output).split()
    return " ".join(word for word in words if word != "|")


def _make_stub_signed_tag(fixture: Path, tag: str) -> None:
    """Point TAG at a tag object that carries an OpenPGP signature block.

    The block is never checked: the installer's git hands it to the stub
    verifier, which replays a canned GnuPG result. No key or gpg is needed.
    """
    commit = _git(["rev-parse", "HEAD"], cwd=fixture).strip()
    tag_file = fixture.parent / f"{tag}.tag"
    tag_file.write_text(
        f"object {commit}\n"
        "type commit\n"
        f"tag {tag}\n"
        "tagger Fixture <fixture@example.invalid> 1700000000 +0000\n"
        "\n"
        "signed release\n"
        "-----BEGIN PGP SIGNATURE-----\n"
        "\n"
        "c3R1Yg==\n"
        "-----END PGP SIGNATURE-----\n",
        encoding="utf-8",
    )
    tag_sha = _git(["hash-object", "-t", "tag", "-w", str(tag_file)], cwd=fixture)
    _git(["update-ref", f"refs/tags/{tag}", tag_sha.strip()], cwd=fixture)


def _use_stub_gpg(
    env: dict[str, str], status: str, human: str, exit_code: int = 1
) -> None:
    """Make the installer's git verify signatures with a stub gpg program.

    The stub drains the payload git writes to its stdin, prints STATUS on
    stdout (git's --status-fd=1) and HUMAN on stderr, and exits EXIT_CODE:
    1 by default, as gpg does when a signature does not verify, 0 for a good
    one. It is set as gpg.program in the isolated HOME's global git config.
    """
    stub_dir = Path(env["HOME"]).parent / "stub-gpg"
    stub_dir.mkdir()
    (stub_dir / "status.txt").write_text(status, encoding="utf-8")
    (stub_dir / "human.txt").write_text(human, encoding="utf-8")
    stub = stub_dir / "gpg"
    stub.write_text(
        "#!/bin/sh\n"
        "cat >/dev/null\n"
        f"cat {shlex.quote(str(stub_dir / 'status.txt'))}\n"
        f"cat {shlex.quote(str(stub_dir / 'human.txt'))} >&2\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    stub.chmod(EXECUTABLE_MODE)
    gitconfig = Path(env["HOME"]) / ".gitconfig"
    _git(
        ["config", "--file", str(gitconfig), "gpg.program", str(stub)],
        cwd=stub_dir,
    )
    env["GIT_CONFIG_GLOBAL"] = str(gitconfig)


def _assert_aborted_before_materialization(env: dict[str, str]) -> None:
    materialized = Path(env["HOME"]) / ".claude" / "settings.json"
    assert not materialized.exists(), (
        f"config materialized despite verification abort: {materialized}"
    )


def test_unsigned_tag_aborts_without_advertising_override(
    tmp_path: Path, run_gate: GateRunner
) -> None:
    """An unsigned annotated tag hits the hard bad-signature abort.

    The abort names possible tampering, prints no key-import guidance (the
    key is not the problem), and does not advertise the
    APOTHEM_ALLOW_UNVERIFIED override on a tamper signal.
    """
    fixture = _make_fixture_repo(tmp_path)
    _git(["tag", "-a", "v9.9.9", "-m", "unsigned release"], cwd=fixture)
    env = _installer_env(tmp_path, fixture, "v9.9.9")

    result = run_gate(env)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, f"script should abort\n{combined}"
    assert BAD_SIGNATURE_MARKER in plain, combined
    assert MISSING_KEY_MARKER not in plain, combined
    assert KEY_IMPORT_MARKER not in plain, combined
    assert OVERRIDE_SUGGESTION not in plain, combined
    _assert_aborted_before_materialization(env)


def test_signed_tag_with_absent_key_prints_import_guidance(
    tmp_path: Path, run_gate: GateRunner
) -> None:
    """A signed tag verified in a keyring lacking the key prints key-import
    guidance — a different abort than the bad-signature case."""
    if shutil.which("gpg") is None:
        pytest.skip("gpg unavailable; cannot create a signed fixture tag")

    fixture = _make_fixture_repo(tmp_path)

    # Ephemeral signing key in an isolated keyring.
    signer_gnupghome = tmp_path / "gnupg-signer"
    signer_gnupghome.mkdir(mode=0o700)
    gpg_env = dict(os.environ)
    gpg_env["GNUPGHOME"] = str(signer_gnupghome)
    keygen = subprocess.run(
        [
            "gpg",
            "--batch",
            "--pinentry-mode",
            "loopback",
            "--passphrase",
            "",
            "--quick-generate-key",
            "Fixture Signer <signer@example.invalid>",
            "ed25519",
            "sign",
            "never",
        ],
        env=gpg_env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if keygen.returncode != 0:
        pytest.skip(f"gpg key generation unavailable: {keygen.stderr.strip()}")

    # Pin the OpenPGP format and the gpg binary that generated the key. A host
    # whose git config signs with SSH (gpg.format=ssh) or routes signing
    # through another program would otherwise leave an SSH signature here,
    # which the installer reports as a bad signature, not a missing key.
    _git(
        [
            "-c",
            "gpg.format=openpgp",
            "-c",
            "gpg.program=gpg",
            "-c",
            "user.signingkey=signer@example.invalid",
            "-c",
            "tag.gpgSign=true",
            "tag",
            "-s",
            "v9.9.8",
            "-m",
            "signed release",
        ],
        cwd=fixture,
        env=gpg_env,
    )
    tag_object = _git(["cat-file", "tag", "v9.9.8"], cwd=fixture)
    assert "-----BEGIN PGP SIGNATURE-----" in tag_object, (
        f"fixture tag is not OpenPGP-signed\n{tag_object}"
    )

    # Verify against a keyring that lacks the signer's public key.
    empty_gnupghome = tmp_path / "gnupg-empty"
    empty_gnupghome.mkdir(mode=0o700)
    env = _installer_env(tmp_path, fixture, "v9.9.8")
    env["GNUPGHOME"] = str(empty_gnupghome)

    result = run_gate(env)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, f"script should abort\n{combined}"
    assert MISSING_KEY_MARKER in plain, combined
    assert KEY_IMPORT_MARKER in plain, combined
    assert BAD_SIGNATURE_MARKER not in plain, combined
    assert OVERRIDE_SUGGESTION not in plain, combined
    _assert_aborted_before_materialization(env)


@pytest.mark.parametrize(
    ("gpg_result", "expected", "unexpected"),
    [
        pytest.param(
            "missing-key",
            (MISSING_KEY_MARKER, KEY_IMPORT_MARKER),
            (BAD_SIGNATURE_MARKER,),
            id="missing-key",
        ),
        pytest.param(
            "bad-signature",
            (BAD_SIGNATURE_MARKER,),
            (MISSING_KEY_MARKER, KEY_IMPORT_MARKER),
            id="bad-signature",
        ),
    ],
)
def test_abort_class_does_not_depend_on_gpg_language(
    tmp_path: Path,
    run_gate: GateRunner,
    gpg_result: str,
    expected: tuple[str, ...],
    unexpected: tuple[str, ...],
) -> None:
    """GnuPG translates its messages, so a missing key reads "Kein
    öffentlicher Schlüssel" under a German locale. The script must still
    tell a missing key from a bad signature, so it reads the status lines,
    which GnuPG does not translate."""
    fixture = _make_fixture_repo(tmp_path)
    _make_stub_signed_tag(fixture, "v9.9.7")
    env = _installer_env(tmp_path, fixture, "v9.9.7")
    status, human = LOCALIZED_GPG_RESULTS[gpg_result]
    _use_stub_gpg(env, status, human)

    result = run_gate(env)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, f"script should abort\n{combined}"
    for marker in expected:
        assert marker in plain, combined
    for marker in unexpected:
        assert marker not in plain, combined
    assert OVERRIDE_SUGGESTION not in plain, combined
    _assert_aborted_before_materialization(env)


def _make_signed_tag_with_ephemeral_key(
    tmp_path: Path, fixture: Path, tag: str
) -> Path:
    """Sign TAG in FIXTURE with a fresh ed25519 key; return its GNUPGHOME.

    Skips when gpg is missing or cannot generate a key. The returned keyring
    holds the signer's key, so ``git verify-tag`` run against it reports a
    good signature from a key that is not the maintainer's.
    """
    if shutil.which("gpg") is None:
        pytest.skip("gpg unavailable; cannot create a signed fixture tag")
    signer_gnupghome = tmp_path / "gnupg-signer"
    signer_gnupghome.mkdir(mode=0o700)
    gpg_env = dict(os.environ)
    gpg_env["GNUPGHOME"] = str(signer_gnupghome)
    keygen = subprocess.run(
        [
            "gpg",
            "--batch",
            "--pinentry-mode",
            "loopback",
            "--passphrase",
            "",
            "--quick-generate-key",
            "Fixture Signer <signer@example.invalid>",
            "ed25519",
            "sign",
            "never",
        ],
        env=gpg_env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if keygen.returncode != 0:
        pytest.skip(f"gpg key generation unavailable: {keygen.stderr.strip()}")
    _git(
        [
            "-c",
            "gpg.format=openpgp",
            "-c",
            "gpg.program=gpg",
            "-c",
            "user.signingkey=signer@example.invalid",
            "-c",
            "tag.gpgSign=true",
            "tag",
            "-s",
            tag,
            "-m",
            "signed release",
        ],
        cwd=fixture,
        env=gpg_env,
    )
    return signer_gnupghome


def test_valid_signature_from_another_key_aborts(
    tmp_path: Path, run_gate: GateRunner
) -> None:
    """A tag that verifies against the local keyring, but was signed by a key
    other than the maintainer's, aborts before anything materializes.

    This is the case key pinning exists for: ``git verify-tag`` succeeds, so
    a script that trusted its exit code alone would install the tag.
    """
    fixture = _make_fixture_repo(tmp_path)
    signer_gnupghome = _make_signed_tag_with_ephemeral_key(tmp_path, fixture, "v9.9.6")
    env = _installer_env(tmp_path, fixture, "v9.9.6")
    env["GNUPGHOME"] = str(signer_gnupghome)

    result = run_gate(env)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, f"script should abort\n{combined}"
    assert OTHER_KEY_MARKER in plain, combined
    assert MAINTAINER_FINGERPRINT in plain, combined
    assert MAINTAINER_OK_MARKER not in plain, combined
    assert OVERRIDE_SUGGESTION not in plain, combined
    _assert_aborted_before_materialization(env)


@pytest.mark.parametrize(
    ("primary", "signing", "accepted"),
    [
        pytest.param(OTHER_FINGERPRINT, None, False, id="other-key"),
        pytest.param(MAINTAINER_FINGERPRINT, None, True, id="maintainer-key"),
        pytest.param(
            MAINTAINER_FINGERPRINT,
            "0123456789ABCDEF0123456789ABCDEF01234567",
            True,
            id="maintainer-subkey",
        ),
        pytest.param(
            MAINTAINER_FINGERPRINT.lower(), None, True, id="lowercase-fingerprint"
        ),
        pytest.param(
            MAINTAINER_FINGERPRINT,
            "two-signatures",
            False,
            id="second-signature-from-another-key",
        ),
        pytest.param(
            OTHER_FINGERPRINT,
            MAINTAINER_FINGERPRINT,
            False,
            id="maintainer-fingerprint-only-as-signing-key",
        ),
    ],
)
def test_key_pin_reads_the_validsig_primary_fingerprint(
    tmp_path: Path,
    run_gate: GateRunner,
    primary: str,
    signing: str | None,
    accepted: bool,
) -> None:
    """The pin compares VALIDSIG's primary-key fingerprint, not the signing
    key's: a maintainer subkey passes, and a signature whose primary key is
    another key fails even when its signing fingerprint reads like the
    maintainer's. A stub gpg replays each good-signature result, so no key
    material is needed.

    An accepted tag passes the gate and stops later, at the fixture's missing
    profile example or profile, so the run still exits non-zero.
    """
    fixture = _make_fixture_repo(tmp_path)
    _make_stub_signed_tag(fixture, "v9.9.5")
    env = _installer_env(tmp_path, fixture, "v9.9.5")
    _use_stub_gpg(env, _good_signature_status(primary, signing), "", exit_code=0)

    result = run_gate(env)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    if accepted:
        assert MAINTAINER_OK_MARKER in plain, combined
        assert OTHER_KEY_MARKER not in plain, combined
    else:
        assert result.returncode != 0, f"script should abort\n{combined}"
        assert OTHER_KEY_MARKER in plain, combined
        assert MAINTAINER_OK_MARKER not in plain, combined
    assert BAD_SIGNATURE_MARKER not in plain, combined
    _assert_aborted_before_materialization(env)


def test_allow_unverified_downgrades_another_key_to_a_warning(
    tmp_path: Path, run_gate: GateRunner
) -> None:
    """APOTHEM_ALLOW_UNVERIFIED=1 is the documented opt-out for every failed
    tag check, the other-key case included; it warns instead of aborting."""
    fixture = _make_fixture_repo(tmp_path)
    _make_stub_signed_tag(fixture, "v9.9.4")
    env = _installer_env(tmp_path, fixture, "v9.9.4")
    env["APOTHEM_ALLOW_UNVERIFIED"] = "1"
    _use_stub_gpg(env, _good_signature_status(OTHER_FINGERPRINT), "", exit_code=0)

    result = run_gate(env)

    plain = _plain(result.stdout + result.stderr)
    assert "or the maintainer key did not make it" in plain, plain
    assert "proceeding because APOTHEM_ALLOW_UNVERIFIED=1" in plain, plain
    assert OTHER_KEY_MARKER not in plain, plain


@requires_bash
def test_existing_nonclone_home_is_refused_without_yes(tmp_path: Path) -> None:
    """A pre-existing non-clone APOTHEM_HOME with content survives.

    The clone path finds a directory without .git — something a previous
    install did not place — and must refuse the destructive replacement
    when --yes is absent.
    """
    fixture = _make_fixture_repo(tmp_path)
    _git(["tag", "-a", "v9.9.9", "-m", "unsigned release"], cwd=fixture)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    apothem_home = Path(env["APOTHEM_HOME"])
    apothem_home.mkdir(parents=True)
    sentinel = apothem_home / "keep.txt"
    sentinel.write_text("not apothem's to delete\n", encoding="utf-8")

    installer_copy = _stage_installer(env)
    result = subprocess.run(
        ["bash", str(installer_copy)],  # deliberately no --yes
        cwd=str(installer_copy.parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0, f"installer should refuse\n{combined}"
    assert NOT_APOTHEM_MARKER in combined, combined
    assert sentinel.is_file(), "sentinel must survive the refused install"
    assert not list(tmp_path.glob("apothem-home.before-apothem-*")), combined


@requires_bash
def test_yes_lets_a_failed_tag_check_leave_the_nonclone_home_alone(
    tmp_path: Path,
) -> None:
    """--yes passes the ownership guard, but the clone is checked in a
    staging directory first: an unsigned tag aborts there, and the existing
    directory is left exactly as it was."""
    fixture = _make_fixture_repo(tmp_path)
    _git(["tag", "-a", "v9.9.9", "-m", "unsigned release"], cwd=fixture)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    apothem_home = Path(env["APOTHEM_HOME"])
    apothem_home.mkdir(parents=True)
    (apothem_home / "keep.txt").write_text("stale\n", encoding="utf-8")

    result = _run_installer(env)  # passes --yes

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined  # unsigned tag aborts at the gate
    assert "holds no Apothem install; it will be moved, unchanged" in combined
    assert BAD_SIGNATURE_MARKER in combined, combined
    assert (apothem_home / "keep.txt").read_text(encoding="utf-8") == "stale\n"
    assert not (apothem_home / ".git").exists(), combined
    assert not list(tmp_path.glob(".apothem-*")), "staging left behind"
    assert not list(tmp_path.glob("apothem-home.before-apothem-*")), combined


@requires_bash
def test_yes_switches_an_archive_install_to_a_clone_and_keeps_engine_data(
    tmp_path: Path,
) -> None:
    """An archive install switched to a clone with --yes keeps the engine's
    rollback backups and install ledgers."""
    fixture = _make_fixture_repo(tmp_path)
    _make_stub_signed_tag(fixture, "v9.9.9")
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)
    apothem_home = Path(env["APOTHEM_HOME"])
    (apothem_home / "src" / "apothem").mkdir(parents=True)
    (apothem_home / "src" / "apothem" / "removed_module.py").write_text(
        "old\n", encoding="utf-8"
    )
    (apothem_home / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (apothem_home / "backups" / "claude-code").mkdir(parents=True)
    (apothem_home / "backups" / "claude-code" / "set.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (apothem_home / "state").mkdir()
    (apothem_home / "state" / "ledger.json").write_text("{}\n", encoding="utf-8")

    result = _run_installer(env)  # passes --yes

    combined = result.stdout + result.stderr
    assert "carries a valid signature from the maintainer key" in combined, combined
    assert (apothem_home / ".git").is_dir(), combined
    assert not (apothem_home / "src" / "apothem" / "removed_module.py").exists()
    assert (apothem_home / "backups" / "claude-code" / "set.json").is_file()
    assert (apothem_home / "state" / "ledger.json").is_file()
    assert not list(tmp_path.glob(".apothem-*")), "staging left behind"


@requires_bash
def test_a_branch_named_like_the_tag_cannot_stand_in_for_it(tmp_path: Path) -> None:
    """The clone checks out refs/tags/<tag>, never a branch of the same name,
    and the tree it verifies is the tag's commit."""
    fixture = _make_fixture_repo(tmp_path)
    _make_stub_signed_tag(fixture, "v9.9.9")
    tagged = _git(["rev-parse", "HEAD"], cwd=fixture).strip()
    _git(["checkout", "--quiet", "-b", "v9.9.9"], cwd=fixture)
    (fixture / "planted.txt").write_text("not in the release\n", encoding="utf-8")
    _git(["add", "planted.txt"], cwd=fixture)
    _git(["commit", "--quiet", "-m", "branch named like the tag"], cwd=fixture)
    _git(["checkout", "--quiet", "main"], cwd=fixture)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)

    result = _run_installer(env)

    combined = result.stdout + result.stderr
    apothem_home = Path(env["APOTHEM_HOME"])
    assert "carries a valid signature from the maintainer key" in combined, combined
    assert not (apothem_home / "planted.txt").exists(), combined
    head = _git(["rev-parse", "HEAD"], cwd=apothem_home).strip()
    assert head == tagged, combined


@pytest.mark.parametrize(
    ("runner", "installer"),
    [
        pytest.param(_run_updater_sh, "install.sh", id="update.sh"),
        pytest.param(
            _run_updater_ps1, "install.ps1", id="update.ps1", marks=requires_pwsh
        ),
    ],
)
def test_updater_sends_an_archive_install_back_to_the_installer(
    tmp_path: Path, runner: GateRunner, installer: str
) -> None:
    """An archive install has no clone to update; the updater says to re-run
    the installer instead of claiming no source was found."""
    fixture = _make_fixture_repo(tmp_path)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    home = Path(env["APOTHEM_HOME"])
    (home / "src" / "apothem").mkdir(parents=True)
    (home / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    plain_runner = {
        _run_updater_sh: UPDATER_SH,
        _run_updater_ps1: UPDATER_PS1,
    }[runner]
    if plain_runner is UPDATER_SH:
        args = ["sh", str(UPDATER_SH)]
    else:
        assert _PWSH is not None
        args = [_PWSH, "-NoProfile", "-NonInteractive", "-File", str(UPDATER_PS1)]
    result = subprocess.run(
        args,
        cwd=env["HOME"],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
        check=False,
    )

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert "was installed from a release archive" in plain, plain
    assert f"Re-run {installer} with cosign and gpg on PATH" in plain, plain


# --- an existing clone: fetch, check the tag, and only then check it out ----

# A file the next fixture release adds, so a checkout of it shows.
NEW_FILE = "new-in-release.txt"


def _advance_fixture(fixture: Path) -> str:
    """Commit what the next release changes to FIXTURE's main (an edit to
    pyproject.toml and a new NEW_FILE); return the new commit."""
    with (fixture / "pyproject.toml").open("a", encoding="utf-8") as handle:
        handle.write("# next release\n")
    (fixture / NEW_FILE).write_text("new\n", encoding="utf-8")
    _git(["add", "-A"], cwd=fixture)
    _git(["commit", "--quiet", "-m", "next release"], cwd=fixture)
    return _head(fixture)


def _head(repo: Path) -> str:
    return _git(["rev-parse", "HEAD"], cwd=repo).strip()


def _clone_home(env: dict[str, str], home: Path | None = None) -> Path:
    """Clone the fixture to HOME (default APOTHEM_HOME), as an earlier
    install left it, and return it."""
    target = home or Path(env["APOTHEM_HOME"])
    _git(["clone", "--quiet", env["APOTHEM_REPO"], str(target)], cwd=Path(env["HOME"]))
    return target


def _worktree(root: Path, *, with_git: bool = False) -> dict[str, bytes | str]:
    """Every entry under ROOT (a file's bytes, or "dir"), leaving out .git
    unless WITH_GIT."""
    entries: dict[str, bytes | str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if not with_git and (rel == ".git" or rel.startswith(".git/")):
            continue
        entries[rel] = "dir" if path.is_dir() else path.read_bytes()
    return entries


def _run_sh(
    env: dict[str, str], script: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    """Run install.sh (staged outside the repository) or update.sh with ARGS
    against whatever is at APOTHEM_HOME already."""
    if script == INSTALLER:
        staged = _stage_installer(env)
        command = ["bash", str(staged), *args]
        cwd = str(staged.parent)
    else:
        command = ["sh", str(script), *args]
        cwd = env["HOME"]
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
        check=False,
    )


def _run_in_place(
    env: dict[str, str], script: Path
) -> subprocess.CompletedProcess[str]:
    """Update the clone at APOTHEM_HOME with SCRIPT (install.sh gets --yes)."""
    return _run_sh(env, script, *(["--yes"] if script == INSTALLER else []))


IN_PLACE_SCRIPTS = [
    pytest.param(INSTALLER, id="install.sh", marks=requires_bash),
    pytest.param(UPDATER_SH, id="update.sh"),
]


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
@pytest.mark.parametrize("kind", ["unsigned", "other-key", "re-pointed"])
def test_an_existing_clone_is_left_at_its_old_head_when_the_new_tag_fails(
    tmp_path: Path, script: Path, kind: str
) -> None:
    """The clone is fetched and the new tag checked before anything is
    checked out, so a tag that fails the check leaves the clone at its old
    commit, with none of the new release's files and nothing changed."""
    fixture = _make_fixture_repo(tmp_path)
    _make_stub_signed_tag(fixture, "v9.9.8")
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    home = _clone_home(env)
    old_head = _head(home)
    before = _worktree(home)
    _advance_fixture(fixture)
    status = _good_signature_status(MAINTAINER_FINGERPRINT)
    if kind == "unsigned":
        _git(["tag", "-a", "v9.9.9", "-m", "unsigned release"], cwd=fixture)
        marker = BAD_SIGNATURE_MARKER
    elif kind == "other-key":
        _make_stub_signed_tag(fixture, "v9.9.9")
        status = _good_signature_status(OTHER_FINGERPRINT)
        marker = OTHER_KEY_MARKER
    else:
        repoint_tag(fixture, "v9.9.8", "v9.9.9")
        marker = REPOINTED_MARKER
    _use_stub_gpg(env, status, "", exit_code=0)

    result = _run_in_place(env, script)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, combined
    assert marker in plain, combined
    assert MAINTAINER_OK_MARKER not in plain, combined
    assert _head(home) == old_head, combined
    assert not (home / NEW_FILE).exists(), combined
    assert _worktree(home) == before, combined
    assert _git(["status", "--porcelain"], cwd=home) == "", combined
    _assert_aborted_before_materialization(env)


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
@pytest.mark.parametrize(
    "change",
    [
        "edited-tracked-file",
        "edit-the-release-does-not-touch",
        "staged-new-file",
        "untracked-file-in-the-way",
    ],
)
def test_local_changes_in_a_clone_stop_the_update_and_are_kept(
    tmp_path: Path, script: Path, change: str
) -> None:
    """A change to a tracked file, staged or not, stops the update after the
    tag check and before the checkout, even one the new release does not
    touch (git checkout would carry it over into the new tree). An untracked
    file the checkout would overwrite stops the checkout itself, which runs
    without --force. Either way the change is still there and the clone is
    at its old commit."""
    fixture = _make_fixture_repo(tmp_path)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    home = _clone_home(env)
    old_head = _head(home)
    _advance_fixture(fixture)
    _make_stub_signed_tag(fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)
    marker = TRACKED_CHANGES_MARKER
    if change == "edited-tracked-file":
        changed = home / "pyproject.toml"
    elif change == "edit-the-release-does-not-touch":
        changed = home / "src" / "apothem" / "__init__.py"
    elif change == "staged-new-file":
        changed = home / "src" / "apothem" / "mine.py"
    else:
        changed = home / NEW_FILE
        marker = LOCAL_CHANGES_MARKER
    changed.write_text("my local change\n", encoding="utf-8")
    if change == "staged-new-file":
        _git(["add", "src/apothem/mine.py"], cwd=home)

    result = _run_in_place(env, script)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, combined
    assert MAINTAINER_OK_MARKER in plain, combined
    assert marker in plain, combined
    if marker == TRACKED_CHANGES_MARKER:
        assert f"{home} {TRACKED_CHANGES_MARKER}" in plain, combined
    assert changed.read_text(encoding="utf-8") == "my local change\n", combined
    assert _head(home) == old_head, combined
    _assert_aborted_before_materialization(env)


@requires_bash
@pytest.mark.parametrize("allow_unverified", ["0", "1"])
def test_a_repointed_signed_tag_is_refused_on_the_clone_path(
    tmp_path: Path, allow_unverified: str
) -> None:
    """refs/tags/v9.9.9 points at a maintainer-signed tag object that names
    itself v9.9.8. The signature is good, but the tag is another release's,
    so the fresh clone is refused before it is checked out or placed, and
    APOTHEM_ALLOW_UNVERIFIED=1 does not change that."""
    fixture = _make_fixture_repo(tmp_path)
    _make_stub_signed_tag(fixture, "v9.9.8")
    _advance_fixture(fixture)
    repoint_tag(fixture, "v9.9.8", "v9.9.9")
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    env["APOTHEM_ALLOW_UNVERIFIED"] = allow_unverified
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)

    result = _run_installer(env)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, combined
    assert "the signed tag object is not the v9.9.9 release tag" in plain, combined
    assert REPOINTED_MARKER in plain, combined
    assert MAINTAINER_OK_MARKER not in plain, combined
    assert not Path(env["APOTHEM_HOME"]).exists(), combined
    assert not list(tmp_path.glob(".apothem-*")), "staging left behind"
    _assert_aborted_before_materialization(env)


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
@pytest.mark.parametrize("branch", ["v9.9.9", "refs/tags/v9.9.9"])
def test_an_update_checks_out_the_tag_not_a_branch_of_the_same_name(
    tmp_path: Path, script: Path, branch: str
) -> None:
    """An existing clone with a local branch named like the tag, or named
    literally refs/tags/<tag>, is checked out at the tag's commit: HEAD is
    the tag's commit, detached, and the branch's planted file is not in the
    tree."""
    fixture = _make_fixture_repo(tmp_path)
    _make_stub_signed_tag(fixture, "v9.9.9")
    tagged = _head(fixture)
    _git(["checkout", "--quiet", "-b", "v9.9.9"], cwd=fixture)
    (fixture / "planted.txt").write_text("not in the release\n", encoding="utf-8")
    _git(["add", "planted.txt"], cwd=fixture)
    _git(["commit", "--quiet", "-m", "branch named like the tag"], cwd=fixture)
    _git(["checkout", "--quiet", "main"], cwd=fixture)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)
    home = _clone_home(env)
    _git(["branch", "--quiet", branch, "refs/remotes/origin/v9.9.9"], cwd=home)

    result = _run_in_place(env, script)

    combined = result.stdout + result.stderr
    assert MAINTAINER_OK_MARKER in _plain(combined), combined
    assert _head(home) == tagged, combined
    assert not (home / "planted.txt").exists(), combined
    symbolic = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "HEAD"],
        cwd=str(home),
        env=hermetic_git_env(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert symbolic.returncode != 0, f"HEAD is on a branch: {symbolic.stdout}"


def _wrap_git(env: dict[str, str], after_checkout: str) -> None:
    """Put a git wrapper first on the scripts' PATH that runs the real git
    and, after a checkout succeeds, runs AFTER_CHECKOUT (sh, with $real
    naming the real git). The clone's own hooks no longer run during an
    update, so this stands in for a hook that changes the checkout."""
    real = shutil.which("git", path=env["PATH"])
    assert real is not None
    wrap_dir = Path(env["HOME"]).parent / "git-wrapper"
    wrap_dir.mkdir()
    wrapper = wrap_dir / "git"
    wrapper.write_text(
        "#!/bin/sh\n"
        f"real={shlex.quote(real)}\n"
        '"$real" "$@"\n'
        "rc=$?\n"
        'case " $* " in *" checkout "*) [ "$rc" = 0 ] && {\n'
        f"{after_checkout}\n"
        "} ;; esac\n"
        'exit "$rc"\n',
        encoding="utf-8",
    )
    wrapper.chmod(EXECUTABLE_MODE)
    env["PATH"] = f"{wrap_dir}{os.pathsep}{env['PATH']}"


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
@pytest.mark.parametrize("drift", ["head-moved", "tracked-file-changed"])
def test_a_checkout_that_does_not_land_on_the_ref_aborts(
    tmp_path: Path, script: Path, drift: str
) -> None:
    """After the checkout, HEAD must be the tag's commit and the tracked
    files must match it. A git that moves HEAD elsewhere, or changes a
    tracked file, after the checkout makes the scripts abort before anything
    materializes."""
    fixture = _make_fixture_repo(tmp_path)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    home = _clone_home(env)
    old_head = _head(home)
    new_head = _advance_fixture(fixture)
    _make_stub_signed_tag(fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)
    if drift == "head-moved":
        action = (
            f'"$real" -C {shlex.quote(str(home))} update-ref --no-deref HEAD {old_head}'
        )
        marker = f"is at '{old_head}', not at the v9.9.9 tag's commit '{new_head}'"
    else:
        action = f"printf 'planted\\n' >> {shlex.quote(str(home / 'pyproject.toml'))}"
        marker = (
            f"The checkout in {home} does not match v9.9.9 after the update. "
            "Aborting before re-materialization."
        )
    _wrap_git(env, action)

    result = _run_in_place(env, script)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, combined
    assert marker in plain, combined
    _assert_aborted_before_materialization(env)


@requires_bash
def test_a_dry_run_leaves_an_existing_clone_unchanged(tmp_path: Path) -> None:
    """The dry run clones and checks the new tag in a scratch directory, so
    the clone at APOTHEM_HOME, its .git included, is left as it was."""
    fixture = _make_fixture_repo(tmp_path)
    _make_stub_signed_tag(fixture, "v9.9.8")
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    home = _clone_home(env)
    before = _worktree(home, with_git=True)
    _advance_fixture(fixture)
    _make_stub_signed_tag(fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)

    result = _run_sh(env, INSTALLER, "--dry-run", "--yes")

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert MAINTAINER_OK_MARKER in plain, combined
    assert "dry run, so" in plain, combined
    assert _worktree(home, with_git=True) == before, combined
    assert not (home / NEW_FILE).exists(), combined
    assert not list(tmp_path.glob(".apothem-*")), "staging left behind"


def _seed_archive_install(home: Path) -> None:
    (home / "src" / "apothem").mkdir(parents=True)
    (home / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (home / "state").mkdir()
    (home / "state" / "ledger.json").write_text("{}\n", encoding="utf-8")


@requires_bash
@pytest.mark.parametrize(
    ("layout", "marker"),
    [
        pytest.param("other-content", NOT_APOTHEM_MARKER, id="other-content"),
        pytest.param("archive-install", ARCHIVE_REFUSED_MARKER, id="archive-install"),
    ],
)
def test_a_dry_run_on_the_clone_path_refuses_what_the_real_run_refuses(
    tmp_path: Path, layout: str, marker: str
) -> None:
    """Without --yes, the dry run stops where the real run would, before
    anything is cloned, and APOTHEM_HOME is left alone."""
    fixture = _make_fixture_repo(tmp_path)
    _make_stub_signed_tag(fixture, "v9.9.9")
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)
    home = Path(env["APOTHEM_HOME"])
    if layout == "archive-install":
        _seed_archive_install(home)
    else:
        home.mkdir()
        (home / "keep.txt").write_text("mine\n", encoding="utf-8")
    before = _worktree(home, with_git=True)

    for args in ((), ("--dry-run",)):
        result = _run_sh(env, INSTALLER, *args)
        combined = result.stdout + result.stderr
        plain = _plain(combined)
        assert result.returncode != 0, combined
        assert marker in plain, combined
        assert MAINTAINER_OK_MARKER not in plain, combined
        assert _worktree(home, with_git=True) == before, combined
        assert not list(tmp_path.glob(".apothem-*")), "staging left behind"


@requires_bash
@pytest.mark.parametrize("dry_run", [False, True], ids=["install", "dry-run"])
def test_a_symlinked_home_is_refused_on_the_clone_path(
    tmp_path: Path, dry_run: bool
) -> None:
    """A clone would be swapped in by renaming, which would replace the link
    itself, so a symbolic link at APOTHEM_HOME is refused even with --yes,
    before anything is cloned."""
    fixture = _make_fixture_repo(tmp_path)
    _make_stub_signed_tag(fixture, "v9.9.9")
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)
    real = tmp_path / "real-home"
    _seed_archive_install(real)
    home = Path(env["APOTHEM_HOME"])
    home.symlink_to(real, target_is_directory=True)
    before = _worktree(real)

    args = ("--dry-run", "--yes") if dry_run else ("--yes",)
    result = _run_sh(env, INSTALLER, *args)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, combined
    assert f"Destination {home} {LINK_MARKER}" in plain, combined
    assert MAINTAINER_OK_MARKER not in plain, combined
    assert home.is_symlink(), combined
    assert _worktree(real) == before, combined
    assert not list(tmp_path.glob(".apothem-*")), "staging left behind"


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
def test_a_clone_reached_through_a_symlink_is_updated_in_place(
    tmp_path: Path, script: Path
) -> None:
    """An in-place update renames nothing, so a link to a clone is fine: the
    clone behind it moves to the new tag and the link stays a link."""
    fixture = _make_fixture_repo(tmp_path)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    real = _clone_home(env, tmp_path / "real-clone")
    home = Path(env["APOTHEM_HOME"])
    home.symlink_to(real, target_is_directory=True)
    new_head = _advance_fixture(fixture)
    _make_stub_signed_tag(fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)

    result = _run_in_place(env, script)

    combined = result.stdout + result.stderr
    assert MAINTAINER_OK_MARKER in _plain(combined), combined
    assert LINK_MARKER not in _plain(combined), combined
    assert home.is_symlink(), combined
    assert _head(real) == new_head, combined
    assert (real / NEW_FILE).is_file(), combined


@pytest.mark.parametrize(
    "runner",
    [
        pytest.param(_run_installer, id="install.sh", marks=requires_bash),
        pytest.param(_run_updater_sh, id="update.sh"),
    ],
)
@pytest.mark.parametrize("key", ["gpg.program", "gpg.openpgp.program"])
def test_gpg_format_ssh_does_not_skip_the_gpg_check(
    tmp_path: Path, runner: GateRunner, key: str
) -> None:
    """Release tags carry OpenPGP signatures whatever gpg.format says, so a
    user's gpg.format=ssh does not skip the check that gpg is there: a
    missing gpg is named as such, not reported as a bad signature. git runs
    gpg.openpgp.program ahead of gpg.program, and so does the check."""
    fixture = _make_fixture_repo(tmp_path)
    _make_stub_signed_tag(fixture, "v9.9.9")
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    gitconfig = Path(env["HOME"]) / ".gitconfig"
    missing = (tmp_path / "no-such-gpg").as_posix()
    if key == "gpg.program":
        config = f"[gpg]\n\tformat = ssh\n\tprogram = {missing}\n"
    else:
        present = shutil.which("true")
        assert present is not None
        config = (
            f"[gpg]\n\tformat = ssh\n\tprogram = {present}\n"
            f'[gpg "openpgp"]\n\tprogram = {missing}\n'
        )
    gitconfig.write_text(config, encoding="utf-8")
    env["GIT_CONFIG_GLOBAL"] = str(gitconfig)

    result = runner(env)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, combined
    assert GPG_MISSING_MARKER in plain, combined
    assert BAD_SIGNATURE_MARKER not in plain, combined
    _assert_aborted_before_materialization(env)


@requires_bash
def test_a_non_release_ref_with_allow_unverified_is_cloned(tmp_path: Path) -> None:
    """APOTHEM_REF=main with APOTHEM_ALLOW_UNVERIFIED=1 warns and checks the
    branch out in the fresh clone."""
    fixture = _make_fixture_repo(tmp_path)
    tip = _advance_fixture(fixture)
    env = _installer_env(tmp_path, fixture, "main")
    env["APOTHEM_ALLOW_UNVERIFIED"] = "1"

    result = _run_installer(env)

    combined = result.stdout + result.stderr
    home = Path(env["APOTHEM_HOME"])
    assert NOT_RELEASE_WARNING in _plain(combined), combined
    assert _head(home) == tip, combined
    assert (home / NEW_FILE).is_file(), combined
    assert (home / "src" / "apothem" / "__init__.py").is_file(), combined
    assert _git(["status", "--porcelain"], cwd=home) == "", combined


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
@pytest.mark.parametrize(
    "ref_kind",
    [
        "commit",
        "remote-only-branch",
        "main",
    ],
)
def test_a_non_release_ref_with_allow_unverified_updates_a_clone(
    tmp_path: Path, script: Path, ref_kind: str
) -> None:
    """With APOTHEM_ALLOW_UNVERIFIED=1, a ref that is not a release tag (a
    commit, a branch the clone has not seen, or main) is fetched and checked
    out in the existing clone: HEAD ends at what origin has for it."""
    fixture = _make_fixture_repo(tmp_path)
    env = _installer_env(tmp_path, fixture, "main")
    home = _clone_home(env)
    tip = _advance_fixture(fixture)
    if ref_kind == "commit":
        env["APOTHEM_REF"] = tip
    elif ref_kind == "remote-only-branch":
        _git(["branch", "feature"], cwd=fixture)
        env["APOTHEM_REF"] = "feature"
    env["APOTHEM_ALLOW_UNVERIFIED"] = "1"

    result = _run_in_place(env, script)

    combined = result.stdout + result.stderr
    assert NOT_RELEASE_WARNING in _plain(combined), combined
    assert _head(home) == tip, combined
    assert (home / NEW_FILE).is_file(), combined


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
def test_a_ref_that_reads_as_an_option_is_not_passed_to_git_as_one(
    tmp_path: Path, script: Path
) -> None:
    """--end-of-options keeps a ref such as ``--orphan=planted`` from being
    read by git checkout as an option: the checkout fails as an unknown ref,
    and the clone keeps its branch and commit."""
    fixture = _make_fixture_repo(tmp_path)
    env = _installer_env(tmp_path, fixture, "--orphan=planted")
    env["APOTHEM_ALLOW_UNVERIFIED"] = "1"
    home = _clone_home(env)
    old_head = _head(home)

    result = _run_in_place(env, script)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, combined
    assert "Could not check out --orphan=planted" in plain, combined
    assert _head(home) == old_head, combined
    branch = _git(["symbolic-ref", "--short", "HEAD"], cwd=home).strip()
    assert branch == "main", combined
    assert "planted" not in _git(["branch", "--list"], cwd=home), combined
    _assert_aborted_before_materialization(env)


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
def test_a_tracked_change_stops_a_non_release_update_too(
    tmp_path: Path, script: Path
) -> None:
    """With APOTHEM_ALLOW_UNVERIFIED=1 and a branch ref, a change to a tracked
    file still stops the update before the checkout."""
    fixture = _make_fixture_repo(tmp_path)
    env = _installer_env(tmp_path, fixture, "main")
    env["APOTHEM_ALLOW_UNVERIFIED"] = "1"
    home = _clone_home(env)
    old_head = _head(home)
    _advance_fixture(fixture)
    changed = home / "src" / "apothem" / "__init__.py"
    changed.write_text("my local change\n", encoding="utf-8")

    result = _run_in_place(env, script)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, combined
    assert f"{home} {TRACKED_CHANGES_MARKER}" in plain, combined
    assert changed.read_text(encoding="utf-8") == "my local change\n", combined
    assert _head(home) == old_head, combined
    _assert_aborted_before_materialization(env)


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
def test_a_clone_whose_git_is_a_file_is_updated_in_place(
    tmp_path: Path, script: Path
) -> None:
    """A clone made with --separate-git-dir has a .git file, not a folder;
    it is still a clone, so it is fetched, checked and checked out in place
    rather than treated as an unknown folder."""
    fixture = _make_fixture_repo(tmp_path)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    home = Path(env["APOTHEM_HOME"])
    _git(
        [
            "clone",
            "--quiet",
            "--separate-git-dir",
            str(tmp_path / "sep.git"),
            env["APOTHEM_REPO"],
            str(home),
        ],
        cwd=Path(env["HOME"]),
    )
    assert (home / ".git").is_file()
    new_head = _advance_fixture(fixture)
    _make_stub_signed_tag(fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)

    result = _run_in_place(env, script)

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert MAINTAINER_OK_MARKER in plain, combined
    assert NOT_APOTHEM_MARKER not in plain, combined
    assert _head(home) == new_head, combined
    assert (home / NEW_FILE).is_file(), combined
    assert (home / ".git").is_file(), combined
    assert not list(tmp_path.glob("apothem-home.before-apothem-*")), combined


def _tag_a_tree(fixture: Path, tag: str) -> None:
    """Point refs/tags/TAG at a signed-looking tag object that names itself
    TAG but tags a tree instead of a commit."""
    tree = _git(["rev-parse", "HEAD^{tree}"], cwd=fixture).strip()
    tag_file = fixture.parent / f"{tag}-tree.tag"
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
    )
    tag_sha = _git(["hash-object", "-t", "tag", "-w", str(tag_file)], cwd=fixture)
    _git(["update-ref", f"refs/tags/{tag}", tag_sha.strip()], cwd=fixture)


@pytest.mark.parametrize(
    "script",
    [
        pytest.param("fresh-install.sh", id="fresh-install.sh", marks=requires_bash),
        *IN_PLACE_SCRIPTS,
    ],
)
def test_a_signed_tag_of_a_tree_is_refused(tmp_path: Path, script: Path | str) -> None:
    """A maintainer-signed tag object that names the release but tags a tree,
    not a commit, is refused before anything is checked out, on a fresh
    clone and on an existing one."""
    fixture = _make_fixture_repo(tmp_path)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)
    if script == "fresh-install.sh":
        _tag_a_tree(fixture, "v9.9.9")
        result = _run_installer(env)
        home = Path(env["APOTHEM_HOME"])
        assert not home.exists(), result.stdout + result.stderr
    else:
        assert isinstance(script, Path)
        home = _clone_home(env)
        old_head = _head(home)
        _advance_fixture(fixture)
        _tag_a_tree(fixture, "v9.9.9")
        result = _run_in_place(env, script)
        assert _head(home) == old_head, result.stdout + result.stderr
        assert not (home / NEW_FILE).exists(), result.stdout + result.stderr

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, combined
    assert REPOINTED_MARKER in plain, combined
    assert MAINTAINER_OK_MARKER not in plain, combined
    assert not list(tmp_path.glob(".apothem-*")), "staging left behind"
    _assert_aborted_before_materialization(env)


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
def test_an_apothem_repo_that_reads_as_an_option_is_refused(
    tmp_path: Path, script: Path
) -> None:
    fixture = _make_fixture_repo(tmp_path)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    planted = tmp_path / "planted"
    env["APOTHEM_REPO"] = f"--upload-pack=touch {planted}"

    result = _run_sh(env, script)

    plain = _plain(result.stdout + result.stderr)
    assert result.returncode != 0, plain
    assert (
        "APOTHEM_REPO must be a repository URL or path, not an option: "
        f"--upload-pack=touch {planted}"
    ) in plain, plain
    assert not planted.exists(), plain


# --- an existing clone that is not safe to update in place --------------------

NOT_WORK_TREE_MARKER = (
    "is not the work tree of its git clone (core.worktree is set, or its .git "
    "points elsewhere). Remove that setting, then re-run."
)


def _assert_refused_before_fetch(
    result: subprocess.CompletedProcess[str],
    home: Path,
    old_head: str,
    marker: str,
    env: dict[str, str],
) -> None:
    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, combined
    assert marker in plain, combined
    assert MAINTAINER_OK_MARKER not in plain, combined
    assert _head(home) == old_head, combined
    fetched = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "refs/tags/v9.9.9"],
        cwd=str(home),
        env=hermetic_git_env(),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert fetched.returncode != 0, "the clone was fetched before the check"
    _assert_aborted_before_materialization(env)


def _clone_with_a_new_tag(tmp_path: Path) -> tuple[dict[str, str], Path, str]:
    """A clone at APOTHEM_HOME and a newer, maintainer-signed v9.9.9 at its
    origin that the clone has not fetched yet."""
    fixture = _make_fixture_repo(tmp_path)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    home = _clone_home(env)
    old_head = _head(home)
    _advance_fixture(fixture)
    _make_stub_signed_tag(fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)
    return env, home, old_head


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_a_change_hidden_from_git_stops_the_update(
    tmp_path: Path, script: Path, flag: str
) -> None:
    """A file marked assume-unchanged or skip-worktree hides its changes
    from git diff, so the update refuses such a clone, before the fetch."""
    env, home, old_head = _clone_with_a_new_tag(tmp_path)
    _git(["update-index", flag, "src/apothem/__init__.py"], cwd=home)
    (home / "src" / "apothem" / "__init__.py").write_text(
        "my hidden change\n", encoding="utf-8"
    )

    result = _run_in_place(env, script)

    _assert_refused_before_fetch(
        result, home, old_head, f"{home} {TRACKED_CHANGES_MARKER}", env
    )
    assert (home / "src" / "apothem" / "__init__.py").read_text(
        encoding="utf-8"
    ) == "my hidden change\n"


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
def test_a_clone_whose_work_tree_is_elsewhere_is_refused(
    tmp_path: Path, script: Path
) -> None:
    """core.worktree makes git check out into another folder; the update
    refuses the clone before the fetch."""
    env, home, old_head = _clone_with_a_new_tag(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _git(["config", "core.worktree", str(elsewhere)], cwd=home)

    result = _run_in_place(env, script)

    _assert_refused_before_fetch(
        result, home, old_head, f"{home} {NOT_WORK_TREE_MARKER}", env
    )
    assert list(elsewhere.iterdir()) == []


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
@pytest.mark.parametrize(
    ("key", "printed"),
    [
        ("core.hooksPath", "core.hookspath"),
        ("core.fsmonitor", "core.fsmonitor"),
        ("gpg.program", "gpg.program"),
        ("gpg.openpgp.program", "gpg.openpgp.program"),
        ("include.path", "include.path"),
        ("includeIf.gitdir:/nowhere/.path", "includeif.gitdir:/nowhere/.path"),
    ],
)
def test_a_clone_whose_own_config_runs_programs_is_refused(
    tmp_path: Path, script: Path, key: str, printed: str
) -> None:
    """A clone's own .git/config could name a program for git to run, or pull
    in other configuration, and the update would trust it. Such a clone is
    refused before the fetch, naming the key as git prints it."""
    env, home, old_head = _clone_with_a_new_tag(tmp_path)
    _git(["config", key, str(tmp_path / "planted")], cwd=home)

    result = _run_in_place(env, script)

    _assert_refused_before_fetch(
        result,
        home,
        old_head,
        f"{home}'s own git config sets {printed}, which the update would trust. "
        f"Remove it from {home}/.git/config, then re-run.",
        env,
    )
    assert not (tmp_path / "planted").exists()


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
def test_the_clones_hooks_do_not_run_during_an_update(
    tmp_path: Path, script: Path
) -> None:
    """Every git command on the clone runs with core.hooksPath pointing at an
    empty folder: the update reaches the new tag and none of the clone's
    hooks (fetch, checkout or ref-update hooks) runs."""
    env, home, _ = _clone_with_a_new_tag(tmp_path)
    new_head = _head(Path(env["APOTHEM_REPO"]))
    ran = tmp_path / "hook-ran"
    for name in ("post-checkout", "reference-transaction", "post-merge"):
        hook = home / ".git" / "hooks" / name
        hook.write_text(f"#!/bin/sh\necho {name} >> '{ran}'\n", encoding="utf-8")
        hook.chmod(EXECUTABLE_MODE)

    result = _run_in_place(env, script)

    combined = result.stdout + result.stderr
    assert MAINTAINER_OK_MARKER in _plain(combined), combined
    assert _head(home) == new_head, combined
    assert not ran.exists(), ran.read_text(encoding="utf-8")


@pytest.mark.parametrize("script", IN_PLACE_SCRIPTS)
def test_a_clone_of_something_else_is_not_updated(tmp_path: Path, script: Path) -> None:
    """A git clone that holds no Apothem source is not treated as an Apothem
    clone: neither script fetches or checks it out, and it is left as it
    was (install.sh, given --yes, moves it aside whole instead)."""
    fixture = _make_fixture_repo(tmp_path)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    other = tmp_path / "other-repo"
    other.mkdir()
    (other / "notes.txt").write_text("mine\n", encoding="utf-8")
    _git(["init", "--quiet", "--initial-branch", "main"], cwd=other)
    _git(["add", "-A"], cwd=other)
    _git(
        [
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "not apothem",
        ],
        cwd=other,
    )
    home = Path(env["APOTHEM_HOME"])
    _git(["clone", "--quiet", str(other), str(home)], cwd=tmp_path)
    old_head = _head(home)
    _make_stub_signed_tag(fixture, "v9.9.9")
    _use_stub_gpg(env, _good_signature_status(MAINTAINER_FINGERPRINT), "", 0)

    if script == INSTALLER:
        result = _run_sh(env, script)  # no --yes
        marker = NOT_APOTHEM_MARKER
    else:
        result = _run_sh(env, script)
        marker = "No source found at"

    combined = result.stdout + result.stderr
    plain = _plain(combined)
    assert result.returncode != 0, combined
    assert marker in plain, combined
    assert "Updating existing clone" not in plain, combined
    assert "Updating clone at" not in plain, combined
    assert _head(home) == old_head, combined
    assert (home / "notes.txt").read_text(encoding="utf-8") == "mine\n"
