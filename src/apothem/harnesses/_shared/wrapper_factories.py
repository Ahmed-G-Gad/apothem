# SPDX-License-Identifier: MIT

"""Factories for the thin per-adapter wrapper shims.

Every harness adapter's ``update.py`` / ``verify.py`` (and the project-scope
adapters' ``install.py`` / ``plan()`` plus the native-config adapters'
``install.py``) repeats byte-identical boilerplate that differs only by the
harness's manifest key, scope, and a handful of per-adapter deltas. This
module carries those wrapper shapes once as closure factories so each adapter
holds only its harness-specific identity; the heavy materialization logic
already lives in :mod:`apothem.harnesses._shared.install_driver` and its
sibling modules and is untouched here.

Behavior is identical to the hand-written shims these factories replace: the
returned closures call the same driver entry points with the same arguments
in the same order, so no rendered install output changes.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from apothem.lib.harness_registry import package_key_for_public_id
from apothem.lib.install_ledger import OwnedEntry

from . import install_driver
from .install_driver import MaterializationError, MaterializationRun

# Lifecycle-delegate closure signatures shared by the class factories below.
_ProjectInstallFn = Callable[..., MaterializationRun]
_ProjectPlanFn = Callable[..., list[dict[str, str]]]
_ProjectUninstallFn = Callable[..., None]
_ProjectVerifyFn = Callable[..., bool]
_NativeInstallFn = Callable[[Path, dict[str, Any]], MaterializationRun]
_NativeUninstallFn = Callable[[Path], None]
_NativeVerifyFn = Callable[[Path], bool]

# Type aliases for the wrapper closure signatures.
_UserScopeInstall = Callable[[Path, dict[str, Any]], MaterializationRun]
_ProjectScopeInstall = Callable[..., MaterializationRun]
_UserScopeUpdate = Callable[[Path, dict[str, Any]], MaterializationRun]
_ProjectScopeUpdate = Callable[..., MaterializationRun]
_UserScopeVerify = Callable[[Path], bool]
_ProjectScopeVerify = Callable[..., bool]
_ProjectScopePlan = Callable[..., list[dict[str, str]]]
_MaterializeFn = Callable[[dict[str, Any]], str]
_RetiredFn = Callable[[dict[str, Any]], tuple[OwnedEntry, ...]]

_UPDATE_DOC = """Re-materialize the harness configuration from the updated profile.

    Functionally equivalent to install; kept as a separate entry point
    so future update semantics (diff, backup-before-overwrite, etc.)
    can be added without changing the install contract."""

_UPDATE_DOC_PROJECT = (
    _UPDATE_DOC
    + " Threads the\n    operator-supplied ``project`` root through to the install entry."
)


def make_update(install_fn: _UserScopeInstall) -> _UserScopeUpdate:
    """Return a user-scope ``update`` shim delegating to *install_fn*.

    The returned closure has the identical contract and behavior as the
    hand-written user-scope ``update`` it replaces: ``return install(...)``.
    """

    def update(output_path: Path, profile: dict[str, Any]) -> MaterializationRun:
        return install_fn(output_path, profile)

    update.__doc__ = _UPDATE_DOC
    return update


def make_update_project(install_fn: _ProjectScopeInstall) -> _ProjectScopeUpdate:
    """Return a project-scope ``update`` shim delegating to *install_fn*.

    The returned closure threads the operator-supplied ``project`` keyword
    through to *install_fn*, matching the hand-written project-scope shim.
    """

    def update(
        output_path: Path,
        profile: dict[str, Any],
        *,
        project: Path | None = None,
    ) -> MaterializationRun:
        return install_fn(output_path, profile, project=project)

    update.__doc__ = _UPDATE_DOC_PROJECT
    return update


_VERIFY_DOC = """Return True when every manifest install-list target is present and valid.

    Delegates to the shared manifest-walk verifier: every install entry's
    resolved target must exist per its mode and parse if it is a JSON/YAML
    config. The harness root is ``output_path.parent``."""

_VERIFY_DOC_PROJECT = """Return True when every manifest install-list target is present and valid.

    Project-scope: the manifest walk resolves targets from the project root, so
    ``output_path`` (already resolved by the adapter wrapper) is unused here."""

# Docstrings for the install / plan / uninstall closures below. These are
# assigned onto the returned closure rather than written inline, matching
# ``_UPDATE_DOC`` / ``_VERIFY_DOC`` above: the closure becomes the adapter's
# public lifecycle method, so its ``__doc__`` is what an operator sees on
# ``help(adapter.install)`` — the enclosing factory's docstring is not reachable
# from there.
_INSTALL_DOC = """Materialize the profile into the harness's native configuration.

    Runs the manifest install against the harness root (``output_path.parent``),
    threading the profile into the instruction anchor's managed block, then
    records the run in the install ledger."""

_INSTALL_DOC_PROJECT = """Materialize the profile into the project's configuration.

    Project-scope: every target resolves from the operator-supplied ``project``
    root, so ``output_path`` is unused. Raises ``ValueError`` when ``project``
    is absent — a project-scope adapter has no user-scope fallback root."""

_INSTALL_DOC_NATIVE = """Render and write the harness's native config, then install support files.

    Materializes the native configuration from the profile, applies it as an
    operator-owned write, installs the manifest support subtree, and finalizes
    the run."""

_PLAN_DOC = """Return the install list without writing anything.

    Materializes the manifest against the harness root (``output_path.parent``)
    so a caller can preview every pending change before it lands."""

_PLAN_DOC_PROJECT = """Return the install list without writing anything.

    Project-scope: targets resolve from the ``project`` root, so ``output_path``
    is unused."""

_UNINSTALL_DOC = """Remove this harness's manifest targets, leaving no orphans.

    The shared driver strips only Apothem's managed block and keys, backing each
    target up under the Apothem backup root first, so operator-authored content
    in a shared file survives."""

_UNINSTALL_DOC_PROJECT = """Remove this harness's manifest targets from the project root.

    The project root passes through when the CLI supplied it; otherwise it is
    derived from the adapter's declared relative target."""

