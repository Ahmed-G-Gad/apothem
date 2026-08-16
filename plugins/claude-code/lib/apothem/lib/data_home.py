# SPDX-License-Identifier: MIT

"""Shared data-home resolution for the memory, contexts, learning, and plans surfaces.

Every base directory receives ONE Apothem-owned working directory shared across
every installation target. The operator's durable memory records, injectable
context fragments, and captured learning signals live in that single home — a
write under one harness is visible to every other harness sharing the base. This
module derives the home deterministically from a base directory and the
working-directory name, so two harnesses installing into the same base resolve
to the same home rather than per-harness silos.

The data home is an Apothem-owned subtree (``<base>/.apothem/``) beneath the
base directory. Memory, contexts, learning, and plans each get a dedicated
child directory so the surfaces never collide.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apothem.lib.profile import WorkspaceConfig

#: The Apothem-owned subtree name placed under the base directory.
_APOTHEM_SUBTREE: str = ".apothem"

#: The plans child directory name beneath the shared working directory.
_PLANS_CHILD: str = "plans"


class DataHomeError(ValueError):
    """Raised when a data home cannot be resolved from the given inputs."""


@dataclass(frozen=True)
class DataHome:
    """The shared on-disk home for an Apothem base directory's data surfaces.

    One home is shared across every installation target rooted at the same
    base; the surfaces are never per-harness.

    Attributes:
        root: The Apothem-owned root directory for the shared data.
        plans: The directory holding plan suites.
        memory: The directory holding durable memory records.
        contexts: The directory holding injectable context fragments.
        learning: The directory holding captured learning signals.
    """

    root: Path
    plans: Path
    memory: Path
    contexts: Path
    learning: Path

    @classmethod
    def from_root(cls, root: Path) -> DataHome:
        """Build a :class:`DataHome` from its Apothem-owned *root* directory.

        The four surface children hang off *root* with fixed names —
        ``plans``, ``memory``, ``contexts``, ``learning`` — so every layout
        that constructs a data home from a known root (the shared home and the
        legacy per-harness home) shares one child-name source of truth. The
        directories are not created; call :meth:`ensure` to materialize them.
        """
        return cls(
            root=root,
            plans=root / _PLANS_CHILD,
            memory=root / "memory",
            contexts=root / "contexts",
            learning=root / "learning",
        )

    def ensure(self) -> DataHome:
        """Create the data-home directory tree if absent and return self.

        Creating an existing tree is a no-op, so the call is idempotent and
        never disturbs records already written under any of the surfaces. The
        ``plans`` child is included so the shared working directory carries its
        plan-suite home alongside the data stores.

        Returns:
            This :class:`DataHome`, for call chaining.
        """
        for directory in (
            self.root,
            self.plans,
            self.memory,
            self.contexts,
            self.learning,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return self


def resolve_shared_data_home(
    *, base: Path, directory_name: str = ".apothem"
) -> DataHome:
    """Resolve the SHARED Apothem working directory beneath *base*.

    All harnesses installing into the same *base* resolve to the SAME home:
    memory, contexts, learning, and plans are shared, never per-harness. The
    home is ``<base>/<directory_name>/`` with ``plans/``, ``memory/``,
    ``contexts/``, and ``learning/`` children.

    Args:
        base: The base directory the working directory sits beneath — the
            project root or the user home, as :func:`resolve_workspace_base`
            selects from the profile's ``workspace.scope``.
        directory_name: The shared working-directory name. Defaults to
            ``".apothem"`` and is overridable from the profile's
            ``workspace.directory_name``. Must be a single path component.

    Returns:
        A :class:`DataHome` with absolute child paths. The directories are
        not created; call :meth:`DataHome.ensure` to materialize the tree.

    Raises:
        DataHomeError: When *directory_name* is empty, carries a path separator
            or a drive specifier (``:``), or is a ``.`` / ``..`` component.
    """
    name = _validate_directory_name(directory_name)
    return DataHome.from_root(base / name)


def _validate_directory_name(directory_name: str) -> str:
    """Return *directory_name* stripped, or raise if it is not one component.

    The working-directory name must be exactly one path component so that
    joining it onto a base never escapes the base. The guard rejects path
    separators, a Windows drive specifier (``:``, which would reset pathlib to
    the drive root), and the ``.`` / ``..`` traversal components.

    Args:
        directory_name: The candidate working-directory name.

    Returns:
        The stripped, validated single-component name.

    Raises:
        DataHomeError: When *directory_name* is empty, carries a separator or a
            drive specifier (``:``), or is a ``.`` / ``..`` component.
    """
    name = directory_name.strip()
    if not name:
        raise DataHomeError("directory_name must be a non-empty string")
    if "/" in name or "\\" in name or ":" in name or name in {".", ".."}:
        raise DataHomeError(
            f"directory_name must be a single path component, got {directory_name!r}"
        )
    return name


def resolve_workspace_base(
    *, workspace: WorkspaceConfig, project_root: Path, home: Path
) -> Path:
    """Resolve the base directory the shared working directory sits beneath.

    The *workspace* scope selects which root the working directory is anchored
    to: ``"project-local"`` (the default) roots it at *project_root*, while
    ``"user-home"`` roots it at *home*. The mapping is pure and deterministic;
    no filesystem access occurs.

    The default scope reproduces today's behavior (base equals the project
    root), so a profile that omits ``workspace`` resolves the shared home under
    the install root exactly as the pre-relocation layout did.

    Args:
        workspace: The profile's workspace configuration carrying ``scope``.
        project_root: The project root used when ``scope`` is project-local.
        home: The user home directory used when ``scope`` is user-home.

    Returns:
        *project_root* for the project-local scope, *home* for the user-home
        scope.

    Raises:
        DataHomeError: When ``workspace.scope`` is neither ``"project-local"``
            nor ``"user-home"``.
    """
    scope = workspace.scope
    if scope == "project-local":
        return project_root
    if scope == "user-home":
        return home
    raise DataHomeError(
        f"workspace.scope must be 'project-local' or 'user-home', got {scope!r}"
    )


def resolve_install_data_home(
    root: Path, *, profile: dict[str, object] | None
) -> DataHome:
    """Resolve the shared data home an install pass into *root* materializes.

    The base is derived from the install *profile*'s ``workspace`` block:
    project-local scope (the default) roots the shared home at *root*; user-home
    scope roots it at the user home. The directory name (default ``.apothem``)
    is the working-directory name. When *profile* is ``None`` (the
    non-interactive path) or omits ``workspace``, the base is *root* and the name
    is ``.apothem`` — behavior-preserving for the base while the harness segment
    is collapsed.

    Args:
        root: The install root (harness root or project root) the shared working
            directory is anchored to under project-local scope.
        profile: The install profile dict carrying the ``workspace`` block, or
            ``None`` for the non-interactive path.

    Returns:
        The shared :class:`DataHome` for the install pass. The directories are
        not created; call :meth:`DataHome.ensure` to materialize the tree.
    """
    # Local import avoids a module-load cycle: profile.py is heavier and is only
    # needed to coerce the workspace block here.
    from apothem.lib.profile import WorkspaceConfig, coerce_profile

    workspace = (
        WorkspaceConfig() if profile is None else coerce_profile(profile).workspace
    )
    base = resolve_workspace_base(
        workspace=workspace, project_root=root, home=Path.home()
    )
    return resolve_shared_data_home(base=base, directory_name=workspace.directory_name)


def plans_root(*, base: Path, directory_name: str = ".apothem") -> Path:
    """Return the shared plans home ``<base>/<directory_name>/plans``.

    This is the canonical plans location under Apothem's single shared working
    directory. The path is computed purely; no filesystem access occurs and the
    directory is not created.

    Consumed by the statusline renderer (:mod:`apothem.statuslines.render`) to
    resolve the plans tree; a legacy ``<project-root>/.plans`` tree is no longer
    canonical — operators upgrade it via ``apothem migrate-workspace``.

    Args:
        base: The base directory the working directory sits beneath — the
            project root or the user home, as :func:`resolve_workspace_base`
            selects from the profile's ``workspace.scope``.
        directory_name: The shared working-directory name. Defaults to
            ``".apothem"`` and is overridable from the profile's
            ``workspace.directory_name``. Must be a single path component.

    Returns:
        The path ``<base>/<directory_name>/plans``.

    Raises:
        DataHomeError: When *directory_name* is not a single path component.
    """
    name = _validate_directory_name(directory_name)
    return base / name / _PLANS_CHILD


__all__ = [
    "DataHome",
    "DataHomeError",
    "plans_root",
    "resolve_install_data_home",
    "resolve_shared_data_home",
    "resolve_workspace_base",
]
