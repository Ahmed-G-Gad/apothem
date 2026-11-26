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
import subprocess
from pathlib import Path
from typing import NoReturn

import pytest

from apothem.conformity import (
    _bounded_run,
    _corpus,
    _grep_base,
    _project_paths,
    agents_md_coverage_grep,
    conventional_commit_grep,
    dynamism_grep,
    gate,
    gate_evidence_grep,
    harden_runner_grep,
    naming_grep,
    no_global_plans_grep,
    no_toplevel_docs_grep,
    oidc_trusted_publishing_grep,
    plan_next_step_consistency_grep,
    plan_suite_structure_grep,
    plans_discipline_language_grep,
)
from apothem.conformity import (
    _git as _git_module,
)
from apothem.conformity._grep_base import (
    is_project_dir,
    is_project_file,
    iter_tree_files,
    list_real_entries,
    nearest_linked_git_entry,
    no_files,
    project_file_target,
)
from apothem.conformity._project_paths import (
    note_root_spelling,
    start_skip_log,
    take_skipped_paths,
)
from tests._shared.git_env import hermetic_git_env

_POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt", reason="named pipes and /dev/zero exist only on POSIX systems"
)

_POSIX_SYMLINKS = pytest.mark.skipif(
    os.name == "nt", reason="a symbolic link to a file needs a privilege on Windows"
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
    """``CLAUDE.md`` pointing at ``AGENTS.md`` is a present surface, read at its target.

    A guard: main followed every link, so this passed there too; it keeps the
    link-aware reader from treating an in-project link as missing.
    """
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
    """Make *link* read as a symbolic link holding *text*, on any host.

    ``os.readlink`` returns the text as stored; ``Path.readlink`` is patched
    too, for any caller that reads a link that way.
    """
    real_readlink = Path.readlink
    real_os_readlink = os.readlink

    def readlink(self: Path) -> Path:
        if self == link:
            return Path(text)
        return real_readlink(self)

    def os_readlink(
        path: os.PathLike[str] | str, *args: object, **kwargs: object
    ) -> str:
        if Path(path) == link:
            return text
        return real_os_readlink(path, *args, **kwargs)  # type: ignore[no-any-return,arg-type]

    monkeypatch.setattr(Path, "readlink", readlink)
    monkeypatch.setattr(os, "readlink", os_readlink)


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
    # On POSIX a backslash is part of a name; that case is tested below.
    if os.name == "nt":
        cases[unc] = None
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


# ---------------------------------------------------------------------------
# Review round 4: Win32 names, link names, typed roots, linked folders
# ---------------------------------------------------------------------------

_WINDOWS_ONLY = pytest.mark.skipif(
    os.name != "nt", reason="Win32 rewrites trailing dots and spaces only on Windows"
)


def _extended(path: Path) -> Path:
    """Return *path* in the extended form, so Win32 keeps a trailing dot."""
    back = chr(92)
    return Path(back * 2 + "?" + back + str(path))


@_WINDOWS_ONLY
def test_a_trailing_dot_folder_beside_a_junction_is_not_entered(tmp_path: Path) -> None:
    """``X.`` reopened by name becomes ``X``; the junction ``X`` is never reached.

    The listing reports ``X.`` as a real folder, but Win32 drops the trailing
    dot when the walk opens it again by name, so the walk would list the
    junction ``X`` beside it, which leads out of the project.
    """
    outside = tmp_path / "outside"
    _write(outside / "secret.md")
    root = (tmp_path / "project").resolve()
    _write(root / "README.md")
    _link_folder(root / "X", outside)
    _extended(root / "X.").mkdir()
    try:
        assert _walk(root, ".md") == ["README.md"]
        assert sorted(p.name for p in list_real_entries(root)) == ["README.md"]
        assert not is_project_file(root, root / "X." / "secret.md")
    finally:
        _extended(root / "X.").rmdir()


@_WINDOWS_ONLY
def test_trailing_dot_folders_beside_junctions_to_the_root_do_not_loop(
    tmp_path: Path,
) -> None:
    """Two ``a.``/``a`` pairs that lead back to the root used to walk for ever."""
    root = (tmp_path / "project").resolve()
    _write(root / "page.md")
    made: list[Path] = []
    try:
        for name in ("a", "b"):
            _link_folder(root / name, root)
            _extended(root / f"{name}.").mkdir()
            made.append(root / f"{name}.")
        found = [
            p.relative_to(root).as_posix()
            for p in itertools.islice(iter_tree_files(root, (".md",)), _LOOP_CAP)
        ]
        assert found == ["page.md"]
    finally:
        for folder in made:
            _extended(folder).rmdir()


def test_naming_checks_a_link_by_its_own_name(tmp_path: Path) -> None:
    """A link is a name in the tree: naming checks it without entering it."""
    outside = tmp_path / "outside"
    _write(outside / "Worse_Name.md")
    root = (tmp_path / "project").resolve()
    _write(root / "src" / "apothem" / "good" / "page.md")
    _link_folder(root / "src" / "apothem" / "Bad_Name", outside)

    result = naming_grep.check_corpus(root)

    assert [finding.component for finding in result.findings] == ["Bad_Name"]


def test_an_absolute_link_through_the_typed_root_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A link written through the root as the operator typed it is inside it.

    The root is resolved before the check, so an absolute link spelled through
    another path to the same folder used to count as missing.
    """
    root = (tmp_path / "project").resolve()
    agents = _write(root / "AGENTS.md")
    alias = tmp_path / "alias"
    _link_folder(alias, root)
    link = root / "CLAUDE.md"
    _fake_readlink(monkeypatch, link, str(alias / "AGENTS.md"))
    try:
        note_root_spelling(root, root)
        assert _project_paths._link_target(root, link) is None
        note_root_spelling(alias, root)
        assert _project_paths._link_target(root, link) == agents
    finally:
        note_root_spelling(root, root)


@pytest.mark.skipif(os.name == "nt", reason="a doubled leading slash is POSIX only")
def test_a_doubled_leading_slash_names_the_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POSIX reads a leading ``//`` as ``/``, so the link still counts."""
    root = (tmp_path / "project").resolve()
    agents = _write(root / "AGENTS.md")
    link = root / "CLAUDE.md"
    _fake_readlink(monkeypatch, link, "/" + str(agents))

    assert _project_paths._link_target(root, link) == agents


def test_a_fixed_folder_that_is_a_link_does_not_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A workflows folder that is a link fails, where a missing one passes.

    The workflow validators pass on a project with no workflows folder yet.
    A folder behind a link may hold workflows the gate never reads, so that
    run reports the link under ``skipped_links`` and does not pass.
    """
    outside = tmp_path / "outside"
    _write(outside / "ci.yml", "name: ci" + chr(10))
    root = (tmp_path / "project").resolve()
    (root / ".github").mkdir(parents=True)
    _link_folder(root / ".github" / "workflows", outside)

    code = harden_runner_grep._main(["harden-runner-grep", str(root)])
    report = json.loads(capsys.readouterr().out)

    assert code == 2
    assert report["passed"] is False
    assert report["skipped_links"] == [".github/workflows"]


def test_a_dangling_top_level_docs_link_is_a_finding(tmp_path: Path) -> None:
    """A ``docs`` link whose target is gone is still the forbidden entry.

    Following the link, as ``is_dir()`` does, finds nothing there.
    """
    gone = tmp_path / "gone"
    gone.mkdir()
    root = (tmp_path / "project").resolve()
    root.mkdir()
    _link_folder(root / "docs", gone)
    gone.rmdir()

    assert [f.path for f in no_toplevel_docs_grep.check(root).findings] == ["docs/"]


def test_a_readme_link_inside_the_project_counts_for_coverage(tmp_path: Path) -> None:
    """A folder whose README links inside the project carries a README.

    One that leads out of the project does not, so that folder is not taken
    to carry a contributor README.
    """
    root = (tmp_path / "project").resolve()
    _write(root / "docs" / "guide.md")
    beside = _write(tmp_path / "beside.md")
    _symlink_file_or_skip(root / "guide" / "README.md", "../docs/guide.md")
    _symlink_file_or_skip(root / "other" / "README.md", str(beside))

    folders = agents_md_coverage_grep.meaningful_folders(root)

    assert "guide" in folders
    assert "other" not in folders


# ---------------------------------------------------------------------------
# Review round 5: ".." above the root, the typed root, skip-log traces
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sibling", "inside"),
    [("desk", True), ("des" + chr(0x212A), False)],
    ids=["back-into-the-root", "kelvin-sibling"],
)
def test_a_link_target_above_the_root_must_come_back_exactly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sibling: str, inside: bool
) -> None:
    """``../desk/AGENTS.md`` from the root ``desk`` lands inside it and counts.

    Climbing above the root may only come straight back in under the root's
    own name, spelled exactly. Windows compares names without case, and the
    Kelvin sign folds to ``K``, so a sibling ``desK`` would pass a by-name
    check and is refused.
    """
    root = (tmp_path / "desk").resolve()
    agents = _write(root / "AGENTS.md")
    if sibling != root.name:
        try:
            _write(tmp_path / sibling / "AGENTS.md")
        except OSError as exc:
            pytest.skip(f"this file system folds the sibling name: {exc}")
    link = root / "CLAUDE.md"
    _fake_readlink(monkeypatch, link, f"../{sibling}/AGENTS.md")

    expected = agents if inside else None
    assert _project_paths._link_target(root, link) == expected


def test_an_absolute_link_to_a_sibling_that_folds_onto_the_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An absolute target is compared with the root's own parts, exactly."""
    root = (tmp_path / "desk").resolve()
    _write(root / "AGENTS.md")
    link = root / "CLAUDE.md"
    folded = root.parent / ("des" + chr(0x212A)) / "AGENTS.md"
    _fake_readlink(monkeypatch, link, str(folded))

    assert _project_paths._link_target(root, link) is None


def test_device_and_extended_paths_count_as_outside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On Windows only an extended drive path can name a project file."""
    root = (tmp_path / "project").resolve()
    agents = _write(root / "AGENTS.md")
    link = root / "CLAUDE.md"
    back = chr(92)
    outside = [
        back.join(["", "", "?", "unc", "server", "share", "AGENTS.md"]),
        back.join(["", "", "?", "GLOBALROOT", "Device", "HarddiskVolume1", "x"]),
        back.join(["", "", "?", "Volume{00000000-0000-0000-0000-000000000000}", "x"]),
        back.join(["", "", ".", "pipe", "x"]),
        back.join(["", "??", "C:", "x"]),
    ]
    if os.name == "nt":
        # Decoys: read without its prefix, each text would name one of these.
        for text in outside:
            rest = text.split(back, 3)[-1]
            _write(root.joinpath(*rest.split(back)))
    for text in outside:
        _fake_readlink(monkeypatch, link, text)
        # On POSIX the same text is one plain name in the link's folder.
        expected = None if os.name == "nt" else link.parent / text
        assert _project_paths._link_target(root, link) == expected, text
    if os.name == "nt":
        _fake_readlink(monkeypatch, link, back * 2 + "?" + back + str(agents))
        assert _project_paths._link_target(root, link) == agents


@_WINDOWS_ONLY
def test_the_walk_does_not_list_an_unwanted_trailing_dot_file(tmp_path: Path) -> None:
    """A file the walk would not have read is not listed, so scopes stay empty."""
    root = (tmp_path / "project").resolve()
    _write(root / "page.md")
    notes = _extended(root / "notes.")
    notes.write_bytes(b"x")
    try:
        start_skip_log(root)
        assert _walk(root, ".md") == ["page.md"]
        assert take_skipped_paths() == []
    finally:
        notes.unlink()


@_POSIX_SYMLINKS
def test_a_package_folder_whose_readme_links_out_still_needs_coverage(
    tmp_path: Path,
) -> None:
    """Rule B: a README that leads out of the project is no README."""
    root = (tmp_path / "project").resolve()
    _write(root / "src" / "apothem" / "foo" / "mod.py")
    beside = _write(tmp_path / "beside.md")
    (root / "src" / "apothem" / "foo" / "README.md").symlink_to(beside)

    assert "src/apothem/foo" in agents_md_coverage_grep.meaningful_folders(root)


@_POSIX_SYMLINKS
def test_a_companion_that_links_out_is_not_judged_stale(tmp_path: Path) -> None:
    """A committed companion later swapped for an outside link is not read."""
    root = (tmp_path / "project").resolve()
    folder = root / "src" / "apothem" / "foo"
    _write(folder / "AGENTS.md", "# Foo\n")
    _write(folder / "mod.py", "x = 1\n")
    env = hermetic_git_env()

    def git(*args: str, when: int | None = None) -> None:
        run_env = dict(env)
        if when is not None:
            stamp = f"{when} +0000"
            run_env["GIT_AUTHOR_DATE"] = stamp
            run_env["GIT_COMMITTER_DATE"] = stamp
        subprocess.run(
            ["git", *args], cwd=root, env=run_env, check=True, capture_output=True
        )

    git("init", "-q")
    git("config", "user.email", "test@apothem.invalid")
    git("config", "user.name", "apothem-test")
    git("config", "commit.gpgsign", "false")
    git("add", "src/apothem/foo/AGENTS.md")
    git("commit", "-qm", "companion", when=1_000_000_000)
    _write(folder / "mod.py", "x = 2\n")
    git("add", "-A")
    git("commit", "-qm", "content", when=1_000_100_000)
    (folder / "AGENTS.md").unlink()
    (folder / "AGENTS.md").symlink_to(_write(tmp_path / "outside.md", "# Out\n"))

    result = agents_md_coverage_grep.check(root)

    assert [f for f in result.findings if "AGENTS" in str(f)] == []


def test_the_typed_root_is_recorded_by_parse_root_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through the command-line parser, a link spelled via the typed root counts."""
    root = (tmp_path / "project").resolve()
    agents = _write(root / "AGENTS.md")
    alias = tmp_path / "alias"
    _link_folder(alias, root)
    link = root / "CLAUDE.md"
    _fake_readlink(monkeypatch, link, str(alias / "AGENTS.md"))
    try:
        resolved = _grep_base.parse_root_args(["v", str(alias)], prog="v").root
        assert resolved == root
        assert _project_paths._link_target(root, link) == agents
        _grep_base.parse_root_args(["v", str(alias / ".." / "alias")], prog="v")
        assert _project_paths._link_target(root, link) is None
    finally:
        note_root_spelling(root, root)
        take_skipped_paths()


@_WINDOWS_ONLY
def test_a_trailing_dot_part_is_refused_even_when_it_names_a_real_folder(
    tmp_path: Path,
) -> None:
    """``X.`` would be opened as ``X``; the check refuses the spelling itself."""
    root = (tmp_path / "project").resolve()
    _write(root / "X" / "page.md")

    assert is_project_file(root, root / "X" / "page.md")
    assert not is_project_file(root, root / "X." / "page.md")


@_WINDOWS_ONLY
def test_the_walk_names_a_trailing_dot_folder_it_skips(tmp_path: Path) -> None:
    """A folder ending in a dot is left out and listed under the skip log."""
    root = (tmp_path / "project").resolve()
    _write(root / "page.md")
    _extended(root / "X.").mkdir()
    try:
        start_skip_log(root)
        assert _walk(root, ".md") == ["page.md"]
        assert take_skipped_paths() == ["X."]
    finally:
        _extended(root / "X.").rmdir()


def test_the_walk_names_a_link_with_a_pruned_name(tmp_path: Path) -> None:
    """A link named like a pruned folder is not walked, but it is listed."""
    outside = tmp_path / "outside"
    _write(outside / "page.md")
    root = (tmp_path / "project").resolve()
    _write(root / "page.md")
    _link_folder(root / "node_modules", outside)

    start_skip_log(root)
    assert _walk(root, ".md") == ["page.md"]
    assert take_skipped_paths() == ["node_modules"]


# ---------------------------------------------------------------------------
# Review round 7: the root under another spelling, drive parts, ASCII case,
# git through a linked .git per caller, listing notes, used links
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, env=hermetic_git_env(), check=True, capture_output=True
    )


