# SPDX-License-Identifier: MIT

"""Context-emission contract for the hook helper (``hooks.emit_hook_context``).

The helper composes the advisory context a hook injects and must stay robust to
the deployed invocation shape: typographic punctuation is normalized to ASCII
(UTF-8 content the map does not name is preserved, not stripped), a degraded or
missing stdin payload falls back rather than raising, a missing header import
degrades to the stdlib-only path, the bash/git trigger boundary fires only on
the intended commands, and every failure converts to a valid-JSON envelope with
breaking characters escaped. These tests pin each branch so a malformed payload
or an absent dependency never produces broken output or an unhandled exception.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import emit_hook_context as ehc  # noqa: E402


class TestNormalizeAscii:
    """Folding typographic characters to ASCII.

    Covers the mapped characters — typographic quotes, the em dash, the arrow —
    against the two preservation cases: an unmapped non-ASCII character survives
    rather than being dropped, and empty input stays empty.
    """

    def test_empty_input_returns_empty(self) -> None:
        """Empty input stays empty."""
        assert ehc.normalize_ascii("") == ""

    def test_typographic_quotes_mapped(self) -> None:
        """Curly double and single quotes fold to their ASCII equivalents."""
        source = "\u201cquoted\u201d and \u2018single\u2019"

        result = ehc.normalize_ascii(source)

        assert result == "\"quoted\" and 'single'"

    def test_em_dash_mapped_to_hyphen(self) -> None:
        """An em dash folds to a hyphen."""
        assert ehc.normalize_ascii("a\u2014b") == "a-b"

    def test_arrow_mapped_to_ascii(self) -> None:
        """An arrow folds to its ASCII digraph."""
        assert ehc.normalize_ascii("x \u2192 y") == "x -> y"

    def test_unmapped_non_ascii_preserved(self) -> None:
        # UTF-8 content the map does not name is PRESERVED (no wholesale strip):
        # the envelope's additionalContext/systemMessage is UTF-8 JSON, so
        # non-Latin MEMORY / plan content must survive rather than be deleted.
        """An unmapped non-ASCII character survives.

        The envelope is UTF-8 JSON, so nothing is stripped wholesale.
        """
        assert ehc.normalize_ascii("hello\u2603world") == "hello\u2603world"

    def test_non_latin_script_preserved(self) -> None:
        """Only mapped typographic characters transliterate.

        Non-Latin script passes through intact.
        """
        source = "\u4e2d\u6587 overview \u2014 done"
        # Only the em dash (a mapped typographic char) transliterates; the
        # non-Latin script survives intact.
        assert ehc.normalize_ascii(source) == "\u4e2d\u6587 overview - done"


class TestBuildMetadataPrefix:
    """Building the metadata prefix from the hook payload.

    Covers the two empty inputs (none payload, empty dict), the fully-populated
    prefix, the partial case emitting only present fields, and non-string values
    being ignored rather than coerced.
    """

    def test_none_payload_returns_empty(self) -> None:
        """A none payload yields no prefix."""
        assert ehc.build_metadata_prefix(None) == ""

    def test_empty_dict_returns_empty(self) -> None:
        """An empty payload yields no prefix."""
        assert ehc.build_metadata_prefix({}) == ""

    def test_all_fields_present(self) -> None:
        """A full payload renders every field in the declared order."""
        payload = {"source": "user", "tool_name": "Write", "matcher": "Write"}

        result = ehc.build_metadata_prefix(payload)

        assert result == "[source=user | tool=Write | matcher=Write]"

    def test_partial_fields_only(self) -> None:
        """Only the fields actually present are rendered."""
        payload = {"tool_name": "Edit"}

        result = ehc.build_metadata_prefix(payload)

        assert result == "[tool=Edit]"

    def test_non_string_values_ignored(self) -> None:
        """A non-string value is dropped, never coerced into the prefix."""
        payload = {"source": 123, "tool_name": "Write"}

        result = ehc.build_metadata_prefix(payload)

        assert result == "[tool=Write]"


class TestComposeContext:
    """Joining the metadata prefix to the context body.

    Covers all four combinations: both present and newline-joined, body only,
    prefix only, and both empty yielding empty.
    """

    def test_prefix_and_body_joined_by_newline(self) -> None:
        """Prefix and body are joined by a single newline."""
        result = ehc.compose_context("body", {"tool_name": "Write"})

        assert result == "[tool=Write]\nbody"

    def test_body_only_when_no_payload(self) -> None:
        """With no payload the body returns alone, no leading newline."""
        assert ehc.compose_context("body", None) == "body"

    def test_prefix_only_when_body_empty(self) -> None:
        """With an empty body the prefix returns alone, no trailing newline."""
        result = ehc.compose_context("", {"tool_name": "Write"})

        assert result == "[tool=Write]"

    def test_both_empty_returns_empty(self) -> None:
        """Both empty yields empty."""
        assert ehc.compose_context("", None) == ""


class TestResolveContextPath:
    """Resolving the context file path.

    Covers a relative path resolving against the root and an absolute path being
    returned verbatim.
    """

    def test_relative_resolved_against_root(self, tmp_path: Path) -> None:
        """A relative path resolves beneath the supplied root."""
        resolved = ehc.resolve_context_path("sub/file.md", tmp_path)

        assert resolved == tmp_path / "sub" / "file.md"

    def test_absolute_returned_verbatim(self, tmp_path: Path) -> None:
        """An absolute path is returned unchanged, ignoring the root."""
        absolute = tmp_path / "absolute.md"

        resolved = ehc.resolve_context_path(str(absolute), tmp_path / "other")

        assert resolved == absolute


class TestReadHookStdin:
    """Reading and parsing the hook payload from stdin.

    Covers the valid JSON parse against every none-returning case — a TTY,
    malformed JSON, empty input, and well-formed JSON that is not an object — so
    the hook degrades rather than raising.
    """

    def test_tty_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeStdin:
            """Stdin double reporting an interactive terminal."""

            @staticmethod
            def isatty() -> bool:
                return True

        monkeypatch.setattr(sys, "stdin", FakeStdin())

        assert ehc.read_hook_stdin() is None

    def test_valid_json_parsed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stream = io.StringIO('{"tool_name":"Write"}')
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

        result = ehc.read_hook_stdin()

        assert result == {"tool_name": "Write"}

    def test_malformed_json_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stream = io.StringIO("not json")
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

        assert ehc.read_hook_stdin() is None

    def test_empty_input_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stream = io.StringIO("   ")
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

        assert ehc.read_hook_stdin() is None

    def test_non_dict_json_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stream = io.StringIO('["list", "not", "dict"]')
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

        assert ehc.read_hook_stdin() is None


class TestHookMode:
    """End-to-end hook-mode emission.

    Covers the valid JSON envelope and the empty-additional cases: a missing
    context file, and each guard that passes — the write-plan guard, the
    project-local plan write, and the bash plan guard.
    """

    def test_emits_valid_json_envelope(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        context = tmp_path / "msg.md"
        context.write_text("Hello hook")

        ehc.run_hook_mode("PreToolUse", "msg.md", quiet=False, root=tmp_path)

        out = capsys.readouterr().out
        envelope = json.loads(out)
        assert envelope["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert "Hello hook" in envelope["hookSpecificOutput"]["additionalContext"]

    def test_missing_context_file_emits_empty_additional(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ehc.run_hook_mode("Stop", "nonexistent.md", quiet=False, root=tmp_path)

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["hookSpecificOutput"]["additionalContext"] == ""

    def test_passing_write_plan_guard_emits_empty_additional(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stream = io.StringIO(
            json.dumps(
                {
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": "src/apothem/example.py",
                        "content": "print('ok')\n",
                    },
                }
            )
        )
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

        ehc.run_hook_mode(
            "PreToolUse",
            "messages/pretooluse-write-plan-guard.md",
            quiet=False,
            root=_HOOKS_DIR,
        )

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["hookSpecificOutput"]["additionalContext"] == ""

    def test_project_local_plan_write_guard_emits_empty_additional(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stream = io.StringIO(
            json.dumps(
                {
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": ".plans/example/PHASE.md",
                        "content": "---\nphase-id: 99\n---\n# Phase\n",
                    },
                }
            )
        )
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

        ehc.run_hook_mode(
            "PreToolUse",
            "messages/pretooluse-write-plan-guard.md",
            quiet=False,
            root=_HOOKS_DIR,
        )

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["hookSpecificOutput"]["additionalContext"] == ""

    def test_passing_bash_plan_guard_emits_empty_additional(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stream = io.StringIO(
            json.dumps(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "python -m pytest -q"},
                }
            )
        )
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

        ehc.run_hook_mode(
            "PreToolUse",
            "messages/pretooluse-bash-plan-guard.md",
            quiet=False,
            root=_HOOKS_DIR,
        )

        envelope = json.loads(capsys.readouterr().out)
        assert envelope["hookSpecificOutput"]["additionalContext"] == ""

    def test_missing_header_guard_still_emits_context(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stream = io.StringIO(
            json.dumps(
                {
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": str(_HOOKS_DIR.parent / "example.py"),
                        "content": "print('missing header')\n",
                    },
                }
            )
        )
        stream.isatty = lambda: False  # type: ignore[method-assign]
        monkeypatch.setattr(sys, "stdin", stream)

        ehc.run_hook_mode(
            "PreToolUse",
            "messages/pretooluse-write-header-guard.md",
            quiet=False,
            root=_HOOKS_DIR,
        )

        envelope = json.loads(capsys.readouterr().out)
        assert (
            "Authorship-Header" in envelope["hookSpecificOutput"]["additionalContext"]
        )

    def test_quiet_suppresses_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ehc.run_hook_mode("Stop", "nonexistent.md", quiet=True, root=tmp_path)

        assert capsys.readouterr().out == ""


class TestDiagnosticMode:
    """Diagnostic-mode output.

    Covers that the header and the counts are both emitted.
    """

    def test_emits_header_and_counts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "rules").mkdir()
        (tmp_path / "rules" / "a.md").write_text("")
        (tmp_path / "commands").mkdir()
        (tmp_path / "CLAUDE.md").write_text("")

        ehc.run_diagnostic_mode(tmp_path)

        out = capsys.readouterr().out
        assert "Apothem Ecosystem Diagnostics" in out
        assert "Rules: 1" in out
        assert "+ CLAUDE.md" in out


class TestEnvelopeShapes:
    """build_envelope picks the schema-correct shape per event class."""

    def test_hook_specific_output_event_uses_hookspecificoutput(self) -> None:
        envelope = ehc.build_envelope("PreToolUse", "ctx")
        assert envelope == {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "ctx",
            }
        }

    def test_precompact_event_uses_system_message(self) -> None:
        envelope = ehc.build_envelope("PreCompact", "ctx")
        assert envelope == {"systemMessage": "ctx"}

    def test_postcompact_event_uses_system_message(self) -> None:
        envelope = ehc.build_envelope("PostCompact", "ctx")
        assert envelope == {"systemMessage": "ctx"}


class TestFailureEnvelope:
    """The last-resort failure writer always emits one valid JSON object."""

    def test_failure_envelope_hookspecificoutput_event(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ehc.emit_failure_envelope("PreToolUse", "boom")
        envelope = json.loads(capsys.readouterr().out)
        assert (
            envelope["hookSpecificOutput"]["additionalContext"]
            == "Hook execution failure: boom"
        )
        assert envelope["hookSpecificOutput"]["hookEventName"] == "PreToolUse"

    def test_failure_envelope_systemmessage_event(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ehc.emit_failure_envelope("PreCompact", "boom")
        envelope = json.loads(capsys.readouterr().out)
        assert envelope["systemMessage"] == "Hook execution failure: boom"

    def test_failure_envelope_empty_event_name_falls_back(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ehc.emit_failure_envelope("", "boom")
        envelope = json.loads(capsys.readouterr().out)
        # An unknown event name is not in the hookSpecificOutput set, so the
        # systemMessage shape is used.
        assert envelope["systemMessage"] == "Hook execution failure: boom"

    def test_failure_envelope_is_valid_json_with_breaking_chars(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A failure message carrying quotes, braces, backslashes, and newlines
        # must still serialize to one parseable JSON object (fail-open).
        nasty = 'broke on "{\\n}" \t with control \x00 chars'
        ehc.emit_failure_envelope("PreToolUse", nasty)
        out = capsys.readouterr().out
        # Exactly one JSON object on one line.
        assert out.count("\n") == 1
        envelope = json.loads(out)
        assert nasty in envelope["hookSpecificOutput"]["additionalContext"]

    def test_main_emits_failure_envelope_when_run_hook_mode_raises(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def _boom(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("hook mode exploded")

        monkeypatch.setattr(ehc, "run_hook_mode", _boom)
        # main must catch and emit a valid JSON failure envelope, never raise.
        ehc.main(["--hook-event-name", "PreToolUse", "--context-file", "x.md"])
        envelope = json.loads(capsys.readouterr().out)
        assert (
            "Hook execution failure: hook mode exploded"
            in envelope["hookSpecificOutput"]["additionalContext"]
        )


class TestIsProjectLocalPlanPath:
    """The recognizer accepts BOTH plans layouts inside the project root.

    ``.apothem/plans/`` is the canonical tree; a legacy ``.plans/`` tree is
    still recognized as project-local (its upgrade path is
    ``apothem migrate-workspace``). Regression: the predicate previously
    matched only the legacy layout, so canonical-plans writes were treated
    as plan-shaped content outside a plans tree.
    """

    @pytest.fixture(autouse=True)
    def _git_project_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_canonical_apothem_plans_tree_recognized(self, tmp_path: Path) -> None:
        target = tmp_path / ".apothem" / "plans" / "2026-07-02--suite" / "plan.md"
        assert ehc._is_project_local_plan_path(str(target)) is True

    def test_legacy_plans_tree_still_recognized(self, tmp_path: Path) -> None:
        target = tmp_path / ".plans" / "suite" / "plan.md"
        assert ehc._is_project_local_plan_path(str(target)) is True

    def test_non_plan_project_path_rejected(self, tmp_path: Path) -> None:
        target = tmp_path / "src" / "module.py"
        assert ehc._is_project_local_plan_path(str(target)) is False

    def test_apothem_dir_without_plans_child_rejected(self, tmp_path: Path) -> None:
        target = tmp_path / ".apothem" / "memory" / "note.md"
        assert ehc._is_project_local_plan_path(str(target)) is False

    def test_explicit_root_arg_anchors_relative_path(self, tmp_path: Path) -> None:
        # With an explicit resolved root, a relative plans path resolves against
        # THAT root (not Path.cwd()), so the cwd-differs-from-root case that used
        # to misclassify a legitimate write is fixed.
        root = tmp_path / "elsewhere"
        (root / ".apothem" / "plans").mkdir(parents=True)
        rel = ".apothem/plans/suite/PHASE.md"
        assert ehc._is_project_local_plan_path(rel, root) is True


class TestBashGitTriggerBoundary:
    """The bash git-reminder fires only on a boundary-matched git-mutation."""

    def test_bare_git_mutation_matches(self) -> None:
        assert ehc._command_has_git_trigger("git commit -m 'x'") is True
        assert ehc._command_has_git_trigger("cd repo && git branch feat") is True

    def test_quoted_substring_does_not_match(self) -> None:
        # A trigger buried inside a quoted string is not a git invocation.
        assert ehc._command_has_git_trigger('echo "git commit"') is False

    def test_non_boundary_token_does_not_match(self) -> None:
        # ``digit branch`` / ``mygit commit`` must not trip the ``git`` matcher.
        assert ehc._command_has_git_trigger("digit branch of a tree") is False
        assert ehc._command_has_git_trigger("mygit commit") is False

    def test_non_git_command_does_not_match(self) -> None:
        assert ehc._command_has_git_trigger("python -m pytest -q") is False


class TestSuppressBashHookDegradedStdin:
    """Degraded stdin suppresses the git reminder instead of firing blind."""

    def test_no_payload_suppresses(self) -> None:
        assert (
            ehc.should_suppress_bash_hook("PreToolUse", "pretooluse-bash.md", None)
            is True
        )

    def test_non_git_command_suppresses(self) -> None:
        payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        assert (
            ehc.should_suppress_bash_hook("PreToolUse", "pretooluse-bash.md", payload)
            is True
        )

    def test_git_mutation_does_not_suppress(self) -> None:
        payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m hi"}}
        assert (
            ehc.should_suppress_bash_hook("PreToolUse", "pretooluse-bash.md", payload)
            is False
        )

    def test_non_bash_message_has_no_opinion(self) -> None:
        # A non-bash message returns False (no opinion) so other predicates run.
        assert (
            ehc.should_suppress_bash_hook("PreToolUse", "pretooluse-write.md", None)
            is False
        )


class TestMissingHeaderImportDegrade:
    """A missing conformity package degrades the header guard to no-advisory."""

    def test_import_error_degrades_to_no_advisory(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import builtins

        real_import = builtins.__import__

        def _fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "apothem.conformity" or name.startswith("apothem.conformity."):
                raise ImportError("no apothem package (plugin-alone)")
            return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(builtins, "__import__", _fake_import)
        # With the checker unavailable the guard must NOT fire (return False),
        # rather than fail closed and fire on every Write/Edit.
        assert ehc._missing_header("some.py", "print('no header')\n") is False
