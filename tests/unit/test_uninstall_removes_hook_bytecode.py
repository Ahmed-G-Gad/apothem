# SPDX-License-Identifier: MIT

"""Uninstall removes the bytecode Python compiled from the modules Apothem wrote.

A hook or statusline module Apothem installed leaves
``__pycache__/<module>.<tag>.pyc`` beside it once Python has run it. When the
uninstall removes the module, it removes that bytecode too (any interpreter
tag, any optimisation level), then the ``__pycache__`` folder if nothing else
is left in it. Any other file in ``__pycache__`` is the operator's and stays.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem import cli
from apothem.harnesses._shared import install_driver
from apothem.harnesses.claude_code import ClaudeCodeAdapter


@pytest.fixture
def claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the user home and the backup root into *tmp_path*; return ``~/.claude``."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    return home / ".claude"


def _uninstall() -> tuple[int, dict]:  # type: ignore[type-arg]
    result = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--format", "json"]
    )
    return result.exit_code, json.loads(result.output)


def _plant(folder: Path, *names: str) -> list[Path]:
    cache = folder / "__pycache__"
    cache.mkdir(exist_ok=True)
    planted = [cache / name for name in names]
    for path in planted:
        path.write_bytes(b"bytecode")
    return planted


def test_the_bytecode_of_removed_modules_goes_and_the_users_stays(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    hooks = claude / ".apothem" / "support" / "hooks"
    statuslines = claude / "statuslines"
    assert (hooks / "askuserquestion_validator.py").is_file()
    assert (statuslines / "render.py").is_file()
    own = _plant(
        hooks,
        "askuserquestion_validator.cpython-314.pyc",
        "askuserquestion_validator.cpython-310.opt-1.pyc",
        "askuserquestion_validator.pypy310.opt-2.pyc",
    )
    users = _plant(
        hooks,
        "my_own_module.cpython-314.pyc",
        "askuserquestion_validator_mine.cpython-314.pyc",
        "askuserquestion_validator.cpython-314.pyc.bak",
    )
    only_own = _plant(statuslines, "render.cpython-314.pyc", "render.cpython-313.pyc")

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert not (hooks / "askuserquestion_validator.py").exists()
    assert [path for path in own if path.exists()] == []
    assert all(path.read_bytes() == b"bytecode" for path in users)
    assert (hooks / "__pycache__").is_dir()
    assert [path for path in only_own if path.exists()] == []
    assert not (statuslines / "__pycache__").exists()


def test_bytecode_of_a_module_the_uninstall_keeps_stays(claude: Path) -> None:
    ClaudeCodeAdapter().install({})
    hooks = claude / ".apothem" / "support" / "hooks"
    module = hooks / "askuserquestion_validator.py"
    module.write_text("# my own edit\n", encoding="utf-8")
    kept = _plant(hooks, "askuserquestion_validator.cpython-314.pyc")

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert module.read_text(encoding="utf-8") == "# my own edit\n"
    assert all(path.is_file() for path in kept)
