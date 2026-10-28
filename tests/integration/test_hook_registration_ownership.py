# SPDX-License-Identifier: MIT

"""Ownership of the native hook registrations, across all five adapters.

CodeBuddy, Devin Local (the Windsurf adapter), Cursor, Kiro and GitHub Copilot
each register Apothem's hooks in a project file the operator can also edit. An
entry is Apothem's when its command runs ``.apothem/support/[<harness>/]hooks/
dispatch.py --contract <id>``, whichever project path it was written under. These
tests drive the real manifest with the user home isolated per test
(``tests/conftest.py``) and assert that:

* an operator's own hook, even one that shares the dispatcher's file name inside
  the project or runs ``python -m apothem.conformity.gate``, survives install,
  update and uninstall;
* a project that is renamed, moved or cloned again keeps one set of entries;
* ``verify`` fails once Apothem's entries are gone;
* an uninstall that cannot read the file says so instead of reporting success;
* a path the shell would misread is refused before anything is written;
* an uninstall backs up an operator's file before it edits it, and a registration
  file left with nothing in it is deleted, after that backup;
* the Windows (PowerShell) forms run the dispatcher the same way the bash forms do.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver, wrapper_factories
from apothem.harnesses._shared.install_driver import MaterializationError
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class


@dataclass(frozen=True)
class Harness:
    """What differs between the five registrations."""

    public_id: str
    package_key: str
    file: str
    shape: str  # claude (nested handlers) | cursor | kiro (list) | copilot
    apothem_commands: int  # command strings one install puts in the file

    @property
    def is_native_hooks_mode(self) -> bool:
        return self.shape != "claude"


CODEBUDDY = Harness(
    "codebuddy", "codebuddy", ".codebuddy/settings.local.json", "claude", 2
)
WINDSURF = Harness("windsurf", "windsurf", ".devin/config.local.json", "claude", 2)
CURSOR = Harness("cursor", "cursor", ".cursor/hooks.json", "cursor", 1)
KIRO = Harness("kiro", "kiro", ".kiro/hooks/apothem.json", "kiro", 1)
COPILOT = Harness(
    "github-copilot", "github_copilot", ".github/hooks/apothem.json", "copilot", 4
)
ALL = pytest.mark.parametrize(
    "harness", [CODEBUDDY, WINDSURF, CURSOR, KIRO, COPILOT], ids=lambda h: h.public_id
)
NATIVE_FILES = pytest.mark.parametrize(
    "harness", [CURSOR, KIRO, COPILOT], ids=lambda h: h.public_id
)


def _adapter(harness: Harness):  # the adapter classes are generated
    return load_adapter_class(get_harness_entry(harness.public_id))()


def _project(tmp_path: Path, name: str = "project") -> Path:
    project = tmp_path / name
    project.mkdir()
    return project


def _file(harness: Harness, project: Path) -> Path:
    return project / harness.file


def _load(harness: Harness, project: Path) -> dict[str, object]:
    return json.loads(_file(harness, project).read_text(encoding="utf-8"))


def _commands(node: object) -> list[str]:
    """Return every command string anywhere in *node*, whichever vendor shape."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"command", "bash", "powershell"} and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_commands(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_commands(item))
    return found


def _apothems(node: object) -> list[str]:
    return [c for c in _commands(node) if "dispatch.py" in c and "--contract" in c]


def _lookalikes(project: Path) -> list[str]:
    """Return hooks an operator may have written that are not Apothem's."""
    root = project.resolve().as_posix()
    return [
        # The dispatcher's file name, inside the project, in the operator's own tree.
        f'"python3" "{root}/tools/hooks/dispatch.py" team-start',
        f'"python3" "{root}/scripts/conformity/gate.py" --check',
        # The module spellings the operator runs on purpose.
        "python -m apothem.conformity.gate --all --strict .",
        "python -m apothem.hooks.dispatch SessionStart",
    ]


