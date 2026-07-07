# SPDX-License-Identifier: MIT

"""Self-tests for the option-annotation-grep per-option Recommended bind (H6)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "option_annotation_grep.py"
)
_FIXTURE_DIR: Final[Path] = Path(__file__).resolve().parent


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("option_annotation_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["option_annotation_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()
_PASS_BODY: Final[str] = (_FIXTURE_DIR / "pass.md").read_text(encoding="utf-8")
_FAIL_BODY: Final[str] = (_FIXTURE_DIR / "fail.md").read_text(encoding="utf-8")


def _kinds(result: object) -> set[str]:
    return {f.kind for f in result.findings}  # type: ignore[attr-defined]


def test_pass_fixture_passes() -> None:
    result = _MOD.check(_PASS_BODY, _FIXTURE_DIR / "pass.md")
    assert result.passed
    assert result.findings == []


def test_fail_fixture_flags_both_bind_directions() -> None:
    result = _MOD.check(_FAIL_BODY, _FIXTURE_DIR / "fail.md")
    assert not result.passed
    assert "non-canonical-postfix-case" in _kinds(result)
    assert "spurious-postfix" in _kinds(result)


def test_missing_canonical_postfix_on_recommended_body() -> None:
    body = "\n".join(
        [
            "structured inquiry: question `Which path?`",
            "- `Accept`:",
            "  rationale: Promotes the output.",
            "  recommendation: recommended — observed-state: zero open unknowns.",
            "  default-pointer: Accept — reversible.",
            "multiSelect: false",
        ]
    )
    result = _MOD.check(body, Path("commands/x.md"))
    assert not result.passed
    assert "missing-canonical-postfix" in _kinds(result)


def test_lowercase_postfix_is_a_finding() -> None:
    body = "\n".join(
        [
            "structured inquiry: question `Which path?`",
            "- `Accept (recommended)`:",
            "  rationale: Promotes the output.",
            "  recommendation: recommended — observed-state: zero open unknowns.",
            "  default-pointer: Accept — reversible.",
            "multiSelect: false",
        ]
    )
    result = _MOD.check(body, Path("commands/x.md"))
    assert not result.passed
    assert "non-canonical-postfix-case" in _kinds(result)
    # The lowercase variant subsumes the missing-canonical finding (one signal).
    assert "missing-canonical-postfix" not in _kinds(result)


def test_spurious_capital_postfix_on_non_recommended_body() -> None:
    body = "\n".join(
        [
            "structured inquiry: question `Which path?`",
            "- `Override (Recommended)`:",
            "  rationale: Proceeds despite the gap.",
            "  recommendation: discouraged — observed-state: dependency unmet.",
            "  default-pointer: Override — escape hatch.",
            "multiSelect: false",
        ]
    )
    result = _MOD.check(body, Path("commands/x.md"))
    assert not result.passed
    assert "spurious-postfix" in _kinds(result)


def test_single_select_rejects_multiple_recommended() -> None:
    body = "\n".join(
        [
            "structured inquiry: question `Which path?`",
            "- `Patch (Recommended)`:",
            "  rationale: Narrow edit.",
            "  recommendation: recommended — observed-state: patch is small.",
            "  default-pointer: Patch — reversible.",
            "- `Rewrite (Recommended)`:",
            "  rationale: Full replacement.",
            "  recommendation: recommended — observed-state: rewrite is complete.",
            "  default-pointer: Patch — reversible.",
            "multiSelect: false",
        ]
    )
    result = _MOD.check(body, Path("commands/x.md"))
    assert not result.passed
    assert "single-select-multi-recommended" in _kinds(result)


def test_multiselect_allows_multiple_recommended() -> None:
    body = "\n".join(
        [
            "structured inquiry: question `Which add-ons should ship?`",
            "- `Exporter (Recommended)`:",
            "  rationale: Adds metrics.",
            "  recommendation: recommended — observed-state: metrics enabled.",
            "  default-pointer: no-default: user decision required.",
            "- `Audit trail (Recommended)`:",
            "  rationale: Adds event retention.",
            "  recommendation: recommended — observed-state: audit required.",
            "  default-pointer: no-default: user decision required.",
            "multiSelect: true",
        ]
    )
    result = _MOD.check(body, Path("commands/x.md"))
    assert result.passed, [f.kind for f in result.findings]


def test_definitional_rule_files_are_excluded() -> None:
    body = "\n".join(
        [
            "structured inquiry: question `Which path?`",
            "- `Accept (recommended)`:",
            "  recommendation: recommended — definitional example.",
            "multiSelect: false",
        ]
    )
    excluded = Path("src/apothem/rules/interactive-questions-canonical-shapes.md")
    result = _MOD.check(body, excluded)
    assert result.passed


def test_narrative_marker_leak_in_recommendation_segment_is_flagged() -> None:
    body = "\n".join(
        [
            "structured inquiry: question `Which path?`",
            "- `Accept (Recommended)`:",
            "  rationale: Promotes the output.",
            "  recommendation: recommended (Recommended) — observed-state: zero unknowns.",
            "  default-pointer: Accept — reversible.",
            "multiSelect: false",
        ]
    )
    result = _MOD.check(body, Path("commands/x.md"))
    assert not result.passed
    assert "narrative-marker-leak" in _kinds(result)


def test_narrative_marker_leak_prose_form_in_rationale_is_flagged() -> None:
    body = "\n".join(
        [
            "structured inquiry: question `Which path?`",
            "- `Accept (Recommended)`:",
            "  rationale: This is the **Recommended** path for the operator.",
            "  recommendation: recommended — observed-state: zero unknowns.",
            "  default-pointer: Accept — reversible.",
            "multiSelect: false",
        ]
    )
    result = _MOD.check(body, Path("commands/x.md"))
    assert not result.passed
    assert "narrative-marker-leak" in _kinds(result)


def test_label_only_marker_is_not_a_narrative_leak() -> None:
    # The legitimate label postfix must never register as a body-segment leak.
    body = "\n".join(
        [
            "structured inquiry: question `Which path?`",
            "- `Accept (Recommended)`:",
            "  rationale: Promotes the output.",
            "  recommendation: recommended — observed-state: zero unknowns.",
            "  default-pointer: Accept — reversible.",
            "multiSelect: false",
        ]
    )
    result = _MOD.check(body, Path("commands/x.md"))
    assert result.passed, [f.kind for f in result.findings]


def test_narrative_marker_leak_excluded_in_definitional_files() -> None:
    body = "\n".join(
        [
            "structured inquiry: question `Which path?`",
            "- `Accept (Recommended)`:",
            "  rationale: Promotes the output.",
            "  recommendation: recommended (Recommended) — definitional example.",
            "  default-pointer: Accept — reversible.",
            "multiSelect: false",
        ]
    )
    excluded = Path("src/apothem/rules/interactive-questions-canonical-shapes.md")
    result = _MOD.check(body, excluded)
    assert result.passed


def test_narrative_leak_fixture_flags_the_leak() -> None:
    leak_body = (_FIXTURE_DIR / "fail-narrative-leak.md").read_text(encoding="utf-8")
    result = _MOD.check(leak_body, _FIXTURE_DIR / "fail-narrative-leak.md")
    assert not result.passed
    assert "narrative-marker-leak" in _kinds(result)


def test_prose_list_without_recommendation_body_is_ignored() -> None:
    body = "\n".join(
        [
            "Some prose introducing a list of unrelated items:",
            "- `first item`: a description with no recommendation taxonomy value",
            "- `second item`: another plain description line",
        ]
    )
    result = _MOD.check(body, Path("commands/x.md"))
    assert result.passed


def test_two_yaml_single_select_blocks_are_not_merged() -> None:
    # Each YAML `question:` opens its own cardinality block, so two independent
    # single-select questions (one recommended option each) are not read as a
    # single block carrying two recommended options.
    body = "\n".join(
        [
            "question: Which migration approach for table A?",
            "header: Table A",
            "multiSelect: false",
            "options:",
            "  - label: Patch (Recommended)",
            "    rationale: Minimal diff.",
            "    recommendation: recommended — observed-state: one additive column.",
            "    default-pointer: Patch — reversible.",
            "  - label: Rewrite",
            "    rationale: Full rebuild.",
            "    recommendation: discouraged — observed-state: scope is tiny.",
            "    default-pointer: Patch — inferior here.",
            "question: Which migration approach for table B?",
            "header: Table B",
            "multiSelect: false",
            "options:",
            "  - label: Patch (Recommended)",
            "    rationale: Minimal diff.",
            "    recommendation: recommended — observed-state: one additive column.",
            "    default-pointer: Patch — reversible.",
            "  - label: Rewrite",
            "    rationale: Full rebuild.",
            "    recommendation: discouraged — observed-state: scope is tiny.",
            "    default-pointer: Patch — inferior here.",
        ]
    )
    result = _MOD.check(body, Path("commands/x.md"))
    assert result.passed, [f.kind for f in result.findings]


def test_yaml_multiselect_block_does_not_mask_sibling_single_select() -> None:
    # A multiSelect:true question must not mark the whole file multiselect; a
    # sibling single-select question with two recommended options is still
    # flagged.
    body = "\n".join(
        [
            "question: Which add-ons should ship?",
            "header: Add-ons",
            "multiSelect: true",
            "options:",
            "  - label: Exporter (Recommended)",
            "    rationale: Metrics.",
            "    recommendation: recommended — observed-state: metrics enabled.",
            "    default-pointer: no-default: user decision required.",
            "  - label: Audit (Recommended)",
            "    rationale: Retention.",
            "    recommendation: recommended — observed-state: audit required.",
            "    default-pointer: no-default: user decision required.",
            "question: Which single migration approach?",
            "header: Migration",
            "multiSelect: false",
            "options:",
            "  - label: Patch (Recommended)",
            "    rationale: Minimal.",
            "    recommendation: recommended — observed-state: small.",
            "    default-pointer: Patch — reversible.",
            "  - label: Rewrite (Recommended)",
            "    rationale: Full.",
            "    recommendation: recommended — observed-state: complete.",
            "    default-pointer: Patch — reversible.",
        ]
    )
    result = _MOD.check(body, Path("commands/x.md"))
    assert not result.passed
    assert "single-select-multi-recommended" in _kinds(result)
