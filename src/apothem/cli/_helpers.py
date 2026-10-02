# SPDX-License-Identifier: MIT

"""Shared helpers, constants, and the ``AliasedGroup`` for the apothem CLI.

Carries the cross-command building blocks the per-command modules consume:
the structured CLI-error type, the adapter protocol + load helpers, the
profile read/write helpers, the lifecycle-envelope builders, harness
selection, project-root resolution, and the drift/plan helpers. Extracted
verbatim from the former monolithic ``cli/__init__.py``; the patchable-helper
call sites inside selection/load helpers resolve through the ``apothem.cli``
package (``_pkg``) so the test patch seams keep landing."""

from __future__ import annotations

import inspect
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, cast

import click
from click.shell_completion import CompletionItem
from rich.console import Console
from rich.markup import escape

import apothem.cli as _pkg
from apothem.cli._json_formatter import emit_json, json_requested
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import (
    MaterializationError,
    MaterializationResult,
    MaterializationRun,
    check_fidelity,
    fidelity_is_faithful,
    write_bytes_safely,
)
from apothem.lib.harness_registry import (
    SUPPORTED_HARNESS_IDS,
    HarnessRegistryEntry,
    iter_harness_entries,
    load_adapter_class,
)
from apothem.lib.profile import (
    ProfileValidationError,
    current_schema_version,
    load_profile_file,
    other_problem_lines,
    resolve_profile_path,
)
from apothem.schemas import profile_minimal_path, profile_schema_path

#: Shared Click context settings (``-h`` / ``--help`` aliases) for ``main`` and
#: the ``profile`` / ``harnesses`` sub-groups.
_CONTEXT = {"help_option_names": ["-h", "--help"]}


_ADAPTER_LOAD_ERRORS = (ImportError, AttributeError, TypeError, OSError)


_EXIT_EXPECTED = 1


_EXIT_PARTIAL = 2


#: Exit code for a command-line usage error (``EX_USAGE`` from sysexits.h): an
#: unknown option or command, a missing required option, or a bad option
#: value. Distinct from the partial-write code 2, which Click would otherwise
#: reuse for usage errors.
_EXIT_USAGE = 64

#: ``Context.meta`` key holding the root argv, so a usage error raised deep in
#: the command tree can still tell whether JSON output was requested.
_ARGV_META_KEY = "apothem.argv"


def _status_for_exit_code(exit_code: int) -> str:
    """Map a lifecycle exit code to its envelope status string.

    Zero is a clean ``success``; the partial-batch code is ``partial``; every
    other non-zero code is ``error``. The single source of truth for the
    exit-code-to-status projection the batch lifecycle commands share.
    """
    return (
        "success"
        if exit_code == 0
        else ("partial" if exit_code == _EXIT_PARTIAL else "error")
    )


class _CliUserError(Exception):
    """Expected operator-facing CLI failure."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        field: str,
        reason: str,
        fix: str,
        safe_value: object | None = None,
        files_written: tuple[str, ...] = (),
    ) -> None:
        """Capture the structured payload behind an operator-facing failure.

        Pre-conditions: ``code`` is the stable machine-readable identifier;
        ``message`` is the human sentence; ``field`` names the offending input;
        ``reason`` says why it was rejected; ``fix`` states the corrective
        action. ``safe_value`` carries a redacted echo of the input when one can
        be shown without leaking a secret, and ``files_written`` lists any paths
        already written before the failure, so a partial run is recoverable
        rather than silently half-applied.

        Post-conditions: ``message`` is passed to ``Exception`` so the plain
        string surfaces in a traceback; every field is also retained for
        :meth:`to_dict`.
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.reason = reason
        self.fix = fix
        self.safe_value = safe_value
        self.files_written = files_written

    def to_dict(self) -> dict[str, object]:
        """Return the machine-readable error object."""
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "reason": self.reason,
            "fix": self.fix,
            "safe_value": self.safe_value,
            "files_written": list(self.files_written),
        }


