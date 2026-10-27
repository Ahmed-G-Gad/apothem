# SPDX-License-Identifier: MIT

"""Nested git checkouts and generated trees stay out of the root-level walks.

A root-level conformity walk must not report on files that belong to another
checkout below the root: a Claude Code worktree under ``.claude/worktrees/``, a
git submodule, or a nested clone. Each carries a ``.git`` entry (a file for a
worktree or submodule, a directory for a clone). These tests cover the shared
walk in ``_grep_base`` directly (what it prunes, which root it accepts, the order
and the links it follows), then plant the same offending file at the root and
inside each kind of nested checkout for every validator that walks the tree, and
assert only the root-level copy is reported.

For the validators whose scope is anchored at the root (the docs, rules and
README surfaces), the nested checkout sits inside an in-scope directory, so the
planted file is in scope by path and only the nested-checkout rule excludes it.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from apothem.conformity import (
    agents_md_coverage_grep,
    agnosticism_grep,
    dynamism_grep,
    freshness_token_grep,
    no_global_plans_grep,
    plain_language_grep,
    reference_token_grep,
)
from apothem.conformity._grep_base import (
    PRUNED_SEGMENTS,
    has_git_entry,
    iter_tree_files,
)

_FIXTURES = Path(__file__).resolve().parent


def _write(path: Path, text: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_worktree(directory: Path) -> Path:
    """Mark ``directory`` as a linked worktree or submodule: ``.git`` is a file."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".git").write_text("gitdir: ../.git/worktrees/wt\n", encoding="utf-8")
    return directory


