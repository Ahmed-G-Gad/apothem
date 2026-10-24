# SPDX-License-Identifier: MIT

"""The authorship-header guard decides with the standard library alone.

A Claude Code plugin install runs the dispatcher from the plugin tree, where the
``apothem`` package is not importable. The guard once imported the package for its
checker, so it stayed silent there; and where the package is importable, the import
cost several hundred milliseconds per Write. These tests pin the replacement:
``hooks/lib/header_check.py`` reads the byte-exact header fixture and the exemption
list from the ``schemas/`` directory beside ``hooks/``, decides by comment family,
and the guard that wraps it fires for a missing header, stays quiet for a present
one, an exempt path, an unknown extension and an Edit that leaves the header alone,
runs from a bare plugin-shaped tree without importing ``apothem``, and speaks only in
a git project that follows the convention.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENGINE = _REPO_ROOT / "src" / "apothem"
_HOOKS_DIR = _ENGINE / "hooks"
_MESSAGES = _HOOKS_DIR / "messages"
for _path in (_HOOKS_DIR, _HOOKS_DIR / "lib"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import emit_hook_context as ehc  # noqa: E402
import header_check  # noqa: E402

_TAG = "SPDX" + "-License-Identifier: MIT"
_FIXTURES = ("authorship-header.txt", "header-exceptions.txt")
_PLUGIN_ENGINE = _REPO_ROOT / "plugins" / "claude-code" / "lib" / "apothem"
_INJECTOR_PATH = _REPO_ROOT / "scripts" / "inject-header.py"

#: One path per comment family and the header line the family requires.
_FAMILY_LINES = {
    "tool.py": f"# {_TAG}",
    "tool.js": f"// {_TAG}",
    "tool.css": f"/* {_TAG} */",
    "tool.sql": f"-- {_TAG}",
    "tool.ini": f"; {_TAG}",
    "tool.md": f"<!-- {_TAG} -->",
    "tool.mdx": f"{{/* {_TAG} */}}",
    "Makefile": f"# {_TAG}",
}


def _third_party_project(tmp_path: Path) -> Path:
    """A git project that has not adopted the header convention."""
    root = tmp_path / "project"
    (root / ".git").mkdir(parents=True)
    return root.resolve()


def _project(tmp_path: Path) -> Path:
    """A git project that follows the convention: it carries the header fixture."""
    root = _third_party_project(tmp_path)
    schemas = root / "src" / "apothem" / "schemas"
    schemas.mkdir(parents=True)
    (schemas / "authorship-header.txt").write_text(f"# {_TAG}\n", encoding="utf-8")
    return root


def _write_fixtures(schemas_dir: Path, banner: str, exceptions: str) -> Path:
    schemas_dir.mkdir(parents=True, exist_ok=True)
    (schemas_dir / "authorship-header.txt").write_text(banner, encoding="utf-8")
    (schemas_dir / "header-exceptions.txt").write_text(exceptions, encoding="utf-8")
    return schemas_dir


def _advisory(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    project: Path,
    tool: str,
    tool_input: dict[str, object],
    cwd: Path | None = None,
) -> str:
    """Run the header guard for one tool call; return the context it injects."""
    payload = {"tool_name": tool, "cwd": str(cwd or project), "tool_input": tool_input}
    stream = io.StringIO(json.dumps(payload))
    stream.isatty = lambda: False  # type: ignore[method-assign]
    monkeypatch.setattr(sys, "stdin", stream)
    message = "pretooluse-edit" if tool == "Edit" else "pretooluse-write"
    ehc.run_hook_mode_multi(
        "PreToolUse", [str(_MESSAGES / f"{message}-header-guard.md")], False, _HOOKS_DIR
    )
    envelope = json.loads(capsys.readouterr().out)
    return str(envelope["hookSpecificOutput"]["additionalContext"])


class TestWriteLacksHeader:
    """A Write is judged on the content it proposes, by the file's comment family."""

    def test_missing_header_fires(self) -> None:
        assert header_check.write_lacks_header("src/new.py", "x = 1\n") is True

    def test_present_header_is_silent(self) -> None:
        content = f"# {_TAG}\n\nx = 1\n"
        assert header_check.write_lacks_header("src/new.py", content) is False

    @pytest.mark.parametrize("rel_path", sorted(_FAMILY_LINES))
    def test_each_comment_family_wants_its_own_line(self, rel_path: str) -> None:
        line = _FAMILY_LINES[rel_path]
        assert header_check.write_lacks_header(rel_path, f"{line}\n\nbody\n") is False
        assert header_check.write_lacks_header(rel_path, "body\n") is True

    def test_another_family_line_does_not_satisfy_the_file(self) -> None:
        wrong = f"// {_TAG}\n\nx = 1\n"
        assert header_check.write_lacks_header("src/new.py", wrong) is True

    def test_header_without_its_blank_line_is_not_canonical(self) -> None:
        assert header_check.write_lacks_header("a.py", f"# {_TAG}\nx = 1\n") is True

    def test_header_must_sit_at_the_top(self) -> None:
        assert header_check.write_lacks_header("a.py", f"x = 1\n# {_TAG}\n\n") is True

    def test_shebang_stays_first(self) -> None:
        shebang = "#!/usr/bin/env python3\n"
        assert (
            header_check.write_lacks_header(
                "bin/run.py", f"{shebang}# {_TAG}\n\nx = 1\n"
            )
            is False
        )
        assert (
            header_check.write_lacks_header("bin/run.py", f"{shebang}x = 1\n") is True
        )

    def test_markdown_header_follows_frontmatter(self) -> None:
        line = f"<!-- {_TAG} -->"
        tight = f"---\ntitle: T\n---\n{line}\n\nBody\n"
        spaced = f"---\ntitle: T\n---\n\n{line}\n\nBody\n"
        bare = "---\ntitle: T\n---\nBody\n"
        assert header_check.write_lacks_header("doc.md", tight) is False
        assert header_check.write_lacks_header("doc.md", spaced) is False
        assert header_check.write_lacks_header("doc.md", bare) is True

    def test_crlf_content_with_the_header_is_canonical(self) -> None:
        content = f"# {_TAG}\r\n\r\nx = 1\r\n"
        assert header_check.write_lacks_header("src/new.py", content) is False

    def test_empty_content_is_silent(self) -> None:
        assert header_check.write_lacks_header("src/new.py", "") is False

    @pytest.mark.parametrize(
        "rel_path",
        [
            "data.json",
            "LICENSE",
            "package-lock.json",
            ".apothem/plans/p.py",
            "web/node_modules/pkg/index.js",
            "src/apothem/_vendor/click/core.py",
            "tests/fixtures/case.yaml",
            "dist/app.min.js",
            "logo.png",
        ],
    )
    def test_exempt_path_is_silent(self, rel_path: str) -> None:
        assert header_check.write_lacks_header(rel_path, "no header\n") is False

    @pytest.mark.parametrize(
        "rel_path", ["notes.xyz", "README", "bin/run", "image.svg", "Makefile.in"]
    )
    def test_unknown_extension_is_silent(self, rel_path: str) -> None:
        assert header_check.write_lacks_header(rel_path, "no header\n") is False

    def test_suffix_is_matched_without_regard_to_case(self) -> None:
        assert header_check.write_lacks_header("SCRIPT.PY", "x = 1\n") is True

    def test_exemptions_come_from_the_tree_the_hook_runs_in(
        self, tmp_path: Path
    ) -> None:
        schemas = _write_fixtures(
            tmp_path / "schemas", f"# {_TAG}\n", "# only this\nvendored/**\n"
        )
        assert header_check.write_lacks_header("vendored/a.py", "x\n", schemas) is False
        assert header_check.write_lacks_header("src/a.py", "x\n", schemas) is True
        # data.json is no longer exempt, but .json has no comment family either.
        assert header_check.write_lacks_header("data.json", "{}\n", schemas) is False

    @pytest.mark.parametrize(
        ("banner", "exceptions"),
        [
            ("", "**/*.json\n"),
            ("not a spdx line\n", "**/*.json\n"),
            (f"// {_TAG}\n", "**/*.json\n"),
            (f"# {_TAG}\n# {_TAG}\n", "**/*.json\n"),
        ],
    )
    def test_an_unusable_banner_fixture_is_silent(
        self, tmp_path: Path, banner: str, exceptions: str
    ) -> None:
        schemas = _write_fixtures(tmp_path / "schemas", banner, exceptions)
        assert header_check.write_lacks_header("a.py", "x = 1\n", schemas) is False

    @pytest.mark.parametrize("missing", _FIXTURES)
    def test_a_missing_fixture_is_silent(self, tmp_path: Path, missing: str) -> None:
        schemas = _write_fixtures(tmp_path / "schemas", f"# {_TAG}\n", "**/*.json\n")
        (schemas / missing).unlink()
        assert header_check.write_lacks_header("a.py", "x = 1\n", schemas) is False

    def test_a_missing_schemas_directory_is_silent(self, tmp_path: Path) -> None:
        nowhere = tmp_path / "nowhere"
        assert header_check.write_lacks_header("a.py", "x = 1\n", nowhere) is False


