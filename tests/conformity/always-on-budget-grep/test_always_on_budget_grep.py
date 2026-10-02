# SPDX-License-Identifier: MIT

"""Pass + fail regression fixture for the always-on-budget matcher.

Always-on rules load into every session as standing directives, so the
token-budget-discipline rule caps each always-on body at
``MAX_SUBSTANTIVE_TOKENS`` substantive tokens. The matcher classifies a rule
as always-on (``alwaysApply: true`` with an empty ``pathFilter``) and counts
body tokens after excluding frontmatter, the trailing ``## Bindings`` section,
and companion-sub-rule pointer lines.

This fixture pins one passing case (an always-on body under the ceiling) and
one failing case (the same frontmatter with a body over the ceiling) using
synthetic in-memory content through the matcher's ``check(...)`` API, so the
verdict has a regression anchor the coverage loop recognises.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_MODULE_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "always_on_budget_grep.py"
)


def _load() -> ModuleType:
    """Load the hyphen-named matcher module via an importlib spec."""
    spec = importlib.util.spec_from_file_location("always_on_budget_grep", _MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["always_on_budget_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()

# Always-on frontmatter: alwaysApply true with an empty pathFilter is the
# classification the matcher's body budget applies to.
_ALWAYS_ON_FRONTMATTER: Final[str] = "---\nalwaysApply: true\npathFilter:\n---\n"


def _build_body(word_count: int) -> str:
    """Return an always-on rule whose substantive body has *word_count* words."""
    body = " ".join("word" for _ in range(word_count))
    return f"{_ALWAYS_ON_FRONTMATTER}# Rule body\n\n{body}\n"


def test_pass_always_on_body_under_ceiling() -> None:
    """An always-on body well under the ceiling passes with no finding."""
    content = _build_body(_MOD.MAX_SUBSTANTIVE_TOKENS - 100)
    result = _MOD.check(content, Path("rules/some-rule.md"))

    always_on, tokens = _MOD.measure(content)
    assert always_on is True
    assert tokens <= _MOD.MAX_SUBSTANTIVE_TOKENS

    assert result.passed is True
    assert result.findings == []


def test_fail_always_on_body_over_ceiling() -> None:
    """An always-on body past the ceiling trips the matcher."""
    content = _build_body(_MOD.MAX_SUBSTANTIVE_TOKENS + 50)
    result = _MOD.check(content, Path("rules/some-rule.md"))

    always_on, tokens = _MOD.measure(content)
    assert always_on is True
    assert tokens > _MOD.MAX_SUBSTANTIVE_TOKENS

    assert result.passed is False
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.always_on is True
    assert finding.over_budget is True
    assert finding.substantive_words > _MOD.MAX_SUBSTANTIVE_TOKENS
