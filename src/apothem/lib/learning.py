# SPDX-License-Identifier: MIT

"""Opt-in continuous-learning loop: capture, extraction, and promotion.

The learning loop ships default-off. Nothing is captured, scored, or promoted
unless the operator has explicitly opted in by setting
``enforcement.learning_loop: true`` in the shared profile. The loop has three
stages:

* **Capture** records one raw :class:`LearningSignal` per observation into an
  append-friendly JSON Lines store under a data home's ``learning`` directory.
  The :func:`capture` gate writes nothing when the opt-in flag is off.
* **Extraction** groups a set of signals and emits one :class:`LearningPattern`
  per group, each carrying a deterministic confidence in the closed interval
  ``[0, 1]``.
* **Promotion** writes a catalog-skill ``SKILL.md`` for any pattern whose
  confidence meets a caller-supplied threshold, validating the synthesized
  frontmatter against the packaged skill schema before it lands on disk.

Signals are neutral: a signal carries no tool-specific or vendor-specific
identifier, so the same signal round-trips between any two installation
targets without loss.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from apothem.lib.atomic_io import (
    advisory_lock,
    append_line_durably,
    write_bytes_atomically,
)
from apothem.lib.data_home import DataHome
from apothem.lib.profile import CanonicalProfile
from apothem.lib.schema_errors import format_schema_errors
from apothem.schemas import learning_signal_schema_path, skill_schema_path

#: The canonical filename, under a data home's ``learning`` dir, holding the
#: append-friendly JSON Lines stream of captured signals.
_SIGNALS_FILENAME: Final[str] = "signals.jsonl"

#: The advisory-lock filename guarding the signal-append window.
_SIGNALS_LOCK_FILENAME: Final[str] = ".signals.lock"

#: The catalog-skill entry-point filename written under a promoted skill dir.
_SKILL_FILENAME: Final[str] = "SKILL.md"

#: The SemVer stamp every freshly promoted skill carries.
_PROMOTED_SKILL_VERSION: Final[str] = "0.1.0"

#: Support count at which confidence saturates to ``1.0``. A group with this
#: many or more supporting signals is treated as fully confident.
_CONFIDENCE_SATURATION_SUPPORT: Final[int] = 5

#: Pattern enforcing the kebab-case identifier shape the skill schema requires.
_KEBAB_CASE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class LearningError(ValueError):
    """Raised when a learning artifact fails validation or synthesis."""


def _signal_schema() -> dict[str, object]:
    """Load and parse the learning-signal JSON schema.

    Returns:
        The parsed schema document.
    """
    raw = learning_signal_schema_path().read_text(encoding="utf-8")
    return cast("dict[str, object]", json.loads(raw))


def _skill_schema() -> dict[str, object]:
    """Load and parse the catalog-skill frontmatter JSON schema.

    Returns:
        The parsed schema document.
    """
    raw = skill_schema_path().read_text(encoding="utf-8")
    return cast("dict[str, object]", json.loads(raw))


def validate_signal(data: Mapping[str, object]) -> None:
    """Validate *data* against the learning-signal schema.

    Args:
        data: The candidate signal mapping to validate.

    Raises:
        LearningError: When *data* violates the schema. The message lists
            every validation error discovered.
    """
    validator = Draft202012Validator(_signal_schema(), format_checker=FormatChecker())
    details = format_schema_errors(validator, dict(data))
    if details:
        raise LearningError(f"invalid learning signal: {details}")


@dataclass(frozen=True)
class LearningSignal:
    """One captured signal in the opt-in continuous-learning loop.

    The signal shape mirrors the learning-signal schema and carries no
    harness-specific or vendor-specific field, so it is portable across any
    installation target.

    Attributes:
        id: Stable signal identifier, unique within a learning store.
        kind: Signal taxonomy; one of ``correction``, ``confirmation``, or
            ``observation``.
        summary: One-line statement of what was observed.
        captured: ISO 8601 date-time the signal was captured.
        tags: Tags used to group related signals during pattern extraction.
        payload: Free-form structured detail accompanying the signal, if any.
    """

    id: str
    kind: str
    summary: str
    captured: str
    tags: tuple[str, ...] = ()
    payload: Mapping[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        """Render the signal as a schema-conformant mapping.

        Optional keys are omitted when unset (empty ``tags``, ``None``
        ``payload``) so the output validates under
        ``additionalProperties: false`` and round-trips cleanly.

        Returns:
            A JSON-serializable mapping of the signal's set fields.
        """
        data: dict[str, object] = {
            "id": self.id,
            "kind": self.kind,
            "summary": self.summary,
            "captured": self.captured,
        }
        if self.tags:
            data["tags"] = list(self.tags)
        if self.payload is not None:
            data["payload"] = dict(self.payload)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> LearningSignal:
        """Reconstruct a signal from a schema-conformant mapping.

        Args:
            data: A mapping carrying at least the required signal fields.

        Returns:
            The reconstructed :class:`LearningSignal`.
        """
        raw_tags = data.get("tags", ())
        tags: tuple[str, ...] = ()
        if isinstance(raw_tags, Sequence) and not isinstance(raw_tags, (str, bytes)):
            tags = tuple(str(tag) for tag in raw_tags)

        raw_payload = data.get("payload")
        payload: Mapping[str, object] | None = None
        if isinstance(raw_payload, Mapping):
            payload = {str(key): value for key, value in raw_payload.items()}

        return cls(
            id=str(data["id"]),
            kind=str(data["kind"]),
            summary=str(data["summary"]),
            captured=str(data["captured"]),
            tags=tags,
            payload=payload,
        )


def _serialize_line(signal: LearningSignal) -> str:
    """Serialize one signal to a single canonical JSON Lines record (no newline).

    The object is emitted with sorted keys and no embedded newline so each
    on-disk line holds exactly one signal once the durable append adds the
    record terminator.

    Args:
        signal: The signal to serialize.

    Returns:
        The canonical line text, without a trailing newline.
    """
    return json.dumps(signal.to_dict(), sort_keys=True, ensure_ascii=False)


class LearningStore:
    """An append-friendly JSON Lines store of captured learning signals.

    The store persists to a single ``signals.jsonl`` file under a data home's
    ``learning`` directory. Each line is one canonically-serialized signal, so
    a capture appends one line without rewriting the whole file.
    """

    def __init__(self, data_home: DataHome) -> None:
        """Bind the store to *data_home*'s learning directory.

        Args:
            data_home: The per-target data home whose ``learning`` directory
                holds this store's JSON Lines signals file.
        """
        self._learning_dir = data_home.learning
        self._signals_path = data_home.learning / _SIGNALS_FILENAME
        self._lock_path = data_home.learning / _SIGNALS_LOCK_FILENAME

    def signals(self) -> list[LearningSignal]:
        """Load every captured signal from disk.

        Returns:
            The stored signals in capture order, or an empty list when the
            file is absent.

        Raises:
            LearningError: When a line is not valid JSON or not a JSON
                object. A torn final line is tolerated: under the store's
                append-only durable-append model, a crash mid-append can
                only tear the last record, and dropping that one interrupted
                record keeps every completed signal readable.
        """
        if not self._signals_path.exists():
            return []
        signals: list[LearningSignal] = []
        lines = self._signals_path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                loaded = json.loads(stripped)
            except json.JSONDecodeError as exc:
                if index == len(lines) - 1:
                    break
                raise LearningError(
                    f"learning signal line {index + 1} is not valid JSON: {exc}"
                ) from exc
            if not isinstance(loaded, Mapping):
                raise LearningError("each learning signal line must be a JSON object")
            signals.append(LearningSignal.from_dict(loaded))
        return signals

    def count(self) -> int:
        """Count the captured signals.

        Returns:
            The number of signals on disk.
        """
        return len(self.signals())

    def ensure_initialized(self) -> Path:
        """Create the canonical signals file as an empty store when absent.

        Materialization calls this so a freshly-installed target carries a
        concrete, empty learning artifact alongside its memory and contexts
        surfaces. The empty store is a zero-length JSON Lines file (no signals
        captured), which :meth:`signals` reads back as an empty list. The
        operation is idempotent and non-destructive: an existing signals file
        is left untouched, so re-materializing a populated store never loses
        captured signals.

        Seeding the surface captures nothing; capture remains gated on the
        operator's ``enforcement.learning_loop`` opt-in at :func:`capture`.

        Returns:
            The path to the canonical signals file.
        """
        # Serialize the check-then-write under the same lock _append() holds, so
        # a concurrent first capture cannot append a signal line between the
        # existence check and the empty-store write that clobbers it.
        with advisory_lock(self._lock_path):
            if not self._signals_path.exists():
                self._learning_dir.mkdir(parents=True, exist_ok=True)
                write_bytes_atomically(self._signals_path, b"")
        return self._signals_path

    def _append(self, signal: LearningSignal) -> None:
        """Append *signal* as one JSON Lines record, creating the dir if absent.

        Args:
            signal: The validated signal to persist.
        """
        self._learning_dir.mkdir(parents=True, exist_ok=True)
        # Hold the advisory lock around the durable O_APPEND so concurrent
        # captures never tear a single JSONL record or interleave bytes.
        with advisory_lock(self._lock_path):
            append_line_durably(self._signals_path, _serialize_line(signal))


def capture(
    signal: LearningSignal,
    *,
    store: LearningStore,
    profile: CanonicalProfile,
) -> LearningSignal | None:
    """Capture *signal* into *store* when the operator has opted in.

    The capture is gated on ``profile.enforcement.learning_loop``. When the
    flag is ``False`` (the default for a clean install), this writes nothing
    and returns ``None``. When the flag is ``True``, the signal is validated
    against the learning-signal schema and appended to the store.

    Args:
        signal: The signal to capture.
        store: The learning store the signal is appended to.
        profile: The shared profile carrying the ``learning_loop`` opt-in flag.

    Returns:
        The captured signal when the flag is on, else ``None``.

    Raises:
        LearningError: When the flag is on and *signal* fails validation.
    """
    if not profile.enforcement.learning_loop:
        return None
    validate_signal(signal.to_dict())
    store._append(signal)
    return signal


@dataclass(frozen=True)
class LearningPattern:
    """A scored pattern extracted across a group of related signals.

    Attributes:
        id: Stable kebab-case identifier derived from the group key.
        summary: One-line statement describing the grouped observation.
        confidence: Numeric confidence in the closed interval ``[0, 1]``.
        support: Count of signals supporting the pattern.
        signal_ids: Identifiers of the supporting signals, in capture order.
    """

    id: str
    summary: str
    confidence: float
    support: int
    signal_ids: tuple[str, ...] = field(default_factory=tuple)


def _score_confidence(support: int) -> float:
    """Score a pattern's confidence from its support count.

    The score is ``support / _CONFIDENCE_SATURATION_SUPPORT``, saturating to
    ``1.0`` once support reaches the saturation threshold. The result is
    clamped to the closed interval ``[0, 1]`` so a malformed (e.g. negative)
    support count can never produce an out-of-range score.

    Args:
        support: The count of signals supporting the pattern.

    Returns:
        A confidence in ``[0, 1]``.
    """
    raw = support / _CONFIDENCE_SATURATION_SUPPORT
    return max(0.0, min(1.0, raw))


def _group_key(signal: LearningSignal) -> str:
    """Derive the grouping key for *signal*.

    Signals carrying at least one tag group by their first tag; otherwise they
    group by ``kind`` plus a whitespace-normalized, lowercased summary. The key
    is rendered kebab-case so it can seed a schema-valid pattern identifier.

    Args:
        signal: The signal to derive a key for.

    Returns:
        A kebab-case grouping key.
    """
    if signal.tags:
        basis = signal.tags[0]
    else:
        normalized_summary = " ".join(signal.summary.lower().split())
        basis = f"{signal.kind} {normalized_summary}"
    return _kebab_case(basis)


def _kebab_case(value: str) -> str:
    """Render *value* as a schema-valid kebab-case identifier.

    Non-alphanumeric runs collapse to single hyphens; the result is lowercased
    and stripped of leading and trailing hyphens. An empty result falls back to
    ``pattern`` so a usable identifier is always produced.

    Args:
        value: The arbitrary basis string.

    Returns:
        A kebab-case identifier matching ``^[a-z0-9]+(-[a-z0-9]+)*$``.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "pattern"


