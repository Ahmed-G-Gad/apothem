# SPDX-License-Identifier: MIT

"""Shared dataclasses, type aliases, constants, and leaf helpers for the install driver."""

from __future__ import annotations

import fnmatch
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Literal

import apothem
from apothem.harnesses._shared import install_driver

IgnoreFn = Callable[[str, list[str]], list[str]]

# Apothem source-package directory (e.g., src/apothem/ in dev installs).
APOTHEM_SRC: Path = Path(apothem.__file__).resolve().parent
BACKUP_ROOT: Path = Path.home() / ".apothem" / "backups"

MaterializationOutcome = Literal[
    "created",
    "updated",
    "unchanged",
    "skipped",
    "warning",
    "error",
]

_OUTCOMES: tuple[MaterializationOutcome, ...] = (
    "created",
    "updated",
    "unchanged",
    "skipped",
    "warning",
    "error",
)

_INSTALL_ENTRY_MODES: tuple[str, ...] = (
    "write_text",
    "sentinel_merge",
    "replace_tree",
    "merge_tree_entries",
    "command_skills",
    "codex_agents",
    "gemini_agents",
    "opencode_agents",
    "qwen_agents",
    "gemini_commands",
    "markdown_commands",
    "claude_rules",
)

#: Plain-language verb phrase for each operation kind. Preview surfaces (the
#: ``diff`` command, any future dry-run preview) render these instead of the
#: internal snake_case identifier so an operator reads an action, not a token.
#: Kept beside the operation-kind definitions above so a newly-added kind gets
#: its label in the same edit; a kind absent here falls back to a humanized
#: form via :func:`operation_label`.
OPERATION_LABELS: Final[dict[str, str]] = {
    "write_text": "Write file",
    "sentinel_merge": "Merge into file",
    "replace_tree": "Replace directory",
    "merge_tree_entries": "Merge directory",
    "command_skills": "Install skills",
    "codex_agents": "Install agents",
    "gemini_agents": "Install agents",
    "opencode_agents": "Install agents",
    "qwen_agents": "Install agents",
    "gemini_commands": "Install commands",
    "markdown_commands": "Install commands",
    "claude_rules": "Install rules",
    "sweep_stale": "Prune stale files",
    "capability_projection": "Project capability",
    "data_surface": "Write data file",
    "surgical_uninstall": "Remove file",
    "remove_existing": "Replace existing target",
    "restore_backup": "Restore backup",
    "remove_data_home": "Remove data directory",
}


def operation_label(operation: str) -> str:
    """Return the plain-language verb phrase for an *operation* kind.

    Falls back to a humanized form of the raw identifier (``snake_case`` to
    sentence case) for any kind absent from :data:`OPERATION_LABELS`, so a
    newly-added operation never surfaces its internal token to an operator.
    """
    label = OPERATION_LABELS.get(operation)
    if label is not None:
        return label
    return operation.replace("_", " ").strip().capitalize() or operation


def preview_status(operation: str, outcome: str, *, dry_run: bool) -> str:
    """Translate a plan-result *outcome* into a coherent preview status word.

    A dry run writes nothing but computes the prospective outcome of each entry
    (``created`` / ``updated`` / ``unchanged``) by comparing source against the
    on-disk target. Two residual ``skipped`` cases remain: a stale-sweep target
    that exists (would be removed), and an operator-owned entry whose source is
    missing. This phrases each dry-run outcome as what ``apothem install``
    *would* do:

    - ``created`` / ``updated`` become ``would create`` / ``would update``.
    - ``unchanged`` becomes ``no change`` (nothing to do for this target).
    - ``skipped`` becomes ``would remove`` for a stale-sweep target and
      ``would write`` otherwise.

    Outside a dry run the raw outcome is already coherent (``created`` /
    ``updated`` / ``unchanged`` / ``error``) and is returned unchanged.
    """
    if not dry_run:
        return outcome
    if outcome == "unchanged":
        return "no change"
    if outcome == "skipped":
        return "would remove" if operation == "sweep_stale" else "would write"
    if outcome == "created":
        return "would create"
    if outcome == "updated":
        return "would update"
    return outcome


# Ownership classes whose write targets are refused outright: a manifest
# entry pointing at a vendor-managed or append-only-record path is a defect,
# not a gated operation (model §5.F hard refusal).
_REFUSED_OWNERSHIP_CLASSES: frozenset[str] = frozenset({"vendor-reserved", "immutable"})


@dataclass(frozen=True)
class AuthorizationRequest:
    """One operator-owned non-additive change awaiting authorization.

    Passed to an :data:`AuthorizeFn` before the propagation driver overwrites
    bytes in an operator-owned target. The ``diff`` is the unified diff the
    operator reviews; returning ``False`` skips the write and leaves the
    operator's file untouched (model §5 destructive-authorization gate).
    """

    harness: str
    path: str
    operation: str
    ownership_class: str
    diff: str


# An operator-supplied authorization gate. Returns ``True`` to proceed with
# the backed-up overwrite, ``False`` to skip it. ``None`` (no callback) is the
# non-interactive default: proceed with a backup, never silently lose operator
# content without one (model §6 item 4).
AuthorizeFn = Callable[[AuthorizationRequest], bool]