def make_clone(directory: Path) -> Path:
    """Mark ``directory`` as a nested clone: ``.git`` is a directory."""
    (directory / ".git").mkdir(parents=True, exist_ok=True)
    (directory / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    return directory


def _rel(root: Path, raw: str) -> str:
    """Return a finding's path relative to ``root`` in POSIX form."""
    path = Path(raw)
    if path.is_absolute():
        path = path.relative_to(root)
    return path.as_posix()


# ---------------------------------------------------------------------------
# The tree walk
# ---------------------------------------------------------------------------


def test_has_git_entry_accepts_file_and_directory(tmp_path: Path) -> None:
    assert has_git_entry(make_worktree(tmp_path / "wt")) is True
    assert has_git_entry(make_clone(tmp_path / "clone")) is True
    assert has_git_entry(tmp_path / "plain") is False
    (tmp_path / "plain").mkdir()
    assert has_git_entry(tmp_path / "plain") is False


def test_iter_tree_files_prunes_nested_checkouts_and_generated_trees(
    tmp_path: Path,
) -> None:
    kept = [
        _write(tmp_path / "README.md"),
        _write(tmp_path / "docs" / "a.md"),
        _write(tmp_path / "docs" / "b.mdx"),
    ]
    _write(tmp_path / "docs" / "c.txt")
    make_worktree(tmp_path / ".claude" / "worktrees" / "wt")
    _write(tmp_path / ".claude" / "worktrees" / "wt" / "AGENTS.md")
    make_clone(tmp_path / "third_party" / "clone")
    _write(tmp_path / "third_party" / "clone" / "deep" / "x.md")
    for segment in sorted(PRUNED_SEGMENTS - {".git"}):
        _write(tmp_path / "site" / segment / "pkg" / "x.md")
    _write(tmp_path / ".git" / "notes.md")

    found = list(iter_tree_files(tmp_path, (".md", ".mdx")))

    # A directory's own files come first, then its subdirectories, in name order.
    assert found == kept
    assert all(path.is_absolute() for path in found)


def test_iter_tree_files_prunes_build_output_directories(tmp_path: Path) -> None:
    """Built-site and build-output trees are listed by no validator."""
    kept = _write(tmp_path / "site" / "content" / "docs" / "a.md")
    for name in ("dist", ".next", ".audit"):
        assert name in PRUNED_SEGMENTS
        _write(tmp_path / name / "x.md")
        _write(tmp_path / "site" / name / "pkg" / "x.md")

    assert list(iter_tree_files(tmp_path, (".md",))) == [kept]


def test_iter_tree_files_honours_names_and_extra_prune(tmp_path: Path) -> None:
    readme = _write(tmp_path / "pkg" / "README.md")
    _write(tmp_path / "pkg" / "NOTREADME.md")
    _write(tmp_path / "scratch" / "README.md")
    _write(tmp_path / "pkg" / "scratch" / "README.md")

    assert list(
        iter_tree_files(tmp_path, names=("README.md",), extra_prune=("scratch",))
    ) == [readme]
    everything = {p.relative_to(tmp_path).as_posix() for p in iter_tree_files(tmp_path)}
    assert everything == {
        "pkg/README.md",
        "pkg/NOTREADME.md",
        "scratch/README.md",
        "pkg/scratch/README.md",
    }


def test_iter_tree_files_matches_rglob_on_a_plain_tree(tmp_path: Path) -> None:
    """Without nested checkouts or pruned names the walk finds what ``rglob`` finds."""
    for rel in ("a.md", "b/c.md", "b/d/e.mdx", "b/d/f.py", "g/h.md"):
        _write(tmp_path / rel)
    (tmp_path / "dir.md").mkdir()

    expected = {p for p in tmp_path.rglob("*.md") if p.is_file()}
    expected |= {p for p in tmp_path.rglob("*.mdx") if p.is_file()}

    assert set(iter_tree_files(tmp_path, (".md", ".mdx"))) == expected


@pytest.mark.parametrize(
    "make_root", [make_worktree, make_clone], ids=["worktree", "clone"]
)
def test_iter_tree_files_reads_the_checkout_it_is_pointed_at(
    make_root: Callable[[Path], Path], tmp_path: Path
) -> None:
    """The root carries its own ``.git`` (a file in a worktree); it is not nested."""
    root = make_root(tmp_path / "checkout")
    top = _write(root / "README.md")
    page = _write(root / "docs" / "a.md")
    make_worktree(root / "nested")
    _write(root / "nested" / "b.md")

    assert list(iter_tree_files(root, (".md",))) == [top, page]


def test_iter_tree_files_visits_siblings_in_name_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The order comes from the walk, not from how the filesystem lists a directory."""
    real_walk = os.walk

    def reversed_walk(top: Path) -> Iterator[tuple[str, list[str], list[str]]]:
        for dirpath, dirnames, filenames in real_walk(top):
            dirnames.reverse()
            filenames.reverse()
            yield dirpath, dirnames, filenames

    monkeypatch.setattr(os, "walk", reversed_walk)
    for rel in ("m.md", "k.md", "c/2.md", "c/1.md", "a/2.md", "a/1.md", "b/1.md"):
        _write(tmp_path / rel)

    found = [p.relative_to(tmp_path).as_posix() for p in iter_tree_files(tmp_path)]

    assert found == ["k.md", "m.md", "a/1.md", "a/2.md", "b/1.md", "c/1.md", "c/2.md"]


def test_iter_tree_files_does_not_enter_symlinked_directories(tmp_path: Path) -> None:
    real = _write(tmp_path / "real" / "x.md")
    try:
        (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
        (tmp_path / "real" / "up").symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"this host cannot create a directory symlink: {exc}")

    assert list(iter_tree_files(tmp_path, (".md",))) == [real]


# ---------------------------------------------------------------------------
# The validators that walk the tree
# ---------------------------------------------------------------------------


def _plant_nested(root: Path, parent: Path, relative_file: str, text: str) -> list[str]:
    """Plant ``relative_file`` inside a worktree and a clone under ``parent``.

    Returns the root-relative POSIX paths of the two planted copies.
    """
    planted: list[str] = []
    for name, make in (("wt", make_worktree), ("clone", make_clone)):
        nested = make(parent / name)
        planted.append(
            _write(nested / relative_file, text).relative_to(root).as_posix()
        )
    return planted


def test_agnosticism_skips_nested_checkouts_and_generated_trees(
    tmp_path: Path,
) -> None:
    offending = "Use Claude Code to open this file.\n"
    _write(tmp_path / "pkg" / "AGENTS.md", offending)
    _write(tmp_path / "src" / "apothem" / "rules" / "r.md", offending)
    _plant_nested(tmp_path, tmp_path / ".claude" / "worktrees", "AGENTS.md", offending)
    _plant_nested(tmp_path, tmp_path / "third_party", "AGENTS.md", offending)
    # A nested checkout inside an in-scope shipped-surface directory.
    _plant_nested(tmp_path, tmp_path / "src" / "apothem" / "rules", "r.md", offending)
    for generated in ("node_modules", "dist", ".audit", "src/apothem/_vendor"):
        _write(tmp_path / generated / "pkg" / "AGENTS.md", offending)

    result = agnosticism_grep.check(tmp_path)

    assert {f.path for f in result.findings} == {
        "pkg/AGENTS.md",
        "src/apothem/rules/r.md",
    }
    assert result.scanned_count == 2


def test_agents_md_coverage_enumerator_skips_nested_checkouts(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "README.md")
    _write(tmp_path / "src" / "apothem" / "harnesses" / "demo" / "__init__.py")
    pkg = tmp_path / "pkg"
    _plant_nested(tmp_path, pkg, "README.md", "x\n")
    _plant_nested(tmp_path, tmp_path / ".claude" / "worktrees", "README.md", "x\n")
    _plant_nested(
        tmp_path, tmp_path / "src" / "apothem" / "harnesses", "worker.py", "x\n"
    )

    assert agents_md_coverage_grep.meaningful_folders(tmp_path) == [
        "pkg",
        "src/apothem/harnesses/demo",
    ]


def test_freshness_token_skips_nested_checkouts(tmp_path: Path) -> None:
    leaky = (_FIXTURES / "freshness-token-grep" / "fail.md").read_text(encoding="utf-8")
    docs = tmp_path / "site" / "content" / "docs"
    _write(docs / "page.md", leaky)
    _plant_nested(tmp_path, docs, "page.md", leaky)

    result = freshness_token_grep.check(tmp_path)

    assert {f.surface for f in result.findings} == {"site/content/docs/page.md"}
    assert result.files_inspected == 1


def test_dynamism_skips_nested_checkouts(tmp_path: Path) -> None:
    docs = tmp_path / "site" / "content" / "docs"
    _write(docs / "page.mdx", "The pinned release is 1.2.3.\n")
    _plant_nested(tmp_path, docs, "page.mdx", "The pinned release is 1.2.3.\n")

    result = dynamism_grep.check(tmp_path)

    assert {_rel(tmp_path, f.path) for f in result.findings} == {
        "site/content/docs/page.mdx"
    }
    assert result.scanned_count == 1


def test_plain_language_skips_nested_checkouts(tmp_path: Path) -> None:
    leaky = (_FIXTURES / "plain-language-grep" / "fail.md").read_text(encoding="utf-8")
    docs = tmp_path / "site" / "content" / "docs"
    _write(docs / "page.md", leaky)
    _plant_nested(tmp_path, docs, "page.md", leaky)

    result = plain_language_grep.check(tmp_path)

    assert {_rel(tmp_path, f.path) for f in result.findings} == {
        "site/content/docs/page.md"
    }
    assert result.scanned_count == 1


def test_reference_token_skips_nested_checkouts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    denylist = tmp_path / "_denylist" / "reference-token-denylist.txt"
    entry = reference_token_grep.digest_entry("skivorn")
    _write(denylist, f"# SPDX-License-Identifier: MIT\n{entry}\n")
    monkeypatch.setattr(reference_token_grep, "_DENYLIST_PATH", denylist)
    root = tmp_path / "repo"
    rules = root / "src" / "apothem" / "rules"
    _write(rules / "leaky.md", "This page names skivorn.\n")
    _plant_nested(root, rules, "leaky.md", "This page names skivorn.\n")

    result = reference_token_grep.check(root)

    assert {f.surface for f in result.findings} == {"src/apothem/rules/leaky.md"}
    assert result.files_inspected == 1


def test_no_global_plans_sweep_skips_nested_checkouts(tmp_path: Path) -> None:
    (tmp_path / "workspace" / ".plans").mkdir(parents=True)
    make_worktree(tmp_path / ".claude" / "worktrees" / "wt")
    (tmp_path / ".claude" / "worktrees" / "wt" / ".apothem" / "plans").mkdir(
        parents=True
    )
    make_clone(tmp_path / "third_party" / "clone")
    (tmp_path / "third_party" / "clone" / "sub" / ".plans").mkdir(parents=True)

    findings = no_global_plans_grep._sweep_stray_plans_dirs(tmp_path, frozenset())

    assert [f.path for f in findings] == ["workspace/.plans/"]


@pytest.mark.parametrize(
    "make_root", [make_worktree, make_clone], ids=["worktree", "clone"]
)
def test_validators_run_from_a_checkout_root_still_read_it(
    make_root: Callable[[Path], Path], tmp_path: Path
) -> None:
    """A run from a worktree root must not collapse into ``inspected: 0``."""
    leaky = (_FIXTURES / "plain-language-grep" / "fail.md").read_text(encoding="utf-8")
    root = make_root(tmp_path / "checkout")
    _write(root / "site" / "content" / "docs" / "page.md", leaky)
    (root / "workspace" / ".plans").mkdir(parents=True)

    result = plain_language_grep.check(root)
    sweep = no_global_plans_grep._sweep_stray_plans_dirs(root, frozenset())

    assert result.scanned_count == 1
    assert {_rel(root, f.path) for f in result.findings} == {
        "site/content/docs/page.md"
    }
    assert [f.path for f in sweep] == ["workspace/.plans/"]


_WALKERS: list[Callable[[Path], object]] = [
    agents_md_coverage_grep.check,
    agnosticism_grep.check,
    dynamism_grep.check,
    freshness_token_grep.check,
    plain_language_grep.check,
    reference_token_grep.check,
]


@pytest.mark.parametrize("check", _WALKERS, ids=lambda fn: fn.__module__)
def test_walkers_never_descend_into_a_nested_checkout(
    check: Callable[[Path], object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The walk prunes a nested checkout without listing it, so it stays fast."""
    visited: list[Path] = []
    real_walk = os.walk

    def spy(top: Path) -> Iterator[tuple[str, list[str], list[str]]]:
        for entry in real_walk(top):
            visited.append(Path(entry[0]))
            yield entry

    monkeypatch.setattr(os, "walk", spy)
    _write(tmp_path / "README.md", "# Title\n")
    make_worktree(tmp_path / ".claude" / "worktrees" / "wt")
    _write(tmp_path / ".claude" / "worktrees" / "wt" / "deep" / "a.md")
    make_clone(tmp_path / "third_party" / "clone")
    _write(tmp_path / "third_party" / "clone" / "deep" / "a.md")
    _write(tmp_path / "site" / "node_modules" / "pkg" / "a.md")

    check(tmp_path)

    assert visited, "the validator did not walk the tree through os.walk"
    skipped = {"deep", "pkg", "node_modules"}
    assert [p for p in visited if skipped & set(p.relative_to(tmp_path).parts)] == []
