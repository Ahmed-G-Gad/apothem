# SPDX-License-Identifier: MIT

"""Installer tag-verification abort branches (clone path).

Exercises the fail-closed signature gate in ``scripts/installer/install.sh``
against a local fixture repository — no network. The gate distinguishes two
abort classes:

- **missing key** — the tag is signed but the maintainer public key is absent
  from the local keyring; the abort prints key-import guidance (fingerprint
  lookup in SECURITY.md plus ``gpg --recv-keys``).
- **bad / absent signature** — an unsigned or tampered tag; the abort is hard
  and deliberately does not advertise the ``APOTHEM_ALLOW_UNVERIFIED``
  override on a possible-tampering signal.

Both tests assert the abort happens before any configuration materializes.
The fixture repository is minimal: the gate runs right after the
``is_apothem_source`` shape check (``src/apothem`` + ``pyproject.toml``), so
no working engine tree is required.

Every git subprocess, fixture and installer alike, runs with the host's
global and system git config switched off, and each test also runs under a
hostile global config, so the outcome does not depend on the host's git setup.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "installer" / "install.sh"

# Message markers mirrored from install.sh's verification gate.
BAD_SIGNATURE_MARKER = "did not verify (possible tampering)"
MISSING_KEY_MARKER = "public key is not in the local keyring"
KEY_IMPORT_MARKER = "gpg --recv-keys"
OVERRIDE_SUGGESTION = "Set APOTHEM_ALLOW_UNVERIFIED=1"

# Subprocess wall-clock ceiling: local clone + abort, no materialization.
INSTALL_TIMEOUT_SECONDS = 120

# Host git config the module's git subprocesses must not inherit. A global
# gpg.format=ssh makes `git tag -s` SSH-sign the fixture tag, so verify-tag
# reports a missing allowed-signers file instead of gpg's missing key. A global
# core.hooksPath pre-commit hook can block the fixture commit. Setting
# GIT_CONFIG_GLOBAL skips both ~/.gitconfig and $XDG_CONFIG_HOME/git/config,
# and GIT_CONFIG_NOSYSTEM skips the system file.
GIT_CONFIG_ISOLATION = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or sys.platform == "win32",
    reason=(
        "exercises the POSIX install.sh; skipped on Windows (install.ps1 is "
        "the Windows path, and `bash` there resolves to the WSL launcher, "
        "not git-bash) and when bash is absent from PATH"
    ),
)


def _git(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    """Run a git command in CWD, without the host's global or system git
    config, and return stdout, failing loudly."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env={**(os.environ if env is None else env), **GIT_CONFIG_ISOLATION},
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
    """Hermetic environment: isolated HOME and git config, fixture repo as the
    clone remote.

    The isolated HOME hides ~/.gitconfig, but an inherited GIT_CONFIG_GLOBAL,
    $XDG_CONFIG_HOME/git/config, and the system config would still reach the
    installer's git (its verify-tag reads gpg.program from them), so the git
    config isolation applies here too.
    """
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("APOTHEM_"):
            del env[key]
    env.pop("PYTHONPATH", None)
    env.update(GIT_CONFIG_ISOLATION)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["APOTHEM_REPO"] = str(fixture)
    env["APOTHEM_REF"] = ref
    env["APOTHEM_HOME"] = str(tmp_path / "apothem-home")
    return env


def _stage_installer(env: dict[str, str]) -> Path:
    """Copy install.sh OUTSIDE the repo tree and return the staged path.

    The installer's source-detection walks up from its own directory looking
    for a surrounding apothem checkout; run in place (under scripts/installer/)
    it finds this repo and takes the local-source branch, which skips the clone
    path — the clone + signature gate and the non-clone-home guard both live
    there. Staging the copy under the isolated HOME's parent (the pytest tmp
    dir, outside the repo) makes that walk find nothing, so the installer
    deterministically takes the fetch + clone branch on every host.
    """
    assert INSTALLER.is_file(), f"installer missing: {INSTALLER}"
    staging = Path(env["HOME"]).parent / "installer-under-test"
    staging.mkdir(parents=True, exist_ok=True)
    installer_copy = staging / "install.sh"
    shutil.copy2(INSTALLER, installer_copy)
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