class _Adapter(Protocol):
    """Structural protocol for a harness adapter as the CLI consumes it.

    The lifecycle surface every registered adapter is resolved against:
    identity (:attr:`name`, :attr:`output_path`), the ``install`` / ``update``
    / ``uninstall`` mutators, and the ``is_installed`` / ``verify`` probes.
    Project-scope adapters additionally opt into the extension below via
    ``requires_project`` (see :func:`_adapter_requires_project`).
    """

    @property
    def name(self) -> str:
        """The adapter's registry key, as the operator types it on the CLI."""
        ...

    @property
    def output_path(self) -> Path:
        """Absolute path of the harness's primary configuration target."""
        ...

    def install(self, profile: dict[str, Any]) -> object:
        """Materialize *profile* into this harness's native configuration."""
        ...

    def update(self, profile: dict[str, Any]) -> object:
        """Re-materialize *profile* over an existing installation."""
        ...

    def uninstall(self) -> None:
        """Remove every artifact this adapter installed, leaving no orphans."""
        ...

    def is_installed(self) -> bool:
        """Return True when this harness carries an Apothem installation."""
        ...

    def verify(self) -> bool:
        """Return True when the installed surface still matches the profile."""
        ...

    # Optional project-scope extension (opt-in per adapter). Adapters
    # that materialize into a project root rather than a user-scope
    # configuration root declare ``requires_project = True`` and accept
    # an optional ``project: Path | None`` keyword argument on their
    # lifecycle methods. The CLI threads the operator-supplied
    # ``--project <path>`` value through ``_materialize`` and routes it
    # to the adapter only when the adapter's signature accepts it (via
    # ``_invoke_with_project`` introspection).
    requires_project: bool


def _adapter_requires_project(adapter: _Adapter) -> bool:
    """Return True iff *adapter* opts into the project-scope contract.

    The opt-in is the literal boolean ``True`` on the ``requires_project``
    attribute. Truthy non-boolean values (e.g., ``MagicMock`` instances
    in unit-test fixtures, sentinel objects from incomplete adapter
    stubs) do not satisfy the opt-in — explicit ratification is required.
    """
    return getattr(adapter, "requires_project", False) is True


def _adapter_resolve_output_path(adapter: _Adapter, project: Path | None) -> Path:
    """Resolve the adapter's output path, threading *project* when supported.

    Project-scope adapters expose a ``resolve_output_path(project)``
    method whose return is the concrete on-disk target under the
    operator-supplied project root. Adapters without that method fall
    back to the static ``output_path`` property — appropriate for
    user-scope adapters whose target is determined by the harness's
    home-rooted configuration directory.
    """
    resolve_fn = getattr(adapter, "resolve_output_path", None)
    if callable(resolve_fn):
        return cast(Path, resolve_fn(project))
    return adapter.output_path


def _stdin_is_interactive() -> bool:
    """Whether an interactive confirmation may be prompted (a TTY is attached).

    A dedicated seam (rather than an inline ``sys.stdin.isatty()``) so the
    blast-radius confirmation gate is exercisable under the test runner, where
    stdin is a replayed stream rather than a terminal.
    """
    return sys.stdin.isatty()


def _path_is_within(target: Path, root: Path) -> bool:
    """Return True iff *target* resolves inside *root* (lexical containment)."""
    try:
        target.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _partition_blast_radius(
    adapters: list[tuple[str, _Adapter]],
    project_root: Path | None,
) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
    """Split adapter targets into (under-project, outside-project/home-rooted).

    Project-scope adapters materialize under the supplied ``--project`` root;
    user-scope adapters materialize under the operator's real home directory,
    i.e. outside that root. The partition is by concrete on-disk containment so
    the disclosure stays truthful even if a home target happens to fall inside
    an unusual project root.
    """
    within: list[tuple[str, Path]] = []
    outside: list[tuple[str, Path]] = []
    for harness_id, adapter in adapters:
        target = _adapter_resolve_output_path(adapter, project_root)
        if project_root is not None and _path_is_within(target, project_root):
            within.append((harness_id, target))
        else:
            outside.append((harness_id, target))
    return within, outside


