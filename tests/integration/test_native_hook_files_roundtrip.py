# SPDX-License-Identifier: MIT

"""Kiro and GitHub Copilot install, verify, update and uninstall their hook files.

Both vendors read hooks from small JSON files in a folder of their own
(``<project>/.kiro/hooks/`` and ``<project>/.github/hooks/``). The install writes
one Apothem-owned file there, ``apothem.json``, and puts the dispatcher in a support
tree under ``<project>/.apothem/support/<harness>/hooks/``. These tests drive the
real manifest with the user home isolated per test (``tests/conftest.py``) and
assert the exact bytes written, that the operator's own files and entries survive
every step, and that an uninstall finds Apothem's entries by what their command
runs, with or without an install record.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from string import Template

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.wrapper_factories import python_bin_tokens
from apothem.lib import install_ledger
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class
from apothem.lib.propagation import load_manifest

_SRC = Path(install_driver.APOTHEM_SRC)


@dataclass(frozen=True)
class Spec:
    """What differs between the two vendors' hook files."""

    public_id: str
    package_key: str
    contract: str
    hook_file: str
    support: str
    template: Path
    events: tuple[str, ...]
    sibling: str

    @property
    def is_list(self) -> bool:
        return self.public_id == "kiro"


KIRO = Spec(
    public_id="kiro",
    package_key="kiro",
    contract="kiro",
    hook_file=".kiro/hooks/apothem.json",
    support=".apothem/support/kiro/hooks",
    template=_SRC / "harnesses" / "kiro" / "templates" / "apothem-hooks.json",
    events=("SessionStart",),
    sibling=".kiro/hooks/lint.json",
)
COPILOT = Spec(
    public_id="github-copilot",
    package_key="github_copilot",
    contract="copilot",
    hook_file=".github/hooks/apothem.json",
    support=".apothem/support/github-copilot/hooks",
    template=_SRC / "harnesses" / "github_copilot" / "templates" / "apothem-hooks.json",
    events=("sessionStart", "postToolUse"),
    sibling=".github/hooks/team.json",
)
SPECS = pytest.mark.parametrize("spec", [KIRO, COPILOT], ids=lambda s: s.public_id)

_OPERATOR_LIST_HOOK = {
    "name": "lint-on-save",
    "trigger": "PostFileSave",
    "action": {"type": "command", "command": "npm run lint"},
}
_OPERATOR_MAP_HOOK = {"type": "command", "bash": "echo operator", "timeoutSec": 5}


def _adapter(spec: Spec):  # the adapter classes are generated
    return load_adapter_class(get_harness_entry(spec.public_id))()


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project


def _file(spec: Spec, project: Path) -> Path:
    return project / spec.hook_file


def _support(spec: Spec, project: Path) -> Path:
    return project / spec.support


def _expected_text(spec: Spec, project: Path) -> str:
    """Return the registration the install writes, rendered the way it renders."""
    tokens = {**python_bin_tokens(), "PROJECT_ROOT": project.resolve().as_posix()}
    return Template(spec.template.read_text(encoding="utf-8")).substitute(tokens)


def _load(spec: Spec, project: Path) -> dict[str, object]:
    return json.loads(_file(spec, project).read_text(encoding="utf-8"))


def _hooks(spec: Spec, doc: dict[str, object]) -> list[dict[str, object]]:
    """Return every hook in *doc*, whichever shape it is."""
    hooks = doc["hooks"]
    if spec.is_list:
        assert isinstance(hooks, list)
        return hooks
    assert isinstance(hooks, dict)
    return [hook for listed in hooks.values() for hook in listed]


def _commands(spec: Spec, doc: dict[str, object]) -> list[str]:
    """Return the command each Apothem hook runs (Kiro's, or Copilot's bash one)."""
    key = "command" if spec.is_list else "bash"
    return [
        (hook["action"] if spec.is_list else hook)[key] for hook in _hooks(spec, doc)
    ]


def _operator_file(spec: Spec, project: Path) -> dict[str, object]:
    """Write an `apothem.json` the operator added a hook to, and return it."""
    if spec.is_list:
        operator: dict[str, object] = {
            "version": "v1",
            "hooks": [_OPERATOR_LIST_HOOK],
        }
    else:
        operator = {
            "version": 1,
            "hooks": {
                "postToolUse": [_OPERATOR_MAP_HOOK],
                "preToolUse": [_OPERATOR_MAP_HOOK],
            },
        }
    _file(spec, project).parent.mkdir(parents=True, exist_ok=True)
    _file(spec, project).write_text(json.dumps(operator, indent=2) + "\n", "utf-8")
    return operator


