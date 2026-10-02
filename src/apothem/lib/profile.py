# SPDX-License-Identifier: MIT

"""Canonical shared-profile model, normalization, and diagnostics.

This module is the one place a raw profile mapping becomes the normalized
``CanonicalProfile`` that every CLI command and harness materializer consumes:
load a mapping, migrate it forward through the ``schema_version`` chain,
validate it against the packaged JSON schema, coerce and normalize it, and
project a per-harness view with ``for_harness()``.

Two concerns are first-class. Validation failures surface as structured
``ProfileDiagnostic`` records — a code, the offending field, a reason, and a
fix — so a malformed profile yields an actionable message rather than an opaque
jsonschema error or a stack trace. And redaction is a defense boundary, not a
formatting nicety: secret-shaped keys and token-shaped strings are replaced
with ``<redacted>`` before any diagnostic echoes a value, so no raw secret
reaches plain or JSON output. Normalization is deterministic — sorted keys,
stabilized mappings — so ``to_dict()`` round-trips byte-stably.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from apothem.lib.harness_registry import SUPPORTED_HARNESS_IDS
from apothem.schemas import profile_schema_path

DEFAULT_PROFILE_PATH = Path("~/.config/apothem/profile.yaml")
DEFAULT_ROLE = "senior software engineer"
DEFAULT_LANGUAGE = "python"
DEFAULT_STYLE = "concise"
DEFAULT_SERIOUSNESS = "PERSONAL_USE"
DEFAULT_WORKSPACE_DIRECTORY_NAME = ".apothem"
DEFAULT_WORKSPACE_SCOPE = "project-local"

SERIOUSNESS_LEVELS = (
    "EXPLORING",
    "PERSONAL_USE",
    "SHARED",
    "PUBLIC_LAUNCH",
)

# Highest profile-schema version this engine understands. A version-less
# profile is treated as this version; a profile stamped higher is rejected
# with an upgrade-the-engine diagnostic before schema validation runs.
_CURRENT_SCHEMA_VERSION: Final[int] = 1

# MCP transports the schema and model both recognize; streamable-http is the
# modern replacement for sse. The schema↔code cross-check test pins these equal.
MCP_TRANSPORTS = ("stdio", "http", "sse", "streamable-http")

# The transport-conditional required field each server shape must carry. stdio
# servers launch a command; http-family servers carry a url. Mirrors the
# schema's if/then required-key blocks.
MCP_REQUIRED_FIELD_BY_TRANSPORT = {
    "stdio": "command",
    "http": "url",
    "sse": "url",
    "streamable-http": "url",
}

_SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "credential",
    "api_key",
    "apikey",
    "private_key",
    "authorization",
    "auth",
    "header",
)

_TOKEN_PATTERNS = (
    re.compile(r"(?i)\b(?:bearer\s+)?sk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"\b[A-Za-z0-9_-]{32,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b"),
)


@dataclass(frozen=True)
class IdentityProfile:
    """Operator identity fields carried by the shared profile."""

    name: str
    role: str = DEFAULT_ROLE
    email: str | None = None
    website: str | None = None
    github: str | None = None

    def to_dict(self) -> dict[str, str]:
        """Serialize to a dict, omitting any unset optional field
        (``email`` / ``website`` / ``github``)."""
        payload = {"name": self.name, "role": self.role}
        if self.email:
            payload["email"] = self.email
        if self.website:
            payload["website"] = self.website
        if self.github:
            payload["github"] = self.github
        return payload


@dataclass(frozen=True)
class PreferenceProfile:
    """Workflow and interaction defaults shared across harnesses."""

    language: str = DEFAULT_LANGUAGE
    style: str = DEFAULT_STYLE
    formatter: str | None = None
    test_framework: str | None = None

    def to_dict(self) -> dict[str, str]:
        """Serialize to a dict, omitting any unset optional field
        (``formatter`` / ``test_framework``)."""
        payload = {"language": self.language, "style": self.style}
        if self.formatter:
            payload["formatter"] = self.formatter
        if self.test_framework:
            payload["test_framework"] = self.test_framework
        return payload


@dataclass(frozen=True)
class EnforcementFlags:
    """Opt-in toggles for shipped behaviors that ship default-off.

    Every flag defaults ``False``: a clean install imposes no sprint
    ceremony, no agent dispatch, no parallel-task expectation, no
    continuous multi-step advancement, and no learning capture. Each
    behavior's machinery stays preserved and invokable; setting a flag
    ``True`` opts the operator into that behavior explicitly, never the
    reverse. Preferences carried as toggles live here; effort and model
    selection are absent-by-default frontmatter resolved per request.
    """

    sprints: bool = False
    agent_teams: bool = False
    multitasking: bool = False
    continuous_execution: bool = False
    learning_loop: bool = False

    def to_dict(self) -> dict[str, bool]:
        """Serialize all five opt-in flags to a bool dict (none omitted)."""
        return {
            "sprints": self.sprints,
            "agent_teams": self.agent_teams,
            "multitasking": self.multitasking,
            "continuous_execution": self.continuous_execution,
            "learning_loop": self.learning_loop,
        }


@dataclass(frozen=True)
class WorkspaceConfig:
    """Where Apothem keeps its shared, gitignored working directory.

    ``directory_name`` names the single working directory (default
    ``.apothem``); ``scope`` roots it project-local (``<project-root>/…``,
    the default) or in the user home (``~/…``). A profile that omits
    ``workspace`` resolves to a project-local ``.apothem``. ``data_home.py``
    consumes these fields to resolve the shared data home; they define the
    layout contract for callers that relocate the working directory.
    """

    directory_name: str = ".apothem"
    scope: str = "project-local"  # "project-local" | "user-home"

    def to_dict(self) -> dict[str, str]:
        """Serialize the workspace config to a string dict (none omitted)."""
        return {"directory_name": self.directory_name, "scope": self.scope}


@dataclass(frozen=True)
class McpServer:
    """One MCP server entry from the shared profile's portability inventory.

    stdio servers carry a ``command`` (and optional ``args``); http/sse/
    streamable-http servers carry a ``url``. ``env`` is an optional string map
    passed to the server process; ``headers`` is an optional string map of HTTP
    request headers for remote (http-family) transports — the surface for
    Bearer / API-key auth against a remote MCP endpoint. The shape mirrors the
    schema's ``mcpServer`` ``$def`` and its transport-conditional required keys.

    Secret VALUES in ``env`` or ``headers`` SHOULD be written as
    environment-variable references (``${VAR}`` — e.g. ``${GITHUB_TOKEN}``).
    Such a reference passes through to native config verbatim; Apothem never
    resolves it at render time, so no raw secret literal is materialized into a
    committable scope. ``sse`` is accepted for back-compat but deprecated;
    prefer ``streamable-http`` (see ``MCP_TRANSPORTS``).
    """

    transport: str
    command: str | None = None
    args: tuple[str, ...] = ()
    url: str | None = None
    env: Mapping[str, str] | None = None
    headers: Mapping[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict, omitting unset optional fields and emitting
        ``env`` / ``headers`` with their keys sorted for deterministic output."""
        payload: dict[str, Any] = {"transport": self.transport}
        if self.command:
            payload["command"] = self.command
        if self.args:
            payload["args"] = list(self.args)
        if self.url:
            payload["url"] = self.url
        if self.env:
            payload["env"] = {key: self.env[key] for key in sorted(self.env)}
        if self.headers:
            payload["headers"] = {
                key: self.headers[key] for key in sorted(self.headers)
            }
        return payload


