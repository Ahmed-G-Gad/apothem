# SPDX-License-Identifier: MIT

"""Unit tests for the UDA-airtightness self-citation exemption.

The matcher at ``tools.validate_ecosystem.validate_uda_airtightness`` flags
hedging vocabulary in binding prescriptions across the governed-core tree.
The closed-list-defining rule body at ``src/apothem/rules/definitiveness.md``
necessarily enumerates the forbidden vocabulary inline as its pedagogical
content; rewriting that line would corrupt rule clarity by forcing readers
to consult two sources. The matcher exempts that line via an entry in
``_UDA_LINE_ALLOWLIST`` analogous to the self-citation-exemption pattern at
``src/apothem/rules/interactive-questions-sweep-matchers.md`` §3.

Three properties verified:

1. The exempted closed-list enumeration line in
   ``src/apothem/rules/definitiveness.md`` produces no hedge finding when
   scanned by the live matcher against the actual on-disk file.
2. A synthetic prescriptive line containing the same closed-list hedge
   words still surfaces as a finding, demonstrating the exemption is
   surgical (per-path / per-content) rather than blanket.
3. The exemption schema (``_UDA_LINE_ALLOWLIST``) is importable as a
   ``frozenset`` of two-tuples and contains the definitional self-citation
   entry — auditable by inspection without invoking the matcher.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV: Final[Path] = _REPO_ROOT / "scripts" / "dev"
_LIB_DIR: Final[Path] = _REPO_ROOT / "src" / "apothem" / "lib"
_HOOKS_LIB: Final[Path] = _REPO_ROOT / "src" / "apothem" / "hooks" / "lib"
for _p in (_SCRIPTS_DEV, _LIB_DIR, _HOOKS_LIB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import validate_ecosystem  # noqa: E402
from reporter import Reporter  # noqa: E402

_DEFINITIONAL_PATH: Final[str] = "src/apothem/rules/definitiveness.md"
_DEFINITIONAL_SUBSTR: Final[str] = (
    "Closed list, detected and eliminated when binding prescription"
)


def test_exemption_schema_importable_and_contains_definitional_entry() -> None:
    """Property 3: schema is auditable by importable inspection."""
    allowlist = validate_ecosystem._UDA_LINE_ALLOWLIST
    assert isinstance(allowlist, frozenset)
    assert all(isinstance(entry, tuple) and len(entry) == 2 for entry in allowlist)
    assert (_DEFINITIONAL_PATH, _DEFINITIONAL_SUBSTR) in allowlist


def test_definitional_line_is_skipped(tmp_path: Path) -> None:
    """Property 1: the live exempted line emits no hedge finding."""
    target = _REPO_ROOT / _DEFINITIONAL_PATH
    assert target.is_file(), f"definitional file missing: {target}"
    content = target.read_text(encoding="utf-8")
    # Locate the closed-list enumeration by content rather than absolute
    # line number so the assertion survives header-size changes.
    closed_list_lines = [
        line
        for line in content.splitlines()
        if _DEFINITIONAL_SUBSTR in line and "maybe, might, could" in line
    ]
    assert closed_list_lines, (
        "fixture invariant broken — the closed-list enumeration line "
        "(detected by content substring) is no longer present"
    )

    reporter = Reporter()
    validate_ecosystem.validate_uda_airtightness(_REPO_ROOT, reporter)
    failure_lines = [msg for msg in reporter.errors if _DEFINITIONAL_PATH in msg]
    assert failure_lines == [], (
        f"definitional self-citation should be exempt, got: {failure_lines}"
    )


def test_sibling_prescriptive_hedge_still_surfaces(tmp_path: Path) -> None:
    """Property 2: exemption is surgical — non-exempt prescriptive hedges still flag."""
    fixture_root = tmp_path
    rules_dir = fixture_root / "rules"
    rules_dir.mkdir()
    canary = rules_dir / "canary.md"
    canary.write_text(
        "---\n"
        "name: canary\n"
        "description: probe rule\n"
        "alwaysApply: false\n"
        "---\n"
        "\n"
        "# Body\n"
        "\n"
        "Operators might prefer the dashboard view in some sessions.\n",
        encoding="utf-8",
    )

    reporter = Reporter()
    validate_ecosystem.validate_uda_airtightness(fixture_root, reporter)
    canary_hits = [msg for msg in reporter.errors if "canary.md" in msg]
    assert canary_hits, (
        "exemption must be surgical — sibling prescriptive hedges must still surface"
    )


@pytest.mark.parametrize("entry", sorted(validate_ecosystem._UDA_LINE_ALLOWLIST))
def test_every_allowlist_entry_is_well_formed(entry: tuple[str, str]) -> None:
    """Every allowlist entry is a (path-suffix, content-substr) string pair."""
    path, substr = entry
    assert isinstance(path, str)
    assert path
    assert isinstance(substr, str)
    assert substr
    assert "/" in path or path.endswith(".md") or path.endswith(".py")
