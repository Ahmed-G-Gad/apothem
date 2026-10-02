# SPDX-License-Identifier: MIT

"""``--version`` and ``--help`` start without the materialization stack.

Importing ``apothem.cli`` used to import every command module, the install
driver, the profile validator (jsonschema) and Rich, so ``--version`` cost
about ten times a bare interpreter. Command modules now load on first use,
and the root ``--help`` lists commands from a static summary table, which a
test keeps equal to each command's own short help.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click
import pytest
from click.utils import make_default_short_help

from apothem.cli import main

_SRC = Path(__file__).resolve().parents[2] / "src"
_HEAVY_MODULES = (
    "apothem.harnesses._shared.install_driver",
    "apothem.lib.profile",
    "jsonschema",
    "rich",
)


def _imported_modules(args: list[str]) -> set[str]:
    env = dict(os.environ, PYTHONPATH=str(_SRC))
    result = subprocess.run(
        [sys.executable, "-X", "importtime", "-m", "apothem", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return {
        line.rsplit("|", 1)[-1].strip()
        for line in result.stderr.splitlines()
        if line.startswith("import time:") and "|" in line
    }


@pytest.mark.parametrize("args", [["--version"], ["--help"]])
def test_version_and_help_skip_the_heavy_imports(args: list[str]) -> None:
    imported = _imported_modules(args)
    assert "apothem.cli" in imported
    loaded = [name for name in _HEAVY_MODULES if name in imported]
    assert loaded == [], f"{args} imported {loaded}"


def test_root_help_summaries_match_each_command() -> None:
    """The static table renders exactly what each loaded command would."""
    ctx = click.Context(main)
    lazy = main.lazy_commands
    assert set(main.list_commands(ctx)) == set(lazy)
    for name, spec in lazy.items():
        command = main.get_command(ctx, name)
        assert command is not None, name
        assert command.hidden is spec.hidden, name
        for limit in range(20, 121):
            assert make_default_short_help(spec.summary, limit) == (
                command.get_short_help_str(limit)
            ), (name, limit)


def test_root_help_lists_the_visible_commands(runner: click.testing.CliRunner) -> None:
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0, result.output
    listed = [
        line.split()[0]
        for line in result.output.split("Commands:", 1)[1].splitlines()
        if line.strip()
    ]
    visible = sorted(
        name for name, spec in main.lazy_commands.items() if not spec.hidden
    )
    assert listed == visible


def test_type_checking_view_matches_the_lazy_exports() -> None:
    """The TYPE_CHECKING imports in apothem.cli list exactly the lazy names."""
    import ast

    import apothem.cli as cli_pkg

    tree = ast.parse((_SRC / "apothem" / "cli" / "__init__.py").read_text("utf-8"))
    typed: dict[str, str] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            for stmt in node.body:
                if isinstance(stmt, ast.ImportFrom) and stmt.module:
                    for alias in stmt.names:
                        typed[alias.asname or alias.name] = stmt.module
    assert typed == cli_pkg._LAZY_EXPORTS