def _render_blast_radius(
    con: Console,
    within: list[tuple[str, Path]],
    outside: list[tuple[str, Path]],
    project_root: Path | None,
) -> None:
    """Print the pre-write disclosure: targets grouped by project vs home root."""
    total = len(within) + len(outside)
    con.print(f"[bold]Apothem will write {total} configuration file(s):[/]")
    width = max((len(hid) for hid, _ in [*within, *outside]), default=0)
    if within:
        con.print(f"  [cyan]Under the project root[/] ({escape(str(project_root))}):")
        for harness_id, target in within:
            con.print(f"    {harness_id.ljust(width)}  -> {escape(str(target))}")
    if outside:
        con.print("  [yellow]Under your home directory[/] (outside --project):")
        for harness_id, target in outside:
            con.print(f"    {harness_id.ljust(width)}  -> {escape(str(target))}")


_PLACEHOLDER_IDENTITY: dict[str, str] = {
    "name": "Example User",
    "email": "dev@example.invalid",
    "website": "https://example.invalid",
    "github": "example-user",
}


def _placeholder_identity_fields(profile: dict[str, Any]) -> list[str]:
    """Return the identity fields still set to their shipped placeholder value."""
    identity = profile.get("identity")
    if not isinstance(identity, dict):
        return []
    return [
        field
        for field, placeholder in _PLACEHOLDER_IDENTITY.items()
        if str(identity.get(field, "")).strip() == placeholder
    ]


def _placeholder_advisory_entry(
    profile_path: Path, fields: list[str]
) -> dict[str, object]:
    """Build the lifecycle-envelope advisory for an unpersonalized identity."""
    return {
        "harness": None,
        "outcome": "advisory",
        "operation": "placeholder_identity",
        "path": str(profile_path),
        "fields": list(fields),
        "message": (
            "Profile identity is still the scaffold placeholder ("
            + ", ".join(fields)
            + "); personalize it so a real identity is projected. Edit the "
            + "profile or run 'apothem profile set identity.name \"Your Name\"'."
        ),
    }


def _baseline_unavailable_entry(
    profile_path: Path, exc: ProfileValidationError
) -> dict[str, object]:
    """Build the lifecycle-envelope advisory for an unreadable drift baseline.

    ``status`` degrades drift rather than aborting when the default profile
    will not load, which is right — the installed/verified facts stay
    reportable. But the degradation needs its own channel: the ``unknown``
    drift cell is only emitted for an *installed* harness, so with nothing
    installed every cell reads ``absent`` and the broken baseline leaves no
    trace at all. This advisory carries the path, the parse failure, and the
    fix, so a degraded sweep is never mistaken for a clean one.
    """
    diagnostic = exc.diagnostic
    return {
        "harness": None,
        "outcome": "advisory",
        "operation": "drift_baseline_unavailable",
        "path": str(profile_path),
        "code": diagnostic.code,
        # `reason` stays its own field rather than being inlined: a YAML
        # syntax failure renders as a multi-line parser dump, which would
        # make the one-line terminal advisory unreadable.
        "reason": diagnostic.reason,
        "fix": diagnostic.fix,
        "message": (
            f"Drift baseline unavailable: {profile_path} could not be loaded "
            f"({diagnostic.code}). Drift reads 'unknown' for installed "
            f"harnesses; installed and verified are unaffected. "
            f"{diagnostic.fix}"
        ),
    }


def _exclusions_unavailable_entry(
    profile_path: Path, exc: Exception
) -> dict[str, object]:
    """Build the lifecycle-envelope advisory for dropped harness exclusions.

    ``verify --harness all`` loads the default profile solely to honour
    ``exclude_harnesses``. Falling back to the full registry when that load
    fails re-creates exactly the false failure the honouring exists to
    prevent: an excluded harness is swept, reports its managed targets
    missing, and verify exits non-zero blaming the harness rather than the
    unreadable profile. Silent, that verdict is unattributable.

    The caller also catches ``OSError``, which carries no diagnostic, so the
    fields degrade to the exception text rather than assuming one.
    """
    if isinstance(exc, ProfileValidationError):
        diagnostic = exc.diagnostic
        code, reason, fix = diagnostic.code, diagnostic.reason, diagnostic.fix
    else:
        code = "profile.unreadable"
        reason = str(exc)
        fix = "Make the profile readable so its exclusions apply."
    return {
        "harness": None,
        "outcome": "advisory",
        "operation": "exclusions_unavailable",
        "path": str(profile_path),
        "code": code,
        "reason": reason,
        "fix": fix,
        "message": (
            f"Harness exclusions unavailable: {profile_path} could not be "
            f"loaded ({code}). Every registered harness was verified, so a "
            f"harness excluded in that profile can report as missing and "
            f"fail the run. {fix}"
        ),
    }


