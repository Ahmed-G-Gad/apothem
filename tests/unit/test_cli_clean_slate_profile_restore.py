# SPDX-License-Identifier: MIT

"""The clean-slate profile restore is the identity safety net.

``install --clean`` reads the shared profile into memory, lets the clean-slate
sweep remove the prior install state (the profile file is one of its bounded
targets), then writes those bytes back. At that moment the in-memory copy and
the timestamped backup are the only copies of the operator's identity source of
truth that exist.

The restore therefore gets the same handling as every other write in the engine:
the atomic writer, so an interruption mid-write cannot leave a truncated
profile at the canonical path, and an ``OSError`` boundary, so a read-only
directory or a full disk surfaces as the standard operator-facing envelope
naming the backup rather than as a traceback over an empty path.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver

# `from apothem.cli import _materialize` binds the re-exported *function* of
# that name, not the module, so patch the module fetched by import_module.
_materialize = importlib.import_module("apothem.cli._materialize")

_PROFILE = (
    "identity:\n"
    "  name: Ada Lovelace\n"
    "  email: ada@analytical.engine\n"
    "  github: adalovelace\n"
    "seriousness: PERSONAL_USE\n"
)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate HOME so the clean-slate sweep never touches real state."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows HOME resolution
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    return home


@pytest.fixture
def profile(tmp_path: Path) -> Path:
    """A real profile file for the run to capture and restore."""
    path = tmp_path / "profile.yaml"
    # Bytes, not write_text: on Windows the text path translates \n to \r\n,
    # and the restore is a byte-for-byte round-trip this test asserts exactly.
    path.write_bytes(_PROFILE.encode("utf-8"))
    return path


def _install_clean(runner: CliRunner, profile: Path, *extra: str) -> object:
    return runner.invoke(
        main,
        [
            "install",
            "--harness",
            "claude-code",
            "--profile",
            str(profile),
            "--clean",
            "--yes",
            *extra,
        ],
    )


def test_restore_goes_through_the_atomic_writer(
    runner: CliRunner, home: Path, profile: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The restore writes through ``write_bytes_atomically``, not a raw write.

    A raw ``Path.write_bytes`` truncates the target before it writes, so an
    interruption leaves an empty profile where the operator's identity was.
    """
    seen: list[tuple[Path, bytes]] = []
    real = _materialize.write_bytes_atomically

    def _record(path: Path, data: bytes) -> None:
        seen.append((path, data))
        real(path, data)

    monkeypatch.setattr(_materialize, "write_bytes_atomically", _record)

    result = _install_clean(runner, profile)

    assert result.exit_code == 0, result.output
    assert (profile, _PROFILE.encode("utf-8")) in seen
    assert profile.read_text(encoding="utf-8") == _PROFILE


def test_restore_failure_emits_the_operator_envelope(
    runner: CliRunner, home: Path, profile: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed restore reports the backup as the recovery source.

    Without the boundary the operator sees a traceback at the moment their
    profile is gone from its canonical path, with nothing pointing at the
    backup that still holds it.
    """

    def _fail(path: Path, data: bytes) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(_materialize, "write_bytes_atomically", _fail)

    result = _install_clean(runner, profile, "--format", "json")

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    error = payload["error"]
    assert error["code"] == "clean_slate.profile_restore_failed"
    assert "No space left on device" in error["reason"]
    assert "backup" in error["fix"].lower()


def test_restore_failure_stops_the_run(
    runner: CliRunner, home: Path, profile: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed restore aborts rather than materializing over a lost profile.

    Continuing would write a fresh harness facade while the profile that
    facade is supposed to express no longer exists on disk.
    """

    def _fail(path: Path, data: bytes) -> None:
        raise PermissionError("read-only")

    monkeypatch.setattr(_materialize, "write_bytes_atomically", _fail)

    result = _install_clean(runner, profile)

    assert result.exit_code == 1, result.output
    assert not (home / ".claude" / "settings.json").exists()