@dataclass(frozen=True)
class CanonicalProfile:
    """Normalized shared profile consumed by CLI and harness materializers.

    The aggregate root this module produces from a validated mapping. Callers
    read its fields directly and rely on two behaviors: :meth:`to_dict` emits a
    deterministic nested dict — MCP-server keys sorted, harness overrides
    stabilized — so serialization round-trips byte-stably, and
    :meth:`for_harness` returns the per-harness projection by deep-merging the
    named harness's override onto the base profile.

    Attributes:
        identity: Operator identity (name, email, handles).
        preferences: Language and response-style preferences.
        rules: Ordered behavioral-rule identifiers.
        seriousness: Governance seriousness level.
        enforcement: Per-discipline enforcement flags.
        mcp_servers: MCP-server inventory keyed by name, or ``None``.
        harnesses: Per-harness override mappings, or ``None``.
        exclude_harnesses: Harness ids to skip when installing all.
        workspace: Workspace and plans configuration.
    """

    identity: IdentityProfile
    preferences: PreferenceProfile
    rules: tuple[str, ...] = ()
    seriousness: str = DEFAULT_SERIOUSNESS
    enforcement: EnforcementFlags = EnforcementFlags()
    mcp_servers: Mapping[str, McpServer] | None = None
    harnesses: Mapping[str, Mapping[str, Any]] | None = None
    exclude_harnesses: tuple[str, ...] = ()
    workspace: WorkspaceConfig = WorkspaceConfig()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full profile to a nested dict, sorting MCP server
        keys and stabilizing harness-override mappings for deterministic
        output."""
        payload: dict[str, Any] = {
            "identity": self.identity.to_dict(),
            "preferences": self.preferences.to_dict(),
            "rules": list(self.rules),
            "seriousness": self.seriousness,
            "enforcement": self.enforcement.to_dict(),
            "mcp_servers": {
                name: (self.mcp_servers or {})[name].to_dict()
                for name in sorted(self.mcp_servers or {})
            },
            "harnesses": {
                harness: _stable_mapping(override)
                for harness, override in (self.harnesses or {}).items()
            },
            "exclude_harnesses": list(self.exclude_harnesses),
            "workspace": self.workspace.to_dict(),
        }
        return payload

    def for_harness(self, harness_id: str) -> dict[str, Any]:
        """Return this profile with the named harness override applied."""
        canonical_id = normalize_harness_id(harness_id)
        if canonical_id not in SUPPORTED_HARNESS_IDS:
            raise ValueError(f"Unsupported harness id: {harness_id}")
        base = self.to_dict()
        overrides = dict((self.harnesses or {}).get(canonical_id, {}))
        merged = _deep_merge(base, overrides)
        merged.pop("harnesses", None)
        merged.pop("exclude_harnesses", None)
        # workspace is project-global filesystem layout, not a per-harness
        # surface — strip it from the per-harness projection.
        merged.pop("workspace", None)
        return _stable_mapping(merged)


@dataclass(frozen=True)
class ProfileDiagnostic:
    """Actionable profile validation error suitable for plain or JSON output."""

    code: str
    message: str
    profile_path: str
    field: str
    reason: str
    fix: str
    safe_value: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict, appending an empty ``files_written`` list so
        the payload matches the CLI lifecycle-envelope shape."""
        return {
            "code": self.code,
            "message": self.message,
            "profile_path": self.profile_path,
            "field": self.field,
            "reason": self.reason,
            "fix": self.fix,
            "safe_value": self.safe_value,
            "files_written": [],
        }

    def format_plain(self) -> str:
        """Render the diagnostic as a human-readable plain-text block."""
        safe_value = "none" if self.safe_value is None else repr(self.safe_value)
        return (
            f"{self.message}\n"
            f"Profile: {self.profile_path}\n"
            f"Field: {self.field}\n"
            f"Reason: {self.reason}\n"
            f"Fix: {self.fix}\n"
            f"Safe value: {safe_value}\n"
            "Files written: none."
        )