@dataclass(frozen=True)
class MaterializationResult:
    """One structured materialization outcome."""

    outcome: MaterializationOutcome
    operation: str
    path: str
    message: str
    source: str | None = None
    backup_path: str | None = None
    detail: dict[str, str] = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        """Return True when this result represents an on-disk mutation."""
        return self.outcome in {"created", "updated"}

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        payload: dict[str, object] = {
            "outcome": self.outcome,
            "operation": self.operation,
            "path": self.path,
            "message": self.message,
        }
        if self.source is not None:
            payload["source"] = self.source
        if self.backup_path is not None:
            payload["backup_path"] = self.backup_path
        if self.detail:
            payload["detail"] = dict(self.detail)
        return payload


@dataclass(frozen=True)
class MaterializationRun:
    """Structured result set for one harness materialization pass."""

    harness: str
    dry_run: bool
    results: tuple[MaterializationResult, ...]

    @property
    def changed(self) -> bool:
        """Return True when any result wrote, replaced, or removed content.

        A dry run writes nothing, so it is never ``changed`` — even though its
        per-result outcomes now carry the *prospective* ``created`` / ``updated``
        classification a real install would produce. The would-this-change
        signal lives on each result; this run-level flag reflects only actual
        on-disk mutation.
        """
        if self.dry_run:
            return False
        return any(result.changed for result in self.results)

    @property
    def files_written(self) -> list[str]:
        """Return paths with created or updated outcomes (empty for a dry run)."""
        if self.dry_run:
            return []
        return [result.path for result in self.results if result.changed]

    @property
    def warnings(self) -> list[MaterializationResult]:
        """Return warning outcomes."""
        return [result for result in self.results if result.outcome == "warning"]

    @property
    def errors(self) -> list[MaterializationResult]:
        """Return error outcomes."""
        return [result for result in self.results if result.outcome == "error"]

    @property
    def counts(self) -> dict[str, int]:
        """Return deterministic per-outcome counts."""
        return {
            outcome: sum(1 for result in self.results if result.outcome == outcome)
            for outcome in _OUTCOMES
        }

    def extend(self, results: list[MaterializationResult]) -> MaterializationRun:
        """Return a copy with additional results appended."""
        return MaterializationRun(
            harness=self.harness,
            dry_run=self.dry_run,
            results=(*self.results, *results),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return {
            "harness": self.harness,
            "dry_run": self.dry_run,
            "changed": self.changed,
            "files_written": self.files_written,
            "counts": self.counts,
            "results": [result.to_dict() for result in self.results],
        }


class MaterializationError(ValueError):
    """Raised when validation prevents a write pass from starting."""

    def __init__(self, message: str, run: MaterializationRun) -> None:
        """Attach the aborted run to the raised validation failure.

        Pre-conditions: ``run`` is the :class:`MaterializationRun` assembled up
        to the point validation rejected the pass — no file has been written.
        Post-conditions: ``message`` reaches ``ValueError`` for the traceback,
        and ``run`` stays reachable so a caller can report exactly which
        planned writes were abandoned instead of only that something failed.
        """
        super().__init__(message)
        self.run = run


def resolve_source(source: str) -> Path:
    """Resolve a manifest source-path (package-relative) to an on-disk path."""
    return install_driver.APOTHEM_SRC / source.rstrip("/")


def _path_text(path: Path) -> str:
    """Return a stable display path for result payloads."""
    return str(path)


def _result(
    outcome: MaterializationOutcome,
    operation: str,
    path: Path,
    message: str,
    *,
    source: Path | None = None,
    backup_path: Path | None = None,
    detail: dict[str, str] | None = None,
) -> MaterializationResult:
    """Build one materialization result with normalized path strings."""
    return MaterializationResult(
        outcome=outcome,
        operation=operation,
        path=_path_text(path),
        message=message,
        source=_path_text(source) if source is not None else None,
        backup_path=_path_text(backup_path) if backup_path is not None else None,
        detail=dict(detail or {}),
    )


def _handle_rm_error(
    func: Callable[..., Any], path: str, exc_info: object
) -> None:  # pragma: no cover
    """Best-effort error handler for ``shutil.rmtree`` — ignore stale handles."""
    return


def _timestamp_slug() -> str:
    """Return the UTC timestamp slug used for backup directories."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_excluded_path(path: Path, exclude: list[str]) -> bool:
    """Return True when *path* is excluded by manifest basename globs."""
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in exclude)


# Sentinel marking a key that the Apothem-removal recursion has emptied out
# (every value it carried was an Apothem contribution). The caller drops the
# key entirely rather than leaving an empty container behind. Distinct object
# identity so it can never collide with a legitimate operator value.
_REMOVE_KEY: Final[object] = object()


def _with_detail(
    result: MaterializationResult, extra: dict[str, str]
) -> MaterializationResult:
    """Return *result* with *extra* keys merged into its detail mapping."""
    if not extra:
        return result
    merged = dict(result.detail)
    merged.update(extra)
    return replace(result, detail=merged)
