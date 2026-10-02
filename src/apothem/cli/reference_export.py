# SPDX-License-Identifier: MIT

"""Deterministic JSON exporter for source-generated documentation reference.

Runnable as ``python -m apothem.cli.reference_export <kind>`` where ``<kind>``
is one of ``cli``, ``conformity`` or ``harnesses``. The emitter introspects
Apothem's own Click command tree, conformity validator modules and harness
registry — the single source of truth — so the generated reference pages cannot
drift from the implementation.

Output is a single JSON document with stable key order and sorted collections,
so repeated runs against an unchanged tree are byte-identical.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

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
    """Return the deterministic harness-adapter registry export.

    Each record carries the registry's capability matrix (``capabilities``:
    surface → status) and the rationale recorded for exempt cells
    (``capability_notes``), so generated pages state per-adapter capability
    from the registry rather than from hand-written prose.
    """
    harnesses = [
        {
            "id": entry.public_id,
            "display_name": entry.display_name,
            "scope": entry.scope,
            "output_format": entry.output_format,
            "target_paths": sorted(entry.target_paths),
            "capabilities": dict(entry.capability_status),
            "capability_notes": dict(entry.unsupported_rationale),
        }
        for entry in iter_harness_entries()
    ]
    harnesses.sort(key=lambda entry: str(entry["id"]))
    return {"kind": "harnesses", "harnesses": harnesses}


def _module_constants(tree: ast.Module) -> dict[str, str]:
    """Return the module-level string constants ``GREP_NAME`` and ``RULE_ANCHOR``."""
    wanted = {"GREP_NAME", "RULE_ANCHOR"}
    constants: dict[str, str] = {}
    for node in tree.body:
        target: ast.expr
        value: ast.expr | None
        if isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        else:
            continue
        if not isinstance(target, ast.Name) or target.id not in wanted:
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            constants[target.id] = value.value
    return constants


def _summary(docstring: str, grep_name: str) -> str:
    """Return the docstring's first paragraph as one line, minus a ``<name>:`` lead-in."""
    paragraph: list[str] = []
    for line in docstring.strip().splitlines():
        if not line.strip():
            break
        paragraph.append(line.strip())
    text = " ".join(paragraph)
    prefix = f"{grep_name}:"
    if text.startswith(prefix):
        text = text[len(prefix) :].strip()
    return text[:1].upper() + text[1:]


def export_conformity() -> dict[str, object]:
    """Return the deterministic conformity-validator export.

    Every module under ``src/apothem/conformity/`` that declares a ``GREP_NAME``
    is one validator. Its ``mode`` says how the gate runs it: ``per-write``
    (the ``--hook`` and ``--all-perwrite`` chain), ``standalone`` (the ``--all``
    corpus sweep and ``--check``), or ``change-set`` (run on a staged diff, not by
    the gate's sweeps). The modules are parsed, not imported, so the export has
    no import side effects beyond the gate's own registry.
    """
    # Imported here so the cli and harnesses kinds do not load the gate.
    from apothem.conformity import gate as conformity_gate

    package_dir = Path(conformity_gate.__file__).parent
    per_write = {name.replace("-", "_") for name in conformity_gate.GREP_MODULES}
    standalone = {name.replace("-", "_") for name in conformity_gate.STANDALONE_MODULES}
    validators: list[dict[str, object]] = []
    for path in sorted(package_dir.glob("*.py")):
        if path.stem.startswith("_") or path.stem == "gate":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = _module_constants(tree)
        grep_name = constants.get("GREP_NAME")
        if grep_name is None:
            continue
        if path.stem in per_write:
            mode = "per-write"
        elif path.stem in standalone:
            mode = "standalone"
        else:
            mode = "change-set"
        validators.append(
            {
                "name": grep_name,
                "module": f"src/apothem/conformity/{path.name}",
                "mode": mode,
                "rule_anchor": constants.get("RULE_ANCHOR", ""),
                "summary": _summary(ast.get_docstring(tree) or "", grep_name),
            }
        )
    validators.sort(key=lambda entry: str(entry["name"]))
    return {"kind": "conformity", "validators": validators}


_EXPORTERS = {
    "cli": export_cli,
    "conformity": export_conformity,
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