_UNINSTALL_DOC_NATIVE = """Remove the rendered native config and the manifest support subtree.

    The materializer-rendered config is not a manifest entry, so Apothem's
    structural contribution is identified by re-rendering from an empty profile
    and removed surgically before the shared driver cleans the support tree."""


def make_verify_harness_root(harness_name: str) -> _UserScopeVerify:
    """Return a user-scope ``verify`` shim for the harness-root cluster."""

    def verify(output_path: Path) -> bool:
        return install_driver.verify_install(
            harness_name, harness_root=output_path.parent
        )

    verify.__doc__ = _VERIFY_DOC
    return verify


def make_verify_project(harness_name: str) -> _ProjectScopeVerify:
    """Return a project-scope ``verify`` shim for the project-scope cluster."""

    def verify(output_path: Path, *, project: Path | None = None) -> bool:
        del output_path  # the manifest walk resolves targets from the project root
        if project is None:
            return False
        return install_driver.verify_install(harness_name, project_root=project)

    verify.__doc__ = _VERIFY_DOC_PROJECT
    return verify


def make_verify_native_config(harness_name: str) -> _UserScopeVerify:
    """Return a verify shim for the native-config (materializer) cluster."""

    def verify(output_path: Path) -> bool:
        return install_driver.verify_install(
            harness_name,
            harness_root=output_path.parent,
            native_config=output_path,
        )

    verify.__doc__ = _VERIFY_DOC
    return verify


