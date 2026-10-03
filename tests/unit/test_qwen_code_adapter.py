# SPDX-License-Identifier: MIT

"""Unit tests for the qwen-code harness adapter.

Protocol-conformance and install-smoke tests for the adapter.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

import pytest
import yaml

import apothem.harnesses.qwen_code as qwen_code_pkg
from apothem.harnesses import HarnessAdapter
from apothem.harnesses.qwen_code import QwenCodeAdapter
from apothem.harnesses.qwen_code.materializer import materialize_native_config

_ADAPTER_DIR = Path(qwen_code_pkg.__file__).resolve().parent


def _capabilities() -> dict[str, object]:
    return yaml.safe_load(
        (_ADAPTER_DIR / "capabilities.yml").read_text(encoding="utf-8")
    )


@pytest.fixture
def adapter() -> QwenCodeAdapter:
    return QwenCodeAdapter()


def test_protocol_conformance(adapter: QwenCodeAdapter) -> None:
    assert isinstance(adapter, HarnessAdapter)


def test_name(adapter: QwenCodeAdapter) -> None:
    assert adapter.name == "qwen-code"


def test_output_path_is_path(adapter: QwenCodeAdapter) -> None:
    assert isinstance(adapter.output_path, Path)


def test_is_installed_returns_bool(adapter: QwenCodeAdapter) -> None:
    result = adapter.is_installed()
    assert isinstance(result, bool)


def test_install_accepts_empty_profile(
    adapter: QwenCodeAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({})  # must not raise
    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert parsed["context"]["fileName"] == "QWEN.md"
    assert "hooks" in parsed
    assert (tmp_path / "QWEN.md").is_file()


def test_materializer_emits_qwen_hook_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pin the resolver to a fixed absolute path so the asserted command is
    # deterministic across hosts. The install driver still renders the
    # ${HARNESS_ROOT} token in the script path to an absolute path at write time.
    from apothem.harnesses.qwen_code import materializer as qwen_materializer

    monkeypatch.setattr(
        qwen_materializer, "resolve_python_bin", lambda: Path("/usr/bin/python3.12")
    )
    parsed = json.loads(materialize_native_config({}))
    pretool_entries = parsed["hooks"]["PreToolUse"]
    assert pretool_entries[0]["matcher"] == "^run_shell_command$"
    assert pretool_entries[0]["sequential"] is True
    first_hook = pretool_entries[0]["hooks"][0]
    assert first_hook["type"] == "command"
    # The command leads with the resolved absolute interpreter path (never a
    # bare ``python``) and addresses the installed dispatcher by ${HARNESS_ROOT}
    # token; the install driver renders that token to an absolute path at write
    # time.
    assert first_hook["command"] == (
        '/usr/bin/python3.12 "${HARNESS_ROOT}/.apothem/support/hooks/dispatch.py" '
        "PreToolUse pretooluse-bash"
    )
    # Qwen reads command-hook timeouts in seconds (a value of 1000 or more is
    # only accepted as legacy milliseconds).
    assert first_hook["timeout"] == 10


def _hook_entries(parsed: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    """Return every emitted hook handler grouped by event name."""
    hooks = parsed["hooks"]
    assert isinstance(hooks, dict)
    grouped: dict[str, list[dict[str, object]]] = {}
    for event, blocks in hooks.items():
        for block in blocks:
            grouped.setdefault(event, []).extend(block["hooks"])
    return grouped


def test_materializer_hook_timeouts_are_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Qwen Code documents command-hook ``timeout`` in seconds and reads a value
    # of 1000 or more as legacy milliseconds. Every emitted timeout must be a
    # seconds value: PreToolUse 10 s, session-lifecycle events 30 s, Stop 60 s.
    from apothem.harnesses.qwen_code import materializer as qwen_materializer

    monkeypatch.setattr(
        qwen_materializer, "resolve_python_bin", lambda: Path("/usr/bin/python3")
    )
    grouped = _hook_entries(json.loads(materialize_native_config({})))
    expected = {
        "SessionStart": 30,
        "PreToolUse": 10,
        "PreCompact": 30,
        "PostCompact": 30,
        "Stop": 60,
    }
    assert set(grouped) == set(expected)
    for event, handlers in grouped.items():
        for handler in handlers:
            assert handler["timeout"] == expected[event], (event, handler)
            assert isinstance(handler["timeout"], int)
            assert handler["timeout"] < 1000


@pytest.mark.parametrize(
    "interpreter",
    [
        "C:/Program Files/Python311/python.exe",
        "/Users/jane doe/.pyenv/versions/3.12.4/bin/python3",
    ],
)
def test_materializer_quotes_an_interpreter_path_with_spaces(
    monkeypatch: pytest.MonkeyPatch, interpreter: str
) -> None:
    # The hook command is a shell-form string. An interpreter under a path with
    # spaces must be one quoted token, or the shell splits it and every guard
    # fails to spawn (the dispatcher is fail-open, so the loss is silent).
    from apothem.harnesses.qwen_code import materializer as qwen_materializer

    monkeypatch.setattr(
        qwen_materializer, "resolve_python_bin", lambda: PurePosixPath(interpreter)
    )
    grouped = _hook_entries(json.loads(materialize_native_config({})))
    for handlers in grouped.values():
        for handler in handlers:
            command = handler["command"]
            assert isinstance(command, str)
            assert command.startswith(
                f'"{interpreter}" "${{HARNESS_ROOT}}/.apothem/support/hooks/'
            ), command


def test_materializer_hook_commands_resolve_a_real_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # H9 regression: on a python3-only POSIX host a bare ``python`` command
    # fails to spawn, silently disabling every guard. The materializer must emit
    # the resolved absolute interpreter path — never a bare ``python`` /
    # ``python3`` — as the leading token of every hook command.
    from apothem.harnesses.qwen_code import materializer as qwen_materializer

    resolved = Path("/opt/python3-only/bin/python3")
    monkeypatch.setattr(qwen_materializer, "resolve_python_bin", lambda: resolved)
    parsed = json.loads(materialize_native_config({}))
    commands: list[str] = []
    for entries in parsed["hooks"].values():
        for block in entries:
            for hook in block["hooks"]:
                commands.append(hook["command"])
    assert commands, "materializer emitted no hook commands"
    for command in commands:
        leading = command.split(" ", 1)[0]
        assert leading not in {"python", "python3"}, command
        # The resolver emits its path via ``as_posix()``; check absoluteness in
        # POSIX terms so the assertion holds on a Windows test host too.
        assert PurePosixPath(leading).is_absolute(), command
        assert leading == resolved.as_posix(), command


def test_uninstall_noop_when_not_installed(
    adapter: QwenCodeAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nonexistent_config"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: missing))
    adapter.uninstall()  # must not raise when output_path does not exist


def test_uninstall_keeps_operator_keys_and_strips_apothem(
    adapter: QwenCodeAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Surgical uninstall of the materializer-rendered settings.json: install,
    # add an operator key, uninstall, and assert the operator key survives while
    # Apothem's keys are stripped — with NO whole-file .bak sibling.
    import json

    from apothem.harnesses._shared import install_driver

    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    target = tmp_path / "settings.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({})
    installed = json.loads(target.read_text(encoding="utf-8"))
    assert "context" in installed  # Apothem-authored key
    assert "hooks" in installed  # Apothem-authored hook wiring
    installed["operatorKey"] = "keep-me"
    target.write_text(json.dumps(installed, indent=2), encoding="utf-8")

    adapter.uninstall()

    assert target.is_file()  # operator content remains
    remaining = json.loads(target.read_text(encoding="utf-8"))
    assert remaining.get("operatorKey") == "keep-me"
    assert "context" not in remaining
    assert "hooks" not in remaining
    assert not list(tmp_path.glob("settings.json.*.bak"))


def test_capabilities_template_path_resolves_and_commands_are_markdown() -> None:
    # The declared system-prompt template must name a real on-disk template
    # (templates/QWEN.md), not a non-existent .j2 variant; and commands are
    # Markdown (Qwen Code consumes Markdown command definitions; TOML is not
    # part of its surface, so the adapter must not emit TOML).
    capabilities = _capabilities()
    template_rel = capabilities["system_prompt_template_path"]
    assert isinstance(template_rel, str)
    assert (_ADAPTER_DIR / template_rel).is_file()
    assert capabilities["custom_command_support"] == "markdown"


_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_qwen_extension_ships_a_markdown_bootstrap_command() -> None:
    # Qwen Code deprecates TOML commands and shows a migration prompt when it
    # finds one. The repo root serves both the Gemini CLI extension (TOML only,
    # read from ``commands/``) and the Qwen Code extension, so the Qwen manifest
    # points its ``commands`` key at a Qwen-only directory that carries the
    # Markdown form of the same bootstrap command.
    manifest = json.loads(
        (_REPO_ROOT / "qwen-extension.json").read_text(encoding="utf-8")
    )
    commands_dir = manifest.get("commands")
    assert isinstance(commands_dir, str)
    assert commands_dir != "commands"
    root = _REPO_ROOT / commands_dir
    assert not list(root.glob("**/*.toml")), "Qwen must not see a TOML command"
    command = root / "apothem.md"
    text = command.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "frontmatter must be the first content"
    _, frontmatter, body = text.split("---\n", 2)
    meta = yaml.safe_load(frontmatter)
    assert isinstance(meta, dict)
    assert meta.get("description")
    # The engine call is pinned to the extension's own version.
    assert re.search(r"!\{npx @ahmed-g-gad/apothem@\d+\.\d+\.\d+ \{\{args\}\}\}", body)
    # The Gemini extension keeps its TOML command in the shared directory.
    assert (_REPO_ROOT / "commands" / "apothem.toml").is_file()