def _write_sibling(spec: Spec, project: Path) -> bytes:
    """Write a hook file of the operator's own beside Apothem's and return its bytes."""
    sibling = project / spec.sibling
    sibling.parent.mkdir(parents=True, exist_ok=True)
    body = (
        {"version": "v1", "hooks": [_OPERATOR_LIST_HOOK]}
        if spec.is_list
        else {"version": 1, "hooks": {"preToolUse": [_OPERATOR_MAP_HOOK]}}
    )
    sibling.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return sibling.read_bytes()


# --- what is written -------------------------------------------------------------


@SPECS
def test_install_writes_the_exact_registration(spec: Spec, tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter(spec).install({}, project=project)

    data = _file(spec, project).read_bytes()
    assert data == _expected_text(spec, project).encode("utf-8")
    assert b"\r" not in data, "LF only"
    assert not data.startswith(b"\xef\xbb\xbf"), "no BOM"
    assert b"${" not in data, "every token is rendered"


@SPECS
def test_only_the_events_the_vendor_delivers_are_registered(
    spec: Spec, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    _adapter(spec).install({}, project=project)
    doc = _load(spec, project)

    if spec.is_list:
        assert [h["trigger"] for h in _hooks(spec, doc)] == list(spec.events)
        assert [h["name"] for h in _hooks(spec, doc)] == ["apothem-session-start"]
        for hook in _hooks(spec, doc):
            # Only the keys Kiro's hooks page lists for a v1 command hook.
            assert set(hook) <= {"name", "description", "trigger", "action", "timeout"}
            assert hook["action"]["type"] == "command"
            assert "matcher" not in hook, "SessionStart is not matched"
            assert "timeout_ms" not in hook
    else:
        assert sorted(doc["hooks"]) == sorted(spec.events)
        assert doc["version"] == 1
        for hook in _hooks(spec, doc):
            # Only the keys the Copilot hooks reference lists for a command hook.
            assert set(hook) == {"type", "bash", "powershell", "timeoutSec"}
            assert hook["type"] == "command"
            assert "matcher" not in hook, "an invalid matcher skips the entry"
        assert "preToolUse" not in doc["hooks"], "Copilot reads only permissions there"


@SPECS
def test_each_command_runs_the_installed_dispatcher_under_the_contract(
    spec: Spec, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    _adapter(spec).install({}, project=project)
    doc = _load(spec, project)

    python = python_bin_tokens()["PYTHON_BIN"]
    dispatcher = (project.resolve() / spec.support / "dispatch.py").as_posix()
    expected = [
        f'"{python}" "{dispatcher}" --contract {spec.contract} {spec.events[0]}'
    ]
    if not spec.is_list:
        expected.append(
            f'"{python}" "{dispatcher}" --contract copilot postToolUse '
            "posttooluse-proactive-compaction"
        )
    assert _commands(spec, doc) == expected
    assert Path(dispatcher).is_file()
    if not spec.is_list:
        # PowerShell needs the call operator before a quoted program path.
        assert [h["powershell"] for h in _hooks(spec, doc)] == [
            f"& {command}" for command in expected
        ]


@SPECS
def test_install_places_the_dispatcher_and_the_shim_in_the_support_tree(
    spec: Spec, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    _adapter(spec).install({}, project=project)

    support = _support(spec, project)
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


@SPECS
def test_the_registration_works_when_it_is_run_the_way_the_vendor_runs_it(
    spec: Spec, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    _adapter(spec).install({}, project=project)
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "APOTHEM_HOOK_STATE_DIR": str(tmp_path / "s"),
    }
    env.pop("APOTHEM_HOOKS_DISABLE", None)

    def run(command: str, payload: dict[str, object]) -> str:
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

    commands = _commands(spec, _load(spec, project))
    if spec.is_list:
        payload = {
            "hook_event_name": "SessionStart",
            "cwd": str(project),
            "session_id": "kiro-1",
        }
        out = run(commands[0], payload)
        # Kiro adds plain stdout to the context: no JSON envelope around it.
        assert out.strip()
        assert not out.lstrip().startswith("{")
    else:
        start = run(
            commands[0],
            {
                "sessionId": "cp-1",
                "timestamp": 1,
                "cwd": str(project),
                "source": "startup",
            },
        )
        assert set(json.loads(start)) == {"additionalContext"}
        assert json.loads(start)["additionalContext"].strip()
        tool = {
            "sessionId": "cp-1",
            "timestamp": 2,
            "cwd": str(project),
            "toolName": "bash",
            "toolArgs": json.dumps({"command": "ls"}),
            "toolResult": {"resultType": "success", "textResultForLlm": "ok"},
        }
        out = run(commands[1], tool)
        if out.strip():
            assert set(json.loads(out)) == {"additionalContext"}


@SPECS
def test_the_registered_commands_stay_silent_and_fail_open(
    spec: Spec, tmp_path: Path
) -> None:
    # A hook that cannot read its input, or that an operator switched off, must
    # still exit 0 and say nothing the vendor could mistake for a decision.
    project = _project(tmp_path)
    _adapter(spec).install({}, project=project)
    base = {
        **os.environ,
        "PYTHONUTF8": "1",
        "APOTHEM_HOOK_STATE_DIR": str(tmp_path / "s"),
    }
    base.pop("APOTHEM_HOOKS_DISABLE", None)

    for command in _commands(spec, _load(spec, project)):
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


# --- the operator's files and entries ---------------------------------------------


@SPECS
def test_the_operators_other_hook_files_are_never_touched(
    spec: Spec, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    sibling = project / spec.sibling
    original = _write_sibling(spec, project)

    _adapter(spec).install({}, project=project)
    assert sibling.read_bytes() == original
    _adapter(spec).update({}, project=project)
    assert sibling.read_bytes() == original
    _adapter(spec).uninstall(project=project)
    assert sibling.read_bytes() == original
    assert not _file(spec, project).exists()


@SPECS
def test_operator_entries_in_the_file_survive_install_update_and_uninstall(
    spec: Spec, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    operator = _operator_file(spec, project)

    _adapter(spec).install({}, project=project)
    merged = _load(spec, project)
    if spec.is_list:
        assert merged["hooks"][0] == _OPERATOR_LIST_HOOK
        assert len(merged["hooks"]) == 2
    else:
        assert merged["hooks"]["preToolUse"] == [_OPERATOR_MAP_HOOK]
        assert merged["hooks"]["postToolUse"][0] == _OPERATOR_MAP_HOOK
        assert len(merged["hooks"]["postToolUse"]) == 2
        # A flat entry is never given a Claude-style handler list.
        assert all("hooks" not in hook for hook in _hooks(spec, merged))
    assert merged["version"] == operator["version"]

    installed = _file(spec, project).read_bytes()
    _adapter(spec).update({}, project=project)
    assert _file(spec, project).read_bytes() == installed, "update is idempotent"

    _adapter(spec).uninstall(project=project)
    assert _load(spec, project) == operator
    assert not _support(spec, project).exists()


@SPECS
def test_uninstall_deletes_a_file_apothem_created(spec: Spec, tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter(spec).install({}, project=project)
    assert _file(spec, project).is_file()

    _adapter(spec).uninstall(project=project)

    assert not _file(spec, project).exists()
    assert not _support(spec, project).exists()


@SPECS
def test_uninstall_without_an_install_record_still_finds_the_hooks(
    spec: Spec, tmp_path: Path
) -> None:
    # The uninstall renders the template without the install-time interpreter
    # token, so ownership has to come from what each command runs: the dispatcher
    # under the project's support tree.
    project = _project(tmp_path)
    operator = _operator_file(spec, project)
    _adapter(spec).install({}, project=project)
    ledger = install_ledger.ledger_path(spec.package_key)
    assert ledger.is_file()
    ledger.unlink()

    _adapter(spec).uninstall(project=project)

    assert _load(spec, project) == operator
    assert "dispatch.py" not in _file(spec, project).read_text(encoding="utf-8")


@SPECS
def test_uninstall_without_a_record_deletes_the_file_it_created(
    spec: Spec, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    _adapter(spec).install({}, project=project)
    install_ledger.ledger_path(spec.package_key).unlink()

    _adapter(spec).uninstall(project=project)

    assert not _file(spec, project).exists()


@SPECS
def test_a_hook_that_runs_another_dispatcher_is_not_removed(
    spec: Spec, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    lookalike = '"/usr/bin/python3" "/opt/team/hooks/dispatch.py" SessionStart'
    if spec.is_list:
        mine = {
            "name": "team",
            "trigger": "SessionStart",
            "action": {"type": "command", "command": lookalike},
        }
        body: dict[str, object] = {"version": "v1", "hooks": [mine]}
    else:
        mine = {"type": "command", "bash": lookalike}
        body = {"version": 1, "hooks": {"sessionStart": [mine]}}
    _file(spec, project).parent.mkdir(parents=True)
    _file(spec, project).write_text(json.dumps(body), encoding="utf-8")

    _adapter(spec).install({}, project=project)
    assert mine in _hooks(spec, _load(spec, project))
    _adapter(spec).uninstall(project=project)

    assert _hooks(spec, _load(spec, project)) == [mine]


@SPECS
def test_a_second_install_does_not_duplicate_the_hooks(
    spec: Spec, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    _adapter(spec).install({}, project=project)
    first = _file(spec, project).read_bytes()
    _adapter(spec).install({}, project=project)

    assert _file(spec, project).read_bytes() == first
    assert len(_commands(spec, json.loads(first))) == len(spec.events)


@SPECS
def test_an_edited_file_is_backed_up_before_it_is_replaced(
    spec: Spec, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    _file(spec, project).parent.mkdir(parents=True)
    _file(spec, project).write_text("{ not json", encoding="utf-8")

    run = _adapter(spec).install({}, project=project)

    written = next(r for r in run.results if r.path == str(_file(spec, project)))
    assert written.outcome == "updated"
    assert written.backup_path is not None
    assert Path(written.backup_path).read_text(encoding="utf-8") == "{ not json"
    assert _load(spec, project)["hooks"]


# --- preview and verify ------------------------------------------------------------


@SPECS
def test_dry_run_writes_nothing_and_previews_the_rendered_registration(
    spec: Spec, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    run = _adapter(spec).preview({}, project=project)

    assert not _file(spec, project).exists()
    assert not _support(spec, project).exists()
    preview = {r.path: r for r in run.results}[str(_file(spec, project))]
    assert preview.operation == "native_hooks"
    assert preview.outcome == "created"
    diff = preview.detail["diff"]
    assert f"--contract {spec.contract}" in diff
    assert "${PYTHON_BIN}" not in diff
    assert python_bin_tokens()["PYTHON_BIN"] in diff


@SPECS
def test_dry_run_after_an_install_reports_no_change(spec: Spec, tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter(spec).install({}, project=project)

    run = _adapter(spec).preview({}, project=project)

    preview = {r.path: r for r in run.results}[str(_file(spec, project))]
    assert preview.outcome == "unchanged"


@SPECS
def test_verify_reads_the_registration(spec: Spec, tmp_path: Path) -> None:
    project = _project(tmp_path)
    adapter = _adapter(spec)
    assert adapter.verify(project=project) is False
    adapter.install({}, project=project)
    assert adapter.verify(project=project) is True

    _file(spec, project).write_text("{ not json", encoding="utf-8")
    assert adapter.verify(project=project) is False


# --- the manifest ------------------------------------------------------------------


@SPECS
def test_the_manifest_entries_for_hooks(spec: Spec) -> None:
    entries = {e.target: e for e in load_manifest()[spec.package_key].install}
    support = entries["${PROJECT_ROOT}/" + spec.support + "/"]
    assert (support.source, support.mode) == ("hooks/", "merge_tree_entries")
    assert support.ownership_class == "apothem-owned"
    registration = entries["${PROJECT_ROOT}/" + spec.hook_file]
    assert registration.mode == "native_hooks"
    assert registration.ownership_class == "apothem-owned"
    assert registration.source == str(spec.template.relative_to(_SRC).as_posix())


def test_the_two_vendors_keep_separate_support_trees(tmp_path: Path) -> None:
    # One shared tree would let either uninstall remove the dispatcher the other
    # still runs, and make each adapter read as installed after the other's.
    assert KIRO.support != COPILOT.support
    project = _project(tmp_path)
    _adapter(KIRO).install({}, project=project)
    assert _adapter(COPILOT).is_installed(project=project) is False

    _adapter(COPILOT).install({}, project=project)
    _adapter(KIRO).uninstall(project=project)

    assert not _file(KIRO, project).exists()
    assert not _support(KIRO, project).exists()
    assert _file(COPILOT, project).is_file()
    assert (_support(COPILOT, project) / "dispatch.py").is_file()
    assert _adapter(COPILOT).verify(project=project) is True
    assert _adapter(KIRO).is_installed(project=project) is False
    assert _adapter(COPILOT).is_installed(project=project) is True


def test_both_registrations_coexist_with_codebuddys_support_tree(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    codebuddy = load_adapter_class(get_harness_entry("codebuddy"))()
    for adapter in (codebuddy, _adapter(KIRO), _adapter(COPILOT)):
        adapter.install({}, project=project)

    codebuddy.uninstall(project=project)

    for spec in (KIRO, COPILOT):
        assert (_support(spec, project) / "dispatch.py").is_file()
        assert _file(spec, project).is_file()