def make_user_scope_install(harness_name: str) -> _UserScopeInstall:
    """Return a user-scope ``install`` shim for the raw-propagation cluster.

    Builds the byte-identical ``finalize_install(run_install(...))`` install
    body the raw-propagation user-scope adapters (antigravity, codex) each
    hand-rolled: run the manifest install against the harness root resolved as
    ``output_path.parent``, threading the shared *profile* into the instruction
    anchor's managed block, then finalize (ledger-record) the run. Behavior is
    identical to the hand-written body — same driver calls, same argument order.

    The claude-code adapter is intentionally *not* on this shim: it interleaves
    a hand-rolled managed-block anchor write and a hook-interpreter resolution
    between ``run_install`` and ``finalize_install``, so it keeps a bespoke
    install body.
    """

    def install(output_path: Path, profile: dict[str, Any]) -> MaterializationRun:
        return install_driver.finalize_install(
            install_driver.run_install(
                harness_name, harness_root=output_path.parent, profile=profile
            ),
            root=output_path.parent,
        )

    install.__doc__ = _INSTALL_DOC
    return install


def make_plan_harness_root(harness_name: str) -> _ProjectPlanFn:
    """Return a user-scope ``plan`` shim for the harness-root cluster.

    Builds the byte-identical ``build_plan`` body the user-scope adapters
    (antigravity, claude_code, codex) each hand-rolled: materialize the
    manifest install list against the harness root resolved as
    ``output_path.parent`` without writing anything.
    """

    def plan(output_path: Path) -> list[dict[str, str]]:
        return install_driver.build_plan(harness_name, harness_root=output_path.parent)

    plan.__doc__ = _PLAN_DOC
    return plan


def make_uninstall(harness_name: str) -> _NativeUninstallFn:
    """Return a user-scope ``uninstall`` shim for the harness-root cluster.

    Builds the byte-identical ``run_uninstall`` delegation the user-scope
    adapters (antigravity, claude_code, codex) each hand-rolled: surgically
    remove *harness_name*'s manifest targets under the harness root resolved as
    ``output_path.parent`` — the shared driver strips only Apothem's managed
    block / keys and backs each target up under the Apothem backup root.
    """

    def uninstall(output_path: Path) -> None:
        install_driver.run_uninstall(harness_name, harness_root=output_path.parent)

    uninstall.__doc__ = _UNINSTALL_DOC
    return uninstall


def make_user_scope_adapter(
    name: str,
    *,
    target_factory: Callable[[], Path],
    install_fn: _UserScopeInstall,
    plan_fn: _ProjectPlanFn,
    uninstall_fn: _NativeUninstallFn,
    update_fn: _UserScopeInstall,
    verify_fn: _NativeVerifyFn,
    class_name: str,
) -> type:
    """Return a user-scope ``<Name>Adapter`` class exposing ``plan()``.

    Builds the byte-identical user-scope adapter class the raw-propagation
    cohort (antigravity, claude_code, codex) each hand-rolled. The class owns
    one ``output_path`` anchor, resolves the harness root as
    ``output_path.parent`` for its lifecycle methods, and additionally exposes a
    ``plan()`` method (the raw-propagation cohort's divergence from the
    native-config cohort, which has no ``plan``). Per-adapter deltas captured as
    parameters:

    - *name*: the canonical kebab-case identifier the ``name`` property returns.
    - *target_factory*: a zero-arg callable returning the absolute config-file
      anchor path; called lazily on every ``output_path`` access so a per-access
      ``Path.home()`` / ``$CODEX_HOME`` evaluation is preserved (eager
      evaluation at import would bind the operator's real home before test
      HOME-isolation could redirect it).
    - *class_name*: the ``__name__`` / ``__qualname__`` the returned class
      carries so entry-point and discovery resolution find ``<Name>Adapter``.

    Behavior is identical to the hand-written classes: same ``name``, same
    ``output_path``, same method delegation and argument order, including the
    ``plan(output_path or self.output_path)`` fallback.
    """
    _name = name

    class _UserScopeAdapter:
        @property
        def name(self) -> str:
            """Return the canonical kebab-case harness identifier."""
            return _name

        @property
        def output_path(self) -> Path:
            """Return the always-propagated singleton config file path.

            The adapter resolves the harness root as ``output_path.parent``;
            ``is_installed()`` / ``verify()`` resolve against this anchor.
            """
            return target_factory()

        def install(self, profile: dict[str, Any]) -> MaterializationRun:
            """Materialize the harness configuration from the shared profile."""
            return install_fn(self.output_path, profile)

        def update(self, profile: dict[str, Any]) -> MaterializationRun:
            """Re-materialize the harness configuration from the updated profile."""
            return update_fn(self.output_path, profile)

        def plan(self, output_path: Path | None = None) -> list[dict[str, str]]:
            """Return the manifest-driven propagation plan without writing."""
            return plan_fn(output_path or self.output_path)

        def uninstall(self) -> None:
            """Remove the harness configuration file if present."""
            uninstall_fn(self.output_path)

        def is_installed(self) -> bool:
            """Return True if this harness root carries an Apothem install."""
            return install_driver.detect_install(
                package_key_for_public_id(_name),
                harness_root=self.output_path.parent,
            )

        def verify(self) -> bool:
            """Return True if the installed configuration is valid."""
            return verify_fn(self.output_path)

    _UserScopeAdapter.__name__ = class_name
    _UserScopeAdapter.__qualname__ = class_name
    _UserScopeAdapter.__doc__ = (
        f"{class_name} — implements :class:`~apothem.harnesses.HarnessAdapter`."
    )
    return _UserScopeAdapter