class ProfileValidationError(ValueError):
    """Raised when a profile cannot be parsed, validated, or normalized."""

    def __init__(self, diagnostic: ProfileDiagnostic) -> None:
        """Raise from a structured diagnostic, keeping both renderings usable.

        Pre-conditions: ``diagnostic`` carries the full failure record — code,
        offending field, reason, and suggested fix.

        Post-conditions: the plain-text rendering becomes the exception message,
        so an uncaught error still prints the operator-facing block; the
        ``diagnostic`` object stays attached so a JSON-mode caller can emit the
        machine-readable form instead of re-parsing that text.
        """
        super().__init__(diagnostic.format_plain())
        self.diagnostic = diagnostic


def resolve_profile_path(profile: str | Path | None) -> Path:
    """Return an absolute shared-profile path without dereferencing symlinks."""
    selected = Path(profile) if profile is not None else DEFAULT_PROFILE_PATH
    # os.path.abspath normalizes to an absolute path WITHOUT resolving symlinks;
    # Path.resolve would dereference them and break the no-symlink contract above.
    return Path(os.path.abspath(selected.expanduser()))  # noqa: PTH100


def load_profile_file(profile_path: Path) -> CanonicalProfile:
    """Read, validate, and normalize a profile YAML file."""
    resolved = resolve_profile_path(profile_path)
    if not resolved.exists():
        raise ProfileValidationError(
            ProfileDiagnostic(
                code="profile.not_found",
                message="Apothem validation failed.",
                profile_path=str(resolved),
                field="profile",
                reason="profile file does not exist",
                fix="Run 'apothem profile init' or pass --profile PATH.",
            )
        )

    try:
        raw_text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ProfileValidationError(
            ProfileDiagnostic(
                code="profile.read_failed",
                message="Apothem validation failed.",
                profile_path=str(resolved),
                field="profile",
                reason=f"profile is not valid UTF-8 ({exc.reason} at byte {exc.start})",
                fix="Save the profile as UTF-8 text.",
            )
        ) from exc
    except OSError as exc:
        raise ProfileValidationError(
            ProfileDiagnostic(
                code="profile.read_failed",
                message="Apothem validation failed.",
                profile_path=str(resolved),
                field="profile",
                reason=str(exc),
                fix="Check the profile path and file permissions.",
            )
        ) from exc

    try:
        raw_profile = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ProfileValidationError(
            ProfileDiagnostic(
                code="profile.yaml_invalid",
                message="Apothem validation failed.",
                profile_path=str(resolved),
                field="profile",
                reason=_one_line(str(exc)),
                fix="Fix the YAML syntax before running the command again.",
            )
        ) from exc
    except RecursionError as exc:
        # The YAML composer recurses once per nesting level, so a deeply
        # nested document exhausts the stack before it is a YAMLError.
        raise ProfileValidationError(
            ProfileDiagnostic(
                code="profile.yaml_invalid",
                message="Apothem validation failed.",
                profile_path=str(resolved),
                field="profile",
                reason="YAML nesting is too deep to parse",
                fix="Fix the YAML syntax before running the command again.",
            )
        ) from exc

    shape_problem = _document_shape_problem(raw_profile)
    if shape_problem is not None:
        raise ProfileValidationError(
            ProfileDiagnostic(
                code="profile.yaml_invalid",
                message="Apothem validation failed.",
                profile_path=str(resolved),
                field="profile",
                reason=shape_problem,
                fix=(
                    "Simplify the YAML: remove self-referencing aliases and "
                    "deep nesting."
                ),
            )
        )

    if raw_profile is None:
        raw_profile = {}
    if not isinstance(raw_profile, Mapping):
        raise ProfileValidationError(
            ProfileDiagnostic(
                code="profile.type_invalid",
                message="Apothem validation failed.",
                profile_path=str(resolved),
                field="profile",
                reason="profile document must be a mapping",
                fix="Use YAML key/value fields such as identity.name.",
                safe_value=redact_value(raw_profile),
            )
        )

    return validate_profile(raw_profile, profile_path=resolved)


