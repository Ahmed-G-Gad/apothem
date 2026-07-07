# SPDX-License-Identifier: MIT

"""Unit tests for the shared jsonschema error-join helper."""

from __future__ import annotations

from jsonschema import Draft202012Validator

from apothem.lib.schema_errors import format_schema_errors


def test_valid_data_returns_none() -> None:
    validator = Draft202012Validator({"type": "object"})
    assert format_schema_errors(validator, {"any": "shape"}) is None


def test_multiple_errors_join_deterministically() -> None:
    validator = Draft202012Validator(
        {"type": "object", "additionalProperties": {"type": "integer"}}
    )
    message = format_schema_errors(validator, {"b": "bad", "a": "bad"})
    assert message is not None
    first, second = message.split("; ")
    assert "'bad'" in first
    assert "'bad'" in second


def test_mixed_int_and_str_paths_sort_without_type_error() -> None:
    """Paths diverging int-vs-str at the same depth must not raise TypeError.

    A mapping with an int key and a str key that both fail produces one
    error path holding an int element and one holding a str element at the
    same position; the sort key must stay type-stable.
    """
    validator = Draft202012Validator(
        {"type": "object", "additionalProperties": {"type": "integer"}}
    )
    message = format_schema_errors(validator, {1: "bad", "a": "bad"})
    assert message is not None
    assert "; " in message
