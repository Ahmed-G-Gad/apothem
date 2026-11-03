# SPDX-License-Identifier: MIT

"""Drift guard: the Cursor native-install example tracks what the install writes.

``examples/harnesses/cursor/native-install/apothem-rules.mdc`` documents itself as
"a materialized Cursor rules file" (``examples/harnesses/README.md``). It is rendered
for ``profile.example.yaml``, while the behavior-diff golden for the Cursor install
is rendered for the test profile, so the two differ from the profile section on.
Above that section the text comes from the adapter template and the install alone,
so there the example must equal the golden, which the behavior-diff tests keep equal
to what the install writes. The example had fallen behind the template once, with
every test passing; this guard catches the next such drift.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_EXAMPLE: Final[Path] = (
    _REPO_ROOT
    / "examples"
    / "harnesses"
    / "cursor"
    / "native-install"
    / "apothem-rules.mdc"
)
_GOLDEN: Final[Path] = (
    _REPO_ROOT
    / "tests"
    / "fixtures"
    / "behavior-diff"
    / "install_driver"
    / "rendered"
    / "cursor"
    / ".cursor"
    / "rules"
    / "apothem-rules.mdc"
)
_PROFILE_SECTION: Final[str] = "# Apothem Shared Profile"


def _above_profile_section(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.count(_PROFILE_SECTION) == 1, path
    return text.split(_PROFILE_SECTION, 1)[0]


def test_cursor_native_install_example_tracks_the_install() -> None:
    """Everything above the profile section matches what the install writes."""
    assert _above_profile_section(_EXAMPLE) == _above_profile_section(_GOLDEN), (
        "examples/harnesses/cursor/native-install/apothem-rules.mdc drifted from "
        "what the Cursor install writes -- re-render it for "
        "src/apothem/schemas/profile.example.yaml with a Cursor install into a "
        "scratch project and copy .cursor/rules/apothem-rules.mdc over it"
    )