# Ordered profile-schema migration chain. Each entry maps a source version N to
# a callable that returns the profile upgraded to version N+1. The chain is a
# no-op while only v1 exists; a future v1->v2 migration registers as
# ``_MIGRATIONS[1] = _migrate_v1_to_v2`` and slots in without touching the
# driver loop in ``migrate_profile``.
_MIGRATIONS: dict[int, Callable[[Mapping[str, Any]], Mapping[str, Any]]] = {
    # 1: _migrate_v1_to_v2,  # registered when schema_version 2 ships.
}


def migrate_profile(
    profile: Mapping[str, Any], *, profile_path: str | Path = "<memory>"
) -> Mapping[str, Any]:
    """Forward-migrate *profile* to the current schema version.

    A version-less profile is treated as ``_CURRENT_SCHEMA_VERSION``. A profile
    stamped with a version greater than this engine supports is rejected with an
    upgrade-the-engine diagnostic before any schema validation runs, so a
    newer-version profile surfaces an actionable message rather than an opaque
    ``additionalProperties`` error. A non-integer or otherwise malformed
    ``schema_version`` is left for the jsonschema validator to reject. The v1
    migration chain is a no-op: the mapping is returned unchanged.
    """
    declared = profile.get("schema_version", _CURRENT_SCHEMA_VERSION)
    # bool is an int subclass; treat a non-int (including bool) version as
    # malformed and let the schema validator emit the precise diagnostic.
    if isinstance(declared, int) and not isinstance(declared, bool):
        if declared > _CURRENT_SCHEMA_VERSION:
            raise ProfileValidationError(
                ProfileDiagnostic(
                    code="profile.version_unsupported",
                    message="Apothem validation failed.",
                    profile_path=str(profile_path),
                    field="schema_version",
                    reason=(
                        f"profile declares schema_version {declared} but this "
                        f"apothem supports up to {_CURRENT_SCHEMA_VERSION}"
                    ),
                    fix=(
                        "Upgrade apothem to a version that supports this "
                        "profile (the profile was written by a newer apothem)."
                    ),
                )
            )
        # A declared version below the first supported one has no migration
        # entry point; fall through so the schema's minimum-1 constraint
        # produces the standard diagnostic, mirroring how a non-int version
        # is deferred to the validator above.
        if declared >= 1:
            version = declared
            while version < _CURRENT_SCHEMA_VERSION:
                profile = _MIGRATIONS[version](profile)
                version += 1
    return profile