def _invoke_with_project(
    fn: Callable[..., object], *args: object, project: Path | None
) -> object:
    """Invoke *fn* passing ``project=`` only when its signature accepts it.

    Backward-compatible bridge: existing user-scope adapters declare
    ``install(self, profile)`` / ``uninstall(self)`` and do not accept
    a ``project`` parameter. Project-scope adapters declare
    ``install(self, profile, project=None)`` and similar. Introspection
    via ``inspect.signature`` lets the CLI thread the operator-supplied
    project root to the adapters that consume it without breaking the
    older signatures.
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn(*args)
    if "project" in sig.parameters:
        return fn(*args, project=project)
    return fn(*args)


def _all_adapters() -> tuple[list[_Adapter], list[dict[str, str]]]:
    """Return instances of all registered harness adapters plus load failures.

    A broken adapter is returned as a failure record rather than printed
    here: the caller decides how to surface it (a JSON error row or the
    fmt-aware console), so the warning respects --quiet/--no-color and
    never leaks styled text into JSON stdout.
    """
    adapters: list[_Adapter] = []
    failures: list[dict[str, str]] = []
    for entry in iter_harness_entries():
        try:
            adapters.append(cast(_Adapter, load_adapter_class(entry)()))
        except _ADAPTER_LOAD_ERRORS as exc:
            failures.append(
                {"name": entry.public_id, "error": f"{type(exc).__name__}: {exc}"}
            )
    return adapters, failures


def _resolve_profile_path(profile: str | None) -> Path:
    """Return the shared-profile path."""
    return resolve_profile_path(profile)


def _complete_harness(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Shell-completion callback for the ``--harness`` option.

    Offers every registered public harness id plus the batch token ``all``,
    filtered to those beginning with the operator's partial input. The
    candidate set is the static registry's public-id form (e.g. ``claude-code``),
    so completion never drifts from the harnesses ``install``/``verify`` accept.
    """
    candidates = [*SUPPORTED_HARNESS_IDS, "all"]
    return [
        CompletionItem(candidate)
        for candidate in candidates
        if candidate.startswith(incomplete)
    ]


def _load_profile(profile_path: Path) -> dict[str, Any]:
    """Load, validate, and normalize the shared profile YAML."""
    return load_profile_file(profile_path).to_dict()


def _write_profile_text_safely(
    profile_path: Path,
    text: str,
    *,
    operation: str,
) -> MaterializationResult:
    """Write a profile document through the shared atomic write boundary."""
    result = write_bytes_safely(
        profile_path,
        text.encode("utf-8"),
        install_root=profile_path.parent,
        harness_name="profile",
        operation=operation,
    )
    if result.outcome == "error":
        raise _CliUserError(
            code="profile.write_failed",
            message="Apothem profile write failed.",
            field="profile",
            reason=result.message,
            fix=(
                "Choose a profile path inside a normal directory and check "
                "file permissions."
            ),
        )
    return result


def _profile_error(exc: ProfileValidationError) -> dict[str, object]:
    """Return the stable CLI error object for profile validation failures."""
    return exc.diagnostic.to_dict()


def _parse_set_value(raw: str) -> object:
    """Parse a ``profile set`` VALUE without YAML scalar-coercion footguns.

    Explicit structured input (a value whose first non-space char is ``[`` or
    ``{``) is parsed as YAML so list/map nodes can be set. Explicit booleans
    (``true``/``false``, case-insensitive) coerce to bool for the enforcement
    flags. Every other scalar is preserved as a literal string — no
    Norway-problem coercion of ``no``/``yes``/``on``/``off``, no date or number
    coercion (``2024-01-01``, ``1.0`` stay strings). Schema validation, not
    guesswork, decides whether the literal is acceptable.
    """
    import yaml

    stripped = raw.strip()
    if stripped[:1] in {"[", "{"}:
        try:
            return yaml.safe_load(raw)
        except yaml.YAMLError:
            return raw
    if stripped.lower() in {"true", "false"}:
        return stripped.lower() == "true"
    return raw


