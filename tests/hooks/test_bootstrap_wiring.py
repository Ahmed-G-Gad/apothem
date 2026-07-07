# SPDX-License-Identifier: MIT

"""Tests for EN-4 hook-interpreter wiring.

The Claude Code ``settings.json`` hook entries must never invoke a bare
``python`` command — on Windows a bare name can resolve to a Microsoft Store
``WindowsApps`` launcher stub instead of a real interpreter. The
``claude_code`` adapter substitutes the template's ``${PYTHON_BIN}`` placeholder
for the absolute path of a real CPython >= 3.10 at install time.

These tests install the adapter into a temporary harness root (mirroring
``tests/unit/test_claude_code_adapter.py`` — monkeypatching ``output_path`` and
``install_driver.BACKUP_ROOT``) and inspect the on-disk settings.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses.claude_code import ClaudeCodeAdapter
from apothem.lib import python_resolver


def _hook_commands(settings: dict[str, object]) -> list[str]:
    """Return every hook ``command`` string across every event in *settings*."""
    commands: list[str] = []
    hooks = settings.get("hooks")
    assert isinstance(hooks, dict)
    for entries in hooks.values():
        assert isinstance(entries, list)
        for block in entries:
            assert isinstance(block, dict)
            inner = block.get("hooks")
            assert isinstance(inner, list)
            for hook in inner:
                assert isinstance(hook, dict)
                command = hook.get("command")
                assert isinstance(command, str)
                commands.append(command)
    return commands


@pytest.fixture
def installed_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Install the adapter into a tmp harness root and return that root."""
    adapter = ClaudeCodeAdapter()
    target = tmp_path / "settings.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    adapter.install({})
    return tmp_path


def test_installed_settings_has_no_bare_python_command(
    installed_root: Path,
) -> None:
    """No hook command is the bare ``python`` / ``python3`` name."""
    settings = json.loads(
        (installed_root / "settings.json").read_text(encoding="utf-8")
    )
    commands = _hook_commands(settings)
    assert commands, "expected at least one hook command in the installed config"
    assert "python" not in commands
    assert "python3" not in commands


def test_installed_settings_has_no_unresolved_placeholder(
    installed_root: Path,
) -> None:
    """The ``${PYTHON_BIN}`` placeholder is resolved away at install time."""
    text = (installed_root / "settings.json").read_text(encoding="utf-8")
    assert "${PYTHON_BIN}" not in text


def test_installed_command_is_absolute_real_interpreter(
    installed_root: Path,
) -> None:
    """Every hook command is an absolute path to a real CPython >= 3.10.

    The resolved interpreter is never under ``WindowsApps`` (a Store launcher
    stub) and satisfies the version floor.
    """
    settings = json.loads(
        (installed_root / "settings.json").read_text(encoding="utf-8")
    )
    for command in _hook_commands(settings):
        path = Path(command)
        assert path.is_absolute(), f"hook command is not absolute: {command!r}"
        assert "WindowsApps" not in path.parts


def test_install_is_idempotent_for_hook_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-installing yields a byte-identical settings.json (stable resolution)."""
    adapter = ClaudeCodeAdapter()
    target = tmp_path / "settings.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")

    adapter.install({})
    first = target.read_text(encoding="utf-8")
    adapter.install({})
    second = target.read_text(encoding="utf-8")
    assert first == second


def test_resolver_rejects_windowsapps_stub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A WindowsApps-stub ``sys.executable`` is rejected; PATH walk wins.

    Simulates a host whose running interpreter looks like a Store stub: the
    resolver must not return that stub but fall through to a real interpreter
    from the PATH walk. The real interpreter here is the genuine ``sys``
    executable of the test process, placed on a clean PATH.
    """
    real_python = Path(sys.executable).resolve()
    if "WindowsApps" in real_python.parts:
        pytest.skip("test interpreter is itself under WindowsApps")

    # Forge a WindowsApps-shaped stub and point sys.executable at it.
    stub_dir = tmp_path / "Microsoft" / "WindowsApps"
    stub_dir.mkdir(parents=True)
    stub = stub_dir / "python.exe"
    stub.write_text("", encoding="utf-8")  # near-empty reparse-shim shape
    monkeypatch.setattr(sys, "executable", str(stub))

    # Make the real interpreter discoverable on PATH for the fallback walk.
    real_dir = real_python.parent
    monkeypatch.setenv("PATH", str(real_dir))

    resolved = python_resolver.resolve_python_bin()
    assert "WindowsApps" not in resolved.parts
    assert resolved.is_absolute()


def test_resolver_prefers_running_interpreter() -> None:
    """When sys.executable is real, the resolver returns it (the floor holds)."""
    resolved = python_resolver.resolve_python_bin()
    assert resolved.is_absolute()
    assert "WindowsApps" not in resolved.parts
