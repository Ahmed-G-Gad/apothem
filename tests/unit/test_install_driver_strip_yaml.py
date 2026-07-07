# SPDX-License-Identifier: MIT

"""Uninstall must not delete an operator's comment-only YAML config.

Regression guard for ``_strip_apothem_yaml``: ``yaml.safe_load`` maps both an
empty document and a comment-only document to ``None``. The strip inverse must
distinguish them — a comment-only file is pure operator content (Apothem only
ever contributes value keys, never bare comments) and must survive uninstall,
while a genuinely empty document is deletable. The prior code returned ``None``
(delete) for any ``None`` parse, silently destroying an operator's annotated
config. This mirrors the JSON sibling's "never destroy content the inverse
cannot reason about" contract.
"""

from __future__ import annotations

from apothem.harnesses._shared import install_driver

_strip = install_driver._strip_apothem_yaml
_TEMPLATE = "managed_key: apothem-owned\n"


def test_comment_only_operator_yaml_is_preserved() -> None:
    operator = "# operator notes\n# keep these annotations\n"
    assert _strip(operator, _TEMPLATE) == operator


def test_empty_operator_yaml_is_deleted() -> None:
    assert _strip("", _TEMPLATE) is None


def test_whitespace_only_operator_yaml_is_deleted() -> None:
    # Spaces + newlines only (no tab — YAML forbids tab indentation, which
    # would route through the unparseable-preserve branch instead).
    assert _strip("   \n\n   \n", _TEMPLATE) is None


def test_unparseable_operator_yaml_is_preserved() -> None:
    # A mapping-value-after-mapping-value error — the inverse cannot reason
    # about it, so the operator content is preserved untouched.
    broken = "a: b: c\n"
    assert _strip(broken, _TEMPLATE) == broken
