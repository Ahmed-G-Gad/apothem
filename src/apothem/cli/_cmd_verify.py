# SPDX-License-Identifier: MIT

"""``apothem verify`` — verify a harness adapter installation."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from rich.markup import escape

import apothem.cli as _pkg
from apothem.cli import main
from apothem.cli._common_flags import (
    common_options,
    get_console,
    get_error_console,
    resolve_format,
)
from apothem.cli._epilogs import _EP_VERIFY
from apothem.cli._helpers import (
    _EXIT_EXPECTED,
    _adapter_failure_result,
    _adapter_resolve_output_path,
    _CliUserError,
    _drift_state,
    _emit_expected_error,
    _exclusions_unavailable_entry,
    _harness_option,
    _invoke_with_project,
    _lifecycle_envelope,
    _load_profile,
    _profile_error,
    _profile_option,
    _project_option,
    _resolve_profile_path,
    _resolve_project_root,
)
from apothem.cli._json_formatter import emit_json
from apothem.lib.profile import ProfileValidationError


@main.command(epilog=_EP_VERIFY)
@_harness_option
@_profile_option
@_project_option
@common_options
def verify(
    harness: str,
    profile: str | None,
    project: str | None,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Verify a harness adapter installation.

    Without ``--profile`` the check is structural: every managed target must be
    present and valid. With ``--profile`` the check additionally requires
    profile fidelity, so a present-but-drifted install fails verify — answering
    "is THIS profile faithfully installed?" rather than merely "does it exist?".
    """
    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    profile_path = _resolve_profile_path(profile) if profile is not None else None
    exclusions_warning: dict[str, object] | None = None
    try:
        project_root = _resolve_project_root(project)
        shared_profile: dict[str, Any] | None = (
            _load_profile(profile_path) if profile_path is not None else None
        )
        # Batch selection honors the profile's exclude_harnesses, mirroring
        # the install/update that produced the state: ``verify --harness all``
        # right after a green ``install --harness all`` must not report the
        # excluded harnesses as missing. Without --profile the default
        # profile supplies the excludes; an unreadable or absent default
        # degrades to the full registry. Fidelity checking stays gated on an
        # explicit --profile.
        excludes_profile = shared_profile
        if excludes_profile is None and harness.strip().lower() == "all":
            default_path = _resolve_profile_path(None)
            try:
                excludes_profile = _load_profile(default_path)
            except (ProfileValidationError, OSError) as exc:
                # Dropping the excludes is the only way to keep going, but it
                # re-creates the false failure the excludes prevent — so the
                # fallback is recorded rather than swallowed.
                excludes_profile = None
                exclusions_warning = _exclusions_unavailable_entry(default_path, exc)
        adapters = _pkg._select_and_load_adapters(
            harness,
            project_root,
            shared_profile=excludes_profile,
            apply_excludes=harness.strip().lower() == "all",
        )
    except ProfileValidationError as exc:
        _emit_expected_error(
            command="verify",
            fmt=fmt,
            harness=harness,
            profile_path=profile_path,
            error=_profile_error(exc),
        )
        return
    except _CliUserError as exc:
        _emit_expected_error(
            command="verify",
            fmt=fmt,
            harness=harness,
            profile_path=profile_path,
            error=exc.to_dict(),
            # Dropped excludes can *cause* this error: without them the
            # project-scope harnesses the operator excluded re-enter the
            # selection and demand --project. The advisory rides along so the
            # error names its own cause.
            warnings=([exclusions_warning] if exclusions_warning is not None else None),
        )
        return

    # Printed ahead of the rows so a resulting failure is attributable to the
    # unreadable profile rather than to the harnesses it stopped excluding.
    if exclusions_warning is not None and fmt != "json":
        get_error_console(no_color=no_color).print(
            f"[yellow]![/] {escape(str(exclusions_warning['message']))}"
        )

    results: list[dict[str, object]] = []
    last_output_path: Path | None = None
    all_verified = True
    for harness_id, adapter in adapters:
        output_path = _adapter_resolve_output_path(adapter, project_root)
        last_output_path = output_path
        try:
            installed = bool(
                _invoke_with_project(adapter.is_installed, project=project_root)
            )
            verified_struct = bool(
                _invoke_with_project(adapter.verify, project=project_root)
            )
            drift: str | None = None
            if shared_profile is not None:
                entry = _pkg.get_harness_entry(harness_id)
                drift = _drift_state(
                    entry, adapter, installed, project_root, shared_profile
                )
        except Exception as exc:
            all_verified = False
            failure = _adapter_failure_result(harness_id, "verify", output_path, exc)
            failure["installed"] = False
            failure["verified"] = False
            if shared_profile is not None:
                failure["drift"] = "error"
            results.append(failure)
            if fmt != "json":
                get_error_console(no_color=no_color).print(
                    f"[red]✗[/] [cyan]{harness_id}[/] verify failed: {escape(str(exc))}"
                )
            continue
        # With --profile the verdict is structural presence AND profile
        # fidelity: a present-but-drifted install fails verify so a chosen
        # profile is confirmed faithfully installed, not merely present.
        verified = verified_struct and drift != "drift"
        all_verified = all_verified and verified
        outcome = "unchanged" if verified else "error"
        if not verified_struct:
            message = "managed targets missing or invalid"
        elif drift == "drift":
            message = "managed targets present but drifted from the profile"
        elif shared_profile is not None:
            message = "managed targets verified and profile-faithful"
        else:
            message = "managed targets verified"
        row: dict[str, object] = {
            "harness": harness_id,
            "outcome": outcome,
            "operation": "verify",
            "path": str(output_path),
            "message": message,
            "installed": installed,
            "verified": verified,
        }
        if drift is not None:
            row["drift"] = drift
        results.append(row)
        if fmt != "json":
            if verified:
                con.print(
                    f"[green]✓[/] [cyan]{harness_id}[/] is verified at "
                    f"{escape(str(output_path))}"
                )
            elif verified_struct and drift == "drift":
                con.print(
                    f"[red]✗[/] [cyan]{harness_id}[/] is installed but drifted "
                    f"from the profile at {escape(str(output_path))}"
                )
            else:
                con.print(
                    f"[red]✗[/] [cyan]{harness_id}[/] is NOT verified "
                    f"(expected path: {escape(str(output_path))})"
                )

    if fmt == "json":
        payload = _lifecycle_envelope(
            status="success" if all_verified else "error",
            command="verify",
            action="verified",
            harness=harness,
            profile_path=profile_path,
            project_root=project_root,
            files_written=[],
            results=results,
            warnings=([exclusions_warning] if exclusions_warning is not None else []),
            output_path=last_output_path if len(adapters) == 1 else None,
        )
        if len(results) == 1:
            payload["installed"] = results[0]["installed"]
            payload["verified"] = results[0]["verified"]
        emit_json(payload)

    if not all_verified:
        sys.exit(_EXIT_EXPECTED)
