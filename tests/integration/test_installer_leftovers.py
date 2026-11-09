# SPDX-License-Identifier: MIT

"""Folders a stopped install left beside APOTHEM_HOME stop the next one.

install.sh builds the new source in a folder beside APOTHEM_HOME
(``.apothem-extract.<leaf>.*`` for a release archive,
``.apothem-clone.<leaf>.*`` for a clone, ``<leaf>`` being APOTHEM_HOME's own
folder name) and moves the earlier tree to ``.apothem-old.<leaf>.*/home``
while it swaps them. Before its first move, a swap that keeps entries of the
earlier install writes their names to ``.apothem-carried-entries`` beside the
new tree. Every way out of a run puts things back and removes those folders,
except a forced kill or a power loss, which give it no chance to. The next
fetched install into the same APOTHEM_HOME, before it downloads, fetches or
swaps anything, stops on such folders: it names each one, says what it holds
(the earlier install, the new source and every entry already moved into it
from APOTHEM_HOME, the user's own files included), says how to put things
back, and changes nothing. Folders made for another APOTHEM_HOME in the same
folder are left alone (a run on that home may be using them); folders with
the earlier names, which say nothing about their home, are reported with a
note. When APOTHEM_HOME itself is missing, the folders it may have been set
aside in are named too. A local tree (``APOTHEM_SOURCE``) is run where it is,
leaves APOTHEM_HOME alone, and is not stopped.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from tests.integration.test_installer_cwd_isolation import (
    _env,
    _fake_checkout,
)
from tests.integration.test_installer_cwd_isolation import _run as _run_local
from tests.integration.test_installer_release_mode import (
    ARCHIVE_ROOT,
    SOURCE_MANIFEST,
    _cosign_args,
    _release,
    _run,
    _seed_earlier_install,
    _snapshot,
    _stub_cosign,
    _stub_mv,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "installer" / "install.sh"
CARRY_LIST = ".apothem-carried-entries"
LEAF = "apothem-home"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None
    or shutil.which("curl") is None
    or sys.platform == "win32",
    reason="exercises the POSIX install.sh; install.ps1 is the Windows path",
)


def _plant(path: Path, files: dict[str, str]) -> Path:
    """Make the folder PATH holding FILES (relative path: text; a path
    ending in "/" is an empty folder)."""
    path.mkdir(parents=True)
    for rel, text in files.items():
        target = path / rel
        if rel.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return path


def _report(home: Path, *lines: str) -> str:
    """The message install.sh prints for leftovers, with LINES naming them."""
    return "\n".join(
        [
            "  ✗ An earlier run was stopped part-way and left these folders "
            f"beside {home}:",
            *(f"    {line}" for line in lines),
            f"    Nothing was changed. If {home} is missing, move the earlier "
            "install back to it first. Then move every entry listed above as "
            f"moved from {home} back into it, remove the folders listed above, "
            "and re-run.",
        ]
    )


def _older(line: str, parent: Path) -> str:
    """LINE with the note an earlier-name folder gets."""
    return (
        f"{line} (made by an earlier installer that did not record which home "
        f"it was for, so it may belong to any Apothem home in {parent}: check "
        "what it holds before you move or remove it)"
    )


def _tree(*roots: Path) -> dict[str, dict[str, bytes | str]]:
    return {str(root): _snapshot(root) for root in roots}


@pytest.mark.parametrize("dry_run", [False, True], ids=["install", "dry-run"])
def test_folders_left_by_a_stopped_run_stop_the_next_install(
    tmp_path: Path, dry_run: bool
) -> None:
    """An earlier install, the tree a stopped swap set aside, a new source
    with entries already moved into it (named by its carry list), and an
    empty staging folder: the install names each folder and what it holds,
    sorted by name, then stops before the tag check or any download, and
    nothing is moved or removed. A dry run stops the same way."""
    home = tmp_path / LEAF
    _seed_earlier_install(home)
    old = _plant(
        tmp_path / f".apothem-old.{LEAF}.Ab12Cd",
        {"home/src/apothem/__init__.py": "", "home/pyproject.toml": "[project]\n"},
    )
    extract = _plant(
        tmp_path / f".apothem-extract.{LEAF}.Ef34Gh",
        {
            CARRY_LIST: "backups\nnotes.txt\nstate\nvenv-gone\n",
            "apothem-v9.9.9/src/apothem/__init__.py": "",
            "apothem-v9.9.9/backups/claude-code/set.json": "{}\n",
            "apothem-v9.9.9/state/ledger.json": "{}\n",
            "apothem-v9.9.9/notes.txt": "mine\n",
        },
    )
    clone = _plant(tmp_path / f".apothem-clone.{LEAF}.Ij56Kl", {})
    before = _tree(home, old, extract, clone)
    base = _release(tmp_path)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir, yes=True, dry_run=dry_run)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        _report(
            home,
            f"{clone}: empty",
            f"{extract}: the new source that was being installed, in "
            f"{extract}/apothem-v9.9.9, with these entries moved into it from "
            f"{home}: backups, notes.txt, state",
            f"{old}: the earlier install that was being replaced, in {old}/home",
        )
        in result.stderr
    ), combined
    assert "carries a valid signature" not in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert _tree(home, old, extract, clone) == before, combined
    assert not (tmp_path / f"{LEAF}.lock").exists(), combined


def test_folders_with_the_earlier_names_are_reported_with_a_note(
    tmp_path: Path,
) -> None:
    """Folders an earlier installer made (no home name in them, no carry
    list) are reported after this home's own, with a note that they may
    belong to any Apothem home there. An archive staging tree's carried
    entries are those its source manifest does not name, user files
    included; a clone staging tree names the engine data it holds."""
    home = tmp_path / LEAF
    _seed_earlier_install(home)
    extract = _plant(
        tmp_path / ".apothem-extract.Qr90St",
        {
            f"{ARCHIVE_ROOT}/{SOURCE_MANIFEST}": (
                f"{SOURCE_MANIFEST}\npyproject.toml\nsrc\n"
            ),
            f"{ARCHIVE_ROOT}/pyproject.toml": "[project]\n",
            f"{ARCHIVE_ROOT}/src/apothem/__init__.py": "",
            f"{ARCHIVE_ROOT}/backups/set.json": "{}\n",
            f"{ARCHIVE_ROOT}/.env": "KEY=1\n",
            f"{ARCHIVE_ROOT}/my-notes/todo.txt": "todo\n",
        },
    )
    clone = _plant(
        tmp_path / ".apothem-clone.Uv12Wx",
        {
            "apothem/src/apothem/__init__.py": "",
            "apothem/state/ledger.json": "{}\n",
            "apothem/plans/plan.md": "# plan\n",
        },
    )
    mine = _plant(tmp_path / f".apothem-old.{LEAF}.Zz00Zz", {})
    before = _tree(home, extract, clone, mine)
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        _report(
            home,
            f"{mine}: empty",
            _older(
                f"{clone}: the new source that was being installed, in "
                f"{clone}/apothem, with these entries moved into it from {home}: "
                "plans, state",
                tmp_path,
            ),
            _older(
                f"{extract}: the new source that was being installed, in "
                f"{extract}/{ARCHIVE_ROOT}, with these entries moved into it "
                f"from {home}: .env, backups, my-notes",
                tmp_path,
            ),
        )
        in result.stderr
    ), combined
    assert _tree(home, extract, clone, mine) == before, combined


def test_another_homes_folders_and_non_folders_do_not_stop_the_install(
    tmp_path: Path,
) -> None:
    """The lock is per APOTHEM_HOME, so another run may be using the staging
    folders of another home in the same folder: they are left alone, as are
    a file and a symbolic link with a staging folder's name. The install
    goes ahead and none of them changes."""
    home = tmp_path / LEAF
    _seed_earlier_install(home)
    theirs = [
        _plant(
            tmp_path / ".apothem-extract.other-home.Ab12Cd",
            {"apothem-v9.9.9/backups/set.json": "{}\n"},
        ),
        # A home named apothem-home.x: its leaf has a dot.
        _plant(tmp_path / f".apothem-old.{LEAF}.x.Cd34Ef", {"home/a.txt": "a\n"}),
        # A home whose name is a prefix of this one's.
        _plant(tmp_path / ".apothem-clone.apothem.Gh56Ij", {"apothem/a.txt": "a\n"}),
    ]
    target = _plant(tmp_path / "elsewhere", {"apothem-v9.9.9/a.txt": "a\n"})
    (tmp_path / f".apothem-old.{LEAF}.Fi1e00").write_text("a file\n", encoding="utf-8")
    (tmp_path / f".apothem-extract.{LEAF}.L1nk00").symlink_to(target)
    before = _tree(*theirs, target)
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True)

    combined = result.stdout + result.stderr
    assert "stopped part-way" not in combined, combined
    assert f"Source ready at {home} (release archive v9.9.9)" in combined, combined
    assert _tree(*theirs, target) == before, combined
    assert (tmp_path / f".apothem-old.{LEAF}.Fi1e00").is_file(), combined
    assert (tmp_path / f".apothem-extract.{LEAF}.L1nk00").is_symlink(), combined


def test_a_missing_apothem_home_also_names_where_it_was_set_aside(
    tmp_path: Path,
) -> None:
    """When APOTHEM_HOME itself is missing (the run was stopped between
    moving it aside and moving the new tree in), the message also names the
    folders it may have been set aside in: <aside>/<leaf> when the earlier
    folder sits inside one, <aside> itself for the earlier layout that held
    its contents directly. A folder whose name only starts the same way is
    not one of them."""
    home = tmp_path / LEAF
    old = _plant(
        tmp_path / f".apothem-old.{LEAF}.Mn78Op",
        {"home/src/apothem/__init__.py": "", "home/pyproject.toml": "[project]\n"},
    )
    extract = _plant(
        tmp_path / f".apothem-extract.{LEAF}.Qr90St",
        {"apothem-v9.9.9/src/apothem/__init__.py": ""},
    )
    nested = _plant(
        tmp_path / f"{LEAF}.before-apothem-20261101000000",
        {f"{LEAF}/notes.txt": "mine\n"},
    )
    flat = _plant(
        tmp_path / f"{LEAF}.before-apothem-20261001120000-4242",
        {"notes.txt": "mine\n"},
    )
    unrelated = _plant(tmp_path / f"{LEAF}.before-apothem-notes", {"a.txt": "a\n"})
    before = _tree(old, extract, nested, flat, unrelated)
    base = _release(tmp_path)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir, yes=True)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        _report(
            home,
            f"{extract}: the new source that was being installed, in "
            f"{extract}/apothem-v9.9.9",
            f"{old}: the earlier install that was being replaced, in {old}/home",
            f"{flat}: the earlier contents of {home}, moved aside, in {flat}",
            f"{nested}: the earlier contents of {home}, moved aside, in "
            f"{nested}/{LEAF}",
        )
        in result.stderr
    ), combined
    assert str(unrelated) not in combined, combined
    assert not home.exists(), combined
    assert _cosign_args(cosign_dir) is None, combined
    assert _tree(old, extract, nested, flat, unrelated) == before, combined


def test_a_leftover_holding_something_else_lists_what_is_in_it(
    tmp_path: Path,
) -> None:
    """A leftover folder that does not hold the usual layout is listed by
    every name in it, in byte order, and is left alone. The empty folder
    install.ps1 makes in its staging folder before renaming it is left out
    of the description."""
    home = tmp_path / LEAF
    _seed_earlier_install(home)
    old = _plant(
        tmp_path / f".apothem-old.{LEAF}.Uv12Wx",
        {"a.txt": "a\n", "B.txt": "b\n", "_under": "u\n", ".hidden": "h\n"},
    )
    extract = _plant(
        tmp_path / f".apothem-extract.{LEAF}.Ps1Tmp",
        {"apothem-v9.9.9/a.txt": "a\n", f"aside.{'0123abcd' * 4}/": ""},
    )
    before = _tree(home, old, extract)
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        _report(
            home,
            f"{extract}: the new source that was being installed, in "
            f"{extract}/apothem-v9.9.9",
            f"{old}: files from that run (.hidden, B.txt, _under, a.txt)",
        )
        in result.stderr
    ), combined
    assert _tree(home, old, extract) == before, combined


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="root reads a folder whatever its mode",
)
def test_a_leftover_that_cannot_be_read_is_not_called_empty(tmp_path: Path) -> None:
    """A leftover folder the user cannot list (a run under another user
    made it) may hold the earlier install: it is reported as unreadable,
    never as empty."""
    home = tmp_path / LEAF
    _seed_earlier_install(home)
    old = _plant(tmp_path / f".apothem-old.{LEAF}.Ro0000", {"home/backups/a": "a\n"})
    base = _release(tmp_path)
    old.chmod(0)
    try:
        result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True)
    finally:
        old.chmod(0o755)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        _report(home, f"{old}: could not be read (check its owner and permissions)")
        in result.stderr
    ), combined
    assert (old / "home" / "backups" / "a").is_file(), combined


def test_a_forced_kill_mid_swap_names_every_entry_it_moved(tmp_path: Path) -> None:
    """A forced kill right after the earlier install was moved aside leaves
    its engine data and the user's own files in the new tree. The next
    install names every one of them (the carry list the swap wrote first),
    not only the engine data, so none is lost by removing the folders."""
    home = tmp_path / LEAF
    _seed_earlier_install(home)
    (home / ".env").write_text("KEY=1\n", encoding="utf-8")
    (home / "my-notes").mkdir()
    (home / "my-notes" / "todo.txt").write_text("todo\n", encoding="utf-8")
    base = _release(tmp_path)
    mv_dir = _stub_mv(tmp_path, [(str(home), "*/.apothem-old.*/home", "KILL")])

    killed = _run(
        tmp_path,
        base,
        cosign_dir=_stub_cosign(tmp_path),
        yes=True,
        path_first=[mv_dir],
    )

    assert killed.returncode != 0, killed.stdout + killed.stderr
    assert not home.exists(), killed.stdout + killed.stderr
    (extract,) = tmp_path.glob(f".apothem-extract.{LEAF}.*")
    (old,) = tmp_path.glob(f".apothem-old.{LEAF}.*")
    # The killed run could not let its lock go; the user removes it.
    shutil.rmtree(tmp_path / f"{LEAF}.lock")
    shutil.rmtree(mv_dir)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        _report(
            home,
            f"{extract}: the new source that was being installed, in "
            f"{extract}/{ARCHIVE_ROOT}, with these entries moved into it from "
            f"{home}: .env, backups, my-notes, plans, state",
            f"{old}: the earlier install that was being replaced, in {old}/home",
        )
        in result.stderr
    ), combined
    assert (extract / ARCHIVE_ROOT / "my-notes" / "todo.txt").is_file(), combined


def test_a_local_source_is_not_stopped_by_leftovers(tmp_path: Path) -> None:
    """A run from a local tree (APOTHEM_SOURCE) swaps nothing at
    APOTHEM_HOME, so folders left beside it neither stop it nor change."""
    old = _plant(
        tmp_path / ".apothem-old.Yz34Ab",
        {"home/src/apothem/__init__.py": ""},
    )
    before = _tree(old)
    checkout = _fake_checkout(tmp_path / "checkout")
    env = _env(tmp_path, APOTHEM_SOURCE=str(checkout))

    result = _run_local(["sh", str(INSTALLER)], cwd=tmp_path, env=env)

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert "stopped part-way" not in combined, combined
    assert _tree(old) == before, combined