def _set_nested(data: dict[str, Any], dotted_key: str, value: object) -> dict[str, Any]:
    """Assign *value* at the dotted path *dotted_key* within *data*.

    Walks the addressed path, creating intermediate maps only along it, and
    sets the leaf. A single key with no dot keeps whole-node behavior. Sibling
    keys and unaddressed structure are preserved. Mutates and returns *data*.
    """
    parts = dotted_key.split(".")
    node = data
    for part in parts[:-1]:
        existing = node.get(part)
        if not isinstance(existing, dict):
            existing = {}
            node[part] = existing
        node = existing
    node[parts[-1]] = value
    return data


def _format_error_plain(
    error: dict[str, object], *, profile_path: Path | None = None
) -> str:
    """Format an expected error with the diagnostic fields operators need."""
    files = error.get("files_written", [])
    if isinstance(files, list) and files:
        files_written = ", ".join(str(item) for item in files)
    else:
        files_written = "none"
    lines = [str(error.get("message", "Apothem command failed."))]
    if profile_path is not None:
        lines.append(f"Profile: {profile_path}")
    lines.extend(
        [
            f"Field: {error.get('field', 'command')}",
            f"Reason: {error.get('reason', 'unknown failure')}",
            f"Fix: {error.get('fix', 'Review the command input and retry.')}",
            f"Files written: {files_written}.",
        ]
    )
    safe_value = error.get("safe_value")
    if safe_value is not None:
        lines.insert(-1, f"Offending value (redacted): {safe_value!r}")
    problems = error.get("errors")
    if isinstance(problems, list):
        for line in other_problem_lines(
            [item for item in problems[1:] if isinstance(item, dict)]
        ):
            lines.insert(-1, line)
    return "\n".join(lines)


def _error_envelope(
    *,
    command: str | None,
    harness: str | None = None,
    profile_path: Path | None = None,
    project_root: Path | None = None,
    error: dict[str, object],
    files_written: list[str] | None = None,
    results: list[dict[str, object]] | None = None,
    warnings: list[dict[str, object]] | None = None,
    status: str = "error",
) -> dict[str, object]:
    """Build the stable machine-readable lifecycle envelope."""
    return {
        "status": status,
        "command": command,
        "harness": harness,
        "profile_path": str(profile_path) if profile_path is not None else None,
        "project": str(project_root) if project_root is not None else None,
        "files_written": files_written or [],
        "results": results or [],
        "warnings": warnings or [],
        "error": error,
    }


def _emit_expected_error(
    *,
    command: str,
    fmt: str,
    error: dict[str, object],
    harness: str | None = None,
    profile_path: Path | None = None,
    project_root: Path | None = None,
    files_written: list[str] | None = None,
    results: list[dict[str, object]] | None = None,
    warnings: list[dict[str, object]] | None = None,
    exit_code: int = _EXIT_EXPECTED,
) -> None:
    """Emit an expected failure as JSON or a Click-formatted plain error."""
    status = "partial" if exit_code == _EXIT_PARTIAL else "error"
    if fmt == "json":
        emit_json(
            _error_envelope(
                command=command,
                harness=harness,
                profile_path=profile_path,
                project_root=project_root,
                error=error,
                files_written=files_written,
                results=results,
                warnings=warnings,
                status=status,
            )
        )
        sys.exit(exit_code)
    message = _format_error_plain(error, profile_path=profile_path)
    if exit_code == _EXIT_EXPECTED:
        raise click.ClickException(message)
    # click.ClickException hard-codes exit 1; emit the same `Error:` prefix
    # by hand and preserve a non-default (partial) exit code in plain mode,
    # for parity with the JSON branch above — a partial outcome exits 2 in
    # both formats, never 2 under --json and 1 in plain.
    click.echo(f"Error: {message}", err=True)
    sys.exit(exit_code)


