# SPDX-License-Identifier: MIT

"""One target check resolves each path once, and keeps nothing for the next.

``_validate_target_path`` asks about the same folders many times (the target,
the allowed root, the home, each folder between them). On Windows each
resolve opens a handle, and install-heavy runs spent about a sixth of their
time there. Within one check a path is now resolved once, and a path that a
resolve returned is not resolved again; the next check starts afresh, so a
folder swapped for a link between two writes is judged by what it is then.

Creating a symbolic link needs a privilege some Windows hosts lack, so there
the link is a junction, which the check also sees as a link.
"""

from __future__ import annotations

import collections
import shutil
import sys
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver_pathsafety as pathsafety


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = (tmp_path / "home").resolve()
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    return folder


def _link(link: Path, target: Path) -> None:
    """Make *link* lead to *target*: a symbolic link, or a junction on Windows."""
    target.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("this host cannot create a directory link")
        import _winapi

        _winapi.CreateJunction(str(target), str(link))


def _record_resolves(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Record each ``(spelling, result)`` of ``Path.resolve`` from now on, in order."""
    calls: list[tuple[str, str]] = []
    real_resolve = Path.resolve

    def resolve(self: Path, strict: bool = False) -> Path:
        found = real_resolve(self, strict=strict)
        calls.append((str(self), str(found)))
        return found

    monkeypatch.setattr(Path, "resolve", resolve)
    return calls


def _check(target: Path, root: Path) -> pathsafety.MaterializationResult | None:
    return pathsafety._validate_target_path(
        target,
        allowed_root=pathsafety._allowed_write_root(root, None),
        operation="write",
        mutating=False,
    )


def test_a_check_resolves_each_path_once(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Spelled with "..", so no path is written the way a resolve returns it:
    # a resolved path asked about again must come from what the check kept.
    (home / "x").mkdir()
    root = home / "x" / ".." / ".tool"
    target = root / "skills" / "one" / "SKILL.md"
    target.parent.mkdir(parents=True)
    floor = pathsafety._allowed_write_root(root, None)
    calls = _record_resolves(monkeypatch)

    assert (
        pathsafety._validate_target_path(
            target, allowed_root=floor, operation="write", mutating=False
        )
        is None
    )

    assert calls, "the check resolved nothing"
    asked = collections.Counter(spelling for spelling, _found in calls)
    assert [spelling for spelling, count in asked.items() if count > 1] == []
    # Nor is a path an earlier resolve returned resolved again.
    again = [
        spelling
        for index, (spelling, _found) in enumerate(calls)
        if spelling in {found for _spelling, found in calls[:index]}
    ]
    assert again == []


def test_the_next_check_resolves_again(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = home / ".tool"
    target = root / "rules" / "a.md"
    target.parent.mkdir(parents=True)
    calls = _record_resolves(monkeypatch)

    assert _check(target, root) is None
    assert _check(target, root) is None

    assert [spelling for spelling, _found in calls].count(str(target)) == 2


def test_a_folder_swapped_for_a_link_out_between_checks_is_seen(
    home: Path, tmp_path: Path
) -> None:
    root = home / ".tool"
    target = root / "rules" / "a.md"
    target.parent.mkdir(parents=True)
    assert _check(target, root) is None

    shutil.rmtree(root / "rules")
    _link(root / "rules", tmp_path / "outside")
    refused = _check(target, root)

    # Resolved afresh, the target is outside the home: the escape refusal,
    # not the link refusal a check reusing the first answer would reach.
    assert refused is not None
    assert refused.message == "target escapes the allowed materialization root"
