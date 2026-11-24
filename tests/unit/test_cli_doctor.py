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

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

import apothem
from apothem.cli import _doctor_hook_text, _doctor_hooks, main
from apothem.harnesses._shared import install_driver, wrapper_factories
from apothem.lib import install_ledger

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
) -> tuple[Path, Path]:
    """Fake a GitHub Copilot project install whose hook file holds *entry*.

    *python_bin* is the interpreter the install record keeps; ``None`` is a
    record from a release that kept none.
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
            (hook_file, "native_hooks"),
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

    monkeypatch.setattr(_doctor_hooks.os, "scandir", scandir)


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
    # that Python instead, which doctor accepts.
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
    assert check["fix"].startswith(
        "Run <a Python outside the project> -m apothem followed by this "
        "command, then run doctor again: update --harness cursor --project "
    )


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
    monkeypatch.setattr(_doctor_hooks.json, "loads", lambda text: document)
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
    real = os.scandir

    def scandir(path: object) -> object:
        if os.path.normcase(str(path)) == os.path.normcase(str(dispatcher.parent)):
            raise PermissionError(13, "Permission denied", str(path))
        return real(path)

    monkeypatch.setattr(_doctor_hooks.os, "scandir", scandir)

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
    assert "not the Python the install recorded, which is inside the project" in (
        unchecked
    )
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
    data = bytes(range(256)) * (5 * 1024 * 1024 // 256 // 2)
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
