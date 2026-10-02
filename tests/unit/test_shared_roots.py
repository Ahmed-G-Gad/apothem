# SPDX-License-Identifier: MIT

"""Shared instruction files carry harness-neutral text.

Several harnesses load the same instruction file. A project ``AGENTS.md`` is
read by Codex, Cursor, GitHub Copilot, Kiro, Devin Desktop, OpenCode, Hermes,
Antigravity, CodeBuddy and Zed as well as Kimi Code; a project ``GEMINI.md`` is
read by Antigravity, the Copilot CLI and Zed as well as Gemini CLI; and
``~/.gemini/GEMINI.md`` is the global context file of both Gemini CLI and
Antigravity. An Apothem block written there must not tell every one of those
tools that it is one particular harness.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import apothem
from apothem.lib.harness_registry import HARNESS_REGISTRY

_PACKAGE_ROOT = Path(apothem.__file__).resolve().parent

# Templates the adapters write into an instruction file another harness reads.
_SHARED_ANCHOR_TEMPLATES = (
    "harnesses/kimi_code/templates/AGENTS.md",
    "harnesses/gemini_cli/templates/GEMINI.md",
    "harnesses/antigravity/templates/GEMINI.md",
)

_DISPLAY_NAMES = sorted(
    {entry.display_name for entry in HARNESS_REGISTRY}
    | {"Gemini", "Kimi", "Copilot", "Devin"},
    key=len,
    reverse=True,
)


@pytest.mark.parametrize("template", _SHARED_ANCHOR_TEMPLATES)
def test_shared_anchor_title_names_no_harness(template: str) -> None:
    text = (_PACKAGE_ROOT / template).read_text(encoding="utf-8")
    headings = [line for line in text.splitlines() if line.startswith("#")]
    assert headings, template
    for heading in headings:
        for name in _DISPLAY_NAMES:
            assert name.lower() not in heading.lower(), (template, heading)


@pytest.mark.parametrize("template", _SHARED_ANCHOR_TEMPLATES)
def test_shared_anchor_claims_no_single_reader(template: str) -> None:
    # The block may say which install wrote it, but never that the file is one
    # harness's own surface: other harnesses read the same file.
    text = " ".join((_PACKAGE_ROOT / template).read_text(encoding="utf-8").split())
    assert not re.search(r"(?i)this file is the [^.]*surface for", text), template
    assert not re.search(r"(?i)is read by `?[a-z-]+`? at every session", text), template
