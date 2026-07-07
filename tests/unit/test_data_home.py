# SPDX-License-Identifier: MIT

"""Unit tests for the shared data-home resolver.

The data home is collapsed across harnesses: every target sharing a base
resolves to ONE shared ``<base>/.apothem`` home with ``plans``, ``memory``,
``contexts``, and ``learning`` children — never a per-harness subtree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.lib.data_home import (
    DataHome,
    DataHomeError,
    plans_root,
    resolve_shared_data_home,
    resolve_workspace_base,
)
from apothem.lib.profile import WorkspaceConfig


def test_all_callers_resolve_to_one_shared_home(tmp_path: Path) -> None:
    # Arrange / Act: resolve the shared home twice under the same base.
    first = resolve_shared_data_home(base=tmp_path)
    second = resolve_shared_data_home(base=tmp_path)

    # Assert: the home is shared — both resolutions point at the same surfaces,
    # so a write under one harness is visible to every other harness.
    assert first.root == second.root
    assert first.memory == second.memory
    assert first.contexts == second.contexts
    assert first.learning == second.learning
    assert first.plans == second.plans


def test_home_layout_is_apothem_owned_subtree(tmp_path: Path) -> None:
    # Act.
    home = resolve_shared_data_home(base=tmp_path)

    # Assert: <base>/.apothem/{plans,memory,contexts,learning} with no harness
    # segment in the path.
    assert home.root == tmp_path / ".apothem"
    assert home.plans == home.root / "plans"
    assert home.memory == home.root / "memory"
    assert home.contexts == home.root / "contexts"
    assert home.learning == home.root / "learning"


def test_home_honors_custom_directory_name(tmp_path: Path) -> None:
    # Act: a profile-driven working-directory name slots into the path.
    home = resolve_shared_data_home(base=tmp_path, directory_name=".workdir")

    # Assert.
    assert home.root == tmp_path / ".workdir"
    assert home.memory == tmp_path / ".workdir" / "memory"


def test_resolve_does_not_create_directories(tmp_path: Path) -> None:
    # Act.
    home = resolve_shared_data_home(base=tmp_path)

    # Assert: resolution is pure; nothing on disk yet.
    assert not home.root.exists()


def test_ensure_creates_the_tree_idempotently(tmp_path: Path) -> None:
    # Act: ensure twice.
    home = resolve_shared_data_home(base=tmp_path).ensure()
    again = home.ensure()

    # Assert: directories exist; ensure returns the same home; no error on re-run.
    assert again is home
    for directory in (
        home.root,
        home.plans,
        home.memory,
        home.contexts,
        home.learning,
    ):
        assert directory.is_dir()


@pytest.mark.parametrize(
    "bad_name",
    # The colon cases (a Windows drive specifier) would otherwise reset pathlib
    # to a drive root and escape the base directory entirely.
    ["", "   ", "a/b", "a\\b", ".", "..", "C:", "D:rel", "a:b"],
)
def test_invalid_directory_name_raises(bad_name: str, tmp_path: Path) -> None:
    # Act / Assert.
    with pytest.raises(DataHomeError):
        resolve_shared_data_home(base=tmp_path, directory_name=bad_name)


def test_data_home_is_frozen(tmp_path: Path) -> None:
    # Assert: the value type is immutable.
    home = resolve_shared_data_home(base=tmp_path)
    assert isinstance(home, DataHome)
    with pytest.raises(AttributeError):
        home.root = tmp_path  # type: ignore[misc]


def test_resolve_workspace_base_project_local_returns_project_root(
    tmp_path: Path,
) -> None:
    # Arrange: a project root distinct from the user home.
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    workspace = WorkspaceConfig()  # scope defaults to project-local.

    # Act.
    base = resolve_workspace_base(
        workspace=workspace, project_root=project_root, home=home
    )

    # Assert: project-local scope roots at the project root.
    assert base == project_root


def test_resolve_workspace_base_user_home_returns_home(tmp_path: Path) -> None:
    # Arrange.
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    workspace = WorkspaceConfig(scope="user-home")

    # Act.
    base = resolve_workspace_base(
        workspace=workspace, project_root=project_root, home=home
    )

    # Assert: user-home scope roots at the user home.
    assert base == home


def test_resolve_workspace_base_rejects_unknown_scope(tmp_path: Path) -> None:
    # Arrange: a config carrying a scope the resolver does not understand.
    workspace = WorkspaceConfig(scope="elsewhere")

    # Act / Assert.
    with pytest.raises(DataHomeError):
        resolve_workspace_base(
            workspace=workspace, project_root=tmp_path, home=tmp_path
        )


def test_plans_root_default_directory_name(tmp_path: Path) -> None:
    # Act.
    plans = plans_root(base=tmp_path)

    # Assert: <base>/.apothem/plans with the default working-directory name.
    assert plans == tmp_path / ".apothem" / "plans"


def test_plans_root_custom_directory_name(tmp_path: Path) -> None:
    # Act.
    plans = plans_root(base=tmp_path, directory_name=".workdir")

    # Assert: the custom name slots into the path.
    assert plans == tmp_path / ".workdir" / "plans"


def test_plans_root_matches_shared_home_plans_child(tmp_path: Path) -> None:
    # Assert: the standalone plans helper and the shared home agree on plans.
    assert plans_root(base=tmp_path) == resolve_shared_data_home(base=tmp_path).plans


def test_plans_root_does_not_create_directories(tmp_path: Path) -> None:
    # Act.
    plans = plans_root(base=tmp_path)

    # Assert: resolution is pure; nothing on disk.
    assert not plans.exists()


@pytest.mark.parametrize(
    "bad_name",
    ["", "   ", "a/b", "a\\b", ".", "..", "C:", "D:rel", "a:b"],
)
def test_plans_root_rejects_invalid_directory_name(
    bad_name: str, tmp_path: Path
) -> None:
    # Act / Assert.
    with pytest.raises(DataHomeError):
        plans_root(base=tmp_path, directory_name=bad_name)


def test_plans_root_is_apothem_plans_when_present(tmp_path: Path) -> None:
    # Arrange: the canonical <base>/.apothem/plans layout exists on disk.
    new_layout = tmp_path / ".apothem" / "plans"
    new_layout.mkdir(parents=True)

    # Act.
    resolved = plans_root(base=tmp_path)

    # Assert: the sole canonical plans location is <base>/.apothem/plans.
    assert resolved == new_layout


def test_plans_root_is_apothem_plans_when_absent(tmp_path: Path) -> None:
    # Act: nothing exists on disk; resolution is pure path math.
    resolved = plans_root(base=tmp_path)

    # Assert: the sole canonical location, computed without creating it. A
    # legacy <base>/.plans is never returned — operators upgrade it via
    # `apothem migrate-workspace`.
    assert resolved == tmp_path / ".apothem" / "plans"
    assert not resolved.exists()


def test_plans_root_ignores_legacy_dot_plans(tmp_path: Path) -> None:
    # Arrange: only a legacy <base>/.plans exists; the canonical tree is absent.
    legacy = tmp_path / ".plans"
    legacy.mkdir()

    # Act.
    resolved = plans_root(base=tmp_path)

    # Assert: the legacy tree is never the resolved canonical location.
    assert resolved == tmp_path / ".apothem" / "plans"
    assert resolved != legacy


def test_plans_root_honors_custom_directory_name(tmp_path: Path) -> None:
    # Arrange: the canonical layout under a custom name exists.
    new_layout = tmp_path / ".workdir" / "plans"
    new_layout.mkdir(parents=True)

    # Act.
    resolved = plans_root(base=tmp_path, directory_name=".workdir")

    # Assert.
    assert resolved == new_layout
