# SPDX-License-Identifier: MIT

"""Agnostic contexts surface — injectable, enable/disable-able prompt fragments.

A *context fragment* is dynamic injectable text the operator can toggle on or
off, with optional activation metadata describing when it applies. The shape is
neutral: it carries no tool-specific or vendor-specific identifier, so the same
fragment applies across any installation target.

This module defines the in-memory fragment value type, schema validation against
the packaged ``context-fragment.schema.json``, and a :class:`ContextStore` that
persists fragments deterministically under a :class:`~apothem.lib.data_home.DataHome`'s
``contexts`` directory.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator

from apothem.lib.atomic_io import advisory_lock, write_bytes_atomically
from apothem.lib.data_home import DataHome
from apothem.lib.schema_errors import format_schema_errors
from apothem.schemas import context_fragment_schema_path

#: The deterministic on-disk filename holding the fragment array.
_FRAGMENTS_FILENAME: Final[str] = "fragments.json"

#: The advisory-lock filename guarding the fragment read-modify-write window.
_FRAGMENTS_LOCK_FILENAME: Final[str] = ".fragments.lock"


class ContextError(ValueError):
    """Raised when a fragment fails validation or a store operation is invalid."""


@dataclass(frozen=True)
class Activation:
    """Metadata describing when a fragment activates.

    Attributes:
        scope: Activation breadth (``global`` | ``session`` | ``task``), or
            ``None`` when unspecified.
        triggers: Phrases or signals that activate the fragment.
    """

    scope: str | None = None
    triggers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Serialize to a schema-conforming mapping, omitting empty optionals.

        Returns:
            A mapping carrying only the populated activation fields.
        """
        data: dict[str, object] = {}
        if self.scope is not None:
            data["scope"] = self.scope
        if self.triggers:
            data["triggers"] = list(self.triggers)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Activation:
        """Reconstruct an :class:`Activation` from a mapping.

        Args:
            data: A mapping carrying ``scope`` and/or ``triggers``.

        Returns:
            The reconstructed activation.
        """
        raw_scope = data.get("scope")
        scope = raw_scope if isinstance(raw_scope, str) else None
        raw_triggers = data.get("triggers")
        triggers: tuple[str, ...] = (
            tuple(str(item) for item in raw_triggers)
            if isinstance(raw_triggers, list)
            else ()
        )
        return cls(scope=scope, triggers=triggers)