def _confirmation_required_error(command: str) -> _CliUserError:
    """The structured refusal for a destructive command that cannot prompt.

    Destructive commands (uninstall, rollback) require per-target
    confirmation. JSON mode must never mix prompt text into the single
    JSON document, and a non-interactive run has no terminal to answer a
    prompt — in both cases the command refuses up front instead of dying
    mid-run on a bare Abort, mirroring the clean-slate contract.
    """
    return _CliUserError(
        code=f"{command}.confirmation_required",
        message="Confirmation is required and no prompt is possible.",
        field="yes",
        reason="This run cannot ask for confirmation (JSON output mode "
        "or no interactive terminal attached).",
        fix="Pass --yes to confirm non-interactively, or re-run "
        "interactively in plain mode.",
    )


def _lifecycle_envelope(
    *,
    status: str,
    command: str,
    action: str,
    harness: str | None,
    profile_path: Path | None,
    project_root: Path | None,
    files_written: list[str],
    results: list[dict[str, object]],
    warnings: list[dict[str, object]],
    output_path: Path | None = None,
    materialization: MaterializationRun | None = None,
) -> dict[str, object]:
    """Build a stable success or dry-run envelope."""
    payload: dict[str, object] = {
        "status": status,
        "command": command,
        "action": action,
        "harness": harness,
        "profile_path": str(profile_path) if profile_path is not None else None,
        "project": str(project_root) if project_root is not None else None,
        "files_written": files_written,
        "results": results,
        "warnings": warnings,
        "error": None,
    }
    if output_path is not None:
        payload["output_path"] = str(output_path)
    if materialization is not None:
        payload["materialization"] = materialization.to_dict()
    return payload


def _result_dicts(
    harness: str, materialization: MaterializationRun | None
) -> list[dict[str, object]]:
    """Return materialization result dictionaries tagged by public harness id."""
    if materialization is None:
        return []
    return [
        {"harness": harness, **result.to_dict()} for result in materialization.results
    ]


def _warning_dicts(
    harness: str, materialization: MaterializationRun | None
) -> list[dict[str, object]]:
    """Return warning result dictionaries tagged by public harness id."""
    if materialization is None:
        return []
    return [
        {"harness": harness, **warning.to_dict()}
        for warning in materialization.warnings
    ]


def _adapter_failure_result(
    harness_id: str,
    operation: str,
    output_path: Path | None,
    exc: Exception,
) -> dict[str, object]:
    """Return a per-harness error result for an adapter that raised mid-batch.

    Adapter lifecycle code is the untrusted edge: one adapter raising must degrade
    that harness to a recorded error and let the batch continue, mirroring the
    install/_materialize error model rather than aborting with a bare traceback.
    """
    return {
        "harness": harness_id,
        "outcome": "error",
        "operation": operation,
        "path": str(output_path) if output_path is not None else None,
        "message": f"{type(exc).__name__}: {exc}",
    }


def _load_adapter_for_entry(entry: HarnessRegistryEntry) -> _Adapter:
    """Load an adapter for a registry entry with structured CLI errors."""
    try:
        return cast(_Adapter, load_adapter_class(entry)())
    except _ADAPTER_LOAD_ERRORS as exc:
        raise _CliUserError(
            code="harness.load_failed",
            message="Apothem adapter loading failed.",
            field="harness",
            reason=f"{entry.public_id}: {exc}",
            fix="Reinstall Apothem or inspect the adapter package import.",
        ) from exc


def _unknown_harness_error(harness: str) -> _CliUserError:
    """Return a structured unknown-harness error."""
    available = ", ".join(SUPPORTED_HARNESS_IDS)
    return _CliUserError(
        code="harness.unknown",
        message="Apothem validation failed.",
        field="harness",
        reason=f"{harness!r} is not a supported harness.",
        fix=f"Use one of: {available}, or use 'all' for batch lifecycle commands.",
    )


