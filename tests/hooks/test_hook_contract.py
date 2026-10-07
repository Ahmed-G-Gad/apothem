# SPDX-License-Identifier: MIT

"""Hook contract: every registered hook command honours the same eight clauses.

Why this test exists. A hook that cannot start fails silently in the harness: a
non-zero exit is a non-blocking notice, so a broken registration leaves a guard
disabled with nothing but a one-line warning. Release 1.0.2 fixed one instance
of that class (a ``Stop`` hook with no fixed point); the same class reappeared as
plugin hooks that could not execute on macOS and Linux (the bootstrap stub was
tracked without its executable bit) and as handlers that injected context on
every call. This module checks the class, not the instance.

Surfaces. Each surface is materialized the way the harness consumes it, and on
macOS and Linux every registered command is run the way the harness runs it
(Windows is covered below):

* the Claude Code plugin ``hooks.json`` in the committed ``plugins/claude-code``
  tree, copied with every executable bit stripped and run through ``sh -c``
  (shell form) with ``CLAUDE_PLUGIN_ROOT`` exported;
* the engine-installed Claude Code ``settings.json`` (exec form: ``command`` plus
  ``args``);
* the engine-installed Codex ``hooks.json`` and Qwen Code ``settings.json``
  (shell form).

On Windows every shell-form command runs through Git Bash. That is how Claude
Code runs a plugin hook there. Codex runs each hook's ``commandWindows`` instead,
and Qwen Code runs hooks through cmd.exe, so on Windows the Codex and Qwen rows
check the dispatcher and its handlers, not those hosts' own command lines. A
separate check holds every Codex ``commandWindows`` to the command run here.

Clauses. (1) executes: exit 0 and stdout empty or one JSON object. (2)
termination: Stop and PostToolUse emissions are bounded per session. (3) output
bound: no emitted string exceeds 10,000 characters, the Claude Code cap. (4)
channel validity: Claude Code surfaces register no event whose output Claude
Code discards, and PreToolUse output never uses the deprecated top-level
``decision``. (5) latency: each command finishes inside its budget. (6) failure
mode: a missing message file still yields exit 0 and a valid envelope. (7) kill
switch: ``APOTHEM_HOOKS_DISABLE=1`` silences every command. (8) single execution:
each (event, matcher, message) is registered once per surface. Two security
clauses ride along: a hook never sources or executes a file from the opened
project, and no emitted context carries an unexpanded ``${...}`` placeholder.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_TREE = REPO_ROOT / "plugins" / "claude-code"
SRC_ROOT = REPO_ROOT / "src"

#: Claude Code truncates hook-injected text above this many characters.
_OUTPUT_CAP = 10_000
#: Wall-clock ceiling for one hook command on a CI runner. Interpreter start-up
#: dominates; the measured median on the plugin chain is ~0.15 s.
_LATENCY_BUDGET_SECONDS = 5.0
#: Shell-form commands run through sh, as the hosts run them on POSIX. On
#: Windows a PATH ``sh`` or ``bash`` can be the WSL launcher, so they run
#: through Git Bash, the shell Claude Code uses there (see the module docstring
#: for the Codex and Qwen Code rows).
_WINDOWS_BASH = find_test_bash() if sys.platform == "win32" else None
_SHELL = _WINDOWS_BASH or "sh"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" and _WINDOWS_BASH is None, reason=SKIP_REASON
)
#: Context-carrying emissions allowed per session for the periodic handlers.
_MAX_STOP_EMISSIONS = 1
_MAX_POSTTOOLUSE_EMISSIONS = 2
#: Events whose output Claude Code discards (hooks reference, PreCompact and
#: PostCompact sections): registering them on a Claude Code surface is dead
#: weight that suggests a delivery that never happens.
_CLAUDE_DISCARDED_EVENTS = frozenset({"PreCompact", "PostCompact"})
_HOSTILE_MARKER = "APOTHEM-CONTRACT-HOSTILE-PROJECT-CODE"


@dataclass(frozen=True)
class HookEntry:
    """One registered hook command as a harness would run it."""

    surface: str
    event: str
    matcher: str
    argv: tuple[str, ...]
    label: str

    @property
    def message(self) -> str:
        """Return the routed message basename (or the event for SessionStart)."""
        for token in reversed(self.argv):
            name = Path(token.strip('"')).name
            if name.endswith(".md"):
                return name[:-3]
        tail = self.label.split()[-1]
        return tail.rsplit("/", 1)[-1].removesuffix(".md")


def _strip_exec_bits(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)


def _isolated_env(home: Path, **extra: str) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("APOTHEM_", "CLAUDE_", "CODEX_", "LLM_"))
        and key not in {"XDG_CONFIG_HOME", "XDG_STATE_HOME", "PYTHONPATH"}
    }
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["APOTHEM_HOOK_STATE_DIR"] = str(home / ".hook-state")
    env.update(extra)
    return env


def _payload(
    event: str, matcher: str, project: Path, session: str
) -> dict[str, object]:
    base: dict[str, object] = {
        "session_id": session,
        "hook_event_name": event,
        "cwd": str(project),
        "transcript_path": str(project / "transcript.jsonl"),
    }
    if event == "SessionStart":
        base["source"] = "startup"
    elif event == "PreToolUse":
        tool = matcher.split("|")[0].strip("^$")
        if tool in {"Write", "Edit", "apply_patch"}:
            base.update(
                tool_name="Write",
                tool_input={
                    "file_path": str(project / "app.py"),
                    "content": "print('ok')\n",
                },
            )
        elif tool == "NotebookEdit":
            base.update(
                tool_name="NotebookEdit",
                tool_input={
                    "notebook_path": str(project / "n.ipynb"),
                    "new_source": "1",
                },
            )
        elif tool in {"Bash", "run_shell_command"}:
            base.update(tool_name="Bash", tool_input={"command": "ls"})
        elif tool == "AskUserQuestion":
            base.update(
                tool_name="AskUserQuestion",
                tool_input={
                    "questions": [
                        {
                            "question": "Which option?",
                            "header": "Choice",
                            "multiSelect": False,
                            "options": [
                                {"label": "First (Recommended)", "description": "a"},
                                {"label": "Second", "description": "b"},
                            ],
                        }
                    ]
                },
            )
    elif event == "PostToolUse":
        base.update(tool_name="Read", tool_input={}, tool_response="x" * 64)
    elif event == "Stop":
        base["stop_hook_active"] = False
    elif event in {"PreCompact", "PostCompact"}:
        base.update(trigger="auto", custom_instructions=None)
    return base


def _run(
    entry: HookEntry, payload: dict[str, object], env: dict[str, str], cwd: Path
) -> tuple[subprocess.CompletedProcess[str], float]:
    started = time.perf_counter()
    result = subprocess.run(
        list(entry.argv),
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
        timeout=60,
        check=False,
    )
    return result, time.perf_counter() - started


def _parse(stdout: str) -> dict[str, object]:
    text = stdout.strip()
    if not text:
        return {}
    parsed = json.loads(text)
    assert isinstance(parsed, dict), f"stdout is not one JSON object: {text[:200]}"
    return parsed


def _strings(obj: object) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _strings(value)


def _context_chars(output: dict[str, object]) -> int:
    specific = output.get("hookSpecificOutput")
    context = (
        specific.get("additionalContext", "") if isinstance(specific, dict) else ""
    )
    return len(str(context or "")) + len(str(output.get("systemMessage") or ""))


# --------------------------------------------------------------------------- #
# Surface materialization
# --------------------------------------------------------------------------- #


def _plugin_entries(plugin_root: Path) -> list[HookEntry]:
    hooks_json = plugin_root / "lib" / "apothem" / "hooks" / "hooks.json"
    data = json.loads(hooks_json.read_text(encoding="utf-8"))
    entries: list[HookEntry] = []
    for event, groups in data["hooks"].items():
        for group in groups:
            for hook in group["hooks"]:
                assert "args" not in hook, "plugin hooks use shell form"
                assert hook.get("shell") in (None, "bash"), (
                    f"plugin hook registers a non-default shell: {hook}"
                )
                entries.append(
                    HookEntry(
                        surface="plugin",
                        event=event,
                        matcher=str(group.get("matcher", "")),
                        argv=(_SHELL, "-c", hook["command"]),
                        label=hook["command"],
                    )
                )
    return entries


def _apothem(home: Path, *argv: str) -> None:
    """Run ``python -m apothem <argv>`` against an isolated HOME and assert success."""
    env = _isolated_env(
        home,
        PYTHONPATH=os.pathsep.join(
            [str(SRC_ROOT / "apothem" / "_vendor"), str(SRC_ROOT)]
        ),
    )
    result = subprocess.run(
        [sys.executable, "-m", "apothem", *argv],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(home),
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, f"{argv}: {result.stderr[-2000:]}"


def _settings_entries(surface: str, config: Path) -> list[HookEntry]:
    data = json.loads(config.read_text(encoding="utf-8"))
    entries: list[HookEntry] = []
    for event, groups in data.get("hooks", {}).items():
        for group in groups:
            for hook in group["hooks"]:
                command = hook["command"]
                if "args" in hook:
                    argv: tuple[str, ...] = (command, *[str(a) for a in hook["args"]])
                    label = " ".join(argv)
                else:
                    argv = (_SHELL, "-c", command)
                    label = command
                entries.append(
                    HookEntry(
                        surface=surface,
                        event=event,
                        matcher=str(group.get("matcher", "")),
                        argv=argv,
                        label=label,
                    )
                )
    return entries


@pytest.fixture(scope="module")
def workspace(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Materialize every surface once for the whole module."""
    base = tmp_path_factory.mktemp("hook-contract")
    plugin = base / "plugin"
    shutil.copytree(PLUGIN_TREE, plugin, ignore=shutil.ignore_patterns("__pycache__"))
    _strip_exec_bits(plugin)
    home = base / "home"
    home.mkdir()
    _apothem(home, "profile", "init")
    for harness in ("claude-code", "codex", "qwen-code"):
        _apothem(home, "install", "--harness", harness)
    project = base / "project"
    project.mkdir()
    (project / ".git").mkdir()
    hostile = base / "hostile-project"
    (hostile / "hooks" / "lib").mkdir(parents=True)
    (hostile / ".git").mkdir()
    (hostile / "hooks" / "lib" / "find-python.sh").write_text(
        f"echo {_HOSTILE_MARKER} >&2\nfind_real_python() {{ echo {_HOSTILE_MARKER}; }}\n",
        encoding="utf-8",
    )
    (hostile / "hooks" / "dispatch.py").write_text(
        f"print('{_HOSTILE_MARKER}')\n", encoding="utf-8"
    )
    return {"plugin": plugin, "home": home, "project": project, "hostile": hostile}


