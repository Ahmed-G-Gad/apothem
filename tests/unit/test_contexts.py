# SPDX-License-Identifier: MIT

"""Unit tests for the agnostic contexts surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.lib.contexts import (
    Activation,
    ContextError,
    ContextFragment,
    ContextStore,
    validate_fragment,
)
from apothem.lib.data_home import resolve_shared_data_home


def _fragment(
    fragment_id: str = "greeting",
    *,
    enabled: bool = True,
) -> ContextFragment:
    """Build a representative fragment for a test."""
    return ContextFragment(
        id=fragment_id,
        name="Greeting",
        body="Always greet the operator warmly.",
        enabled=enabled,
        activation=Activation(scope="global", triggers=("hello",)),
        tags=("tone",),
    )


def test_fragment_with_enabled_field_validates_clean(tmp_path: Path) -> None:
    # Arrange
    fragment = _fragment()

    # Act
    data = fragment.to_dict()

    # Assert
    assert data["enabled"] is True
    validate_fragment(data)  # raises ContextError on any schema error


def test_store_add_and_fragments_round_trips(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = ContextStore(home)
    fragment = _fragment()

    # Act
    store.add(fragment)
    loaded = store.fragments()

    # Assert
    assert loaded == [fragment]
    assert store.contains("greeting") is True


def test_fragments_empty_when_store_absent(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = ContextStore(home)

    # Act
    fragments = store.fragments()

    # Assert
    assert fragments == []


def test_disabled_fragment_excluded_from_enabled(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = ContextStore(home)
    store.add(_fragment("on", enabled=True))
    store.add(_fragment("off", enabled=False))

    # Act
    enabled = store.enabled_fragments()

    # Assert
    assert [fragment.id for fragment in enabled] == ["on"]


def test_set_enabled_flips_the_switch(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = ContextStore(home)
    store.add(_fragment("toggle", enabled=False))

    # Act
    store.set_enabled("toggle", True)

    # Assert
    assert [fragment.id for fragment in store.enabled_fragments()] == ["toggle"]


def test_set_enabled_unknown_id_raises(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = ContextStore(home)

    # Act / Assert
    with pytest.raises(ContextError):
        store.set_enabled("absent", True)


def test_add_replaces_same_id(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = ContextStore(home)
    store.add(_fragment("dup", enabled=True))

    # Act
    store.add(_fragment("dup", enabled=False))

    # Assert
    assert len(store.fragments()) == 1
    assert store.enabled_fragments() == []


def test_missing_enabled_field_raises(tmp_path: Path) -> None:
    # Arrange
    data = {"id": "x", "name": "X", "body": "text"}

    # Act / Assert
    with pytest.raises(ContextError):
        validate_fragment(data)


def test_bad_activation_scope_raises(tmp_path: Path) -> None:
    # Arrange
    data = {
        "id": "x",
        "name": "X",
        "body": "text",
        "enabled": True,
        "activation": {"scope": "everywhere"},
    }

    # Act / Assert
    with pytest.raises(ContextError):
        validate_fragment(data)


def test_additional_property_raises(tmp_path: Path) -> None:
    # Arrange
    data = {
        "id": "x",
        "name": "X",
        "body": "text",
        "enabled": True,
        "rogue": "field",
    }

    # Act / Assert
    with pytest.raises(ContextError):
        validate_fragment(data)


def test_store_entry_missing_id_raises_context_error(tmp_path: Path) -> None:
    # Arrange — an on-disk fragment lacking the 'id' every consumer keys on.
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = ContextStore(home)
    store_path = home.contexts / "fragments.json"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(
        json.dumps([{"name": "X", "body": "text", "enabled": True}]),
        encoding="utf-8",
    )

    # Act / Assert — the documented ContextError with the offending path, not
    # a bare KeyError, from every consumer of the raw store.
    with pytest.raises(ContextError, match="missing the required 'id' field"):
        store.contains("x")
    with pytest.raises(ContextError, match=r"entry 0"):
        store.fragments()
    with pytest.raises(ContextError, match="missing the required 'id' field"):
        store.set_enabled("x", True)


def test_store_non_object_entry_raises_context_error(tmp_path: Path) -> None:
    # Arrange — a store file holding a JSON array of non-objects.
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = ContextStore(home)
    store_path = home.contexts / "fragments.json"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(["just-a-string"]), encoding="utf-8")

    # Act / Assert
    with pytest.raises(ContextError, match="entry 0 is not a JSON object"):
        store.fragments()


def test_serialized_fragment_carries_no_harness_token(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = ContextStore(home)
    store.add(_fragment())

    # Act
    serialized = (home.contexts / "fragments.json").read_text(encoding="utf-8")
    parsed = json.loads(serialized)

    # Assert — the persisted shape is agnostic: no installation-target name leaks
    for token in ("claude", "cursor", "copilot", "gemini", "codex", "harness"):
        assert token not in serialized.lower()
    assert parsed[0]["id"] == "greeting"