def _selected_harness_ids(
    harness: str, *, shared_profile: dict[str, Any] | None, apply_excludes: bool
) -> list[str]:
    """Resolve one harness or the deterministic registry-wide selection."""
    requested = harness.strip().lower()
    if requested == "all":
        selected = list(SUPPORTED_HARNESS_IDS)
        if apply_excludes and shared_profile is not None:
            excluded = set(shared_profile.get("exclude_harnesses", []))
            selected = [item for item in selected if item not in excluded]
        if not selected:
            raise _CliUserError(
                code="harness.none_selected",
                message="Apothem validation failed.",
                field="harness",
                reason="batch selection resolved to zero harnesses.",
                fix="Remove at least one entry from exclude_harnesses or select a named harness.",
            )
        return selected
    try:
        return [_pkg.get_harness_entry(harness).public_id]
    except KeyError as exc:
        raise _unknown_harness_error(harness) from exc


def _require_project_for_selection(
    harness_ids: list[str], project_root: Path | None
) -> None:
    """Reject selected project-scope harnesses when no project root exists."""
    project_scoped = [
        harness_id
        for harness_id in harness_ids
        if _pkg.get_harness_entry(harness_id).scope == "project"
    ]
    if project_scoped and project_root is None:
        joined = ", ".join(project_scoped)
        raise _CliUserError(
            code="project.required",
            message="Apothem validation failed.",
            field="project",
            reason=f"project-scope harnesses require --project: {joined}.",
            fix="Pass --project PATH or select only user-scope harnesses.",
        )


def _select_and_load_adapters(
    harness: str,
    project_root: Path | None,
    *,
    shared_profile: dict[str, Any] | None,
    apply_excludes: bool,
) -> list[tuple[str, _Adapter]]:
    """Resolve the harness selection and load each selected adapter.

    Runs the shared selection preamble the lifecycle commands share: resolve
    the selected public harness ids (honoring ``all`` batch excludes only when
    *apply_excludes* is set), reject a project-scope selection lacking a
    project root, then load each adapter as a ``(harness_id, adapter)`` pair.
    Every step routes through the ``apothem.cli`` package (``_pkg``) so the
    test patch seams keep landing, and raises the same :class:`_CliUserError`
    the inline preambles did — callers keep their own try/except wiring.
    """
    selected = _pkg._selected_harness_ids(
        harness, shared_profile=shared_profile, apply_excludes=apply_excludes
    )
    _pkg._require_project_for_selection(selected, project_root)
    return [
        (harness_id, _pkg._load_adapter_for_entry(_pkg.get_harness_entry(harness_id)))
        for harness_id in selected
    ]


def _profile_scaffold_text() -> str:
    """Return a schema-valid minimal profile scaffold stamped with its version.

    The scaffold opens with a ``yaml-language-server`` modeline naming the
    profile schema's ``$id``, so an editor validates the file as it is edited.

    Every scaffold writer (``profile init``, ``profile edit`` on a missing
    file, ``quickstart``, and a first ``install``) goes through here, so each
    new profile records the schema version it was written for and a later
    migration can tell it apart from a newer one.
    """
    import yaml

    data = yaml.safe_load(profile_minimal_path().read_text(encoding="utf-8"))
    if isinstance(data, dict) and "schema_version" not in data:
        data = {"schema_version": current_schema_version(), **data}
    # The first-line modeline points YAML language servers (editors) at the
    # schema's $id, which the documentation site serves.
    schema_id = json.loads(profile_schema_path().read_text(encoding="utf-8"))["$id"]
    return f"# yaml-language-server: $schema={schema_id}\n" + yaml.safe_dump(
        data, sort_keys=False
    )


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


def _resolve_project_root(project: str | None) -> Path | None:
    """Resolve operator-supplied ``--project`` value to an absolute path."""
    if project is None:
        return None
    project_root = Path(project).expanduser().resolve(strict=False)
    if not project_root.exists():
        raise _CliUserError(
            code="project.not_found",
            message="Apothem validation failed.",
            field="project",
            reason=f"project root does not exist: {project_root}",
            fix="Create the project directory or pass an existing --project PATH.",
        )
    if not project_root.is_dir():
        raise _CliUserError(
            code="project.invalid_type",
            message="Apothem validation failed.",
            field="project",
            reason=f"project root is not a directory: {project_root}",
            fix="Pass a directory path as --project.",
        )
    return project_root


