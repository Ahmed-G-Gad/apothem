# SPDX-License-Identifier: MIT

"""``apothem completion`` — emit a sourceable shell-completion script."""

from __future__ import annotations

import os

import click
from click.shell_completion import (
    CompletionItem,
    ShellComplete,
    add_completion_class,
    get_completion_class,
    split_arg_string,
)

from apothem.cli import main
from apothem.cli._epilogs import _EP_COMPLETION

_NATIVE_COMPLETION_SHELLS: tuple[str, ...] = ("bash", "zsh", "fish")


_COMPLETION_SHELLS: tuple[str, ...] = (*_NATIVE_COMPLETION_SHELLS, "powershell")


_COMPLETION_PROG_NAME = "apothem"


_COMPLETION_COMPLETE_VAR = "_APOTHEM_COMPLETE"


class _PowerShellComplete(ShellComplete):
    """PowerShell completion over Click's env-var protocol.

    Click ships no PowerShell completion class, so this one closes the loop
    the emitted script drives: ``Register-ArgumentCompleter`` invokes the
    program with ``%(complete_var)s=powershell_complete``, passing the whole
    command line in ``COMP_WORDS`` and the CHARACTER cursor offset in
    ``COMP_CWORD`` (unlike bash, where ``COMP_CWORD`` is a word index).
    Responses are ``type,value,help`` lines the script maps to
    ``CompletionResult`` objects.
    """

    name = "powershell"
    source_template = """\
# Apothem shell completion for PowerShell.
# Append to your PowerShell profile ($PROFILE) to enable, then restart the shell:
#   apothem completion powershell >> $PROFILE
Register-ArgumentCompleter -Native -CommandName %(prog_name)s -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $env:%(complete_var)s = "powershell_complete"
    $env:COMP_WORDS = $commandAst.ToString()
    $env:COMP_CWORD = $cursorPosition
    try {
        %(prog_name)s | ForEach-Object {
            $type, $value, $help = $_ -split ",", 3
            if ($value) {
                $tooltip = if ($help) { $help } else { $value }
                [System.Management.Automation.CompletionResult]::new(
                    $value, $value, 'ParameterValue', $tooltip
                )
            }
        }
    } finally {
        Remove-Item Env:%(complete_var)s
        Remove-Item Env:COMP_WORDS
        Remove-Item Env:COMP_CWORD
    }
}
"""

    def get_completion_args(self) -> tuple[list[str], str]:
        """Return ``(args, incomplete)`` parsed from the PowerShell handshake.

        Pre-conditions: the completion script exports ``COMP_WORDS`` (the whole
        command line) and ``COMP_CWORD`` (the cursor offset). A missing or
        non-integer ``COMP_CWORD`` falls back to end-of-line, so completion
        degrades to whole-line parsing rather than raising.

        Post-conditions: ``args`` excludes the program name. The final token
        becomes ``incomplete`` only when the cursor sits directly against it —
        a trailing space means the operator finished that word and wants the
        next argument's candidates instead.
        """
        command_line = os.environ.get("COMP_WORDS", "")
        try:
            cursor = int(os.environ.get("COMP_CWORD", ""))
        except ValueError:
            cursor = len(command_line)
        text = command_line[:cursor]
        words = split_arg_string(text)
        args = words[1:] if words else []
        incomplete = ""
        if args and text and not text[-1].isspace():
            incomplete = args.pop()
        return args, incomplete

    def format_completion(self, item: CompletionItem) -> str:
        """Render one completion candidate as a single comma-joined line.

        Post-conditions: returns ``type,value,help`` with an empty trailing
        field when the item carries no help text.
        """
        # One completion per line; the script splits on the first two commas,
        # so a help text containing commas survives intact.
        return f"{item.type},{item.value},{item.help or ''}"


add_completion_class(_PowerShellComplete)


@main.command(epilog=_EP_COMPLETION)
@click.argument(
    "shell",
    type=click.Choice(_COMPLETION_SHELLS, case_sensitive=False),
)
def completion(shell: str) -> None:
    """Print a shell-completion script for SHELL to stdout.

    Supported shells: bash, zsh, fish, powershell. Every script is generated
    by Click's env-var completion protocol — PowerShell through the
    completion class registered above, since Click ships none natively.
    Enabling completion is opt-in: this command only prints the script — pipe
    or append it to the shell's completion file yourself (see ``--help``).
    """
    target = shell.lower()
    completion_cls = get_completion_class(target)
    if completion_cls is None:  # pragma: no cover - guarded by click.Choice
        raise click.ClickException(
            f"Completion is not supported for {shell!r}. "
            f"Supported shells: {', '.join(_COMPLETION_SHELLS)}."
        )
    comp = completion_cls(main, {}, _COMPLETION_PROG_NAME, _COMPLETION_COMPLETE_VAR)
    click.echo(comp.source())
