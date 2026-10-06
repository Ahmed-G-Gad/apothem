# SPDX-License-Identifier: MIT

"""Tests for the read-only JSONC / JSON5 reader in ``apothem.lib.lenient_json``."""

from __future__ import annotations

import json
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from apothem.lib import lenient_json

_JSON_VALUES = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(min_value=-(10**12), max_value=10**12)
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=12),
    lambda children: (
        st.lists(children, max_size=4)
        | st.dictionaries(st.text(max_size=6), children, max_size=4)
    ),
    max_leaves=12,
)


@settings(max_examples=200, deadline=None, derandomize=True)
@given(_JSON_VALUES)
def test_strict_json_parses_exactly_like_json_loads(value: object) -> None:
    for text in (json.dumps(value), json.dumps(value, indent=2)):
        assert lenient_json.loads(text) == json.loads(text)


def test_jsonc_comments_and_trailing_commas() -> None:
    text = """{
      // line comment
      "a": [1, 2, 3,], /* block
      comment */ "b": {"c": "// not a comment",},
    }"""
    assert lenient_json.loads(text) == {"a": [1, 2, 3], "b": {"c": "// not a comment"}}


def test_json5_syntax() -> None:
    text = """// JSON5
    {
      unquoted: 'single \\'quoted\\'',
      $dollar_key: 0x1F,
      leading: .5, trailing: 2., plus: +3,
      big: Infinity, small: -Infinity,
      escapes: "\\x41\\u0042\\
continued",
    }"""
    parsed = lenient_json.loads(text)
    assert isinstance(parsed, dict)
    assert parsed["unquoted"] == "single 'quoted'"
    assert parsed["$dollar_key"] == 31
    assert parsed["leading"] == 0.5
    assert parsed["trailing"] == 2.0
    assert parsed["plus"] == 3
    assert parsed["big"] == math.inf
    assert parsed["small"] == -math.inf
    assert parsed["escapes"] == "ABcontinued"


def test_nan_literal() -> None:
    parsed = lenient_json.loads("[NaN]")
    assert isinstance(parsed, list)
    assert math.isnan(parsed[0])


@pytest.mark.parametrize(
    "text",
    [
        "",
        "{",
        '{"a" 1}',
        "[1 2]",
        "{a: }",
        '"unterminated',
        "/* open comment",
        "{} trailing",
        "nope",
        "0x",
        '"bad \\x4"',
        '"line\nbreak"',
    ],
)
def test_invalid_documents_raise(text: str) -> None:
    with pytest.raises(lenient_json.LenientJSONError):
        lenient_json.loads(text)
