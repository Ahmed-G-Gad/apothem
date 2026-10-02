# SPDX-License-Identifier: MIT

"""Robustness properties for the frontmatter parsers over malformed input.

The engine reads frontmatter in three places: the field probe in
``apothem.lib.frontmatter`` (adapters read ``name``, ``description`` and tool
lists through it when they convert agents and commands), the body strippers in
the install-driver converters, and the plan-provenance reader in
``apothem.audit.plan_frontmatter`` (plan files are operator-authored). None of
them parses YAML fully; each must treat a malformed, truncated or binary block
as "no such field" rather than raise, because one bad file would otherwise
abort a whole install or audit sweep.

Properties checked over arbitrary bytes, arbitrary text, and frontmatter-shaped
"YAML token soup":

* no parser raises;
* the field probe returns ``None`` or a single-line string, and
  ``has_field`` / ``has_all_fields`` agree with it;
* a stripper only ever removes a prefix: its output is a suffix of its input;
* the plan reader returns only the three tracked keys, each a single line.
"""

from __future__ import annotations

from pathlib import Path

from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from apothem.audit.plan_frontmatter import parse_frontmatter, strip_frontmatter
from apothem.harnesses._shared.install_driver_converters import (
    _strip_leading_html_comment,
    _strip_markdown_frontmatter,
)
from apothem.lib.frontmatter import (
    extract_frontmatter,
    field_value,
    has_all_fields,
    has_field,
)

TEST_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

_FIELDS = ("name", "description", "tools", "title", "project", "created")

_FRONTMATTER_TOKENS = (
    "---",
    "---\n",
    "\n",
    "\r\n",
    "<!-- SPDX-License-Identifier: MIT -->\n",
    "<!--",
    "-->",
    "name: x\n",
    'description: "a: b"\n',
    "description: |\n  folded\n",
    "tools: Read, Grep\n",
    "title: t\n",
    "project: p\n",
    "created: 2026-10-02\n",
    "name:\n",
    ": \n",
    "- item\n",
    "  ",
    "\t",
    "[",
    "{",
    "&a ",
    "*a",
    "!!binary ",
    '"',
    "'",
    "#",
    "\x00",
    "\ufeff",
    "\u2028",
    "...\n",
    "body text\n",
)

_frontmatter_soup = st.lists(
    st.sampled_from(_FRONTMATTER_TOKENS), min_size=0, max_size=30
).map("".join)
_any_text = st.one_of(st.text(max_size=300), _frontmatter_soup)


def _write(tmp_path: Path, payload: bytes) -> Path:
    path = tmp_path / "artifact.md"
    path.write_bytes(payload)
    return path


def _check_field_probe(path: Path) -> None:
    block = extract_frontmatter(path)
    assert block is None or isinstance(block, str)
    values = {}
    for name in _FIELDS:
        value = field_value(path, name)
        assert value is None or isinstance(value, str)
        if value is not None:
            assert "\n" not in value
        assert has_field(path, name) is (value is not None)
        values[name] = value
    assert has_all_fields(path, list(_FIELDS)) is all(
        value is not None for value in values.values()
    )


@TEST_SETTINGS
@given(payload=st.binary(max_size=300))
@example(payload=b"---\nname: \xff\xfe\n---\nbody\n")
@example(payload=b"\xef\xbb\xbf---\nname: x\n---\n")
def test_field_probe_never_raises_on_arbitrary_bytes(
    tmp_path: Path, payload: bytes
) -> None:
    _check_field_probe(_write(tmp_path, payload))


@TEST_SETTINGS
@given(text=_any_text)
@example(text="---\nname: x\n")
@example(text="---\n---\n")
@example(text="<!-- unterminated\n---\nname: x\n---\n")
def test_field_probe_never_raises_on_malformed_frontmatter(
    tmp_path: Path, text: str
) -> None:
    _check_field_probe(_write(tmp_path, text.encode("utf-8")))


def test_field_probe_on_missing_file_reports_absent(tmp_path: Path) -> None:
    missing = tmp_path / "missing.md"
    assert extract_frontmatter(missing) is None
    assert field_value(missing, "name") is None


@TEST_SETTINGS
@given(text=_any_text)
@example(text="---\n")
@example(text="---\nname: x\n---")
@example(text="<!--")
def test_converter_strippers_only_remove_a_prefix(text: str) -> None:
    for strip in (_strip_markdown_frontmatter, _strip_leading_html_comment):
        stripped = strip(text)
        assert isinstance(stripped, str)
        assert text.endswith(stripped)


@TEST_SETTINGS
@given(text=_any_text)
@example(text="---\ntitle: a\ntitle: b\n---\n")
def test_plan_frontmatter_reader_never_raises(text: str) -> None:
    fields = parse_frontmatter(text)
    assert set(fields) <= {"project", "title", "created"}
    for value in fields.values():
        assert isinstance(value, str)
        assert "\n" not in value
    stripped = strip_frontmatter(text)
    assert text.endswith(stripped)
