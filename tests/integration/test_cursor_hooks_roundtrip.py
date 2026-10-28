# SPDX-License-Identifier: MIT

"""Cursor installs, verifies, updates and uninstalls its native hook.

Cursor reads hooks from ``<project>/.cursor/hooks.json``: one file, which a team
edits and commits, holding a version and a map from camelCase event to a flat
array of ``{command, type, timeout, ...}`` entries. The install merges one
``sessionStart`` entry into it (the ``native_hooks`` mode, operator-owned) and
puts the dispatcher in the support tree under
``<project>/.apothem/support/cursor/hooks/``. These tests drive the real manifest
with the user home isolated per test (``tests/conftest.py``) and assert the exact
bytes written, that the operator's own entries and keys survive every step, that a
file Apothem would have to damage is refused, that an uninstall finds Apothem's
entry by what its command runs, with or without an install record, and that the
command is silent the second time it runs in one session.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from string import Template

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver, wrapper_factories
from apothem.harnesses._shared.install_driver import MaterializationError
from apothem.harnesses._shared.wrapper_factories import (
    python_bin_tokens,
    python_call_tokens,
)
from apothem.lib import install_ledger
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class
from apothem.lib.propagation import load_manifest

_SRC = Path(install_driver.APOTHEM_SRC)
_TEMPLATE = _SRC / "harnesses" / "cursor" / "templates" / "apothem-hooks.json"

_OPERATOR_HOOK = {
    "command": ".cursor/hooks/audit.sh",
    "matcher": "Shell",
    "failClosed": True,
}
_OPERATOR_STOP = {"command": ".cursor/hooks/stop.sh", "loop_limit": 3}


def _adapter(public_id: str = "cursor"):  # the adapter classes are generated
    return load_adapter_class(get_harness_entry(public_id))()


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project


def _file(project: Path) -> Path:
    return project / ".cursor" / "hooks.json"


def _support(project: Path) -> Path:
    return project / ".apothem" / "support" / "cursor" / "hooks"


def _expected_text(project: Path) -> str:
    """Return the registration the install writes, rendered the way it renders."""
    tokens = {**python_call_tokens(), "PROJECT_ROOT": project.resolve().as_posix()}
    return Template(_TEMPLATE.read_text(encoding="utf-8")).substitute(tokens)


def _load(project: Path) -> dict[str, object]:
    return json.loads(_file(project).read_text(encoding="utf-8"))


def _hooks(doc: dict[str, object]) -> list[dict[str, object]]:
    hooks = doc["hooks"]
    assert isinstance(hooks, dict)
    return [hook for listed in hooks.values() for hook in listed]


def _ours(doc: dict[str, object]) -> list[str]:
    """Return the command of every Apothem entry in *doc*."""
    return [
        str(hook["command"])
        for hook in _hooks(doc)
        if "dispatch.py" in str(hook["command"])
    ]


def _write_operator_file(project: Path) -> dict[str, object]:
    operator: dict[str, object] = {
        "version": 1,
        "x-team": {"owner": "platform"},
        "hooks": {
            "sessionStart": [{"command": ".cursor/hooks/session.sh"}],
            "beforeShellExecution": [_OPERATOR_HOOK],
            "stop": [_OPERATOR_STOP],
        },
    }
    _file(project).parent.mkdir(parents=True)
    _file(project).write_text(json.dumps(operator, indent=2) + "\n", encoding="utf-8")
    return operator


def _argv(command: str) -> list[str]:
    """Return *command* as the argument vector a shell would run, call operator off."""
    return shlex.split(command.removeprefix("& "))


def _env(state: Path, **extra: str) -> dict[str, str]:
    env = {**os.environ, "PYTHONUTF8": "1", "APOTHEM_HOOK_STATE_DIR": str(state)}
    env.pop("APOTHEM_HOOKS_DISABLE", None)
    env.update(extra)
    return env


def _run(command: str, payload: dict[str, object], project: Path, state: Path) -> str:
    """Run *command* the way Cursor runs a hook command and return its stdout."""
    done = subprocess.run(
        _argv(command),
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_env(state),
        cwd=str(project),
        timeout=60,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


def _start_payload(project: Path, conversation: str = "c-1") -> dict[str, object]:
    return {
        "conversation_id": conversation,
        "session_id": conversation,
        "generation_id": "g-1",
        "hook_event_name": "sessionStart",
        "workspace_roots": [str(project)],
        "is_background_agent": False,
        "composer_mode": "agent",
    }


# --- what is written -------------------------------------------------------------


def test_install_writes_the_exact_registration(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    data = _file(project).read_bytes()
    assert data == _expected_text(project).encode("utf-8")
    assert b"\r" not in data, "LF only"
    assert not data.startswith(b"\xef\xbb\xbf"), "no BOM"
    assert b"${" not in data, "every token is rendered"


def test_only_session_start_is_registered_with_the_documented_keys(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    doc = _load(project)

    assert doc["version"] == 1
    assert list(doc["hooks"]) == ["sessionStart"]
    [hook] = _hooks(doc)
    # Only keys Cursor's hooks page lists for a command hook; sessionStart is not
    # matched, and a hook that fails must not block (no failClosed).
    assert set(hook) == {"type", "command", "timeout"}
    assert hook["type"] == "command"
    assert "hooks" not in hook, (
        "a flat entry is never given a Claude-style handler list"
    )


def test_the_command_runs_the_installed_dispatcher_under_the_contract(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    python = python_bin_tokens()["PYTHON_BIN"]
    dispatcher = (
        project.resolve() / ".apothem/support/cursor/hooks/dispatch.py"
    ).as_posix()
    operator = python_call_tokens()["CALL_OP"]
    assert _ours(_load(project)) == [
        f'{operator}"{python}" "{dispatcher}" --contract cursor sessionStart'
    ]
    assert Path(dispatcher).is_file()


@pytest.mark.parametrize(("windows", "prefix"), [(True, "& "), (False, "")])
def test_the_call_operator_is_rendered_for_the_host_that_installs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, windows: bool, prefix: str
) -> None:
    # Cursor's desktop app runs hook commands through PowerShell on Windows, where
    # a line that starts with a quoted program path is not a call (design inference
    # from PowerShell syntax; the vendor page names the shell, not the quoting).
    monkeypatch.setattr(wrapper_factories, "_on_windows", lambda: windows)
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    [command] = _ours(_load(project))
    assert command.startswith(f'{prefix}"')
    assert command.startswith('& "') is windows


def test_install_places_the_dispatcher_and_the_shim_in_the_support_tree(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    support = _support(project)
    for name in (
        "dispatch.py",
        "session_start_bootstrap.py",
        "lib/vendor_contract.py",
        "lib/state_dir.py",
        "messages/sessionstart.md",
    ):
        assert (support / name).read_bytes() == (_SRC / "hooks" / name).read_bytes(), (
            name
        )
    assert not (support / "README.md").exists()


def test_no_user_level_hook_file_is_written(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    assert not (Path.home() / ".cursor" / "hooks.json").exists()
    assert not (project / ".claude").exists()


# --- the command, run the way Cursor runs it -------------------------------------


def test_the_registered_command_works_when_run_the_way_cursor_runs_it(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    [command] = _ours(_load(project))

    out = _run(command, _start_payload(project), project, tmp_path / "state")

    output = json.loads(out)
    # Cursor reads {env, additional_context} from sessionStart; the dispatcher
    # sends the context and nothing that could be read as a decision.
    assert set(output) == {"additional_context"}
    assert output["additional_context"].strip()


def test_session_start_speaks_once_per_session(tmp_path: Path) -> None:
    # Cursor also loads Claude Code's hooks and runs every matching hook from
    # every source, so a sessionStart command can fire twice for one session. The
    # contract records a marker per session.
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    [command] = _ours(_load(project))
    state = tmp_path / "state"

    assert _run(command, _start_payload(project, "c-1"), project, state).strip()
    assert _run(command, _start_payload(project, "c-1"), project, state) == ""
    assert _run(command, _start_payload(project, "c-2"), project, state).strip()


def test_the_registered_command_stays_silent_and_fails_open(tmp_path: Path) -> None:
    # A hook that cannot read its input, or that an operator switched off, must
    # still exit 0 and say nothing Cursor could mistake for a decision.
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    [command] = _ours(_load(project))

    garbage = subprocess.run(
        _argv(command),
        input="not json",
        capture_output=True,
        text=True,
        env=_env(tmp_path / "s"),
        cwd=str(project),
        timeout=60,
        check=False,
    )
    assert garbage.returncode == 0, garbage.stderr
    disabled = subprocess.run(
        _argv(command),
        input=json.dumps(_start_payload(project)),
        capture_output=True,
        text=True,
        env=_env(tmp_path / "s2", APOTHEM_HOOKS_DISABLE="1"),
        cwd=str(project),
        timeout=60,
        check=False,
    )
    assert disabled.returncode == 0, disabled.stderr
    assert disabled.stdout == ""


# --- the operator's file ---------------------------------------------------------


def test_operator_entries_and_keys_survive_install_update_and_uninstall(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    operator = _write_operator_file(project)

    _adapter().install({}, project=project)
    merged = _load(project)
    assert merged["x-team"] == operator["x-team"]
    assert merged["version"] == 1
    assert merged["hooks"]["beforeShellExecution"] == [_OPERATOR_HOOK]
    assert merged["hooks"]["stop"] == [_OPERATOR_STOP]
    # The operator's own sessionStart entry stays first; Apothem's follows it.
    session = merged["hooks"]["sessionStart"]
    assert session[0] == {"command": ".cursor/hooks/session.sh"}
    assert len(session) == 2
    assert len(_ours(merged)) == 1

    installed = _file(project).read_bytes()
    _adapter().update({}, project=project)
    assert _file(project).read_bytes() == installed, "update is idempotent"

    _adapter().uninstall(project=project)
    assert _load(project) == operator
    assert not _support(project).exists()


def test_uninstall_deletes_a_file_apothem_created(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    assert _file(project).is_file()

    _adapter().uninstall(project=project)

    assert not _file(project).exists()
    assert not _support(project).exists()


def test_uninstall_without_an_install_record_still_finds_the_hook(
    tmp_path: Path,
) -> None:
    # The uninstall renders the template without the install-time interpreter and
    # call-operator tokens, so ownership has to come from what the command runs:
    # the dispatcher under the project's support tree.
    project = _project(tmp_path)
    operator = _write_operator_file(project)
    _adapter().install({}, project=project)
    ledger = install_ledger.ledger_path("cursor")
    assert ledger.is_file()
    ledger.unlink()

    _adapter().uninstall(project=project)

    assert _load(project) == operator
    assert "dispatch.py" not in _file(project).read_text(encoding="utf-8")


def test_uninstall_without_a_record_deletes_the_file_it_created(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    install_ledger.ledger_path("cursor").unlink()

    _adapter().uninstall(project=project)

    assert not _file(project).exists()


@pytest.mark.parametrize("windows", [True, False])
def test_uninstall_finds_the_hook_whichever_form_the_host_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, windows: bool
) -> None:
    # A file written on a Windows host starts its command with "& "; the removal
    # reads the dispatcher path, not the prefix.
    monkeypatch.setattr(wrapper_factories, "_on_windows", lambda: windows)
    project = _project(tmp_path)
    operator = _write_operator_file(project)
    _adapter().install({}, project=project)

    _adapter().uninstall(project=project)

    assert _load(project) == operator


def test_a_hook_that_runs_another_dispatcher_is_not_removed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    mine = {
        "command": '"/usr/bin/python3" "/opt/team/hooks/dispatch.py" SessionStart',
    }
    _file(project).parent.mkdir(parents=True)
    _file(project).write_text(
        json.dumps({"version": 1, "hooks": {"sessionStart": [mine]}}), encoding="utf-8"
    )

    _adapter().install({}, project=project)
    assert mine in _hooks(_load(project))
    _adapter().uninstall(project=project)

    assert _hooks(_load(project)) == [mine]


def test_a_second_install_does_not_duplicate_the_hook(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    first = _file(project).read_bytes()
    _adapter().install({}, project=project)

    assert _file(project).read_bytes() == first
    assert len(_ours(json.loads(first))) == 1


def test_a_file_with_no_hooks_key_keeps_its_keys_and_gains_the_hook(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _file(project).parent.mkdir(parents=True)
    _file(project).write_text('{"version": 1, "x-team": true}', encoding="utf-8")

    _adapter().install({}, project=project)

    doc = _load(project)
    assert doc["x-team"] is True
    assert len(_ours(doc)) == 1


@pytest.mark.parametrize(
    "text",
    [
        '{\n  // team notes\n  "version": 1,\n  "hooks": {}\n}\n',
        '{"version": 1, "hooks": {},}',
        '{"version": 1, "hooks": [{"command": "x"}]}',
        "[]",
    ],
    ids=["comments", "trailing-comma", "other-shape", "not-an-object"],
)
def test_a_file_that_cannot_be_merged_into_losslessly_is_refused(
    tmp_path: Path, text: str
) -> None:
    # .cursor/hooks.json is the operator's file: unlike the Apothem-owned
    # apothem.json files of Kiro and Copilot, it is never replaced.
    project = _project(tmp_path)
    _file(project).parent.mkdir(parents=True)
    _file(project).write_text(text, encoding="utf-8")

    with pytest.raises(MaterializationError, match="cannot add its hooks"):
        _adapter().install({}, project=project)

    assert _file(project).read_text(encoding="utf-8") == text
    # The install rolls back: nothing else of Apothem's is left in the project.
    assert sorted(p.name for p in project.rglob("*") if p.is_file()) == ["hooks.json"]
    _adapter().uninstall(project=project)
    assert _file(project).read_text(encoding="utf-8") == text


def test_the_cli_reports_a_refused_hook_file_as_config_unparseable(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _file(project).parent.mkdir(parents=True)
    commented = '{\n  // notes\n  "version": 1\n}\n'
    _file(project).write_text(commented, encoding="utf-8")

    result = CliRunner().invoke(
        main, ["install", "--harness", "cursor", "--project", str(project), "--json"]
    )

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "config.unparseable"
    assert "re-run" in error["fix"]
    assert _file(project).read_text(encoding="utf-8") == commented


def test_the_refusal_shows_in_a_dry_run(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _file(project).parent.mkdir(parents=True)
    commented = '{\n  // notes\n  "version": 1\n}\n'
    _file(project).write_text(commented, encoding="utf-8")

    run = _adapter().preview({}, project=project)

    preview = next(r for r in run.results if r.path == str(_file(project)))
    assert preview.outcome == "error"
    assert preview.detail["code"] == "config.unparseable"
    assert str(_file(project)) in preview.message
    assert _file(project).read_text(encoding="utf-8") == commented


# --- the support trees of the adapters that share a project ----------------------


def test_each_adapter_keeps_its_own_support_tree(tmp_path: Path) -> None:
    # One shared tree would let either uninstall remove the dispatcher the other
    # still runs, and make each adapter read as installed after the other's.
    project = _project(tmp_path)
    for public_id in ("cursor", "windsurf", "github-copilot"):
        _adapter(public_id).install({}, project=project)

    _adapter("cursor").uninstall(project=project)

    assert not _support(project).exists()
    assert not _file(project).exists()
    assert (project / ".apothem/support/windsurf/hooks/dispatch.py").is_file()
    assert (project / ".apothem/support/github-copilot/hooks/dispatch.py").is_file()
    assert _adapter("cursor").is_installed(project=project) is False
    assert _adapter("windsurf").is_installed(project=project) is True


# --- preview and verify ------------------------------------------------------------


def test_dry_run_writes_nothing_and_previews_the_rendered_registration(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    run = _adapter().preview({}, project=project)

    assert not _file(project).exists()
    assert not _support(project).exists()
    preview = {r.path: r for r in run.results}[str(_file(project))]
    assert preview.operation == "native_hooks"
    assert preview.outcome == "created"
    assert preview.detail["ownership_class"] == "operator-owned"
    diff = preview.detail["diff"]
    assert "--contract cursor" in diff
    assert "${PYTHON_BIN}" not in diff
    assert "${CALL_OP}" not in diff
    assert python_bin_tokens()["PYTHON_BIN"] in diff


def test_dry_run_after_an_install_reports_no_change(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    run = _adapter().preview({}, project=project)

    assert {r.path: r for r in run.results}[str(_file(project))].outcome == "unchanged"


def test_verify_reads_the_registration(tmp_path: Path) -> None:
    project = _project(tmp_path)
    adapter = _adapter()
    assert adapter.verify(project=project) is False
    adapter.install({}, project=project)
    assert adapter.verify(project=project) is True

    _file(project).write_text("{ not json", encoding="utf-8")
    assert adapter.verify(project=project) is False


# --- the manifest ------------------------------------------------------------------


def test_the_manifest_entries_for_hooks() -> None:
    entries = {e.target: e for e in load_manifest()["cursor"].install}
    support = entries["${PROJECT_ROOT}/.apothem/support/cursor/hooks/"]
    assert (support.source, support.mode) == ("hooks/", "merge_tree_entries")
    assert support.ownership_class == "apothem-owned"
    registration = entries["${PROJECT_ROOT}/.cursor/hooks.json"]
    assert registration.mode == "native_hooks"
    assert registration.ownership_class == "operator-owned"
    assert registration.source == "harnesses/cursor/templates/apothem-hooks.json"
