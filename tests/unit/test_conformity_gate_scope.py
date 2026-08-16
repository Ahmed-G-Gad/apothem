# SPDX-License-Identifier: MIT

"""Tests for the conformity-gate scope-aware short-circuit.

The gate's ``--hook`` mode runs matchers only when the write target
lives under a configured scope (defaults include user-scope hook-capable
harness roots such as ``~/.claude/`` and ``~/.codex/``; configurable via
the ``APOTHEM_CONFORMITY_SCOPE`` env var). Out-of-scope writes short-circuit
to a silent pass-through; in-scope writes invoke the full matcher chain as
today.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.conformity import gate


@pytest.fixture(autouse=True)
def _clear_scope_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no ambient scope env var pollutes the per-test resolution."""
    monkeypatch.delenv(gate.SCOPE_ENV_VAR, raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)


def test_resolve_scope_defaults_to_harness_root() -> None:
    """When the env var is unset, the legacy scope resolves to ~/.claude/."""
    scope = gate._resolve_scope()
    assert scope == (Path.home() / ".claude").resolve()


def test_resolve_scopes_defaults_to_hook_capable_user_roots() -> None:
    """Default hook scopes include Claude Code and Codex user roots."""
    scopes = gate._resolve_scopes()
    assert (Path.home() / ".claude").resolve() in scopes
    assert (Path.home() / ".codex").resolve() in scopes


def test_resolve_scopes_honors_codex_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The Codex default scope follows CODEX_HOME when present."""
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))

    assert (tmp_path / "codex-home").resolve() in gate._resolve_scopes()


def test_resolve_scope_honours_env_var(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The env var overrides the default scope; the result is an absolute path."""
    monkeypatch.setenv(gate.SCOPE_ENV_VAR, str(tmp_path))
    scope = gate._resolve_scope()
    assert scope == tmp_path.resolve()
    assert gate._resolve_scopes() == (tmp_path.resolve(),)


def test_resolve_scope_expands_user_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ~-prefixed env-var value is expanded against the user home."""
    monkeypatch.setenv(gate.SCOPE_ENV_VAR, "~")
    scope = gate._resolve_scope()
    assert scope == Path.home().resolve()


def test_path_in_scope_returns_true_for_in_scope_target(tmp_path: Path) -> None:
    """A target under the scope dir is reported in-scope."""
    target = tmp_path / "subdir" / "file.txt"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    assert gate._path_in_scope(target, tmp_path.resolve())


def test_path_in_scope_returns_false_for_out_of_scope_target(tmp_path: Path) -> None:
    """A target outside the scope dir is reported out-of-scope."""
    other = tmp_path.parent / "other-workspace" / "file.txt"
    assert not gate._path_in_scope(other, tmp_path.resolve())


def test_path_in_scope_returns_true_for_none_target(tmp_path: Path) -> None:
    """A None target (CLI-mode invocation) is treated as in-scope."""
    assert gate._path_in_scope(None, tmp_path.resolve())


def test_path_in_scope_returns_true_on_resolve_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Path-resolution failures fall back to in-scope (fail-permissive)."""

    class _BrokenPath:
        """Path double whose resolution always raises.

        Models the filesystem conditions the real ``Path.resolve`` fails on — a
        broken symlink loop, a permission denial — without needing to create
        one on disk.
        """

        def expanduser(self) -> _BrokenPath:
            return self

        def resolve(self) -> _BrokenPath:
            raise OSError("simulated path-resolution failure")

    assert gate._path_in_scope(_BrokenPath(), tmp_path.resolve())  # type: ignore[arg-type]


def test_path_in_scope_handles_symlinked_target(tmp_path: Path) -> None:
    """A symlink under the scope resolves to its real path (still in-scope when real)."""
    real = tmp_path / "real.txt"
    real.write_text("x", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("symlinks unavailable on this platform")
    assert gate._path_in_scope(link, tmp_path.resolve())


def test_path_in_any_scope_accepts_second_scope(tmp_path: Path) -> None:
    """A target under any configured scope is reported in-scope."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    target = second / "file.txt"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")

    assert gate._path_in_any_scope(target, (first.resolve(), second.resolve()))
