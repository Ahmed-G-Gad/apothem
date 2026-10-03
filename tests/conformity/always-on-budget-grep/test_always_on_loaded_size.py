# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The always-on matcher reports what a harness actually loads, in named units.

The budget count excludes the ``## Bindings`` section and companion-pointer
lines, yet a harness that loads a rule file strips only the frontmatter. The
excluded regions are most of the always-on text, so the budget number alone
understates the standing context cost several times over. The matcher keeps
its budget verdict unchanged (same exclusions, same 500 ceiling) and adds a
second, stricter measurement: the frontmatter-stripped body in UTF-8 bytes,
characters and whitespace-separated words, per rule and summed over the
always-on rules. The count unit is named as words, because that is what a
whitespace split counts; it is not a model-token count.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_MODULE_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "always_on_budget_grep.py"
)
_RULES_DIR: Final[Path] = _REPO_ROOT / "src" / "apothem" / "rules"


def _load() -> ModuleType:
    """Load the matcher module via an importlib spec."""
    spec = importlib.util.spec_from_file_location(
        "always_on_budget_grep_loaded_size", _MODULE_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["always_on_budget_grep_loaded_size"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()

_FRONTMATTER: Final[str] = (
    '---\nname: "probe"\nalwaysApply: true\npathFilter: ""\n---\n'
)
_BODY: Final[str] = (
    "<!-- SPDX-License-Identifier: MIT -->\n\n"
    "# Rule: Probe\n\n"
    "Directive text with § and → glyphs.\n"
    "(Companion Sub-Rule Anchor) See the companion for the rest.\n\n"
    "## Bindings (§0.j five-direction)\n\n"
    "- **Drives →** ● one peer.\n"
)


def _loaded_body(text: str) -> str:
    """Independent reference: everything after the closing frontmatter line."""
    match = re.match(r"---\n.*?\n---\n", text, re.DOTALL)
    assert match is not None
    return text[match.end() :]


def test_finding_reports_loaded_size_including_excluded_regions(tmp_path: Path) -> None:
    rule = tmp_path / "probe.md"
    rule.write_text(_FRONTMATTER + _BODY, encoding="utf-8")

    finding = _MOD.check_file(rule)

    assert finding.loaded_bytes == len(_BODY.encode("utf-8"))
    assert finding.loaded_chars == len(_BODY)
    assert finding.loaded_words == len(_BODY.split())
    # The budget count still excludes Bindings and pointer lines, so it is
    # strictly smaller than the loaded word count.
    assert finding.substantive_words < finding.loaded_words


def test_budget_unit_is_named_words_and_threshold_is_unchanged(tmp_path: Path) -> None:
    rule = tmp_path / "probe.md"
    rule.write_text(_FRONTMATTER + _BODY, encoding="utf-8")
    result = _MOD.GrepResult(
        grep=_MOD.GREP_NAME, passed=True, findings=[_MOD.check_file(rule)]
    )

    payload = json.loads(result.to_json())

    assert payload["max-substantive-words"] == 500
    assert payload["count-unit"] == "whitespace-separated words"
    assert "max-substantive-tokens" not in payload
    assert "substantive_words" in payload["findings"][0]
    assert "substantive_tokens" not in payload["findings"][0]


def test_aggregate_covers_always_on_rules_only(tmp_path: Path) -> None:
    always_on = tmp_path / "on.md"
    always_on.write_text(_FRONTMATTER + _BODY, encoding="utf-8")
    scoped = tmp_path / "scoped.md"
    scoped.write_text(
        '---\nalwaysApply: false\npathFilter: "src/**"\n---\nscoped body\n',
        encoding="utf-8",
    )
    findings = [_MOD.check_file(always_on), _MOD.check_file(scoped)]
    result = _MOD.GrepResult(grep=_MOD.GREP_NAME, passed=True, findings=findings)

    aggregate = json.loads(result.to_json())["always-on-loaded"]

    assert aggregate == {
        "rules": 1,
        "bytes": len(_BODY.encode("utf-8")),
        "chars": len(_BODY),
        "words": len(_BODY.split()),
    }


def test_corpus_aggregate_matches_independent_measurement() -> None:
    files = sorted(_RULES_DIR.glob("*.md"))
    expected_bytes = 0
    expected_rules = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not re.search(r"^alwaysApply:\s*true\s*$", text, re.MULTILINE):
            continue
        expected_rules += 1
        expected_bytes += len(_loaded_body(text).encode("utf-8"))
    findings = [_MOD.check_file(path) for path in files]
    result = _MOD.GrepResult(grep=_MOD.GREP_NAME, passed=True, findings=findings)

    aggregate = json.loads(result.to_json())["always-on-loaded"]

    assert aggregate["rules"] == expected_rules
    assert aggregate["bytes"] == expected_bytes


# REUSE-IgnoreEnd
