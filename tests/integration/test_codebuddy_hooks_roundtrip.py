# SPDX-License-Identifier: MIT

"""CodeBuddy installs, verifies, updates and uninstalls its native hooks.

CodeBuddy runs hook commands from the ``hooks`` key of its settings files; the
install registers Apothem's SessionStart and PostToolUse in the uncommitted
``<project>/.codebuddy/settings.local.json`` and puts the dispatcher in the
support tree under ``<project>/.apothem/support/hooks/``. These tests drive the
real manifest with the user home isolated per test (``tests/conftest.py``) and
assert the exact bytes written, that the operator's own entries survive every
step, and that an uninstall removes the Apothem handlers by what their command
runs, with or without an install record.
"""

from __future__ import annotations

import json
from pathlib import Path
from string import Template

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.wrapper_factories import python_bin_tokens
from apothem.lib import install_ledger
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class
from apothem.lib.propagation import load_manifest

_SRC = Path(install_driver.APOTHEM_SRC)
_TEMPLATE = _SRC / "harnesses" / "codebuddy" / "templates" / "settings-local.json"

_OPERATOR_HOOK = {"type": "command", "command": "echo operator-post-tool"}
_OPERATOR_PRE = {"type": "command", "command": "bash scripts/guard.sh"}


def _adapter():  # the adapter classes are generated
    return load_adapter_class(get_harness_entry("codebuddy"))()


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project


def _settings(project: Path) -> Path:
    return project / ".codebuddy" / "settings.local.json"


def _support(project: Path) -> Path:
    return project / ".apothem" / "support" / "hooks"


def _expected_text(project: Path) -> str:
    """Return the registration the install writes, rendered the way it renders."""
    tokens = {
        **python_bin_tokens(),
        "PROJECT_ROOT": project.resolve().as_posix(),
    }
    return Template(_TEMPLATE.read_text(encoding="utf-8")).substitute(tokens)


def _commands(settings: dict[str, object]) -> list[str]:
    hooks = settings["hooks"]
    assert isinstance(hooks, dict)
    return [
        handler["command"]
        for groups in hooks.values()
        for group in groups
        for handler in group["hooks"]
    ]


def _write_operator_file(project: Path) -> dict[str, object]:
    operator: dict[str, object] = {
        "permissions": {"allow": ["Bash(ls:*)"]},
        "hooks": {
            "PostToolUse": [{"matcher": "*", "hooks": [_OPERATOR_HOOK]}],
            "PreToolUse": [{"matcher": "Bash", "hooks": [_OPERATOR_PRE]}],
        },
    }
    _settings(project).parent.mkdir(parents=True)
    _settings(project).write_text(
        json.dumps(operator, indent=2) + "\n", encoding="utf-8"
    )
    return operator


