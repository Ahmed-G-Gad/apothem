# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""Claude Code rule scoping: ``pathFilter`` becomes the native ``paths:`` list.

Claude Code loads every file under ``~/.claude/rules/`` at launch unless its
frontmatter carries ``paths:``, the only rule field it reads. The corpus marks
path-scoped rules with the harness-neutral ``pathFilter`` key, so a verbatim
copy loaded all 91 rules in every session. The claude_code install renders each
rule through ``_claude_rule_text``, which adds ``paths:`` for path-filtered
rules and leaves always-on rules byte-identical.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared.install_driver_converters import _claude_rule_text

_REPO = Path(__file__).resolve().parents[2]
_RULES = _REPO / "src" / "apothem" / "rules"


def _frontmatter(text: str) -> dict[str, object]:
    assert text.startswith("---\n")
    block = text.split("\n---\n", 1)[0][4:]
    loaded = yaml.safe_load(block)
    assert isinstance(loaded, dict)
    return loaded


def _rule(tmp_path: Path, path_filter: str, always: bool) -> Path:
    path = tmp_path / "r.md"
    path.write_text(
        "---\n"
        'name: "r"\n'
        'description: "A rule."\n'
        f'pathFilter: "{path_filter}"\n'
        f"alwaysApply: {'true' if always else 'false'}\n"
        "---\n\n<!-- SPDX-License-Identifier: MIT -->\n\n# Rule\n",
        encoding="utf-8",
    )
    return path


def test_path_filter_becomes_a_paths_list(tmp_path: Path) -> None:
    source = _rule(tmp_path, "**/*.py, **/pyproject.toml", always=False)
    rendered = _claude_rule_text(source)
    assert _frontmatter(rendered)["paths"] == ["**/*.py", "**/pyproject.toml"]
    original = source.read_text(encoding="utf-8")
    assert rendered.split("\n---\n", 1)[1] == original.split("\n---\n", 1)[1]


def test_always_on_rule_is_unchanged(tmp_path: Path) -> None:
    source = _rule(tmp_path, "", always=True)
    assert _claude_rule_text(source) == source.read_text(encoding="utf-8")


def test_every_shipped_rule_renders_to_its_intended_scope() -> None:
    scoped = unscoped = 0
    for path in sorted(_RULES.glob("*.md")):
        if path.name in {"README.md", "AGENTS.md"}:
            continue
        source = _frontmatter(path.read_text(encoding="utf-8"))
        rendered = _frontmatter(_claude_rule_text(path))
        if str(source.get("pathFilter") or "").strip():
            assert rendered.get("paths"), path.name
            assert source.get("alwaysApply") is False, path.name
            scoped += 1
        else:
            assert "paths" not in rendered, path.name
            assert source.get("alwaysApply") is True, path.name
            unscoped += 1
    assert scoped > 0
    assert unscoped > 0


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX home layout")
def test_engine_install_scopes_path_filtered_rules(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **{
            k: v
            for k, v in os.environ.items()
            if k not in {"CODEX_HOME", "XDG_CONFIG_HOME"}
        },
        "HOME": str(home),
        "USERPROFILE": str(home),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "PYTHONPATH": str(_REPO / "src"),
    }
    for argv in (["profile", "init"], ["install", "--harness", "claude-code", "--yes"]):
        done = subprocess.run(
            [sys.executable, "-m", "apothem", *argv],
            env=env,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode == 0, done.stdout + done.stderr
    installed = sorted((home / ".claude" / "rules").glob("*.md"))
    assert installed
    loaded_at_launch = [
        p.name for p in installed if "paths" not in _frontmatter(p.read_text("utf-8"))
    ]
    always_on = [
        p.name
        for p in sorted(_RULES.glob("*.md"))
        if p.name not in {"README.md", "AGENTS.md"}
        and _frontmatter(p.read_text("utf-8")).get("alwaysApply") is True
    ]
    assert loaded_at_launch == always_on


# REUSE-IgnoreEnd
