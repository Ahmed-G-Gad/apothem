# SPDX-License-Identifier: MIT

"""Behavioral pass+fail coverage for the production-ready-pr matcher.

The matcher's per-file ``check`` is a soft pass by design; the substantive
four-class shape check fires in ``_check_staged`` over the staged-diff path
list. These tests drive ``_classify`` directly (path -> class labels) and
drive ``_check_staged`` with a monkeypatched ``_staged_paths`` so the
pass case (code + tests + docs + changelog all present) and the fail case
(code-only change-set) are both deterministic and network-free.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

from tests._shared.git_env import hermetic_git_env

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "production_ready_pr_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "production_ready_pr_grep", _GREP_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["production_ready_pr_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def test_classify_recognizes_each_class() -> None:
    assert "code" in _MOD._classify("src/apothem/cli/main.py")
    assert "tests" in _MOD._classify("tests/unit/test_main.py")
    assert "docs" in _MOD._classify("README.md")
    assert "changelog" in _MOD._classify("CHANGELOG.md")


def test_name_with_a_line_break_inside_is_classified() -> None:
    # git can stage a name that holds a line break; ``.`` must cross it.
    assert "code" in _MOD._classify("src/apothem/a\nb.py")
    assert "tests" in _MOD._classify("tests/a\nb.py")
    assert "docs" in _MOD._classify("site/content/docs/a\nb.mdx")


@pytest.mark.parametrize(
    ("name", "label"),
    [
        ("a\nb/README.md", "docs"),
        ("a\nb/CONTRIBUTING.md", "docs"),
        ("a\nb/templates/c.md", "docs"),
        ("a\nb/test_x.py", "tests"),
        ("a\nb_test.go", "tests"),
        ("a\nb.test.ts", "tests"),
        ("lib/a\nb.py", "code"),
        ("rules/a\nb.md", "code"),
    ],
)
def test_each_pattern_crosses_a_line_break(name: str, label: str) -> None:
    # Each name matches one pattern of its class only, so that pattern's
    # ``re.DOTALL`` alone lets ``.`` cross the line break.
    assert label in _MOD._classify(name)


def test_name_with_a_final_line_break_is_not_the_changelog() -> None:
    # ``$`` with ``match`` also matches before a final line break, which
    # would credit a different file as the changelog.
    assert "changelog" not in _MOD._classify("CHANGELOG.md\n")
    assert "docs" not in _MOD._classify("README.md\n")
    assert "code" not in _MOD._classify("src/apothem/cli/main.py\n")


def test_site_content_docs_is_docs_class() -> None:
    # This repo's documentation lives under site/content/docs/; those paths must
    # count as the docs-class the four-class shape requires.
    assert "docs" in _MOD._classify("site/content/docs/reference/cli.mdx")
    # Harness product templates count as documentation surfaces too.
    assert "docs" in _MOD._classify(
        "src/apothem/harnesses/cursor/templates/apothem-rules.mdc"
    )
    # A nested README/CONTRIBUTING is a docs surface at any depth.
    assert "docs" in _MOD._classify("src/apothem/lib/README.md")


def test_root_docs_tree_is_not_docs_class() -> None:
    # no_toplevel_docs_grep hard-forbids a root docs/ tree, so the old ^docs?/
    # expectation is retired: a root docs/ path must NOT be credited as
    # docs-class (the two validators no longer contradict each other).
    assert "docs" not in _MOD._classify("docs/cli.md")


def test_code_plus_site_docs_change_set_passes(monkeypatch) -> None:
    # A code change accompanied by a site/content/docs page (plus tests and
    # CHANGELOG) satisfies the four-class shape — previously impossible because
    # the ^docs?/ pattern could never match this repo's docs tree.
    monkeypatch.setattr(
        _MOD,
        "_staged_paths",
        lambda: [
            "src/apothem/cli/main.py",
            "tests/unit/test_main.py",
            "site/content/docs/reference/cli.mdx",
            "CHANGELOG.md",
        ],
    )
    result = _MOD._check_staged()
    assert result.passed, result.to_json()
    assert result.findings == []


def test_per_file_check_is_soft_pass() -> None:
    result = _MOD.check("anything at all", Path("src/apothem/cli/main.py"))
    assert result.passed
    assert result.findings == []


def test_complete_change_set_passes(monkeypatch) -> None:
    monkeypatch.setattr(
        _MOD,
        "_staged_paths",
        lambda: [
            "src/apothem/cli/main.py",
            "tests/unit/test_main.py",
            "site/content/docs/reference/cli.mdx",
            "CHANGELOG.md",
        ],
    )
    result = _MOD._check_staged()
    assert result.passed, result.to_json()
    assert result.findings == []


def test_code_only_change_set_fails(monkeypatch) -> None:
    monkeypatch.setattr(_MOD, "_staged_paths", lambda: ["src/apothem/cli/main.py"])
    result = _MOD._check_staged()
    assert not result.passed
    issues = {f.issue for f in result.findings}
    assert "missing tests-class file" in issues
    assert "missing docs-class file" in issues
    assert "missing CHANGELOG entry" in issues


def test_staged_paths_are_read_from_the_top_with_diff_relative_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # diff.relative=true made git print names from the current folder, and
    # leave out names outside it: ``src/apothem/api.py`` came back as
    # ``apothem/api.py``, a name no class pattern matches, and the
    # top-level CHANGELOG.md was missing.
    if shutil.which("git") is None:
        pytest.skip("git not available")
    repo = tmp_path / "repo"
    (repo / "src" / "apothem").mkdir(parents=True)

    def _git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=str(repo),
            env=hermetic_git_env(),
            check=True,
            capture_output=True,
        )

    _git("-c", "init.defaultBranch=main", "init", "-q")
    (repo / "src" / "apothem" / "api.py").write_bytes(b"X = 1\n")
    (repo / "CHANGELOG.md").write_bytes(b"# Changelog\n")
    _git("add", ".")
    global_config = tmp_path / "gitconfig"
    global_config.write_bytes(b"[diff]\n\trelative = true\n")
    env = hermetic_git_env()
    for name in list(os.environ):
        if name not in env:
            monkeypatch.delenv(name)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.chdir(repo / "src")

    assert sorted(_MOD._staged_paths()) == ["CHANGELOG.md", "src/apothem/api.py"]


def test_staged_paths_argv_turns_diff_relative_off_before_the_subcommand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # diff.relative is off among git's own options. The subcommand comes
    # right after them, so run_git adds its diff options, and git older
    # than 2.28 is never given --no-relative.
    from apothem.conformity import _bounded_run
    from apothem.conformity._git import DIFF_OPTIONS, PROTECTIVE_OPTIONS

    if shutil.which("git") is None:
        pytest.skip("git not available")
    seen: list[list[str]] = []

    def _record(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(_bounded_run, "run_bounded", _record)
    assert _MOD._staged_paths() == []
    (argv,) = seen
    start = 1 + len(PROTECTIVE_OPTIONS)
    assert tuple(argv[1:start]) == PROTECTIVE_OPTIONS
    assert argv[start : start + 1 + len(DIFF_OPTIONS)] == ["diff", *DIFF_OPTIONS]
    pair = argv.index("diff.relative=false")
    assert argv[pair - 1] == "-c"
    assert pair < start
    assert "--no-relative" not in argv


def test_non_code_only_change_set_passes(monkeypatch) -> None:
    # A docs-only change-set has no code-class file, so the four-class
    # requirement does not trigger.
    monkeypatch.setattr(_MOD, "_staged_paths", lambda: ["docs/notes.md"])
    result = _MOD._check_staged()
    assert result.passed
    assert result.findings == []