def _operator_doc(harness: Harness, project: Path) -> dict[str, object]:
    first, second, third, fourth = _lookalikes(project)
    if harness.shape == "claude":

        def group(*commands: str, matcher: str | None = None) -> dict[str, object]:
            handlers = [{"type": "command", "command": c} for c in commands]
            return {**({"matcher": matcher} if matcher else {}), "hooks": handlers}

        return {
            "hooks": {
                "SessionStart": [group(first)],
                "Stop": [group(third, second)],
                "PostToolUse": [group(fourth, matcher="*")],
            }
        }
    if harness.shape == "cursor":
        return {
            "version": 1,
            "hooks": {
                "sessionStart": [{"command": first}],
                "afterFileEdit": [{"command": third}, {"command": "echo keep"}],
                "stop": [{"command": second}],
                "preCompact": [{"command": fourth}],
            },
        }
    if harness.shape == "kiro":
        return {
            "version": "v1",
            "hooks": [
                {
                    "name": f"team-{i}",
                    "trigger": "SessionStart",
                    "action": {"type": "command", "command": command},
                }
                for i, command in enumerate((first, second, third, fourth))
            ],
        }
    return {
        "version": 1,
        "hooks": {
            "sessionStart": [{"type": "command", "bash": first}],
            "postToolUse": [{"type": "command", "bash": fourth}],
            "agentStop": [{"type": "command", "bash": third}],
            "preToolUse": [{"type": "command", "bash": second}],
        },
    }


def _seed(harness: Harness, project: Path) -> dict[str, object]:
    doc = _operator_doc(harness, project)
    target = _file(harness, project)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def _empty_registration(harness: Harness) -> dict[str, object]:
    if harness.shape == "kiro":
        return {"version": "v1", "hooks": []}
    return {"hooks": {}} if harness.shape == "claude" else {"version": 1, "hooks": {}}


# --- an operator's lookalike hooks ---------------------------------------------------


