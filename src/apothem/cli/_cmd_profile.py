# SPDX-License-Identifier: MIT

"""``apothem profile`` group — show / init / set / edit the shared profile."""

from __future__ import annotations

import click
from rich.markup import escape

from apothem.cli import main
from apothem.cli._common_flags import (
    common_options,
    get_console,
    resolve_format,
)
from apothem.cli._epilogs import (
    _EP_PROFILE_EDIT,
    _EP_PROFILE_INIT,
    _EP_PROFILE_SET,
    _EP_PROFILE_SHOW,
)
from apothem.cli._helpers import (
    _CONTEXT,
    AliasedGroup,
    _CliUserError,
    _emit_expected_error,
    _lifecycle_envelope,
    _load_profile,
    _parse_set_value,
    _placeholder_advisory_entry,
    _placeholder_identity_fields,
    _profile_error,
    _profile_option,
    _profile_scaffold_text,
    _resolve_profile_path,
    _set_nested,
    _write_profile_text_safely,
)
from apothem.cli._json_formatter import emit_json
from apothem.lib.profile import (
    PROFILE_NOT_FOUND_FIX,
    ProfileValidationError,
    validate_profile,
)


@main.group(cls=AliasedGroup, context_settings=_CONTEXT)
def profile() -> None:
    """Manage the shared Apothem profile."""