def extract_patterns(signals: Sequence[LearningSignal]) -> list[LearningPattern]:
    """Group *signals* and emit one confidence-scored pattern per group.

    Signals group by :func:`_group_key` (first tag, else kind plus normalized
    summary). Each group yields one :class:`LearningPattern`. Confidence is
    scored by :func:`_score_confidence`, which saturates support to ``1.0`` and
    clamps the result to ``[0, 1]``; every returned pattern therefore satisfies
    ``0.0 <= confidence <= 1.0``. Groups are emitted in sorted-key order for
    determinism.

    Args:
        signals: The captured signals to extract patterns from.

    Returns:
        One pattern per distinct group key, ordered by key.
    """
    groups: dict[str, list[LearningSignal]] = {}
    for signal in signals:
        groups.setdefault(_group_key(signal), []).append(signal)

    patterns: list[LearningPattern] = []
    for key in sorted(groups):
        members = groups[key]
        support = len(members)
        patterns.append(
            LearningPattern(
                id=key,
                summary=members[0].summary,
                confidence=_score_confidence(support),
                support=support,
                signal_ids=tuple(member.id for member in members),
            )
        )
    return patterns


def _skill_frontmatter(pattern: LearningPattern, *, today: str) -> dict[str, object]:
    """Synthesize catalog-skill frontmatter from *pattern*.

    Args:
        pattern: The pattern being promoted.
        today: ISO 8601 date stamped as the skill's ``updated`` field.

    Returns:
        A mapping carrying every required catalog-skill frontmatter key.
    """
    return {
        "name": pattern.id,
        "description": (
            f"Learned pattern: {pattern.summary} "
            f"(confidence {pattern.confidence:.2f}, support {pattern.support})."
        ),
        "version": _PROMOTED_SKILL_VERSION,
        "updated": today,
        "archetype": "learned-template",
        "userInvocable": True,
        "disable-model-invocation": True,
        "allowed-tools": "*",
    }


