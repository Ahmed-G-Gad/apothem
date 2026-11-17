# SPDX-License-Identifier: MIT

"""The shared tree walk yields only regular files inside the root it walks.

Why these tests exist. A project can arrive with its files from someone else,
in an archive or a shared folder, and the root-walking ``--all`` validators
read every file :func:`iter_tree_files` yields. So the walk must not lead out
of the project:

- a file link (a symbolic link) can point at a file anywhere on the disk;
- a folder link can do the same for a whole tree. ``os.walk`` does not follow
  a symbolic link to a folder, but it does enter a Windows junction, which is
  not a symbolic link to Python;
- a link that points inside the project would make its target read twice,
  once under the link's name;
- a named pipe, or a link to a device such as ``/dev/zero``, makes a read wait
  or never end.

A link is skipped wherever it sits, and a file or folder it points to inside
the root is walked under its own path. Windows junctions need no privilege, so
the folder-link tests run everywhere; a test that needs a symbolic link to a
file skips where the host cannot create one (Windows without the privilege).
"""

from __future__ import annotations

import itertools
import json
import os
from pathlib import Path

import pytest

from apothem.conformity import (
    _project_paths,
    dynamism_grep,
    no_global_plans_grep,
    no_toplevel_docs_grep,
    plans_discipline_language_grep,
)
from apothem.conformity._grep_base import (
    is_project_dir,
    is_project_file,
    iter_tree_files,
    list_real_entries,
    project_file_target,
)
from apothem.conformity._project_paths import start_skip_log, take_skipped_paths

_POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt", reason="named pipes and /dev/zero exist only on POSIX systems"
)

# Enough paths to show a walk that follows a folder link back into the root,
# without walking until the host's path-length limit stops it.
_LOOP_CAP = 200


def _write(path: Path, text: str = "x\n") -> Path:
    """Write *text* to *path*, making its folders first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _symlink_or_skip(link: Path, target: Path) -> None:
    """Make *link* a symbolic link to *target*, or skip where that is not allowed."""
    try:
        link.symlink_to(target)
    except OSError as exc:  # Windows without the symbolic-link privilege
        pytest.skip(f"cannot create a symbolic link here: {exc}")


def _link_folder(link: Path, target: Path) -> None:
    """Make *link* a folder link to *target*.

    Windows gets a junction, which needs no special privilege; other systems
    get a symbolic link.
    """
    if os.name == "nt":
        winapi = pytest.importorskip("_winapi")
        winapi.CreateJunction(str(target), str(link))
        return
    link.symlink_to(target, target_is_directory=True)


def _walk(root: Path, *suffixes: str) -> list[str]:
    """Return the walk's yields under *root* as POSIX paths relative to it."""
    return [p.relative_to(root).as_posix() for p in iter_tree_files(root, suffixes)]


def test_a_file_link_leading_out_of_the_root_is_not_yielded(tmp_path: Path) -> None:
    """A symbolic link to a file outside the root is skipped, not followed."""
    outside = _write(tmp_path / "outside" / "secret.md")
    root = tmp_path / "project"
    _write(root / "README.md")
    _write(root / "docs" / "page.md")
    _symlink_or_skip(root / "linked.md", outside)
    _symlink_or_skip(root / "docs" / "linked.md", outside)

    assert _walk(root, ".md") == ["README.md", "docs/page.md"]


@pytest.mark.parametrize(
    "link_rel",
    ["docs", "site/content/docs"],
    ids=["top-level-folder", "folder-deeper-down"],
)
def test_a_folder_link_on_the_way_to_a_file_is_not_entered(
    tmp_path: Path, link_rel: str
) -> None:
    """A folder link (a junction on Windows) is not walked into, at any depth."""
    outside = tmp_path / "outside"
    _write(outside / "secret.md")
    _write(outside / "nested" / "deeper.md")
    root = tmp_path / "project"
    _write(root / "README.md")
    link = root / link_rel
    link.parent.mkdir(parents=True, exist_ok=True)
    _link_folder(link, outside)

    assert _walk(root, ".md") == ["README.md"]


def test_a_file_link_inside_the_root_leaves_its_target_to_its_own_path(
    tmp_path: Path,
) -> None:
    """A link to a file inside the root is skipped; the file is yielded once."""
    root = tmp_path / "project"
    _write(root / "docs" / "real.md")
    _symlink_or_skip(root / "alias.md", Path("docs") / "real.md")

    assert _walk(root, ".md") == ["docs/real.md"]


