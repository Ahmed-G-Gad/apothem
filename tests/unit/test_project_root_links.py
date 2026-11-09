# SPDX-License-Identifier: MIT

"""A project root the operator named is followed; a link inside it is refused.

The CLI resolves ``--project`` before any write, so a project folder that is
itself a link, even one that leads out of the home (a linked ``~/.config``
among them), is followed: the operator named that folder. The write guard
gives the Python API the same rule through the project boundary
(``_ProjectFloor``), which carries the project root as the caller spelled it:
the link at that spelling is followed, and every link inside the project root
is refused, including one that leads back to the project root in one hop or
two. A boundary built from the floor keeps only the stricter kind. A harness
root's boundary keeps the harness rule, where a link at the boundary that
leads out of the home is refused.

Creating a symbolic link needs a privilege some Windows hosts lack, so there
each link is a junction, which the guards also see as a link.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared import install_driver_pathsafety as pathsafety
from apothem.harnesses._shared.install_driver import MaterializationResult
from apothem.harnesses._shared.install_driver_sweep import stale_blocker
from apothem.harnesses._shared.install_driver_written import remove_written


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    for name in ("XDG_CONFIG_HOME", "CODEX_HOME", "OPENCODE_CONFIG_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    return folder


def _link(link: Path, target: Path) -> None:
    """Make *link* lead to *target*: a symbolic link, or a junction on Windows."""
    target.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("this host cannot create a directory link")
        import _winapi

        _winapi.CreateJunction(str(target), str(link))


def _check_project(project: Path, target: Path) -> MaterializationResult | None:
    return pathsafety._validate_target_path(
        target,
        allowed_root=pathsafety._allowed_write_root(None, project),
        operation="t",
    )


# -- the Python API -----------------------------------------------------------


def test_a_project_root_that_leads_out_of_the_home_is_followed(
    home: Path, tmp_path: Path
) -> None:
    _link(home / "proj", tmp_path / "outside" / "proj")
    project = home / "proj"

    assert _check_project(project, project / ".cursor" / "x.md") is None


@pytest.mark.parametrize("leads", ["out", "in"])
def test_a_linked_config_as_project_root_is_followed(
    home: Path, tmp_path: Path, leads: str
) -> None:
    where = tmp_path / "outside" / "config" if leads == "out" else home / "dots"
    _link(home / ".config", where)
    project = home / ".config"

    assert _check_project(project, project / "x.md") is None


def test_a_link_inside_the_project_root_is_refused(home: Path) -> None:
    project = home / "proj"
    _link(project / ".cursor", project / "real-cursor")

    error = _check_project(project, project / ".cursor" / "x.md")

    assert error is not None
    assert error.message.startswith("target path crosses a link")
    assert error.detail["symlink"] == str(project / ".cursor")


def test_a_link_inside_the_project_root_leading_back_to_it_is_refused(
    home: Path,
) -> None:
    # proj/.cursor resolves to the project root itself; it is still a link
    # inside the project, not the folder the operator named.
    project = home / "proj"
    project.mkdir()
    _link(project / ".cursor", project)

    error = _check_project(project, project / ".cursor" / "x.md")

    assert error is not None
    assert error.message.startswith("target path crosses a link")


def test_a_link_inside_a_linked_project_root_leading_out_is_refused(
    home: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside" / "proj"
    _link(home / "proj", outside)
    _link(outside / ".cursor", tmp_path / "elsewhere")
    project = home / "proj"

    error = _check_project(project, project / ".cursor" / "x.md")

    assert error is not None
    assert error.message == "target escapes the allowed materialization root"


def test_a_link_inside_a_linked_project_root_staying_inside_is_refused(
    home: Path, tmp_path: Path
) -> None:
    # The inner link stays inside the resolved project, so only the link
    # check, not the containment check, can refuse it.
    outside = tmp_path / "outside" / "proj"
    _link(home / "proj", outside)
    _link(outside / ".cursor", outside / "real")
    project = home / "proj"

    error = _check_project(project, project / ".cursor" / "x.md")

    assert error is not None
    assert error.message.startswith("target path crosses a link")
    assert error.detail["symlink"] == str(project / ".cursor")


@pytest.mark.parametrize(
    ("first", "second", "target"),
    [
        (".apothem", "support/cursor/hooks", ".apothem/support/cursor/hooks"),
        (".cursor", "rules", ".cursor/rules/apothem-rules.mdc"),
    ],
)
def test_a_two_hop_link_back_to_the_project_root_is_refused(
    home: Path, tmp_path: Path, first: str, second: str, target: str
) -> None:
    # proj/<first> leads out, and a link out there leads back to proj: every
    # folder on the way resolves inside the project, so only a walk that
    # stops at the project root by name finds the inner link.
    project = home / "proj"
    project.mkdir()
    hop = tmp_path / "outside" / "x"
    _link(project / first, hop)
    _link(hop / second, project)

    error = _check_project(project, project / target)

    assert error is not None
    assert error.message.startswith("target path crosses a link")
    assert error.detail["symlink"] == str(project / first / second)


def test_a_project_root_that_leads_to_its_own_parent_is_followed(
    home: Path,
) -> None:
    parent = home / "w"
    parent.mkdir()
    _link(parent / "proj", parent)
    project = parent / "proj"

    assert _check_project(project, project / ".cursor" / "x.md") is None


def test_a_link_inside_a_project_rooted_at_the_home_is_refused(home: Path) -> None:
    # The user-level exemption is for the home's own writes, not for a
    # project that happens to be rooted at the home.
    _link(home / ".agents", home / "dots")
    target = home / ".agents" / "skills" / "x" / "SKILL.md"

    error = _check_project(home, target)
    user_level = pathsafety._validate_target_path(
        target, allowed_root=pathsafety._normalized(home), operation="t"
    )

    assert error is not None
    assert error.detail["symlink"] == str(home / ".agents")
    assert user_level is None


def test_a_boundary_built_from_a_project_floor_follows_no_link(home: Path) -> None:
    project = home / "proj"
    _link(project / ".cursor", project / "real")
    floor = pathsafety._allowed_write_root(None, project)

    error = pathsafety._validate_target_path(
        project / ".cursor" / "x.md", allowed_root=floor / ".cursor", operation="t"
    )

    assert error is not None
    assert error.message.startswith("target path crosses a link")
    assert error.detail["symlink"] == str(project / ".cursor")


def test_only_the_floor_itself_carries_the_named_folder(home: Path) -> None:
    project = home / "proj"
    floor = pathsafety._allowed_write_root(None, project)

    assert pathsafety._named_floor(floor) == project
    assert pathsafety._named_floor(floor / "sub") is None
    assert pathsafety._named_floor(floor.parent) is None
    assert pathsafety._named_floor(pathsafety._normalized(floor)) is None
    assert pathsafety._named_floor(project) is None


@pytest.mark.parametrize("name", ["opencode", "codex"])
def test_a_harness_root_below_a_linked_config_is_still_followed(
    home: Path, name: str
) -> None:
    _link(home / ".config", home / "dots" / "config")
    root = home / ".config" / name

    error = pathsafety._validate_target_path(
        root / "x.md",
        allowed_root=pathsafety._allowed_write_root(root, None),
        operation="t",
    )

    assert error is None


def test_a_harness_boundary_that_leads_out_of_the_home_is_refused(
    home: Path, tmp_path: Path
) -> None:
    _link(home / "a", tmp_path / "outside" / "a")
    root = home / "a" / "codex"

    error = pathsafety._validate_target_path(
        root / "x.md",
        allowed_root=pathsafety._allowed_write_root(root, None),
        operation="t",
    )

    assert error is not None
    assert error.detail["symlink"] == str(home / "a")


def test_a_project_floor_keeps_its_kind_through_resolve(home: Path) -> None:
    floor = pathsafety._allowed_write_root(None, home / "proj")

    assert isinstance(floor, pathsafety._ProjectFloor)
    assert isinstance(pathsafety._normalized(floor), pathsafety._ProjectFloor)
    harness_floor = pathsafety._allowed_write_root(home / "proj", None)
    assert not isinstance(harness_floor, pathsafety._ProjectFloor)
    assert floor == (home / "proj").resolve()


def test_the_write_boundary_keeps_the_kind_it_is_given(home: Path) -> None:
    floor = pathsafety._allowed_write_root(None, home / "proj")
    plain = home / "proj"

    assert pathsafety._write_boundary(floor, plain) is floor
    assert pathsafety._write_boundary(None, floor) is floor
    assert pathsafety._write_boundary(None, plain) is plain


def test_a_boundary_without_a_kind_refuses_a_linked_project_root(
    home: Path, tmp_path: Path
) -> None:
    # A writer given no allowed_root checks its install root as a harness
    # boundary: it refuses the linked project root the project rule follows.
    _link(home / "proj", tmp_path / "outside" / "proj")
    project = home / "proj"
    target = project / "x.md"
    plain = pathsafety._write_boundary(None, project)

    refused = pathsafety._validate_target_path(
        target, allowed_root=plain, operation="t"
    )
    followed = pathsafety._validate_target_path(
        target,
        allowed_root=pathsafety._write_boundary(
            pathsafety._allowed_write_root(None, project), project
        ),
        operation="t",
    )

    assert refused is not None
    assert followed is None


def test_the_link_lookups_read_the_project_floor_they_are_given(
    home: Path, tmp_path: Path
) -> None:
    # The checks that tell a link refusal from another one (uninstall, the
    # stale sweep) pass the boundary object: they follow the folder the
    # operator named, as the write guard does, and still find a link inside.
    _link(home / "proj", tmp_path / "outside" / "proj")
    project = home / "proj"
    floor = pathsafety._allowed_write_root(None, project)
    target = project / ".cursor" / "x.md"
    target.parent.mkdir(parents=True)

    assert pathsafety._unsafe_symlink(target, floor) is None
    assert pathsafety._link_below_floor(target, floor) is None

    _link(project / "inner", tmp_path / "elsewhere")
    inner = project / "inner" / "x.md"
    assert pathsafety._unsafe_symlink(inner, floor) == project / "inner"
    assert pathsafety._link_below_floor(inner, floor) == project / "inner"


def test_a_boundary_derived_from_the_floor_does_not_follow_the_named_link(
    home: Path, tmp_path: Path
) -> None:
    # A derived path keeps the stricter kind but not the spelling, which is
    # why the callers pass the boundary object and not a resolved copy.
    _link(home / "proj", tmp_path / "outside" / "proj")
    project = home / "proj"
    floor = pathsafety._allowed_write_root(None, project)
    target = project / ".cursor" / "x.md"
    target.parent.mkdir(parents=True)

    assert pathsafety._unsafe_symlink(target, pathsafety._normalized(floor)) == project


def test_the_sweep_and_uninstall_checks_follow_the_named_project_folder(
    home: Path, tmp_path: Path
) -> None:
    # The stale sweep and the removal of written files each ask whether a
    # link caused a refusal. With the folder the operator named as a link,
    # neither of them reports that link.
    _link(home / "proj", tmp_path / "outside" / "proj")
    project = home / "proj"
    floor = pathsafety._allowed_write_root(None, project)
    rules = project / ".cursor" / "rules"
    rules.mkdir(parents=True)
    (rules / "a.md").write_text("x\n", encoding="utf-8")
    live = frozenset({pathsafety._normalized(rules)})

    kept = stale_blocker(project / ".cursor", live, floor)
    written = remove_written(
        rules / "a.md",
        recorded=None,
        install_root=project,
        harness_name="t",
        allowed_root=floor,
    )

    assert kept is not None
    assert kept.outcome == "unchanged", kept.message
    assert written is not None
    assert "symlink" not in written.detail, written.message


def test_the_sweep_and_uninstall_checks_name_a_link_inside_the_project(
    home: Path, tmp_path: Path
) -> None:
    project = home / "proj"
    project.mkdir()
    floor = pathsafety._allowed_write_root(None, project)
    _link(project / ".cursor", tmp_path / "elsewhere")
    rules = project / ".cursor" / "rules"
    rules.mkdir(parents=True)
    (rules / "a.md").write_text("x\n", encoding="utf-8")
    live = frozenset({pathsafety._normalized(rules)})

    kept = stale_blocker(project / ".cursor", live, floor)
    written = remove_written(
        rules / "a.md",
        recorded=None,
        install_root=project,
        harness_name="t",
        allowed_root=floor,
    )

    assert kept is not None
    assert kept.outcome == "warning", kept.message
    assert str(project / ".cursor") in kept.message
    assert written is not None
    assert written.outcome == "warning", written.message
    assert written.detail["symlink"] == str(project / ".cursor")
    assert (rules / "a.md").exists()


# -- the CLI ------------------------------------------------------------------


def _profile(tmp_path: Path) -> Path:
    profile = tmp_path / "prof" / "profile.yaml"
    made = CliRunner().invoke(main, ["profile", "init", "--profile", str(profile)])
    assert made.exit_code == 0, made.output
    return profile


def test_install_follows_a_project_folder_that_leads_out_of_the_home(
    home: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside" / "proj"
    _link(home / "proj", outside)
    profile = _profile(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "install",
            "--harness",
            "cursor",
            "--project",
            str(home / "proj"),
            "--profile",
            str(profile),
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (outside / ".cursor" / "rules" / "apothem-rules.mdc").is_file()


def _install_cursor(project: Path, profile: Path) -> Result:
    return CliRunner().invoke(
        main,
        [
            "install",
            "--harness",
            "cursor",
            "--project",
            str(project),
            "--profile",
            str(profile),
            "--yes",
        ],
    )


def test_install_refuses_a_two_hop_link_back_to_the_project_folder(
    home: Path, tmp_path: Path
) -> None:
    project = home / "proj"
    project.mkdir()
    (project / "dispatch.py").write_text("mine\n", encoding="utf-8")
    hop = tmp_path / "outside" / "x"
    _link(project / ".apothem", hop)
    _link(hop / "support" / "cursor" / "hooks", project)
    profile = _profile(tmp_path)

    result = _install_cursor(project, profile)

    assert result.exit_code != 0, result.output
    assert "target path crosses a link" in result.output
    assert (project / "dispatch.py").read_text(encoding="utf-8") == "mine\n"
    assert sorted(item.name for item in project.iterdir()) == [
        ".apothem",
        "dispatch.py",
    ]


def test_install_follows_a_project_folder_that_leads_to_its_parent(
    home: Path, tmp_path: Path
) -> None:
    parent = home / "w"
    parent.mkdir()
    _link(parent / "proj", parent)
    profile = _profile(tmp_path)

    result = _install_cursor(parent / "proj", profile)

    assert result.exit_code == 0, result.output
    assert (parent / ".cursor" / "rules" / "apothem-rules.mdc").is_file()


def test_install_refuses_a_link_inside_the_project_folder(
    home: Path, tmp_path: Path
) -> None:
    project = home / "proj"
    elsewhere = tmp_path / "outside" / "cursor"
    _link(project / ".cursor", elsewhere)
    profile = _profile(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "install",
            "--harness",
            "cursor",
            "--project",
            str(project),
            "--profile",
            str(profile),
            "--yes",
        ],
    )

    assert result.exit_code != 0, result.output
    assert list(elsewhere.iterdir()) == []