# Bounds on a parsed profile document. A real profile nests about five levels
# and holds at most a few hundred values. The bounds sit far above that and
# below the point where recursive validation and redaction would exhaust the
# stack, or where YAML aliases (which share one object per anchor) would expand
# into an exponential walk.
_MAX_DOCUMENT_DEPTH: Final[int] = 64
_MAX_DOCUMENT_VALUES: Final[int] = 100_000


def _document_shape_problem(document: object) -> str | None:
    """Return why a parsed YAML document cannot be validated safely, or None.

    Walks the document iteratively (so the check itself cannot overflow the
    stack) and reports, in plain words, a value that contains itself (an alias
    cycle such as ``&a [*a]``), nesting deeper than ``_MAX_DOCUMENT_DEPTH``, or
    more than ``_MAX_DOCUMENT_VALUES`` values once aliases are followed.
    """
    stack: list[tuple[object, int, frozenset[int]]] = [(document, 0, frozenset())]
    visited = 0
    while stack:
        value, depth, ancestors = stack.pop()
        visited += 1
        if visited > _MAX_DOCUMENT_VALUES:
            return (
                f"profile expands to more than {_MAX_DOCUMENT_VALUES} values "
                "once YAML aliases are followed"
            )
        if isinstance(value, Mapping):
            children: list[object] = list(value.values())
        elif isinstance(value, list):
            children = list(value)
        else:
            continue
        if id(value) in ancestors:
            return "YAML aliases form a cycle: a value contains itself"
        if depth >= _MAX_DOCUMENT_DEPTH:
            return f"profile nests deeper than {_MAX_DOCUMENT_DEPTH} levels"
        inner = ancestors | {id(value)}
        stack.extend((child, depth + 1, inner) for child in children)
    return None


