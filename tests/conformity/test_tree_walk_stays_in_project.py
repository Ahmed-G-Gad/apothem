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
import os
from pathlib import Path

import pytest

from apothem.conformity._grep_base import (
    is_project_dir,
    is_project_file,
    iter_tree_files,
    list_real_entries,
)

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
