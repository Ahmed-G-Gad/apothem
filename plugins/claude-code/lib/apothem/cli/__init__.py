# SPDX-License-Identifier: MIT

"""Apothem CLI — host-agnostic AI harness configuration manager.

Entry point: the Click group ``apothem.cli:main``. There is no
``[project.scripts]`` console-script shim; the engine is invoked through
the module surface (``python -m apothem``) — the same surface the npm
shim (``npx @ahmed-g-gad/apothem``), the Claude Code plugin, and the
one-shot installers run. Uses Click for argument parsing and Rich for
terminal output.

The CLI surface provides continuous-form command aliases
(``Installing``/``Updating``/``Uninstalling`` plus lowercase
variants, hidden from ``--help`` but still resolvable), per-subcommand
epilog blocks, a standard cross-subcommand flag set, shell-completion
script emission (``apothem completion <shell>``), and a JSON output mode.

This module is the thin assembly layer and is kept cheap to import, so
``--version`` and ``--help`` start quickly. It defines the ``main`` group
(a :class:`~apothem.cli._group.RootGroup`, which imports each command module
the first time that command runs) and nothing heavier. The helpers, epilogs,
and command bodies live in sibling modules:

- ``_group`` — the light group plumbing: lazy command loading, the
  usage-error contract, context settings, and UTF-8 stdio setup.
- ``_helpers`` — shared constants, the structured CLI-error type, the adapter
  protocol + load helpers, profile read/write, lifecycle-envelope builders,
  harness selection, project-root resolution, and the drift/plan helpers.
- ``_epilogs`` — the per-subcommand ``--help`` epilog strings.
- ``_materialize`` — the shared install/update materialization orchestrators.
- ``_cmd_*`` — one module per command / command-group.

The shared helpers are re-exported on this package namespace so that the
existing test seams (``patch("apothem.cli.NAME")`` /
``monkeypatch.setattr(cli, "NAME", ...)``) keep landing: the command bodies
and orchestrators resolve those helpers through ``apothem.cli`` at call time.
The re-exports resolve on first access (module ``__getattr__``), so importing
this package does not import the materialization stack.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import click

import apothem
from apothem.cli._group import _CONTEXT, RootGroup
from apothem.cli._group import _configure_stdio as _configure_stdio
from apothem.cli._group import configure_stdio as configure_stdio

if TYPE_CHECKING:
    # Static view of the lazy re-exports below, for type checkers only.
    from apothem.cli._helpers import (
        _ADAPTER_LOAD_ERRORS as _ADAPTER_LOAD_ERRORS,
    )
    from apothem.cli._helpers import (
        _EXIT_EXPECTED as _EXIT_EXPECTED,
    )
    from apothem.cli._helpers import (
        _EXIT_PARTIAL as _EXIT_PARTIAL,
    )
    from apothem.cli._helpers import (
        _PLACEHOLDER_IDENTITY as _PLACEHOLDER_IDENTITY,
    )
    from apothem.cli._helpers import (
        AliasedGroup as AliasedGroup,
    )
    from apothem.cli._helpers import (
        _Adapter as _Adapter,
    )
    from apothem.cli._helpers import (
        _adapter_failure_result as _adapter_failure_result,
    )
    from apothem.cli._helpers import (
        _adapter_requires_project as _adapter_requires_project,
    )
    from apothem.cli._helpers import (
        _adapter_resolve_output_path as _adapter_resolve_output_path,
    )
    from apothem.cli._helpers import (
        _all_adapters as _all_adapters,
    )
    from apothem.cli._helpers import (
        _CliUserError as _CliUserError,
    )
    from apothem.cli._helpers import (
        _complete_harness as _complete_harness,
    )
    from apothem.cli._helpers import (
        _drift_state as _drift_state,
    )
    from apothem.cli._helpers import (
        _dry_run_plan as _dry_run_plan,
    )
    from apothem.cli._helpers import (
        _emit_expected_error as _emit_expected_error,
    )
    from apothem.cli._helpers import (
        _error_envelope as _error_envelope,
    )
    from apothem.cli._helpers import (
        _format_error_plain as _format_error_plain,
    )
    from apothem.cli._helpers import (
        _harness_roots as _harness_roots,
    )
    from apothem.cli._helpers import (
        _invoke_with_project as _invoke_with_project,
    )
    from apothem.cli._helpers import (
        _lifecycle_envelope as _lifecycle_envelope,
    )
    from apothem.cli._helpers import (
        _load_adapter_for_entry as _load_adapter_for_entry,
    )
    from apothem.cli._helpers import (
        _load_profile as _load_profile,
    )
    from apothem.cli._helpers import (
        _materialization_error as _materialization_error,
    )
    from apothem.cli._helpers import (
        _parse_set_value as _parse_set_value,
    )
    from apothem.cli._helpers import (
        _partition_blast_radius as _partition_blast_radius,
    )
    from apothem.cli._helpers import (
        _path_is_within as _path_is_within,
    )
    from apothem.cli._helpers import (
        _placeholder_advisory_entry as _placeholder_advisory_entry,
    )
    from apothem.cli._helpers import (
        _placeholder_identity_fields as _placeholder_identity_fields,
    )
    from apothem.cli._helpers import (
        _profile_error as _profile_error,
    )
    from apothem.cli._helpers import (
        _profile_scaffold_text as _profile_scaffold_text,
    )
    from apothem.cli._helpers import (
        _project_option as _project_option,
    )
    from apothem.cli._helpers import (
        _render_blast_radius as _render_blast_radius,
    )
    from apothem.cli._helpers import (
        _require_project_for_selection as _require_project_for_selection,
    )
    from apothem.cli._helpers import (
        _resolve_profile_path as _resolve_profile_path,
    )
    from apothem.cli._helpers import (
        _resolve_project_root as _resolve_project_root,
    )
    from apothem.cli._helpers import (
        _result_dicts as _result_dicts,
    )
    from apothem.cli._helpers import (
        _select_and_load_adapters as _select_and_load_adapters,
    )
    from apothem.cli._helpers import (
        _selected_harness_ids as _selected_harness_ids,
    )
    from apothem.cli._helpers import (
        _set_nested as _set_nested,
    )
    from apothem.cli._helpers import (
        _status_for_exit_code as _status_for_exit_code,
    )
    from apothem.cli._helpers import (
        _stdin_is_interactive as _stdin_is_interactive,
    )
    from apothem.cli._helpers import (
        _unknown_harness_error as _unknown_harness_error,
    )
    from apothem.cli._helpers import (
        _warning_dicts as _warning_dicts,
    )
    from apothem.cli._helpers import (
        _write_profile_text_safely as _write_profile_text_safely,
    )
    from apothem.cli._materialize import (
        _dry_run_materialization as _dry_run_materialization,
    )
    from apothem.cli._materialize import (
        _materialize as _materialize,
    )
    from apothem.lib.harness_registry import (
        get_harness_entry as get_harness_entry,
    )
    from apothem.lib.harness_registry import (
        iter_harness_entries as iter_harness_entries,
    )

# Single version source: the package root resolves the version tree-first
# (the co-located pyproject.toml), then installed metadata, then the
# explicit unknown sentinel.
_VERSION = apothem.__version__

_HELPERS = "apothem.cli._helpers"
_MATERIALIZE = "apothem.cli._materialize"
_REGISTRY = "apothem.lib.harness_registry"

#: Names re-exported on this package, mapped to the module that defines them.
#: The command modules and orchestrators resolve these through ``apothem.cli``
#: at call time, so every name a test patches must be listed here.
_LAZY_EXPORTS: dict[str, str] = {
    **dict.fromkeys(
        (
            "_ADAPTER_LOAD_ERRORS",
            "_EXIT_EXPECTED",
            "_EXIT_PARTIAL",
            "_PLACEHOLDER_IDENTITY",
            "AliasedGroup",
            "_Adapter",
            "_adapter_failure_result",
            "_adapter_requires_project",
            "_adapter_resolve_output_path",
            "_all_adapters",
            "_CliUserError",
            "_complete_harness",
            "_drift_state",
            "_dry_run_plan",
            "_emit_expected_error",
            "_error_envelope",
            "_format_error_plain",
            "_harness_roots",
            "_invoke_with_project",
            "_lifecycle_envelope",
            "_load_adapter_for_entry",
            "_load_profile",
            "_materialization_error",
            "_parse_set_value",
            "_partition_blast_radius",
            "_path_is_within",
            "_placeholder_advisory_entry",
            "_placeholder_identity_fields",
            "_profile_error",
            "_profile_scaffold_text",
            "_project_option",
            "_render_blast_radius",
            "_require_project_for_selection",
            "_resolve_profile_path",
            "_resolve_project_root",
            "_result_dicts",
            "_select_and_load_adapters",
            "_selected_harness_ids",
            "_set_nested",
            "_status_for_exit_code",
            "_stdin_is_interactive",
            "_unknown_harness_error",
            "_warning_dicts",
            "_write_profile_text_safely",
        ),
        _HELPERS,
    ),
    "_dry_run_materialization": _MATERIALIZE,
    "_materialize": _MATERIALIZE,
    "get_harness_entry": _REGISTRY,
    "iter_harness_entries": _REGISTRY,
}


def __getattr__(name: str) -> object:
    """Resolve a re-exported helper on first access and cache it here."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List the lazy re-exports alongside the eagerly bound names."""
    return sorted({*globals(), *_LAZY_EXPORTS})


# -----------------------------------------------------------------------
# Top-level group.
# -----------------------------------------------------------------------


@click.group(cls=RootGroup, context_settings=_CONTEXT)
@click.version_option(version=_VERSION, prog_name="Apothem")
def main() -> None:
    """Apothem — host-agnostic AI harness configuration manager."""
    configure_stdio()