def test_a_folder_link_inside_the_root_leaves_its_target_to_its_own_path(
    tmp_path: Path,
) -> None:
    """A link to a folder inside the root is skipped; the folder is walked once."""
    root = tmp_path / "project"
    _write(root / "real" / "a.md")
    _write(root / "real" / "sub" / "b.md")
    _link_folder(root / "alias", root / "real")

    assert _walk(root, ".md") == ["real/a.md", "real/sub/b.md"]


def test_a_folder_link_back_to_the_root_is_not_walked_again(tmp_path: Path) -> None:
    """A folder link to the root itself would make the walk repeat the tree.

    ``os.walk`` stops this for a symbolic link but not for a junction, so on
    Windows the walk used to go round until the path grew too long.
    """
    root = tmp_path / "project"
    _write(root / "a.md")
    _write(root / "sub" / "b.md")
    _link_folder(root / "sub" / "loop", root)

    found = [
        p.relative_to(root).as_posix()
        for p in itertools.islice(iter_tree_files(root, (".md",)), _LOOP_CAP)
    ]

    assert found == ["a.md", "sub/b.md"]


@_POSIX_ONLY
def test_named_pipes_and_device_links_are_not_yielded(tmp_path: Path) -> None:
    """A named pipe or a link to a device is never yielded, so never read."""
    root = tmp_path / "project"
    _write(root / "README.md")
    os.mkfifo(root / "pipe.md")
    (root / "zero.md").symlink_to("/dev/zero")

    assert _walk(root, ".md") == ["README.md"]


# ---------------------------------------------------------------------------
# The checks the validators use for fixed paths and folder listings
# ---------------------------------------------------------------------------


def test_the_project_checks_fail_closed_outside_the_root(tmp_path: Path) -> None:
    """A path outside the root, through ``..``, or missing is never a project file."""
    root = tmp_path / "project"
    inside = _write(root / "docs" / "page.md")
    beside = _write(tmp_path / "beside.md")

    assert is_project_file(root, inside)
    assert not is_project_file(root, beside)
    assert not is_project_file(root, root / "docs" / ".." / ".." / "beside.md")
    assert not is_project_file(root, root / "missing.md")
    assert not is_project_file(root, root / "docs")
    assert not is_project_file(root, root)
    assert is_project_dir(root, root)
    assert is_project_dir(root, root / "docs")
    assert not is_project_dir(root, inside)
    assert not is_project_dir(root, tmp_path)


def test_a_link_in_the_middle_of_a_path_fails_the_project_checks(
    tmp_path: Path,
) -> None:
    """A folder link between real folders stops the check at every level below it."""
    outside = tmp_path / "outside"
    _write(outside / "deeper" / "page.md")
    root = tmp_path / "project"
    real = _write(root / "real" / "page.md")
    _link_folder(root / "real" / "mid", outside)

    assert is_project_file(root, real)
    assert is_project_dir(root, root / "real")
    assert not is_project_dir(root, root / "real" / "mid")
    assert not is_project_dir(root, root / "real" / "mid" / "deeper")
    assert not is_project_file(root, root / "real" / "mid" / "deeper" / "page.md")


def test_list_real_entries_leaves_links_and_special_files_out(tmp_path: Path) -> None:
    """Only real folders and regular files are listed; links and pipes are left out."""
    outside = _write(tmp_path / "outside" / "secret.md").parent
    root = tmp_path / "project"
    _write(root / "a.md")
    (root / "sub").mkdir()
    _link_folder(root / "linked", outside)
    if os.name != "nt":
        os.mkfifo(root / "pipe.md")
        (root / "zero.md").symlink_to("/dev/zero")
        (root / "alias.md").symlink_to("a.md")

    assert sorted(p.name for p in list_real_entries(root)) == ["a.md", "sub"]


# ---------------------------------------------------------------------------
# The stray-plans sweep, a walk of its own
# ---------------------------------------------------------------------------


def test_the_stray_plans_sweep_does_not_follow_a_folder_link(tmp_path: Path) -> None:
    """A folder link to a tree that holds a plans folder is not searched.

    The sweep in ``no-global-plans-grep`` looks for stray plans folders below
    the root. It went into every entry that ``is_dir()`` called a folder, and
    that call follows a junction or a symbolic link, so a link to an outside
    tree made it search that tree and report a plans folder outside the
    project. A stray plans folder inside the project is still reported.
    """
    outside = tmp_path / "outside"
    (outside / "deep" / ".plans").mkdir(parents=True)
    root = tmp_path / "project"
    (root / "real" / ".plans").mkdir(parents=True)
    _link_folder(root / "j", outside)

    findings = no_global_plans_grep._sweep_stray_plans_dirs(root, frozenset())

    assert [finding.path for finding in findings] == ["real/.plans/"]