def make_project_scope_install(
    harness_name: str, *, error_message: str
) -> _ProjectScopeInstall:
    """Return a project-scope ``install`` shim for the rules-only cluster.

    *error_message* is the adapter's distinct ``--project`` rejection message.
    """

    def install(
        output_path: Path,
        profile: dict[str, Any],
        *,
        project: Path | None = None,
    ) -> MaterializationRun:
        del output_path  # resolved per-entry from manifest + project root
        if project is None:
            raise ValueError(error_message)
        return install_driver.finalize_install(
            install_driver.run_install(
                harness_name, project_root=project, profile=profile
            ),
            root=project,
        )

    install.__doc__ = _INSTALL_DOC_PROJECT
    return install


def make_project_scope_plan(harness_name: str) -> _ProjectScopePlan:
    """Return a project-scope ``plan`` shim for the rules-only cluster."""

    def plan(output_path: Path, *, project: Path | None = None) -> list[dict[str, str]]:
        del output_path  # resolved per-entry from manifest + project root
        return install_driver.build_plan(harness_name, project_root=project)

    plan.__doc__ = _PLAN_DOC_PROJECT
    return plan


def make_project_scope_uninstall(
    harness_name: str, *, relative_target: Path
) -> _ProjectUninstallFn:
    """Return a project-scope ``uninstall`` shim for the rules-only cluster.

    Builds the ``run_uninstall`` delegation the project-scope adapters
    (codebuddy, cursor, gemini_cli, github_copilot, glm, kiro, trae, windsurf,
    zed) each hand-rolled. The project root passes through when the CLI supplied
    it; on a direct module call without ``project`` the root is derived from the
    adapter's declared *relative_target* — the same sentinel path the adapter's
    ``resolve_output_path`` joins onto the project root — by ascending exactly as
    many parents as the target has path components. This replaces the
    hand-rolled ``output_path.parents[N]`` fallback whose ``N`` was a magic index
    that had to be kept in lockstep with *relative_target* by hand: a target of
    depth ``d`` (``d`` path components) means ``output_path`` is ``d`` levels
    below the project root, so the project root is ``output_path.parents[d - 1]``.
    Deriving ``d`` from *relative_target* keeps the correct root under any
    manifest-depth change, where a hardcoded index would silently derive the
    wrong root.
    """
    _depth = len(relative_target.parts) - 1

    def uninstall(output_path: Path, *, project: Path | None = None) -> None:
        project_root = project if project is not None else output_path.parents[_depth]
        install_driver.run_uninstall(harness_name, project_root=project_root)

    uninstall.__doc__ = _UNINSTALL_DOC_PROJECT
    return uninstall


