# SPDX-License-Identifier: MIT

"""The Trae rule file uses Trae's documented activation keys.

Trae project rules under ``.trae/rules/`` take their application mode from the
``alwaysApply`` property ("Always Apply" sets it to ``true``), with
``description`` or ``globs`` for the other modes, per
https://docs.trae.ai/ide/rules (retrieved 2026-10-02). ``trigger`` is a
Windsurf key that Trae does not read.
"""

from __future__ import annotations

from pathlib import Path

import yaml

import apothem.harnesses.trae as trae_pkg
from apothem.harnesses.trae import TraeAdapter

_TEMPLATE = Path(trae_pkg.__file__).resolve().parent / "templates" / "apothem-rules.md"


def test_template_has_no_windsurf_trigger_key() -> None:
    assert "trigger:" not in _TEMPLATE.read_text(encoding="utf-8")


def test_installed_rule_opens_with_always_apply(tmp_path: Path) -> None:
    adapter = TraeAdapter()
    adapter.install({}, project=tmp_path)
    text = adapter.resolve_output_path(tmp_path).read_text(encoding="utf-8")
    assert text.startswith("---\nalwaysApply: true\n")
    block = text[4 : text.index("\n---\n", 4)]
    keys = yaml.safe_load(block)
    assert keys["alwaysApply"] is True
    assert isinstance(keys["description"], str)
    assert keys["description"]
