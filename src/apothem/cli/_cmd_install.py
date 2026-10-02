# SPDX-License-Identifier: MIT

"""``apothem install`` + ``quickstart`` + the continuous-form aliases."""

from __future__ import annotations

import click
from rich.markup import escape

import apothem.cli as _pkg
from apothem.cli import main
from apothem.cli._common_flags import (
    common_options,
    get_console,
    resolve_format,
)
from apothem.cli._epilogs import (
    _EP_INSTALL,
    _EP_QUICKSTART,
)
from apothem.cli._helpers import (
    _CliUserError,
    _complete_harness,
    _emit_expected_error,
    _harness_option,
    _load_profile,
    _placeholder_identity_fields,
    _profile_error,
    _profile_option,
    _profile_scaffold_text,
    _project_option,
    _resolve_profile_path,
    _write_profile_text_safely,
)
from apothem.cli._json_formatter import emit_json
from apothem.cli._materialize import _materialize
from apothem.lib.profile import ProfileValidationError


@main.command(epilog=_EP_INSTALL)
@_harness_option
@_profile_option
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview install without writing files.",
)
@click.option(
    "--clean",
    "--fresh",
    "clean",
    is_flag=True,
    help="Opt-in clean slate: back up and remove the prior install state "
    "(~/.claude, ~/.codex, ~/.agents, ~/.config/apothem) before installing.",
)
@click.option(
    "--yes",
    "assume_yes",
    is_flag=True,
    help="Skip per-target confirmation during a clean-slate removal "
    "(required for non-interactive --clean runs).",
)
@_project_option
@common_options
def install(
    harness: str,
    profile: str | None,
    dry_run: bool,
    clean: bool,
    assume_yes: bool,
    project: str | None,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Install a harness adapter configuration."""
    _materialize(
        harness,
        profile,
        dry_run,
        "install",
        "Installed",
        fmt=resolve_format(output_format, json_flag),
        quiet=quiet,
        no_color=no_color,
        project=project,
        clean=clean,
        assume_yes=assume_yes,
        verbose=verbose,
        create_default_profile=True,
    )


@main.command(epilog=_EP_QUICKSTART)
@click.option(
    "--harness",
    default="all",
    metavar="NAME",
    help="Harness adapter name or 'all' for every supported harness (default: all).",
    shell_complete=_complete_harness,
)
@_profile_option
@click.option(
    "--yes",
    "assume_yes",
    is_flag=True,
    help="Run the full guided sequence non-interactively (skip every prompt).",
)
@click.option(
    "--project",
    default=".",
    metavar="PATH",
    help="Project root for project-scope harnesses (default: current directory).",
)
@common_options
def quickstart(
    harness: str,
    profile: str | None,
    assume_yes: bool,
    project: str | None,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Guided first run: ensure a profile, preview the writes, then install.

    Walks a new operator through the canonical path in one linear flow — create a
    starter profile if none exists (with a personalize nudge), preview the files
    each harness will write (project root vs your home directory), confirm, then
    install with the grouped capability-note output — and ends with the
    recommended next commands. ``--yes`` runs the whole sequence
    non-interactively; ``--format json`` emits one structured summary of every
    step. It composes the install building blocks; it does not duplicate them.
    """
    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    profile_path = _resolve_profile_path(profile)
    steps: list[dict[str, object]] = []

    # Step 1 — ensure a profile exists (offer to scaffold one if it is missing).
    created = False
    if not profile_path.is_file():
        may_create = assume_yes or fmt == "json" or not _pkg._stdin_is_interactive()
        if not may_create:
            may_create = click.confirm(
                f"No profile at {profile_path}. Create a starter profile?",
                default=True,
            )
        if not may_create:
            _emit_expected_error(
                command="quickstart",
                fmt=fmt,
                harness=harness,
                profile_path=profile_path,
                error=_CliUserError(
                    code="profile.required",
                    message="Apothem quickstart needs a profile.",
                    field="profile",
                    reason="no profile exists and creation was declined",
                    fix="Run 'apothem profile init', or re-run quickstart and "
                    "accept profile creation.",
                ).to_dict(),
            )
            return
        try:
            _write_profile_text_safely(
                profile_path, _profile_scaffold_text(), operation="quickstart"
            )
        except _CliUserError as exc:
            _emit_expected_error(
                command="quickstart",
                fmt=fmt,
                harness=harness,
                profile_path=profile_path,
                error=exc.to_dict(),
            )
            return
        except OSError as exc:
            _emit_expected_error(
                command="quickstart",
                fmt=fmt,
                harness=harness,
                profile_path=profile_path,
                error=_CliUserError(
                    code="profile.write_failed",
                    message="Apothem quickstart could not create a profile.",
                    field="profile",
                    reason=str(exc),
                    fix="Check the profile path and directory permissions.",
                ).to_dict(),
            )
            return
        created = True

    try:
        placeholder = _placeholder_identity_fields(_load_profile(profile_path))
    except ProfileValidationError as exc:
        _emit_expected_error(
            command="quickstart",
            fmt=fmt,
            harness=harness,
            profile_path=profile_path,
            error=_profile_error(exc),
        )
        return
    if fmt != "json" and created:
        con.print(
            f"[green]✓[/] Created a starter profile at "
            f"[cyan]{escape(str(profile_path))}[/]"
        )
        if placeholder:
            named = ", ".join(placeholder)
            con.print(
                f"[yellow]Personalize[/] the identity ({named}) — edit the "
                f"profile or run 'apothem profile set identity.name \"Your Name\"'."
            )
    steps.append(
        {
            "step": "profile",
            "outcome": "created" if created else "existing",
            "path": str(profile_path),
            "placeholder_identity": placeholder,
        }
    )

    # The recommended follow-up must actually run: a project-scope selection
    # (a named project-scope harness as much as ``all``) needs --project, and
    # it should name the root the operator just installed into.
    verify_cmd = f"apothem verify --harness {harness}"
    requested = harness.strip().lower()
    try:
        needs_project = (
            requested == "all" or _pkg.get_harness_entry(requested).scope == "project"
        )
    except KeyError:
        needs_project = False
    if needs_project:
        verify_cmd += f" --project {project}" if project else " --project ."
    recommended = [verify_cmd, "apothem doctor"]

    # Steps 2-4 — preview + confirm + install, composed from the install path
    # (blast-radius preview/confirm, placeholder advisory, and grouped notes all
    # live in ``_materialize``; quickstart never reimplements them).
    if fmt == "json":
        sink: list[dict[str, object]] = []
        _materialize(
            harness,
            profile,
            False,
            "install",
            "Installed",
            fmt="json",
            quiet=quiet,
            no_color=no_color,
            project=project,
            assume_yes=assume_yes,
            verbose=verbose,
            payload_sink=sink,
        )
        if not sink:
            # The install step failed; ``_materialize`` already emitted the error
            # envelope (one JSON document) — do not emit a second.
            return
        install_payload = sink[0]
        steps.append(
            {
                "step": "install",
                "status": install_payload.get("status"),
                "harness": harness,
                "files_written": install_payload.get("files_written"),
                "warnings": install_payload.get("warnings"),
                "results": install_payload.get("results"),
            }
        )
        steps.append({"step": "recommend", "next": recommended})
        emit_json(
            {
                "status": install_payload.get("status", "success"),
                "command": "quickstart",
                "profile_path": str(profile_path),
                "steps": steps,
                "recommended_next": recommended,
            }
        )
        return

    _materialize(
        harness,
        profile,
        False,
        "install",
        "Installed",
        fmt="plain",
        quiet=quiet,
        no_color=no_color,
        project=project,
        assume_yes=assume_yes,
        verbose=verbose,
    )
    if not quiet:
        con.print("\n[bold]Recommended next step:[/]")
        con.print(f"  Confirm the install:  [cyan]{escape(recommended[0])}[/]")
        con.print(f"  Check system health:  [cyan]{escape(recommended[1])}[/]")


def _make_installing_alias(name: str) -> click.Command:
    """Build the ``Installing`` / ``installing`` continuous-form alias."""

    @click.command(name=name, epilog=_EP_INSTALL, hidden=True)
    @_harness_option
    @_profile_option
    @click.option(
        "--dry-run",
        is_flag=True,
        help="Preview install without writing files.",
    )
    @click.option(
        "--clean",
        "--fresh",
        "clean",
        is_flag=True,
        help="Opt-in clean slate: back up and remove the prior install state "
        "(~/.claude, ~/.codex, ~/.agents, ~/.config/apothem) before installing.",
    )
    @click.option(
        "--yes",
        "assume_yes",
        is_flag=True,
        help="Skip per-target confirmation during a clean-slate removal "
        "(required for non-interactive --clean runs).",
    )
    @_project_option
    @common_options
    def _alias(
        harness: str,
        profile: str | None,
        dry_run: bool,
        clean: bool,
        assume_yes: bool,
        project: str | None,
        quiet: bool,
        verbose: bool,
        output_format: str,
        no_color: bool,
        json_flag: bool,
    ) -> None:
        """Alias for install (continuous form). Identical behavior."""
        _materialize(
            harness,
            profile,
            dry_run,
            "install",
            "Installed",
            fmt=resolve_format(output_format, json_flag),
            quiet=quiet,
            no_color=no_color,
            project=project,
            clean=clean,
            assume_yes=assume_yes,
            verbose=verbose,
            create_default_profile=True,
        )

    return _alias


main.add_command(_make_installing_alias("Installing"))


main.add_command(_make_installing_alias("installing"))