def _native_allowed_root(output_path: Path) -> Path:
    """Return the allowed-write boundary for a native config at *output_path*.

    The same boundary :func:`install_driver.run_install` uses for the harness
    root ``output_path.parent``: its parent (the home directory for a
    user-scope harness). Backups are keyed relative to this boundary and
    :func:`install_driver.restore_backup` rebuilds paths from it, so the native
    config's backup must use it too — keying it relative to the harness root
    instead restored the operator's config one directory too high.
    """
    return install_driver._allowed_write_root(output_path.parent, None)


def make_native_config_uninstall(
    harness_name: str,
    materialize_fn: _MaterializeFn,
    *,
    apothem_keys: frozenset[str] = frozenset(),
) -> _NativeUninstallFn:
    """Return a native-config (materializer) ``uninstall`` shim.

    Builds the byte-identical ``surgically_remove_materialized_config`` +
    ``run_uninstall`` body the native-config adapters (hermes, open_claw,
    opencode, qwen_code) each hand-rolled. The materializer-rendered native
    config is not a manifest entry, so it is cleaned surgically here: the
    adapter's *materialize_fn* rendered from an empty profile identifies
    Apothem's structural contribution for an install recorded before
    ownership tracking (newer installs remove exactly the entries the ledger
    records), *apothem_keys* names top-level namespaces stripped wholesale
    from such an older install (empty — the driver default — for every
    current adapter) — and the manifest support subtree is then cleaned by
    the shared driver.
    Behavior is identical to the hand-written body — same driver calls, same
    argument order.
    """

    def uninstall(output_path: Path) -> None:
        install_driver.surgically_remove_materialized_config(
            output_path,
            materialize_fn({}),
            install_root=output_path.parent,
            harness_name=harness_name,
            allowed_root=_native_allowed_root(output_path),
            apothem_keys=apothem_keys,
        )
        install_driver.run_uninstall(harness_name, harness_root=output_path.parent)

    uninstall.__doc__ = _UNINSTALL_DOC_NATIVE
    return uninstall


def make_native_config_install(
    harness_name: str,
    materialize_fn: _MaterializeFn,
    *,
    harness_id: str,
    render_tokens: bool = False,
    support_profile: bool = False,
    retired_fn: _RetiredFn | None = None,
) -> _UserScopeInstall:
    """Return a native-config (materializer) ``install`` shim.

    The pipeline is identical for every native-config adapter: materialize the
    native config, project capability warnings, apply the operator-owned write,
    raise on a write error, run the support install, drop ``warning`` results,
    project the profile document, and finalize. Per-adapter deltas:

    - *render_tokens*: when True, the materialized content is passed through
      :func:`install_driver.render_content_tokens` against the harness root
      (qwen_code only).
    - *support_profile*: when True, the support ``run_install`` receives the
      ``profile`` keyword (qwen_code only).
    - *retired_fn*: returns, for a profile, the entries an earlier release of
      this adapter wrote at a location it no longer uses, so an update over
      such an install removes them (hermes only).
    """

    def install(output_path: Path, profile: dict[str, Any]) -> MaterializationRun:
        content = materialize_fn(profile)
        if render_tokens:
            content = install_driver.render_content_tokens(
                content, harness_root=output_path.parent
            )
        capability_warnings = install_driver._capability_projection_results(
            harness_name
        )
        native_result = install_driver.apply_operator_owned_content(
            output_path,
            content,
            install_root=output_path.parent,
            harness_name=harness_name,
            allowed_root=_native_allowed_root(output_path),
            retired=retired_fn(profile) if retired_fn is not None else (),
        )
        if native_result.outcome == "error":
            raise MaterializationError(
                f"materialization write failed: {native_result.message}",
                MaterializationRun(
                    harness=harness_name,
                    dry_run=False,
                    results=(*capability_warnings, native_result),
                ),
            )
        if support_profile:
            support_run = install_driver.run_install(
                harness_name,
                harness_root=output_path.parent,
                profile=profile,
            )
        else:
            support_run = install_driver.run_install(
                harness_name,
                harness_root=output_path.parent,
            )
        support_results = tuple(
            result for result in support_run.results if result.outcome != "warning"
        )
        profile_result = install_driver.project_profile_document(
            output_path.parent,
            harness_id=harness_id,
            harness_name=harness_name,
            profile=profile,
        )
        return install_driver.finalize_install(
            MaterializationRun(
                harness=harness_name,
                dry_run=False,
                results=(
                    *capability_warnings,
                    native_result,
                    *support_results,
                    profile_result,
                ),
            ),
            root=output_path.parent,
        )

    install.__doc__ = _INSTALL_DOC_NATIVE
    return install


