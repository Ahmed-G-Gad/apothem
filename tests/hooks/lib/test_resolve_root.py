# SPDX-License-Identifier: MIT

"""Tests for `hooks.lib.resolve_root`.

Covers all four resolution levels, both marker modes, and negative cases
(no markers, partial markers, missing paths).
"""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_LIB = Path(__file__).resolve().parents[3] / "src" / "apothem" / "hooks" / "lib"
if str(_HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(_HOOKS_LIB))

from resolve_root import (  # noqa: E402
    Mode,
    ResolutionStrategy,
    default_content_root,
    resolve_project_root,
)


def _make_hooks_root(base: Path) -> Path:
    """Create a valid HOOKS-mode root at `base` and return it."""
    base.mkdir(parents=True, exist_ok=True)
    (base / "hooks").mkdir(exist_ok=True)
    (base / "rules").mkdir(exist_ok=True)
    return base


def _make_marker_root(base: Path) -> Path:
    """Create a valid MARKER-mode root at `base` and return it."""
    base.mkdir(parents=True, exist_ok=True)
    (base / "CLAUDE.md").write_text("# marker")
    return base


class TestResolutionStrategy:
    """The two marker strategies a candidate directory is matched against.

    Covers hooks mode requiring both directories, marker mode requiring the
    instruction file, and the guard that a non-directory candidate never matches
    whatever its name.
    """

    def test_hooks_mode_requires_both_directories(self, tmp_path: Path) -> None:
        strategy = ResolutionStrategy.for_mode(Mode.HOOKS)

        (tmp_path / "hooks").mkdir()

        assert strategy.matches(tmp_path) is False

        (tmp_path / "rules").mkdir()

        assert strategy.matches(tmp_path) is True

    def test_marker_mode_requires_claude_md_file(self, tmp_path: Path) -> None:
        strategy = ResolutionStrategy.for_mode(Mode.MARKER)

        assert strategy.matches(tmp_path) is False

        (tmp_path / "CLAUDE.md").write_text("# marker")

        assert strategy.matches(tmp_path) is True

    def test_non_directory_candidate_never_matches(self, tmp_path: Path) -> None:
        strategy = ResolutionStrategy.for_mode(Mode.HOOKS)
        file_path = tmp_path / "not-a-dir"
        file_path.write_text("x")

        assert strategy.matches(file_path) is False


class TestEnvironmentVariable:
    """Root resolution from the environment.

    Covers the precedence between the primary and fallback variables — the
    primary wins when valid, the fallback applies when the primary is absent or
    invalid — and an invalid value falling through to the next strategy rather
    than resolving to a bad root.
    """

    def test_claude_project_dir_wins_when_valid(self, tmp_path: Path) -> None:
        root = _make_hooks_root(tmp_path / "root-a")
        _make_hooks_root(tmp_path / "root-b")

        resolved = resolve_project_root(
            Mode.HOOKS,
            environ={"CLAUDE_PROJECT_DIR": str(root)},
            cwd=tmp_path / "root-b",
        )

        assert resolved == root.resolve()

    def test_invalid_env_var_falls_through(self, tmp_path: Path) -> None:
        cwd_root = _make_hooks_root(tmp_path / "cwd-root")
        bogus = tmp_path / "does-not-exist"

        resolved = resolve_project_root(
            Mode.HOOKS,
            environ={"CLAUDE_PROJECT_DIR": str(bogus)},
            cwd=cwd_root,
            home=tmp_path,
        )

        assert resolved == cwd_root.resolve()

    def test_llm_project_dir_fallback_when_primary_absent(self, tmp_path: Path) -> None:
        root = _make_hooks_root(tmp_path / "llm-root")

        resolved = resolve_project_root(
            Mode.HOOKS,
            environ={"LLM_PROJECT_DIR": str(root)},
            cwd=tmp_path,
            home=tmp_path,
        )

        assert resolved == root.resolve()

    def test_claude_project_dir_wins_over_llm_project_dir(self, tmp_path: Path) -> None:
        claude_root = _make_hooks_root(tmp_path / "claude-root")
        llm_root = _make_hooks_root(tmp_path / "llm-root")

        resolved = resolve_project_root(
            Mode.HOOKS,
            environ={
                "CLAUDE_PROJECT_DIR": str(claude_root),
                "LLM_PROJECT_DIR": str(llm_root),
            },
            cwd=tmp_path,
            home=tmp_path,
        )

        assert resolved == claude_root.resolve()

    def test_llm_project_dir_used_when_primary_invalid(self, tmp_path: Path) -> None:
        llm_root = _make_hooks_root(tmp_path / "llm-root")
        bogus = tmp_path / "does-not-exist"

        resolved = resolve_project_root(
            Mode.HOOKS,
            environ={
                "CLAUDE_PROJECT_DIR": str(bogus),
                "LLM_PROJECT_DIR": str(llm_root),
            },
            cwd=tmp_path,
            home=tmp_path,
        )

        assert resolved == llm_root.resolve()


