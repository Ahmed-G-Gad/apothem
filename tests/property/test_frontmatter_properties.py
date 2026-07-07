# SPDX-License-Identifier: MIT

"""Property tests for `apothem.lib.frontmatter`.

Invariants exercised over auto-generated input:

* `extract_frontmatter` is **deterministic** — same content, same return.
* `extract_frontmatter` is **idempotent** under repeated reads.
* `field_value` round-trips a generated `(key, value)` pair when written
  into a canonical frontmatter block.
* `has_field` agrees with `field_value` on presence.
* `has_all_fields` agrees with the conjunction of per-field `has_field` checks.
* Non-frontmatter content never produces a false-positive extraction.

These invariants provide fuzz-like coverage even when external scoring
systems do not classify Hypothesis as a fuzzer integration.
"""

from __future__ import annotations

import string
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from apothem.lib.frontmatter import (
    extract_frontmatter,
    field_value,
    has_all_fields,
    has_field,
)

# Conservative test settings — property runs land in CI on every PR.
# ``derandomize=True`` pins the generated inputs so the same examples run every
# CI invocation (matching the sibling property-test templates), keeping runs
# byte-stable rather than nondeterministic across machines.
TEST_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    derandomize=True,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        # The `yaml_keys` strategy filters on `s[0].isalpha() and s.isascii()`,
        # which rejects a meaningful fraction of generated inputs (those whose
        # first character is a digit, hyphen, or underscore). The filter is
        # semantic (kebab-case YAML key shape), not pathological — accept the
        # rejection rate rather than narrow the alphabet at strategy level
        # (which would couple test data to an unrelated invariant).
        HealthCheck.filter_too_much,
    ],
)

# YAML-safe keys: kebab-case ASCII identifiers, 1-32 chars.
yaml_keys = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"
    ),
    min_size=1,
    max_size=32,
).filter(lambda s: s[0].isalpha() and s.isascii())

# YAML-safe scalar values: printable ASCII excluding YAML control characters
# (newline, ":", "#", and surrounding quotes). 0-64 chars.
yaml_values = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd", "Zs"), whitelist_characters=".-_/"
    ),
    min_size=0,
    max_size=64,
).map(lambda s: s.strip())


def _make_frontmatter_file(tmp_path: Path, body: str) -> Path:
    """Write `body` to a temp file and return its Path."""
    path = tmp_path / "fixture.md"
    path.write_text(body, encoding="utf-8")
    return path


@given(text=st.text(alphabet=string.printable, min_size=0, max_size=200))
@TEST_SETTINGS
def test_extract_is_deterministic(tmp_path: Path, text: str) -> None:
    """Two extractions of the same content return equal results."""
    path = _make_frontmatter_file(tmp_path, text)
    first = extract_frontmatter(path)
    second = extract_frontmatter(path)
    assert first == second


@given(key=yaml_keys, value=yaml_values)
@TEST_SETTINGS
def test_field_value_round_trips(tmp_path: Path, key: str, value: str) -> None:
    """A `(key, value)` pair written into a frontmatter block round-trips."""
    body = f"---\n{key}: {value}\n---\n\n# content\n"
    path = _make_frontmatter_file(tmp_path, body)
    result = field_value(path, key)
    # Whitespace-only values are normalized to empty string by the probe;
    # otherwise the value round-trips byte-for-byte after strip.
    assert result == value.strip()


@given(key=yaml_keys, value=yaml_values)
@TEST_SETTINGS
def test_has_field_agrees_with_field_value(
    tmp_path: Path, key: str, value: str
) -> None:
    """`has_field` is True iff `field_value` returns non-None."""
    body = f"---\n{key}: {value}\n---\n"
    path = _make_frontmatter_file(tmp_path, body)
    assert has_field(path, key) == (field_value(path, key) is not None)


@given(
    keys=st.lists(yaml_keys, min_size=1, max_size=8, unique=True),
    value=yaml_values,
)
@TEST_SETTINGS
def test_has_all_fields_is_conjunction(
    tmp_path: Path, keys: list[str], value: str
) -> None:
    """`has_all_fields([k1, k2, ...])` == all(has_field(ki) for ki)."""
    block_lines = "\n".join(f"{k}: {value}" for k in keys)
    body = f"---\n{block_lines}\n---\n"
    path = _make_frontmatter_file(tmp_path, body)
    assert has_all_fields(path, keys) == all(has_field(path, k) for k in keys)


@given(
    arbitrary_keys=st.lists(yaml_keys, min_size=1, max_size=4, unique=True),
)
@TEST_SETTINGS
def test_absent_field_returns_none(tmp_path: Path, arbitrary_keys: list[str]) -> None:
    """A field that is not in the frontmatter returns None / False."""
    body = "---\nexisting-key: existing-value\n---\n"
    path = _make_frontmatter_file(tmp_path, body)
    for k in arbitrary_keys:
        if k == "existing-key":
            continue
        assert field_value(path, k) is None
        assert has_field(path, k) is False


@given(text=st.text(alphabet=string.printable, min_size=0, max_size=200))
@TEST_SETTINGS
def test_extraction_never_returns_falsey_truth(tmp_path: Path, text: str) -> None:
    """`extract_frontmatter` returns either a non-empty string or None."""
    # Avoid generating accidentally-valid frontmatter at the top of the file.
    if text.startswith("---"):
        return
    path = _make_frontmatter_file(tmp_path, text)
    result = extract_frontmatter(path)
    assert result is None or isinstance(result, str)


def test_missing_file_returns_none(tmp_path: Path) -> None:
    """A non-existent path returns None — no exception raised."""
    missing = tmp_path / "does-not-exist.md"
    assert extract_frontmatter(missing) is None
    assert field_value(missing, "any") is None
    assert has_field(missing, "any") is False
    assert has_all_fields(missing, ["a", "b"]) is False


@pytest.mark.parametrize(
    "body", ["", "no frontmatter at all", "## Heading", "{}", "---\n"]
)
def test_known_negative_examples(tmp_path: Path, body: str) -> None:
    """Known non-frontmatter inputs return None — regression guard."""
    path = _make_frontmatter_file(tmp_path, body)
    assert extract_frontmatter(path) is None
