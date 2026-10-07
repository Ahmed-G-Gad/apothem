# SPDX-License-Identifier: MIT

"""Release-tag verification abort branches (clone path).

Exercises the fail-closed signature gate in ``scripts/installer/install.sh``,
``install.ps1``, ``update.sh`` and ``update.ps1`` against a local fixture
repository — no network. The gate distinguishes two abort classes:

- **missing key** — the tag is signed but the maintainer public key is absent
  from the local keyring; the abort prints key-import guidance (fingerprint
  lookup in SECURITY.md plus ``gpg --recv-keys``).
- **bad / absent signature** — an unsigned or tampered tag; the abort is hard
  and deliberately does not advertise the ``APOTHEM_ALLOW_UNVERIFIED``
  override on a possible-tampering signal.

Each abort-class test runs every script against the same fixture, so the
four keep the same classes and messages. Every test asserts the abort happens
before any configuration materializes.
A stub verifier replays GnuPG's German output for both classes, to show the
split rests on GnuPG's status lines rather than its translated messages.
The fixture repository is minimal: the gate runs right after the source-shape
check (``src/apothem`` + ``pyproject.toml``), so no working engine tree is
required.

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
KEY_IMPORT_MARKER = "gpg --recv-keys"
OVERRIDE_SUGGESTION = "Set APOTHEM_ALLOW_UNVERIFIED=1"

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


def _use_stub_gpg(env: dict[str, str], status: str, human: str) -> None:
    """Make the installer's git verify signatures with a stub gpg program.

    The stub drains the payload git writes to its stdin, prints STATUS on
    stdout (git's --status-fd=1) and HUMAN on stderr, and exits 1, as gpg
    does when a signature does not verify. It is set as gpg.program in the
    isolated HOME's global git config.
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
        "exit 1\n",
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
    assert "refusing to delete" in combined, combined
    assert sentinel.is_file(), "sentinel must survive the refused install"


@requires_bash
def test_yes_authorizes_replacing_nonclone_home(tmp_path: Path) -> None:
    """--yes authorizes the replacement: the non-clone directory gives way
    to the clone (this run still aborts later, at the verification gate,
    which is fine — the guard under test sits before the clone)."""
    fixture = _make_fixture_repo(tmp_path)
    _git(["tag", "-a", "v9.9.9", "-m", "unsigned release"], cwd=fixture)
    env = _installer_env(tmp_path, fixture, "v9.9.9")
    apothem_home = Path(env["APOTHEM_HOME"])
    apothem_home.mkdir(parents=True)
    (apothem_home / "keep.txt").write_text("stale\n", encoding="utf-8")

    result = _run_installer(env)  # passes --yes

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined  # unsigned tag aborts at the gate
    assert not (apothem_home / "keep.txt").exists(), combined
    assert (apothem_home / ".git").is_dir(), combined
