# SPDX-License-Identifier: MIT

"""Deterministic JSON exporter for source-generated documentation reference.

Runnable as ``python -m apothem.cli.reference_export <kind>`` where ``<kind>``
is one of ``cli`` or ``harnesses``. The emitter introspects Apothem's own Click
command tree and harness registry — the single source of truth — so the
generated reference pages cannot drift from the implementation.

Output is a single JSON document with stable key order and sorted collections,
so repeated runs against an unchanged tree are byte-identical.
"""

from __future__ import annotations

import json
import sys

import click

from apothem.cli import main as cli_main
from apothem.lib.harness_registry import iter_harness_entries

# Continuous-form CLI aliases (``Installing`` / ``installing`` and the
# capitalized / lowercase ``Updating`` / ``Uninstalling`` variants) duplicate
# the canonical lowercase verbs. They are excluded from the reference so each
# command appears exactly once under its canonical name.
_ALIAS_COMMAND_NAMES: frozenset[str] = frozenset(
    {
        "Installing",
        "installing",
        "Updating",
        "updating",
        "Uninstalling",
        "uninstalling",
    }
)


def _option_signatures(command: click.Command) -> list[str]:
    """Return the sorted flag signatures declared by *command*.

    Each entry is the comma-joined option declaration string (for example
    ``--harness`` or ``-h, --help``). The implicit ``--help`` option Click adds
    is included so the reference matches the observable CLI surface.
    """
    signatures: list[str] = []
    for param in command.params:
        if not isinstance(param, click.Option):
            continue
        signatures.append(", ".join(param.opts))
    return sorted(signatures)


def _command_entry(name: str, command: click.Command) -> dict[str, object]:
    """Build the deterministic export record for one leaf command."""
    return {
        "name": name,
        "flags": _option_signatures(command),
        "description": (command.help or command.short_help or "").strip(),
    }


def _walk_commands(prefix: str, group: click.Group) -> list[dict[str, object]]:
    """Recursively collect leaf-command records under *group*.

    Sub-groups (``profile``, ``harnesses``) recurse so their subcommands are
    emitted as ``profile show``, ``harnesses list``, and so on. Alias commands
    are skipped at the top level.
    """
    entries: list[dict[str, object]] = []
    for child_name in group.commands:
        if not prefix and child_name in _ALIAS_COMMAND_NAMES:
            continue
        child = group.commands[child_name]
        full_name = f"{prefix} {child_name}".strip()
        if isinstance(child, click.Group):
            entries.extend(_walk_commands(full_name, child))
        else:
            entries.append(_command_entry(full_name, child))
    return entries


def export_cli() -> dict[str, object]:
    """Return the deterministic CLI command-and-flag export."""
    commands = _walk_commands("", cli_main)
    commands.sort(key=lambda entry: str(entry["name"]))
    return {"kind": "cli", "commands": commands}


def export_harnesses() -> dict[str, object]:
    """Return the deterministic harness-adapter registry export."""
    harnesses = [
        {
            "id": entry.public_id,
            "display_name": entry.display_name,
            "scope": entry.scope,
            "output_format": entry.output_format,
            "target_paths": sorted(entry.target_paths),
        }
        for entry in iter_harness_entries()
    ]
    harnesses.sort(key=lambda entry: str(entry["id"]))
    return {"kind": "harnesses", "harnesses": harnesses}


_EXPORTERS = {
    "cli": export_cli,
    "harnesses": export_harnesses,
}


def main(argv: list[str] | None = None) -> int:
    """Emit the requested export kind as deterministic JSON on stdout."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in _EXPORTERS:
        kinds = ", ".join(sorted(_EXPORTERS))
        sys.stderr.write(f"usage: python -m apothem.cli.reference_export <{kinds}>\n")
        return 2
    payload = _EXPORTERS[args[0]]()
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