def validate_profile(
    profile: Mapping[str, Any], *, profile_path: str | Path = "<memory>"
) -> CanonicalProfile:
    """Validate *profile* against the packaged schema, then normalize it."""
    profile = migrate_profile(profile, profile_path=profile_path)
    schema = yaml.safe_load(profile_schema_path().read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    # Type-stable sort key: an error path mixes str mapping keys with int
    # array indices, and comparing those directly raises TypeError.
    errors = sorted(
        validator.iter_errors(profile),
        key=lambda err: [(isinstance(p, int), str(p)) for p in err.absolute_path],
    )
    if errors:
        raise ProfileValidationError(
            _diagnostic_from_validation_error(errors[0], profile_path)
        )
    return coerce_profile(profile)


def coerce_profile(profile: Mapping[str, Any]) -> CanonicalProfile:
    """Apply profile defaults and deterministic normalization."""
    identity = _mapping(profile.get("identity"))
    preferences = _mapping(profile.get("preferences"))
    enforcement = _mapping(profile.get("enforcement"))
    workspace = _mapping(profile.get("workspace"))
    harnesses = _mapping(profile.get("harnesses"))

    normalized_harnesses: dict[str, Mapping[str, Any]] = {}
    for harness_id in sorted(harnesses, key=_harness_sort_key):
        value = harnesses[harness_id]
        if isinstance(value, Mapping):
            normalized_harnesses[normalize_harness_id(harness_id)] = _stable_mapping(
                value
            )

    return CanonicalProfile(
        identity=IdentityProfile(
            name=_normalize_scalar(identity.get("name", "")),
            role=_normalize_scalar(identity.get("role", DEFAULT_ROLE)) or DEFAULT_ROLE,
            email=_optional_scalar(identity.get("email")),
            website=_optional_scalar(identity.get("website")),
            github=_optional_scalar(identity.get("github")),
        ),
        preferences=PreferenceProfile(
            language=normalize_language(preferences.get("language", DEFAULT_LANGUAGE)),
            style=_normalize_scalar(preferences.get("style", DEFAULT_STYLE))
            or DEFAULT_STYLE,
            formatter=_optional_scalar(preferences.get("formatter")),
            test_framework=_optional_scalar(preferences.get("test_framework")),
        ),
        rules=tuple(_normalize_rules(profile.get("rules"))),
        seriousness=_normalize_scalar(profile.get("seriousness", DEFAULT_SERIOUSNESS))
        or DEFAULT_SERIOUSNESS,
        enforcement=EnforcementFlags(
            sprints=_normalize_flag(enforcement.get("sprints")),
            agent_teams=_normalize_flag(enforcement.get("agent_teams")),
            multitasking=_normalize_flag(enforcement.get("multitasking")),
            continuous_execution=_normalize_flag(
                enforcement.get("continuous_execution")
            ),
            learning_loop=_normalize_flag(enforcement.get("learning_loop")),
        ),
        mcp_servers=_normalize_mcp_servers(profile.get("mcp_servers")),
        harnesses=normalized_harnesses,
        exclude_harnesses=tuple(
            sorted(
                (
                    normalize_harness_id(item)
                    for item in _sequence(profile.get("exclude_harnesses"))
                ),
                key=_harness_sort_key,
            )
        ),
        workspace=WorkspaceConfig(
            directory_name=_normalize_scalar(workspace.get("directory_name"))
            or DEFAULT_WORKSPACE_DIRECTORY_NAME,
            scope=_normalize_scalar(workspace.get("scope")) or DEFAULT_WORKSPACE_SCOPE,
        ),
    )


def normalize_harness_id(value: object) -> str:
    """Return the canonical spelling for an already supported harness id."""
    return _normalize_scalar(value).lower()


def normalize_language(value: object) -> str:
    """Normalize the profile language preference to its semantic form."""
    return _normalize_scalar(value).lower() or DEFAULT_LANGUAGE


def redact_value(value: object, *, field_path: tuple[object, ...] = ()) -> object:
    """Return *value* with secret-like keys and token-shaped strings redacted.

    A value collapses to ``"<redacted>"`` on either of two independent triggers:
    its ``field_path`` ends in a sensitive key part (``_SENSITIVE_KEY_PARTS`` —
    token, secret, password, credential, ...), or, for a string, it matches a
    known token shape (``_TOKEN_PATTERNS``). Mappings and lists are walked
    recursively with the key or index appended to ``field_path``, so a nested
    secret is caught by its path even when the value itself is not token-shaped.
    This is a defense boundary, not a formatting nicety: it gates every value a
    ``ProfileDiagnostic`` echoes, so no raw secret reaches plain or JSON output.
    """
    if _path_is_sensitive(field_path):
        return "<redacted>"
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in _TOKEN_PATTERNS):
            return "<redacted>"
        return value
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            redacted[str(key)] = redact_value(item, field_path=(*field_path, key))
        return redacted
    if isinstance(value, list):
        return [
            redact_value(item, field_path=(*field_path, index))
            for index, item in enumerate(value)
        ]
    return value