class TestScriptRelative:
    """Root resolution relative to the running script.

    Covers a script inside the hooks folder resolving its parent, and a script
    outside that folder being ignored so an unrelated location cannot be
    mistaken for a root.
    """

    def test_script_in_hooks_folder_resolves_parent(self, tmp_path: Path) -> None:
        root = _make_hooks_root(tmp_path / "ecosystem")
        script = root / "hooks" / "dispatch.py"
        script.write_text("# stub")

        resolved = resolve_project_root(
            Mode.HOOKS,
            script_path=script,
            environ={},
            cwd=tmp_path,
            home=tmp_path,
        )

        assert resolved == root.resolve()

    def test_script_outside_hooks_folder_ignored(self, tmp_path: Path) -> None:
        root = _make_hooks_root(tmp_path / "ecosystem")
        script = tmp_path / "elsewhere" / "unrelated.py"
        script.parent.mkdir()
        script.write_text("# stub")

        resolved = resolve_project_root(
            Mode.HOOKS,
            script_path=script,
            environ={},
            cwd=root,
            home=tmp_path,
        )

        assert resolved == root.resolve()


class TestCwdWalk:
    """Root resolution by walking up from the working directory.

    Covers the working directory matching directly, a deep subdirectory walking
    up to find it, and partial markers being skipped so a half-formed directory
    never wins.
    """

    def test_cwd_itself_matches(self, tmp_path: Path) -> None:
        root = _make_hooks_root(tmp_path / "ecosystem")

        resolved = resolve_project_root(Mode.HOOKS, environ={}, cwd=root, home=tmp_path)

        assert resolved == root.resolve()

    def test_deep_subdirectory_walks_up(self, tmp_path: Path) -> None:
        root = _make_hooks_root(tmp_path / "ecosystem")
        deep = root / "a" / "b" / "c"
        deep.mkdir(parents=True)

        resolved = resolve_project_root(Mode.HOOKS, environ={}, cwd=deep, home=tmp_path)

        assert resolved == root.resolve()

    def test_partial_markers_skipped_during_walk(self, tmp_path: Path) -> None:
        fake = tmp_path / "fake"
        (fake / "hooks").mkdir(parents=True)
        real = _make_hooks_root(tmp_path)
        deep = fake / "deep"
        deep.mkdir()

        resolved = resolve_project_root(Mode.HOOKS, environ={}, cwd=deep, home=tmp_path)

        assert resolved == real.resolve()


class TestHomeFallback:
    """The last-resort home directory fallback.

    Covers the home location being used when no ancestor matches, and the
    explicit none when every strategy fails — the caller is told, not handed a
    guess.
    """

    def test_home_claude_used_when_no_ancestor_matches(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        home.mkdir()
        _make_hooks_root(home / ".claude")
        unrelated = tmp_path / "unrelated"
        unrelated.mkdir()

        resolved = resolve_project_root(
            Mode.HOOKS, environ={}, cwd=unrelated, home=home
        )

        assert resolved == (home / ".claude").resolve()

    def test_returns_none_when_all_strategies_fail(self, tmp_path: Path) -> None:
        empty_home = tmp_path / "home"
        empty_home.mkdir()
        unrelated = tmp_path / "unrelated"
        unrelated.mkdir()

        resolved = resolve_project_root(
            Mode.HOOKS, environ={}, cwd=unrelated, home=empty_home
        )

        assert resolved is None


class TestMarkerMode:
    """Marker-mode resolution specifically.

    Covers resolution via the instruction file, and the deliberate exclusion of
    hooks-only directories that marker mode must not claim.
    """

    def test_marker_mode_resolves_via_claude_md(self, tmp_path: Path) -> None:
        root = _make_marker_root(tmp_path / "project")

        resolved = resolve_project_root(
            Mode.MARKER, environ={}, cwd=root, home=tmp_path
        )

        assert resolved == root.resolve()

    def test_marker_mode_ignores_hooks_only_directories(self, tmp_path: Path) -> None:
        hooks_only = _make_hooks_root(tmp_path / "hooks-only")
        real = _make_marker_root(tmp_path / "real")
        deep = hooks_only / "deep"
        deep.mkdir()

        resolved = resolve_project_root(
            Mode.MARKER, environ={}, cwd=deep, home=tmp_path
        )

        assert resolved == real.resolve() or resolved is None


class TestDefaultContentRoot:
    """Deriving the content root from the resolved project root.

    Covers the src layout resolving into the package directory, the flat layout
    returning the root unchanged, and a src directory without a package marker
    falling back to the root rather than descending into a non-package.
    """

    def test_src_layout_resolves_to_package_dir(self, tmp_path: Path) -> None:
        package = tmp_path / "src" / "apothem"
        (package / "hooks").mkdir(parents=True)

        assert default_content_root(tmp_path) == package

    def test_flat_layout_returns_root_unchanged(self, tmp_path: Path) -> None:
        (tmp_path / "hooks").mkdir()

        assert default_content_root(tmp_path) == tmp_path

    def test_src_dir_without_package_marker_returns_root(self, tmp_path: Path) -> None:
        (tmp_path / "src" / "apothem").mkdir(parents=True)

        assert default_content_root(tmp_path) == tmp_path
