# SPDX-License-Identifier: MIT

"""Self-tests for the frontmatter-grep validator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "frontmatter_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("frontmatter_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["frontmatter_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


_RULE_PASS = """---
name: example-rule
description: A canonical rule body.
alwaysApply: true
---

# Body
"""


_RULE_MISSING_KEY = """---
name: example-rule
description: Missing alwaysApply.
---

# Body
"""


_RULE_NON_KEBAB = """---
name: example-rule
description: Has a camelCase key.
alwaysApply: true
camelCaseKey: bad
---
"""


_NO_FRONTMATTER = """# Body without frontmatter
"""


def test_rule_with_required_keys_passes() -> None:
    result = _MOD.check(_RULE_PASS, Path("src/apothem/rules/example.md"))
    assert result.passed, result.findings


def test_rule_missing_required_key_fails() -> None:
    result = _MOD.check(_RULE_MISSING_KEY, Path("src/apothem/rules/example.md"))
    assert not result.passed
    assert any("alwaysApply" in f.detail for f in result.findings)


def test_non_kebab_key_fails() -> None:
    result = _MOD.check(_RULE_NON_KEBAB, Path("src/apothem/rules/example.md"))
    assert not result.passed
    assert any("camelCaseKey" in f.detail for f in result.findings)


def test_absent_frontmatter_on_rule_fails() -> None:
    result = _MOD.check(_NO_FRONTMATTER, Path("src/apothem/rules/example.md"))
    assert not result.passed
    assert any("frontmatter block absent" in f.detail for f in result.findings)


def test_absent_frontmatter_on_unknown_class_passes() -> None:
    result = _MOD.check(_NO_FRONTMATTER, Path("notes.md"))
    assert result.passed


def test_allowlisted_keys_pass() -> None:
    body = """---
name: example
description: Allow-listed pre-ratification keys are admitted.
pathFilter: "**/*.py"
alwaysApply: false
---
"""
    result = _MOD.check(body, Path("src/apothem/rules/example.md"))
    assert result.passed, result.findings