class TestEditLacksHeader:
    """An Edit fires on create-via-edit and on header removal, never on a fragment."""

    @staticmethod
    def _edit(target: Path, old: str, new: str, *, replace_all: bool = False) -> bool:
        return header_check.edit_lacks_header(
            target.name, target, old, new, replace_all
        )

    def test_creating_a_file_without_the_header_fires(self, tmp_path: Path) -> None:
        assert self._edit(tmp_path / "new.py", "", "x = 1\n") is True

    def test_creating_a_file_with_the_header_is_silent(self, tmp_path: Path) -> None:
        content = f"# {_TAG}\n\nx = 1\n"
        assert self._edit(tmp_path / "new.py", "", content) is False

    def test_an_edit_that_has_text_to_find_in_a_missing_file_is_silent(
        self, tmp_path: Path
    ) -> None:
        # The Edit tool rejects it and creates nothing, so there is no file to lack
        # the header.
        assert self._edit(tmp_path / "ghost.py", "foo", "bar") is False

    def test_a_target_that_cannot_be_examined_is_silent(self, tmp_path: Path) -> None:
        class Unreadable(type(Path())):  # type: ignore[misc]
            def exists(self, *args: object, **kwargs: object) -> bool:
                raise PermissionError("denied")

        target = Unreadable(tmp_path / "new.py")
        assert self._edit(target, "", "x = 1\n") is False

    def test_a_fragment_edit_of_a_headed_file_is_silent(self, tmp_path: Path) -> None:
        target = tmp_path / "mod.py"
        target.write_text(f"# {_TAG}\n\nx = 1\ny = 2\n", encoding="utf-8")
        assert self._edit(target, "y = 2", "y = 3\nz = 4") is False

    def test_a_fragment_edit_of_a_file_that_never_had_one_is_silent(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "legacy.py"
        target.write_text("x = 1\ny = 2\n", encoding="utf-8")
        assert self._edit(target, "y = 2", "y = 3") is False

    def test_removing_the_header_fires(self, tmp_path: Path) -> None:
        target = tmp_path / "mod.py"
        target.write_text(f"# {_TAG}\n\nx = 1\n", encoding="utf-8")
        assert self._edit(target, f"# {_TAG}\n\n", "") is True

    def test_mangling_the_header_fires(self, tmp_path: Path) -> None:
        target = tmp_path / "mod.py"
        target.write_text(f"# {_TAG}\n\nx = 1\n", encoding="utf-8")
        assert self._edit(target, "MIT", "Apache-2.0") is True

    def test_an_edit_that_restates_the_header_is_silent(self, tmp_path: Path) -> None:
        target = tmp_path / "mod.py"
        target.write_text(f"# {_TAG}\n\nx = 1\n", encoding="utf-8")
        old = f"# {_TAG}\n\nx = 1"
        assert self._edit(target, old, f"# {_TAG}\n\nx = 2") is False

    def test_only_the_first_match_is_replaced_without_replace_all(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "mod.py"
        target.write_text(f"# {_TAG}\n\nMIT\nMIT\n", encoding="utf-8")
        assert self._edit(target, "MIT", "BSD") is True
        assert self._edit(target, "\nMIT", "\nBSD") is False
        assert self._edit(target, "\nMIT", "\nBSD", replace_all=True) is False

    def test_replace_all_that_reaches_the_header_fires(self, tmp_path: Path) -> None:
        target = tmp_path / "mod.py"
        target.write_text(f"# {_TAG}\n\nMIT\n", encoding="utf-8")
        assert self._edit(target, "MIT", "BSD", replace_all=True) is True

    def test_an_empty_old_string_on_an_existing_file_is_silent(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "mod.py"
        target.write_text(f"# {_TAG}\n\nx = 1\n", encoding="utf-8")
        assert self._edit(target, "", "prefix\n") is False

    def test_a_crlf_file_is_judged_on_its_text(self, tmp_path: Path) -> None:
        target = tmp_path / "mod.py"
        target.write_bytes(f"# {_TAG}\r\n\r\nx = 1\r\n".encode())
        assert self._edit(target, "x = 1", "x = 2") is False
        assert self._edit(target, f"# {_TAG}\n\n", "") is True

    def test_a_file_that_cannot_be_read_as_text_is_silent(self, tmp_path: Path) -> None:
        target = tmp_path / "mod.py"
        target.write_bytes(b"\xff\xfe\x00 not utf-8")
        assert self._edit(target, "x", "y") is False

    def test_a_file_over_the_size_cap_is_silent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "mod.py"
        target.write_text(f"# {_TAG}\n\nx = 1\n", encoding="utf-8")
        monkeypatch.setattr(header_check, "_MAX_EDIT_BYTES", 4)
        assert self._edit(target, f"# {_TAG}\n\n", "") is False

    def test_a_directory_target_is_silent(self, tmp_path: Path) -> None:
        folder = tmp_path / "pkg.py"
        folder.mkdir()
        assert self._edit(folder, "a", "b") is False

    def test_an_exempt_or_unknown_path_is_silent(self, tmp_path: Path) -> None:
        assert self._edit(tmp_path / "data.json", "", "{}") is False
        assert self._edit(tmp_path / "notes.xyz", "", "hi") is False


class TestGuardInsideTheProject:
    """The guard judges project files, by the path relative to the project root."""

    def test_a_headerless_write_names_the_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        target = root / "src" / "new.py"
        text = _advisory(
            monkeypatch,
            capsys,
            root,
            "Write",
            {"file_path": str(target), "content": "x = 1\n"},
        )
        assert str(target) in text
        assert "canonical `SPDX" + "-License-Identifier: MIT` header" in text
        assert "Full procedure:" in text

    def test_a_headed_write_is_silent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        tool_input = {
            "file_path": str(root / "new.py"),
            "content": f"# {_TAG}\n\nx = 1\n",
        }
        assert _advisory(monkeypatch, capsys, root, "Write", tool_input) == ""

    @pytest.mark.parametrize("rel", ["data.json", "LICENSE", ".apothem/plans/p.py"])
    def test_an_exempt_write_is_silent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        rel: str,
    ) -> None:
        root = _project(tmp_path)
        tool_input = {"file_path": str(root / rel), "content": "no header\n"}
        assert _advisory(monkeypatch, capsys, root, "Write", tool_input) == ""

    def test_an_unknown_extension_is_silent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        tool_input = {"file_path": str(root / "notes.xyz"), "content": "hello\n"}
        assert _advisory(monkeypatch, capsys, root, "Write", tool_input) == ""

    def test_a_write_outside_the_project_is_silent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        tool_input = {"file_path": str(tmp_path / "elsewhere.py"), "content": "x = 1\n"}
        assert _advisory(monkeypatch, capsys, root, "Write", tool_input) == ""

    def test_a_relative_path_resolves_against_the_working_directory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        (root / "pkg").mkdir()
        tool_input = {"file_path": "new.py", "content": "x = 1\n"}
        text = _advisory(
            monkeypatch, capsys, root, "Write", tool_input, cwd=root / "pkg"
        )
        assert "new.py" in text

    def test_a_write_without_a_path_is_silent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        assert _advisory(monkeypatch, capsys, root, "Write", {"content": "x\n"}) == ""

    def test_creating_a_file_through_edit_fires(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        tool_input = {
            "file_path": str(root / "new.py"),
            "old_string": "",
            "new_string": "x = 1\n",
        }
        text = _advisory(monkeypatch, capsys, root, "Edit", tool_input)
        assert "would lack the canonical" in text

    def test_a_fragment_edit_stays_quiet(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The case that protects users: an ordinary edit to the middle of a file
        # carries no header in its new_string, and must not be taken for a removal.
        root = _project(tmp_path)
        target = root / "mod.py"
        target.write_text(f"# {_TAG}\n\nx = 1\ny = 2\n", encoding="utf-8")
        tool_input = {
            "file_path": str(target),
            "old_string": "y = 2",
            "new_string": "y = 3",
        }
        assert _advisory(monkeypatch, capsys, root, "Edit", tool_input) == ""

    def test_an_edit_that_strips_the_header_fires(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = _project(tmp_path)
        target = root / "mod.py"
        target.write_text(f"# {_TAG}\n\nx = 1\n", encoding="utf-8")
        tool_input = {
            "file_path": str(target),
            "old_string": f"# {_TAG}\n\n",
            "new_string": "",
        }
        text = _advisory(monkeypatch, capsys, root, "Edit", tool_input)
        assert "would lack the canonical" in text

    def test_a_defect_in_the_checker_fails_closed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def explode(*_args: object) -> bool:
            raise RuntimeError("checker defect")

        monkeypatch.setattr(ehc, "write_lacks_header", explode)
        root = _project(tmp_path)
        tool_input = {"file_path": str(root / "new.py"), "content": "x = 1\n"}
        text = _advisory(monkeypatch, capsys, root, "Write", tool_input)
        assert "SPDX-License-Identifier" in text


class TestProjectAdoptsHeader:
    """The convention is Apothem's own; only a git project that carries it is judged."""

    def test_a_git_project_with_the_fixture_adopts_it(self, tmp_path: Path) -> None:
        assert header_check.project_adopts_header(_project(tmp_path)) is True

    def test_a_git_project_without_the_fixture_does_not(self, tmp_path: Path) -> None:
        assert (
            header_check.project_adopts_header(_third_party_project(tmp_path)) is False
        )

    def test_a_directory_without_git_does_not(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        shutil.rmtree(root / ".git")
        assert header_check.project_adopts_header(root) is False

    def test_a_worktree_git_file_counts_as_git(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        shutil.rmtree(root / ".git")
        (root / ".git").write_text("gitdir: ../elsewhere\n", encoding="utf-8")
        assert header_check.project_adopts_header(root) is True

    def test_a_fixture_that_is_a_directory_does_not_count(self, tmp_path: Path) -> None:
        root = _third_party_project(tmp_path)
        (root / "src" / "apothem" / "schemas" / "authorship-header.txt").mkdir(
            parents=True
        )
        assert header_check.project_adopts_header(root) is False

    def test_a_root_that_cannot_be_examined_does_not(self, tmp_path: Path) -> None:
        class Unreadable(type(Path())):  # type: ignore[misc]
            def exists(self, *args: object, **kwargs: object) -> bool:
                raise PermissionError("denied")

        assert header_check.project_adopts_header(Unreadable(tmp_path)) is False

    @pytest.mark.parametrize("tool", ["Write", "Edit"])
    @pytest.mark.parametrize(
        "rel", ["src/app.py", "src/app.ts", "README.md", "index.html", "Dockerfile"]
    )
    def test_a_project_that_has_not_adopted_it_is_not_nagged(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tool: str,
        rel: str,
    ) -> None:
        root = _third_party_project(tmp_path)
        tool_input: dict[str, object] = {"file_path": str(root / rel)}
        if tool == "Write":
            tool_input["content"] = "no header\n"
        else:
            tool_input.update(old_string="", new_string="no header\n")
        assert _advisory(monkeypatch, capsys, root, tool, tool_input) == ""

    def test_a_directory_without_git_is_not_nagged(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # No ``.git`` anywhere above: the project root falls back to the working
        # directory, and the fixture is there, yet it is not a project.
        root = _project(tmp_path)
        shutil.rmtree(root / ".git")
        tool_input = {"file_path": str(root / "new.py"), "content": "x = 1\n"}
        assert _advisory(monkeypatch, capsys, root, "Write", tool_input) == ""


class TestWithoutTheApothemPackage:
    """The guard runs from a bare plugin-shaped tree and never imports ``apothem``."""

    @staticmethod
    def _engine_tree(tmp_path: Path) -> Path:
        engine = tmp_path / "plugin" / "lib" / "apothem"
        shutil.copytree(
            _HOOKS_DIR,
            engine / "hooks",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        (engine / "schemas").mkdir()
        for name in _FIXTURES:
            shutil.copy2(_ENGINE / "schemas" / name, engine / "schemas" / name)
        return engine

    @staticmethod
    def _dispatch(
        engine: Path, project: Path, tool_input: dict[str, object], tool: str = "Write"
    ) -> tuple[str, list[str]]:
        """Run the dispatcher as the plugin does; return its output and imports."""
        guard = f"pretooluse-{tool.lower()}-header-guard.md"
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env.pop("CLAUDE_PROJECT_DIR", None)
        payload = {"tool_name": tool, "cwd": str(project), "tool_input": tool_input}
        done = subprocess.run(
            [
                sys.executable,
                "-X",
                "importtime",
                str(engine / "hooks" / "dispatch.py"),
                "--event-name",
                "PreToolUse",
                "--context-file",
                str(engine / "hooks" / "messages" / guard),
            ],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            cwd=project,
            timeout=60,
            check=False,
        )
        assert done.returncode == 0, done.stderr
        imported = [
            line.rsplit("|", 1)[-1].strip()
            for line in done.stderr.splitlines()
            if line.startswith("import time:")
        ]
        return done.stdout.strip(), imported

    def test_a_missing_header_fires_from_the_plugin_tree(self, tmp_path: Path) -> None:
        engine = self._engine_tree(tmp_path)
        project = _project(tmp_path)
        target = project / "new.py"

        out, imported = self._dispatch(
            engine, project, {"file_path": str(target), "content": "x = 1\n"}
        )

        text = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        assert "missing the canonical" in text
        assert "new.py" in text
        assert "header_check" in imported
        assert not [name for name in imported if name.split(".")[0] == "apothem"]

    def test_quiet_paths_stay_quiet_from_the_plugin_tree(self, tmp_path: Path) -> None:
        engine = self._engine_tree(tmp_path)
        project = _project(tmp_path)
        quiet = {
            "headed.py": f"# {_TAG}\n\nx = 1\n",
            "data.json": "{}\n",
            "notes.xyz": "hello\n",
            "LICENSE": "terms\n",
        }
        for name, content in quiet.items():
            out, imported = self._dispatch(
                engine, project, {"file_path": str(project / name), "content": content}
            )
            assert json.loads(out)["hookSpecificOutput"]["additionalContext"] == "", (
                name
            )
            assert not [n for n in imported if n.split(".")[0] == "apothem"]

    def test_a_project_that_has_not_adopted_it_is_quiet_from_the_plugin_tree(
        self, tmp_path: Path
    ) -> None:
        engine = self._engine_tree(tmp_path)
        third_party = _third_party_project(tmp_path / "git")
        plain = tmp_path / "plain"
        plain.mkdir()
        for project in (third_party, plain):
            for name in ("src/app.py", "README.md", "index.html"):
                tool_input = {"file_path": str(project / name), "content": "x\n"}
                out, imported = self._dispatch(engine, project, tool_input)
                context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
                assert context == "", (project.name, name)
                assert not [n for n in imported if n.split(".")[0] == "apothem"]

    def test_a_fragment_edit_stays_quiet_from_the_plugin_tree(
        self, tmp_path: Path
    ) -> None:
        engine = self._engine_tree(tmp_path)
        project = _project(tmp_path)
        target = project / "mod.py"
        target.write_text(f"# {_TAG}\n\nx = 1\n", encoding="utf-8")

        out, _ = self._dispatch(
            engine,
            project,
            {"file_path": str(target), "old_string": "x = 1", "new_string": "x = 2"},
            tool="Edit",
        )

        assert json.loads(out)["hookSpecificOutput"]["additionalContext"] == ""


class TestFixturesShipBesideTheHooks:
    """Every tree that ships the hooks ships the two fixtures the checker reads."""

    @pytest.mark.parametrize(
        "engine",
        [
            pytest.param(_ENGINE, id="source"),
            pytest.param(
                _PLUGIN_ENGINE,
                id="plugin",
                marks=pytest.mark.skipif(
                    not _PLUGIN_ENGINE.is_dir(), reason="no assembled plugin tree"
                ),
            ),
        ],
    )
    def test_schemas_sit_beside_hooks(self, engine: Path) -> None:
        assert (engine / "hooks" / "lib").is_dir()
        for name in _FIXTURES:
            assert (engine / "schemas" / name).is_file(), name

    def test_the_default_schemas_directory_is_that_sibling(self) -> None:
        assert header_check.SCHEMAS_DIR == _ENGINE / "schemas"


def _load_injector() -> ModuleType:
    """Load scripts/inject-header.py in-process (hyphenated filename)."""
    name = "apothem_inject_header_hook_parity"
    spec = importlib.util.spec_from_file_location(name, _INJECTOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def injector() -> ModuleType:
    return _load_injector()


class TestParityWithTheInjector:
    """The guard applies the rules ``scripts/inject-header.py`` applies."""

    def test_variant_tables_are_equal(self, injector: ModuleType) -> None:
        assert header_check.SUFFIX_VARIANT == injector.SUFFIX_VARIANT
        assert header_check.BASENAME_VARIANT == injector.BASENAME_VARIANT

    def test_every_family_renders_the_injectors_line(
        self, injector: ModuleType
    ) -> None:
        banner = injector.load_canonical_banner(_ENGINE / "schemas" / _FIXTURES[0])
        for variant in sorted(set(injector.SUFFIX_VARIANT.values())):
            assert header_check._render_variant(
                banner.hash_form_line, variant
            ) == tuple(injector.render_variant(banner, variant)), variant

    def test_exemption_globs_agree_over_the_shipped_list(
        self, injector: ModuleType
    ) -> None:
        globs = injector.load_exception_globs(_ENGINE / "schemas" / _FIXTURES[1])
        paths = [
            "LICENSE",
            "VERSION",
            "a/b/data.json",
            "yarn.lock",
            "src/apothem/_vendor/x/y.py",
            "tests/fixtures/a/b.yaml",
            "tests/fixtures/a/b.py",
            ".apothem/plans/s/p.md",
            "docs/.keep",
            "app/dist/main.min.js",
            "pkg/generated/m.py",
            "icons/logo.svg",
            "src/main.py",
            "README.md",
            "schemas/authorship-header.txt",
        ]
        for path in paths:
            expected = injector.matches_exception(path, globs) is not None
            actual = any(header_check._glob_matches(path, g) for g in globs)
            assert actual == expected, path

    def test_insertion_site_agrees(self, injector: ModuleType) -> None:
        samples = [
            "",
            "x\n",
            "#!/bin/sh\nx\n",
            "---\na: 1\n---\n\nbody\n",
            "---\na: 1\n---\nbody\n",
            "#!/bin/sh\n---\na: 1\n---\nbody\n",
            "---\nnever closed\n",
        ]
        for text in samples:
            lines = text.split("\n")
            for variant in ("hash", "html", "mdx", "c-block"):
                assert header_check._insertion_index(
                    lines, variant
                ) == injector.determine_insertion_index(lines, variant), (text, variant)
