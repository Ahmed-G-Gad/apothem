# SPDX-License-Identifier: MIT

"""Unit tests for the opt-in continuous-learning loop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.learning import (
    LearningError,
    LearningPattern,
    LearningSignal,
    LearningStore,
    capture,
    extract_patterns,
    promote,
)
from apothem.lib.profile import load_profile_file
from apothem.schemas import profile_minimal_path, skill_schema_path


def _store(tmp_path: Path) -> LearningStore:
    """Build a learning store bound to an ensured data home under *tmp_path*."""
    data_home = resolve_shared_data_home(base=tmp_path).ensure()
    return LearningStore(data_home)


def _signal(
    signal_id: str, *, kind: str = "observation", tag: str = "auth"
) -> LearningSignal:
    """Build a schema-valid learning signal fixture."""
    return LearningSignal(
        id=signal_id,
        kind=kind,
        summary="prefer parameterized queries over string interpolation",
        captured="2026-06-09T12:00:00Z",
        tags=(tag,),
    )


def _profile_with_learning(tmp_path: Path, *, enabled: bool) -> Path:
    """Write a profile YAML flipping enforcement.learning_loop and return its path."""
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "identity:\n"
        "  name: Test User\n"
        "enforcement:\n"
        f"  learning_loop: {'true' if enabled else 'false'}\n",
        encoding="utf-8",
    )
    return profile_path


def test_signals_tolerates_torn_final_line(tmp_path: Path) -> None:
    """A crash mid-append tears only the last record; the rest stays readable."""
    store = _store(tmp_path)
    signals_path = store.ensure_initialized()
    signals_path.write_text(
        json.dumps(_signal("sig-1").to_dict())
        + "\n"
        + json.dumps(_signal("sig-2").to_dict())
        + '\n{"id": "sig-3", "kind": "obs',
        encoding="utf-8",
    )
    loaded = store.signals()
    assert [signal.id for signal in loaded] == ["sig-1", "sig-2"]
    assert store.count() == 2


def test_signals_raises_learning_error_for_mid_file_corruption(
    tmp_path: Path,
) -> None:
    """Corruption anywhere but the tail is damage, surfaced as LearningError."""
    store = _store(tmp_path)
    signals_path = store.ensure_initialized()
    signals_path.write_text(
        "not json at all\n" + json.dumps(_signal("sig-1").to_dict()) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(LearningError, match="line 1 is not valid JSON"):
        store.signals()


# --- task 7: capture gate -------------------------------------------------


def test_capture_with_flag_off_writes_nothing(tmp_path: Path) -> None:
    # Arrange
    profile = load_profile_file(profile_minimal_path())
    store = _store(tmp_path)
    signal = _signal("sig-1")

    # Act
    result = capture(signal, store=store, profile=profile)

    # Assert
    assert result is None
    assert store.count() == 0


def test_default_off_profile_flag_is_false(tmp_path: Path) -> None:
    # Arrange / Act
    profile = load_profile_file(profile_minimal_path())

    # Assert
    assert profile.enforcement.learning_loop is False


def test_capture_with_flag_on_appends_one_signal(tmp_path: Path) -> None:
    # Arrange
    profile = load_profile_file(_profile_with_learning(tmp_path, enabled=True))
    store = _store(tmp_path)
    signal = _signal("sig-1")

    # Act
    result = capture(signal, store=store, profile=profile)

    # Assert
    assert result == signal
    assert store.count() == 1
    assert store.signals()[0].id == "sig-1"


def test_capture_with_flag_on_appends_jsonl_lines(tmp_path: Path) -> None:
    # Arrange
    profile = load_profile_file(_profile_with_learning(tmp_path, enabled=True))
    store = _store(tmp_path)

    # Act
    capture(_signal("sig-1"), store=store, profile=profile)
    capture(_signal("sig-2"), store=store, profile=profile)

    # Assert
    assert store.count() == 2
    assert {signal.id for signal in store.signals()} == {"sig-1", "sig-2"}


# --- store seeding: ensure_initialized -------------------------------------


def test_ensure_initialized_seeds_empty_store(tmp_path: Path) -> None:
    # Arrange
    store = _store(tmp_path)

    # Act
    signals_path = store.ensure_initialized()

    # Assert: a concrete, empty JSON Lines artifact exists and reads as zero
    # captured signals.
    assert signals_path.is_file()
    assert signals_path.name == "signals.jsonl"
    assert signals_path.read_text(encoding="utf-8") == ""
    assert store.count() == 0


def test_ensure_initialized_is_idempotent_and_non_destructive(tmp_path: Path) -> None:
    # Arrange: an operator has opted in and captured a signal.
    profile = load_profile_file(_profile_with_learning(tmp_path, enabled=True))
    store = _store(tmp_path)
    capture(_signal("sig-1"), store=store, profile=profile)

    # Act: re-seeding the surface (a re-install) must not clobber the signal.
    first = store.ensure_initialized()
    second = store.ensure_initialized()

    # Assert
    assert first == second
    assert store.count() == 1
    assert store.signals()[0].id == "sig-1"


# --- task 8: confidence-scored extraction ---------------------------------


def test_extract_patterns_returns_patterns_with_clamped_confidence(
    tmp_path: Path,
) -> None:
    # Arrange
    signals = [
        _signal("sig-1", tag="auth"),
        _signal("sig-2", tag="auth"),
        _signal("sig-3", tag="caching"),
    ]

    # Act
    patterns = extract_patterns(signals)

    # Assert
    assert len(patterns) >= 1
    for pattern in patterns:
        assert 0.0 <= pattern.confidence <= 1.0


def test_extract_patterns_saturates_confidence_to_one(tmp_path: Path) -> None:
    # Arrange
    signals = [_signal(f"sig-{index}", tag="auth") for index in range(8)]

    # Act
    patterns = extract_patterns(signals)

    # Assert
    assert len(patterns) == 1
    assert patterns[0].confidence == 1.0
    assert patterns[0].support == 8


def test_extract_patterns_empty_input_returns_empty(tmp_path: Path) -> None:
    # Arrange / Act
    patterns = extract_patterns([])

    # Assert
    assert patterns == []


# --- task 9: promotion to skill -------------------------------------------


def test_promote_at_threshold_writes_valid_skill(tmp_path: Path) -> None:
    # Arrange
    skills_dir = tmp_path / "skills"
    pattern = LearningPattern(
        id="prefer-parameterized-queries",
        summary="prefer parameterized queries over string interpolation",
        confidence=0.8,
        support=4,
        signal_ids=("sig-1", "sig-2"),
    )
    schema = json.loads(skill_schema_path().read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    # Act
    skill_path = promote(
        pattern, threshold=0.8, skills_dir=skills_dir, today="2026-06-09"
    )

    # Assert
    assert skill_path is not None
    assert skill_path == skills_dir / "prefer-parameterized-queries" / "SKILL.md"
    assert skill_path.is_file()
    text = skill_path.read_text(encoding="utf-8")
    frontmatter_block = text.split("---", 2)[1]
    frontmatter = yaml.safe_load(frontmatter_block)
    assert not list(validator.iter_errors(frontmatter))
    assert frontmatter["name"] == "prefer-parameterized-queries"
    assert frontmatter["updated"] == "2026-06-09"


def test_promote_below_threshold_writes_nothing(tmp_path: Path) -> None:
    # Arrange
    skills_dir = tmp_path / "skills"
    pattern = LearningPattern(
        id="weak-pattern",
        summary="seen only once",
        confidence=0.2,
        support=1,
        signal_ids=("sig-1",),
    )

    # Act
    result = promote(pattern, threshold=0.8, skills_dir=skills_dir, today="2026-06-09")

    # Assert
    assert result is None
    assert not skills_dir.exists()


def test_promote_end_to_end_from_extracted_pattern(tmp_path: Path) -> None:
    # Arrange
    skills_dir = tmp_path / "skills"
    signals = [_signal(f"sig-{index}", tag="auth") for index in range(5)]
    patterns = extract_patterns(signals)

    # Act
    skill_path = promote(
        patterns[0], threshold=1.0, skills_dir=skills_dir, today="2026-06-09"
    )

    # Assert
    assert skill_path is not None
    assert skill_path.is_file()


def test_promote_without_today_fails_loudly(tmp_path: Path) -> None:
    # Arrange — a promotable pattern; the caller "forgets" the date stamp.
    skills_dir = tmp_path / "skills"
    pattern = LearningPattern(
        id="prefer-parameterized-queries",
        summary="prefer parameterized queries over string interpolation",
        confidence=1.0,
        support=5,
        signal_ids=("sig-1",),
    )

    # Act / Assert — 'today' is required: no epoch placeholder is silently
    # stamped into the promoted skill's metadata; the omission fails loudly.
    with pytest.raises(TypeError, match="today"):
        promote(pattern, threshold=0.5, skills_dir=skills_dir)  # type: ignore[call-arg]
    assert not skills_dir.exists()


def test_promote_rejects_non_kebab_pattern_id(tmp_path: Path) -> None:
    # Arrange
    skills_dir = tmp_path / "skills"
    pattern = LearningPattern(
        id="Not Kebab Case",
        summary="bad id",
        confidence=1.0,
        support=5,
        signal_ids=("sig-1",),
    )

    # Act / Assert
    with pytest.raises(LearningError, match="kebab-case"):
        promote(pattern, threshold=0.5, skills_dir=skills_dir, today="2026-06-09")