def _assert_aborted_before_materialization(env: dict[str, str]) -> None:
    materialized = Path(env["HOME"]) / ".claude" / "settings.json"
    assert not materialized.exists(), (
        f"config materialized despite verification abort: {materialized}"
    )


@pytest.fixture(autouse=True, params=["host-config", "hostile-global-config"])
def _host_git_config(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run each test under the host's git config and under a hostile one.

    CI runners carry no global git config, so the hostile run is what
    exercises GIT_CONFIG_ISOLATION and the signing pins there. It points
    GIT_CONFIG_GLOBAL at a config that SSH-signs through a missing program,
    names a missing gpg binary, and blocks every commit with a global
    pre-commit hook, and it injects gpg.format=ssh at command scope through
    GIT_CONFIG_COUNT. A leak into any fixture or installer git call fails the
    test.
    """
    if request.param == "host-config":
        return
    hooks = tmp_path / "hostile-hooks"
    hooks.mkdir()
    pre_commit = hooks / "pre-commit"
    pre_commit.write_text(
        "#!/bin/sh\necho 'hostile global pre-commit hook ran' >&2\nexit 1\n",
        encoding="utf-8",
    )
    pre_commit.chmod(0o755)
    missing = tmp_path / "missing-program"
    hostile = tmp_path / "hostile-gitconfig"
    hostile.write_text(
        f"[gpg]\n\tformat = ssh\n\tprogram = {missing}\n"
        f'[gpg "ssh"]\n\tprogram = {missing}\n'
        "[commit]\n\tgpgsign = true\n"
        f"[core]\n\thooksPath = {hooks}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(hostile))
    index = int(os.environ.get("GIT_CONFIG_COUNT") or "0")
    monkeypatch.setenv(f"GIT_CONFIG_KEY_{index}", "gpg.format")
    monkeypatch.setenv(f"GIT_CONFIG_VALUE_{index}", "ssh")
    monkeypatch.setenv("GIT_CONFIG_COUNT", str(index + 1))


def test_unsigned_tag_aborts_without_advertising_override(tmp_path: Path) -> None:
    """An unsigned annotated tag hits the hard bad-signature abort.

    The abort names possible tampering, prints no key-import guidance (the
    key is not the problem), and does not advertise the
    APOTHEM_ALLOW_UNVERIFIED override on a tamper signal.
    """
    fixture = _make_fixture_repo(tmp_path)
    _git(["tag", "-a", "v9.9.9", "-m", "unsigned release"], cwd=fixture)
    env = _installer_env(tmp_path, fixture, "v9.9.9")

    result = _run_installer(env)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, f"installer should abort\n{combined}"
    assert BAD_SIGNATURE_MARKER in combined, combined
    assert MISSING_KEY_MARKER not in combined, combined
    assert KEY_IMPORT_MARKER not in combined, combined
    assert OVERRIDE_SUGGESTION not in combined, combined
    _assert_aborted_before_materialization(env)


def test_signed_tag_with_absent_key_prints_import_guidance(tmp_path: Path) -> None:
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

    # Pin the OpenPGP backend and the gpg binary that minted the key. Config
    # injected through GIT_CONFIG_COUNT or GIT_CONFIG_PARAMETERS is command
    # scope, which GIT_CONFIG_ISOLATION does not reach, and only `-c` overrides
    # it. An SSH-signed tag would never hit the missing-key branch.
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

    # Verify against a keyring that lacks the signer's public key.
    empty_gnupghome = tmp_path / "gnupg-empty"
    empty_gnupghome.mkdir(mode=0o700)
    env = _installer_env(tmp_path, fixture, "v9.9.8")
    env["GNUPGHOME"] = str(empty_gnupghome)

    result = _run_installer(env)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, f"installer should abort\n{combined}"
    assert MISSING_KEY_MARKER in combined, combined
    assert KEY_IMPORT_MARKER in combined, combined
    assert BAD_SIGNATURE_MARKER not in combined, combined
    assert OVERRIDE_SUGGESTION not in combined, combined
    _assert_aborted_before_materialization(env)


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