def _all_entries(ws: dict[str, Path]) -> list[HookEntry]:
    home = ws["home"]
    entries = _plugin_entries(ws["plugin"])
    entries += _settings_entries("claude-engine", home / ".claude" / "settings.json")
    entries += _settings_entries("codex", home / ".codex" / "hooks.json")
    entries += _settings_entries("qwen", home / ".qwen" / "settings.json")
    return entries


def _is_engine_gate(entry: HookEntry) -> bool:
    return "--hook" in entry.argv


def _env_for(
    entry: HookEntry, ws: dict[str, Path], project: Path, **extra: str
) -> dict[str, str]:
    env = _isolated_env(ws["home"], CLAUDE_PROJECT_DIR=str(project), **extra)
    if entry.surface == "plugin":
        env["CLAUDE_PLUGIN_ROOT"] = str(ws["plugin"])
    return env


# --------------------------------------------------------------------------- #
# Clauses
# --------------------------------------------------------------------------- #


def test_every_surface_registers_hooks(workspace: dict[str, Path]) -> None:
    """Each surface carries a non-empty hook set (guards against a vacuous pass)."""
    by_surface: dict[str, int] = {}
    for entry in _all_entries(workspace):
        by_surface[entry.surface] = by_surface.get(entry.surface, 0) + 1
    assert set(by_surface) == {"plugin", "claude-engine", "codex", "qwen"}
    assert all(count > 0 for count in by_surface.values()), by_surface