def _diagnostic_from_validation_error(
    error: ValidationError, profile_path: str | Path
) -> ProfileDiagnostic:
    field = _format_field_path(error.absolute_path)
    return ProfileDiagnostic(
        code=_error_code(error.validator),
        message="Apothem validation failed.",
        profile_path=str(profile_path),
        field=field,
        reason=error.message,
        fix=_suggest_fix(error),
        safe_value=redact_value(error.instance, field_path=tuple(error.absolute_path)),
    )


def _error_code(validator_name: object) -> str:
    if not isinstance(validator_name, str):
        return "profile.validation_failed"
    return {
        "additionalProperties": "profile.unknown_field",
        "enum": "profile.invalid_choice",
        "format": "profile.invalid_format",
        "minLength": "profile.empty_value",
        "required": "profile.required",
        "type": "profile.invalid_type",
        "uniqueItems": "profile.duplicate_value",
    }.get(validator_name, "profile.validation_failed")


def _suggest_fix(error: ValidationError) -> str:
    if error.validator == "required":
        return "Add the missing required field."
    if error.validator == "additionalProperties":
        return "Remove the unsupported field or correct its spelling."
    if error.validator == "enum":
        validator_value = error.validator_value
        if not isinstance(validator_value, Iterable) or isinstance(
            validator_value, str | bytes
        ):
            return "Use one of the allowed values."
        choices = ", ".join(repr(choice) for choice in validator_value)
        return f"Use one of: {choices}."
    if error.validator == "format":
        return "Use a value that matches the required format."
    if error.validator == "minLength":
        return "Use a non-empty value."
    if error.validator == "type":
        return "Use a value with the expected type."
    if error.validator == "uniqueItems":
        return "Remove duplicate values."
    return "Fix the profile field and run the command again."


def _format_field_path(path: Iterable[object]) -> str:
    parts = [str(part) for part in path]
    return ".".join(parts) if parts else "profile"


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _sequence(value: object) -> list[object]:
    if isinstance(value, list):
        return list(value)
    if value is None:
        return []
    return [value]


def _normalize_scalar(value: object) -> str:
    if value is None:
        return ""
    return _normalize_newlines(str(value)).strip()


def _optional_scalar(value: object) -> str | None:
    normalized = _normalize_scalar(value)
    return normalized or None


def _normalize_flag(value: object) -> bool:
    """Coerce an opt-in enforcement flag to bool; absent reads as default-off."""
    return bool(value)


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_rules(value: object) -> list[str]:
    normalized: list[str] = []
    for item in _sequence(value):
        rule = _normalize_scalar(item)
        if rule:
            normalized.append(rule)
    return normalized