def make_project_scope_adapter(
    name: str,
    *,
    error_label: str,
    relative_target: Path,
    install_fn: _ProjectInstallFn,
    plan_fn: _ProjectPlanFn,
    uninstall_fn: _ProjectUninstallFn,
    update_fn: _ProjectInstallFn,
    verify_fn: _ProjectVerifyFn,
    class_name: str,
) -> type:
    """Return a project-scope ``<Name>Adapter`` class.

    Builds the byte-identical project-scope adapter class every
    project-scope harness shares (codebuddy, cursor, gemini_cli,
    github_copilot, glm, kimi_code, kiro, trae, windsurf, zed). The class
    opts into the ``requires_project`` contract, resolves its on-disk target
    under the operator-supplied ``--project`` root, and delegates every
    lifecycle method to the per-adapter sibling functions passed in.
    Per-adapter deltas captured as parameters:

    - *name*: the canonical kebab-case identifier the ``name`` property returns.
    - *error_label*: the package-name token the ``resolve_output_path``
      ``ValueError`` message uses (underscore form, e.g. ``github_copilot``),
      which is distinct from *name* for the hyphen-vs-underscore harnesses.
    - *relative_target*: the sentinel relative path ``output_path`` returns
      and the concrete target ``resolve_output_path`` joins onto the project
      root.
    - *class_name*: the ``__name__`` / ``__qualname__`` the returned class
      carries so entry-point and discovery resolution find ``<Name>Adapter``.

    Behavior is identical to the hand-written classes: same ``name``, same
    resolved output paths, same ``requires_project`` flag, same method
    delegation and argument order.
    """
    _relative = relative_target
    _error = error_label
    _name = name

    class _ProjectScopeAdapter:
        #: Opt-in to the project-scope adapter contract.
        requires_project: bool = True

        @property
        def name(self) -> str:
            """Return the canonical kebab-case harness identifier."""
            return _name

        @property
        def output_path(self) -> Path:
            """Return a display-only sentinel relative path."""
            return _relative

        def resolve_output_path(self, project: Path | None) -> Path:
            """Return the concrete on-disk target under the project root."""
            if project is None:
                raise ValueError(
                    f"{_error} adapter requires --project <path> to resolve output_path"
                )
            return project / _relative

        def install(
            self, profile: dict[str, Any], *, project: Path | None = None
        ) -> MaterializationRun:
            """Materialize the harness configuration into the project root."""
            output_path = self.resolve_output_path(project)
            return install_fn(output_path, profile, project=project)

        def update(
            self, profile: dict[str, Any], *, project: Path | None = None
        ) -> MaterializationRun:
            """Re-materialize the harness configuration into the project root."""
            output_path = self.resolve_output_path(project)
            return update_fn(output_path, profile, project=project)

        def plan(
            self,
            output_path: Path | None = None,
            *,
            project: Path | None = None,
        ) -> list[dict[str, str]]:
            """Return the manifest-driven propagation plan without writing."""
            resolved = output_path or (
                self.resolve_output_path(project) if project is not None else _relative
            )
            return plan_fn(resolved, project=project)

        def uninstall(self, *, project: Path | None = None) -> None:
            """Remove the harness configuration file if present."""
            output_path = self.resolve_output_path(project)
            uninstall_fn(output_path, project=project)

        def is_installed(self, *, project: Path | None = None) -> bool:
            """Return True if this project root carries an Apothem install."""
            if project is None:
                return False
            return install_driver.detect_install(
                package_key_for_public_id(_name), project_root=project
            )

        def verify(self, *, project: Path | None = None) -> bool:
            """Return True if the installed configuration is valid."""
            if project is None:
                return False
            return verify_fn(self.resolve_output_path(project), project=project)

    _ProjectScopeAdapter.__name__ = class_name
    _ProjectScopeAdapter.__qualname__ = class_name
    _ProjectScopeAdapter.__doc__ = (
        f"{class_name} — implements :class:`~apothem.harnesses.HarnessAdapter`.\n\n"
        "    Project-scope adapter: opts into the ``requires_project`` contract\n"
        "    declared at :func:`apothem.cli._adapter_requires_project`. The CLI\n"
        "    threads the operator-supplied ``--project <path>`` value through\n"
        "    ``_invoke_with_project`` for every lifecycle method."
    )
    return _ProjectScopeAdapter