def test_the_stray_plans_sweep_reports_a_linked_plans_child_by_name(
    tmp_path: Path,
) -> None:
    """A ``plans`` link inside a nested ``.apothem`` folder is a stray, not entered.

    Its plans tree lives wherever the link leads, so the sweep reports the link
    by name; it never lists the folder the link points to.
    """
    outside = tmp_path / "outside"
    (outside / "deep" / ".plans").mkdir(parents=True)
    root = tmp_path / "project"
    (root / "sub" / ".apothem").mkdir(parents=True)
    _link_folder(root / "sub" / ".apothem" / "plans", outside)
    (root / "other" / ".apothem" / "plans").mkdir(parents=True)

    findings = no_global_plans_grep._sweep_stray_plans_dirs(root, frozenset())

    assert sorted(finding.path for finding in findings) == [
        "other/.apothem/plans/",
        "sub/.apothem/plans/",
    ]
    linked = next(f for f in findings if f.path == "sub/.apothem/plans/")
    assert "link" in linked.detail


@pytest.mark.parametrize(
    ("link_rel", "reported"),
    [
        (".plans", ".plans/"),
        ("sub/.plans", "sub/.plans/"),
        (".apothem", ".apothem/"),
        (".apothem/plans", ".apothem/plans/"),
    ],
    ids=["root-plans", "nested-plans", "root-apothem", "canonical-plans"],
)
def test_the_stray_plans_sweep_reports_a_plans_location_that_is_a_link(
    tmp_path: Path, link_rel: str, reported: str
) -> None:
    """A link at a plans location is reported by name, the canonical one included.

    An operator who keeps plans in a global folder and links it into the
    project has a plans tree outside the project, whatever the link is called.
    The sweep reports it without following the link, so nothing behind it, not
    even another plans folder, is listed.
    """
    outside = tmp_path / "outside"
    (outside / "deep" / ".plans").mkdir(parents=True)
    root = tmp_path / "project"
    link = root / link_rel
    link.parent.mkdir(parents=True, exist_ok=True)
    _link_folder(link, outside)

    findings = no_global_plans_grep._sweep_stray_plans_dirs(root, frozenset())

    assert [finding.path for finding in findings] == [reported]


# ---------------------------------------------------------------------------
# A forbidden name is checked by name, link or not
# ---------------------------------------------------------------------------


def test_a_top_level_docs_link_is_still_a_finding(tmp_path: Path) -> None:
    """A ``docs`` link at the root is the forbidden entry, without following it."""
    outside = tmp_path / "outside"
    (outside / "page.md").parent.mkdir(parents=True)
    root = tmp_path / "project"
    root.mkdir()
    _link_folder(root / "docs", outside)

    result = no_toplevel_docs_grep.check(root)

    assert [finding.path for finding in result.findings] == ["docs/"]


def test_a_top_level_docs_file_is_not_a_finding(tmp_path: Path) -> None:
    """A regular file named ``docs`` is not the forbidden folder, as before."""
    root = tmp_path / "project"
    _write(root / "docs", "notes\n")

    assert no_toplevel_docs_grep.check(root).findings == []


# ---------------------------------------------------------------------------
# A link never hides a file without a trace
# ---------------------------------------------------------------------------


