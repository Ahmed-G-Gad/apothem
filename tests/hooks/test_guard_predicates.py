# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""Unit tests for the hook runtime pieces added for the hook contract.

Covers the maintainer-text stripper, the dependency and dynamic-eval guard
predicates (and their parity with the messages that declare the triggers), the
shell-tool name set, the dispatcher's global kill switch, and the per-user
state directory.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "hooks"
for _path in (_HOOKS_DIR, _HOOKS_DIR / "lib"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import dispatch  # noqa: E402
import emit_hook_context as ehc  # noqa: E402
import message_text  # noqa: E402
import state_dir  # noqa: E402

_MESSAGES = _HOOKS_DIR / "messages"


class TestStripMaintainerText:
    def test_drops_spdx_comment_and_bindings(self) -> None:
        body = (
            "<!-- SPDX-License-Identifier: MIT -->\n\nGuidance line.\n\n"
            "## Bindings (§0.j five-direction)\n\n- **Drives →** x\n"
        )
        assert message_text.strip_maintainer_text(body) == "Guidance line."

    def test_keeps_text_without_maintainer_blocks(self) -> None:
        assert message_text.strip_maintainer_text("A\n\nB\n") == "A\n\nB"

    def test_every_shipped_message_loses_its_spdx_line(self) -> None:
        for path in _MESSAGES.glob("*.md"):
            stripped = message_text.strip_maintainer_text(
                path.read_text(encoding="utf-8")
            )
            assert "<!-- SPDX-License-Identifier" not in stripped, path.name
            assert "## Bindings" not in stripped, path.name


class TestDependencyGuardPredicate:
    @pytest.mark.parametrize(
        "path",
        [
            "/p/pyproject.toml",
            "/p/requirements.txt",
            "/p/requirements-dev.txt",
            "/p/package.json",
            "/p/Cargo.toml",
            "/p/go.mod",
            "/p/Gemfile",
            "/p/uv.lock",
            "/p/poetry.lock",
            "/p/package-lock.json",
            "/p/pnpm-lock.yaml",
            "/p/yarn.lock",
            "/p/Cargo.lock",
            "/p/go.sum",
            "/p/Gemfile.lock",
            "C:\\\\work\\\\pyproject.toml",
        ],
    )
    def test_manifests_match(self, path: str) -> None:
        assert ehc._touches_dependency_manifest(path, "")

    @pytest.mark.parametrize(
        "path", ["/p/app.py", "/p/README.md", "/p/package.json.bak"]
    )
    def test_other_paths_do_not_match(self, path: str) -> None:
        assert not ehc._touches_dependency_manifest(path, "")

    def test_codex_patch_targets_are_read_from_the_patch_body(self) -> None:
        patch = "*** Begin Patch\n*** Update File: svc/requirements.txt\n@@\n+x\n"
        assert ehc._touches_dependency_manifest("", patch)
        assert not ehc._touches_dependency_manifest("", "*** Update File: svc/app.py\n")

    def test_parity_with_the_message_scope(self) -> None:
        """Every manifest the message names is matched by the predicate."""
        text = (_MESSAGES / "pretooluse-dependency-guard.md").read_text(
            encoding="utf-8"
        )
        scope = text.split("Scope.", 1)[1].split("\n\n", 1)[0]
        names = re.findall(r"`([^`]+)`", scope)
        assert names, "the message must list its manifests in backticks"
        for name in names:
            concrete = name.replace("*", "-dev")
            assert ehc._touches_dependency_manifest(f"/p/{concrete}", ""), name


class TestEvalGuardPredicate:
    @pytest.mark.parametrize(
        "text",
        [
            "eval(user_input)",
            "exec(code)",
            "compile(src, 'x', 'exec')",
            "new Function(body)",
            "os.system(cmd)",
            "subprocess.run(cmd, shell=True)",
            "require('child_process').exec(cmd)",
            "pickle.loads(blob)",
            "marshal.loads(blob)",
            "yaml.load(stream)",
            "yaml.unsafe_load(stream)",
            'eval "$(ssh-agent)"',
        ],
    )
    def test_primitives_match(self, text: str) -> None:
        assert ehc._has_eval_primitive(text)

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "ls -la",
            "pattern = re.compile(r'x')",
            "match = regex.exec(line)",
            "yaml.load(stream, Loader=yaml.SafeLoader)",
            "data = yaml.safe_load(stream)",
            "subprocess.run(['ls'], check=True)",
            "evaluate(model)",
        ],
    )
    def test_benign_text_does_not_match(self, text: str) -> None:
        assert not ehc._has_eval_primitive(text)


class TestShellToolNames:
    @pytest.mark.parametrize("tool", ["Bash", "PowerShell", "run_shell_command"])
    def test_git_mutation_fires_for_every_shell_tool(self, tool: str) -> None:
        payload: dict[str, object] = {
            "tool_name": tool,
            "tool_input": {"command": "git commit -m x"},
        }
        assert not ehc.should_suppress_bash_hook(
            "PreToolUse", "/m/pretooluse-bash.md", payload
        )

    def test_other_tools_are_suppressed(self) -> None:
        payload: dict[str, object] = {
            "tool_name": "Read",
            "tool_input": {"command": "git commit -m x"},
        }
        assert ehc.should_suppress_bash_hook(
            "PreToolUse", "/m/pretooluse-bash.md", payload
        )


class TestKillSwitch:
    @pytest.mark.parametrize("raw", ["1", "true", "YES", "on"])
    def test_truthy_values_silence_dispatch(
        self,
        raw: str,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(dispatch.DISABLE_ENV, raw)
        stream = io.StringIO(json.dumps({"tool_name": "Bash"}))
        monkeypatch.setattr(sys, "stdin", stream)
        dispatch.main(["PreToolUse", "pretooluse-bash"])
        assert capsys.readouterr().out == ""

    @pytest.mark.parametrize("raw", ["", "0", "false", "off", "anything"])
    def test_other_values_leave_hooks_on(
        self, raw: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(dispatch.DISABLE_ENV, raw)
        assert dispatch.hooks_disabled() is False


class TestStateDir:
    def test_override_wins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(state_dir.OVERRIDE_ENV, str(tmp_path / "s"))
        assert state_dir.hook_state_dir("x") == tmp_path / "s" / "x"

    def test_plugin_data_dir_is_used(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(state_dir.OVERRIDE_ENV, raising=False)
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "data"))
        assert state_dir.hook_state_dir("x") == tmp_path / "data" / "state" / "x"

    def test_xdg_state_home_is_used(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(state_dir.OVERRIDE_ENV, raising=False)
        monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
        assert state_dir.hook_state_dir("x") == tmp_path / "xdg" / "apothem" / "x"

    @pytest.mark.skipif(not hasattr(os, "getuid"), reason="POSIX permission bits")
    def test_directory_is_private(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loose = tmp_path / "s" / "x"
        loose.mkdir(parents=True, mode=0o777)
        loose.chmod(0o777)
        monkeypatch.setenv(state_dir.OVERRIDE_ENV, str(tmp_path / "s"))
        assert state_dir.hook_state_dir("x").stat().st_mode & 0o777 == 0o700

    @pytest.mark.parametrize("raw", [None, 7, "", "   ", "../..", "...."])
    def test_unusable_ids_key_by_parent_pid(self, raw: object) -> None:
        assert state_dir.session_key(raw) == f"ppid-{os.getppid()}"

    def test_ids_are_sanitized(self) -> None:
        assert state_dir.session_key("../../etc/passwd") == "etcpasswd"
        assert state_dir.session_key("abc-123_x.y") == "abc-123_x.y"


# REUSE-IgnoreEnd