def make_native_config_adapter(
    name: str,
    *,
    target_factory: Callable[[], Path],
    install_fn: _NativeInstallFn,
    uninstall_fn: _NativeUninstallFn,
    update_fn: _NativeInstallFn,
    verify_fn: _NativeVerifyFn,
    class_name: str,
) -> type:
    """Return a native-config (materializer) ``<Name>Adapter`` class.

    Builds the byte-identical user-scope adapter class the native-config
    cohort (hermes, open_claw, opencode, qwen_code) each hand-rolled. The
    class owns one absolute ``output_path`` anchor and delegates every
    lifecycle method to the per-adapter sibling functions passed in.
    Per-adapter deltas captured as parameters:

    - *name*: the canonical kebab-case identifier the ``name`` property returns.
    - *target_factory*: a zero-arg callable returning the absolute target
      configuration path; called lazily on every ``output_path`` access so the
      hand-rolled property's per-access ``Path.home()`` evaluation is preserved
      (eager evaluation at import would bind the operator's real home directory
      before test HOME-isolation could redirect it).
    - *class_name*: the ``__name__`` / ``__qualname__`` the returned class
      carries so entry-point and discovery resolution find ``<Name>Adapter``.

    Behavior is identical to the hand-written classes: same ``name``, same
    ``output_path``, same method delegation and argument order.
    """
    _name = name

    class _NativeConfigAdapter:
        @property
        def name(self) -> str:
            """Return the canonical kebab-case harness identifier."""
            return _name

        @property
        def output_path(self) -> Path:
            """Return the target configuration file path."""
            return target_factory()

        def install(self, profile: dict[str, Any]) -> MaterializationRun:
            """Materialize the harness configuration from the shared profile."""
            return install_fn(self.output_path, profile)

        def update(self, profile: dict[str, Any]) -> MaterializationRun:
            """Re-materialize the harness configuration from the updated profile."""
            return update_fn(self.output_path, profile)

        def uninstall(self) -> None:
            """Remove the harness configuration file if present."""
            uninstall_fn(self.output_path)

        def is_installed(self) -> bool:
            """Return True if this harness root carries an Apothem install."""
            return install_driver.detect_install(
                package_key_for_public_id(_name),
                harness_root=self.output_path.parent,
            )

        def verify(self) -> bool:
            """Return True if the installed configuration is valid."""
            return verify_fn(self.output_path)

    _NativeConfigAdapter.__name__ = class_name
    _NativeConfigAdapter.__qualname__ = class_name
    _NativeConfigAdapter.__doc__ = (
        f"{class_name} implements :class:`~apothem.harnesses.HarnessAdapter`."
    )
    return _NativeConfigAdapter
