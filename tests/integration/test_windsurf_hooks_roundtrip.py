# SPDX-License-Identifier: MIT

"""Windsurf (Devin Local) installs, verifies, updates and uninstalls its native hooks.

Devin Local runs hook commands from the ``hooks`` key of its config files; the
install registers Apothem's SessionStart and PostToolUse in the local override
``<project>/.devin/config.local.json`` and puts the dispatcher in the support tree
under ``<project>/.apothem/support/windsurf/hooks/``. These tests drive the real
manifest with the user home isolated per test (``tests/conftest.py``) and assert
the exact bytes written, that the operator's own entries survive every step, that
an uninstall removes the Apothem handlers by what their command runs, with or
without an install record, and that the SessionStart command is silent the second
time it runs in one session.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from string import Template

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.wrapper_factories import python_bin_tokens
from apothem.lib import install_ledger
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class
from apothem.lib.propagation import load_manifest

_SRC = Path(install_driver.APOTHEM_SRC)
_TEMPLATE = _SRC / "harnesses" / "windsurf" / "templates" / "config-local.json"

_OPERATOR_HOOK = {"type": "command", "command": "echo operator-post-tool"}
_OPERATOR_PRE = {"type": "command", "command": "bash scripts/guard.sh"}


def _adapter(public_id: str = "windsurf"):  # the adapter classes are generated
    return load_adapter_class(get_harness_entry(public_id))()


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project


def _config(project: Path) -> Path:
    return project / ".devin" / "config.local.json"


def _support(project: Path) -> Path:
    return project / ".apothem" / "support" / "windsurf" / "hooks"


def _expected_text(project: Path) -> str:
    """Return the registration the install writes, rendered the way it renders."""
    tokens = {
        **python_bin_tokens(),
        "PROJECT_ROOT": project.resolve().as_posix(),
    }
    return Template(_TEMPLATE.read_text(encoding="utf-8")).substitute(tokens)


def _load(project: Path) -> dict[str, object]:
    return json.loads(_config(project).read_text(encoding="utf-8"))


def _commands(config: dict[str, object]) -> list[str]:
    hooks = config["hooks"]
    assert isinstance(hooks, dict)
    return [
        handler["command"]
        for groups in hooks.values()
        for group in groups
        for handler in group["hooks"]
    ]


def _write_operator_file(project: Path) -> dict[str, object]:
    operator: dict[str, object] = {
        "permissions": {"allow": ["read(./docs)"]},
        "hooks": {
            "PostToolUse": [{"hooks": [_OPERATOR_HOOK]}],
            "PreToolUse": [{"matcher": "exec", "hooks": [_OPERATOR_PRE]}],
        },
    }
    _config(project).parent.mkdir(parents=True)
    _config(project).write_text(json.dumps(operator, indent=2) + "\n", encoding="utf-8")
    return operator


def _run(command: str, payload: dict[str, object], project: Path, state: Path) -> str:
    """Run *command* the way Devin runs a hook command and return its stdout."""
    env = {**os.environ, "PYTHONUTF8": "1", "APOTHEM_HOOK_STATE_DIR": str(state)}
    env.pop("APOTHEM_HOOKS_DISABLE", None)
    done = subprocess.run(
        shlex.split(command),
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(project),
        timeout=60,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


# --- what is written -------------------------------------------------------------


def test_install_writes_the_exact_registration(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    data = _config(project).read_bytes()
    assert data == _expected_text(project).encode("utf-8")
    assert b"\r" not in data, "LF only"
    assert not data.startswith(b"\xef\xbb\xbf"), "no BOM"
    assert b"${" not in data, "every token is rendered"


def test_only_the_events_devin_delivers_are_registered(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    hooks = _load(project)["hooks"]
    assert sorted(hooks) == ["PostToolUse", "SessionStart"]
    for groups in hooks.values():
        for group in groups:
            # Devin's matcher is a regex and an omitted one matches all; "*" is
            # not a valid regex, so none is written.
            assert "matcher" not in group
            for handler in group["hooks"]:
                # Only the keys Devin's hooks page lists for a command hook.
                assert set(handler) == {"type", "command", "timeout"}
                assert handler["type"] == "command"
    assert "PreToolUse" not in hooks, "Devin documents no context channel there"


def test_each_command_runs_the_installed_dispatcher_under_the_contract(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    python = python_bin_tokens()["PYTHON_BIN"]
    dispatcher = (
        project.resolve() / ".apothem/support/windsurf/hooks/dispatch.py"
    ).as_posix()
    assert _commands(_load(project)) == [
        f'"{python}" "{dispatcher}" --contract devin SessionStart',
        f'"{python}" "{dispatcher}" --contract devin PostToolUse '
        "posttooluse-proactive-compaction",
    ]
    assert Path(dispatcher).is_file()


def test_install_places_the_dispatcher_and_the_shim_in_the_support_tree(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    support = _support(project)
    for name in (
        "dispatch.py",
        "session_start_bootstrap.py",
        "proactive_compaction_tracker.py",
        "lib/vendor_contract.py",
        "lib/state_dir.py",
        "messages/sessionstart.md",
        "messages/posttooluse-proactive-compaction.md",
    ):
        assert (support / name).read_bytes() == (_SRC / "hooks" / name).read_bytes(), (
            name
        )
    assert not (support / "README.md").exists()


def test_the_hook_files_stay_out_of_the_shared_config(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    for shared in ("config.json", "hooks.v1.json", "hooks.json"):
        assert not (project / ".devin" / shared).exists(), shared
    assert not (project / ".claude").exists()
    assert _config(project).is_file()


# --- the commands, run the way Devin runs them -----------------------------------


def test_the_registered_commands_work_when_run_the_way_devin_runs_them(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    start, tool = _commands(_load(project))
    state = tmp_path / "state"

    out = _run(
        start,
        {
            "hook_event_name": "SessionStart",
            "session_id": "devin-1",
            "source": "startup",
            "cwd": str(project),
        },
        project,
        state,
    )
    envelope = json.loads(out)
    assert set(envelope) == {"hookSpecificOutput"}, "advisory only: no decision"
    specific = envelope["hookSpecificOutput"]
    assert specific["hookEventName"] == "SessionStart"
    assert specific["additionalContext"].strip()

    post = _run(
        tool,
        {
            "hook_event_name": "PostToolUse",
            "session_id": "devin-1",
            "cwd": str(project),
            "tool_name": "exec",
            "tool_input": {"command": "ls"},
            "tool_response": {"success": True, "output": "ok", "error": None},
        },
        project,
        state,
    )
    if post.strip():
        assert set(json.loads(post)) <= {"hookSpecificOutput", "systemMessage"}
        assert "decision" not in json.loads(post)


def test_session_start_speaks_once_per_session(tmp_path: Path) -> None:
    # Devin Local also loads the Claude Code hooks, so a SessionStart command can
    # fire twice for one session. The contract records a marker per session.
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    start = _commands(_load(project))[0]
    state = tmp_path / "state"

    def fire(session_id: str, source: str = "startup") -> str:
        return _run(
            start,
            {
                "hook_event_name": "SessionStart",
                "session_id": session_id,
                "source": source,
                "cwd": str(project),
            },
            project,
            state,
        )

    assert fire("s-1").strip()
    assert fire("s-1") == "", "the same session, the same source: silent"
    assert fire("s-2").strip(), "a new session speaks"
    assert fire("s-1", source="compact").strip(), "a compaction restart still speaks"


def test_the_registered_commands_stay_silent_and_fail_open(tmp_path: Path) -> None:
    # A hook that cannot read its input, or that an operator switched off, must
    # still exit 0 and say nothing Devin could mistake for a decision.
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    base = {
        **os.environ,
        "PYTHONUTF8": "1",
        "APOTHEM_HOOK_STATE_DIR": str(tmp_path / "s"),
    }
    base.pop("APOTHEM_HOOKS_DISABLE", None)

    for command in _commands(_load(project)):
        garbage = subprocess.run(
            shlex.split(command),
            input="not json",
            capture_output=True,
            text=True,
            env=base,
            cwd=str(project),
            timeout=60,
            check=False,
        )
        assert garbage.returncode == 0, garbage.stderr
        disabled = subprocess.run(
            shlex.split(command),
            input="{}",
            capture_output=True,
            text=True,
            env={**base, "APOTHEM_HOOKS_DISABLE": "1"},
            cwd=str(project),
            timeout=60,
            check=False,
        )
        assert disabled.returncode == 0, disabled.stderr
        assert disabled.stdout == ""


# --- the operator's entries ------------------------------------------------------


def test_operator_hooks_and_keys_survive_install_update_and_uninstall(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    operator = _write_operator_file(project)
    original = _config(project).read_bytes()

    _adapter().install({}, project=project)
    merged = _load(project)
    assert merged["permissions"] == operator["permissions"]
    # The operator's handler stays first under its (empty) matcher; Apothem's
    # follows it.
    post = merged["hooks"]["PostToolUse"]
    assert len(post) == 1
    assert post[0]["hooks"][0] == _OPERATOR_HOOK
    assert len(post[0]["hooks"]) == 2
    assert merged["hooks"]["PreToolUse"] == [
        {"matcher": "exec", "hooks": [_OPERATOR_PRE]}
    ]
    assert "SessionStart" in merged["hooks"]

    installed = _config(project).read_bytes()
    _adapter().update({}, project=project)
    assert _config(project).read_bytes() == installed, "update is idempotent"

    _adapter().uninstall(project=project)
    assert _load(project) == operator
    assert not _support(project).exists()
    # The operator's file is restored to the keys it had; only whitespace may differ.
    assert (
        original.decode("utf-8").split()
        == _config(project).read_text(encoding="utf-8").split()
    )


def test_uninstall_deletes_a_registration_apothem_created(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    assert _config(project).is_file()

    _adapter().uninstall(project=project)

    assert not _config(project).exists()
    assert not _support(project).exists()


def test_uninstall_without_an_install_record_still_finds_the_handlers(
    tmp_path: Path,
) -> None:
    # The uninstall renders the template without the install-time interpreter
    # token, so ownership has to come from what each command runs: the dispatcher
    # under the project's support tree.
    project = _project(tmp_path)
    operator = _write_operator_file(project)
    _adapter().install({}, project=project)
    ledger = install_ledger.ledger_path("windsurf")
    assert ledger.is_file()
    ledger.unlink()

    _adapter().uninstall(project=project)

    assert _load(project) == operator
    assert "dispatch.py" not in _config(project).read_text(encoding="utf-8")


def test_an_operator_handler_that_runs_another_dispatcher_is_not_removed(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    lookalike = {
        "type": "command",
        "command": '"/usr/bin/python3" "/opt/team/hooks/dispatch.py" PostToolUse',
    }
    _config(project).parent.mkdir(parents=True)
    _config(project).write_text(
        json.dumps({"hooks": {"PostToolUse": [{"hooks": [lookalike]}]}}),
        encoding="utf-8",
    )

    _adapter().install({}, project=project)
    _adapter().uninstall(project=project)

    assert _load(project)["hooks"]["PostToolUse"][0]["hooks"] == [lookalike]


def test_a_second_install_does_not_duplicate_the_handlers(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    first = _config(project).read_bytes()
    _adapter().install({}, project=project)

    assert _config(project).read_bytes() == first
    assert len(_commands(json.loads(first))) == 2


def test_a_registration_that_cannot_be_rewritten_losslessly_is_refused(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _config(project).parent.mkdir(parents=True)
    commented = '{\n  // my notes\n  "permissions": {"allow": []}\n}\n'
    _config(project).write_text(commented, encoding="utf-8")

    run = _adapter().preview({}, project=project)
    result = next(r for r in run.results if r.path == str(_config(project)))
    assert result.outcome == "error"
    assert _config(project).read_text(encoding="utf-8") == commented


# --- the support trees of the adapters that share a project ----------------------


def test_each_adapter_keeps_its_own_support_tree(tmp_path: Path) -> None:
    # One shared tree would let either uninstall remove the dispatcher the other
    # still runs, and make each adapter read as installed after the other's.
    project = _project(tmp_path)
    codebuddy = _adapter("codebuddy")
    for adapter in (codebuddy, _adapter("windsurf"), _adapter("kiro")):
        adapter.install({}, project=project)

    _adapter("windsurf").uninstall(project=project)

    assert not _support(project).exists()
    assert not _config(project).exists()
    assert (project / ".apothem/support/hooks/dispatch.py").is_file()
    assert (project / ".apothem/support/kiro/hooks/dispatch.py").is_file()
    assert _adapter("windsurf").is_installed(project=project) is False
    assert _adapter("kiro").is_installed(project=project) is True


# --- preview and verify ------------------------------------------------------------


def test_dry_run_writes_nothing_and_previews_the_rendered_registration(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    run = _adapter().preview({}, project=project)

    assert not _config(project).exists()
    assert not _support(project).exists()
    preview = {r.path: r for r in run.results}[str(_config(project))]
    assert preview.outcome == "created"
    diff = preview.detail["diff"]
    assert "--contract devin" in diff
    assert "${PYTHON_BIN}" not in diff
    assert python_bin_tokens()["PYTHON_BIN"] in diff


def test_verify_reads_the_registration(tmp_path: Path) -> None:
    project = _project(tmp_path)
    adapter = _adapter()
    assert adapter.verify(project=project) is False
    adapter.install({}, project=project)
    assert adapter.verify(project=project) is True

    _config(project).write_text("{ not json", encoding="utf-8")
    assert adapter.verify(project=project) is False


# --- the manifest ------------------------------------------------------------------


def test_the_manifest_entries_for_hooks() -> None:
    entries = {e.target: e for e in load_manifest()["windsurf"].install}
    support = entries["${PROJECT_ROOT}/.apothem/support/windsurf/hooks/"]
    assert (support.source, support.mode) == ("hooks/", "merge_tree_entries")
    assert support.ownership_class == "apothem-owned"
    registration = entries["${PROJECT_ROOT}/.devin/config.local.json"]
    assert registration.mode == "write_text"
    assert registration.ownership_class == "operator-owned"
    assert registration.source == "harnesses/windsurf/templates/config-local.json"
