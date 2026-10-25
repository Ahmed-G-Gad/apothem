# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The always-on matcher holds the loaded always-on set to a byte ceiling.

The per-rule body budget (500 words) cannot bound the set by itself: the
``## Bindings`` section and companion-pointer lines are excluded from it yet
load with the rule. The matcher therefore reports ``always-on-ceiling-bytes``
and, pointed at a rules directory, fails when the loaded always-on bytes exceed
that ceiling or the rule index exceeds its own. A single-file run never trips
the aggregate, because one file is not the set.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_MODULE_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "always_on_budget_grep.py"
)
_RULES_DIR: Final[Path] = _REPO_ROOT / "src" / "apothem" / "rules"


def _load() -> ModuleType:
    """Load the matcher module via an importlib spec."""
    spec = importlib.util.spec_from_file_location(
        "always_on_budget_grep_ceiling", _MODULE_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["always_on_budget_grep_ceiling"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()

_ALWAYS_ON: Final[str] = '---\nname: "r"\nalwaysApply: true\npathFilter: ""\n---\n'
_SCOPED: Final[str] = '---\nname: "s"\nalwaysApply: false\npathFilter: "src/**"\n---\n'


def _body(word_count: int, word_len: int) -> str:
    """A body of *word_count* words, each *word_len* characters long."""
    return " ".join("w" * word_len for _ in range(word_count)) + "\n"


def _run(target: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict]:
    code = _MOD._main(["always_on_budget_grep", str(target)])
    return code, json.loads(capsys.readouterr().out)


def test_report_names_the_aggregate_ceiling() -> None:
    result = _MOD.GrepResult(grep=_MOD.GREP_NAME, passed=True, findings=[])
    payload = json.loads(result.to_json())
    assert payload["always-on-ceiling-bytes"] == _MOD.MAX_ALWAYS_ON_LOADED_BYTES
    assert isinstance(payload["always-on-ceiling-bytes"], int)


def test_directory_over_the_aggregate_ceiling_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Two bodies under the 500-word budget whose loaded bytes together pass the
    # ceiling: 300 words of 80 characters is about 24 KB each.
    for name in ("one.md", "two.md"):
        (tmp_path / name).write_text(_ALWAYS_ON + _body(300, 80), encoding="utf-8")
    code, payload = _run(tmp_path, capsys)
    assert payload["always-on-loaded"]["bytes"] > _MOD.MAX_ALWAYS_ON_LOADED_BYTES
    assert not any(f["over_budget"] for f in payload["findings"])
    assert code == _MOD.EXIT_FAIL
    assert payload["passed"] is False


def test_directory_under_the_aggregate_ceiling_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "one.md").write_text(_ALWAYS_ON + _body(300, 80), encoding="utf-8")
    code, payload = _run(tmp_path, capsys)
    assert payload["always-on-loaded"]["bytes"] <= _MOD.MAX_ALWAYS_ON_LOADED_BYTES
    assert code == _MOD.EXIT_PASS
    assert payload["passed"] is True


def test_scoped_rules_do_not_count_toward_the_ceiling(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("a.md", "b.md", "c.md"):
        (tmp_path / name).write_text(_SCOPED + _body(300, 80), encoding="utf-8")
    code, payload = _run(tmp_path, capsys)
    assert payload["always-on-loaded"]["bytes"] == 0
    assert code == _MOD.EXIT_PASS


def test_a_single_file_never_trips_the_aggregate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 400 words of 120 characters is about 48 KB: over the aggregate ceiling,
    # under the 500-word body budget.
    rule = tmp_path / "big.md"
    rule.write_text(_ALWAYS_ON + _body(400, 120), encoding="utf-8")
    code, payload = _run(rule, capsys)
    assert payload["always-on-loaded"]["bytes"] > _MOD.MAX_ALWAYS_ON_LOADED_BYTES
    assert code == _MOD.EXIT_PASS


@pytest.mark.parametrize("as_directory", [True, False])
def test_the_index_has_its_own_ceiling(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], as_directory: bool
) -> None:
    index = tmp_path / f"{_MOD.INDEX_RULE_STEM}.md"
    index.write_text(_ALWAYS_ON + _body(300, 20), encoding="utf-8")
    code, payload = _run(tmp_path if as_directory else index, capsys)
    assert payload["findings"][0]["loaded_bytes"] > _MOD.MAX_INDEX_LOADED_BYTES
    assert code == _MOD.EXIT_FAIL


def test_the_shipped_corpus_passes_directory_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, payload = _run(_RULES_DIR, capsys)
    assert code == _MOD.EXIT_PASS, payload["always-on-loaded"]
    assert payload["always-on-loaded"]["bytes"] <= payload["always-on-ceiling-bytes"]


# REUSE-IgnoreEnd
