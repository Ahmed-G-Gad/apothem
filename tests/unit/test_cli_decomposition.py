# SPDX-License-Identifier: MIT

"""Module-boundary pin for the cli/__init__.py decomposition.

Asserts the structural shape the decomposition established and that later
edits must preserve:

- ``cli/__init__.py`` is a thin assembly (a line-count ceiling; no
  ``@main.command`` command *bodies* live there — only the ``main`` group and
  the registration wiring).
- Every expected ``cli/_cmd_*.py`` per-command module exists.
- The full command set (visible commands + hidden continuous-form aliases +
  the ``profile`` / ``harnesses`` sub-groups) is registered on ``main``.
- ``harness_registry.py`` re-exports its full public surface after the
  data/logic split.

The behavior-preservation guarantee itself lives in
``tests/integration/test_cli_behavior_diff.py``; this test pins the structure so
a future regression that re-monolithizes the CLI or drops a command is caught.
"""

from __future__ import annotations

import ast
from pathlib import Path

from apothem.cli import main
from apothem.lib import harness_registry

_CLI_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem" / "cli"

# Generous ceiling: the thin assembly is ~230 lines today (down from ~3315).
# The ceiling guards against re-monolithization, not against small edits.
_THIN_INIT_CEILING = 400

_EXPECTED_CMD_MODULES = (
    "_cmd_completion.py",
    "_cmd_install.py",
    "_cmd_uninstall.py",
    "_cmd_update.py",
    "_cmd_verify.py",
    "_cmd_status.py",
    "_cmd_diff.py",
    "_cmd_doctor.py",
    "_cmd_profile.py",
    "_cmd_harnesses.py",
)

_EXPECTED_HELPER_MODULES = (
    "_helpers.py",
    "_epilogs.py",
    "_materialize.py",
    "_group.py",
)

# Every command name registered on ``main`` in the pre-decomposition monolith.
_EXPECTED_COMMANDS = {
    "completion",
    "install",
    "quickstart",
    "uninstall",
    "rollback",
    "update",
    "verify",
    "status",
    "diff",
    "doctor",
    "profile",
    "harnesses",
    "migrate-workspace",
    # Hidden continuous-form aliases (initial-cap + lowercase).
    "Installing",
    "installing",
    "Uninstalling",
    "uninstalling",
    "Updating",
    "updating",
}

_PUBLIC_REGISTRY_SURFACE = (
    "HARNESS_REGISTRY",
    "REQUIRED_CAPABILITIES",
    "SUPPORTED_HARNESS_COUNT",
    "SUPPORTED_HARNESS_IDS",
    "SUPPORTED_PACKAGE_KEYS",
    "AdapterDiscoveryError",
    "CapabilityStatus",
    "HarnessRegistryEntry",
    "HarnessScope",
    "discover_adapters",
    "discovered_adapter_map",
    "get_harness_entry",
    "iter_harness_entries",
    "load_adapter_class",
    "normalize_harness_reference",
    "package_key_for_public_id",
    "public_id_for_package_key",
)


def test_init_is_thin_assembly() -> None:
    """The package __init__ stays a thin assembly under the line-count ceiling."""
    init = _CLI_PKG / "__init__.py"
    line_count = len(init.read_text(encoding="utf-8").splitlines())
    assert line_count <= _THIN_INIT_CEILING, (
        f"cli/__init__.py is {line_count} lines (> {_THIN_INIT_CEILING}); it should "
        "remain a thin assembly — move command bodies into _cmd_* modules"
    )


def test_init_carries_no_command_bodies() -> None:
    """No ``@main.command`` / ``@main.group`` command body is defined in __init__.

    The only Click callable defined in __init__ is the ``main`` group itself
    (decorated with ``@click.group``); every command is decorated with
    ``@main.command`` / ``@main.group`` and must live in a _cmd_* module.
    """
    tree = ast.parse((_CLI_PKG / "__init__.py").read_text(encoding="utf-8"))
    offending: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            # A decorator like ``main.command`` / ``main.group`` (attribute on
            # the ``main`` name) marks a command body — forbidden in __init__.
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "main"
            ):
                offending.append(node.name)
    assert not offending, f"command bodies must not live in __init__: {offending}"


def test_expected_command_modules_exist() -> None:
    for name in (*_EXPECTED_CMD_MODULES, *_EXPECTED_HELPER_MODULES):
        assert (_CLI_PKG / name).is_file(), f"missing CLI module: {name}"


def test_full_command_set_is_registered() -> None:
    # The root group loads command modules on first use, so resolve every
    # listed name (which imports its module) before reading the registry.
    import click

    ctx = click.Context(main)
    for name in main.list_commands(ctx):
        assert main.get_command(ctx, name) is not None, name
    registered = set(main.commands.keys())
    missing = _EXPECTED_COMMANDS - registered
    extra = registered - _EXPECTED_COMMANDS
    assert not missing, f"commands missing from main: {sorted(missing)}"
    assert not extra, f"unexpected commands on main: {sorted(extra)}"


def test_registry_logic_module_reexports_full_public_surface() -> None:
    for name in _PUBLIC_REGISTRY_SURFACE:
        assert hasattr(harness_registry, name), (
            f"harness_registry must re-export {name} after the data/logic split"
        )
    # The data table lives in the sibling data module and is the same object.
    from apothem.lib import harness_registry_data

    assert harness_registry_data.HARNESS_REGISTRY is harness_registry.HARNESS_REGISTRY
    # The dataclass stays frozen.
    assert harness_registry.HarnessRegistryEntry.__dataclass_params__.frozen is True