def test_clause1_3_5_every_command_executes_bounded_and_fast(
    workspace: dict[str, Path],
) -> None:
    """(1) exit 0 with empty or single-object JSON, (3) bounded, (5) in budget."""
    failures: list[str] = []
    for entry in _all_entries(workspace):
        if _is_engine_gate(entry):
            continue  # covered by test_engine_gate_hook_starts
        payload = _payload(entry.event, entry.matcher, workspace["project"], "c1")
        env = _env_for(entry, workspace, workspace["project"])
        result, seconds = _run(entry, payload, env, workspace["project"])
        if result.returncode != 0:
            failures.append(
                f"{entry.surface} {entry.event} {entry.message}: exit "
                f"{result.returncode}: {result.stderr.strip()[-300:]}"
            )
            continue
        try:
            output = _parse(result.stdout)
        except (json.JSONDecodeError, AssertionError) as exc:
            failures.append(f"{entry.surface} {entry.event} {entry.message}: {exc}")
            continue
        for text in _strings(output):
            if len(text) > _OUTPUT_CAP:
                failures.append(f"{entry.surface} {entry.message}: {len(text)} chars")
            if "${" in text:
                failures.append(
                    f"{entry.surface} {entry.message}: unexpanded placeholder"
                )
        if seconds > _LATENCY_BUDGET_SECONDS:
            failures.append(f"{entry.surface} {entry.message}: {seconds:.2f}s")
    assert not failures, "\n".join(failures)


