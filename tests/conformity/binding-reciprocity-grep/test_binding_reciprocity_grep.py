# SPDX-License-Identifier: MIT

"""Behavioral pass+fail coverage for the binding-reciprocity matcher.

The per-file matcher enforces the in-file notation discipline of the
Bindings section: canonical Unicode arrows pass; ASCII-substitute arrows
(``->``, ``<-``, ``<->``) inside the Bindings region fail. Content with no
Bindings section passes (not every artifact carries one). The half-edge
case here is the notation-drift half-edge the per-file grep is scoped to
catch (cross-file reciprocity is the orchestrator's corpus walk).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "binding_reciprocity_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "binding_reciprocity_grep", _GREP_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["binding_reciprocity_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()
_PATH: Final[Path] = Path("rules/sample.md")

_CANONICAL_BINDINGS: Final[str] = "\n".join(
    [
        "# Rule: Sample",
        "",
        "Body prose here.",
        "",
        "## Bindings (§0.j five-direction)",
        "",
        "- **Drives →** the downstream consumer",
        "- **Driven by ←** the upstream gate",
        "- **Established by ↑** the ratifying registry",
        "- **Cross-bound with ↔** the sibling rule",
    ]
)


def test_canonical_arrows_pass() -> None:
    result = _MOD.check(_CANONICAL_BINDINGS, _PATH)
    assert result.passed, [f.match for f in result.findings]
    assert result.findings == []


def test_no_bindings_section_passes() -> None:
    body = "# Rule: Sample\n\nNarrative prose with no Bindings section.\n"
    result = _MOD.check(body, _PATH)
    assert result.passed


def test_inline_code_arrow_in_bindings_is_not_flagged() -> None:
    # An ASCII arrow inside an inline-code span quotes a signature, not the
    # Bindings notation, so it must not be flagged.
    body = "\n".join(
        [
            "## Bindings (§0.j five-direction)",
            "",
            "- **Drives →** the consumer with signature `materialize(p) -> str`",
            "- **Driven by ←** the upstream gate",
        ]
    )
    result = _MOD.check(body, _PATH)
    assert result.passed, [f.match for f in result.findings]


def test_fenced_code_arrow_in_bindings_is_not_flagged() -> None:
    body = "\n".join(
        [
            "## Bindings (§0.j five-direction)",
            "",
            "- **Drives →** the consumer",
            "",
            "```python",
            "def f() -> str: ...",
            "```",
        ]
    )
    result = _MOD.check(body, _PATH)
    assert result.passed, [f.match for f in result.findings]


def test_prose_arrow_still_flagged_when_inline_code_present() -> None:
    # The inline-code span is excluded, but a real prose ASCII arrow on the
    # same line is still flagged.
    body = "\n".join(
        [
            "## Bindings (§0.j five-direction)",
            "",
            "- **Drives** -> target while `f() -> str` stays code",
        ]
    )
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert len(result.findings) == 1
    assert result.findings[0].match == "->"


def test_ascii_arrow_in_bindings_fails() -> None:
    body = _CANONICAL_BINDINGS.replace(
        "- **Drives →** the downstream consumer",
        "- **Drives ->** the downstream consumer",
    )
    result = _MOD.check(body, _PATH)
    assert not result.passed
    assert any(f.match == "->" for f in result.findings)


def test_multiple_ascii_arrows_all_flagged() -> None:
    body = "\n".join(
        [
            "## Bindings (§0.j five-direction)",
            "",
            "- **Drives ->** target",
            "- **Driven by <-** source",
        ]
    )
    result = _MOD.check(body, _PATH)
    assert not result.passed
    matches = {f.match for f in result.findings}
    assert "->" in matches
    assert "<-" in matches


def test_ascii_arrow_outside_bindings_region_passes() -> None:
    # Prose above the Bindings heading may legitimately use ASCII arrows;
    # the matcher scans only inside the Bindings region.
    body = "\n".join(
        [
            "# Rule: Sample",
            "",
            "A -> B is a flow described in prose.",
            "",
            "## Bindings (§0.j five-direction)",
            "",
            "- **Drives →** the downstream consumer",
        ]
    )
    result = _MOD.check(body, _PATH)
    assert result.passed
