# SPDX-License-Identifier: MIT

"""The golden regeneration script refuses machine-dependent runs and never half-writes.

``scripts/dev/regen-behavior-goldens.py`` checks the interpreter, the rendering
libraries and the source tree before it captures, then captures into a staging
directory and swaps it in only when both oracles succeed. These tests drive
those pieces directly: the flag and version checks with fixed inputs, the
source-tree check against a hermetic git repository, and the staged capture
with stand-in oracles.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

from tests._shared.git_env import hermetic_git_env

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "dev" / "regen-behavior-goldens.py"

_spec = importlib.util.spec_from_file_location("regen_behavior_goldens", _SCRIPT)
assert _spec is not None
assert _spec.loader is not None
regen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(regen)

_PYPROJECT = '"click==8.4.2",\n    "rich>=15.0.0",\n'


@pytest.mark.parametrize(
    ("optimize", "verbose", "flags"),
    [(0, 0, []), (1, 0, []), (2, 0, ["-OO"]), (0, 1, ["-v"]), (2, 2, ["-OO", "-v"])],
)
def test_interpreter_flags_that_change_captures_are_named(
    optimize: int, verbose: int, flags: list[str]
) -> None:
    """-OO and -v are refused; -O, which changes no capture, is allowed."""
    problems = regen.interpreter_problems(optimize=optimize, verbose=verbose)

    assert len(problems) == len(flags)
    for flag, problem in zip(flags, problems, strict=True):
        assert flag in problem


@pytest.mark.parametrize(
    ("versions", "named"),
    [
        ({"click": "8.4.2", "rich": "15.0.0"}, []),
        ({"click": "8.4.2", "rich": "15.3.1"}, []),
        ({"click": "8.4.1", "rich": "15.0.0"}, ["click 8.4.1"]),
        ({"click": "8.4.2", "rich": "14.3.4"}, ["rich 14.3.4"]),
        ({"click": "8.4.2"}, ["rich is not installed"]),
    ],
)
def test_rendering_library_versions_outside_pyproject_are_named(
    versions: dict[str, str], named: list[str]
) -> None:
    """Click must match its pin exactly; Rich must meet its floor."""

    def version_of(name: str) -> str:
        if name not in versions:
            raise importlib.metadata.PackageNotFoundError(name)
        return versions[name]

    problems = regen.library_problems(_PYPROJECT, version_of)

    assert len(problems) == len(named)
    for fragment, problem in zip(named, problems, strict=True):
        assert fragment in problem


def test_pyproject_declares_both_rendering_libraries() -> None:
    """The checked-in pyproject.toml still carries a pin the check can read."""
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    problems = regen.library_problems(pyproject, lambda _name: "0.0.0")

    assert [problem.split()[0] for problem in problems] == ["click", "rich"]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        env=hermetic_git_env(),
        check=True,
        capture_output=True,
    )


_needs_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git is not on PATH"
)


@pytest.fixture
def hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the script's git calls without the host's git configuration."""
    hermetic = hermetic_git_env()
    for name in set(os.environ) - set(hermetic):
        monkeypatch.delenv(name)
    for name, value in hermetic.items():
        monkeypatch.setenv(name, value)


def _write(path: Path, data: bytes = b"x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


@_needs_git
@pytest.mark.usefixtures("hermetic_git")
def test_ignored_files_and_ignored_only_directories_are_named(tmp_path: Path) -> None:
    """Stray files and dirs are named; caches and new unignored files are not."""
    repo = tmp_path / "repo"
    source = repo / "src" / "apothem"
    _write(repo / ".gitignore", b".DS_Store\n*~\n__pycache__/\n")
    _write(source / "hooks" / "dispatch.py")
    _write(source / "skills" / "kept" / "SKILL.md")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(
        repo,
        "-c",
        "user.name=T",
        "-c",
        "user.email=t@example.invalid",
        "commit",
        "-qm",
        "init",
    )

    _write(source / "hooks" / ".DS_Store")
    _write(source / "hooks" / "dispatch.py~")
    _write(source / "hooks" / "__pycache__" / "dispatch.cpython-313.pyc")
    _write(source / "skills" / "retired" / "__pycache__" / "old.cpython-313.pyc")
    (source / "templates" / "empty").mkdir(parents=True)
    _write(source / "skills" / "new-skill" / "SKILL.md")

    assert regen.stray_source_paths(repo) == [
        "src/apothem/hooks/.DS_Store",
        "src/apothem/hooks/dispatch.py~",
        "src/apothem/skills/retired/",
        "src/apothem/templates/",
    ]


@_needs_git
@pytest.mark.usefixtures("hermetic_git")
def test_source_check_is_skipped_outside_a_git_work_tree(tmp_path: Path) -> None:
    """Without a work tree the check reports that it could not run."""
    assert regen.stray_source_paths(tmp_path) is None


def _oracle(**functions: object) -> ModuleType:
    module = ModuleType("stand_in_oracle")
    for name, function in functions.items():
        setattr(module, name, function)
    return module


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_failed_capture_leaves_the_destination_unchanged(tmp_path: Path) -> None:
    """A capture that raises keeps the committed corpus and leaves no staging dir."""
    dest = tmp_path / "behavior-diff"
    _write(dest / "install_driver" / "plan" / "x.json", b"committed\n")
    _write(dest / "cli" / "doctor.json", b"committed\n")
    before = _tree(dest)

    def capture_full(out_root: Path) -> None:
        _write(out_root / "plan" / "x.json", b"fresh\n")

    def capture(out_root: Path) -> int:
        raise RuntimeError("capture failed")

    with pytest.raises(RuntimeError, match="capture failed"):
        regen.capture_staged(
            dest, _oracle(capture_full=capture_full), _oracle(capture=capture)
        )

    assert _tree(dest) == before
    assert [entry.name for entry in tmp_path.iterdir()] == ["behavior-diff"]


def test_successful_capture_replaces_both_subtrees(tmp_path: Path) -> None:
    """A complete capture replaces each subtree, dropping files it no longer writes."""
    dest = tmp_path / "behavior-diff"
    _write(dest / "install_driver" / "plan" / "stale.json", b"old\n")
    _write(dest / "cli" / "doctor.json", b"old\n")

    def capture_full(out_root: Path) -> None:
        _write(out_root / "plan" / "x.json", b"fresh\n")

    def capture(out_root: Path) -> int:
        _write(out_root / "doctor.json", b"fresh\n")
        return 1

    count = regen.capture_staged(
        dest, _oracle(capture_full=capture_full), _oracle(capture=capture)
    )

    assert count == 1
    assert _tree(dest) == {
        "cli/doctor.json": b"fresh\n",
        "install_driver/plan/x.json": b"fresh\n",
    }
    assert [entry.name for entry in tmp_path.iterdir()] == ["behavior-diff"]
