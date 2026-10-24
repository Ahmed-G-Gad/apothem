# SPDX-License-Identifier: MIT

"""Hooks that stay quiet when nothing is wrong and cheap when they run.

Pins the behaviour that keeps per-tool-call hooks from costing context or time:

* the guards anchor "inside the project" on the payload's ``cwd`` (never on the
  tree the hook is installed in), so a write to the project's own plans tree is
  silent under a plugin install;
* a firing guard injects only its ``## Advisory`` template, filled with the
  findings, plus a pointer to the full procedure;
* every guard for one matcher runs in one process and answers with one
  envelope;
* the Bash plan guard inspects write targets, not substrings, and the git
  reminder fires only on a mechanical finding;
* the compaction tracker reads the measured context size and resets after a
  compaction;
* the bootstrap caches the interpreter it probed and accepts several messages.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_DIR = _REPO_ROOT / "src" / "apothem" / "hooks"
_MESSAGES = _HOOKS_DIR / "messages"
for _path in (_HOOKS_DIR, _HOOKS_DIR / "lib"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import dispatch  # noqa: E402
import emit_hook_context as ehc  # noqa: E402
import message_text  # noqa: E402
import proactive_compaction_tracker as pct  # noqa: E402
import state_dir  # noqa: E402

from apothem.lib.plugin_tree import build_plugin_hooks_json  # noqa: E402

_BASH = find_test_bash()
# Built in two parts so licence scanners do not read the literal as this file's
# own licence expression.
_HEADER = "# SPDX" + "-License-Identifier: MIT\n"


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / ".git").mkdir(parents=True)
    return root


def _run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payload: dict[str, object],
    *messages: str,
) -> str:
    stream = io.StringIO(json.dumps(payload))
    stream.isatty = lambda: False  # type: ignore[method-assign]
    monkeypatch.setattr(sys, "stdin", stream)
    ehc.run_hook_mode_multi(
        "PreToolUse", [str(_MESSAGES / f"{m}.md") for m in messages], False, _HOOKS_DIR
    )
    envelope = json.loads(capsys.readouterr().out)
    return str(envelope["hookSpecificOutput"]["additionalContext"])


class TestProjectRoot:
    """The project is the git root above the payload ``cwd``."""

    def test_payload_cwd_wins(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "src").mkdir()
        assert ehc.target_project_root({"cwd": str(root / "src")}) == root.resolve()

    def test_plans_write_is_silent_whatever_tree_the_hook_lives_in(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The regression: the plan guard used the hook's install tree as the
        # project root, so every write to the project's own plans tree fired.
        root = _project(tmp_path)
        payload = {
            "tool_name": "Write",
            "cwd": str(root),
            "tool_input": {
                "file_path": str(root / ".apothem" / "plans" / "p.md"),
                "content": "---\nphases: 3\n---\nTracks CM-19 and Phase-B.\n",
            },
        }
        text = _run(
            monkeypatch,
            capsys,
            payload,
            "pretooluse-write",
            "pretooluse-write-plan-guard",
        )
        assert text == ""


class TestPlanVerdicts:
    """The plans-locality matrix, applied mechanically."""

    @pytest.mark.parametrize(
        "rel",
        [
            ".apothem/plans/s/PLAN.md",
            ".plans/s/PLAN.md",
            "docs/plan-notes.md",
            "src/x.py",
        ],
    )
    def test_inside_the_project_is_allowed(self, tmp_path: Path, rel: str) -> None:
        root = _project(tmp_path)
        assert (
            ehc.classify_plan_target(str(root / rel), "phases:\n", root)
            == ehc.PLAN_ALLOW
        )

    def test_a_plans_tree_elsewhere_is_redirect_required(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        target = tmp_path / "home" / ".claude" / ".plans" / "p.md"
        assert ehc.classify_plan_target(str(target), "", root) == ehc.PLAN_REDIRECT

    def test_a_plan_named_file_elsewhere_is_soft_flagged(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        target = tmp_path / "Desktop" / "release-plan.md"
        assert ehc.classify_plan_target(str(target), "", root) == ehc.PLAN_SOFT_FLAG

    def test_the_scratchpad_is_exempt_from_the_soft_flag(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        scratch = tmp_path / "scratch"
        target = scratch / "notes.md"
        exempt = ehc._exempt_roots({"scratchpad_dir": str(scratch)})
        assert ehc.classify_plan_target(str(target), "", root, exempt) == ehc.PLAN_ALLOW


class TestShellWriteTargets:
    """Only paths a command writes are classified."""

    @pytest.mark.parametrize(
        ("command", "expected"),
        [
            ("echo hi > out.md", ["out.md"]),
            ("cat >> 'a b.md' <<'EOF'\nx\nEOF", ["'a b.md'"]),
            ("ls | tee -a log.txt other.txt", ["log.txt", "other.txt"]),
            ("Get-Date | Out-File -FilePath plan.md", ["plan.md"]),
            ("cp a.md b.md && mv b.md c.md", ["b.md", "c.md"]),
            ("python -m pytest -q 2>/dev/null", []),
            ("ls .apothem/plans", []),
        ],
    )
    def test_targets(self, command: str, expected: list[str]) -> None:
        assert ehc.shell_write_targets(command) == expected

    def test_reading_the_plans_tree_is_silent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        payload = {
            "tool_name": "Bash",
            "cwd": str(root),
            "tool_input": {"command": "mkdir -p .apothem/plans && ls .apothem/plans"},
        }
        assert _run(monkeypatch, capsys, payload, "pretooluse-bash-plan-guard") == ""

    def test_writing_a_global_plans_tree_fires_briefly(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        target = tmp_path / "home" / ".plans" / "p.md"
        payload = {
            "tool_name": "Bash",
            "cwd": str(root),
            "tool_input": {"command": f"echo x > {target.as_posix()}"},
        }
        text = _run(monkeypatch, capsys, payload, "pretooluse-bash-plan-guard")
        assert "redirect-required" in text
        assert "Full procedure:" in text
        assert len(text) < 800


class TestPlanTerms:
    """Public identifiers that look like plan ids are not plan terms."""

    def test_standard_ids_are_ignored(self) -> None:
        assert ehc._plan_terms("UTF-8, SHA-256, ISO-8601, CVE-2026-1, RFC-2119") == []

    def test_plan_ids_are_found(self) -> None:
        assert ehc._plan_terms("see CM-19 and Phase-B, again CM-19") == [
            "CM-19",
            "Phase-B",
        ]

    def test_writes_outside_the_project_are_not_scanned(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        payload = {
            "tool_name": "Write",
            "cwd": str(root),
            "tool_input": {
                "file_path": str(tmp_path / "memory" / "m.md"),
                "content": "CM-19",
            },
        }
        assert _run(monkeypatch, capsys, payload, "pretooluse-write") == ""


class TestGitReminder:
    """The git reminder is a mechanical check, not a standing lecture."""

    def test_clean_commit_is_silent(self) -> None:
        assert (
            ehc._git_write_findings('git commit -m "fix(hooks): handle UTF-8 paths"')
            == []
        )

    def test_findings(self) -> None:
        command = 'git commit -m "close CM-7" -m "Co-Authored-By: Claude <noreply@anthropic.com>"'
        findings = ehc._git_write_findings(command)
        assert any("`CM-7`" in f for f in findings)
        assert any("attribution" in f for f in findings)

    def test_suite_root_numeric_prefix(self) -> None:
        findings = ehc._git_write_findings("git mv a.md .apothem/plans/s/00-NOTES.md")
        assert any("numeric prefix" in f for f in findings)


class TestAdvisoryRendering:
    """A firing guard injects its short template, filled, and nothing else."""

    def test_every_guard_message_has_an_advisory(self) -> None:
        guards = sorted(_MESSAGES.glob("pretooluse-*.md"))
        missing = [
            p.name
            for p in guards
            if p.stem
            not in {"pretooluse-conformity", "pretooluse-askuserquestion-recommended"}
            and message_text.advisory_section(p.read_text(encoding="utf-8")) is None
        ]
        assert missing == []

    def test_fill_leaves_unknown_placeholders(self) -> None:
        assert message_text.fill_placeholders("{a} {b} {}", {"a": "x"}) == "x {b} {}"

    def test_merged_envelope_is_short(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        payload = {
            "tool_name": "Write",
            "cwd": str(root),
            "tool_input": {
                "file_path": str(root / "app.py"),
                "content": _HEADER + "value = eval(text)  # CM-19\n",
            },
        }
        text = _run(
            monkeypatch,
            capsys,
            payload,
            "pretooluse-write",
            "pretooluse-write-plan-guard",
            "pretooluse-eval-guard",
        )
        assert text.startswith("[tool=Write]")
        assert "`CM-19`" in text
        assert "`eval(`" in text
        assert text.count("Full procedure:") == 2
        assert "Fail-disposition" not in text
        assert len(text) < 1500


class TestFastParse:
    """The dispatcher reads its fixed shapes without argparse."""

    def test_positional_messages(self) -> None:
        parsed = dispatch.fast_parse(
            ["PreToolUse", "pretooluse-write", "pretooluse-eval-guard"]
        )
        assert parsed is not None
        assert parsed.event_name == "PreToolUse"
        assert [Path(p).name for p in parsed.context_files] == [
            "pretooluse-write.md",
            "pretooluse-eval-guard.md",
        ]

    def test_flag_form_repeats(self) -> None:
        parsed = dispatch.fast_parse(
            ["--event-name", "PreToolUse", "--context-file", "a.md", "-c", "b.md", "-q"]
        )
        assert parsed is not None
        assert parsed.context_files == ["a.md", "b.md"]
        assert parsed.quiet is True

    @pytest.mark.parametrize(
        "argv",
        [["--help"], ["--event-name=Stop"], [], ["--context-file"], ["-x", "Stop"]],
    )
    def test_anything_else_falls_back(self, argv: list[str]) -> None:
        assert dispatch.fast_parse(argv) is None


class TestPluginHooksJson:
    """One process per matcher; the tracker never blocks."""

    def test_one_entry_per_matcher(self) -> None:
        events = build_plugin_hooks_json("lib/apothem")["hooks"]
        assert isinstance(events, dict)
        for groups in events.values():
            for group in groups:
                assert len(group["hooks"]) == 1

    def test_tracker_is_async(self) -> None:
        events = build_plugin_hooks_json("lib/apothem")["hooks"]
        assert isinstance(events, dict)
        (post,) = events["PostToolUse"]
        assert post["hooks"][0].get("async") is True
        (pre_write,) = [g for g in events["PreToolUse"] if g["matcher"] == "Write"]
        assert "async" not in pre_write["hooks"][0]


class TestContextTracker:
    """The tracker measures the context instead of guessing from output bytes."""

    @pytest.fixture(autouse=True)
    def _isolate(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv(state_dir.OVERRIDE_ENV, str(tmp_path / "state"))
        for name in (
            pct.CONTEXT_WINDOW_ENV,
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
            pct.ENABLED_ENV,
        ):
            monkeypatch.delenv(name, raising=False)

    @staticmethod
    def _transcript(path: Path, tokens: int, *, sidechain: int | None = None) -> None:
        usage = {"input_tokens": 2, "cache_read_input_tokens": tokens - 2}
        lines = [{"type": "assistant", "message": {"usage": usage}}]
        if sidechain is not None:
            lines.append(
                {
                    "type": "assistant",
                    "isSidechain": True,
                    "message": {"usage": {"input_tokens": sidechain}},
                }
            )
        with path.open("a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(json.dumps(line, separators=(",", ":")) + "\n")

    def test_reads_the_newest_main_thread_usage(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        self._transcript(transcript, 1000)
        self._transcript(transcript, 5000, sidechain=99)
        assert pct.context_tokens({"transcript_path": str(transcript)}) == 5000

    @pytest.mark.parametrize(
        ("tokens", "window", "sent", "level"),
        [
            (100_000, None, 0, None),
            (130_000, None, 0, 1),
            (130_000, None, 1, None),
            (260_000, None, 0, 2),
            (400_000, 1_000_000, 0, None),
            (500_000, 1_000_000, 0, 1),
            (760_000, 1_000_000, 1, 2),
        ],
    )
    def test_policy(
        self, tokens: int, window: int | None, sent: int, level: int | None
    ) -> None:
        assert pct.advisory_level(tokens, window, sent) == level

    def test_two_advisories_then_compaction_restarts(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        payload: dict[str, object] = {
            "session_id": "s",
            "transcript_path": str(transcript),
        }
        self._transcript(transcript, 130_000)
        first = pct.evaluate(payload)
        assert "130,000 tokens" in str(first["hookSpecificOutput"])  # type: ignore[index]
        assert pct.evaluate(payload) == {}
        self._transcript(transcript, 260_000)
        assert pct.evaluate(payload) != {}
        self._transcript(transcript, 270_000)
        assert pct.evaluate(payload) == {}
        self._transcript(transcript, 20_000)  # compacted
        assert pct.evaluate(payload) == {}
        self._transcript(transcript, 125_000)
        assert pct.evaluate(payload) != {}

    def test_model_text_never_asks_the_model_to_compact(self) -> None:
        for level in (1, 2):
            text = pct._advisory_text(level, 300_000, None).lower()
            assert "compact" not in text.replace("proactive-compaction", "")


class TestReviewRegressions:
    """Cases the adversarial review of this change turned up."""

    def test_relative_targets_resolve_against_the_payload_cwd(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        (root / "sub").mkdir()
        inside = {
            "tool_name": "Bash",
            "cwd": str(root / "sub"),
            "tool_input": {"command": "echo x > ../.apothem/plans/s/PHASE.md"},
        }
        assert _run(monkeypatch, capsys, inside, "pretooluse-bash-plan-guard") == ""
        escaping = {
            "tool_name": "Bash",
            "cwd": str(root / "sub"),
            "tool_input": {"command": "echo x > ../../home/.plans/p.md"},
        }
        assert "redirect-required" in _run(
            monkeypatch, capsys, escaping, "pretooluse-bash-plan-guard"
        )

    def test_apply_patch_targets_are_classified(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        outside = (tmp_path / "home" / ".apothem" / "plans" / "p.md").as_posix()
        patch = (
            f"*** Begin Patch\n*** Add File: {outside}\n+master-plan: x\n*** End Patch"
        )
        payload = {
            "tool_name": "apply_patch",
            "cwd": str(root),
            "tool_input": {"command": patch},
        }
        assert "redirect-required" in _run(
            monkeypatch, capsys, payload, "pretooluse-write-plan-guard"
        )
        local = (root / ".apothem" / "plans" / "p.md").as_posix()
        patch = f"*** Begin Patch\n*** Add File: {local}\n+tracks CM-19\n*** End Patch"
        payload = {
            "tool_name": "apply_patch",
            "cwd": str(root),
            "tool_input": {"command": patch},
        }
        text = _run(
            monkeypatch,
            capsys,
            payload,
            "pretooluse-write",
            "pretooluse-write-plan-guard",
        )
        assert text == ""

    @pytest.mark.parametrize(
        ("command", "expected"),
        [
            ("cp a.md b.md > log.txt", ["log.txt", "b.md"]),
            ("cp -t /dest a.md b.md", ["/dest"]),
            ("mv --target-directory=/dest a.md", ["/dest"]),
            ("touch a.md b.md", ["a.md", "b.md"]),
            ("echo hi # > x.md", []),
            ("Set-Content -Value hi -Path plan.md", ["plan.md"]),
            ("Out-File -Encoding utf8 -FilePath:x.md", ["x.md"]),
            ("Copy-Item a.md -Destination b.md", ["b.md"]),
            ("New-Item -ItemType File notes.md", ["notes.md"]),
            ("FOO=1 sudo tee -a out.md", ["out.md"]),
            ("cat > s.py <<'EOF'\nif a > b.md:\n    pass\nEOF", ["s.py"]),
        ],
    )
    def test_write_target_forms(self, command: str, expected: list[str]) -> None:
        assert ehc.shell_write_targets(command) == expected

    def test_targets_are_capped(self) -> None:
        command = "; ".join(f"echo x > f{i}.md" for i in range(200))
        assert len(ehc.shell_write_targets(command)) == ehc._MAX_SHELL_TARGETS

    def test_unc_paths_are_never_resolved(self) -> None:
        assert (
            ehc._resolve_target("\\\\server\\share\\.plans\\p.md", Path.cwd()) is None
        )
        assert ehc._resolve_target("//server/share/.plans/p.md", Path.cwd()) is None

    def test_os_temp_dir_is_exempt_without_temp_variables(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import tempfile

        for name in ("TMPDIR", "TEMP", "TMP"):
            monkeypatch.delenv(name, raising=False)
        root = _project(tmp_path / "work")
        target = Path(tempfile.gettempdir()) / "apothem-test-notes.md"
        verdict = ehc.classify_plan_target(
            str(target), "", root, lambda: ehc._exempt_roots(None)
        )
        assert verdict == ehc.PLAN_ALLOW

    @pytest.mark.parametrize(
        "command",
        [
            'git commit -m "x" -m "Co-Authored-By: Jane Doe <jane@example.com>"',
            'git commit -m "x" -m "Co-Authored-By: Ro Bot <robot@example.com>"',
            'git commit -m "fix: explain the Claude Code hook contract"',
        ],
    )
    def test_human_and_product_mentions_are_not_attribution(self, command: str) -> None:
        assert ehc._git_write_findings(command) == []

    @pytest.mark.parametrize(
        "command",
        [
            'git commit -m "x" -m "Co-Authored-By: Qwen Coder <q@example.com>"',
            'git commit -m "x" -m "Co-Authored-By: ci <ci-bot@example.com>"',
            'git commit -m "[ai] tidy imports"',
            'git -c user.email=noreply@anthropic.com commit -m "x"',
            'git commit -m "update the Resumption Contract"',
        ],
    )
    def test_attribution_and_plan_vocabulary_are_found(self, command: str) -> None:
        assert ehc._git_write_findings(command) != []

    def test_adversarial_inputs_stay_fast(self) -> None:
        import time

        long_line = "Co-Authored-By: " + "a" * 50_000
        many_tokens = "cp " + " ".join(f"f{i}" for i in range(20_000)) + " dest"
        yaml_calls = "yaml.load(" * 20_000
        started = time.perf_counter()
        ehc._git_write_findings("git commit -m '" + long_line + "'")
        ehc.shell_write_targets(many_tokens)
        ehc._eval_primitives(yaml_calls)
        assert time.perf_counter() - started < 2.0


@pytest.mark.skipif(_BASH is None, reason=SKIP_REASON)
def test_bootstrap_ignores_a_relative_state_dir(tmp_path: Path) -> None:
    assert _BASH is not None
    env = dict(os.environ)
    env["APOTHEM_HOOK_STATE_DIR"] = "relative-state"
    payload = json.dumps({"tool_name": "Write", "cwd": str(tmp_path), "tool_input": {}})
    result = subprocess.run(
        [
            _BASH,
            str(_HOOKS_DIR / "lib" / "bootstrap.sh"),
            "PreToolUse",
            str(_MESSAGES / "pretooluse-write.md"),
        ],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "relative-state").exists()


@pytest.mark.skipif(_BASH is None, reason=SKIP_REASON)
def test_bootstrap_caches_the_interpreter_and_takes_several_messages(
    tmp_path: Path,
) -> None:
    assert _BASH is not None
    env = dict(os.environ)
    env["APOTHEM_HOOK_STATE_DIR"] = str(tmp_path / "state")
    payload = json.dumps({"tool_name": "Write", "cwd": str(tmp_path), "tool_input": {}})
    stub = _HOOKS_DIR / "lib" / "bootstrap.sh"
    for _ in range(2):
        result = subprocess.run(
            [
                _BASH,
                str(stub),
                "PreToolUse",
                str(_MESSAGES / "pretooluse-write.md"),
                str(_MESSAGES / "pretooluse-eval-guard.md"),
            ],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        envelope = json.loads(result.stdout.strip().splitlines()[-1])
        assert envelope["hookSpecificOutput"]["additionalContext"] == ""
    cached = (
        (tmp_path / "state" / "interpreter-path").read_text(encoding="utf-8").strip()
    )
    assert cached
