# SPDX-License-Identifier: MIT

"""Unit tests for harness-registry lookup + id-conversion helpers.

``get_harness_entry`` resolves a reference (public id OR package key) to its
registry entry; ``public_id_for_package_key`` / ``package_key_for_public_id``
convert between the hyphenated public id and the underscored Python package key.
These target the unknown-reference KeyError, the dual-reference resolution, and
the two conversion delegations that the broader suite does not reach directly.
"""

from __future__ import annotations

import pytest

from apothem.lib import harness_registry as hr


def test_get_harness_entry_unknown_reference_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        hr.get_harness_entry("definitely-not-a-harness")


def test_get_harness_entry_accepts_either_reference() -> None:
    # The same entry resolves whether addressed by public id or package key.
    by_public = hr.get_harness_entry("claude-code")
    by_package = hr.get_harness_entry("claude_code")
    assert by_public is by_package


def test_public_id_for_package_key_converts() -> None:
    assert hr.public_id_for_package_key("claude_code") == "claude-code"


def test_package_key_for_public_id_converts() -> None:
    assert hr.package_key_for_public_id("claude-code") == "claude_code"
