# SPDX-License-Identifier: MIT

"""Click group plumbing that loads without the materialization stack.

``apothem --version`` and ``apothem --help`` import only this module, Click,
and the JSON helper. The root group (:class:`RootGroup`) knows each command
by name, defining module, and one-line summary (:data:`ROOT_COMMANDS`), and
imports a command's module only when that command runs. The root ``--help``
renders its command list from the summaries, which a unit test keeps equal to
each command's own short help.

Also here, because every group needs them before any command module loads:
the usage-error contract (exit code 64 and a JSON error envelope under
``--json``) in :class:`AliasedGroup`, the shared context settings, and the
Windows UTF-8 stdio setup.
"""

from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any, ClassVar, cast

import click
from click.utils import make_default_short_help

from apothem.cli._json_formatter import emit_json, json_requested

#: Shared Click context settings (``-h`` / ``--help`` aliases) for ``main`` and
#: the ``profile`` / ``harnesses`` sub-groups.
_CONTEXT = {"help_option_names": ["-h", "--help"]}

#: Exit code for a command-line usage error (``EX_USAGE`` from sysexits.h): an
#: unknown option or command, a missing required option, or a bad option
#: value. Distinct from the partial-write code 2, which Click would otherwise
#: reuse for usage errors.
_EXIT_USAGE = 64

#: ``Context.meta`` key holding the root argv, so a usage error raised deep in
#: the command tree can still tell whether JSON output was requested.
_ARGV_META_KEY = "apothem.argv"


def _usage_failure(
    exc: click.UsageError, argv: list[str]
) -> click.UsageError | click.exceptions.Exit:
    """Map a Click usage error onto the CLI contract; return what to raise.

    The error's exit code becomes :data:`_EXIT_USAGE`. Under ``--json`` /
    ``--format json`` the error is written as one JSON error envelope with
    code ``cli.usage`` and an ``Exit`` is returned so Click prints nothing
    else; otherwise the usage error itself is returned for Click to show.
    """
    # exit_code is a class attribute on ClickException; set it on this instance
    # so the original subclass (and its own show()) is kept.
    cast(Any, exc).exit_code = _EXIT_USAGE
    if not json_requested(argv):
        return exc
    from apothem.cli._helpers import _CliUserError, _error_envelope

    ctx = exc.ctx
    names: list[str] = []
    node = ctx
    while node is not None and node.parent is not None:
        names.append(node.info_name or "")
        node = node.parent
    field = "command"
    if isinstance(exc, click.BadParameter) and exc.param is not None:
        field = exc.param.name or field
    elif isinstance(exc, click.NoSuchOption):
        field = exc.option_name
    help_path = ctx.command_path if ctx is not None else "apothem"
    error = _CliUserError(
        code="cli.usage",
        message="Apothem usage error.",
        field=field,
        reason=exc.format_message(),
        fix=f"Run '{help_path} --help' for the accepted options and commands.",
    ).to_dict()
    emit_json(_error_envelope(command=" ".join(reversed(names)) or None, error=error))
    return click.exceptions.Exit(_EXIT_USAGE)


