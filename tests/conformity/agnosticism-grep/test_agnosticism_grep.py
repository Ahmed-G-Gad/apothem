# SPDX-License-Identifier: MIT

"""Self-tests for the agnosticism-grep validator.

The validator walks the four shipped-surface directories under a root and
flags two closed classes: privileging harness-brand references and
re-introduced ``effort:`` / ``model:`` enforcement presets. These tests
scaffold a corpus under ``tmp_path`` to exercise each branch, then assert
the live repository root passes (the canonical green-CI contract)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "agnosticism_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("agnosticism_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["agnosticism_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def _seed(root: Path, rel: str, content: str) -> None:
    """Write ``content`` to ``root/rel``, creating parent directories."""
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def test_clean_shipped_surface_passes(tmp_path: Path) -> None:
    """A harness-neutral, preset-free corpus produces a passing result."""
    _seed(
        tmp_path,
        "src/apothem/rules/sample.md",
        "# Rule\n\nThe harness reads its defaults through this rule.\n",
    )
    _seed(
        tmp_path,
        "src/apothem/commands/sample.md",
        '---\nname: "sample"\ndescription: "x"\n---\n\n# Command\n',
    )
    result = _MOD.check(tmp_path)
    assert result.passed, [str(f) for f in result.findings]
    assert result.scanned_count == 2


def test_seeded_brand_phrase_flagged(tmp_path: Path) -> None:
    """A privileging brand phrase in a shipped surface is flagged."""
    _seed(
        tmp_path,
        "src/apothem/rules/biased.md",
        "# Rule\n\nAugment Claude Code's built-in memory with discipline.\n",
    )
    result = _MOD.check(tmp_path)
    assert not result.passed
    assert any("Claude Code" in f.match for f in result.findings)
    assert any("harness-bias" in f.detail for f in result.findings)


def test_branded_model_flagged(tmp_path: Path) -> None:
    """A branded model name in a shipped surface is flagged."""
    _seed(
        tmp_path,
        "src/apothem/statuslines/statusline.md",
        "# Statusline\n\nExample render: my-project - Claude Opus 4.7 - 47s\n",
    )
    result = _MOD.check(tmp_path)
    assert not result.passed
    assert any("Claude Opus" in f.match for f in result.findings)


def test_catalog_slug_line_exempt(tmp_path: Path) -> None:
    """A per-harness catalog row carrying the slug is not flagged."""
    _seed(
        tmp_path,
        "src/apothem/rules/catalog.md",
        "# Catalog\n\n| claude_code | settings.json | Claude Code settings schema |\n",
    )
    result = _MOD.check(tmp_path)
    assert result.passed, [str(f) for f in result.findings]


def test_fenced_block_exempt(tmp_path: Path) -> None:
    """A brand phrase inside a fenced code block is not flagged."""
    _seed(
        tmp_path,
        "src/apothem/commands/fenced.md",
        "# Command\n\n```text\nexample for Claude Code only\n```\n",
    )
    result = _MOD.check(tmp_path)
    assert result.passed, [str(f) for f in result.findings]


def test_enforcement_preset_flagged(tmp_path: Path) -> None:
    """A re-introduced effort/model frontmatter preset is flagged."""
    _seed(
        tmp_path,
        "src/apothem/commands/preset.md",
        '---\nname: "preset"\neffort: high\n---\n\n# Command\n',
    )
    result = _MOD.check(tmp_path)
    assert not result.passed
    assert any("enforcement-preset" in f.detail for f in result.findings)


def test_skill_enforcement_preset_flagged(tmp_path: Path) -> None:
    """A re-introduced effort/model preset in a skill definition is flagged."""
    _seed(
        tmp_path,
        "src/apothem/skills/sample-skill/SKILL.md",
        '---\nname: "sample-skill"\neffort: high\n---\n\n# Skill\n',
    )
    result = _MOD.check(tmp_path)
    assert not result.passed
    assert any("enforcement-preset" in f.detail for f in result.findings)


def test_agent_enforcement_preset_flagged(tmp_path: Path) -> None:
    """A re-introduced effort/model preset in an agent definition is flagged."""
    _seed(
        tmp_path,
        "src/apothem/agents/sample-agent.md",
        '---\nname: "sample-agent"\neffort: high\n---\n\n# Agent\n',
    )
    result = _MOD.check(tmp_path)
    assert not result.passed
    assert any("enforcement-preset" in f.detail for f in result.findings)


def test_skill_and_agent_without_preset_pass(tmp_path: Path) -> None:
    """A skill and an agent with no effort/model key produce no finding."""
    _seed(
        tmp_path,
        "src/apothem/skills/clean-skill/SKILL.md",
        '---\nname: "clean-skill"\ndescription: "x"\n---\n\n# Skill\n',
    )
    _seed(
        tmp_path,
        "src/apothem/agents/clean-agent.md",
        '---\nname: "clean-agent"\ndescription: "x"\n---\n\n# Agent\n',
    )
    result = _MOD.check(tmp_path)
    assert result.passed, [str(f) for f in result.findings]
    assert result.scanned_count == 2


def test_preset_outside_frontmatter_ignored(tmp_path: Path) -> None:
    """An ``effort:``-shaped line in the body, not frontmatter, is ignored."""
    _seed(
        tmp_path,
        "src/apothem/commands/body.md",
        '---\nname: "body"\n---\n\n# Command\n\neffort: discussed in prose here.\n',
    )
    result = _MOD.check(tmp_path)
    assert result.passed, [str(f) for f in result.findings]


def test_out_of_scope_path_ignored(tmp_path: Path) -> None:
    """Brand references outside the four shipped dirs are not flagged."""
    _seed(
        tmp_path,
        "tests/fixtures/sample.md",
        "# Fixture\n\nThis fixture mentions Claude Code freely.\n",
    )
    _seed(
        tmp_path,
        "src/apothem/harnesses/claude_code/notes.md",
        "# Adapter\n\nThe Claude Code adapter walks its config.\n",
    )
    result = _MOD.check(tmp_path)
    assert result.passed, [str(f) for f in result.findings]
    assert result.scanned_count == 0


def test_real_repo_root_passes() -> None:
    """The validator passes cleanly against this repository's shipped surfaces."""
    result = _MOD.check(_REPO_ROOT)
    assert result.passed, [str(f) for f in result.findings]
