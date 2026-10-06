# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""Behavioral coverage for the five-direction Bindings presence validator.

Every rule, command, agent, and skill closes with a ``## Bindings`` section
carrying Drives, Satisfies, Established by, Gated by, and Cross-bound with;
every hook message carries the Drives, Established by, and Cross-bound with
subset. The fixtures below build a minimal content tree in both supported
layouts (a repository checkout under ``src/apothem/`` and an installed flat
tree) and plant one defect at a time.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.conformity import _grep_base
from apothem.conformity import binding_five_direction_grep as b5

_FULL = """
## Bindings (§0.j five-direction)

- **Drives →** the downstream surface.
- **Satisfies →** the end state.
- **Established by ↑** the anchor.
- **Gated by ←** the activation condition.
- **Cross-bound with ↔** the sibling.
"""

_SUBSET = """
## Bindings (§0.j five-direction)

- **Drives →** the agent's behavior at the event.
- **Established by ↑** the hook registration.
- **Cross-bound with ↔** the sibling message.
"""


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"<!-- SPDX-License-Identifier: MIT -->\n\nBody.\n{body}", encoding="utf-8"
    )


def _corpus(base: Path) -> Path:
    """Write one conformant artifact per stratum under *base*; return *base*."""
    _write(base / "rules" / "sample-rule.md", _FULL)
    _write(base / "commands" / "sample-command.md", _FULL)
    _write(base / "agents" / "sample-agent.md", _FULL)
    _write(base / "skills" / "sample-skill" / "SKILL.md", _FULL)
    _write(base / "hooks" / "messages" / "sample-event.md", _SUBSET)
    return base


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository-checkout layout: the corpus lives under ``src/apothem``."""
    _corpus(tmp_path / "src" / "apothem")
    return tmp_path


def test_conformant_corpus_passes(repo: Path) -> None:
    result = b5.check(repo)
    assert result.passed, [f.detail for f in result.findings]
    assert result.inspected == 5


def test_installed_flat_layout_resolves(tmp_path: Path) -> None:
    """An installed harness tree carries the strata at its root."""
    _corpus(tmp_path)
    result = b5.check(tmp_path)
    assert result.passed
    assert result.inspected == 5


def test_rule_missing_bindings_section_fails(repo: Path) -> None:
    _write(repo / "src" / "apothem" / "rules" / "no-bindings.md", "")
    result = b5.check(repo)
    assert not result.passed
    assert [f.path for f in result.findings] == ["rules/no-bindings.md"]
    assert "no ## Bindings section" in result.findings[0].detail


def test_rule_missing_one_direction_names_it(repo: Path) -> None:
    body = _FULL.replace("- **Gated by ←** the activation condition.\n", "")
    _write(repo / "src" / "apothem" / "rules" / "partial.md", body)
    result = b5.check(repo)
    assert [f.path for f in result.findings] == ["rules/partial.md"]
    assert result.findings[0].missing == ["Gated by ←"]


def test_agent_and_command_need_the_full_set(repo: Path) -> None:
    _write(repo / "src" / "apothem" / "agents" / "subset-agent.md", _SUBSET)
    _write(repo / "src" / "apothem" / "commands" / "subset-command.md", _SUBSET)
    result = b5.check(repo)
    assert sorted(f.path for f in result.findings) == [
        "agents/subset-agent.md",
        "commands/subset-command.md",
    ]


def test_hook_message_missing_bindings_fails(repo: Path) -> None:
    _write(repo / "src" / "apothem" / "hooks" / "messages" / "bare.md", "")
    result = b5.check(repo)
    assert [f.path for f in result.findings] == ["hooks/messages/bare.md"]


def test_folder_readme_is_in_scope(repo: Path) -> None:
    """A convention folder's README carries the folder's own Bindings."""
    _write(repo / "src" / "apothem" / "rules" / "README.md", "")
    result = b5.check(repo)
    assert [f.path for f in result.findings] == ["rules/README.md"]


def test_fenced_example_is_not_a_bindings_section(repo: Path) -> None:
    """A ``## Bindings`` block inside a code fence is an example, not the section."""
    fenced = "\n```markdown" + _FULL + "```\n"
    _write(repo / "src" / "apothem" / "rules" / "example-only.md", fenced)
    result = b5.check(repo)
    assert [f.path for f in result.findings] == ["rules/example-only.md"]


def test_direction_outside_the_section_does_not_count(repo: Path) -> None:
    """A direction label in the body cannot stand in for a missing bullet."""
    body = "\nSee **Gated by ←** in the prose.\n" + _FULL.replace(
        "- **Gated by ←** the activation condition.\n", ""
    )
    _write(repo / "src" / "apothem" / "rules" / "prose-label.md", body)
    result = b5.check(repo)
    assert [f.path for f in result.findings] == ["rules/prose-label.md"]


def test_empty_root_inspects_nothing(tmp_path: Path) -> None:
    result = b5.check(tmp_path)
    assert result.inspected == 0


def test_cli_exit_codes(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Clean exits 0; a finding exits 2; an empty root fails; a missing root is usage."""
    assert b5._main(["prog", str(repo)]) == _grep_base.EXIT_PASS
    payload = json.loads(capsys.readouterr().out)
    assert payload["inspected"] == 5

    _write(repo / "src" / "apothem" / "rules" / "no-bindings.md", "")
    assert b5._main(["prog", str(repo)]) == _grep_base.EXIT_FAIL
    capsys.readouterr()

    empty = tmp_path_factory.mktemp("empty")
    assert b5._main(["prog", str(empty)]) == _grep_base.EXIT_FAIL
    capsys.readouterr()

    with pytest.raises(SystemExit) as excinfo:
        b5._main(["prog", str(empty / "absent")])
    assert excinfo.value.code == _grep_base.EXIT_USAGE


# REUSE-IgnoreEnd