@ALL
def test_an_operators_lookalike_hooks_inside_the_project_survive_every_step(
    harness: Harness, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    seed = _seed(harness, project)
    mine = _lookalikes(project)
    adapter = _adapter(harness)

    for step in (adapter.install, adapter.update):
        step({}, project=project)
        doc = _load(harness, project)
        assert all(c in _commands(doc) for c in mine), step.__name__
        assert len(_apothems(doc)) == harness.apothem_commands, step.__name__

    adapter.uninstall(project=project)

    assert sorted(_commands(_load(harness, project))) == sorted(_commands(seed))
    assert _apothems(_load(harness, project)) == []


# --- a renamed, moved or cloned project --------------------------------------------


@ALL
def test_a_moved_project_keeps_one_set_of_entries(
    harness: Harness, tmp_path: Path
) -> None:
    first = _project(tmp_path, "first")
    _adapter(harness).install({}, project=first)
    moved = tmp_path / "renamed"
    shutil.copytree(first, moved)

    _adapter(harness).install({}, project=moved)

    text = _file(harness, moved).read_text(encoding="utf-8")
    assert len(_apothems(_load(harness, moved))) == harness.apothem_commands
    assert moved.resolve().as_posix() in text
    assert first.resolve().as_posix() not in text, "the old checkout's entries went"

    _adapter(harness).uninstall(project=moved)
    left = _file(harness, moved)
    assert not left.exists() or _apothems(_load(harness, moved)) == []


@NATIVE_FILES
def test_a_teammates_entry_in_a_committed_file_is_replaced_not_added_to(
    harness: Harness, tmp_path: Path
) -> None:
    mine = _project(tmp_path, "mine")
    _adapter(harness).install({}, project=mine)
    # The file is committed; a teammate's checkout holds it with their paths.
    theirs = _project(tmp_path, "theirs")
    target = _file(harness, theirs)
    target.parent.mkdir(parents=True)
    text = _file(harness, mine).read_text(encoding="utf-8")
    target.write_text(
        text.replace(mine.resolve().as_posix(), "/home/mate/work/app"), encoding="utf-8"
    )

    _adapter(harness).install({}, project=theirs)

    assert len(_apothems(_load(harness, theirs))) == harness.apothem_commands
    assert "/home/mate/work/app" not in target.read_text(encoding="utf-8")


# --- verify -------------------------------------------------------------------------


@ALL
def test_verify_fails_once_apothems_entries_are_gone(
    harness: Harness, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    adapter = _adapter(harness)
    adapter.install({}, project=project)
    assert adapter.verify(project=project) is True

    # Reverted by `git checkout`, deleted by hand, or lost in a fresh clone.
    _file(harness, project).write_text(
        json.dumps(_empty_registration(harness)), encoding="utf-8"
    )
    assert adapter.verify(project=project) is False

    # An operator's lookalike hooks are not Apothem's either.
    _seed(harness, project)
    assert adapter.verify(project=project) is False

    adapter.install({}, project=project)
    assert adapter.verify(project=project) is True


# --- an uninstall that cannot read the file -------------------------------------------


@ALL
def test_an_uninstall_that_cannot_read_the_file_says_so(
    harness: Harness, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    _seed(harness, project)  # the operator's own entries keep the file in play
    _adapter(harness).install({}, project=project)
    target = _file(harness, project)
    edited = "// edited by hand\n" + target.read_text(encoding="utf-8")
    target.write_text(edited, encoding="utf-8")

    results = install_driver.run_uninstall(harness.package_key, project_root=project)

    [result] = [r for r in results if r.path == str(target)]
    assert result.outcome == "skipped", result
    assert "no Apothem hook to remove" not in result.message
    assert target.read_text(encoding="utf-8") == edited, "the file is left as it is"
    if harness.is_native_hooks_mode:
        assert "by hand" in result.message


# --- paths the shell would misread ------------------------------------------------------


def _try_mkdir(parent: Path, name: str) -> Path:
    path = parent / name
    try:
        path.mkdir()
    except OSError:
        pytest.skip(f"this file system cannot hold a directory named {name!r}")
    return path


@ALL
@pytest.mark.parametrize("name", ["dollar$x", "tick`x", 'quote"x'])
def test_a_project_path_the_shell_would_misread_is_refused_before_any_write(
    harness: Harness, tmp_path: Path, name: str
) -> None:
    project = _try_mkdir(tmp_path, name)

    with pytest.raises(MaterializationError) as refused:
        _adapter(harness).install({}, project=project)

    [error] = refused.value.run.errors
    assert name in error.message
    assert error.detail["fix"]
    assert not _file(harness, project).exists()
    assert not (project / ".apothem").exists(), "nothing was written"


@ALL
def test_a_dry_run_reports_the_same_refusal(harness: Harness, tmp_path: Path) -> None:
    project = _try_mkdir(tmp_path, "dollar$x")

    with pytest.raises(MaterializationError):
        _adapter(harness).preview({}, project=project)

    assert not (project / ".apothem").exists()


@ALL
@pytest.mark.parametrize("name", ["my proj", "o'brien"])
def test_a_space_or_an_apostrophe_in_the_path_is_fine(
    harness: Harness, tmp_path: Path, name: str
) -> None:
    project = _try_mkdir(tmp_path, name)
    _adapter(harness).install({}, project=project)
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "APOTHEM_HOOK_STATE_DIR": str(tmp_path / "s"),
    }

    for command in _apothems(_load(harness, project)):
        if command.startswith("& "):
            command = command[2:]
        done = subprocess.run(
            shlex.split(command),
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            cwd=str(project),
            timeout=60,
            check=False,
        )
        assert done.returncode == 0, (command, done.stderr)


def test_an_interpreter_path_the_shell_would_misread_is_refused(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    with (
        install_driver.content_tokens(PYTHON_BIN="/opt/py$thon/bin/python"),
        pytest.raises(MaterializationError) as refused,
    ):
        install_driver.run_install("kiro", project_root=project)

    [error] = refused.value.run.errors
    assert "PYTHON_BIN" in error.message
    assert "'$'" in error.message
    assert not (project / ".kiro").exists()


# --- backups and an emptied file ---------------------------------------------------------


@NATIVE_FILES
def test_an_uninstall_backs_up_the_file_it_edits(
    harness: Harness, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    _seed(harness, project)
    _adapter(harness).install({}, project=project)
    target = _file(harness, project)
    before = target.read_bytes()

    results = install_driver.run_uninstall(harness.package_key, project_root=project)

    [result] = [r for r in results if r.path == str(target)]
    assert result.outcome == "updated", result
    assert result.backup_path is not None
    assert Path(result.backup_path).read_bytes() == before
    assert before != target.read_bytes()


def test_a_cursor_file_the_operator_left_with_nothing_in_it_is_deleted_after_a_backup(
    tmp_path: Path,
) -> None:
    # native_hooks does not record who created the file: a registration with no
    # entries left is deleted, and the backup keeps what it held.
    project = _project(tmp_path)
    target = _file(CURSOR, project)
    target.parent.mkdir(parents=True)
    target.write_text('{"version": 1, "hooks": {}}\n', encoding="utf-8")
    _adapter(CURSOR).install({}, project=project)
    before = target.read_bytes()

    results = install_driver.run_uninstall("cursor", project_root=project)

    [result] = [r for r in results if r.path == str(target)]
    assert not target.exists()
    assert result.backup_path is not None
    assert Path(result.backup_path).read_bytes() == before


# --- the Windows forms ---------------------------------------------------------------------


def _pwsh() -> str:
    exe = shutil.which("pwsh")
    if exe is None:
        pytest.skip("PowerShell 7 (pwsh) is not installed")
    probe = subprocess.run(
        [exe, "-NoProfile", "-Command", "exit 0"],
        capture_output=True,
        timeout=60,
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip("pwsh does not start on this host")
    return exe


def _run_in(shell: list[str], tmp_path: Path, project: Path, payload: object) -> str:
    done = subprocess.run(
        shell,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONUTF8": "1",
            "APOTHEM_HOOK_STATE_DIR": str(tmp_path / "state"),
            "APOTHEM_HOOKS_DISABLE": "",
        },
        cwd=str(project),
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


def test_cursors_windows_command_runs_under_powershell_like_the_posix_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pwsh = _pwsh()
    monkeypatch.setattr(wrapper_factories, "_on_windows", lambda: True)
    project = _project(tmp_path)
    _adapter(CURSOR).install({}, project=project)
    [command] = _commands(_load(CURSOR, project))
    assert command.startswith('& "'), "the call operator, rendered for a Windows host"
    payload = {
        "session_id": "ps-1",
        "conversation_id": "ps-1",
        "hook_event_name": "sessionStart",
        "workspace_roots": [str(project)],
    }

    posix = _run_in(shlex.split(command.removeprefix("& ")), tmp_path, project, payload)
    # A different session id, so the per-session marker does not silence the second.
    other = {**payload, "session_id": "ps-2", "conversation_id": "ps-2"}
    powershell = _run_in(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
        tmp_path,
        project,
        other,
    )

    assert json.loads(posix)["additional_context"].strip()
    assert json.loads(powershell) == json.loads(posix)


def test_copilots_powershell_field_runs_under_powershell_like_the_bash_one(
    tmp_path: Path,
) -> None:
    pwsh = _pwsh()
    project = _project(tmp_path)
    _adapter(COPILOT).install({}, project=project)
    session_start = _load(COPILOT, project)["hooks"]["sessionStart"][0]
    payload = {"sessionId": "cp-ps", "timestamp": 1, "cwd": str(project)}

    posix = _run_in(shlex.split(session_start["bash"]), tmp_path, project, payload)
    powershell = _run_in(
        [
            pwsh,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            session_start["powershell"],
        ],
        tmp_path,
        project,
        payload,
    )

    assert set(json.loads(posix)) == {"additionalContext"}
    assert json.loads(powershell) == json.loads(posix)
