# SPDX-License-Identifier: MIT

"""Shared Click options + console factory for the apothem CLI.

Every subcommand in :mod:`apothem.cli` decorates itself with
:func:`common_options` to receive the standard cross-subcommand flag set:
``--quiet/-q``, ``--verbose/-v``, ``--format``, ``--no-color``, ``--json``
(shorthand for ``--format json``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import click
from rich.console import Console


def common_options(f: Callable[..., Any]) -> Callable[..., Any]:
    """Apply the standard cross-subcommand flag set to *f*.

    Click stacks decorators bottom-up, so the order in which the
    options appear in ``--help`` output is the *reverse* of the order
    they are applied here. To get ``--quiet, --verbose, --format,
    --no-color, --json`` in that visible order, the decorators below
    are applied in reverse.
    """
    f = click.option(
        "--json",
        "json_flag",
        is_flag=True,
        default=False,
        help="Shorthand for --format json.",
    )(f)
    f = click.option(
        "--no-color",
        is_flag=True,
        default=False,
        help="Disable ANSI color codes in output.",
    )(f)
    f = click.option(
        "--format",
        "output_format",
        type=click.Choice(["plain", "json"], case_sensitive=False),
        default="plain",
        show_default=True,
        help="Output format.",
    )(f)
    f = click.option(
        "--verbose",
        "-v",
        is_flag=True,
        default=False,
        help="Emit additional diagnostic output.",
    )(f)
    return click.option(
        "--quiet",
        "-q",
        is_flag=True,
        default=False,
        help="Suppress informational output; only errors are emitted.",
    )(f)


def get_console(no_color: bool = False, quiet: bool = False) -> Console:
    """Return a Rich :class:`Console` honoring ``--no-color`` and ``--quiet``.

    ``soft_wrap=True`` keeps each printed message on one logical line. When
    stdout is not a terminal, Rich assumes 80 columns and would otherwise break
    a long path across lines, so a piped or logged path could not be copied.
    A terminal still wraps long lines visually; tables keep their layout.
    """
    if quiet:
        return Console(highlight=False, quiet=True, soft_wrap=True)
    if no_color:
        return Console(highlight=False, no_color=True, soft_wrap=True)
    return Console(highlight=False, soft_wrap=True)


def get_error_console(no_color: bool = False) -> Console:
    """Return a Rich error :class:`Console` that writes to stderr and is never quiet.

    ``--quiet`` suppresses informational output but the documented contract is
    that errors are still emitted; an error console that ignores ``quiet`` and
    targets stderr (the conventional error stream) honors that contract so a
    batch failure under ``-q`` is never silent.
    """
    return Console(stderr=True, highlight=False, no_color=no_color, soft_wrap=True)


def resolve_format(output_format: str, json_flag: bool) -> str:
    """Return ``"json"`` when ``--json`` is set or ``--format json`` was chosen, else ``"plain"``."""
    if json_flag:
        return "json"
    return output_format