def test_engine_gate_hook_starts(workspace: dict[str, Path]) -> None:
    """The engine's conformity gate hook starts and returns a JSON report."""
    gates = [e for e in _all_entries(workspace) if _is_engine_gate(e)]
    assert gates, "the engine install registers the conformity gate hook"
    for entry in gates:
        payload = _payload("PreToolUse", "Write", workspace["project"], "gate")
        env = _env_for(entry, workspace, workspace["project"])
        result, _ = _run(entry, payload, env, workspace["project"])
        assert result.returncode == 0, result.stderr[-500:]
        _parse(result.stdout)


def test_clause2_stop_is_bounded_and_off_by_default(workspace: dict[str, Path]) -> None:
    """Stop: at most one emission per session, none while stop_hook_active."""
    for entry in (e for e in _all_entries(workspace) if e.event == "Stop"):
        env = _env_for(entry, workspace, workspace["project"])
        emitted = 0
        for _ in range(50):
            payload = _payload(
                "Stop", "", workspace["project"], f"stop-{entry.surface}"
            )
            result, _ = _run(entry, payload, env, workspace["project"])
            # _parse reads a dead command's empty stdout as no emission.
            assert result.returncode == 0, (entry.label, result.stderr[-300:])
            emitted += _context_chars(_parse(result.stdout)) > 0
        assert emitted <= _MAX_STOP_EMISSIONS, (entry.surface, emitted)
        assert emitted == 0, f"{entry.surface}: session-end protocol must be opt-in"
        active = _payload("Stop", "", workspace["project"], f"active-{entry.surface}")
        active["stop_hook_active"] = True
        opt_in = _env_for(
            entry, workspace, workspace["project"], APOTHEM_SESSION_END_ENABLED="1"
        )
        for _ in range(5):
            result, _ = _run(entry, active, opt_in, workspace["project"])
            assert result.returncode == 0, (entry.label, result.stderr[-300:])
            assert _context_chars(_parse(result.stdout)) == 0