def test_the_report_lists_a_skipped_link(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A docs folder linked into a pruned folder is named under ``skipped_links``.

    The walk does not follow the link, and it prunes ``node_modules``, so the
    pages are read nowhere; the report says which link it left out.
    """
    root = tmp_path / "project"
    _write(root / "README.md", "# Sample\n")
    _write(root / "node_modules" / "docs-src" / "guide.md", "Install 9.9.9 now.\n")
    (root / "site" / "content").mkdir(parents=True)
    _link_folder(root / "site" / "content" / "docs", root / "node_modules" / "docs-src")

    dynamism_grep._main(["dynamism-grep", str(root)])
    report = json.loads(capsys.readouterr().out)

    assert report["skipped_links"] == ["site/content/docs"]
    assert report["findings"] == []


# ---------------------------------------------------------------------------
# A fixed file that links to another file in the project still counts
# ---------------------------------------------------------------------------


def _symlink_file_or_skip(link: Path, target: str) -> None:
    """Make *link* a symbolic link with the text *target*, or skip the test."""
    link.parent.mkdir(parents=True, exist_ok=True)
    _symlink_or_skip(link, Path(target))


def test_project_file_target_follows_one_link_inside_the_project(
    tmp_path: Path,
) -> None:
    """A link to a regular file in the project names that file; nothing else does."""
    root = tmp_path / "project"
    agents = _write(root / "AGENTS.md", "# Agents\n")
    beside = _write(tmp_path / "beside.md")
    _write(root / "docs" / "page.md")
    _symlink_file_or_skip(root / "CLAUDE.md", "AGENTS.md")
    _symlink_file_or_skip(root / "nested" / "up.md", "../AGENTS.md")
    _symlink_file_or_skip(root / "out.md", str(beside))
    _symlink_file_or_skip(root / "chain.md", "CLAUDE.md")
    _symlink_file_or_skip(root / "folder.md", "docs")

    assert project_file_target(root, agents) == agents
    assert project_file_target(root, root / "CLAUDE.md") == agents
    assert project_file_target(root, root / "nested" / "up.md") == agents
    assert project_file_target(root, root / "out.md") is None
    assert project_file_target(root, root / "chain.md") is None
    assert project_file_target(root, root / "folder.md") is None
    assert project_file_target(root, root / "missing.md") is None


def test_a_required_surface_that_links_inside_the_project_counts(
    tmp_path: Path,
) -> None:
    """``CLAUDE.md`` pointing at ``AGENTS.md`` is a present surface, read at its target."""
    root = tmp_path / "project"
    _write(root / "AGENTS.md", "# Agents\n")
    _symlink_file_or_skip(root / "CLAUDE.md", "AGENTS.md")

    result = plans_discipline_language_grep.check(root)

    absent = [
        f.surface
        for f in result.findings
        if f.detail.startswith("surface file absent at canonical path")
    ]
    assert "CLAUDE.md" not in absent
    assert "AGENTS.md" not in absent


def test_the_stray_plans_sweep_names_a_link_it_does_not_search(tmp_path: Path) -> None:
    """A link the sweep does not search is named in the skip log.

    ``vend`` leads to a folder holding a ``.plans`` tree. The sweep never
    follows it, so the report must say which link it left out.
    """
    outside = tmp_path / "outside"
    (outside / ".plans").mkdir(parents=True)
    root = (tmp_path / "project").resolve()
    root.mkdir()
    _link_folder(root / "vend", outside)

    start_skip_log(root)
    findings = no_global_plans_grep._sweep_stray_plans_dirs(root, frozenset())

    assert findings == []
    assert take_skipped_paths() == ["vend"]


def _fake_readlink(monkeypatch: pytest.MonkeyPatch, link: Path, text: str) -> None:
    """Make *link* read as a symbolic link holding *text*, on any host."""
    real_readlink = Path.readlink

    def readlink(self: Path) -> Path:
        if self == link:
            return Path(text)
        return real_readlink(self)

    monkeypatch.setattr(Path, "readlink", readlink)


def test_a_link_target_is_found_level_by_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``..`` steps up only from a real folder, so a link on the way stops it.

    The system resolves ``jsub/../AGENTS.md`` through the link ``jsub``, so
    tidying the text to ``AGENTS.md`` would read a file the link does not name.
    The link text is faked, so this runs on hosts that cannot create links.
    """
    outside = tmp_path / "outside"
    _write(outside / "AGENTS.md")
    root = (tmp_path / "project").resolve()
    agents = _write(root / "AGENTS.md")
    (root / "real").mkdir()
    (root / "nested").mkdir()
    (outside / "sub").mkdir()
    _link_folder(root / "jsub", outside / "sub")
    link = root / "nested" / "CLAUDE.md"
    cases = {
        "../AGENTS.md": agents,
        "../real/../AGENTS.md": agents,
        str(agents): agents,
        "../jsub/../AGENTS.md": None,
        "../../outside/AGENTS.md": None,
        str(outside / "AGENTS.md"): None,
        "..": None,
    }
    back = chr(92)  # a backslash, built here so no escape is needed
    unc = back.join(["", "", "?", "UNC", "server", "share", "AGENTS.md"])
    cases[unc] = None
    if os.name == "nt":
        cases["C:AGENTS.md"] = None
        cases[back + "AGENTS.md"] = None
    for text, expected in cases.items():
        _fake_readlink(monkeypatch, link, text)
        assert _project_paths._link_target(root, link) == expected, text


@pytest.mark.skipif(os.name != "nt", reason="junctions exist only on Windows")
def test_a_junction_to_a_file_is_not_read_as_that_file(tmp_path: Path) -> None:
    """Only a symbolic link names a file; a junction to one cannot be opened as it."""
    winapi = pytest.importorskip("_winapi")
    root = (tmp_path / "project").resolve()
    agents = _write(root / "AGENTS.md")
    try:
        winapi.CreateJunction(str(agents), str(root / "CLAUDE.md"))
    except OSError as exc:
        pytest.skip(f"cannot create a junction to a file here: {exc}")

    assert project_file_target(root, root / "CLAUDE.md") is None
