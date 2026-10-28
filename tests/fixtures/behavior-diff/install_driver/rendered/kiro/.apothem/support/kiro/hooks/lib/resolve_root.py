# SPDX-License-Identifier: MIT

"""Project root resolution for the apothem ecosystem.

Resolves the absolute path of the apothem project root using a
four-strategy cascade: explicit environment variable, script-relative
ascent, current-working-directory walk, and a `$HOME/.claude` fallback
(the Claude Code harness's config root — one of the supported harnesses).
The environment-variable strategy consults two names in order
(``CLAUDE_PROJECT_DIR`` then ``LLM_PROJECT_DIR``), which is why
:func:`resolve_project_root` enumerates five numbered steps below.

The bootstrap stubs ``hooks/lib/bootstrap.sh`` and ``hooks/lib/bootstrap.ps1``
do not use this cascade: they resolve only their own installed tree (the
directory two levels above the stub), because they dot-source an interpreter
locator and execute the dispatcher, and taking either from the opened project
would run project-supplied code inside every hook. This module serves scripts
that read project files as data. Keep the three headers in step when either
rule changes.

Two marker strategies are supported:

* ``Mode.HOOKS`` — the root must contain both ``hooks/`` and ``rules/``
  subdirectories. Used by runtime hook scripts that need a populated
  ecosystem.
* ``Mode.MARKER`` — the root must contain a ``CLAUDE.md`` file. Used by
  scripts that may run before the full layout exists (ecosystem
  scaffolding, bootstrap utilities).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

#: The Apothem-owned shared working-directory name. The sole canonical
#: project-local plans home is ``<project-root>/.apothem/plans``. The legacy
#: ``<project-root>/.plans`` layout is no longer canonical; operators upgrade an
#: existing ``.plans`` tree via ``apothem migrate-workspace``.
_APOTHEM_SUBTREE: Final[str] = ".apothem"
_PLANS_CHILD: Final[str] = "plans"

__all__ = [
    "Mode",
    "ResolutionStrategy",
    "canonical_plans_dir",
    "default_content_root",
    "is_canonical_project_plans_dir",
    "resolve_project_root",
]


class Mode(str, Enum):
    """Marker-set selector for root detection."""

    HOOKS = "hooks"
    MARKER = "marker"


_HOOKS_MARKERS: Final[tuple[str, ...]] = ("hooks", "rules")
_FILE_MARKERS: Final[tuple[str, ...]] = ("CLAUDE.md",)


@dataclass(frozen=True)
class ResolutionStrategy:
    """Concrete resolution configuration derived from a `Mode`.

    Attributes:
        directory_markers: Subdirectories whose presence identifies a root.
        file_markers: Files whose presence identifies a root.
    """

    directory_markers: tuple[str, ...]
    file_markers: tuple[str, ...]

    @classmethod
    def for_mode(cls, mode: Mode) -> ResolutionStrategy:
        """Return the strategy corresponding to `mode`."""
        if mode is Mode.HOOKS:
            return cls(directory_markers=_HOOKS_MARKERS, file_markers=())
        return cls(directory_markers=(), file_markers=_FILE_MARKERS)

    def matches(self, candidate: Path) -> bool:
        """Return True when `candidate` contains all required markers."""
        if not candidate.is_dir():
            return False
        if not all((candidate / name).is_dir() for name in self.directory_markers):
            return False
        return all((candidate / name).is_file() for name in self.file_markers)


def _iter_ancestors(start: Path) -> Iterable[Path]:
    """Yield `start` and each parent up to the filesystem root."""
    current = start.resolve()
    yield current
    yield from current.parents


def _from_env(strategy: ResolutionStrategy, env: Mapping[str, str]) -> Path | None:
    """Resolve via ``$CLAUDE_PROJECT_DIR`` or ``$LLM_PROJECT_DIR``, or ``None``.

    The primary variable ``CLAUDE_PROJECT_DIR`` is consulted first; if it is
    unset or does not satisfy the strategy, the vendor-neutral alias
    ``LLM_PROJECT_DIR`` is tried as secondary. A successor harness that only
    sets ``LLM_PROJECT_DIR`` resolves without falling through to later steps.
    """
    for var_name in ("CLAUDE_PROJECT_DIR", "LLM_PROJECT_DIR"):
        env_dir = env.get(var_name)
        if not env_dir:
            continue
        candidate = Path(env_dir)
        if strategy.matches(candidate):
            return candidate.resolve()
    return None


def _from_script(
    strategy: ResolutionStrategy, script_path: Path | str | None
) -> Path | None:
    """Resolve via the parent of a script located in ``hooks/``."""
    if script_path is None:
        return None
    script = Path(script_path).resolve()
    if script.parent.name != "hooks":
        return None
    grand = script.parent.parent
    return grand if strategy.matches(grand) else None


def _from_walk(strategy: ResolutionStrategy, cwd: Path | str | None) -> Path | None:
    """Resolve by walking ancestors of `cwd`."""
    start = Path(cwd) if cwd is not None else Path.cwd()
    for ancestor in _iter_ancestors(start):
        if strategy.matches(ancestor):
            return ancestor
    return None


def _from_home(strategy: ResolutionStrategy, home: Path | str | None) -> Path | None:
    """Resolve via ``$HOME/.claude``."""
    home_dir = Path(home) if home is not None else Path.home()
    fallback = home_dir / ".claude"
    return fallback.resolve() if strategy.matches(fallback) else None


def resolve_project_root(
    mode: Mode = Mode.HOOKS,
    *,
    script_path: Path | str | None = None,
    cwd: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | str | None = None,
) -> Path | None:
    """Locate the apothem project root.

    The resolution order is:

    1. ``$CLAUDE_PROJECT_DIR`` if it satisfies the strategy.
    2. ``$LLM_PROJECT_DIR`` (vendor-neutral alias) if it satisfies the
       strategy.
    3. ``script_path``'s grandparent, when `script_path`'s immediate
       parent is named ``hooks``.
    4. Walk from `cwd` upward; return the first ancestor that
       satisfies the strategy.
    5. ``$HOME/.claude`` if it satisfies the strategy.

    Returns ``None`` when no candidate satisfies the chosen strategy.

    Args:
        mode: Which marker set to require.
        script_path: Absolute path of the calling script. When provided
            and located in a ``hooks/`` directory, the parent is tested.
        cwd: Starting directory for the upward walk. Defaults to
            ``Path.cwd()``.
        environ: Environment mapping. Defaults to ``os.environ``.
        home: Home directory. Defaults to ``Path.home()``.

    Returns:
        Absolute `Path` of the resolved root, or `None` if unresolved.
    """
    strategy = ResolutionStrategy.for_mode(mode)
    env: Mapping[str, str] = os.environ if environ is None else environ
    resolvers: tuple[Callable[[], Path | None], ...] = (
        lambda: _from_env(strategy, env),
        lambda: _from_script(strategy, script_path),
        lambda: _from_walk(strategy, cwd),
        lambda: _from_home(strategy, home),
    )
    for resolver in resolvers:
        result = resolver()
        if result is not None:
            return result
    return None


def default_content_root(root: Path) -> Path:
    """Resolve the harness content root for an apothem project root.

    In the apothem *source* repository the harness convention surface
    (``hooks/``, ``rules/``, ``commands/``, ...) lives under the
    ``src/apothem/`` package directory; in an installed harness (for
    example ``~/.claude/``) it sits flat at the project root. This
    helper returns ``root / "src" / "apothem"`` when that path carries
    the package marker (a ``hooks/`` subdirectory), otherwise ``root``
    unchanged — so dev validators run bare from either layout without an
    explicit ``--content-root`` flag.

    Args:
        root: The resolved apothem project root.

    Returns:
        The directory under which the harness convention surface lives.
    """
    src_layout = root / "src" / "apothem"
    if (src_layout / "hooks").is_dir():
        return src_layout
    return root


def canonical_plans_dir(project_root: Path) -> Path:
    """Return the canonical project-local plans directory for a root.

    Apothem keeps its working state in a single shared
    ``<project-root>/.apothem`` directory; the sole canonical plans tree is
    ``<project-root>/.apothem/plans``. The legacy ``<project-root>/.plans``
    layout is no longer canonical — operators upgrade an existing ``.plans``
    tree via ``apothem migrate-workspace``.

    The project-root resolution itself (git-ascent + CWD walk via
    :func:`resolve_project_root`) is unchanged; this helper only names the
    canonical plans location beneath an already-resolved root. The path is
    computed purely; no filesystem access occurs and no directory is created.

    Args:
        project_root: The resolved project root.

    Returns:
        ``<project-root>/.apothem/plans`` — the sole canonical plans location.
    """
    return project_root / _APOTHEM_SUBTREE / _PLANS_CHILD


def is_canonical_project_plans_dir(candidate: Path, project_root: Path) -> bool:
    """Return True iff *candidate* is the canonical project-local plans directory.

    The sole canonical project-local plans directory is
    ``<project-root>/.apothem/plans``. Any other plans-shaped directory — a
    legacy ``<project-root>/.plans``, a stray ``.plans`` nested elsewhere, or an
    ``.apothem/plans`` under a different root such as a harness-config root or
    the user home — is NOT canonical and remains subject to the global-plans
    deny.

    The comparison is by resolved path so a relative *candidate* and an absolute
    *project_root* compare correctly.

    Args:
        candidate: The plans-directory path under test.
        project_root: The resolved project root the candidate must sit beneath.

    Returns:
        True when *candidate* resolves to the canonical project-local plans
        directory, False otherwise.
    """
    try:
        resolved_candidate = candidate.resolve()
    except (OSError, RuntimeError):
        return False
    try:
        return resolved_candidate == canonical_plans_dir(project_root).resolve()
    except (OSError, RuntimeError):
        return False