def _project_with_linked_git(tmp_path: Path) -> Path:
    """Return a project whose ``.git`` links to another, working repository.

    The other repository tracks a plans file and has history, so a check that
    ran git through the link would see it: each caller's own result shows
    whether that caller looked at the link first.
    """
    other = tmp_path / "other"
    _write(other / ".plans" / "x.md")
    _write(other / "pkg" / "AGENTS.md")
    _git(other, "init", "-q")
    _git(other, "config", "user.email", "test@apothem.invalid")
    _git(other, "config", "user.name", "apothem-test")
    _git(other, "config", "commit.gpgsign", "false")
    _git(other, "add", "-A")
    _git(other, "commit", "-qm", "feat: other repository")
    root = (tmp_path / "project").resolve()
    root.mkdir()
    _link_folder(root / ".git", other / ".git")
    return root


_LINKED_GIT_MESSAGE = "the .git entry is a link, so git would read another repository"


def test_the_plans_listing_refuses_a_linked_git(tmp_path: Path) -> None:
    root = _project_with_linked_git(tmp_path)
    start_skip_log(root)
    with pytest.raises(RuntimeError) as raised:
        no_global_plans_grep._git_ls_files(root)
    assert str(raised.value) == _LINKED_GIT_MESSAGE
    assert take_skipped_paths() == [".git"]