def test_clause2_posttooluse_advisory_is_capped(workspace: dict[str, Path]) -> None:
    """PostToolUse: at most two advisories in 60 heavy calls; none when switched off."""
    entries = [e for e in _all_entries(workspace) if e.event == "PostToolUse"]
    assert entries
    for entry in entries:
        for switch, ceiling in (("1", _MAX_POSTTOOLUSE_EMISSIONS), ("0", 0)):
            env = _env_for(
                entry,
                workspace,
                workspace["project"],
                APOTHEM_PROACTIVE_COMPACTION_ENABLED=switch,
            )
            emitted = 0
            for _ in range(60):
                payload = _payload(
                    "PostToolUse",
                    "*",
                    workspace["project"],
                    f"ptu-{entry.surface}-{switch}",
                )
                payload["tool_response"] = "y" * 8_192
                result, _ = _run(entry, payload, env, workspace["project"])
                # _parse reads a dead command's empty stdout as no emission.
                assert result.returncode == 0, (entry.label, result.stderr[-300:])
                emitted += _context_chars(_parse(result.stdout)) > 0
            assert emitted <= ceiling, (entry.surface, switch, emitted)


def test_clause4_claude_surfaces_use_valid_channels(workspace: dict[str, Path]) -> None:
    """No discarded-output events on Claude Code surfaces; no deprecated decision."""
    for entry in _all_entries(workspace):
        if entry.surface not in {"plugin", "claude-engine"}:
            continue
        assert entry.event not in _CLAUDE_DISCARDED_EVENTS, entry.label
    aq = [e for e in _all_entries(workspace) if "askuserquestion" in e.message]
    assert aq
    for entry in aq:
        payload = _payload("PreToolUse", "AskUserQuestion", workspace["project"], "aq")
        payload["tool_input"] = {
            "questions": [
                {
                    "question": "Which?",
                    "header": "H",
                    "multiSelect": False,
                    "options": [
                        {"label": "A (recommended)", "description": "a"},
                        {"label": "B", "description": "b"},
                    ],
                }
            ]
        }
        for strict in ("0", "1"):
            env = _env_for(
                entry, workspace, workspace["project"], APOTHEM_CONFORMITY_STRICT=strict
            )
            result, _ = _run(entry, payload, env, workspace["project"])
            output = _parse(result.stdout)
            assert "decision" not in output, output
            specific = output.get("hookSpecificOutput")
            assert isinstance(specific, dict), output
            if strict == "1":
                assert specific.get("permissionDecision") == "deny"
                assert specific.get("permissionDecisionReason")
            else:
                assert specific.get("additionalContext")


def test_clause6_missing_message_fails_open(workspace: dict[str, Path]) -> None:
    """A message file that does not exist still yields exit 0 and valid JSON."""
    for entry in _plugin_entries(workspace["plugin"]):
        if not entry.label.rstrip().endswith('.md"'):
            continue
        broken = HookEntry(
            surface=entry.surface,
            event=entry.event,
            matcher=entry.matcher,
            argv=(
                entry.argv[0],
                entry.argv[1],
                entry.argv[2].replace('.md"', '-missing.md"'),
            ),
            label=entry.label,
        )
        payload = _payload(entry.event, entry.matcher, workspace["project"], "c6")
        env = _env_for(entry, workspace, workspace["project"])
        result, _ = _run(broken, payload, env, workspace["project"])
        assert result.returncode == 0, result.stderr[-300:]
        _parse(result.stdout)


def test_clause7_kill_switch_silences_every_command(workspace: dict[str, Path]) -> None:
    """APOTHEM_HOOKS_DISABLE=1 makes every registered command silent."""
    for entry in _all_entries(workspace):
        if _is_engine_gate(entry):
            continue
        payload = _payload(entry.event, entry.matcher, workspace["project"], "c7")
        env = _env_for(
            entry, workspace, workspace["project"], APOTHEM_HOOKS_DISABLE="1"
        )
        result, _ = _run(entry, payload, env, workspace["project"])
        assert result.returncode == 0, (entry.label, result.stderr[-300:])
        assert result.stdout.strip() == "", (entry.label, result.stdout[:200])


