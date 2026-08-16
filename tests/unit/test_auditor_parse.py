# SPDX-License-Identifier: MIT

"""Unit tests for the auditor's _parse_structure config-format dispatch.

The main auditor suite exercises the scan capabilities end to end; these target
the _parse_structure helper's per-format branches directly: the JSON / YAML /
TOML happy paths, the malformed-input _ParseError for each, and the raw-text
fallback for an unrecognized suffix. These branches are the format-detection
core every config scan funnels through.
"""

from __future__ import annotations

import sys

import pytest

from apothem.lib import auditor as au


class TestParseStructure:
    """Parsing a configuration file by suffix.

    Covers the JSON and YAML success paths against their malformed
    counterparts, which raise carrying the offending line so the operator is
    pointed at the fault rather than told only that parsing failed.
    """

    def test_json_parses(self) -> None:
        assert au._parse_structure('{"a": 1}', ".json") == {"a": 1}

    def test_json_malformed_raises_with_line(self) -> None:
        with pytest.raises(au._ParseError) as exc:
            au._parse_structure("{bad", ".json")
        assert exc.value.line == 1  # the decoder's line number is preserved

    def test_yaml_parses(self) -> None:
        assert au._parse_structure("a: 1\nb: two\n", ".yaml") == {"a": 1, "b": "two"}

    def test_yaml_malformed_raises(self) -> None:
        with pytest.raises(au._ParseError):
            au._parse_structure("a: [unclosed\n", ".yaml")

    def test_toml_parses(self) -> None:
        result = au._parse_structure('a = 1\nb = "two"\n', ".toml")
        if sys.version_info >= (3, 11):
            assert result == {"a": 1, "b": "two"}
        else:
            # py3.10 has no stdlib tomllib; the parser deliberately exposes the
            # raw text for line-level scanning instead of structured parsing.
            assert result == {"_raw": 'a = 1\nb = "two"\n'}

    def test_toml_malformed_raises(self) -> None:
        if sys.version_info >= (3, 11):
            with pytest.raises(au._ParseError):
                au._parse_structure("a = = 1\n", ".toml")
        else:
            # py3.10 exposes raw text rather than parsing, so it never raises.
            assert au._parse_structure("a = = 1\n", ".toml") == {"_raw": "a = = 1\n"}

    def test_unknown_suffix_returns_raw_text(self) -> None:
        # An unrecognized suffix exposes the raw text for line-level scanning.
        assert au._parse_structure("plain text", ".conf") == {"_raw": "plain text"}
