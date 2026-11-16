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
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

import apothem
from apothem.cli import _doctor_hooks, main
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


@pytest.mark.parametrize("harness", ["cursor", "github-copilot"])
def test_doctor_reports_a_project_hook_whose_interpreter_is_gone(
    runner: CliRunner,
    home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    harness: str,
) -> None:
    # The Python the install wrote into the hook lines was removed later. The
    # hooks cannot start, and doctor says so without starting anything.
    _as_windows(monkeypatch)
    gone = tmp_path / "removed-python" / "python.exe"
    monkeypatch.setattr(wrapper_factories, "resolve_python_bin", lambda: gone)
    project = _project(tmp_path)
    _install(runner, harness, "--project", str(project))

    code, payload = _doctor(runner, "--project", str(project))

    assert code == 1, payload
    failed = [check for check in payload["checks"] if check["status"] == "fail"]
    assert [check["code"] for check in failed] == ["hook.start_failed"]
    assert failed[0]["harness"] == harness
    # The command shown starts with the interpreter, not with PowerShell's "&".
    assert f"cannot start: {gone.as_posix()} " in failed[0]["message"]
    assert "the interpreter does not exist" in failed[0]["message"]


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
    [message] = _unchecked(payload, harness)
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
    edited: bool = False,
) -> tuple[Path, Path]:
    """Fake a GitHub Copilot project install whose hook file holds *entry*.

    With *edited*, the hook file changes after the install recorded it, the way
    a commit changes it, so the install's checksum of it no longer matches.
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
    if edited:
        hook_file.write_text(
            hook_file.read_text(encoding="utf-8") + "\n", encoding="utf-8"
        )
    record = SimpleNamespace(targets=targets)
    monkeypatch.setattr(
        install_ledger, "current_install_record", lambda package_key, root: record
    )
    return hook_file, dispatcher


def _read_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, windows: bool = False
) -> _doctor_hooks.RegisteredHooks:
    monkeypatch.setattr(_doctor_hooks, "_on_windows", lambda: windows)
    hooks = _doctor_hooks.registered_hooks("github_copilot", project_root=tmp_path)
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
            "runs &, not a Python Apothem runs under",
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


def _symlink(link: Path, target: Path, *, folder: bool = False) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=folder)
    except OSError:
        pytest.skip("this host cannot create a symbolic link")


def _link_folder(tmp_path: Path, dispatcher: Path) -> None:
    elsewhere = tmp_path / "elsewhere-lib"
    elsewhere.mkdir()
    _symlink(dispatcher.parent / "lib", elsewhere, folder=True)


def _venv_python(tmp_path: Path, dispatcher: Path) -> None:
    # A committed folder that looks like a virtual environment, whose python
    # links to the real one: started from there, Python would read the
    # folder's pyvenv.cfg and its .pth files.
    _symlink(tmp_path / "e" / "bin" / "python3", Path(sys.executable))
    (tmp_path / "e" / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("line", "edited", "change", "outcome", "detail"),
    [
        pytest.param(_DOUBLE, False, None, "start", None, id="apothem-line"),
        pytest.param(
            '"{other}" "{script}" --contract copilot',
            True,
            None,
            "unchecked",
            "not a Python Apothem runs under",
            id="another-python",
        ),
        pytest.param(
            '"{other}" "{script}" --contract copilot',
            False,
            None,
            "start",
            None,
            id="the-python-the-install-wrote",
        ),
        pytest.param(
            '"{tmp}/removed/python" "{script}" --contract copilot',
            False,
            None,
            "cannot start",
            "the interpreter does not exist",
            id="the-python-the-install-wrote-is-gone",
        ),
        pytest.param(
            '"{tmp}/removed/python" "{script}" --contract copilot',
            True,
            None,
            "unchecked",
            "not a Python Apothem runs under",
            id="an-unknown-python-is-not-looked-up",
        ),
        pytest.param(
            '"{tmp}/e/bin/python3" "{script}" --contract copilot',
            True,
            _venv_python,
            "unchecked",
            "not a Python Apothem runs under",
            id="a-link-to-the-python-is-not-it",
        ),
        pytest.param(
            '"{py}" -c "import os" "{script}" --contract copilot',
            False,
            None,
            "unchecked",
            "an option Apothem does not write",
            id="code-option",
        ),
        pytest.param(
            '"{py}" "{other}" "{script}" --contract copilot',
            False,
            None,
            "unchecked",
            "which this install did not write",
            id="another-script",
        ),
        pytest.param(
            '"{py}" "{tmp}/x/../.apothem/support/github-copilot/hooks/dispatch.py"'
            " --contract copilot",
            False,
            None,
            "unchecked",
            "which this install did not write",
            id="dot-dot",
        ),
        pytest.param(
            '"{py}" "{script}" --contract copilot --',
            False,
            None,
            "unchecked",
            "arguments Apothem does not write",
            id="end-of-options",
        ),
        pytest.param(
            '"{py}" "{script}" sessionStart --contract copilot',
            False,
            None,
            "unchecked",
            "arguments Apothem does not write",
            id="contract-not-first",
        ),
        pytest.param(
            _DOUBLE,
            False,
            _delete_dispatcher,
            "cannot start",
            "the hook script does not exist",
            id="dispatcher-gone",
        ),
        pytest.param(
            _DOUBLE,
            False,
            _plant_module,
            "unchecked",
            "hold json.py, which the install did not write",
            id="planted-module",
        ),
        pytest.param(
            _DOUBLE,
            False,
            _change_dispatcher,
            "unchecked",
            "changed after the install (dispatch.py)",
            id="changed-dispatcher",
        ),
        pytest.param(
            _DOUBLE, False, _link_folder, "unchecked", "hold a link", id="link"
        ),
    ],
)
def test_doctor_starts_a_project_hook_line_only_when_it_runs_known_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    line: str,
    edited: bool,
    change: object,
    outcome: str,
    detail: str | None,
) -> None:
    other = tmp_path / "other-python.exe"
    other.write_text("", encoding="utf-8")
    command = line.format(
        py=Path(sys.executable).as_posix(),
        script=_dispatcher(tmp_path, "github-copilot").as_posix(),
        other=other.as_posix(),
        tmp=tmp_path.as_posix(),
    )
    _, dispatcher = _fake_install(
        tmp_path, monkeypatch, {"type": "command", "bash": command}, edited=edited
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