def test_install_writes_the_exact_registration(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    data = _settings(project).read_bytes()
    assert data == _expected_text(project).encode("utf-8")
    assert b"\r" not in data, "LF only"
    assert not data.startswith(b"\xef\xbb\xbf"), "no BOM"
    assert b"${" not in data, "every token is rendered"


def test_only_the_events_codebuddy_delivers_are_registered(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    hooks = json.loads(_settings(project).read_text(encoding="utf-8"))["hooks"]
    assert sorted(hooks) == ["PostToolUse", "SessionStart"]
    assert [g.get("matcher") for g in hooks["SessionStart"]] == [None]
    assert [g.get("matcher") for g in hooks["PostToolUse"]] == ["*"]
    for groups in hooks.values():
        for group in groups:
            for handler in group["hooks"]:
                # Only the keys CodeBuddy's hooks page documents for a command hook.
                assert set(handler) == {"type", "command", "timeout"}
                assert handler["type"] == "command"


def test_each_command_runs_the_installed_dispatcher_under_the_contract(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    commands = _commands(json.loads(_settings(project).read_text(encoding="utf-8")))
    assert len(commands) == 2
    python = python_bin_tokens()["PYTHON_BIN"]
    dispatcher = (project.resolve() / ".apothem/support/hooks/dispatch.py").as_posix()
    assert commands == [
        f'"{python}" "{dispatcher}" --contract codebuddy SessionStart',
        f'"{python}" "{dispatcher}" --contract codebuddy PostToolUse '
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


def test_the_hook_files_stay_out_of_the_committed_settings(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    assert not (project / ".codebuddy" / "settings.json").exists()
    assert _settings(project).is_file()


def test_operator_hooks_and_keys_survive_install_update_and_uninstall(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    operator = _write_operator_file(project)
    original = _settings(project).read_bytes()

    _adapter().install({}, project=project)
    merged = json.loads(_settings(project).read_text(encoding="utf-8"))
    assert merged["permissions"] == operator["permissions"]
    # The operator's handler stays first under its matcher; Apothem's follows it.
    post = merged["hooks"]["PostToolUse"]
    assert [g["matcher"] for g in post] == ["*"]
    assert post[0]["hooks"][0] == _OPERATOR_HOOK
    assert len(post[0]["hooks"]) == 2
    assert merged["hooks"]["PreToolUse"] == [
        {"matcher": "Bash", "hooks": [_OPERATOR_PRE]}
    ]
    assert "SessionStart" in merged["hooks"]

    installed = _settings(project).read_bytes()
    _adapter().update({}, project=project)
    assert _settings(project).read_bytes() == installed, "update is idempotent"

    _adapter().uninstall(project=project)
    assert json.loads(_settings(project).read_text(encoding="utf-8")) == operator
    assert not _support(project).exists()
    # The operator's file is restored to the keys it had; only whitespace may differ.
    assert (
        original.decode("utf-8").split()
        == _settings(project).read_text(encoding="utf-8").split()
    )


def test_uninstall_deletes_a_registration_apothem_created(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    assert _settings(project).is_file()

    _adapter().uninstall(project=project)

    assert not _settings(project).exists()
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
    ledger = install_ledger.ledger_path("codebuddy")
    assert ledger.is_file()
    ledger.unlink()

    _adapter().uninstall(project=project)

    after = json.loads(_settings(project).read_text(encoding="utf-8"))
    assert after == operator
    assert "dispatch.py" not in _settings(project).read_text(encoding="utf-8")


def test_an_operator_handler_that_runs_another_dispatcher_is_not_removed(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    lookalike = {
        "type": "command",
        "command": '"/usr/bin/python3" "/opt/team/hooks/dispatch.py" PostToolUse',
    }
    _settings(project).parent.mkdir(parents=True)
    _settings(project).write_text(
        json.dumps(
            {"hooks": {"PostToolUse": [{"matcher": "*", "hooks": [lookalike]}]}}
        ),
        encoding="utf-8",
    )

    _adapter().install({}, project=project)
    _adapter().uninstall(project=project)

    after = json.loads(_settings(project).read_text(encoding="utf-8"))
    assert after["hooks"]["PostToolUse"][0]["hooks"] == [lookalike]


def test_a_second_install_does_not_duplicate_the_handlers(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    first = _settings(project).read_bytes()
    _adapter().install({}, project=project)

    assert _settings(project).read_bytes() == first
    assert len(_commands(json.loads(first))) == 2


def test_dry_run_writes_nothing_and_previews_the_rendered_registration(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    run = _adapter().preview({}, project=project)

    assert not _settings(project).exists()
    assert not _support(project).exists()
    targets = {r.path: r for r in run.results}
    preview = targets[str(_settings(project))]
    assert preview.outcome == "created"
    diff = preview.detail["diff"]
    assert "--contract codebuddy" in diff
    assert "${PYTHON_BIN}" not in diff
    assert python_bin_tokens()["PYTHON_BIN"] in diff


def test_verify_reads_the_registration(tmp_path: Path) -> None:
    project = _project(tmp_path)
    adapter = _adapter()
    assert adapter.verify(project=project) is False
    adapter.install({}, project=project)
    assert adapter.verify(project=project) is True

    _settings(project).write_text("{ not json", encoding="utf-8")
    assert adapter.verify(project=project) is False


def test_a_registration_that_cannot_be_rewritten_losslessly_is_refused(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _settings(project).parent.mkdir(parents=True)
    commented = '{\n  // my notes\n  "permissions": {"allow": []}\n}\n'
    _settings(project).write_text(commented, encoding="utf-8")

    run = _adapter().preview({}, project=project)
    result = next(r for r in run.results if r.path == str(_settings(project)))
    assert result.outcome == "error"
    assert _settings(project).read_text(encoding="utf-8") == commented


def test_the_manifest_entries_for_hooks() -> None:
    entries = {e.target: e for e in load_manifest()["codebuddy"].install}
    support = entries["${PROJECT_ROOT}/.apothem/support/hooks/"]
    assert (support.source, support.mode) == ("hooks/", "merge_tree_entries")
    assert support.ownership_class == "apothem-owned"
    registration = entries["${PROJECT_ROOT}/.codebuddy/settings.local.json"]
    assert registration.mode == "write_text"
    assert registration.ownership_class == "operator-owned"
    assert registration.source == "harnesses/codebuddy/templates/settings-local.json"
