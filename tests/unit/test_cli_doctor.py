# SPDX-License-Identifier: MIT

"""``doctor`` judges installed harnesses only, verifies them, and probes hooks.

doctor used to exit 1 unless all 17 harnesses were installed, and it only
checked presence. A user with one healthy harness
always got a failure, so doctor could not gate a setup step, while a broken
hook runtime passed unnoticed. Now an uninstalled harness is informational;
an installed one must verify, and every hook command it registered must start
with a no-op payload.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

import apothem
from apothem.cli import _cmd_doctor, _doctor_hook_text, _doctor_hooks, main
from apothem.harnesses._shared import install_driver, wrapper_factories
from apothem.lib import install_ledger
from apothem.lib.propagation import load_manifest

_PROFILE = (
    "schema_version: 1\nidentity:\n  name: Ada Lovelace\n"
    "  email: ada@analytical.engine\n  github: adalovelace\n"
)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.chdir(tmp_path)
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text(_PROFILE, encoding="utf-8")
    return home


def _doctor(runner: CliRunner, *options: str) -> tuple[int, dict]:
    result = runner.invoke(main, ["doctor", "--json", *options])
    return result.exit_code, json.loads(result.stdout)


def _install(runner: CliRunner, harness: str, *options: str) -> None:
    result = runner.invoke(main, ["install", "--harness", harness, "--json", *options])
    assert result.exit_code == 0, result.output


def _row(payload: dict, name: str) -> dict:
    return next(row for row in payload["harnesses"] if row["name"] == name)


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project


def test_doctor_passes_with_nothing_installed(runner: CliRunner, home: Path) -> None:
    code, payload = _doctor(runner)
    assert code == 0, payload
    assert payload["all_ok"] is True
    statuses = {row["status"] for row in payload["harnesses"]}
    # Project-scope harnesses are only judged when --project names a root.
    assert statuses == {"not_installed", "needs_project"}


def test_doctor_passes_after_a_single_harness_install(
    runner: CliRunner, home: Path
) -> None:
    _install(runner, "codex")
    code, payload = _doctor(runner)
    assert code == 0, payload
    assert payload["all_ok"] is True
    codex = _row(payload, "codex")
    assert codex["status"] == "ok"
    assert codex["verified"] is True
    assert codex["hooks"]["probed"] >= 1
    assert codex["hooks"]["failed"] == []
    assert _row(payload, "opencode")["status"] == "not_installed"


def test_doctor_fails_when_a_registered_hook_cannot_start(
    runner: CliRunner, home: Path
) -> None:
    _install(runner, "codex")
    dispatcher = home / ".codex" / "hooks" / "dispatch.py"
    assert dispatcher.is_file()
    dispatcher.write_text("raise SystemExit(3)\n", encoding="utf-8")

    code, payload = _doctor(runner)

    assert code == 1, payload
    assert payload["all_ok"] is False
    failed = [check for check in payload["checks"] if check["status"] == "fail"]
    assert [check["code"] for check in failed] == ["hook.start_failed"]
    assert failed[0]["harness"] == "codex"
    assert "dispatch.py" in failed[0]["message"]
    assert failed[0]["fix"]


def test_doctor_checks_the_hooks_of_the_root_it_examines(
    runner: CliRunner, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A newer install at a since-deleted ``CODEX_HOME`` does not stand in."""
    _install(runner, "codex")
    elsewhere = tmp_path / "codex-elsewhere"
    monkeypatch.setenv("CODEX_HOME", str(elsewhere))
    _install(runner, "codex")
    monkeypatch.delenv("CODEX_HOME")
    shutil.rmtree(elsewhere)
    dispatcher = home / ".codex" / "hooks" / "dispatch.py"
    dispatcher.write_text("raise SystemExit(3)\n", encoding="utf-8")

    code, payload = _doctor(runner)

    assert code == 1, payload
    codex = _row(payload, "codex")
    assert codex["status"] == "hook_failed"
    assert codex["hooks"]["probed"] >= 1
    assert "dispatch.py" in codex["hooks"]["failed"][0]["command"]


def test_doctor_checks_the_hooks_of_the_project_it_is_given(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    """A newer install in a since-deleted project does not stand in."""
    first, second = tmp_path / "first", tmp_path / "second"
    for project in (first, second):
        project.mkdir()
        result = runner.invoke(
            main,
            ["install", "--harness", "cursor", "--project", str(project), "--yes"],
        )
        assert result.exit_code == 0, result.output
    shutil.rmtree(second)
    # Healthy first: the hook command (with PowerShell's "&" on Windows) starts.
    result = runner.invoke(main, ["doctor", "--json", "--project", str(first)])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0, payload
    assert _row(payload, "cursor")["hooks"] == {"probed": 1, "failed": []}
    dispatcher = first / ".apothem" / "support" / "cursor" / "hooks" / "dispatch.py"
    assert dispatcher.is_file()
    # A changed project dispatcher is never started; a removed one cannot start.
    dispatcher.unlink()

    result = runner.invoke(main, ["doctor", "--json", "--project", str(first)])

    payload = json.loads(result.stdout)
    assert result.exit_code == 1, payload
    cursor = _row(payload, "cursor")
    assert cursor["status"] == "hook_failed"
    assert cursor["hooks"]["probed"] >= 1
    command = os.path.normcase(cursor["hooks"]["failed"][0]["command"])
    [failure] = [c for c in payload["checks"] if c["code"] == "hook.start_failed"]
    assert "to put the hook scripts back" in failure["fix"]
    assert os.path.normcase(str(first / ".apothem")) in command
    assert os.path.normcase(str(second)) not in command


def test_doctor_reports_the_hook_check_not_run_for_a_root_with_no_record(
    runner: CliRunner, home: Path
) -> None:
    _install(runner, "codex")
    # The only record now names another root (an install of an earlier spelling).
    ledger = install_ledger.ledger_path("codex")
    text = ledger.read_text(encoding="utf-8")
    ledger.write_text(
        text.replace(json.dumps(str(home / ".codex"))[1:-1], "elsewhere"),
        encoding="utf-8",
    )

    code, payload = _doctor(runner)

    codex = _row(payload, "codex")
    assert codex["status"] == "ok", payload
    assert codex["hooks"] is None
    unchecked = [c for c in payload["checks"] if c["code"] == "hook.unchecked"]
    assert [c["harness"] for c in unchecked] == ["codex"]
    assert "--project" not in unchecked[0]["fix"]
    assert code == 0
    # The plain report says so too, rather than leaving the Hooks cell blank.
    plain = runner.invoke(main, ["doctor"])
    assert plain.exit_code == 0, plain.output
    assert "not checked" in plain.output
    assert "no install record for" in plain.output
    # The last line says what was not checked rather than that all passed.
    flat = " ".join(plain.output.split())
    assert "All checks passed" not in flat
    assert "the hook commands of codex were not checked" in flat


def test_doctor_finds_the_install_under_another_spelling_of_its_folder(
    runner: CliRunner, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``CODEX_HOME`` spelled another way still names the folder installed to."""
    codex_home = tmp_path / "cx"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    _install(runner, "codex")
    (codex_home / "hooks" / "dispatch.py").write_text(
        "raise SystemExit(3)\n", encoding="utf-8"
    )
    (tmp_path / "step").mkdir()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "step" / ".." / "cx"))

    code, payload = _doctor(runner)

    assert code == 1, payload
    codex = _row(payload, "codex")
    assert codex["status"] == "hook_failed"
    assert not [c for c in payload["checks"] if c["code"] == "hook.unchecked"]


def test_doctor_finds_the_install_under_another_letter_case_of_its_folder(
    runner: CliRunner, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On a case-insensitive file system, ``CODEX_HOME`` may change its case."""
    codex_home = tmp_path / "cx"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    _install(runner, "codex")
    if not (tmp_path / "CX").is_dir():
        pytest.skip("this file system tells letter cases apart")
    (codex_home / "hooks" / "dispatch.py").write_text(
        "raise SystemExit(3)\n", encoding="utf-8"
    )
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "CX"))

    code, payload = _doctor(runner)

    assert code == 1, payload
    assert _row(payload, "codex")["status"] == "hook_failed"
    assert not [c for c in payload["checks"] if c["code"] == "hook.unchecked"]


def test_a_spelling_in_another_letter_case_is_matched_by_file_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where the OS does not fold case (macOS), the file ID joins the spellings.

    ``same_location`` is made to answer no, as it does on macOS, so this runs
    the file-ID branch on every case-insensitive file system.
    """
    (tmp_path / "cx").mkdir()
    (tmp_path / "other").mkdir()
    if not (tmp_path / "CX").is_dir():
        pytest.skip("this file system tells letter cases apart")
    monkeypatch.setattr(_doctor_hooks, "same_location", lambda left, right: False)

    assert _doctor_hooks._same_folder(str(tmp_path / "cx"), tmp_path / "CX")
    assert not _doctor_hooks._same_folder(str(tmp_path / "cx"), tmp_path / "other")


def test_two_folders_that_differ_only_in_letter_case_stay_apart(
    tmp_path: Path,
) -> None:
    """On a case-sensitive file system ``cx`` and ``CX`` are two folders."""
    (tmp_path / "cx").mkdir()
    try:
        (tmp_path / "CX").mkdir()
    except FileExistsError:
        pytest.skip("this file system folds letter case")

    assert not _doctor_hooks._same_folder(str(tmp_path / "cx"), tmp_path / "CX")


@pytest.mark.parametrize(
    ("windows", "name", "quotes"),
    [
        (True, "plain dir", '"{}"'),
        (True, "a $HOME", None),
        (True, "100%PATH%", None),
        (True, "trailing, comma,", '"{}"'),
        (False, "plain dir", "'{}'"),
        (False, "it's", None),
    ],
)
def test_the_project_in_a_fix_is_quoted_or_given_in_words(
    windows: bool,
    name: str,
    quotes: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Doctor quotes the root with the helper every printed command uses.

    The command ends the fix, after a colon, so nothing follows the root. Where
    those quotes cannot carry the root (``$`` or ``%`` on Windows, ``'``
    elsewhere), the fix names ``--project`` in words and ends with the root as
    it is. The fix puts no quotes of its own around the command.
    """
    from functools import partial

    from apothem.cli import _cmd_doctor
    from apothem.lib.shell_quote import shell_quoted

    project = tmp_path / name
    monkeypatch.setattr(
        _cmd_doctor, "shell_quoted", partial(shell_quoted, windows=windows)
    )
    fix = _cmd_doctor._update_fix("cursor", project)
    assert "'update" not in fix
    if quotes is None:
        assert _cmd_doctor._update_command("cursor", project) is None
        assert fix == (
            "Run update --harness cursor with the same command prefix you "
            "installed with and this folder as --project, then run doctor again: "
            f"{project}"
        )
        return
    expected = "update --harness cursor --project " + quotes.format(project)
    assert _cmd_doctor._update_command("cursor", project) == expected
    assert fix == (
        "Run this command with the same command prefix you installed with, "
        f"then run doctor again: {expected}"
    )
    if not windows:
        assert shlex.split(expected)[-1] == str(project)


