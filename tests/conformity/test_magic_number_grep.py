# SPDX-License-Identifier: MIT

"""Behavior contract for `src/apothem/conformity/magic-number-grep.py`.

Tests cover four contracts: (a) repeated logic literal is flagged;
(b) idiomatic boundary values (0/1/-1/2) are exempt; (c) numeric values
inside triple-quoted docstring spans are stripped before matching so
documentation numerals do not surface as logic-literal findings;
(d) non-code suffixes are skipped silently.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_TOOLS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "conformity"
_MODULE_PATH = _TOOLS_DIR / "magic_number_grep.py"


def _load_module():
    """Load the hyphen-named matcher module via importlib spec.

    Registers the module in `sys.modules` before `exec_module` so
    dataclass introspection (Python 3.14+) can resolve `cls.__module__`
    against the live module record. Without the registration, frozen
    dataclasses inside the loaded module raise AttributeError on first
    instantiation.
    """
    spec = importlib.util.spec_from_file_location("magic_number_grep", _MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module spec from {_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["magic_number_grep"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def matcher():
    """Return the loaded magic-number-grep module."""
    return _load_module()


def test_repeated_logic_literal_is_flagged(matcher) -> None:
    """A literal repeated 2+ times in logic context produces a finding."""
    content = (
        "def retry_with_budget(operation):\n"
        "    for attempt in range(7):\n"
        "        try:\n"
        "            return operation(timeout=7)\n"
        "        except TimeoutError:\n"
        "            continue\n"
        "    raise RuntimeError('exhausted 7 attempts')\n"
    )
    result = matcher.check(content, Path("src/retry.py"))

    assert result.passed is False
    assert any(f.value == "7" and len(f.occurrences) >= 2 for f in result.findings)


def test_idiomatic_boundary_values_are_exempt(matcher) -> None:
    """0, 1, -1, 2 are EXEMPT_VALUES even when repeated."""
    content = (
        "def slice_head(items):\n"
        "    if len(items) == 0:\n"
        "        return []\n"
        "    if len(items) == 1:\n"
        "        return items[0:1]\n"
        "    return items[0:2]\n"
    )
    result = matcher.check(content, Path("src/slice.py"))

    assert result.passed is True
    assert result.findings == []


def test_triple_quoted_docstring_numerals_are_stripped(matcher) -> None:
    """Numerals inside `\"\"\"...\"\"\"` spans must not surface as findings.

    Triple-quoted spans are documentation context, not logic context;
    their numerals are stripped before line iteration.
    """
    content = (
        '"""Module docstring describing the 8-surface install matrix.\n'
        "\n"
        "Surfaces: sdist · wheel · tarball · zip · sbom · signature · "
        "manifest · installer.\n"
        "The 8 surfaces cover macOS / Linux / Windows triads.\n"
        '"""\n'
        "\n"
        "from typing import Final\n"
        "\n"
        "RETRY_BUDGET: Final[int] = 3\n"
    )
    result = matcher.check(content, Path("src/install.py"))

    assert result.passed is True
    assert result.findings == []


def test_triple_quoted_single_quote_variant_is_stripped(matcher) -> None:
    """`'''...'''` variant of the triple-quoted span behaves identically."""
    content = (
        "def render():\n"
        "    return '''\n"
        "    The 42-line preamble references 42 across paragraphs;\n"
        "    every 42 in here is documentation, not logic.\n"
        "    '''\n"
    )
    result = matcher.check(content, Path("src/render.py"))

    assert result.passed is True
    assert result.findings == []


def test_non_code_suffixes_pass_silently(matcher) -> None:
    """Markdown / YAML / JSON / TOML / RST / TXT are out of scope."""
    drift_content = "Build 17 retried 17 times before falling back to mode 17.\n"
    for outside_path in (
        Path("docs/index.md"),
        Path("config.yaml"),
        Path("config.yml"),
        Path("package.json"),
        Path("pyproject.toml"),
        Path("README.rst"),
        Path("notes.txt"),
    ):
        result = matcher.check(drift_content, outside_path)
        assert result.passed is True, f"{outside_path} should be exempt"
        assert result.findings == []


def test_named_constant_assignment_line_is_skipped(matcher) -> None:
    """A `NAME: Final[int] = N` line names the constant; the literal is exempt."""
    content = (
        "from typing import Final\n"
        "\n"
        "MAX_RETRIES: Final[int] = 5\n"
        "TIMEOUT_SECONDS: Final[int] = 5\n"
    )
    result = matcher.check(content, Path("src/config.py"))

    assert result.passed is True
    assert result.findings == []


def test_single_occurrence_does_not_trigger(matcher) -> None:
    """One literal in isolation is not the magic-number signal."""
    content = "def f():\n    return 42\n"
    result = matcher.check(content, Path("src/f.py"))

    assert result.passed is True
    assert result.findings == []
