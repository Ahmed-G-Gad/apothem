# SPDX-License-Identifier: MIT

"""An uninstall that cannot finish says so, and says what to do.

A file Apothem wrote alone that another program holds open cannot be
deleted: the step is an error, so the uninstall is unfinished and keeps the
install recorded for the next run. A rules file saved in another encoding
than UTF-8 reaches the step that says how to fix it, instead of a decoding
error before anything is looked at.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from apothem.cli import main
from apothem.cli._cmd_uninstall import _quoted
from apothem.harnesses._shared.install_driver_backup import _guarded_unlink


def _cli(*args: str) -> Result:
    return CliRunner().invoke(main, list(args))


def _install(project: Path, tmp_path: Path) -> None:
    profile = tmp_path / "prof" / "profile.yaml"
    made = _cli("profile", "init", "--profile", str(profile))
    assert made.exit_code == 0, made.output
    installed = _cli(
        "install",
        "--harness",
        "cursor",
        "--project",
        str(project),
        "--profile",
        str(profile),
        "--yes",
    )
    assert installed.exit_code == 0, installed.output


def test_an_apothem_only_file_that_cannot_be_deleted_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "apothem-rules.mdc"
    target.write_text("x", encoding="utf-8")

    def unlink(self: Path, missing_ok: bool = False) -> None:
        raise PermissionError(13, "The file is in use")

    monkeypatch.setattr(Path, "unlink", unlink)

    result = _guarded_unlink(
        target, allowed_root=tmp_path, operation="surgical_uninstall"
    )

    assert result.outcome == "error"
    assert f"could not remove {target}, an Apothem-only file" in result.message
    assert "run the uninstall again" in result.message


def test_an_apothem_only_file_already_gone_is_not_counted_removed(
    tmp_path: Path,
) -> None:
    result = _guarded_unlink(
        tmp_path / "gone.mdc", allowed_root=tmp_path, operation="surgical_uninstall"
    )

    assert result.outcome == "unchanged"


def test_a_rules_file_that_is_not_utf8_gets_the_fix_not_a_decoding_error(
    tmp_path: Path,
) -> None:
    project = tmp_path / "X"
    project.mkdir()
    _install(project, tmp_path)
    rules = project / ".cursor" / "rules" / "apothem-rules.mdc"
    rules.write_bytes(rules.read_bytes() + b"\nnotes in cp1252: caf\xe9\n")

    result = _cli(
        "uninstall", "--harness", "cursor", "--project", str(project), "--yes"
    )

    text = " ".join(result.output.split())
    assert result.exit_code == 2, result.output
    assert "codec" not in text, text
    assert "not UTF-8 text" in text
    assert "Save it as UTF-8" in text
    assert rules.exists()


@pytest.mark.parametrize("name", ["my proj", "a&b", "x(1)", "it's", "a$b", "a;b"])
def test_a_folder_a_shell_would_split_is_quoted(name: str) -> None:
    # The no-record message prints commands to paste; a folder name with a
    # character a shell treats specially is quoted, so the command still works.
    folder = Path("work") / name

    quoted = _quoted(folder)

    if sys.platform == "win32":
        assert quoted == f'"{folder}"'
    else:
        assert shlex.split(quoted) == [str(folder)]
    assert _quoted(Path("work") / "proj") == str(Path("work") / "proj")