def test_the_plans_check_reports_a_linked_git_and_still_sweeps(tmp_path: Path) -> None:
    root = _project_with_linked_git(tmp_path)
    (root / ".plans").mkdir()
    start_skip_log(root)
    result = no_global_plans_grep.check(root)
    assert take_skipped_paths() == [".git"]
    assert result.tracked_count == 0
    assert sorted(f.path for f in result.findings) == [".git", ".plans/"]
    assert not result.passed


def test_the_plans_command_gives_its_report_for_a_linked_git(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project_with_linked_git(tmp_path)
    code = no_global_plans_grep._main(["no-global-plans-grep", str(root)])
    payload = json.loads(capsys.readouterr().out)
    assert code != 0
    assert payload["skipped_links"] == [".git"]
    assert payload["passed"] is False


def test_the_coverage_history_refuses_a_linked_git(tmp_path: Path) -> None:
    root = _project_with_linked_git(tmp_path)
    start_skip_log(root)
    assert agents_md_coverage_grep._read_history(root) is None
    assert take_skipped_paths() == [".git"]


def test_the_commit_subject_refuses_a_linked_git(tmp_path: Path) -> None:
    root = _project_with_linked_git(tmp_path)
    start_skip_log(root)
    assert conventional_commit_grep._read_head_subject(root) == (
        None,
        "not-a-git-repo",
        None,
    )
    assert take_skipped_paths() == [".git"]


def test_the_perwrite_run_refuses_a_linked_git(tmp_path: Path) -> None:
    # The other repository tracks .plans/x.md and pkg/AGENTS.md; a run that
    # listed them through the link would scan them.
    root = _project_with_linked_git(tmp_path)
    passed, payload_json = gate._run_all_perwrite(root)
    payload = json.loads(payload_json)
    assert not passed
    assert payload["check_error"] == _LINKED_GIT_MESSAGE
    assert payload["files_scanned"] == 0


# git looks for the repository in the folders above the root too, so a run on
# a subfolder of a project whose .git is a link would read the other
# repository's index and history through it. ``pkg`` holds a file the other
# repository tracks, so a check that ran git there would find it.

_SUBFOLDERS = pytest.mark.parametrize("below", ["pkg", "pkg/deep/er"])


def _no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any program start fail the test, git through ``run_git`` or not."""

    def no_program(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError(f"a program started: {args!r}")

    monkeypatch.setattr(_bounded_run, "_POPEN", no_program)
    monkeypatch.setattr(subprocess, "Popen", no_program)


def _subfolder_of_linked_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, below: str = "pkg"
) -> Path:
    """Return a folder below :func:`_project_with_linked_git`; no program may start."""
    root = _project_with_linked_git(tmp_path)
    inner = root / below
    _write(inner / "AGENTS.md")
    _no_git(monkeypatch)
    return inner


def _project_git(inner: Path) -> Path:
    """Return the linked ``.git`` of the ``project`` folder *inner* lies in."""
    project = next(p for p in (inner, *inner.parents) if p.name == "project")
    return project / ".git"


def _above_message(inner: Path) -> str:
    return (
        f"the .git entry {_project_git(inner).as_posix()} on git's search path "
        "is a link, so the gate does not run git below it"
    )


@_SUBFOLDERS
def test_the_plans_listing_refuses_a_linked_git_above_the_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, below: str
) -> None:
    inner = _subfolder_of_linked_git(tmp_path, monkeypatch, below)
    start_skip_log(inner)
    with pytest.raises(RuntimeError) as raised:
        no_global_plans_grep._git_ls_files(inner)
    assert str(raised.value) == _above_message(inner)
    assert take_skipped_paths() == [_project_git(inner).as_posix()]


@_SUBFOLDERS
def test_the_plans_check_reports_a_linked_git_above_the_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, below: str
) -> None:
    inner = _subfolder_of_linked_git(tmp_path, monkeypatch, below)
    (inner / ".plans").mkdir()
    start_skip_log(inner)
    result = no_global_plans_grep.check(inner)
    linked = _project_git(inner).as_posix()
    assert take_skipped_paths() == [linked]
    assert result.tracked_count == 0
    # The finding names the entry as the skip log does, and the sweep ran.
    assert sorted(f.path for f in result.findings) == sorted([linked, ".plans/"])
    assert not result.passed


def test_the_plans_command_reports_a_linked_git_above_the_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    inner = _subfolder_of_linked_git(tmp_path, monkeypatch)
    code = no_global_plans_grep._main(["no-global-plans-grep", str(inner)])
    payload = json.loads(capsys.readouterr().out)
    assert code != 0
    assert payload["skipped_links"] == [_project_git(inner).as_posix()]
    assert payload["passed"] is False


@_SUBFOLDERS
def test_the_coverage_history_refuses_a_linked_git_above_the_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, below: str
) -> None:
    inner = _subfolder_of_linked_git(tmp_path, monkeypatch, below)
    start_skip_log(inner)
    assert agents_md_coverage_grep._read_history(inner) is None
    assert take_skipped_paths() == [_project_git(inner).as_posix()]


@_SUBFOLDERS
def test_the_commit_subject_refuses_a_linked_git_above_the_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, below: str
) -> None:
    inner = _subfolder_of_linked_git(tmp_path, monkeypatch, below)
    start_skip_log(inner)
    assert conventional_commit_grep._read_head_subject(inner) == (
        None,
        "not-a-git-repo",
        None,
    )
    assert take_skipped_paths() == [_project_git(inner).as_posix()]


@_SUBFOLDERS
def test_the_corpus_listing_refuses_a_linked_git_above_the_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, below: str
) -> None:
    inner = _subfolder_of_linked_git(tmp_path, monkeypatch, below)
    start_skip_log(inner)
    with pytest.raises(_corpus.CorpusListError) as raised:
        _corpus.tracked_entries(inner)
    assert str(raised.value) == _above_message(inner)
    assert take_skipped_paths() == [_project_git(inner).as_posix()]


def test_the_perwrite_run_refuses_a_linked_git_above_the_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inner = _subfolder_of_linked_git(tmp_path, monkeypatch)
    passed, payload_json = gate._run_all_perwrite(inner)
    payload = json.loads(payload_json)
    assert not passed
    assert payload["check_error"] == _above_message(inner)
    assert payload["files_scanned"] == 0


def test_the_commit_command_does_not_pass_with_a_linked_git_above_the_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    inner = _subfolder_of_linked_git(tmp_path, monkeypatch)
    code = conventional_commit_grep._main(["conventional-commit-grep", str(inner)])
    payload = json.loads(capsys.readouterr().out)
    assert code != 0
    assert payload["status"] == "not-a-git-repo"
    assert payload["passed"] is False
    assert payload["skipped_links"] == [_project_git(inner).as_posix()]


def test_the_discovering_git_run_drops_the_location_variables() -> None:
    environ = dict.fromkeys(_git_module.GIT_LOCATION_VARIABLES, "elsewhere")
    environ["GIT_CEILING_DIRECTORIES"] = "kept"
    assert set(_git_module.GIT_LOCATION_VARIABLES) <= set(
        _git_module.git_environment(environ)
    )
    discovering = _git_module.git_environment(environ, discover=True)
    assert not set(_git_module.GIT_LOCATION_VARIABLES) & set(discovering)
    assert discovering["GIT_CEILING_DIRECTORIES"] == "kept"


def _plain_repository_with_a_hook_git_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Return a plain repository while ``GIT_DIR`` names the other one.

    git exports ``GIT_DIR`` to the hooks it runs; a check run from a hook must
    still read the repository it finds from its root.
    """
    other = _project_with_linked_git(tmp_path).parent / "other"
    plain = _real_repository(tmp_path / "plain")
    _write(plain / "a.txt")
    _git(plain, "config", "user.email", "test@apothem.invalid")
    _git(plain, "config", "user.name", "apothem-test")
    _git(plain, "config", "commit.gpgsign", "false")
    _git(plain, "add", "-A")
    _git(plain, "commit", "-qm", "fix: the plain repository")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    return plain


def test_a_git_dir_from_a_hook_does_not_redirect_the_commit_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = _plain_repository_with_a_hook_git_dir(tmp_path, monkeypatch)
    subject, status, _ = conventional_commit_grep._read_head_subject(plain)
    assert (subject or "").strip() == "fix: the plain repository"
    assert status == "ok"


def test_a_git_dir_from_a_hook_does_not_redirect_the_corpus_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = _plain_repository_with_a_hook_git_dir(tmp_path, monkeypatch)
    assert [entry.name for entry in _corpus.tracked_entries(plain)] == ["a.txt"]


def test_a_git_dir_from_a_hook_does_not_redirect_the_plans_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = _plain_repository_with_a_hook_git_dir(tmp_path, monkeypatch)
    assert no_global_plans_grep._git_ls_files(plain) == ["a.txt"]


def test_a_git_dir_from_a_hook_does_not_redirect_the_coverage_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = _plain_repository_with_a_hook_git_dir(tmp_path, monkeypatch)
    # The other repository's history holds .plans/x.md and pkg/AGENTS.md.
    history = agents_md_coverage_grep._read_history(plain)
    assert history is not None
    assert set(history.times) == {"a.txt"}
    assert not agents_md_coverage_grep._is_partial_clone(plain)


def test_an_entry_lstat_cannot_read_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard fails closed: a .git entry it cannot look at counts as a link."""
    inner = (tmp_path / "project" / "pkg").resolve()
    inner.mkdir(parents=True)
    blocked = inner.parent / ".git"
    real_lstat = os.lstat

    def lstat(path: object, *args: object, **kwargs: object) -> os.stat_result:
        if os.fspath(path) == os.fspath(blocked):  # type: ignore[arg-type]
            raise PermissionError(13, "denied", os.fspath(blocked))
        return real_lstat(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "lstat", lstat)
    start_skip_log(inner)
    assert nearest_linked_git_entry(inner) == blocked
    assert take_skipped_paths() == [blocked.as_posix()]


def _real_repository(folder: Path, *, bare: bool = False) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    _git(folder, "init", "-q", *(["--bare"] if bare else []))
    return folder


@pytest.mark.parametrize("bare", [False, True], ids=["repository", "bare"])
def test_a_repository_below_a_linked_git_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bare: bool
) -> None:
    """Any .git link on git's search path is refused, even above a repository.

    git would use the inner repository first; the rule does not judge that,
    so a project whose .git is a link is refused as a whole.
    """
    project = _project_with_linked_git(tmp_path)
    inner = _real_repository(project / ("bare.git" if bare else "sub"), bare=bare)
    deep = inner / "refs" if bare else inner / "deep"
    deep.mkdir(exist_ok=True)
    _no_git(monkeypatch)
    start_skip_log(deep)
    assert nearest_linked_git_entry(deep) == project / ".git"
    assert take_skipped_paths() == [(project / ".git").as_posix()]
    with pytest.raises(_corpus.CorpusListError) as raised:
        _corpus.tracked_entries(deep)
    assert str(raised.value) == (
        f"the .git entry {(project / '.git').as_posix()} on git's search path "
        "is a link, so the gate does not run git below it"
    )


def test_a_real_git_folder_in_the_root_does_not_hide_a_link_above(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The root's own .git folder does not end the search for links above it."""
    inner = _subfolder_of_linked_git(tmp_path, monkeypatch)
    (inner / ".git").mkdir()
    start_skip_log(inner)
    assert nearest_linked_git_entry(inner) == _project_git(inner)
    assert take_skipped_paths() == [_project_git(inner).as_posix()]


def test_a_subfolder_of_a_plain_checkout_is_not_refused(tmp_path: Path) -> None:
    deep = _real_repository(tmp_path / "plain") / "a" / "b"
    deep.mkdir(parents=True)
    start_skip_log(deep)
    assert nearest_linked_git_entry(deep) is None
    assert take_skipped_paths() == []


def test_a_dangling_linked_git_above_the_root_is_refused(tmp_path: Path) -> None:
    gone = tmp_path / "gone"
    gone.mkdir()
    root = (tmp_path / "project").resolve()
    inner = root / "pkg"
    inner.mkdir(parents=True)
    _link_folder(root / ".git", gone)
    gone.rmdir()
    start_skip_log(inner)
    assert nearest_linked_git_entry(inner) == root / ".git"
    assert take_skipped_paths() == [(root / ".git").as_posix()]


def test_a_root_reached_through_a_link_is_judged_where_it_lies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The walk climbs from the resolved root, where git runs."""
    inner = _subfolder_of_linked_git(tmp_path, monkeypatch)
    door = tmp_path / "door"
    _link_folder(door, inner)
    start_skip_log(door)
    assert nearest_linked_git_entry(door) == _project_git(inner)
    assert take_skipped_paths() == [_project_git(inner).as_posix()]


@_WINDOWS_ONLY
def test_a_link_through_another_case_of_the_root_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NTFS opens ``proj`` and ``PROJ`` as one folder, so both spellings count."""
    root = (tmp_path / "Proj").resolve()
    agents = _write(root / "AGENTS.md")
    link = root / "CLAUDE.md"
    lower = str(root).lower() + chr(92) + "AGENTS.md"
    for text in (lower, "../PROJ/AGENTS.md", "../proj/AGENTS.md"):
        _fake_readlink(monkeypatch, link, text)
        assert _project_paths._link_target(root, link) == agents, text


@_WINDOWS_ONLY
def test_a_link_part_with_a_drive_looks_at_nothing_outside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``D:foo`` or ``E:`` inside a link would replace the folder with another drive."""
    root = (tmp_path / "project").resolve()
    _write(root / "sub" / "x" / "AGENTS.md")
    link = root / "CLAUDE.md"
    back = chr(92)
    looked: list[str] = []
    real_lstat = os.lstat

    def lstat(path: os.PathLike[str] | str, *args: object, **kwargs: object) -> object:
        looked.append(str(path))
        return real_lstat(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "lstat", lstat)
    texts = [
        back.join(["sub", "D:foo", "x", "AGENTS.md"]),
        back.join(["sub", "D:..", "x", "AGENTS.md"]),
        back.join(["sub", "E:", "AGENTS.md"]),
        back.join(["sub", "C:..", "..", "x", "AGENTS.md"]),
        back.join(["sub", "x", "AGENTS.md:stream"]),
    ]
    for text in texts:
        _fake_readlink(monkeypatch, link, text)
        looked.clear()
        assert _project_paths._link_target(root, link) is None, text
        assert [p for p in looked if not p.startswith(str(root))] == [], text


@pytest.mark.parametrize(
    ("root", "path", "inside"),
    [
        ("C:/proj", "c:/proj/f.md", True),
        ("//srv/share/proj", "//SRV/SHARE/proj/f.md", True),
        ("//srv/stra" + chr(0xDF) + "e/proj", "//srv/STRASSE/proj/f.md", False),
        ("//srv/share/proj", "//" + chr(0x17F) + "rv/share/proj/f.md", False),
        ("S:/proj", chr(0x17F) + ":/proj/f.md", False),
        ("I:/proj", chr(0x131) + ":/proj/f.md", False),
    ],
    ids=[
        "drive-letter",
        "ascii-share",
        "sharp-s",
        "long-s-server",
        "long-s",
        "dotless-i",
    ],
)
def test_only_ascii_letters_of_the_first_part_compare_without_case(
    root: str, path: str, inside: bool
) -> None:
    """``str.upper`` folds a sharp s to ``SS``; those name other shares and drives."""
    from pathlib import PureWindowsPath

    assert (
        _project_paths._exactly_inside(PureWindowsPath(root), PureWindowsPath(path))  # type: ignore[arg-type]
        is inside
    )


@_WINDOWS_ONLY
def test_an_extended_target_takes_dots_and_slashes_literally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After ``\\?\\`` Windows does not apply ``..`` or ``/``, so such a link is broken."""
    root = (tmp_path / "project").resolve()
    _write(root / "AGENTS.md")
    (root / "sub").mkdir()
    link = root / "CLAUDE.md"
    back = chr(92)
    prefix = back * 2 + "?" + back
    for rest in (
        str(root) + back + "sub" + back + ".." + back + "AGENTS.md",
        str(root) + back + "." + back + "AGENTS.md",
        str(root) + "/AGENTS.md",
        str(root) + back * 2 + "AGENTS.md",
        str(root) + back + "AGENTS.md" + back,
    ):
        _fake_readlink(monkeypatch, link, prefix + rest)
        assert _project_paths._link_target(root, link) is None, rest
    native = back + "??" + back
    for rest in (
        str(root) + back * 2 + "AGENTS.md",
        str(root) + back + "AGENTS.md" + back,
    ):
        _fake_readlink(monkeypatch, link, native + rest)
        assert _project_paths._link_target(root, link) is None, native + rest


def test_a_nul_in_link_text_is_refused_without_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = (tmp_path / "project").resolve()
    _write(root / "sub" / "AGENTS.md")
    link = root / "CLAUDE.md"
    _fake_readlink(monkeypatch, link, "sub" + chr(0) + "b/AGENTS.md")
    looked: list[str] = []
    real_lstat = os.lstat

    def lstat(path: os.PathLike[str] | str, *args: object, **kwargs: object) -> object:
        looked.append(str(path))
        return real_lstat(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "lstat", lstat)
    assert _project_paths._link_target(root, link) is None
    assert looked == []


@_WINDOWS_ONLY
def test_a_folder_listing_notes_a_trailing_dot_file_only_where_names_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``notes.`` is noted for a caller that checks file names, not for one that wants folders."""
    root = (tmp_path / "project").resolve()
    plans = root / ".apothem" / "plans"
    plans.mkdir(parents=True)
    notes = _extended(plans / "notes.")
    notes.write_bytes(b"x")
    try:
        start_skip_log(root)
        assert list_real_entries(plans) == []
        assert take_skipped_paths() == [".apothem/plans/notes."]
        start_skip_log(root)
        assert list_real_entries(plans, wanted_files=no_files) == []
        assert list_real_entries(plans, wanted_files=lambda name: name == "other") == []
        assert take_skipped_paths() == []
        start_skip_log(root)
        assert list_real_entries(plans, wanted_files=lambda name: name == "notes") == []
        assert take_skipped_paths() == [".apothem/plans/notes."]
        code = gate_evidence_grep._main(["gate-evidence-grep", str(root)])
        payload = json.loads(capsys.readouterr().out)
        assert code == 0
        assert payload.get("skipped_links", []) == []
    finally:
        notes.unlink()


@_WINDOWS_ONLY
def test_the_walk_notes_a_trailing_dot_file_it_would_have_read(tmp_path: Path) -> None:
    """``page.md.`` opens as ``page.md``, a name the walk wants, so it is named."""
    root = (tmp_path / "project").resolve()
    _write(root / "keep.md")
    page = _extended(root / "page.md.")
    page.write_bytes(b"x")
    try:
        start_skip_log(root)
        assert _walk(root, ".md") == ["keep.md"]
        assert take_skipped_paths() == ["page.md."]
    finally:
        page.unlink()


@_WINDOWS_ONLY
def test_a_junction_with_a_trailing_dot_is_a_link(tmp_path: Path) -> None:
    """A link is a link whatever its name, so the walk names it as one."""
    outside = tmp_path / "outside"
    _write(outside / "page.md")
    root = (tmp_path / "project").resolve()
    root.mkdir()
    winapi = pytest.importorskip("_winapi")
    winapi.CreateJunction(str(outside), str(_extended(root / "docs.")))
    try:
        assert [(p.name, kind) for p, kind in _project_paths.scan_entries(root)] == [
            ("docs.", _project_paths.LINK_ENTRY)
        ]
    finally:
        _extended(root / "docs.").rmdir()


@_WINDOWS_ONLY
def test_the_stray_plans_sweep_names_a_trailing_dot_folder(tmp_path: Path) -> None:
    """A plans tree inside ``work.`` is not searched, so the folder is named."""
    root = (tmp_path / "project").resolve()
    root.mkdir()
    work = _extended(root / "work.")
    (work / ".plans").mkdir(parents=True)
    try:
        start_skip_log(root)
        assert no_global_plans_grep._sweep_stray_plans_dirs(root, frozenset()) == []
        assert take_skipped_paths() == ["work."]
    finally:
        (work / ".plans").rmdir()
        work.rmdir()


def test_a_name_walk_with_links_names_a_folder_link_it_does_not_want(
    tmp_path: Path,
) -> None:
    """A folder link may hide a README, so a walk that yields links still names it."""
    outside = tmp_path / "outside"
    _write(outside / "README.md")
    root = (tmp_path / "project").resolve()
    _write(root / "README.md")
    _link_folder(root / "vend", outside)

    start_skip_log(root)
    found = list(iter_tree_files(root, names=("README.md",), include_links=True))
    assert [p.relative_to(root).as_posix() for p in found] == ["README.md"]
    assert take_skipped_paths() == ["vend"]


def test_a_readme_link_the_check_used_is_not_listed_as_skipped(tmp_path: Path) -> None:
    """A README link that names a project file counts, so it hid nothing."""
    root = (tmp_path / "project").resolve()
    _write(root / "src" / "apothem" / "bar" / "mod.py")
    shared = _write(root / "docs-shared" / "README.md")
    _symlink_or_skip(root / "src" / "apothem" / "bar" / "README.md", shared)

    start_skip_log(root)
    folders = agents_md_coverage_grep.meaningful_folders(root)
    assert "src/apothem/bar" in folders
    assert take_skipped_paths() == []


_KELVIN_NAME = "chec" + chr(0x212A) + ".yml"


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        ((("skip", "check.yml"), ("use", "check.yml")), []),
        ((("use", "check.yml"), ("skip", "check.yml")), []),
        ((("skip", _KELVIN_NAME), ("use", "check.yml")), [_KELVIN_NAME]),
        ((("use", "check.yml"), ("skip", _KELVIN_NAME)), [_KELVIN_NAME]),
    ],
    ids=[
        "skip-then-use",
        "use-then-skip",
        "kelvin-skip-then-use",
        "kelvin-use-then-skip",
    ],
)
def test_only_the_exact_link_read_through_leaves_the_skip_log(
    tmp_path: Path, steps: tuple[tuple[str, str], ...], expected: list[str]
) -> None:
    """``Path`` equality folds case on Windows; a Kelvin-sign sibling is another entry."""
    root = (tmp_path / "project").resolve()
    start_skip_log(root)
    for step, name in steps:
        if step == "skip":
            _project_paths.note_skipped(root / name)
        else:
            _project_paths._note_used(root / name)
    assert take_skipped_paths() == expected


def _case_sensitive_folder(folder: Path) -> Path:
    """Make *folder* and turn on NTFS case sensitivity for it, or skip."""
    folder.mkdir(parents=True)
    try:
        subprocess.run(
            ["fsutil", "file", "setCaseSensitiveInfo", str(folder), "enable"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"this host cannot make a case-sensitive folder: {exc}")
    return folder


@_WINDOWS_ONLY
def test_another_case_that_is_another_folder_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In a case-sensitive folder ``proj`` beside ``Proj`` is a different folder."""
    base = _case_sensitive_folder(tmp_path / "cs")
    root = (base / "Proj").resolve()
    _write(root / "AGENTS.md")
    _write(base / "proj" / "AGENTS.md")
    link = root / "CLAUDE.md"
    for text in ("../proj/AGENTS.md", str(base / "proj" / "AGENTS.md")):
        _fake_readlink(monkeypatch, link, text)
        assert _project_paths._link_target(root, link) is None, text


@_WINDOWS_ONLY
def test_an_other_case_ancestor_that_is_a_junction_is_not_crossed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``work`` beside ``Work`` may be a junction; nothing below it is looked at."""
    base = _case_sensitive_folder(tmp_path / "cs")
    root = (base / "Work" / "Proj").resolve()
    _write(root / "AGENTS.md")
    elsewhere = tmp_path / "elsewhere"
    _write(elsewhere / "Proj" / "AGENTS.md")
    _link_folder(base / "work", elsewhere)
    link = root / "CLAUDE.md"
    _fake_readlink(monkeypatch, link, str(base / "work" / "Proj" / "AGENTS.md"))
    looked: list[str] = []
    real_lstat = os.lstat

    def lstat(path: os.PathLike[str] | str, *args: object, **kwargs: object) -> object:
        looked.append(str(path))
        return real_lstat(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "lstat", lstat)
    assert _project_paths._link_target(root, link) is None
    below = str(base / "work") + chr(92)
    assert [p for p in looked if p.startswith(below)] == []


@_WINDOWS_ONLY
@pytest.mark.parametrize(
    ("validator", "expected"),
    [
        (plan_suite_structure_grep, [".apothem/plans/demo/01-intro.md."]),
        (plan_next_step_consistency_grep, []),
        (oidc_trusted_publishing_grep, [".github/workflows/publish-py.yml."]),
    ],
    ids=["suite-root-prefixes", "folders-only", "publish-workflows"],
)
def test_each_listing_caller_names_only_the_trailing_dot_files_it_would_read(
    tmp_path: Path, validator: object, expected: list[str]
) -> None:
    """A caller's own name rule decides which skipped files the report lists."""
    root = (tmp_path / "project").resolve()
    plans = root / ".apothem" / "plans"
    suite = plans / "demo"
    _write(suite / "PLAN.md")
    _write(suite / "phases" / "01-intro" / "PHASE.md")
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    for odd in (
        suite / "01-intro.md.",
        suite / "notes.",
        suite / "phases" / "01-intro" / "notes.",
        plans / "stray.",
        workflows / "publish-py.yml.",
        workflows / "readme.txt.",
    ):
        _extended(odd).write_bytes(b"x")
    start_skip_log(root)
    validator.check(root)  # type: ignore[attr-defined]
    assert take_skipped_paths() == expected


def test_a_sibling_the_host_case_rule_keeps_apart_is_not_looked_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``desK`` with a Kelvin sign is refused by name, before any ``os.lstat``."""
    root = (tmp_path / "desk").resolve()
    _write(root / "AGENTS.md")
    sibling = tmp_path / ("des" + chr(0x212A))
    try:
        _write(sibling / "AGENTS.md")
    except OSError as exc:
        pytest.skip(f"this file system folds the sibling name: {exc}")
    link = root / "CLAUDE.md"
    looked: list[str] = []
    real_lstat = os.lstat

    def lstat(path: os.PathLike[str] | str, *args: object, **kwargs: object) -> object:
        looked.append(str(path))
        return real_lstat(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "lstat", lstat)
    for text in (f"../{sibling.name}/AGENTS.md", str(sibling / "AGENTS.md")):
        _fake_readlink(monkeypatch, link, text)
        looked.clear()
        assert _project_paths._link_target(root, link) is None, text
        assert [p for p in looked if p.startswith(str(sibling))] == [], text
