# SPDX-License-Identifier: MIT

"""Folders a stopped install left beside APOTHEM_HOME stop the next one.

install.sh builds the new source in a folder beside APOTHEM_HOME
(``.apothem-extract.*`` for a release archive, ``.apothem-clone.*`` for a
clone) and moves the earlier tree to ``.apothem-old.*/home`` while it swaps
them. Every way out of a run puts things back and removes those folders,
except a forced kill or a power loss, which give it no chance to. The next
install, before it downloads, fetches or swaps anything, stops on such
folders: it names each one, says what it holds (the earlier install, the new
source and any engine data already moved into it), says how to put the data
back, and changes nothing. When APOTHEM_HOME itself is missing, the folders
it may have been set aside in are named too. A local tree
(``APOTHEM_SOURCE``) is run where it is, leaves APOTHEM_HOME alone, and is
not stopped.
"""

from __future__ import annotations

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
    _cosign_args,
    _release,
    _run,
    _seed_earlier_install,
    _snapshot,
    _stub_cosign,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "installer" / "install.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None
    or shutil.which("curl") is None
    or sys.platform == "win32",
    reason="exercises the POSIX install.sh; install.ps1 is the Windows path",
)


def _plant(path: Path, files: dict[str, str]) -> Path:
    """Make the folder PATH holding FILES (relative path: text)."""
    path.mkdir(parents=True)
    for rel, text in files.items():
        target = path / rel
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
            "install back to it first. Then move any engine data listed above "
            f"back into {home}, remove these folders, and re-run.",
        ]
    )


def _tree(*roots: Path) -> dict[str, dict[str, bytes | str]]:
    return {str(root): _snapshot(root) for root in roots}


@pytest.mark.parametrize("dry_run", [False, True], ids=["install", "dry-run"])
def test_folders_left_by_a_stopped_run_stop_the_next_install(
    tmp_path: Path, dry_run: bool
) -> None:
    """An earlier install, the tree a stopped swap set aside, a new source
    with engine data already moved into it, and an empty staging folder:
    the install names each folder and what it holds, then stops before the
    tag check or any download, and nothing is moved or removed. A dry run
    stops the same way."""
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    old = _plant(
        tmp_path / ".apothem-old.Ab12Cd",
        {"home/src/apothem/__init__.py": "", "home/pyproject.toml": "[project]\n"},
    )
    extract = _plant(
        tmp_path / ".apothem-extract.Ef34Gh",
        {
            "apothem-v9.9.9/src/apothem/__init__.py": "",
            "apothem-v9.9.9/backups/claude-code/set.json": "{}\n",
            "apothem-v9.9.9/state/ledger.json": "{}\n",
        },
    )
    clone = _plant(tmp_path / ".apothem-clone.Ij56Kl", {})
    before = _tree(home, old, extract, clone)
    base = _release(tmp_path)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir, yes=True, dry_run=dry_run)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        _report(
            home,
            f"{old}: the earlier install that was being replaced, in {old}/home",
            f"{extract}: the new source that was being installed, in "
            f"{extract}/apothem-v9.9.9, with engine data moved into it: backups "
            "state",
            f"{clone}: empty",
        )
        in result.stderr
    ), combined
    assert "carries a valid signature" not in combined, combined
    assert _cosign_args(cosign_dir) is None, combined
    assert _tree(home, old, extract, clone) == before, combined
    left = sorted(p.name for p in tmp_path.glob(".apothem-*"))
    assert left == [
        ".apothem-clone.Ij56Kl",
        ".apothem-extract.Ef34Gh",
        ".apothem-old.Ab12Cd",
    ]
    assert not (tmp_path / "apothem-home.lock").exists(), combined


def test_a_missing_apothem_home_also_names_where_it_was_set_aside(
    tmp_path: Path,
) -> None:
    """When APOTHEM_HOME itself is missing (the run was stopped between
    moving it aside and moving the new tree in), the message also names
    the folders it may have been set aside in."""
    home = tmp_path / "apothem-home"
    old = _plant(
        tmp_path / ".apothem-old.Mn78Op",
        {"home/src/apothem/__init__.py": "", "home/pyproject.toml": "[project]\n"},
    )
    extract = _plant(
        tmp_path / ".apothem-extract.Qr90St",
        {"apothem-v9.9.9/src/apothem/__init__.py": ""},
    )
    aside = _plant(
        tmp_path / "apothem-home.before-apothem-20261101000000",
        {"apothem-home/notes.txt": "mine\n"},
    )
    before = _tree(old, extract, aside)
    base = _release(tmp_path)
    cosign_dir = _stub_cosign(tmp_path)

    result = _run(tmp_path, base, cosign_dir=cosign_dir, yes=True)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        _report(
            home,
            f"{old}: the earlier install that was being replaced, in {old}/home",
            f"{extract}: the new source that was being installed, in "
            f"{extract}/apothem-v9.9.9",
            f"{aside}: the earlier contents of {home}, moved aside, in "
            f"{aside}/apothem-home",
        )
        in result.stderr
    ), combined
    assert not home.exists(), combined
    assert _cosign_args(cosign_dir) is None, combined
    assert _tree(old, extract, aside) == before, combined


def test_a_leftover_holding_something_else_lists_what_is_in_it(
    tmp_path: Path,
) -> None:
    """A leftover folder that does not hold the usual layout is listed by
    the names in it, and is left alone."""
    home = tmp_path / "apothem-home"
    _seed_earlier_install(home)
    old = _plant(tmp_path / ".apothem-old.Uv12Wx", {"a.txt": "a\n", "b.txt": "b\n"})
    before = _tree(home, old)
    base = _release(tmp_path)

    result = _run(tmp_path, base, cosign_dir=_stub_cosign(tmp_path), yes=True)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert _report(home, f"{old}: files from that run (a.txt b.txt)") in (
        result.stderr
    ), combined
    assert _tree(home, old) == before, combined


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