def test_an_unreadable_ledger_fix_ends_with_the_update_command(
    runner: CliRunner, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``ledger.unreadable`` fix moves the ledger aside, then names update."""
    from apothem.cli import _cmd_doctor
    from apothem.lib.install_ledger import LedgerError
    from apothem.lib.shell_quote import shell_quoted

    project = tmp_path / "proj"
    project.mkdir()
    result = runner.invoke(
        main, ["install", "--harness", "cursor", "--project", str(project), "--yes"]
    )
    assert result.exit_code == 0, result.output

    def unreadable(*args: object, **kwargs: object) -> None:
        raise LedgerError("damaged line 3")

    monkeypatch.setattr(_cmd_doctor, "registered_hooks", unreadable)
    result = runner.invoke(main, ["doctor", "--json", "--project", str(project)])

    payload = json.loads(result.stdout)
    failed = [c for c in payload["checks"] if c["code"] == "ledger.unreadable"]
    assert [c["harness"] for c in failed] == ["cursor"]
    quoted = shell_quoted(str(project))
    assert quoted is not None
    assert failed[0]["fix"] == (
        "Move the damaged ledger file aside, then run this command with the "
        "same command prefix you installed with, to record a fresh install: "
        f"update --harness cursor --project {quoted}"
    )


def test_doctor_names_the_project_in_a_project_harness_fix(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    result = runner.invoke(
        main, ["install", "--harness", "cursor", "--project", str(project), "--yes"]
    )
    assert result.exit_code == 0, result.output
    ledger = install_ledger.ledger_path("cursor")
    text = ledger.read_text(encoding="utf-8")
    ledger.write_text(
        text.replace(json.dumps(str(project))[1:-1], "elsewhere"), encoding="utf-8"
    )

    result = runner.invoke(main, ["doctor", "--json", "--project", str(project)])

    payload = json.loads(result.stdout)
    unchecked = [c for c in payload["checks"] if c["code"] == "hook.unchecked"]
    assert [c["harness"] for c in unchecked] == ["cursor"]
    quoted = f'"{project}"' if os.name == "nt" else f"'{project}'"
    command = f"update --harness cursor --project {quoted}"
    assert unchecked[0]["fix"].endswith(f"to record the install: {command}")


@pytest.mark.parametrize(
    "command",
    [
        '& "py" "x/hooks/dispatch.py" --contract cursor sessionStart',
        'py "x/hooks/dispatch.py" --contract cursor sessionStart',
    ],
)
def test_a_shell_form_hook_drops_the_powershell_call_operator(
    command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The operator is PowerShell's, so it is dropped where Windows runs the line.
    monkeypatch.setattr(_doctor_hooks, "_on_windows", lambda: True)
    argv = _doctor_hooks._handler_argv({"command": command}, ("command",))
    assert argv == ["py", "x/hooks/dispatch.py", "--contract", "cursor", "sessionStart"]


def _as_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Write hook files and read them back as a Windows host does, on any host."""
    monkeypatch.setattr(wrapper_factories, "_on_windows", lambda: True)
    monkeypatch.setattr(_doctor_hooks, "_on_windows", lambda: True)


def _marker_script(tmp_path: Path) -> tuple[Path, Path]:
    """Return a script that writes a marker file when it runs, and the marker."""
    marker = tmp_path / "foreign-hook-ran.txt"
    script = tmp_path / "foreign_hook.py"
    script.write_text(
        f"import pathlib\npathlib.Path({str(marker)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    return script, marker


_HOOK_FILES = {
    "cursor": Path(".cursor", "hooks.json"),
    "github-copilot": Path(".github", "hooks", "apothem.json"),
}
_CONTRACTS = {"cursor": "cursor", "github-copilot": "copilot"}


def _dispatcher(project: Path, harness: str) -> Path:
    return project / ".apothem" / "support" / harness / "hooks" / "dispatch.py"


def _command_entry(harness: str, line: str) -> dict[str, object]:
    """Return a hook entry that runs *line*, in the shape *harness* reads."""
    if harness == "github-copilot":
        return {"type": "command", "bash": line, "powershell": f"& {line}"}
    call = "& " if _doctor_hooks._on_windows() else ""
    return {"type": "command", "command": f"{call}{line}"}


def _add_entry(hook_file: Path, entry: dict[str, object]) -> None:
    """Add *entry* to *hook_file* under a stop event, writing the file if absent."""
    if hook_file.is_file():
        document = json.loads(hook_file.read_text(encoding="utf-8"))
    else:
        hook_file.parent.mkdir(parents=True, exist_ok=True)
        document = {"version": 1, "hooks": {}}
    document["hooks"].setdefault("stop", []).append(entry)
    hook_file.write_text(json.dumps(document, indent=2), encoding="utf-8")


def _unchecked(payload: dict, harness: str) -> list[str]:
    return [
        check["message"]
        for check in payload["checks"]
        if check["code"] == "hook.unchecked" and check["harness"] == harness
    ]


def test_doctor_starts_a_cursor_hook_written_for_powershell(
    runner: CliRunner, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Cursor runs hook lines through PowerShell on Windows, so an install there
    # writes `& "<python>" "<dispatch.py>" ...`: doctor must start the
    # interpreter, not a program named "&".
    _as_windows(monkeypatch)
    project = _project(tmp_path)
    _install(runner, "cursor", "--project", str(project))
    hook_file = project / ".cursor" / "hooks.json"
    [entry] = json.loads(hook_file.read_text(encoding="utf-8"))["hooks"]["sessionStart"]
    assert entry["command"].startswith('& "')

    code, payload = _doctor(runner, "--project", str(project))

    assert code == 0, payload
    assert _row(payload, "cursor")["hooks"] == {"probed": 1, "failed": []}
    assert _unchecked(payload, "cursor") == []


def test_doctor_starts_github_copilot_hooks(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    # Copilot entries hold their command lines under "bash" and "powershell",
    # with no "command" key.
    project = _project(tmp_path)
    _install(runner, "github-copilot", "--project", str(project))

    code, payload = _doctor(runner, "--project", str(project))

    assert code == 0, payload
    assert _row(payload, "github-copilot")["hooks"] == {"probed": 1, "failed": []}
    assert _unchecked(payload, "github-copilot") == []


@pytest.mark.parametrize(
    ("harness", "operator_hook"),
    [
        pytest.param("cursor", False, id="cursor"),
        pytest.param("cursor", True, id="cursor-with-an-operator-hook"),
        pytest.param("github-copilot", False, id="github-copilot"),
        pytest.param("kiro", False, id="kiro"),
        pytest.param("codebuddy", False, id="codebuddy"),
        pytest.param("windsurf", False, id="windsurf"),
    ],
)
def test_doctor_reports_a_project_hook_whose_interpreter_is_gone(
    runner: CliRunner,
    home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    harness: str,
    operator_hook: bool,
) -> None:
    # The Python the install wrote into the hook lines, which its record keeps,
    # was removed later. The hooks cannot start, and doctor says so without
    # starting anything, also after the operator added a hook of their own.
    _as_windows(monkeypatch)
    gone = tmp_path / "removed-python" / "python.exe"
    monkeypatch.setattr(wrapper_factories, "resolve_python_bin", lambda: gone)
    project = _project(tmp_path)
    _install(runner, harness, "--project", str(project))
    if operator_hook:
        entry = {"type": "command", "command": "echo operator-own-hook"}
        _add_entry(project / _HOOK_FILES[harness], entry)

    code, payload = _doctor(runner, "--project", str(project))

    assert code == 1, payload
    failed = [check for check in payload["checks"] if check["status"] == "fail"]
    assert [check["code"] for check in failed] == ["hook.start_failed"]
    assert failed[0]["harness"] == harness
    # The command shown starts with the interpreter, not with PowerShell's "&".
    assert f"cannot start: {gone.as_posix()} " in failed[0]["message"]
    assert "the interpreter does not exist" in failed[0]["message"]


def test_doctor_does_not_start_handlers_kept_inside_a_kiro_hook(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    # A committed Kiro hook file hides handlers in the "enabled" value of a hook
    # that looks like Apothem's. The install keeps only a true or false flag
    # there, and doctor reads a handler only where Kiro does, under "action".
    project = _project(tmp_path)
    script, marker = _marker_script(tmp_path)
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(project, "kiro").as_posix()
    missing = (tmp_path / "planted" / "python.exe").as_posix()
    apothem_like = (
        "python .apothem/support/kiro/hooks/dispatch.py --contract kiro SessionStart"
    )
    hidden = [
        {"command": f'"{missing}" "{dispatcher}" --contract kiro SessionStart'},
        {
            "command": f'"{python}" "{script.as_posix()}" "{dispatcher}" '
            "--contract kiro SessionStart"
        },
    ]
    planted = {
        "version": "v1",
        "hooks": [
            {
                "name": "apothem-session-start",
                "trigger": "SessionStart",
                "action": {"type": "command", "command": apothem_like},
                "enabled": hidden,
            }
        ],
    }
    hook_file = project / ".kiro" / "hooks" / "apothem.json"
    hook_file.parent.mkdir(parents=True)
    hook_file.write_text(json.dumps(planted), encoding="utf-8")
    _install(runner, "kiro", "--project", str(project))
    installed = json.loads(hook_file.read_text(encoding="utf-8"))
    assert all("enabled" not in hook for hook in installed["hooks"])

    code, payload = _doctor(runner, "--project", str(project))

    assert not marker.exists()
    assert code == 0, payload
    assert _row(payload, "kiro")["hooks"] == {"probed": 1, "failed": []}
    assert not any(missing in check["message"] for check in payload["checks"])


def test_doctor_prints_why_it_did_not_start_a_hook(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    _install(runner, "github-copilot", "--project", str(project))
    _dispatcher(project, "github-copilot").write_text("# changed\n", encoding="utf-8")

    result = runner.invoke(main, ["doctor", "--project", str(project), "--no-color"])

    assert result.exit_code == 0, result.output
    shown = " ".join(result.output.split())
    assert "changed after the install (dispatch.py)" in shown
    assert "Fix: Check the hook command or file named here." in shown


@pytest.mark.parametrize("shape", ["line", "args", "nested", "commandWindows"])
@pytest.mark.parametrize("harness", ["cursor", "github-copilot"])
def test_doctor_does_not_start_a_hook_line_the_install_did_not_write(
    runner: CliRunner,
    home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    harness: str,
    shape: str,
) -> None:
    # A project's hook files are shared, so anyone who can commit to the project
    # can put a line in them after the install. Each line here runs a marker
    # script and still names a native dispatcher and a --contract, the way
    # Apothem's own lines do. (The install would replace the "line" shape, so
    # the lines are added after it.)
    if shape == "commandWindows":
        _as_windows(monkeypatch)  # the key Codex reads on Windows
    project = _project(tmp_path)
    _install(runner, harness, "--project", str(project))
    script, marker = _marker_script(tmp_path)
    python = Path(sys.executable).as_posix()
    elsewhere = _dispatcher(tmp_path / "elsewhere", harness).as_posix()
    contract = _CONTRACTS[harness]
    line = f'"{python}" "{script.as_posix()}" "{elsewhere}" --contract {contract}'
    entry: dict[str, object] = {
        "line": _command_entry(harness, line),
        "args": {
            "type": "command",
            "command": python,
            "args": [script.as_posix(), elsewhere, "--contract", contract],
        },
        "nested": {"type": "command", "note": {"command": line}},
        "commandWindows": {"type": "command", "commandWindows": line},
    }[shape]
    _add_entry(project / _HOOK_FILES[harness], entry)

    code, payload = _doctor(runner, "--project", str(project))

    assert not marker.exists()
    assert code == 0, payload
    assert _row(payload, harness)["hooks"] == {"probed": 1, "failed": []}
    messages = _unchecked(payload, harness)
    if shape in {"nested", "commandWindows", "args"}:
        # Not where, or not under a key, the tool reads a handler: not a hook.
        # Neither tool reads "args", so it runs the bare interpreter there.
        assert messages == []
    else:
        [message] = messages
        assert "foreign_hook.py, which this install did not write" in message


@pytest.mark.parametrize("harness", ["cursor", "github-copilot"])
def test_doctor_starts_only_apothem_lines_of_a_hook_file_as_installed(
    runner: CliRunner, home: Path, tmp_path: Path, harness: str
) -> None:
    # The operator's own entry names a hooks/dispatch.py of its own, but not the
    # project's dispatcher with --contract, so it is not Apothem's to start.
    project = _project(tmp_path)
    script, marker = _marker_script(tmp_path)
    python = Path(sys.executable).as_posix()
    line = f'"{python}" "{script.as_posix()}" not-apothem/hooks/dispatch.py'
    _add_entry(project / _HOOK_FILES[harness], _command_entry(harness, line))
    _install(runner, harness, "--project", str(project))

    code, payload = _doctor(runner, "--project", str(project))

    assert not marker.exists()
    assert code == 0, payload
    assert _row(payload, harness)["hooks"] == {"probed": 1, "failed": []}
    assert _unchecked(payload, harness) == []


@pytest.mark.parametrize("harness", ["cursor", "github-copilot"])
def test_doctor_does_not_run_a_hook_script_changed_after_the_install(
    runner: CliRunner, home: Path, tmp_path: Path, harness: str
) -> None:
    project = _project(tmp_path)
    _install(runner, harness, "--project", str(project))
    script, marker = _marker_script(tmp_path)
    dispatcher = _dispatcher(project, harness)
    dispatcher.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")

    code, payload = _doctor(runner, "--project", str(project))

    assert not marker.exists()
    assert code == 0, payload
    assert _row(payload, harness)["hooks"] == {"probed": 0, "failed": []}
    [message] = _unchecked(payload, harness)
    assert "changed after the install (dispatch.py)" in message


def test_doctor_does_not_run_a_hook_script_beside_a_module_it_did_not_install(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    # dispatch.py puts its own folder first on sys.path, so a file there named
    # after a standard module takes that module's place.
    project = _project(tmp_path)
    _install(runner, "github-copilot", "--project", str(project))
    script, marker = _marker_script(tmp_path)
    planted = _dispatcher(project, "github-copilot").with_name("argparse.py")
    planted.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")

    code, payload = _doctor(runner, "--project", str(project))

    assert not marker.exists()
    assert code == 0, payload
    [message] = _unchecked(payload, "github-copilot")
    assert "argparse.py, which the install did not write" in message


def test_doctor_reads_the_install_record_of_the_named_project(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    # The newest install went into another project; the named project's own
    # record still lists the hooks doctor starts there.
    project = _project(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    _install(runner, "github-copilot", "--project", str(project))
    _install(runner, "github-copilot", "--project", str(other))

    code, payload = _doctor(runner, "--project", str(project))

    assert code == 0, payload
    assert _row(payload, "github-copilot")["hooks"] == {"probed": 1, "failed": []}


def _fake_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: dict[str, object],
    *,
    python_bin: str | None = None,
    mode: str = "native_hooks",
) -> tuple[Path, Path]:
    """Fake a GitHub Copilot project install whose hook file holds *entry*.

    *python_bin* is the interpreter the install record keeps; ``None`` is a
    record from a release that kept none. *mode* is the hook file's install
    mode: ``write_text`` for a settings file the hooks are merged into.
    """
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    dispatcher.parent.mkdir(parents=True)
    dispatcher.write_text("# the dispatcher the install wrote\n", encoding="utf-8")
    hook_file = tmp_path / _HOOK_FILES["github-copilot"]
    _add_entry(hook_file, entry)
    targets = [
        SimpleNamespace(
            path=str(path),
            mode=mode,
            digest=hashlib.sha256(path.read_bytes()).hexdigest(),
            files=None,
        )
        for path, mode in (
            (hook_file, mode),
            (dispatcher, "merge_tree_entries"),
        )
    ]
    record = SimpleNamespace(targets=targets, python_bin=python_bin, root=str(tmp_path))
    monkeypatch.setattr(
        install_ledger, "current_install_record", lambda package_key, root: record
    )
    return hook_file, dispatcher


def _read_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, windows: bool = False
) -> _doctor_hooks.RegisteredHooks:
    monkeypatch.setattr(_doctor_hooks, "_on_windows", lambda: windows)
    hooks = _doctor_hooks.registered_hooks(
        "github_copilot", root=tmp_path, project=True
    )
    assert hooks is not None
    return hooks


_DOUBLE = '"{py}" -E -s "{script}" --contract copilot'
_SINGLE = "'{py}' -E -s '{script}' --contract copilot"
_ARGV = ["{py}", "-E", "-s", "{script}", "--contract", "copilot"]


@pytest.mark.parametrize(
    ("windows", "lines", "expected", "note"),
    [
        pytest.param(
            True,
            {"bash": f"{_DOUBLE} bash", "powershell": f"& {_DOUBLE} powershell"},
            [*_ARGV, "powershell"],
            None,
            id="windows-reads-powershell",
        ),
        pytest.param(
            False,
            {"bash": f"{_DOUBLE} bash", "powershell": f"& {_DOUBLE} powershell"},
            [*_ARGV, "bash"],
            None,
            id="posix-reads-bash",
        ),
        pytest.param(
            True,
            {"command": f"{_DOUBLE} command"},
            [*_ARGV, "command"],
            None,
            id="windows-falls-back-to-command",
        ),
        pytest.param(
            False,
            {"command": f"{_DOUBLE} command"},
            [*_ARGV, "command"],
            None,
            id="posix-falls-back-to-command",
        ),
        pytest.param(
            True,
            {"powershell": f"& {_SINGLE} powershell"},
            [*_ARGV, "powershell"],
            None,
            id="windows-single-quotes",
        ),
        pytest.param(
            False,
            {"command": f"& {_DOUBLE} command"},
            None,
            "runs &, which is not the Python Apothem runs under",
            id="posix-keeps-the-call-operator",
        ),
        pytest.param(
            True,
            {"bash": f"{_DOUBLE} bash"},
            None,
            "holds no hook command doctor can start",
            id="windows-bash-only",
        ),
    ],
)
def test_doctor_reads_the_hook_line_the_harness_runs_on_this_platform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    windows: bool,
    lines: dict[str, str],
    expected: list[str] | None,
    note: str | None,
) -> None:
    # GitHub Copilot runs "powershell" on Windows and "bash" on macOS and Linux,
    # and falls back to "command" when the platform's key is absent. Each line
    # here ends with its own key name, so the argv shows which one was read.
    # The "&" call operator is PowerShell's: sh cannot run a line with it.
    python = Path(sys.executable).as_posix()
    script = _dispatcher(tmp_path, "github-copilot")
    entry: dict[str, object] = {"type": "command"}
    entry.update(
        {
            key: line.format(py=python, script=script.as_posix())
            for key, line in lines.items()
        }
    )
    _fake_install(tmp_path, monkeypatch, entry)

    hooks = _read_hooks(tmp_path, monkeypatch, windows=windows)

    if expected is None:
        assert hooks.argvs == []
        [unchecked] = hooks.unchecked
        assert note is not None
        assert note in unchecked
    else:
        # Doctor starts the trusted strings: the Python it runs under and the
        # dispatcher path the install recorded, not the tokens in the file.
        argv = [part.format(py=sys.executable, script=str(script)) for part in expected]
        assert hooks.argvs == [argv]
        assert hooks.unchecked == []


def _plant_module(tmp_path: Path, dispatcher: Path) -> None:
    dispatcher.with_name("json.py").write_text(
        "raise SystemExit(9)\n", encoding="utf-8"
    )


def _change_dispatcher(tmp_path: Path, dispatcher: Path) -> None:
    dispatcher.write_text("raise SystemExit(9)\n", encoding="utf-8")


def _delete_dispatcher(tmp_path: Path, dispatcher: Path) -> None:
    dispatcher.unlink()


def _link(link: Path, target: Path, *, folder: bool = False) -> None:
    """Make *link* a symbolic link to *target*; a junction for a folder on Windows."""
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=folder)
    except OSError:
        if not (folder and sys.platform == "win32"):
            pytest.skip("this host cannot create a symbolic link")
        import _winapi  # Windows only; a junction needs no privilege

        _winapi.CreateJunction(str(target), str(link))


def _link_folder(tmp_path: Path, dispatcher: Path) -> None:
    elsewhere = tmp_path / "elsewhere-lib"
    elsewhere.mkdir()
    _link(dispatcher.parent / "lib", elsewhere, folder=True)


def _venv_python(tmp_path: Path, dispatcher: Path) -> None:
    # A committed folder that looks like a virtual environment, whose python
    # links to the real one: started from there, Python would read the
    # folder's pyvenv.cfg and its .pth files.
    _link(tmp_path / "e" / "bin" / "python3", Path(sys.executable))
    (tmp_path / "e" / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")


_OTHER_PYTHON = '"{other}" "{script}" --contract copilot'
_GONE_PYTHON = '"{out}/removed/python" "{script}" --contract copilot'


@pytest.mark.parametrize(
    ("line", "python_bin", "change", "outcome", "detail"),
    [
        pytest.param(_DOUBLE, None, None, "start", None, id="apothem-line"),
        pytest.param(
            _OTHER_PYTHON,
            "{other}",
            None,
            "start",
            None,
            id="the-python-the-install-recorded",
        ),
        pytest.param(
            _GONE_PYTHON,
            "{out}/removed/python",
            None,
            "cannot start",
            "the interpreter does not exist",
            id="the-python-the-install-recorded-is-gone",
        ),
        pytest.param(
            _OTHER_PYTHON,
            "{out}/recorded/python",
            None,
            "unchecked",
            "not the Python the install recorded",
            id="not-the-python-the-install-recorded",
        ),
        pytest.param(
            _OTHER_PYTHON,
            None,
            None,
            "unchecked",
            "earlier Apothem that kept no interpreter",
            id="a-record-that-kept-no-interpreter",
        ),
        pytest.param(
            _GONE_PYTHON,
            None,
            None,
            "unchecked",
            "which is not the Python Apothem runs under",
            id="an-unknown-python-is-not-looked-up",
        ),
        pytest.param(
            '"{out}/removed/python" "{other}" "{script}" --contract copilot',
            "{out}/removed/python",
            None,
            "unchecked",
            "which this install did not write",
            id="a-rejected-line-is-not-looked-up",
        ),
        pytest.param(
            '"{tmp}/e/bin/python3" "{script}" --contract copilot',
            None,
            _venv_python,
            "unchecked",
            "which is not the Python Apothem runs under",
            id="a-link-to-the-python-is-not-it",
        ),
        pytest.param(
            '"{py}" -c "import os" "{script}" --contract copilot',
            None,
            None,
            "unchecked",
            "an option Apothem does not write",
            id="code-option",
        ),
        pytest.param(
            '"{py}" "{other}" "{script}" --contract copilot',
            None,
            None,
            "unchecked",
            "which this install did not write",
            id="another-script",
        ),
        pytest.param(
            '"{py}" "{tmp}/x/../.apothem/support/github-copilot/hooks/dispatch.py"'
            " --contract copilot",
            None,
            None,
            "unchecked",
            "which this install did not write",
            id="dot-dot",
        ),
        pytest.param(
            '"{py}" "{script}" --contract copilot --',
            None,
            None,
            "unchecked",
            "arguments Apothem does not write",
            id="end-of-options",
        ),
        pytest.param(
            '"{py}" "{script}" sessionStart --contract copilot',
            None,
            None,
            "unchecked",
            "arguments Apothem does not write",
            id="contract-not-first",
        ),
        pytest.param(
            '"{py}" "{script}" --contract copilot ' + "a" * 65,
            None,
            None,
            "unchecked",
            "arguments Apothem does not write",
            id="overlong-name",
        ),
        pytest.param(
            '"{py}" "{script}" --contract copilot ' + " x" * 8,
            None,
            None,
            "unchecked",
            "arguments Apothem does not write",
            id="too-many-names",
        ),
        pytest.param(
            _DOUBLE,
            None,
            _delete_dispatcher,
            "cannot start",
            "the hook script does not exist",
            id="dispatcher-gone",
        ),
        pytest.param(
            _DOUBLE,
            None,
            _plant_module,
            "unchecked",
            "hold json.py, which the install did not write",
            id="planted-module",
        ),
        pytest.param(
            _DOUBLE,
            None,
            _change_dispatcher,
            "unchecked",
            "changed after the install (dispatch.py)",
            id="changed-dispatcher",
        ),
        pytest.param(
            _DOUBLE, None, _link_folder, "unchecked", "hold a link", id="link"
        ),
        pytest.param(
            '"{tmp}/.venv/Scripts/python.exe" "{script}" --contract copilot',
            "{tmp}/.venv/Scripts/python.exe",
            None,
            "unchecked",
            "the Python the install recorded, which is inside the project",
            id="a-recorded-python-inside-the-project",
        ),
    ],
)
def test_doctor_starts_a_project_hook_line_only_when_it_runs_known_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    line: str,
    python_bin: str | None,
    change: object,
    outcome: str,
    detail: str | None,
) -> None:
    # The project is tmp_path; an interpreter the install recorded lives
    # outside it, as the operator's own Python does.
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    other = outside / "other-python.exe"
    other.write_text("", encoding="utf-8")
    values = {
        "out": outside.as_posix(),
        "py": Path(sys.executable).as_posix(),
        "script": _dispatcher(tmp_path, "github-copilot").as_posix(),
        "other": other.as_posix(),
        "tmp": tmp_path.as_posix(),
    }
    _, dispatcher = _fake_install(
        tmp_path,
        monkeypatch,
        {"type": "command", "bash": line.format(**values)},
        python_bin=None if python_bin is None else python_bin.format(**values),
    )
    if callable(change):
        change(tmp_path, dispatcher)

    hooks = _read_hooks(tmp_path, monkeypatch)

    if outcome == "start":
        [argv] = hooks.argvs
        assert argv[-3:] == [str(dispatcher), "--contract", "copilot"]
        assert hooks.unchecked == []
        assert hooks.unstartable == []
        return
    assert hooks.argvs == []
    if outcome == "cannot start":
        [probe] = hooks.unstartable
        assert probe.ok is False
        assert probe.detail == detail
        assert hooks.unchecked == []
    else:
        [unchecked] = hooks.unchecked
        assert detail is not None
        assert detail in unchecked
        assert hooks.unstartable == []


def test_doctor_reads_no_handler_kept_beside_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Only the places the tool reads a command count: a handler kept in another
    # value of the entry is not one, whatever it names.
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot").as_posix()
    hidden = (
        f'"{tmp_path.as_posix()}/planted/python" "{dispatcher}" --contract copilot x'
    )
    entry = {
        "type": "command",
        "bash": _DOUBLE.format(py=python, script=dispatcher),
        "enabled": [{"command": hidden}],
        "note": {"bash": hidden},
    }
    _fake_install(tmp_path, monkeypatch, entry)

    hooks = _read_hooks(tmp_path, monkeypatch)

    [argv] = hooks.argvs
    assert argv[-2:] == ["--contract", "copilot"]
    assert hooks.unchecked == []
    assert hooks.unstartable == []


def test_doctor_spells_out_control_characters_from_a_hook_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Shown as it is, an escape character in a committed hook line could move
    # the cursor or repaint the report.
    escape = chr(27)
    script = _dispatcher(tmp_path, "github-copilot").as_posix()
    line = f'"{tmp_path.as_posix()}/a{escape}[2Jb/python" "{script}" --contract copilot'
    _fake_install(tmp_path, monkeypatch, {"type": "command", "bash": line})

    hooks = _read_hooks(tmp_path, monkeypatch)

    [unchecked] = hooks.unchecked
    assert escape not in unchecked
    assert "a<0x1b>[2Jb" in unchecked


class _Entry:
    """A folder entry that fails the test if a link is followed to classify it."""

    def __init__(self, folder: Path, name: str, *, link: bool) -> None:
        self.name = name
        self.path = str(folder / name)
        self._link = link

    def is_symlink(self) -> bool:
        return self._link

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        assert not (self._link and follow_symlinks), "followed a link"
        return False


def _with_entries(
    monkeypatch: pytest.MonkeyPatch, folder: Path, *extra: _Entry
) -> None:
    """List *extra* in *folder*, beside its real entries, when doctor walks it."""
    real = os.scandir

    class _Listing:
        def __init__(self, entries: list[object]) -> None:
            self._entries = entries

        def __enter__(self) -> list[object]:
            return self._entries

        def __exit__(self, *exc: object) -> None:
            return None

    def scandir(path: object) -> object:
        with real(path) as listing:
            entries: list[object] = list(listing)
        if os.path.normcase(str(path)) == os.path.normcase(str(folder)):
            entries += list(extra)
        return _Listing(entries)

    # The listing walk() makes, in the module that holds it.
    monkeypatch.setattr(_doctor_hook_text.os, "scandir", scandir)


def test_doctor_does_not_follow_a_link_in_the_hook_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Following a link, even to tell whether it names a folder, reaches its
    # target, which may sit on a network share.
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = _DOUBLE.format(py=python, script=dispatcher.as_posix())
    _fake_install(tmp_path, monkeypatch, {"type": "command", "bash": line})
    _with_entries(
        monkeypatch, dispatcher.parent, _Entry(dispatcher.parent, "zz", link=True)
    )

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    [unchecked] = hooks.unchecked
    assert "hold a link, zz" in unchecked


def test_doctor_spells_out_control_characters_in_hook_folder_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    escape = chr(27)
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = _DOUBLE.format(py=python, script=dispatcher.as_posix())
    _fake_install(tmp_path, monkeypatch, {"type": "command", "bash": line})
    planted = _Entry(dispatcher.parent, f"a{escape}[2Jb.py", link=False)
    _with_entries(monkeypatch, dispatcher.parent, planted)

    hooks = _read_hooks(tmp_path, monkeypatch)

    [unchecked] = hooks.unchecked
    assert escape not in unchecked
    assert "hold a<0x1b>[2Jb.py, which the install did not write" in unchecked


def test_doctor_reads_at_most_a_hundred_commands_from_a_hook_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = _DOUBLE.format(py=python, script=dispatcher.as_posix())
    hook_file, _ = _fake_install(
        tmp_path, monkeypatch, {"type": "command", "bash": line}
    )
    entries = [{"type": "command", "bash": f"{line} n{index}"} for index in range(150)]
    document = {"version": 1, "hooks": {"sessionStart": entries}}
    hook_file.write_text(json.dumps(document), encoding="utf-8")

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert len(hooks.argvs) == 100
    assert hooks.unchecked == [
        f"{hook_file} holds more than 100 hook commands; doctor read only the first 100"
    ]


def test_doctor_reports_a_hook_file_nested_too_deep_to_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = _DOUBLE.format(py=python, script=dispatcher.as_posix())
    hook_file, _ = _fake_install(
        tmp_path, monkeypatch, {"type": "command", "bash": line}
    )
    hook_file.write_text(
        '{"hooks": ' + "[" * 200_000 + "]" * 200_000 + "}", encoding="utf-8"
    )

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    assert hooks.unchecked == [
        f"{hook_file} cannot be read as JSON, so no hook in it was started"
    ]


def test_a_recorded_python_inside_the_project_names_itself_to_run_with(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = (tmp_path / ".venv" / "Scripts" / "python.exe").as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = f'"{recorded}" "{dispatcher.as_posix()}" --contract copilot'
    _fake_install(
        tmp_path, monkeypatch, {"type": "command", "bash": line}, python_bin=recorded
    )

    hooks = _read_hooks(tmp_path, monkeypatch)

    [unchecked] = hooks.unchecked
    assert hooks.run_with == {unchecked: recorded}


def test_doctor_names_an_install_recorded_without_checksums(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A release before checksums recorded the hook files with none, and a hook
    # subfolder as one folder; doctor says so instead of calling them foreign.
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = _DOUBLE.format(py=python, script=dispatcher.as_posix())
    _fake_install(tmp_path, monkeypatch, {"type": "command", "bash": line})
    lib = dispatcher.parent / "lib"
    lib.mkdir()
    (lib / "__init__.py").write_text("", encoding="utf-8")
    record = install_ledger.current_install_record("github_copilot", root=tmp_path)
    for target in record.targets:
        target.digest = None
    record.targets.append(
        SimpleNamespace(
            path=str(lib), mode="merge_tree_entries", digest=None, files=None
        )
    )

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    [unchecked] = hooks.unchecked
    assert "installed by an earlier Apothem that kept no checksums" in unchecked


def test_the_summary_names_a_harness_with_unchecked_hooks_once() -> None:
    import io

    from rich.console import Console

    from apothem.cli import _cmd_doctor

    out = io.StringIO()
    rows = [{"name": "kiro", "installed": True}]
    checks = [
        {"code": "hook.unchecked", "harness": "kiro", "status": "info"},
        {"code": "hook.unchecked", "harness": "kiro", "status": "info"},
    ]

    _cmd_doctor._print_summary(Console(file=out, width=200), rows, checks)

    assert "the hook commands of kiro were not checked" in out.getvalue()


def test_doctor_judges_the_key_the_tool_runs_not_another(
    runner: CliRunner, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Cursor runs "command". A teammate points it at their own program and moves
    # the install's line to "commandWindows", a key only Codex reads: doctor
    # must judge the line Cursor runs, not report the moved one as started.
    _as_windows(monkeypatch)
    project = _project(tmp_path)
    _install(runner, "cursor", "--project", str(project))
    script, marker = _marker_script(tmp_path)
    hook_file = project / _HOOK_FILES["cursor"]
    document = json.loads(hook_file.read_text(encoding="utf-8"))
    [entry] = document["hooks"]["sessionStart"]
    dispatcher = _dispatcher(project, "cursor").as_posix()
    python = Path(sys.executable).as_posix()
    entry["commandWindows"] = entry["command"]
    entry["command"] = (
        f'& "{python}" "{script.as_posix()}" "{dispatcher}" --contract cursor sessionStart'
    )
    hook_file.write_text(json.dumps(document, indent=2), encoding="utf-8")

    code, payload = _doctor(runner, "--project", str(project))

    assert not marker.exists()
    assert code == 0, payload
    assert _row(payload, "cursor")["hooks"] == {"probed": 0, "failed": []}
    [message] = _unchecked(payload, "cursor")
    assert "foreign_hook.py, which this install did not write" in message


def test_doctor_fix_for_a_recorded_python_inside_the_project(
    runner: CliRunner, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Doctor starts no interpreter inside the project, so the fix never says
    # to run that one: an update under a Python outside the project records
    # that Python instead, which doctor accepts. The update runs from a folder
    # outside the project: "python -m apothem" run in the project folder would
    # import an apothem package committed there, whatever launcher started it.
    # An active project environment puts its Python first on PATH, where the
    # npx shim would find it again, so the fix says to deactivate it first and
    # names the variable that picks the shim's Python.
    from apothem.cli import _cmd_doctor

    project = _project(tmp_path)
    _install(runner, "cursor", "--project", str(project))
    recorded = (project / ".venv" / "Scripts" / "python.exe").as_posix()
    reason = f"a hook command runs {recorded}, the Python the install recorded"
    hooks = _doctor_hooks.RegisteredHooks()
    hooks.note(reason, run_with=recorded)
    monkeypatch.setattr(_cmd_doctor, "registered_hooks", lambda *a, **k: hooks)

    code, payload = _doctor(runner, "--project", str(project))

    assert code == 0, payload
    [check] = [c for c in payload["checks"] if c["code"] == "hook.unchecked"]
    assert recorded not in check["fix"]
    assert "-m apothem" not in check["fix"]
    assert check["fix"].startswith(
        "If the project's virtual environment is active, deactivate it. Then "
        "from a folder outside the project, with an Apothem that runs under a "
        "Python outside the project (not one installed into the project's own "
        "environment; for npx, set APOTHEM_PYTHON to that Python), run this "
        "command, then "
        "run doctor again: update --harness cursor --project "
    )
    assert check["fix"].count("then run") == 1


def test_a_claude_code_install_records_the_interpreter_of_its_hooks(
    runner: CliRunner, home: Path
) -> None:
    _install(runner, "claude-code")

    record = install_ledger.latest_record("claude_code")

    assert record is not None
    assert record.python_bin
    settings = (home / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert record.python_bin in settings


@pytest.mark.parametrize("probed", [0, 1])
def test_the_summary_says_some_when_a_harness_also_started_hooks(probed: int) -> None:
    import io

    from rich.console import Console

    from apothem.cli import _cmd_doctor

    out = io.StringIO()
    rows = [{"name": "cursor", "installed": True, "hooks": {"probed": probed}}]
    checks = [{"code": "hook.unchecked", "harness": "cursor", "status": "info"}]

    _cmd_doctor._print_summary(Console(file=out, width=200), rows, checks)

    which = "some hook commands" if probed else "the hook commands"
    assert f"{which} of cursor were not checked" in out.getvalue()


def test_doctor_fails_when_an_installed_harness_does_not_verify(
    runner: CliRunner, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(runner, "codex")
    from apothem.harnesses.codex import CodexAdapter

    monkeypatch.setattr(CodexAdapter, "verify", lambda self: False)

    code, payload = _doctor(runner)

    assert code == 1, payload
    codes = [c["code"] for c in payload["checks"] if c["status"] == "fail"]
    assert codes == ["harness.verify_failed"]


def test_doctor_reports_an_invalid_profile_with_its_code(
    runner: CliRunner, home: Path
) -> None:
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.write_text("identity: [unclosed\n", encoding="utf-8")

    code, payload = _doctor(runner)

    assert code == 1, payload
    assert payload["profile_valid"] is False
    assert payload["profile_error_code"] == "profile.yaml_invalid"
    codes = [c["code"] for c in payload["checks"] if c["status"] == "fail"]
    assert codes == ["profile.yaml_invalid"]


def test_doctor_hook_probe_imports_in_a_fresh_interpreter() -> None:
    """``doctor`` loads its hook probe before anything imports the install driver.

    In-process tests import the driver shim first, which hides an import cycle
    that only a fresh interpreter (the real ``apothem doctor``) meets.
    """
    src_root = Path(apothem.__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(src_root), env.get("PYTHONPATH", "")) if part
    )
    result = subprocess.run(
        [sys.executable, "-c", "import apothem.cli._doctor_hooks"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _user_install(monkeypatch: pytest.MonkeyPatch, hook_file: Path) -> None:
    """Fake a user-scope install whose one JSON target is *hook_file*."""
    target = SimpleNamespace(path=str(hook_file), mode="native_hooks", files=None)
    record = SimpleNamespace(
        targets=[target], python_bin=None, root=str(hook_file.parent)
    )
    monkeypatch.setattr(
        install_ledger, "current_install_record", lambda package_key, root: record
    )


def test_doctor_carries_on_past_a_user_hook_file_too_deep_to_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # json.loads itself gives up on nesting this deep; doctor must not.
    hook_file = tmp_path / "hooks.json"
    hook_file.write_text(
        '{"hooks": ' + "[" * 200_000 + "]" * 200_000 + "}", encoding="utf-8"
    )
    _user_install(monkeypatch, hook_file)

    hooks = _doctor_hooks.registered_hooks("codex", root=tmp_path)

    assert hooks is not None
    assert hooks.argvs == []


def test_doctor_reads_a_user_hook_file_nested_deeper_than_the_call_depth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A document nested deeper than Python's call depth: a walk that recursed
    # per level raised RecursionError out of doctor. json.loads parses such
    # nesting only from 3.14, so the parsed document is built here instead.
    depth = sys.getrecursionlimit() * 3
    line = f"python3 {tmp_path.as_posix()}/hooks/dispatch.py --contract codex x"
    nested: object = {"command": line}
    for _ in range(depth):
        nested = [nested]
    document = {"hooks": nested}
    hook_file = tmp_path / "hooks.json"
    hook_file.write_text("{}", encoding="utf-8")
    _user_install(monkeypatch, hook_file)
    # Only the hook module's json is stubbed, not json.loads for every caller.
    monkeypatch.setattr(
        _doctor_hooks, "json", SimpleNamespace(loads=lambda text: document)
    )
    monkeypatch.setattr(_doctor_hooks, "_on_windows", lambda: False)

    hooks = _doctor_hooks.registered_hooks("codex", root=tmp_path)

    assert hooks is not None
    assert hooks.argvs == [shlex.split(line)]


def test_doctor_reports_a_hook_folder_it_cannot_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = _DOUBLE.format(py=python, script=dispatcher.as_posix())
    _fake_install(tmp_path, monkeypatch, {"type": "command", "bash": line})
    real = _doctor_hooks.walk

    def walk(folder: Path) -> Iterator[tuple[Path, str]]:
        if os.path.normcase(str(folder)) == os.path.normcase(str(dispatcher.parent)):
            raise PermissionError(13, "Permission denied", str(folder))
        return real(folder)

    monkeypatch.setattr(_doctor_hooks, "walk", walk)

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    assert hooks.unchecked == [
        f"the hook scripts in {dispatcher.parent} cannot be read, so no hook "
        "command that runs them was started"
    ]


def test_doctor_judges_a_recorded_python_under_the_resolved_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The project is checked through a link (a junction on Windows), and the
    # install recorded its interpreter resolved, under the link's target. That
    # interpreter is still inside the project, where others can change it.
    real = tmp_path / "real"
    real.mkdir()
    project = tmp_path / "linked"
    _link(project, real, folder=True)
    recorded = real / ".venv" / "Scripts" / "python.exe"
    recorded.parent.mkdir(parents=True)
    recorded.write_text("", encoding="utf-8")
    dispatcher = _dispatcher(project, "github-copilot")
    line = f'"{recorded.as_posix()}" "{dispatcher.as_posix()}" --contract copilot'
    _fake_install(
        project,
        monkeypatch,
        {"type": "command", "bash": line},
        python_bin=str(recorded),
    )

    hooks = _read_hooks(project, monkeypatch)

    assert hooks.argvs == []
    assert hooks.unstartable == []
    [unchecked] = hooks.unchecked
    assert "the Python the install recorded, which is inside the project" in unchecked
    assert hooks.run_with == {unchecked: str(recorded)}


@pytest.mark.parametrize(
    ("entry", "outcome"),
    [
        pytest.param(
            {"command": "{py}", "args": ["{script}", "--contract", "copilot"]},
            "holds no hook command doctor can start",
            id="args-the-tool-never-reads",
        ),
        pytest.param(
            {"command": _DOUBLE, "args": []},
            "start",
            id="a-stray-args-list-beside-a-shell-line",
        ),
    ],
)
def test_doctor_reads_no_args_list_for_a_tool_that_runs_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: dict[str, object],
    outcome: str,
) -> None:
    # GitHub Copilot runs "command" as one shell line and never reads "args":
    # a bare interpreter there starts nothing, whatever "args" holds, and a
    # working line is not rebuilt from an "args" list beside it.
    values = {
        "py": Path(sys.executable).as_posix(),
        "script": _dispatcher(tmp_path, "github-copilot").as_posix(),
    }
    filled: dict[str, object] = {"type": "command"}
    for key, value in entry.items():
        if isinstance(value, list):
            filled[key] = [part.format(**values) for part in value]
        else:
            filled[key] = str(value).format(**values)
    _fake_install(tmp_path, monkeypatch, filled)

    hooks = _read_hooks(tmp_path, monkeypatch)

    if outcome == "start":
        [argv] = hooks.argvs
        assert argv[-2:] == ["--contract", "copilot"]
        assert hooks.unchecked == []
    else:
        assert hooks.argvs == []
        assert hooks.unchecked == [
            f"{tmp_path / _HOOK_FILES['github-copilot']} {outcome}"
        ]


def test_a_claude_code_argument_list_is_read() -> None:
    handler = {"command": "/usr/bin/python3", "args": ["/h/hooks/dispatch.py", "Stop"]}

    argv = _doctor_hooks._handler_argv(handler, ("command",), args_key="args")

    assert argv == ["/usr/bin/python3", "/h/hooks/dispatch.py", "Stop"]
    assert _doctor_hooks._ARGS_KEYS == {"claude_code": "args"}


def _deny_lookups_under(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    """Make a link lookup under *folder* raise, as Python 3.10 to 3.13 do.

    There ``Path.is_symlink`` raises for a folder the operator cannot search
    (``EACCES``), where later releases return False. Only 3.14 runs here.
    """
    real = _doctor_hooks.is_link
    prefix = os.path.normcase(str(folder))

    def is_link(path: Path) -> bool:
        if os.path.normcase(str(path)).startswith(prefix):
            raise PermissionError(13, "Permission denied", str(path))
        return real(path)

    monkeypatch.setattr(_doctor_hooks, "is_link", is_link)


def test_doctor_reports_a_hook_script_it_cannot_look_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = _DOUBLE.format(py=python, script=dispatcher.as_posix())
    _fake_install(tmp_path, monkeypatch, {"type": "command", "bash": line})
    _deny_lookups_under(monkeypatch, tmp_path / ".apothem")

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    [unchecked] = hooks.unchecked
    assert "runs a file doctor cannot look up" in unchecked
    assert "Permission denied" in unchecked


def test_doctor_reports_a_hook_file_it_cannot_look_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = _DOUBLE.format(py=python, script=dispatcher.as_posix())
    hook_file, _ = _fake_install(
        tmp_path, monkeypatch, {"type": "command", "bash": line}
    )
    _deny_lookups_under(monkeypatch, tmp_path / ".github")

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    [unchecked] = hooks.unchecked
    assert unchecked.startswith(f"{hook_file} cannot be looked up (")
    assert unchecked.endswith("so no hook in it was read")
    # An update cannot change the folder's permissions: the fix says so.
    assert hooks.fixes == {unchecked: _doctor_hook_text.LOOKUP_FIX}


def test_doctor_reports_a_hook_script_reached_through_a_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = _DOUBLE.format(py=python, script=dispatcher.as_posix())
    hook_file, _ = _fake_install(
        tmp_path, monkeypatch, {"type": "command", "bash": line}
    )
    real = _doctor_hooks.is_link
    support = os.path.normcase(str(tmp_path / ".apothem"))
    monkeypatch.setattr(
        _doctor_hooks,
        "is_link",
        lambda path: os.path.normcase(str(path)) == support or real(path),
    )

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    [unchecked] = hooks.unchecked
    assert unchecked.startswith(f"a hook command in {hook_file} runs {dispatcher}")
    # The note names the step that is the link, not only the script.
    assert f"reached through the link {tmp_path / '.apothem'}," in unchecked
    assert hooks.fixes == {}
    assert hooks.update_leads == {unchecked: _doctor_hook_text.SCRIPT_LINK_FIX}


def test_doctor_reports_an_interpreter_it_cannot_look_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Python 3.10 to 3.13 raise from Path.exists for a folder the operator
    # cannot search; later releases answer False.
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = _DOUBLE.format(py=python, script=dispatcher.as_posix())
    _fake_install(tmp_path, monkeypatch, {"type": "command", "bash": line})
    real = Path.exists

    def exists(self: Path, *args: object, **kwargs: object) -> bool:
        if os.path.normcase(str(self)) == os.path.normcase(sys.executable):
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "exists", exists)

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    [unchecked] = hooks.unchecked
    assert "runs a file doctor cannot look up" in unchecked


def test_doctor_spells_out_control_characters_in_a_command_that_cannot_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The interpreter the install recorded is gone, and its path holds an
    # escape character: the report names it with that character spelled out.
    escape = chr(27)
    recorded = f"{tmp_path.parent.as_posix()}/gone-a{escape}[2Jb/python"
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = f'"{recorded}" "{dispatcher.as_posix()}" --contract copilot'
    _fake_install(
        tmp_path, monkeypatch, {"type": "command", "bash": line}, python_bin=recorded
    )

    hooks = _read_hooks(tmp_path, monkeypatch)

    [probe] = hooks.unstartable
    assert probe.detail == "the interpreter does not exist"
    assert escape not in probe.command
    assert "gone-a<0x1b>[2Jb" in probe.command


def test_doctor_spells_out_control_characters_in_a_started_command(
    tmp_path: Path,
) -> None:
    escape = chr(27)
    missing = str(tmp_path / f"a{escape}[2Jb" / "python")

    [probe] = _doctor_hooks.probe_hooks([[missing, "x/hooks/dispatch.py"]])

    assert probe.ok is False
    assert escape not in probe.command
    assert escape not in probe.detail
    assert "a<0x1b>[2Jb" in probe.command


def test_a_note_is_kept_beside_an_argv_that_spells_the_same() -> None:
    # One list's record of what it holds never hides an entry of another.
    hooks = _doctor_hooks.RegisteredHooks()

    hooks.add(["note", "a reason"])
    hooks.note("a reason")

    assert hooks.argvs == [["note", "a reason"]]
    assert hooks.unchecked == ["a reason"]


def test_a_line_beside_a_recorded_python_inside_the_project_names_it_to_run_with(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The install recorded an interpreter inside the project and the line now
    # runs another: an update under that same Python would record it again,
    # so the fix is the one for a Python outside the project.
    recorded = (tmp_path / ".venv" / "Scripts" / "python.exe").as_posix()
    other = (tmp_path.parent / "elsewhere" / "python.exe").as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = f'"{other}" "{dispatcher.as_posix()}" --contract copilot'
    _fake_install(
        tmp_path, monkeypatch, {"type": "command", "bash": line}, python_bin=recorded
    )

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    [unchecked] = hooks.unchecked
    assert (
        f"runs {other}, not the Python the install recorded ({recorded}, which "
        "is inside the project, where others can change it)"
    ) in unchecked
    assert hooks.run_with == {unchecked: recorded}


def test_doctor_reads_no_project_hook_file_larger_than_its_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = _DOUBLE.format(py=python, script=dispatcher.as_posix())
    hook_file, _ = _fake_install(
        tmp_path, monkeypatch, {"type": "command", "bash": line}
    )
    text = hook_file.read_text(encoding="utf-8")
    padding = _doctor_hook_text.MAX_HOOK_FILE_BYTES - len(text.encode("utf-8")) + 1
    hook_file.write_text(text + " " * padding, encoding="utf-8")

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    assert hooks.unchecked == [
        f"{hook_file} is larger than 4 MB, so no hook in it was read"
    ]


def test_the_checksum_of_a_file_read_in_blocks_is_its_sha256(tmp_path: Path) -> None:
    path = tmp_path / "big.py"
    data = bytes(range(256)) * (3 * 1024 * 1024 // 256)
    path.write_bytes(data)

    assert _doctor_hook_text.sha256_of(path) == hashlib.sha256(data).hexdigest()
    assert _doctor_hook_text.sha256_of(tmp_path / "missing.py") is None


def test_doctor_starts_the_hooks_of_a_claude_code_install(
    runner: CliRunner, home: Path
) -> None:
    # Claude Code runs a bare interpreter with its script in an "args" list:
    # read without that list, no handler is Apothem's and nothing is started.
    _install(runner, "claude-code")

    code, payload = _doctor(runner)

    assert code == 0, payload
    row = _row(payload, "claude-code")
    assert row["hooks"]["probed"] > 0
    assert row["hooks"]["failed"] == []
    hooks = _doctor_hooks.registered_hooks("claude_code", root=home / ".claude")
    assert hooks is not None
    assert hooks.argvs
    assert any(Path(argv[1]).name == "dispatch.py" for argv in hooks.argvs)


def _pad_past_the_cap(path: Path) -> None:
    """Pad the JSON in *path* with spaces until it is one byte over the cap."""
    text = path.read_text(encoding="utf-8")
    padding = _doctor_hook_text.MAX_HOOK_FILE_BYTES - len(text.encode("utf-8")) + 1
    path.write_text(text + " " * padding, encoding="utf-8")


def _copilot_line(tmp_path: Path) -> dict[str, object]:
    python = Path(sys.executable).as_posix()
    dispatcher = _dispatcher(tmp_path, "github-copilot")
    line = _DOUBLE.format(py=python, script=dispatcher.as_posix())
    return {"type": "command", "bash": line}


def test_doctor_names_a_merged_settings_file_larger_than_its_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A settings file the hooks are merged into (CodeBuddy's, say) is still
    # read by its tool, so skipping it must not pass as a clean check.
    hook_file, _ = _fake_install(
        tmp_path, monkeypatch, _copilot_line(tmp_path), mode="write_text"
    )
    _pad_past_the_cap(hook_file)

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    assert hooks.unchecked == [
        f"{hook_file} is larger than 4 MB, so no hook in it was read"
    ]


def test_doctor_names_a_merged_settings_file_it_cannot_look_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook_file, _ = _fake_install(
        tmp_path, monkeypatch, _copilot_line(tmp_path), mode="write_text"
    )
    _deny_lookups_under(monkeypatch, tmp_path / ".github")

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    [unchecked] = hooks.unchecked
    assert unchecked.startswith(f"{hook_file} cannot be looked up (")


def test_doctor_stays_quiet_about_a_merged_settings_file_that_is_not_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A settings file may hold comments its tool reads; with no hook in it,
    # a note would only be noise.
    hook_file, _ = _fake_install(
        tmp_path, monkeypatch, _copilot_line(tmp_path), mode="write_text"
    )
    hook_file.write_text("{ // a comment\n}", encoding="utf-8")

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    assert hooks.unchecked == []


def test_doctor_names_a_user_hook_file_larger_than_its_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook_file = tmp_path / "hooks.json"
    line = f"python3 {tmp_path.as_posix()}/hooks/dispatch.py --contract codex x"
    hook_file.write_text(json.dumps({"hooks": [{"command": line}]}), encoding="utf-8")
    _pad_past_the_cap(hook_file)
    _user_install(monkeypatch, hook_file)

    hooks = _doctor_hooks.registered_hooks("codex", root=tmp_path)

    assert hooks is not None
    assert hooks.argvs == []
    assert hooks.unchecked == [
        f"{hook_file} is larger than 4 MB, so no hook in it was read"
    ]


def test_doctor_reports_an_oversize_claude_code_settings_file_as_unchecked(
    runner: CliRunner, home: Path
) -> None:
    # The harness's own verify step passes such a file; doctor must say it
    # started none of the hooks in it rather than report a clean pass.
    _install(runner, "claude-code")
    settings = home / ".claude" / "settings.json"
    _pad_past_the_cap(settings)

    code, payload = _doctor(runner)

    assert code == 0, payload
    assert _row(payload, "claude-code")["hooks"] == {"probed": 0, "failed": []}
    assert _unchecked(payload, "claude-code") == [
        f"claude-code: {settings} is larger than 4 MB, so no hook in it was read."
    ]


@pytest.mark.parametrize(
    ("harness", "config"),
    [
        pytest.param(
            "opencode", (".config", "opencode", "opencode.json"), id="opencode"
        ),
        pytest.param("open-claw", (".openclaw", "openclaw.json"), id="open-claw"),
    ],
)
def test_doctor_names_no_oversize_settings_file_its_tool_runs_no_hook_from(
    runner: CliRunner, home: Path, harness: str, config: tuple[str, ...]
) -> None:
    # Apothem writes no hook into these files and the tool runs none from
    # them, so a large one is no unchecked hook, and an update would not
    # clear the note.
    _install(runner, harness)
    settings = home.joinpath(*config)
    _pad_past_the_cap(settings)
    support = home.joinpath(*config[:-1], ".apothem", "support", "hooks", "hooks.json")
    _pad_past_the_cap(support)

    code, payload = _doctor(runner)
    plain = runner.invoke(main, ["doctor"])

    assert code == 0, payload
    assert _unchecked(payload, harness) == []
    assert plain.exit_code == 0, plain.output
    assert "were not checked" not in plain.output


@pytest.mark.parametrize(
    ("package_key", "mode", "noted"),
    [
        pytest.param("github_copilot", "native_hooks", True, id="hook-file"),
        pytest.param("github_copilot", "write_text", True, id="merged-settings"),
        pytest.param("github_copilot", "merge_tree_entries", False, id="support-copy"),
        pytest.param("opencode", "write_text", False, id="no-native-hooks"),
    ],
)
def test_doctor_names_an_unread_file_only_where_its_tool_runs_hooks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    package_key: str,
    mode: str,
    noted: bool,
) -> None:
    # One file padded past the cap, read as a project and as a user install.
    hook_file, _ = _fake_install(
        tmp_path, monkeypatch, _copilot_line(tmp_path), mode=mode
    )
    _pad_past_the_cap(hook_file)
    reason = f"{hook_file} is larger than 4 MB, so no hook in it was read"
    hooks = {
        project: _doctor_hooks.registered_hooks(
            package_key, root=tmp_path, project=project
        )
        for project in (True, False)
    }

    for found in hooks.values():
        assert found is not None
        assert found.unchecked == ([reason] if noted else [])


@pytest.mark.parametrize(
    ("package_key", "mode"),
    [
        pytest.param("github_copilot", "merge_tree_entries", id="support-copy"),
        pytest.param("opencode", "write_text", id="no-native-hooks"),
    ],
)
def test_doctor_stays_quiet_about_a_file_it_cannot_look_up_that_runs_no_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, package_key: str, mode: str
) -> None:
    # The lookup note, like the size one, is only for a file a tool runs
    # hooks from (a merged settings file is named: the test above).
    _fake_install(tmp_path, monkeypatch, _copilot_line(tmp_path), mode=mode)
    _deny_lookups_under(monkeypatch, tmp_path / ".github")

    hooks = _doctor_hooks.registered_hooks(package_key, root=tmp_path, project=True)

    assert hooks is not None
    assert hooks.argvs == []
    assert hooks.unchecked == []


def _manifest_json_targets() -> Iterator[tuple[str, str, bool]]:
    """Yield each JSON install target's harness, mode, and whether it holds hooks.

    A target holds hooks when its template names a command a hook runs.
    """
    templates = Path(apothem.__file__).parent
    for package_key, rules in load_manifest().items():
        for rule in rules.install:
            if not str(rule.target).endswith(".json"):
                continue
            text = (templates / str(rule.source)).read_text(encoding="utf-8")
            holds = any(key in text for key in ('"command"', '"bash"', "dispatch.py"))
            yield package_key, str(rule.mode), holds


def test_every_file_a_tool_runs_hooks_from_is_named_when_unread() -> None:
    # _may_hold_hooks keys on the registry's hook status and the install
    # mode; a file with hook commands outside both would go unread silently.
    # A heuristic: templates are matched by their text (a "command" or "bash"
    # key, or the hook script's name), and files a materializer writes appear
    # only as the rows added by hand below, so a materializer that starts
    # writing hooks needs its own row here.
    targets = list(_manifest_json_targets())
    # Qwen Code's settings file is merged outside the manifest, as write_text.
    targets.append(("qwen_code", "write_text", True))

    assert any(holds for _, _, holds in targets)
    for package_key, mode, holds in targets:
        if holds:
            target = SimpleNamespace(mode=mode)
            assert _doctor_hooks._may_hold_hooks(package_key, target), (
                package_key,
                mode,
            )


class _StatAs:
    """A stat result with some fields replaced; every other one is the real one.

    ``os.stat_result`` rebuilt from a list drops the extra fields, such as
    Windows' ``st_reparse_tag``, which other lookups in the same call read.
    """

    def __init__(self, real: os.stat_result, **fields: int) -> None:
        self._real = real
        self.__dict__.update(fields)

    def __getattr__(self, name: str) -> object:
        return getattr(self._real, name)


def _look_as(
    monkeypatch: pytest.MonkeyPatch, path: Path, kind: int, *, followed: bool
) -> None:
    """Make a look at *path* report file type *kind*, which this host cannot make.

    The look that does not follow a link changes, and the one that does too
    when *followed* (a pipe is one either way; a link only to a look that
    does not follow it). Only the module's look seam is replaced.
    """
    target = os.path.normcase(str(path))
    real = _doctor_hook_text._look

    def look(name: Path, *, follow_link: bool) -> object:
        result = real(name, follow_link=follow_link)
        if os.path.normcase(str(name)) != target or (follow_link and not followed):
            return result
        return _StatAs(result, st_mode=kind | 0o644)

    monkeypatch.setattr(_doctor_hook_text, "_look", look)


def _as_pipe(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    """Make *path* look like a named pipe, which ``os.mkfifo`` cannot make here.

    Only its ``lstat`` and ``stat`` answers change; any open of it fails the
    test, since a pipe with no writer would make the open wait for good.
    """
    real_open = _doctor_hook_text._open_descriptor
    target = os.path.normcase(str(path))
    _look_as(monkeypatch, path, stat.S_IFIFO, followed=True)

    def no_open(name: Path, flags: int) -> int:
        assert os.path.normcase(str(name)) != target, "the pipe was opened"
        return real_open(name, flags)

    monkeypatch.setattr(_doctor_hook_text, "_open_descriptor", no_open)


def test_a_pipe_is_neither_read_nor_hashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "dispatch.py"
    path.write_text("# a pipe on POSIX\n", encoding="utf-8")
    _as_pipe(monkeypatch, path)

    with pytest.raises(_doctor_hook_text.NotARegularFileError):
        _doctor_hook_text.read_hook_file(path)
    assert _doctor_hook_text.sha256_of(path) is None


def test_doctor_names_a_project_hook_file_that_is_a_pipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook_file, _ = _fake_install(tmp_path, monkeypatch, _copilot_line(tmp_path))
    _as_pipe(monkeypatch, hook_file)

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    assert hooks.unchecked == [
        f"{hook_file} is not a regular file, so no hook in it was read"
    ]


def test_doctor_names_a_user_hook_file_that_is_a_pipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook_file = tmp_path / "hooks.json"
    hook_file.write_text("{}", encoding="utf-8")
    _user_install(monkeypatch, hook_file)
    _as_pipe(monkeypatch, hook_file)

    hooks = _doctor_hooks.registered_hooks("codex", root=tmp_path)

    assert hooks is not None
    assert hooks.unchecked == [
        f"{hook_file} is not a regular file, so no hook in it was read"
    ]


def test_doctor_does_not_start_a_hook_whose_recorded_file_is_a_pipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A recorded file swapped for a pipe cannot be hashed, so it no longer
    # matches its checksum, and the open never waits on it.
    _, dispatcher = _fake_install(tmp_path, monkeypatch, _copilot_line(tmp_path))
    _as_pipe(monkeypatch, dispatcher)

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    [unchecked] = hooks.unchecked
    assert "changed after the install (dispatch.py)" in unchecked


@pytest.mark.parametrize(
    ("swap", "same_file_check"),
    [
        pytest.param("pipe", False, id="a-pipe-once-open"),
        pytest.param("another-file", True, id="another-file-once-open"),
    ],
)
def test_a_file_swapped_after_the_look_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, swap: str, same_file_check: bool
) -> None:
    # Between the look and the open the path can be swapped; the open file
    # must still be a regular file, and on POSIX the one looked at.
    path = tmp_path / "hooks.json"
    path.write_text("{}", encoding="utf-8")
    real_fstat, real_close = os.fstat, os.close
    closed: list[int] = []

    def fstat(descriptor: int) -> object:
        real = real_fstat(descriptor)
        if swap == "pipe":
            return _StatAs(real, st_mode=stat.S_IFIFO | 0o644)
        return _StatAs(real, st_ino=real.st_ino + 1)  # another file

    def close(descriptor: int) -> None:
        closed.append(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(_doctor_hook_text.os, "fstat", fstat)
    monkeypatch.setattr(_doctor_hook_text.os, "close", close)
    monkeypatch.setattr(_doctor_hook_text, "_SAME_FILE_CHECK", same_file_check)

    with pytest.raises(_doctor_hook_text.NotARegularFileError):
        _doctor_hook_text.read_hook_file(path)
    assert len(closed) == 1


@pytest.mark.parametrize("follow_link", [False, True])
def test_a_file_swapped_for_a_folder_before_the_open_is_not_a_regular_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, follow_link: bool
) -> None:
    # Windows refuses to open a folder or a junction as access denied; the
    # second look tells that swap from a file the operator cannot read.
    path = tmp_path / "settings.json"
    path.write_text("{}", encoding="utf-8")
    real = _doctor_hook_text._look
    looks: list[bool] = []

    def swapped(name: Path, *, follow_link: bool) -> object:
        result = real(name, follow_link=follow_link)
        looks.append(follow_link)
        if len(looks) == 1:
            return result
        return _StatAs(result, st_mode=stat.S_IFDIR | 0o755)

    def denied(name: Path, flags: int) -> int:
        raise PermissionError(errno.EACCES, "Permission denied", str(name))

    monkeypatch.setattr(_doctor_hook_text, "_look", swapped)
    monkeypatch.setattr(_doctor_hook_text, "_open_descriptor", denied)

    with pytest.raises(_doctor_hook_text.NotARegularFileError):
        _doctor_hook_text.read_hook_file(path, follow_link=follow_link)
    assert looks == [follow_link, follow_link]


def test_a_regular_file_that_cannot_be_opened_keeps_its_own_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{}", encoding="utf-8")

    def denied(name: Path, flags: int) -> int:
        raise PermissionError(errno.EACCES, "Permission denied", str(name))

    monkeypatch.setattr(_doctor_hook_text, "_open_descriptor", denied)

    with pytest.raises(PermissionError) as raised:
        _doctor_hook_text.read_hook_file(path)
    assert not isinstance(raised.value, _doctor_hook_text.NotARegularFileError)


@pytest.mark.skipif(
    not hasattr(os, "O_NOFOLLOW"),
    reason="Windows has no open flag that refuses a link; the look before the "
    "open is its only guard",
)
def test_a_hook_file_is_opened_without_following_a_link_where_the_os_can() -> None:
    assert _doctor_hook_text._NO_FOLLOW == os.O_NOFOLLOW
    assert _doctor_hook_text._OPEN_FLAGS & os.O_NONBLOCK == os.O_NONBLOCK


def test_a_project_hook_file_that_is_a_link_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "hooks.json"
    path.write_text("{}", encoding="utf-8")
    _look_as(monkeypatch, path, stat.S_IFLNK, followed=False)

    with pytest.raises(_doctor_hook_text.NotARegularFileError):
        _doctor_hook_text.read_hook_file(path)
    assert _doctor_hook_text.read_hook_file(path, follow_link=True) == "{}"


def test_doctor_reads_a_user_hook_file_reached_through_a_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A dotfile manager keeps the operator's settings file as a link to a
    # regular file; its hooks are read like any other file under the home.
    hook_file = tmp_path / "hooks.json"
    line = f"python3 {tmp_path.as_posix()}/hooks/dispatch.py --contract codex x"
    hook_file.write_text(json.dumps({"hooks": [{"command": line}]}), encoding="utf-8")
    _user_install(monkeypatch, hook_file)
    _look_as(monkeypatch, hook_file, stat.S_IFLNK, followed=False)
    monkeypatch.setattr(_doctor_hooks, "_on_windows", lambda: False)

    hooks = _doctor_hooks.registered_hooks("codex", root=tmp_path)

    assert hooks is not None
    assert hooks.unchecked == []
    assert hooks.argvs == [shlex.split(line)]


@pytest.mark.parametrize("code", [errno.ELOOP, errno.EMLINK])
def test_a_link_swapped_in_before_the_open_is_named_not_a_regular_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    # An open that refuses a link fails with ELOOP (EMLINK on FreeBSD); the
    # file then gets the same note as any other that is not a regular file.
    path = tmp_path / "hooks.json"
    path.write_text("{}", encoding="utf-8")

    def refused(name: Path, flags: int) -> int:
        raise OSError(code, os.strerror(code), str(name))

    monkeypatch.setattr(_doctor_hook_text, "_open_descriptor", refused)

    with pytest.raises(_doctor_hook_text.NotARegularFileError) as caught:
        _doctor_hook_text.read_hook_file(path)
    assert _doctor_hook_text.unread_reason(path, caught.value) == (
        f"{path} is not a regular file, so no hook in it was read"
    )


def test_a_hook_script_larger_than_the_cap_is_not_hashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No hook script Apothem writes is that large, so it has changed; hashing
    # a large or sparse file committed in its place would take minutes.
    path = tmp_path / "dispatch.py"
    path.write_bytes(b"x" * 65)
    monkeypatch.setattr(_doctor_hook_text, "MAX_HOOK_FILE_BYTES", 64)
    assert _doctor_hook_text.sha256_of(path) is None

    # A file that grows once open is cut off the same way.
    real_fstat = os.fstat
    monkeypatch.setattr(
        _doctor_hook_text.os,
        "fstat",
        lambda descriptor: _StatAs(real_fstat(descriptor), st_size=0),
    )
    assert _doctor_hook_text.sha256_of(path) is None

    path.write_bytes(b"x" * 64)
    assert _doctor_hook_text.sha256_of(path) == hashlib.sha256(b"x" * 64).hexdigest()


def test_the_hook_probe_modules_hold_the_ci_complexity_bound() -> None:
    # CI runs ruff's C901 check over the CLI at a bound of 15, tighter than
    # the repo-wide one.
    cli = Path(_doctor_hooks.__file__).parent
    hook_module = cli / "_doctor_hooks.py"
    pytest.importorskip("ruff")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-cache",
            "--select",
            "C901",
            "--config",
            "lint.mccabe.max-complexity=15",
            str(hook_module),
            str(cli / "_doctor_hook_text.py"),
            str(cli / "_cmd_doctor.py"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _hook_fixes(payload: dict, harness: str) -> list[str]:
    return [
        check["fix"]
        for check in payload["checks"]
        if check["code"] == "hook.unchecked" and check["harness"] == harness
    ]


def test_an_oversize_settings_file_is_fixed_by_shrinking_it_not_by_update(
    runner: CliRunner, home: Path
) -> None:
    # An update keeps the operator's settings, so it never clears this note.
    _install(runner, "claude-code")
    _pad_past_the_cap(home / ".claude" / "settings.json")

    code, payload = _doctor(runner)

    assert code == 0, payload
    assert _hook_fixes(payload, "claude-code") == [
        "Shrink the file named here below 4 MB, then run doctor again."
    ]


def test_a_hook_file_that_is_not_a_regular_file_is_fixed_by_replacing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook_file, _ = _fake_install(tmp_path, monkeypatch, _copilot_line(tmp_path))
    _as_pipe(monkeypatch, hook_file)

    hooks = _read_hooks(tmp_path, monkeypatch)

    [unchecked] = hooks.unchecked
    assert hooks.fixes == {
        unchecked: "Replace the path named here with a regular file, then run "
        "doctor again."
    }


def test_a_changed_hook_script_keeps_the_update_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Only a note no update clears gets a fix of its own.
    _, dispatcher = _fake_install(tmp_path, monkeypatch, _copilot_line(tmp_path))
    dispatcher.write_text("# changed\n", encoding="utf-8")

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert len(hooks.unchecked) == 1
    assert hooks.fixes == {}


@pytest.mark.parametrize("mode", ["native_hooks", "write_text"])
def test_a_project_hook_file_reached_through_a_link_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    # A tool follows the link and runs the hooks behind it, whether the file
    # holds only hooks or is a settings file the hooks are merged into.
    hook_file, _ = _fake_install(
        tmp_path, monkeypatch, _copilot_line(tmp_path), mode=mode
    )
    hooks_folder = hook_file.parent
    outside = tmp_path / "outside-hooks"
    shutil.copytree(hooks_folder, outside)
    shutil.rmtree(hooks_folder)
    _link(hooks_folder, outside, folder=True)

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    # The note names the folder that is the link, not only the file under it.
    reason = (
        f"{hook_file} is reached through the link {hooks_folder}, so no hook in "
        "it was read"
    )
    assert hooks.unchecked == [reason]
    assert hooks.fixes == {}
    assert hooks.update_leads == {reason: _doctor_hook_text.LINK_FIX}


@pytest.mark.skipif(
    sys.platform != "win32", reason="only Windows has junctions to a file"
)
def test_a_project_hook_file_that_is_itself_a_junction_names_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _winapi  # Windows only; a junction needs no privilege

    hook_file, _ = _fake_install(tmp_path, monkeypatch, _copilot_line(tmp_path))
    outside = tmp_path / "outside.json"
    shutil.copyfile(hook_file, outside)
    hook_file.unlink()
    _winapi.CreateJunction(str(outside), str(hook_file))

    hooks = _read_hooks(tmp_path, monkeypatch)

    reason = (
        f"{hook_file} is reached through the link {hook_file}, so no hook in it "
        "was read"
    )
    assert hooks.unchecked == [reason]
    assert hooks.update_leads == {reason: _doctor_hook_text.LINK_FIX}


def test_a_hook_script_behind_a_junctioned_folder_names_that_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A real link (a junction here) on the support path: the note names the
    # folder that is the link, so the fix can point at it.
    _, dispatcher = _fake_install(tmp_path, monkeypatch, _copilot_line(tmp_path))
    support = tmp_path / ".apothem" / "support"
    outside = tmp_path / "outside-support"
    shutil.copytree(support, outside)
    shutil.rmtree(support)
    _link(support, outside, folder=True)

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.argvs == []
    [unchecked] = hooks.unchecked
    assert f"runs {dispatcher}, reached through the link {support}, " in unchecked
    assert hooks.update_leads == {unchecked: _doctor_hook_text.SCRIPT_LINK_FIX}


@pytest.mark.skipif(
    sys.platform != "win32", reason="only Windows has junctions to a file"
)
def test_a_hook_script_that_is_itself_a_junction_names_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _winapi  # Windows only; a junction needs no privilege

    _, dispatcher = _fake_install(tmp_path, monkeypatch, _copilot_line(tmp_path))
    outside = tmp_path / "outside-dispatch.py"
    shutil.copyfile(dispatcher, outside)
    dispatcher.unlink()
    _winapi.CreateJunction(str(outside), str(dispatcher))

    hooks = _read_hooks(tmp_path, monkeypatch)

    [unchecked] = hooks.unchecked
    assert f"runs {dispatcher}, reached through the link {dispatcher}, " in unchecked
    assert hooks.update_leads == {unchecked: _doctor_hook_text.SCRIPT_LINK_FIX}


@pytest.mark.skipif(
    sys.platform != "win32", reason="only Windows folds the case of a path"
)
def test_a_link_under_a_mixed_case_folder_is_named_as_the_file_spells_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The link is found by comparing case-folded paths, but the note names it
    # with the steps as the recorded path spells them.
    hook_file, _ = _fake_install(tmp_path, monkeypatch, _copilot_line(tmp_path))
    record = install_ledger.current_install_record("", tmp_path)
    spelled = tmp_path / ".GitHub" / "Hooks" / hook_file.name
    record.targets[0].path = str(spelled)
    hooks_folder = hook_file.parent
    outside = tmp_path / "outside-hooks"
    shutil.copytree(hooks_folder, outside)
    shutil.rmtree(hooks_folder)
    _link(hooks_folder, outside, folder=True)

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert hooks.unchecked == [
        f"{spelled} is reached through the link {spelled.parent}, so no hook in "
        "it was read"
    ]


def test_a_root_recorded_through_a_link_walks_from_the_real_spelling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The root is given through a link while the install recorded the real
    # paths: those are inside the project, and no step below the real root is
    # a link, so the hook is started and nothing is named as a link.
    real = tmp_path / "real"
    real.mkdir()
    _fake_install(real, monkeypatch, _copilot_line(real))
    alias = tmp_path / "alias"
    _link(alias, real, folder=True)
    install_ledger.current_install_record("", alias).root = str(alias)

    hooks = _read_hooks(alias, monkeypatch)

    assert hooks.unchecked == []
    assert len(hooks.argvs) == 1


def test_a_recorded_hook_script_outside_the_project_is_not_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The hook file is inside the project root, the script the install
    # recorded is not: it is named as outside the project, not as a link, and
    # its fix says nothing about removing it.
    _, dispatcher = _fake_install(tmp_path, monkeypatch, _copilot_line(tmp_path))
    root = tmp_path / ".github"
    install_ledger.current_install_record("", root).root = str(root)

    hooks = _read_hooks(root, monkeypatch)

    assert hooks.argvs == []
    [unchecked] = hooks.unchecked
    assert f"runs {dispatcher}, which is outside the project {root}, " in unchecked
    assert "link" not in unchecked
    assert hooks.fixes == {}
    assert hooks.update_leads == {}


def test_a_path_outside_the_project_is_never_called_link_free(
    tmp_path: Path,
) -> None:
    # A caller that skipped the inside check still gets no trust: the path
    # itself comes back, so nothing under it is started.
    record = SimpleNamespace(targets=[], python_bin=None)
    install = _doctor_hooks._ProjectInstall(
        tmp_path / "proj", record, ("command",), None
    )
    outside = tmp_path / "elsewhere" / "dispatch.py"
    assert install._link_on_path(outside) == outside


def test_the_steps_to_a_shared_hook_script_are_looked_up_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two hook commands run the same script: its link check is made once.
    hook_file, dispatcher = _fake_install(
        tmp_path, monkeypatch, _copilot_line(tmp_path)
    )
    second = dict(_copilot_line(tmp_path))
    second["bash"] = f"{second['bash']} other"
    _add_entry(hook_file, second)
    record = install_ledger.current_install_record("", tmp_path)
    record.targets[0].digest = hashlib.sha256(hook_file.read_bytes()).hexdigest()
    looked: list[Path] = []
    real_is_link = _doctor_hooks.is_link

    def counting(path: Path) -> bool:
        looked.append(path)
        return real_is_link(path)

    monkeypatch.setattr(_doctor_hooks, "is_link", counting)

    hooks = _read_hooks(tmp_path, monkeypatch)

    assert len(hooks.argvs) == 2
    support = tmp_path / ".apothem"
    under = [path for path in looked if support in (path, *path.parents)]
    assert len(under) == len(dispatcher.relative_to(tmp_path).parts)


def test_doctor_names_a_merged_settings_file_behind_a_junction(
    runner: CliRunner, home: Path, tmp_path: Path
) -> None:
    # CodeBuddy merges its hooks into .codebuddy/settings.local.json. With the
    # folder swapped for a link to one outside the project, CodeBuddy still
    # runs the hooks there, so doctor must not report a clean pass.
    project = _project(tmp_path)
    _install(runner, "codebuddy", "--project", str(project))
    folder = project / ".codebuddy"
    outside = tmp_path / "outside-codebuddy"
    shutil.copytree(folder, outside)
    shutil.rmtree(folder)
    _link(folder, outside, folder=True)

    code, payload = _doctor(runner, "--project", str(project))
    plain = runner.invoke(main, ["doctor", "--project", str(project), "--no-color"])

    assert code == 0, payload
    messages = _unchecked(payload, "codebuddy")
    assert any(
        f"settings.local.json is reached through the link {folder}, so no hook "
        "in it was read" in message
        for message in messages
    ), messages
    # The fix ends with the exact update command, --project included, as
    # every other fix that runs update does.
    expected = _cmd_doctor._update_fix(
        "codebuddy", project, lead=_doctor_hook_text.LINK_FIX
    )
    assert expected in _hook_fixes(payload, "codebuddy")
    assert expected.startswith(_doctor_hook_text.LINK_FIX + " this command")
    _, _, command = expected.rpartition("then run doctor again: ")
    assert "update --harness codebuddy --project " in command
    assert str(project) in command
    assert "were not checked" in " ".join(plain.output.split())


@pytest.mark.parametrize("entry", ["link", "stray"])
def test_an_entry_the_install_did_not_write_in_the_hook_folder_has_its_own_fix(
    runner: CliRunner, home: Path, tmp_path: Path, entry: str
) -> None:
    # An update keeps a link or the operator's own .py file in the hook
    # folder, so the update fix never clears the note. Removing the entry does.
    project = _project(tmp_path)
    _install(runner, "codebuddy", "--project", str(project))
    [dispatcher] = (project / ".apothem" / "support").rglob("dispatch.py")
    if entry == "link":
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        planted = dispatcher.parent / "extra"
        _link(planted, elsewhere, folder=True)
        detail = "hold a link, extra,"
    else:
        planted = dispatcher.parent / "mine.py"
        planted.write_text("x = 1\n", encoding="utf-8")
        detail = "hold mine.py, which the install did not write"

    code, payload = _doctor(runner, "--project", str(project))

    assert code == 0, payload
    [message] = [m for m in _unchecked(payload, "codebuddy") if detail in m]
    fixes = [
        check["fix"]
        for check in payload["checks"]
        if check["code"] == "hook.unchecked" and check["message"] == message
    ]
    assert fixes == [_doctor_hook_text.FOLDER_ENTRY_FIX]

    # Following the fix clears the line.
    if entry == "link":
        planted.rmdir()  # removes the junction or link, not its target
    else:
        planted.unlink()
    code, payload = _doctor(runner, "--project", str(project))

    assert code == 0, payload
    assert _unchecked(payload, "codebuddy") == []
    assert _row(payload, "codebuddy")["hooks"]["failed"] == []


@pytest.mark.parametrize("second", [FileNotFoundError, PermissionError])
@pytest.mark.parametrize("follow_link", [False, True])
def test_an_open_that_fails_on_a_file_gone_keeps_its_own_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    follow_link: bool,
    second: type[OSError],
) -> None:
    # The file was removed (or shut off) after the look: the second look fails
    # too, and the open's own error is the one reported, not "not a regular
    # file". A followed look is made again without following only for a
    # junction to a file, never for these errors.
    path = tmp_path / "settings.json"
    path.write_text("{}", encoding="utf-8")
    real_look = _doctor_hook_text._look
    looks: list[bool] = []

    def look(name: Path, *, follow_link: bool) -> os.stat_result:
        looks.append(follow_link)
        if len(looks) == 1:
            return real_look(name, follow_link=follow_link)
        raise second(errno.ENOENT, "No such file", str(name))

    def gone(name: Path, flags: int) -> int:
        raise FileNotFoundError(errno.ENOENT, "No such file", str(name))

    monkeypatch.setattr(_doctor_hook_text, "_look", look)
    monkeypatch.setattr(_doctor_hook_text, "_open_descriptor", gone)

    with pytest.raises(FileNotFoundError) as raised:
        _doctor_hook_text.read_hook_file(path, follow_link=follow_link)
    assert not isinstance(raised.value, _doctor_hook_text.NotARegularFileError)
    assert looks == [follow_link, follow_link]


def test_a_project_second_look_does_not_follow_a_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # In a project a path swapped for a link to a regular file is still not a
    # regular file: the second look must not follow the link.
    path = tmp_path / "settings.json"
    path.write_text("{}", encoding="utf-8")
    real_look = _doctor_hook_text._look
    looks: list[bool] = []

    def look(name: Path, *, follow_link: bool) -> object:
        looks.append(follow_link)
        result = real_look(name, follow_link=follow_link)
        if len(looks) == 1 or follow_link:
            return result
        return _StatAs(result, st_mode=stat.S_IFLNK | 0o777)

    def denied(name: Path, flags: int) -> int:
        raise PermissionError(errno.EACCES, "Permission denied", str(name))

    monkeypatch.setattr(_doctor_hook_text, "_look", look)
    monkeypatch.setattr(_doctor_hook_text, "_open_descriptor", denied)

    with pytest.raises(_doctor_hook_text.NotARegularFileError):
        _doctor_hook_text.read_hook_file(path)
    assert looks == [False, False]


def test_a_project_second_look_that_fails_on_a_folder_step_is_not_made_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Only a followed look is made again without following it. A look that
    # did not follow and fails keeps the open's own error, even if a third
    # look would now find a folder.
    path = tmp_path / "settings.json"
    path.write_text("{}", encoding="utf-8")
    real_look = _doctor_hook_text._look
    looks: list[bool] = []

    def look(name: Path, *, follow_link: bool) -> object:
        looks.append(follow_link)
        if len(looks) == 1:
            return real_look(name, follow_link=follow_link)
        if len(looks) == 2:
            raise NotADirectoryError(errno.ENOTDIR, "Not a folder", str(name))
        return _StatAs(real_look(name, follow_link=False), st_mode=stat.S_IFDIR)

    def denied(name: Path, flags: int) -> int:
        raise PermissionError(errno.EACCES, "Permission denied", str(name))

    monkeypatch.setattr(_doctor_hook_text, "_look", look)
    monkeypatch.setattr(_doctor_hook_text, "_open_descriptor", denied)

    with pytest.raises(PermissionError) as raised:
        _doctor_hook_text.read_hook_file(path)
    assert not isinstance(raised.value, _doctor_hook_text.NotARegularFileError)
    assert looks == [False, False]


@pytest.mark.parametrize("fallback", ["link", "error"])
def test_a_followed_second_look_names_only_a_junction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fallback: str
) -> None:
    # A followed look that fails as on a junction to a file is made again
    # without following. A link to a file under the home (the dotfile case),
    # or a look that fails too, keeps the open's own error.
    path = tmp_path / "settings.json"
    path.write_text("{}", encoding="utf-8")
    real_look = _doctor_hook_text._look
    looks: list[bool] = []

    def look(name: Path, *, follow_link: bool) -> object:
        looks.append(follow_link)
        if len(looks) == 1:
            return real_look(name, follow_link=follow_link)
        if follow_link:
            raise NotADirectoryError(errno.ENOTDIR, "Not a folder", str(name))
        if fallback == "error":
            raise PermissionError(errno.EACCES, "Permission denied", str(name))
        return _StatAs(real_look(name, follow_link=False), st_mode=stat.S_IFLNK)

    def denied(name: Path, flags: int) -> int:
        raise PermissionError(errno.EACCES, "Permission denied", str(name))

    monkeypatch.setattr(_doctor_hook_text, "_look", look)
    monkeypatch.setattr(_doctor_hook_text, "_open_descriptor", denied)

    with pytest.raises(PermissionError) as raised:
        _doctor_hook_text.read_hook_file(path, follow_link=True)
    assert not isinstance(raised.value, _doctor_hook_text.NotARegularFileError)
    assert looks == [True, True, False]


@pytest.mark.skipif(
    sys.platform != "win32", reason="only Windows has junctions to a file"
)
def test_a_file_swapped_for_a_junction_to_a_file_is_named_when_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Under the home a link is followed, but Windows cannot follow a junction
    # to a file: the followed look fails, and the look at the link itself
    # finds a junction, so the file is named as not a regular file.
    import _winapi  # Windows only; a junction needs no privilege

    target = tmp_path / "real.json"
    target.write_text("{}", encoding="utf-8")
    path = tmp_path / "settings.json"
    _winapi.CreateJunction(str(target), str(path))
    real_look = _doctor_hook_text._look
    looks: list[bool] = []

    def look(name: Path, *, follow_link: bool) -> os.stat_result:
        looks.append(follow_link)
        if len(looks) == 1:  # a regular file when first looked at
            return real_look(target, follow_link=follow_link)
        return real_look(name, follow_link=follow_link)

    monkeypatch.setattr(_doctor_hook_text, "_look", look)

    with pytest.raises(_doctor_hook_text.NotARegularFileError) as raised:
        _doctor_hook_text.read_hook_file(path, follow_link=True)
    assert looks == [True, True, False]
    assert _doctor_hook_text.unread_reason(path, raised.value) == (
        f"{path} is not a regular file, so no hook in it was read"
    )