def _validate_skill_frontmatter(frontmatter: Mapping[str, object]) -> None:
    """Validate synthesized skill frontmatter against the skill schema.

    Args:
        frontmatter: The candidate frontmatter mapping.

    Raises:
        LearningError: When the frontmatter violates the skill schema.
    """
    validator = Draft202012Validator(_skill_schema(), format_checker=FormatChecker())
    details = format_schema_errors(validator, dict(frontmatter))
    if details:
        raise LearningError(f"invalid promoted skill frontmatter: {details}")


def promote(
    pattern: LearningPattern,
    *,
    threshold: float,
    skills_dir: Path,
    today: str,
) -> Path | None:
    """Promote *pattern* to a catalog skill when it meets *threshold*.

    When ``pattern.confidence >= threshold``, a catalog-skill ``SKILL.md`` is
    written at ``<skills_dir>/<pattern.id>/SKILL.md`` with synthesized
    frontmatter (validated against the skill schema before it lands) plus a
    short Markdown body. When the pattern is below threshold, nothing is
    written.

    Args:
        pattern: The scored pattern to consider for promotion.
        threshold: The minimum confidence at which promotion proceeds.
        skills_dir: The directory under which the promoted skill directory is
            created.
        today: ISO 8601 date stamped as the skill's ``updated`` field.
            Required — the caller supplies the real date explicitly, keeping
            promotion deterministic and testable with no epoch placeholder
            silently stamped into skill metadata.

    Returns:
        The path to the written ``SKILL.md`` when promotion proceeds, else
        ``None``.

    Raises:
        LearningError: When the pattern id is not kebab-case, or the
            synthesized frontmatter fails skill-schema validation.
    """
    if pattern.confidence < threshold:
        return None
    if not _KEBAB_CASE.match(pattern.id):
        raise LearningError(
            f"pattern id must be kebab-case to promote, got {pattern.id!r}"
        )

    frontmatter = _skill_frontmatter(pattern, today=today)
    _validate_skill_frontmatter(frontmatter)

    skill_dir = skills_dir / pattern.id
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / _SKILL_FILENAME

    yaml_block = yaml.safe_dump(frontmatter, sort_keys=True, default_flow_style=False)
    body = (
        f"# {pattern.id}\n\n"
        f"{pattern.summary}\n\n"
        f"Promoted from {pattern.support} learning signal(s) at "
        f"confidence {pattern.confidence:.2f}.\n"
    )
    write_bytes_atomically(skill_path, f"---\n{yaml_block}---\n\n{body}".encode())
    return skill_path


__all__ = [
    "LearningError",
    "LearningPattern",
    "LearningSignal",
    "LearningStore",
    "capture",
    "extract_patterns",
    "promote",
    "validate_signal",
]
