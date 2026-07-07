# SPDX-License-Identifier: MIT

"""Pass + fail regression fixture for the brand-mark matcher.

The brand-mark matcher classifies each ``Apothem``/``apothem`` occurrence
against per-surface canonical form: display surfaces render the PascalCase
wordmark, identifier surfaces render the lowercase distribution name. This
fixture pins one passing case (compliant per-surface forms) and one failing
case (lowercase wordmark on a display heading) so the matcher's verdict has a
regression anchor the coverage loop recognises.

The richer behaviour contract — out-of-scope skips, fenced-code exclusion,
cross-surface per-line flagging — lives at ``tests/conformity/test_brand_mark_grep.py``;
this in-directory fixture exists so the matcher-coverage loop resolves a
``test_*.py`` under ``brand-mark-grep/`` for the matcher.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_MODULE_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "brand_mark_grep.py"
)


def _load() -> ModuleType:
    """Load the hyphen-named matcher module via an importlib spec."""
    spec = importlib.util.spec_from_file_location("brand_mark_grep", _MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["brand_mark_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def test_pass_compliant_per_surface_forms() -> None:
    """Display wordmark + identifier distribution name on their own surfaces pass."""
    content = (
        "# Apothem\n"
        '<p align="center"><em>Apothem materializes harness-native config</em></p>\n'
        "\n"
        "## Install\n"
        "Run `scoop install apothem` then visit github.com/ahmed-g-gad/apothem.\n"
    )
    result = _MOD.check(content, Path("README.md"))

    assert result.passed is True
    assert result.findings == []


def test_fail_identifier_form_on_display_heading() -> None:
    """A lowercase wordmark on a display heading trips the matcher."""
    content = "# apothem\n\nBody text describing the project.\n"
    result = _MOD.check(content, Path("README.md"))

    assert result.passed is False
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.match == "apothem"
    assert finding.drift == "identifier-form-on-display-surface"
    assert finding.line == 1