class AliasedGroup(click.Group):
    """Click group that resolves subcommands case-insensitively.

    It also owns the usage-error contract for every command beneath it: a
    usage error exits :data:`_EXIT_USAGE` (64) instead of Click's 2, and under
    JSON output it prints a ``cli.usage`` error envelope instead of plain text.
    """

    def make_context(
        self,
        info_name: str | None,
        args: list[str],
        parent: click.Context | None = None,
        **extra: object,
    ) -> click.Context:
        """Build the context, mapping a parse-time usage error to the contract."""
        argv = list(args)
        try:
            ctx = super().make_context(info_name, args, parent=parent, **extra)
        except click.UsageError as exc:
            root_argv = (
                parent.meta.get(_ARGV_META_KEY, argv) if parent is not None else argv
            )
            raise _usage_failure(exc, root_argv) from None
        ctx.meta.setdefault(_ARGV_META_KEY, argv)
        return ctx

    def invoke(self, ctx: click.Context) -> object:
        """Invoke the subcommand, mapping any usage error to the contract."""
        try:
            return super().invoke(ctx)
        except click.UsageError as exc:
            raise _usage_failure(exc, ctx.meta.get(_ARGV_META_KEY, [])) from None

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Resolve *cmd_name* exactly, then fall back to a case-insensitive match.

        Pre-conditions: ``cmd_name`` is the subcommand token as typed.
        Post-conditions: an exact match wins without any case folding, so
        declared names always take precedence. Otherwise a single
        case-insensitive match is returned; several matches fail the context
        with an ambiguity message rather than silently picking one, and no match
        returns ``None`` so Click emits its own unknown-command error.
        """
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd
        lower = cmd_name.lower()
        matches = [n for n in self.list_commands(ctx) if n.lower() == lower]
        if len(matches) == 1:
            return super().get_command(ctx, matches[0])
        if len(matches) > 1:
            ctx.fail(f"Ambiguous command {cmd_name!r}: matches {sorted(matches)}")
        return None


@dataclass(frozen=True)
class LazyCommand:
    """Where a root command is defined, and the summary its help line shows.

    ``summary`` is the first sentence of the command's docstring; the root
    ``--help`` passes it through Click's own short-help shortening.
    """

    module: str
    summary: str
    hidden: bool = False


_INSTALL = "apothem.cli._cmd_install"
_UPDATE = "apothem.cli._cmd_update"
_UNINSTALL = "apothem.cli._cmd_uninstall"

#: Every root command, keyed by the name it is invoked as.
ROOT_COMMANDS: Mapping[str, LazyCommand] = {
    "completion": LazyCommand(
        "apothem.cli._cmd_completion",
        "Print a shell-completion script for SHELL to stdout.",
    ),
    "diff": LazyCommand(
        "apothem.cli._cmd_diff",
        "Preview the pending configuration changes for a single harness.",
    ),
    "doctor": LazyCommand(
        "apothem.cli._cmd_doctor",
        "Check the installed harnesses and the shared profile; exit 1 on any failure.",
    ),
    "harnesses": LazyCommand(
        "apothem.cli._cmd_harnesses",
        "List and inspect registered harness adapters.",
    ),
    "install": LazyCommand(_INSTALL, "Install a harness adapter configuration."),
    "quickstart": LazyCommand(
        _INSTALL,
        "Guided first run: ensure a profile, preview the writes, then install.",
    ),
    "Installing": LazyCommand(
        _INSTALL, "Alias for install (continuous form).", hidden=True
    ),
    "installing": LazyCommand(
        _INSTALL, "Alias for install (continuous form).", hidden=True
    ),
    "migrate-workspace": LazyCommand(
        "apothem.cli._cmd_migrate_workspace",
        "Migrate a legacy per-harness workspace into the shared ``.apothem`` layout.",
    ),
    "profile": LazyCommand(
        "apothem.cli._cmd_profile", "Manage the shared Apothem profile."
    ),
    "rollback": LazyCommand(
        _UPDATE, "Restore a harness to the state before its recorded install."
    ),
    "status": LazyCommand(
        "apothem.cli._cmd_status",
        "Report install, verify, and drift state for every registered harness.",
    ),
    "uninstall": LazyCommand(_UNINSTALL, "Remove a harness adapter configuration."),
    "Uninstalling": LazyCommand(
        _UNINSTALL, "Alias for uninstall (continuous form).", hidden=True
    ),
    "uninstalling": LazyCommand(
        _UNINSTALL, "Alias for uninstall (continuous form).", hidden=True
    ),
    "update": LazyCommand(
        _UPDATE, "Re-install a harness adapter configuration from the current profile."
    ),
    "Updating": LazyCommand(
        _UPDATE, "Alias for update (continuous form).", hidden=True
    ),
    "updating": LazyCommand(
        _UPDATE, "Alias for update (continuous form).", hidden=True
    ),
    "verify": LazyCommand(
        "apothem.cli._cmd_verify", "Verify a harness adapter installation."
    ),
}


class RootGroup(AliasedGroup):
    """The root ``apothem`` group: commands load on first use.

    A command module registers its commands on ``main`` when imported (its
    ``@main.command`` decorators run), so loading a command is importing its
    module. ``--version`` loads none, and ``--help`` renders the command list
    from :data:`ROOT_COMMANDS` without importing any.
    """

    lazy_commands: ClassVar[Mapping[str, LazyCommand]] = ROOT_COMMANDS

    def list_commands(self, ctx: click.Context) -> list[str]:
        """Return every root command name, loaded or not, sorted."""
        return sorted({*self.commands, *self.lazy_commands})

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Import the module behind *cmd_name* (any letter case), then resolve it."""
        lower = cmd_name.lower()
        for name, spec in self.lazy_commands.items():
            if name.lower() == lower and name not in self.commands:
                importlib.import_module(spec.module)
        return super().get_command(ctx, cmd_name)

    def format_commands(
        self, ctx: click.Context, formatter: click.HelpFormatter
    ) -> None:
        """Write the Commands section without importing any command module.

        Mirrors :meth:`click.Group.format_commands`: hidden commands are
        skipped and each summary is shortened to the same width limit.
        """
        rows: list[tuple[str, str]] = []
        names = [name for name in self.list_commands(ctx) if not self._hidden(name)]
        if not names:
            return
        limit = formatter.width - 6 - max(len(name) for name in names)
        for name in names:
            command = self.commands.get(name)
            if command is not None:
                rows.append((name, command.get_short_help_str(limit)))
            else:
                summary = self.lazy_commands[name].summary
                rows.append((name, make_default_short_help(summary, limit).strip()))
        with formatter.section("Commands"):
            formatter.write_dl(rows)

    def _main_shell_completion(
        self,
        ctx_args: MutableMapping[str, Any],
        prog_name: str,
        complete_var: str | None = None,
    ) -> None:
        """Load the completion module before Click answers a completion request.

        That module registers the PowerShell completion class, which Click looks
        up by shell name; with commands loading lazily it would otherwise be
        missing. The check mirrors Click's own: only when the completion
        environment variable is set.
        """
        name = complete_var or f"_{prog_name}_COMPLETE".replace("-", "_").upper()
        if os.environ.get(name):
            importlib.import_module("apothem.cli._cmd_completion")
        super()._main_shell_completion(ctx_args, prog_name, complete_var)

    def _hidden(self, name: str) -> bool:
        command = self.commands.get(name)
        if command is not None:
            return command.hidden
        return self.lazy_commands[name].hidden


def _configure_stdio() -> None:
    """Force UTF-8 stdio on Windows so Rich output renders correctly.

    Runs at CLI invocation only — never at import time — so it cannot
    disturb a host process's captured streams. ``reconfigure`` mutates
    the existing stream in place rather than replacing ``sys.stdout``,
    which would orphan and later close a wrapping process's buffer
    (e.g. pytest's capture buffer).
    """
    if sys.platform != "win32":
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