@profile.command("show", epilog=_EP_PROFILE_SHOW)
@_profile_option
@common_options
def profile_show(
    profile: str | None,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Display the current shared profile."""
    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    profile_path = _resolve_profile_path(profile)

    if not profile_path.exists():
        error = _CliUserError(
            code="profile.not_found",
            message="Apothem validation failed.",
            field="profile",
            reason="profile file does not exist",
            fix=PROFILE_NOT_FOUND_FIX,
        ).to_dict()
        _emit_expected_error(
            command="profile show",
            fmt=fmt,
            profile_path=profile_path,
            error=error,
        )
        return

    try:
        data = _load_profile(profile_path)
    except ProfileValidationError as exc:
        _emit_expected_error(
            command="profile show",
            fmt=fmt,
            profile_path=profile_path,
            error=_profile_error(exc),
        )
        return
    if fmt == "json":
        emit_json(data)
    else:
        con.print_json(data=data)


@profile.command("init", epilog=_EP_PROFILE_INIT)
@_profile_option
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite an existing profile scaffold.",
)
@common_options
def profile_init(
    profile: str | None,
    force: bool,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Create a schema-valid shared profile scaffold."""
    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    profile_path = _resolve_profile_path(profile)

    if profile_path.exists() and not force:
        _emit_expected_error(
            command="profile init",
            fmt=fmt,
            profile_path=profile_path,
            error=_CliUserError(
                code="profile.exists",
                message="Apothem validation failed.",
                field="profile",
                reason="profile file already exists",
                fix="Pass --force to overwrite it or choose another --profile PATH.",
            ).to_dict(),
        )
        return

    try:
        result = _write_profile_text_safely(
            profile_path,
            _profile_scaffold_text(),
            operation="profile_init",
        )
        scaffold_profile = _load_profile(profile_path)
    except _CliUserError as exc:
        _emit_expected_error(
            command="profile init",
            fmt=fmt,
            profile_path=profile_path,
            error=exc.to_dict(),
        )
        return
    except OSError as exc:
        _emit_expected_error(
            command="profile init",
            fmt=fmt,
            profile_path=profile_path,
            error=_CliUserError(
                code="profile.write_failed",
                message="Apothem profile initialization failed.",
                field="profile",
                reason=str(exc),
                fix="Check the profile path and directory permissions.",
            ).to_dict(),
        )
        return
    except ProfileValidationError as exc:
        _emit_expected_error(
            command="profile init",
            fmt=fmt,
            profile_path=profile_path,
            error=_profile_error(exc),
        )
        return

    placeholder_fields = _placeholder_identity_fields(scaffold_profile)
    init_warnings: list[dict[str, object]] = []
    if placeholder_fields:
        init_warnings.append(
            _placeholder_advisory_entry(profile_path, placeholder_fields)
        )

    payload = _lifecycle_envelope(
        status="success",
        command="profile init",
        action="initialized",
        harness=None,
        profile_path=profile_path,
        project_root=None,
        files_written=[str(profile_path)],
        results=[
            {
                **result.to_dict(),
                "message": "schema-valid profile scaffold written",
            }
        ],
        warnings=init_warnings,
        output_path=profile_path,
    )
    if fmt == "json":
        emit_json(payload)
    else:
        con.print(
            f"[green]✓[/] Initialized profile at [cyan]{escape(str(profile_path))}[/]"
        )
        if placeholder_fields:
            named = ", ".join(placeholder_fields)
            con.print(
                f"[yellow]Personalize your profile[/] before installing: the "
                f"identity fields ({escape(named)}) still hold scaffold "
                f"placeholders. Edit [cyan]{escape(str(profile_path))}[/] or run "
                f"'apothem profile set identity.name \"Your Name\"'."
            )


@profile.command("set", epilog=_EP_PROFILE_SET)
@click.argument("key")
@click.argument("value")
@_profile_option
@common_options
def profile_set(
    key: str,
    value: str,
    profile: str | None,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Set a key in the shared profile.

    KEY is a dotted path that descends into the nested profile structure
    (``identity.name``, ``preferences.style``, ``enforcement.sprints``,
    ``harnesses.<harness>.preferences.style``); a single key with no dot
    sets a top-level node. VALUE is stored as a literal string — bare words
    are not coerced (``no`` stays ``"no"``, ``2024-01-01`` and ``1.0`` stay
    strings) — except ``true``/``false`` (the boolean enforcement flags) and
    explicit ``[...]``/``{...}`` list/map input. The fully-assembled profile
    is validated against the packaged schema BEFORE writing; an invalid set is
    refused with the standard diagnostic and the profile on disk is unchanged.
    """
    import yaml

    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    profile_path = _resolve_profile_path(profile)
    profile_path.parent.mkdir(parents=True, exist_ok=True)

    if profile_path.exists():
        # A malformed existing profile must surface as a clean diagnostic, not
        # a raw YAML traceback — and the file on disk is left unchanged (the
        # write happens only after validation below). A non-mapping top-level
        # (e.g. a YAML list) is rejected with the same standard error shape.
        load_error: str | None = None
        try:
            with profile_path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except (yaml.YAMLError, OSError) as exc:
            data, load_error = {}, f"existing profile is not valid YAML: {exc}"
        if load_error is None and not isinstance(data, dict):
            load_error = "existing profile is not a YAML mapping"
        if load_error is not None:
            _emit_expected_error(
                command="profile set",
                fmt=fmt,
                profile_path=profile_path,
                error=_CliUserError(
                    code="profile.unreadable",
                    message="Apothem validation failed.",
                    field="profile",
                    reason=load_error,
                    fix=(
                        "Fix the file at the path above, or re-scaffold it "
                        "with 'apothem profile init --force'."
                    ),
                ).to_dict(),
            )
            return
    else:
        data = {}

    parsed = _parse_set_value(value)
    data = _set_nested(data, key, parsed)

    try:
        validate_profile(data, profile_path=profile_path)
    except ProfileValidationError as exc:
        _emit_expected_error(
            command="profile set",
            fmt=fmt,
            profile_path=profile_path,
            error=_profile_error(exc),
        )
        return

    try:
        _write_profile_text_safely(
            profile_path,
            # sort_keys=False preserves the operator's hand-authored key order,
            # matching the scaffold writer (_helpers.py); the default True would
            # alphabetize and silently reformat the whole profile on every set.
            yaml.safe_dump(data, sort_keys=False),
            operation="profile_set",
        )
    except _CliUserError as exc:
        _emit_expected_error(
            command="profile set",
            fmt=fmt,
            profile_path=profile_path,
            error=exc.to_dict(),
        )
        return

    if fmt == "json":
        emit_json({"action": "set", "key": key, "value": parsed})
    else:
        con.print(f"[green]✓[/] Set [cyan]{escape(key)}[/] = {escape(repr(parsed))}")


@profile.command("edit", epilog=_EP_PROFILE_EDIT)
@_profile_option
@common_options
def profile_edit(
    profile: str | None,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Open the shared profile in the system editor."""
    profile_path = _resolve_profile_path(profile)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    if not profile_path.exists():
        try:
            _write_profile_text_safely(
                profile_path,
                _profile_scaffold_text(),
                operation="profile_edit_init",
            )
        except _CliUserError as exc:
            _emit_expected_error(
                command="profile edit",
                fmt=resolve_format(output_format, json_flag),
                profile_path=profile_path,
                error=exc.to_dict(),
            )
            return
    click.edit(filename=str(profile_path))
    # The editor session is interactive, but --json still owes the caller one
    # parseable document instead of silence.
    if resolve_format(output_format, json_flag) == "json":
        emit_json({"action": "edit", "path": str(profile_path)})
