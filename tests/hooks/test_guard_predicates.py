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

    @pytest.mark.parametrize("line", ["<!-- note -->", "  <!-- note -->\t", "<!---->"])
    def test_drops_a_line_that_is_one_whole_comment(self, line: str) -> None:
        assert message_text.strip_maintainer_text(f"A\n{line}\nB\n") == "A\nB"

    @pytest.mark.parametrize(
        "line",
        [
            "<!-->",
            "<!--->",
            "<!-- note --> trailing",
            "leading <!-- note -->",
            "<!-- never closed",
        ],
    )
    def test_keeps_a_line_that_is_not_one_whole_comment(self, line: str) -> None:
        assert message_text.strip_maintainer_text(f"A\n{line}\nB\n") == f"A\n{line}\nB"

    def test_keeps_a_comment_that_spans_lines(self) -> None:
        # The stripper works a line at a time: the comment it removes is the
        # one-line SPDX header every message file opens with.
        body = "A\n<!-- first\nsecond -->\nB"
        assert message_text.strip_maintainer_text(body) == body

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
            "result = eval(x)",
            "new Function('a', 'return a')",
            "const fn = Function('a')",
            'eval "$cmd"',
            "eval $cmd",
            "eval 'echo hi'",
            "eval `ssh-agent -s`",
            'x=1; eval "$x"',
            'a && eval "$b"',
            'cd /tmp\n  eval "$(tool env)"',
            'eval set -- "$OPTS"',
            'eval export "$x"',
            'eval -- "$x"',
            "eval echo ~$USER",
            "eval cmd_$x",
            r"eval echo \$$name",
            "yaml.load(open(path))",
            "yaml.load(\n    stream,\n    Loader=yaml.FullLoader,\n)",
            "yaml.load(stream)\nloader = yaml.SafeLoader",
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
            "yaml.load(open('f'), Loader=yaml.SafeLoader)",
            "yaml.load(open(f), Loader=yaml.CSafeLoader)",
            "yaml.load(\n    stream,\n    Loader=yaml.SafeLoader,\n)",
            "data = yaml.safe_load(stream)",
            "subprocess.run(['ls'], check=True)",
            "evaluate(model)",
        ],
    )
    def test_benign_text_does_not_match(self, text: str) -> None:
        assert not ehc._has_eval_primitive(text)

    @pytest.mark.parametrize(
        "text",
        [
            '"""Perf-audit eval (one-off) over the corpus."""',
            "perf-audit eval (one-off)",
            "see compile (the docs) for the flags",
            "Function (deprecated) since 2.0",
            "the guard flags eval ( in prose",
            "run exec (the stage) next",
            "result = eval (x)",
            "pattern = re.compile (r'x')",
            "eval is the primitive the guard looks for",
            "eval the result before shipping",
            "eval (one-off) results are in the table",
            "  eval is indented prose",
            "eval\n$cmd",
            'retrieval "$x"',
            "cat <<'EOF'\nPerf-audit eval (one-off)\neval (one-off) is quiet too\nEOF",
        ],
    )
    def test_prose_does_not_match(self, text: str) -> None:
        assert not ehc._has_eval_primitive(text)

    @pytest.mark.parametrize(
        "text",
        [
            "def compile(self, source):",
            "    async def exec(self):",
            "function eval(s) {}",
            "pub fn eval(&self) -> Value",
            "fun exec(cmd: String)",
            "func compile(src string)",
            "The eval() function is dangerous",
            "Avoid `eval()` in prose",
            "Call exec() to run it",
            "const f = Function()",
            "class Function(Application, Expr):",
        ],
    )
    def test_definitions_and_empty_calls_are_not_calls(self, text: str) -> None:
        assert not ehc._has_eval_primitive(text)

    @pytest.mark.parametrize(
        ("text", "token"),
        [
            ("eval(x)", "`eval(`"),
            ("exec(code)", "`exec(`"),
            ("compile(src, f, 'exec')", "`compile(`"),
            ("new Function('a')", "`new Function(`"),
            ('eval "$cmd"', "`eval`"),
            ('cd /tmp;\n  eval "$cmd"', "`eval`"),
            ('make && eval "$cmd"', "`eval`"),
        ],
    )
    def test_reports_the_matched_construct(self, text: str, token: str) -> None:
        assert ehc._eval_primitives(text) == [token]

    def test_heredoc_body_is_scanned_like_a_write(self) -> None:
        command = "cat > run.py <<'EOF'\nimport os\nresult = eval(payload)\nEOF"
        assert ehc._eval_primitives(command) == ["`eval(`"]

    def test_guard_stays_silent_on_prose_and_speaks_on_code(self) -> None:
        def values(content: str) -> dict[str, str] | None:
            payload: dict[str, object] = {
                "cwd": str(_HOOKS_DIR),
                "tool_name": "Write",
                "tool_input": {"file_path": "/p/notes.py", "content": content},
            }
            return ehc.guard_values(
                "PreToolUse",
                str(_MESSAGES / "pretooluse-eval-guard.md"),
                payload,
                _HOOKS_DIR,
            )

        assert values('"""Perf-audit eval (one-off)."""\n') is None
        assert values("value = eval(text)\n") == {
            "path": "/p/notes.py",
            "primitives": "`eval(`",
        }

    def test_adversarial_whitespace_stays_fast(self) -> None:
        import time

        started = time.perf_counter()
        for text in (
            "\n" * 50_000,
            ";" + " " * 50_000,
            "\n\t " * 20_000,
            ";eval x" * 20_000,
            "eval" + " " * 100_000,
        ):
            assert not ehc._has_eval_primitive(text)
        assert time.perf_counter() - started < 2.0

    def test_adversarial_yaml_calls_stay_fast(self) -> None:
        import time

        started = time.perf_counter()
        for text in (
            "yaml.load(" * 20_000,
            "yaml.load(" + "(a)" * 50_000,
            ("yaml.load(" + "(a)" * 150) * 500,
        ):
            assert ehc._has_eval_primitive(text)
        assert time.perf_counter() - started < 2.0

    @staticmethod
    def _command_values(command: str) -> dict[str, str] | None:
        payload: dict[str, object] = {
            "cwd": str(_HOOKS_DIR),
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
        message = str(_MESSAGES / "pretooluse-eval-guard.md")
        return ehc.guard_values("PreToolUse", message, payload, _HOOKS_DIR)

    @pytest.mark.parametrize(
        "command",
        [
            "grep -rn 'eval(' src/",
            r"rg 'exec\(' .",
            "grep -rn 'eval(' src/ 2>/dev/null | grep -v tests",
            'git commit -m "narrow the eval() guard"',
            "git grep -n 'compile(' -- '*.py'",
            "git log --oneline --grep='eval('",
            "cd src && grep -n 'exec(' app.py",
        ],
    )
    def test_a_search_or_commit_command_is_not_scanned(self, command: str) -> None:
        assert self._command_values(command) is None

    @pytest.mark.parametrize(
        "command",
        [
            "echo 'eval(x)' > run.py",
            "sed -i 's/a/eval(b)/' run.py",
            'grep x f; eval "$y"',
            'grep x f & eval "$y"',
            'grep x f && eval "$y"',
            "grep -n \"$(python -c 'eval(1)')\" f",
            "grep `python -c 'exec(1)'` f",
            "git commit -m \"$(cat <<'EOF'\nresult = eval(x)\nEOF\n)\"",
            "grep x f | xargs -I{} python -c 'eval({})'",
        ],
    )
    def test_any_other_command_is_still_scanned(self, command: str) -> None:
        assert self._command_values(command) is not None

    @pytest.mark.parametrize(
        ("command", "fires"),
        [
            ("grep -rn 'eval(' src/", False),
            ('git commit -m "narrow the eval() guard"', False),
            ("python -c 'eval(input())'", True),
            ("grep -n x f; python -c 'exec(s)'", True),
        ],
    )
    def test_the_dispatched_bash_hook_follows_the_search_skip(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        command: str,
        fires: bool,
    ) -> None:
        payload = {
            "tool_name": "Bash",
            "cwd": str(_HOOKS_DIR),
            "tool_input": {"command": command},
        }
        stream = io.StringIO(json.dumps(payload))
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)
        message = str(_MESSAGES / "pretooluse-eval-guard.md")
        ehc.run_hook_mode_multi("PreToolUse", [message], False, _HOOKS_DIR)
        envelope = json.loads(capsys.readouterr().out)
        context = envelope["hookSpecificOutput"]["additionalContext"]
        assert bool(context) is fires
        if fires:
            assert "Dynamic evaluation" in context

    def test_the_search_skip_does_not_reach_a_write(self) -> None:
        payload: dict[str, object] = {
            "cwd": str(_HOOKS_DIR),
            "tool_name": "Write",
            "tool_input": {"file_path": "/p/a.py", "content": "grep x\neval(y)\n"},
        }
        message = str(_MESSAGES / "pretooluse-eval-guard.md")
        assert ehc.guard_values("PreToolUse", message, payload, _HOOKS_DIR) is not None


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