def _normalize_mcp_servers(value: object) -> dict[str, McpServer]:
    """Normalize the profile MCP inventory into name-keyed McpServer values.

    Servers are emitted in sorted name order for deterministic output. Each
    server's transport is lower-cased; stdio ``args`` and ``env`` values are
    coerced to strings. Non-mapping entries are skipped (the schema rejects
    them before this runs on a validated profile).
    """
    servers: dict[str, McpServer] = {}
    mapping = _mapping(value)
    for name in sorted(mapping):
        spec = mapping[name]
        if not isinstance(spec, Mapping):
            continue
        env_raw = _mapping(spec.get("env"))
        env = {str(key): _normalize_scalar(item) for key, item in env_raw.items()}
        headers_raw = _mapping(spec.get("headers"))
        headers = {
            str(key): _normalize_scalar(item) for key, item in headers_raw.items()
        }
        servers[_normalize_scalar(name)] = McpServer(
            transport=_normalize_scalar(spec.get("transport")).lower(),
            command=_optional_scalar(spec.get("command")),
            args=tuple(str(item) for item in _sequence(spec.get("args"))),
            url=_optional_scalar(spec.get("url")),
            env=env or None,
            headers=headers or None,
        )
    return servers


def _union_lists(base: list[Any], override: list[Any]) -> list[Any]:
    """Return base ++ override with order preserved and duplicates removed."""
    merged = list(base)
    for item in override:
        if item not in merged:
            merged.append(item)
    return merged


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Merge *override* onto *base* with the ratified per-harness semantics.

    Mappings merge recursively; list-valued overrides (e.g. ``rules``) UNION
    additively (base first, then new, deduplicated) — the ratified "refine"
    semantics, not silent replace. The MCP inventory unions by server name with
    each named server replaced wholesale, so an overridden server carries only
    its own transport's keys (no stale-field pollution). Other scalars override.
    """
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if (
            key == "mcp_servers"
            and isinstance(existing, Mapping)
            and isinstance(value, Mapping)
        ):
            merged[key] = {**existing, **value}
        elif isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(existing, value)
        elif isinstance(existing, list) and isinstance(value, list):
            merged[key] = _union_lists(existing, value)
        else:
            merged[key] = value
    return merged


def _stable_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    stable: dict[str, Any] = {}
    for key in sorted(value):
        item = value[key]
        if isinstance(item, Mapping):
            stable[str(key)] = _stable_mapping(item)
        elif isinstance(item, list):
            stable[str(key)] = [
                _stable_mapping(child) if isinstance(child, Mapping) else child
                for child in item
            ]
        else:
            stable[str(key)] = item
    return stable


def _harness_sort_key(value: object) -> tuple[int, str]:
    harness_id = normalize_harness_id(value)
    try:
        return (SUPPORTED_HARNESS_IDS.index(harness_id), harness_id)
    except ValueError:
        return (len(SUPPORTED_HARNESS_IDS), harness_id)


def _path_is_sensitive(path: tuple[object, ...]) -> bool:
    joined = ".".join(str(part).lower() for part in path)
    return any(part in joined for part in _SENSITIVE_KEY_PARTS)


def _one_line(value: str) -> str:
    return " ".join(value.split())


__all__ = [
    "DEFAULT_LANGUAGE",
    "DEFAULT_PROFILE_PATH",
    "DEFAULT_ROLE",
    "DEFAULT_SERIOUSNESS",
    "DEFAULT_STYLE",
    "DEFAULT_WORKSPACE_DIRECTORY_NAME",
    "DEFAULT_WORKSPACE_SCOPE",
    "MCP_REQUIRED_FIELD_BY_TRANSPORT",
    "MCP_TRANSPORTS",
    "SERIOUSNESS_LEVELS",
    "SUPPORTED_HARNESS_IDS",
    "CanonicalProfile",
    "EnforcementFlags",
    "IdentityProfile",
    "McpServer",
    "PreferenceProfile",
    "ProfileDiagnostic",
    "ProfileValidationError",
    "WorkspaceConfig",
    "coerce_profile",
    "load_profile_file",
    "migrate_profile",
    "normalize_harness_id",
    "normalize_language",
    "redact_value",
    "resolve_profile_path",
    "validate_profile",
]