@dataclass(frozen=True)
class ContextFragment:
    """One named, injectable prompt or context fragment.

    Attributes:
        id: Stable identifier, unique within a contexts store.
        name: Human-readable fragment name.
        body: The injectable prompt or context text.
        enabled: Enable/disable switch; when ``False`` the fragment is retained
            but never injected.
        activation: Optional activation metadata, or ``None``.
        tags: Discovery tags.
        updated: Optional ISO 8601 timestamp of the last amendment.
    """

    id: str
    name: str
    body: str
    enabled: bool
    activation: Activation | None = None
    tags: tuple[str, ...] = ()
    updated: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize to a schema-conforming mapping, omitting empty optionals.

        The required fields (``id``, ``name``, ``body``, ``enabled``) are always
        present; optional fields are emitted only when populated so the output
        validates under ``additionalProperties: false``.

        Returns:
            A mapping ready for JSON serialization and schema validation.
        """
        data: dict[str, object] = {
            "id": self.id,
            "name": self.name,
            "body": self.body,
            "enabled": self.enabled,
        }
        if self.activation is not None:
            activation = self.activation.to_dict()
            if activation:
                data["activation"] = activation
        if self.tags:
            data["tags"] = list(self.tags)
        if self.updated is not None:
            data["updated"] = self.updated
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ContextFragment:
        """Reconstruct a :class:`ContextFragment` from a mapping.

        Args:
            data: A mapping carrying the fragment fields.

        Returns:
            The reconstructed fragment.

        Raises:
            ContextError: When a required field is absent or carries the wrong
                type.
        """
        try:
            identifier = data["id"]
            name = data["name"]
            body = data["body"]
            enabled = data["enabled"]
        except KeyError as exc:
            raise ContextError(f"fragment is missing required field: {exc}") from exc
        if not (
            isinstance(identifier, str)
            and isinstance(name, str)
            and isinstance(body, str)
            and isinstance(enabled, bool)
        ):
            raise ContextError("fragment carries a field of the wrong type")
        raw_activation = data.get("activation")
        activation = (
            Activation.from_dict(raw_activation)
            if isinstance(raw_activation, Mapping)
            else None
        )
        raw_tags = data.get("tags")
        tags: tuple[str, ...] = (
            tuple(str(item) for item in raw_tags) if isinstance(raw_tags, list) else ()
        )
        raw_updated = data.get("updated")
        updated = raw_updated if isinstance(raw_updated, str) else None
        return cls(
            id=identifier,
            name=name,
            body=body,
            enabled=enabled,
            activation=activation,
            tags=tags,
            updated=updated,
        )


def _validator() -> Draft202012Validator:
    """Build a validator bound to the packaged context-fragment schema.

    Returns:
        A draft-2020-12 validator for a single fragment instance.
    """
    schema = json.loads(context_fragment_schema_path().read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_fragment(data: Mapping[str, object]) -> None:
    """Validate a fragment mapping against the packaged schema.

    Args:
        data: The candidate fragment mapping.

    Raises:
        ContextError: When the mapping violates the schema; the message lists
            every validation error.
    """
    joined = format_schema_errors(_validator(), data)
    if joined:
        raise ContextError(f"invalid context fragment: {joined}")


@dataclass(frozen=True)
class ContextStore:
    """Deterministic persistence for fragments under a data home.

    The store reads and writes ``fragments.json`` within the data home's
    ``contexts`` directory. The on-disk array is sorted by fragment id so the
    serialization is byte-stable across runs.

    Attributes:
        data_home: The per-target data home whose ``contexts`` directory backs
            this store.
    """

    data_home: DataHome

    @property
    def _lock_path(self) -> Path:
        """Return the advisory-lock path guarding the fragments RMW window."""
        return self.data_home.contexts / _FRAGMENTS_LOCK_FILENAME

    def _read_raw(self) -> list[dict[str, object]]:
        """Read the raw fragment mappings from disk.

        Returns:
            The stored mappings, or an empty list when the file is absent.

        Raises:
            ContextError: When the file does not hold a JSON array of objects,
                or an entry lacks the ``id`` field every consumer keys on.
        """
        path = self.data_home.contexts / _FRAGMENTS_FILENAME
        if not path.is_file():
            return []
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ContextError(f"{path} does not hold a JSON array")
        entries: list[dict[str, object]] = []
        for index, entry in enumerate(loaded):
            # Malformed on-disk state surfaces as the module's documented
            # ContextError with the offending path/entry, not a bare KeyError
            # from a downstream consumer (contains / _write_raw sort keys).
            if not isinstance(entry, dict):
                raise ContextError(f"{path} entry {index} is not a JSON object")
            if "id" not in entry:
                raise ContextError(
                    f"{path} entry {index} is missing the required 'id' field"
                )
            entries.append(dict(entry))
        return entries

    def _write_raw(self, entries: list[dict[str, object]]) -> None:
        """Persist fragment mappings deterministically.

        Args:
            entries: The fragment mappings to serialize.
        """
        self.data_home.contexts.mkdir(parents=True, exist_ok=True)
        ordered = sorted(entries, key=lambda entry: str(entry["id"]))
        path = self.data_home.contexts / _FRAGMENTS_FILENAME
        serialized = json.dumps(ordered, indent=2, sort_keys=True, ensure_ascii=False)
        write_bytes_atomically(path, (serialized + "\n").encode("utf-8"))

    def ensure_initialized(self) -> Path:
        """Create the canonical fragments file as an empty store when absent.

        Materialization calls this so a freshly-installed target carries a
        concrete, empty contexts artifact. The operation is idempotent and
        non-destructive: an existing fragments file is left untouched, so
        re-materializing a populated store never loses fragments.

        Returns:
            The path to the canonical fragments file.
        """
        path = self.data_home.contexts / _FRAGMENTS_FILENAME
        # Serialize the check-then-write under the same lock add()/set_enabled()
        # hold, so a concurrent first add() cannot create the file with a
        # fragment between the existence check and the empty-store write.
        with advisory_lock(self._lock_path):
            if not path.is_file():
                self._write_raw([])
        return path

    def fragments(self) -> list[ContextFragment]:
        """Return every stored fragment, sorted by id.

        Returns:
            The fragments, or an empty list when the store is absent.
        """
        return [ContextFragment.from_dict(entry) for entry in self._read_raw()]

    def enabled_fragments(self) -> list[ContextFragment]:
        """Return only the fragments whose enable switch is on.

        Returns:
            The enabled fragments, sorted by id.
        """
        return [fragment for fragment in self.fragments() if fragment.enabled]

    def contains(self, fragment_id: str) -> bool:
        """Report whether a fragment with *fragment_id* is stored.

        Args:
            fragment_id: The identifier to look up.

        Returns:
            ``True`` when a fragment with that id exists.
        """
        return any(entry["id"] == fragment_id for entry in self._read_raw())

    def add(self, fragment: ContextFragment) -> None:
        """Validate and persist a fragment, replacing any same-id fragment.

        Args:
            fragment: The fragment to store.

        Raises:
            ContextError: When the fragment fails schema validation.
        """
        data = fragment.to_dict()
        validate_fragment(data)
        self.data_home.contexts.mkdir(parents=True, exist_ok=True)
        # Serialize the RMW window so concurrent writers cannot lose a fragment.
        with advisory_lock(self._lock_path):
            entries = [e for e in self._read_raw() if e["id"] != fragment.id]
            entries.append(data)
            self._write_raw(entries)

    def set_enabled(self, fragment_id: str, enabled: bool) -> None:
        """Flip a stored fragment's enable switch and persist.

        Args:
            fragment_id: The identifier of the fragment to toggle.
            enabled: The new enable state.

        Raises:
            ContextError: When no fragment with *fragment_id* is stored.
        """
        self.data_home.contexts.mkdir(parents=True, exist_ok=True)
        with advisory_lock(self._lock_path):
            entries = self._read_raw()
            for entry in entries:
                if entry["id"] == fragment_id:
                    entry["enabled"] = enabled
                    self._write_raw(entries)
                    return
            raise ContextError(f"no fragment with id {fragment_id!r}")


__all__ = [
    "Activation",
    "ContextError",
    "ContextFragment",
    "ContextStore",
    "validate_fragment",
]
