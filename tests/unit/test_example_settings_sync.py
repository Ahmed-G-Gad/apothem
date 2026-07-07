# SPDX-License-Identifier: MIT

"""Drift guard: the claude-code native-install example tracks the adapter template.

``examples/harnesses/claude-code/native-install/settings.json`` documents itself as
"a materialized Claude Code ``settings.json`` --- the shape an install writes into
the harness's native location" (``examples/harnesses/README.md``). It uses the same
``${HARNESS_ROOT}`` / ``${PYTHON_BIN}`` placeholders as the adapter's source template,
so the two carry identical hook content by contract.

This guard fails if the template gains or loses a hook block (event, matcher, or hook
id) without the example being re-synced --- the exact drift this test was added to
catch: the example had silently fallen behind by an ``AskUserQuestion`` PreToolUse
matcher and a whole ``PostToolUse`` block. Comparison is on parsed JSON, not raw bytes,
so it is immune to the working tree's platform line-ending differences (CRLF/LF).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_TEMPLATE: Final[Path] = (
    _REPO_ROOT
    / "src"
    / "apothem"
    / "harnesses"
    / "claude_code"
    / "templates"
    / "settings.json"
)
_EXAMPLE: Final[Path] = (
    _REPO_ROOT
    / "examples"
    / "harnesses"
    / "claude-code"
    / "native-install"
    / "settings.json"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_native_install_example_tracks_adapter_template() -> None:
    """The example settings.json carries the same content as the adapter template."""
    assert _load(_EXAMPLE) == _load(_TEMPLATE), (
        "examples/harnesses/claude-code/native-install/settings.json drifted from "
        "src/apothem/harnesses/claude_code/templates/settings.json -- re-sync with: "
        "cp src/apothem/harnesses/claude_code/templates/settings.json "
        "examples/harnesses/claude-code/native-install/settings.json"
    )
