# SPDX-License-Identifier: MIT

"""Tests for the conformity-gate ``--check`` validator-name resolution.

The gate exposes two validator registries: ``GREP_MODULES`` (per-Write
matchers, stored underscored) and ``STANDALONE_MODULES`` (corpus-level
validators, stored hyphenated for CLI ergonomics). ``_resolve_validator``
maps a caller-supplied short or full name to its canonical registry entry,
accepting both hyphenated and underscored input.

These tests pin the regression where ``_resolve_validator`` compared the
underscored *candidates* against the raw (hyphenated) ``STANDALONE_MODULES``
entries, so ``--check <standalone-grep>`` never matched and always raised
``unknown grep``. They also assert the per-Write branch, ``--all``, and
``--list`` dispatch remain intact.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.conformity import gate


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param("naming-grep", ("naming-grep", True), id="standalone-hyphenated"),
        pytest.param("naming_grep", ("naming-grep", True), id="standalone-underscored"),
        pytest.param("naming", ("naming-grep", True), id="standalone-short-form"),
        pytest.param(
            "recommend-next-step-grep",
            ("recommend-next-step-grep", True),
            id="standalone-multi-hyphen",
        ),
        pytest.param(
            "file-header-grep",
            ("file_header_grep", False),
            id="per-write-hyphenated",
        ),
        pytest.param(
            "file_header_grep",
            ("file_header_grep", False),
            id="per-write-underscored",
        ),
        pytest.param(
            "file_header", ("file_header_grep", False), id="per-write-short-form"
        ),
    ],
)
def test_resolve_validator_maps_to_canonical(
    name: str, expected: tuple[str, bool]
) -> None:
    """Both name forms resolve to the canonical entry and standalone flag."""
    assert gate._resolve_validator(name) == expected


def test_resolve_validator_standalone_returns_standalone_true() -> None:
    """A standalone grep is flagged ``is_standalone=True`` (regression guard).

    Before the fix the standalone branch never matched, so this call raised
    ``ValueError`` instead of returning the canonical tuple.
    """
    canonical, is_standalone = gate._resolve_validator("naming-grep")

    assert canonical == "naming-grep"
    assert is_standalone is True


def test_resolve_validator_unknown_name_raises() -> None:
    """A name in neither registry raises ``ValueError`` with the raw name."""
    with pytest.raises(ValueError, match="unknown grep: 'nonexistent-grep'"):
        gate._resolve_validator("nonexistent-grep")


def test_main_check_standalone_routes_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--check <standalone>`` routes through ``_run_standalone`` and exits 0.

    The standalone validator's verdict is stubbed to PASS so the test isolates
    the routing fix from the validator's own corpus walk.
    """
    calls: list[tuple[str, Path]] = []

    def _stub(name: str, root: Path) -> tuple[bool, str]:
        calls.append((name, root))
        return True, ""

    monkeypatch.setattr(gate, "_run_standalone", _stub)

    exit_code = gate.main(["gate", "--check", "naming-grep", "."])

    assert exit_code == gate.EXIT_PASS
    # The relative root is resolved before dispatch, so ``.`` and the absolute
    # form inspect the same tree.
    assert calls == [("naming-grep", Path.cwd().resolve())]


def test_main_check_standalone_is_advisory_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing standalone validator is advisory by default: ``main`` exits 0
    (findings reported, action not blocked)."""

    def _stub(name: str, root: Path) -> tuple[bool, str]:
        return False, f"{name}: flagged"

    monkeypatch.setattr(gate, "_run_standalone", _stub)

    exit_code = gate.main(["gate", "--check", "naming-grep", "."])

    assert exit_code == gate.EXIT_PASS


def test_main_check_standalone_strict_propagates_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the opt-in ``--strict`` flag, a failing standalone validator drives
    ``main`` to the non-zero exit."""

    def _stub(name: str, root: Path) -> tuple[bool, str]:
        return False, f"{name}: flagged"

    monkeypatch.setattr(gate, "_run_standalone", _stub)

    exit_code = gate.main(["gate", "--check", "naming-grep", ".", "--strict"])

    assert exit_code == gate.EXIT_FAIL


def test_main_list_enumerates_both_registries(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--list`` still emits the full registry enumeration and exits 0."""
    exit_code = gate.main(["gate", "--list"])

    assert exit_code == gate.EXIT_PASS
    payload = json.loads(capsys.readouterr().out)
    assert "naming-grep" in payload["standalone_validators"]
    assert "file_header_grep" in payload["per_write_greps"]
    assert payload["total"] == len(gate.GREP_MODULES) + len(gate.STANDALONE_MODULES)


def test_main_all_runs_every_standalone_validator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--all`` still dispatches every standalone validator and exits 0.

    ``_run_standalone`` is stubbed to PASS so the test asserts the dispatch
    set is intact without depending on each validator's corpus verdict.
    """
    invoked: list[str] = []

    def _stub(name: str, root: Path) -> tuple[bool, str]:
        invoked.append(name)
        return True, ""

    monkeypatch.setattr(gate, "_run_standalone", _stub)

    exit_code = gate.main(["gate", "--all", str(tmp_path)])

    assert exit_code == gate.EXIT_PASS
    assert invoked == list(gate.STANDALONE_MODULES)
