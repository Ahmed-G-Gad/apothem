# SPDX-License-Identifier: MIT

"""Property tests for the profile loader, `apothem.lib.profile.load_profile_file`.

The shared profile is operator-controlled text, and every CLI command reads it
first. The loader's contract is that any file content yields one of two
outcomes: a normalized ``CanonicalProfile``, or a ``ProfileValidationError``
carrying a structured ``ProfileDiagnostic`` (code, field, reason, fix) that the
CLI renders as plain text or JSON. Any other exception escapes as a raw
traceback and breaks the JSON envelope, so it is a defect.

Inputs exercised:

* arbitrary Unicode text and arbitrary bytes (including invalid UTF-8);
* a "YAML token soup" of indicators, anchors, aliases, tags, directives and
  indentation that drives the YAML parser into its error paths;
* well-formed YAML documents of arbitrary shape, which parse cleanly and then
  stress schema validation, migration and normalization;
* pinned examples for the known hard cases: self-referential aliases, deep
  nesting, tagged binary values and an invalid UTF-8 byte.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from apothem.lib.profile import (
    CanonicalProfile,
    ProfileDiagnostic,
    ProfileValidationError,
    load_profile_file,
)

TEST_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

_YAML_TOKENS = (
    "identity:",
    "  name: x",
    "preferences:",
    "rules:",
    "- a",
    "  - b",
    "mcp_servers:",
    "harnesses:",
    "schema_version: 1",
    "seriousness: PERSONAL_USE",
    ":",
    "- ",
    "? ",
    "[",
    "]",
    "{",
    "}",
    ",",
    "&a ",
    "*a",
    "*missing",
    "!!binary aGk=",
    "!!python/object:os.system",
    "!custom",
    "%YAML 1.1",
    "---",
    "...",
    "|",
    ">",
    '"',
    "'",
    "#",
    "\t",
    "  ",
    "\n",
    "\r\n",
    "\x00",
    "\ufeff",
    "1e999",
    "~",
    "2026-10-02",
    "yes",
)

_yaml_soup = st.lists(st.sampled_from(_YAML_TOKENS), min_size=0, max_size=40).map(
    "".join
)

_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=True, allow_infinity=True),
    st.text(max_size=40),
)
_keys = st.one_of(
    st.sampled_from(
        [
            "identity",
            "preferences",
            "rules",
            "seriousness",
            "enforcement",
            "mcp_servers",
            "harnesses",
            "exclude_harnesses",
            "workspace",
            "schema_version",
            "name",
            "email",
            "command",
            "args",
            "env",
        ]
    ),
    st.text(min_size=1, max_size=12),
)
_documents = st.recursive(
    _scalars,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(_keys, children, max_size=5),
    ),
    max_leaves=25,
)


# Nested aliases: each level references the previous one ten times, so seven
# levels name ten million values while the file stays under 400 bytes.
_ALIAS_EXPANSION = "l0: &l0 [x, x, x, x, x, x, x, x, x, x]\n" + "".join(
    f"l{i}: &l{i} [{', '.join([f'*l{i - 1}'] * 10)}]\n" for i in range(1, 7)
)


def _load(tmp_path: Path, payload: bytes) -> CanonicalProfile:
    target = tmp_path / "profile.yaml"
    target.write_bytes(payload)
    return load_profile_file(target)


def _assert_structured_outcome(tmp_path: Path, payload: bytes) -> None:
    """The loader returns a profile or raises a structured diagnostic, nothing else."""
    try:
        profile = _load(tmp_path, payload)
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic
        assert isinstance(diagnostic, ProfileDiagnostic)
        assert diagnostic.code.startswith("profile.")
        assert diagnostic.field
        assert diagnostic.reason
        assert diagnostic.fix
        # Both renderings must work: the CLI prints one or the other.
        assert diagnostic.format_plain()
        assert isinstance(diagnostic.to_dict(), dict)
        return
    assert isinstance(profile, CanonicalProfile)


@TEST_SETTINGS
@given(text=st.text(max_size=400))
@example(text="")
@example(text="identity: &a {name: *a}\n")
@example(text="&a [*a]\n")
@example(text="[" * 5000)
@example(text="a:\n" + "".join("  " * i + "b:\n" for i in range(1, 400)))
@example(text="identity:\n  name: !!binary aGVsbG8=\n")
@example(text="%YAML 9.9\n---\nidentity: {}\n")
@example(text=_ALIAS_EXPANSION)
def test_arbitrary_text_yields_profile_or_structured_error(
    tmp_path: Path, text: str
) -> None:
    _assert_structured_outcome(tmp_path, text.encode("utf-8", "surrogatepass"))


@TEST_SETTINGS
@given(payload=st.binary(max_size=400))
@example(payload=b"\xff\xfe\x00identity: {}\n")
@example(payload=b"identity:\n  name: \x80\n")
def test_arbitrary_bytes_yield_profile_or_structured_error(
    tmp_path: Path, payload: bytes
) -> None:
    _assert_structured_outcome(tmp_path, payload)


@TEST_SETTINGS
@given(text=_yaml_soup)
def test_yaml_token_soup_yields_profile_or_structured_error(
    tmp_path: Path, text: str
) -> None:
    _assert_structured_outcome(tmp_path, text.encode("utf-8"))


@TEST_SETTINGS
@given(document=_documents)
def test_wellformed_yaml_of_any_shape_yields_profile_or_structured_error(
    tmp_path: Path, document: object
) -> None:
    text = yaml.safe_dump(document, allow_unicode=True)
    _assert_structured_outcome(tmp_path, text.encode("utf-8"))
