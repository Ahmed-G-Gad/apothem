# SPDX-License-Identifier: MIT

"""The golden regeneration script refuses machine-dependent runs and keeps the corpus.

``scripts/dev/regen-behavior-goldens.py`` checks the interpreter, the rendering
libraries and the installed source directories before it captures, then
captures into a staging directory and swaps each subtree in by rename,
restoring the committed subtrees when a capture or a swap fails. These tests
drive those pieces directly: the flag and version checks with fixed inputs, the
source-tree check against a hermetic git repository, the staged capture with
stand-in oracles, and ``main`` end to end for a refused run.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
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
    ("pyproject", "versions", "named"),
    [
        (_PYPROJECT, {"click": "8.4.2", "rich": "15.0.0"}, []),
        (_PYPROJECT, {"click": "8.4.2", "rich": "15.3.1"}, []),
        (_PYPROJECT, {"click": "8.4.1", "rich": "15.0.0"}, ["click 8.4.1"]),
        (_PYPROJECT, {"click": "8.4.2", "rich": "14.3.4"}, ["rich 14.3.4"]),
        (_PYPROJECT, {"click": "8.4.2", "rich": "9.0.0"}, ["rich 9.0.0"]),
        ('"rich>=15.9.0"', {"rich": "15.10.0"}, []),
        (_PYPROJECT, {"click": "8.4.2"}, ["rich is not installed"]),
    ],
)
def test_rendering_library_versions_outside_pyproject_are_named(
    pyproject: str, versions: dict[str, str], named: list[str]
) -> None:
    """Click must match its pin exactly; Rich must meet its floor numerically."""

    def version_of(name: str) -> str:
        if name not in versions:
            raise importlib.metadata.PackageNotFoundError(name)
        return versions[name]

    problems = regen.library_problems(pyproject, version_of)

    assert len(problems) == len(named)
    for fragment, problem in zip(named, problems, strict=True):
        assert fragment in problem


def test_pyproject_declares_both_rendering_libraries() -> None:
    """The checked-in pyproject.toml still carries a pin the check can read."""
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    problems = regen.library_problems(pyproject, lambda _name: "0.0.0")

    assert [problem.split()[0] for problem in problems] == ["click", "rich"]


def test_installed_source_roots_are_the_manifest_directories() -> None:
    """The check scans the cohort directories an install copies, not all of src."""
    roots = {root.as_posix() for root in regen.installed_source_roots(_REPO_ROOT)}

    assert {"src/apothem/hooks", "src/apothem/skills", "src/apothem/rules"} <= roots
    assert not roots & {"src/apothem/cli", "src/apothem/lib", "src/apothem/_vendor"}


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


_ROOTS = [
    PurePosixPath(f"src/apothem/{name}") for name in ("hooks", "skills", "templates")
]


@_needs_git
@pytest.mark.usefixtures("hermetic_git")
def test_ignored_files_and_ignored_only_directories_are_named(tmp_path: Path) -> None:
    """Strays in the roots are named; caches, new files and other dirs are not."""
    repo = tmp_path / "repo"
    source = repo / "src" / "apothem"
    _write(repo / ".gitignore", b".DS_Store\n*~\n__pycache__/\n")
    _write(source / "hooks" / "dispatch.py")
    _write(source / "skills" / "kept" / "SKILL.md")
    _write(source / "skills" / "removed" / "SKILL.md")
    _write(source / "cli" / "main.py")
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
    (source / "skills" / "removed" / "SKILL.md").unlink()
    (source / "templates" / "empty").mkdir(parents=True)
    _write(source / "skills" / "new-skill" / "SKILL.md")
    _write(source / "cli" / ".DS_Store")

    assert regen.stray_source_paths(repo, _ROOTS) == [
        "src/apothem/hooks/.DS_Store",
        "src/apothem/hooks/dispatch.py~",
        "src/apothem/skills/removed/",
        "src/apothem/skills/retired/",
        "src/apothem/templates/",
    ]


def test_source_check_is_skipped_without_a_git_directory(tmp_path: Path) -> None:
    """A tree with no .git reports that the check could not run."""
    assert regen.stray_source_paths(tmp_path, _ROOTS) is None


@_needs_git
@pytest.mark.usefixtures("hermetic_git")
def test_git_failure_on_the_work_tree_is_raised_with_its_message(
    tmp_path: Path,
) -> None:
    """git present but failing stops the run instead of skipping the check."""
    (tmp_path / ".git").write_text(
        f"gitdir: {tmp_path / 'missing'}\n", encoding="utf-8"
    )

    # git words a gitfile that points nowhere differently across builds ("not a
    # git repository: ..." on Linux git 2.43, "gitfile does not point to a valid
    # repository: ..." on some macOS and Windows runners), so pin only that the
    # message is git's own fatal line and not the "git ls-files exited N"
    # fallback.
    with pytest.raises(regen.SourceCheckError, match=r"^fatal: "):
        regen.stray_source_paths(tmp_path, _ROOTS)


def test_refused_run_exits_1_and_writes_nothing(tmp_path: Path) -> None:
    """main names the -OO problem, exits 1 and never creates the destination."""
    dest = tmp_path / "corpus"

    result = subprocess.run(
        [sys.executable, "-OO", str(_SCRIPT), "--dest", str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1, result.stderr
    assert "-OO" in result.stderr
    assert not dest.exists()


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
    assert sorted(entry.name for entry in dest.iterdir()) == ["cli", "install_driver"]


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
    assert sorted(entry.name for entry in dest.iterdir()) == ["cli", "install_driver"]


def test_failed_swap_restores_the_committed_subtrees(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A rename that fails midway puts every committed subtree back."""
    dest = tmp_path / "behavior-diff"
    _write(dest / "install_driver" / "plan" / "x.json", b"committed\n")
    _write(dest / "cli" / "doctor.json", b"committed\n")
    before = _tree(dest)
    real_replace = Path.replace

    def replace(self: Path, target: Path) -> Path:
        if self.name == "cli" and self.parent.name.startswith(".r"):
            raise OSError("simulated rename failure")
        return real_replace(self, target)

    def capture_full(out_root: Path) -> None:
        _write(out_root / "plan" / "x.json", b"fresh\n")

    def capture(out_root: Path) -> int:
        _write(out_root / "doctor.json", b"fresh\n")
        return 1

    monkeypatch.setattr(Path, "replace", replace)
    with pytest.raises(OSError, match="simulated rename failure"):
        regen.capture_staged(
            dest, _oracle(capture_full=capture_full), _oracle(capture=capture)
        )

    assert _tree(dest) == before
    assert sorted(entry.name for entry in dest.iterdir()) == ["cli", "install_driver"]