def test_clause8_single_registration_per_surface(workspace: dict[str, Path]) -> None:
    """Each (event, matcher, message) is registered once; no dual-shell pairs."""
    seen: dict[tuple[str, str, str, str], int] = {}
    for entry in _all_entries(workspace):
        key = (entry.surface, entry.event, entry.matcher, entry.message)
        seen[key] = seen.get(key, 0) + 1
    duplicates = {key: count for key, count in seen.items() if count > 1}
    assert not duplicates, duplicates
    for entry in _plugin_entries(workspace["plugin"]):
        assert entry.argv[2].startswith('bash "'), entry.label


def test_codex_windows_command_mirrors_the_command(workspace: dict[str, Path]) -> None:
    """Codex runs ``commandWindows`` on Windows; it makes the same dispatcher call.

    The clauses above run ``command``. Each override must be that command with
    only the interpreter launcher swapped, so a clean run covers both strings.
    """
    config = workspace["home"] / ".codex" / "hooks.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    hooks = [
        hook
        for groups in data["hooks"].values()
        for group in groups
        for hook in group["hooks"]
    ]

    assert hooks
    for hook in hooks:
        command = hook["command"]
        assert command.startswith("python3 "), command
        assert hook.get("commandWindows") == "py -3 " + command.removeprefix("python3 ")


def test_shell_guards_cover_the_powershell_tool(workspace: dict[str, Path]) -> None:
    """Claude Code shell guards also match the PowerShell tool."""
    for entry in _all_entries(workspace):
        if entry.surface in {"plugin", "claude-engine"} and entry.message in {
            "pretooluse-bash",
            "pretooluse-bash-plan-guard",
        }:
            assert "PowerShell" in entry.matcher.split("|"), entry.matcher


def test_qwen_shell_matcher_names_the_runtime_tool(workspace: dict[str, Path]) -> None:
    """Qwen matches regex matchers against its tool id, run_shell_command."""
    for entry in _all_entries(workspace):
        if entry.surface == "qwen" and entry.message.startswith("pretooluse-bash"):
            assert "run_shell_command" in entry.matcher, entry.matcher


def test_hooks_never_run_project_supplied_code(workspace: dict[str, Path]) -> None:
    """A project's own hooks/ files are never sourced or executed by a hook."""
    for entry in _all_entries(workspace):
        if _is_engine_gate(entry):
            continue
        payload = _payload(entry.event, entry.matcher, workspace["hostile"], "hostile")
        env = _env_for(
            entry,
            workspace,
            workspace["hostile"],
            LLM_PROJECT_DIR=str(workspace["hostile"]),
        )
        result, _ = _run(entry, payload, env, workspace["hostile"])
        combined = result.stdout + result.stderr
        assert _HOSTILE_MARKER not in combined, entry.label
        # A command that cannot start never prints the marker either.
        assert result.returncode == 0, (entry.label, result.stderr[-300:])


def test_guards_are_silent_on_benign_payloads(workspace: dict[str, Path]) -> None:
    """Dependency and eval guards inject nothing unless the payload matches."""
    entries = [
        e
        for e in _all_entries(workspace)
        if e.message in {"pretooluse-dependency-guard", "pretooluse-eval-guard"}
    ]
    assert entries
    for entry in entries:
        env = _env_for(entry, workspace, workspace["project"])
        benign = _payload("PreToolUse", entry.matcher, workspace["project"], "benign")
        result, _ = _run(entry, benign, env, workspace["project"])
        assert _context_chars(_parse(result.stdout)) == 0, entry.label
        if entry.message == "pretooluse-dependency-guard":
            hit = _payload("PreToolUse", "Write", workspace["project"], "dep")
            hit["tool_input"] = {
                "file_path": str(workspace["project"] / "pyproject.toml"),
                "content": '[project]\ndependencies = ["requests"]\n',
            }
        else:
            hit = _payload("PreToolUse", "Write", workspace["project"], "eval")
            hit["tool_input"] = {
                "file_path": str(workspace["project"] / "run.py"),
                "content": "import pickle\nobj = pickle.loads(reply)\n",
            }
        result, _ = _run(entry, hit, env, workspace["project"])
        assert _context_chars(_parse(result.stdout)) > 0, entry.label