_project_option = click.option(
    "--project",
    default=None,
    metavar="PATH",
    help=(
        "Project root for project-scope harnesses (e.g., cursor). Required "
        "by adapters that materialize into a project tree rather than a "
        "user-scope configuration directory."
    ),
)

# Shared `--harness` decorator for the lifecycle commands whose option is
# byte-identical (install, uninstall, update, rollback, verify, and their
# continuous-form aliases): required, name-or-'all', shell-completed. The
# `diff` and `quickstart` variants differ (distinct help, and quickstart's
# `default="all"`) and declare their own `--harness` inline, so this is the
# single source of truth only for the identical form.
_harness_option = click.option(
    "--harness",
    required=True,
    metavar="NAME",
    help="Harness adapter name or 'all' for every supported harness.",
    shell_complete=_complete_harness,
)

# Shared `--profile` decorator for every command that resolves the shared
# profile (install, update, diff, verify, status, profile show/init/set/edit,
# and the continuous-form aliases): an optional path to the shared profile
# YAML, defaulting to the host's standard location when omitted. The single
# source of truth so the flag surface stays uniform across the lifecycle.
_profile_option = click.option(
    "--profile",
    default=None,
    metavar="PATH",
    help="Path to shared profile YAML.",
)


def _harness_roots(
    entry: HarnessRegistryEntry,
    adapter: _Adapter,
    project_root: Path | None,
) -> tuple[Path | None, Path | None]:
    """Resolve the (harness_root, project_root) pair the install driver consumes.

    The shared ``install_driver`` seams (``run_install`` / ``check_fidelity``)
    take a user-scope ``harness_root`` (the home-rooted configuration directory)
    XOR a project-scope ``project_root``. Project-scope adapters thread the
    operator-supplied ``--project`` value; user-scope adapters resolve their
    home root as the parent of the adapter's static ``output_path``.
    """
    if entry.scope == "project":
        return None, project_root
    return _adapter_resolve_output_path(adapter, project_root).parent, None


def _drift_state(
    entry: HarnessRegistryEntry,
    adapter: _Adapter,
    installed: bool,
    project_root: Path | None,
    shared_profile: dict[str, Any],
) -> str:
    """Classify a harness's profile-fidelity drift for the ``status`` command.

    ``absent`` when the adapter reports no install; otherwise the profile
    fidelity verdict — ``in-sync`` when every projected anchor carries the
    freshly-projected profile body verbatim, else ``drift``. The check is
    read-only: it re-projects the profile in memory and compares against the
    on-disk anchors, mutating nothing.
    """
    if not installed:
        return "absent"
    harness_root, scoped_project = _harness_roots(entry, adapter, project_root)
    results = check_fidelity(
        entry.package_key,
        harness_root=harness_root,
        project_root=scoped_project,
        profile=shared_profile,
    )
    return "in-sync" if fidelity_is_faithful(results) else "drift"


def _dry_run_plan(
    entry: HarnessRegistryEntry,
    adapter: _Adapter,
    project_root: Path | None,
    shared_profile: dict[str, Any],
) -> MaterializationRun:
    """Return the no-write dry-run plan for one harness, diffs included.

    Routes through the same ``install_driver.run_install(dry_run=True, profile=…)``
    seam the install path uses, so the result carries the unified diff already
    present in each operator-owned target's ``.detail`` — no re-derivation.
    """
    harness_root, scoped_project = _harness_roots(entry, adapter, project_root)
    return install_driver.run_install(
        entry.package_key,
        harness_root=harness_root,
        project_root=scoped_project,
        dry_run=True,
        profile=shared_profile,
    )


def _materialization_error(
    exc: MaterializationError, *, files_written: list[str]
) -> dict[str, object]:
    """Convert a materialization exception to the CLI diagnostic contract."""
    first = exc.run.errors[0] if exc.run.errors else None
    return _CliUserError(
        code="materialization.failed",
        message="Apothem materialization failed.",
        field=first.operation if first is not None else "materialization",
        reason=first.message if first is not None else str(exc),
        fix="Review the target path, permissions, and harness support files before retrying.",
        files_written=tuple(files_written),
    ).to_dict()


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
