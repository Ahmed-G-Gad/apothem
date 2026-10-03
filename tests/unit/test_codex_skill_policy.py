# SPDX-License-Identifier: MIT

"""Codex honours each skill's model-invocation intent.

Codex ignores ``disable-model-invocation``; it controls implicit invocation only
through ``agents/openai.yaml`` beside the skill's ``SKILL.md``, with
``policy.allow_implicit_invocation`` (default ``true``; ``false`` keeps explicit
``$skill`` invocation working), per https://developers.openai.com/codex/skills
(redirects to https://learn.chatgpt.com/docs/build-skills, retrieved
2026-10-02). The codex install writes that file for every skill and
command-skill whose source sets ``disable-model-invocation: true``, and only
for those.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared import install_driver
from apothem.lib.frontmatter import field_value

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"


def _sources() -> dict[str, Path]:
    """Map each installed skill name to its source; a skill wins over a command."""
    sources = {
        command.stem: command
        for command in (_PKG / "commands").glob("*.md")
        if command.name not in {"README.md", "AGENTS.md"}
    }
    sources.update({p.parent.name: p for p in (_PKG / "skills").glob("*/SKILL.md")})
    return sources


def _user_only(path: Path) -> bool:
    return field_value(path, "disable-model-invocation") == "true"


@pytest.fixture(scope="module")
def codex_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    home = tmp_path_factory.mktemp("home")
    install_driver.run_install("codex", harness_root=home / ".codex")
    return home


def test_policy_file_written_exactly_for_user_only_sources(codex_home: Path) -> None:
    skills_root = codex_home / ".agents" / "skills"
    sources = _sources()
    expected = {name for name, path in sources.items() if _user_only(path)}
    assert expected, "corpus has no user-only skill; the test would be vacuous"
    written = {p.parent.parent.name for p in skills_root.glob("*/agents/openai.yaml")}
    assert written == expected
    assert {p.name for p in skills_root.iterdir()} == set(sources)


def test_policy_file_disables_implicit_invocation(codex_home: Path) -> None:
    for policy in (codex_home / ".agents" / "skills").glob("*/agents/openai.yaml"):
        data = yaml.safe_load(policy.read_text(encoding="utf-8"))
        assert data == {"policy": {"allow_implicit_invocation": False}}, policy


def test_skill_md_is_unchanged_for_codex(codex_home: Path) -> None:
    source = _PKG / "skills" / "plan-suite" / "SKILL.md"
    emitted = codex_home / ".agents" / "skills" / "plan-suite" / "SKILL.md"
    assert emitted.read_bytes() == source.read_bytes()


def test_reinstall_and_dry_run_report_unchanged(tmp_path: Path) -> None:
    root = tmp_path / ".codex"
    install_driver.run_install("codex", harness_root=root)
    skill_ops = {"command_skills", "native_skills"}
    run = install_driver.run_install("codex", harness_root=root)
    outcomes = {r.outcome for r in run.results if r.operation in skill_ops}
    assert outcomes == {"unchanged"}
    preview = install_driver.run_install("codex", harness_root=root, dry_run=True)
    previewed = {r.outcome for r in preview.results if r.operation in skill_ops}
    assert previewed == {"unchanged"}


def test_uninstall_removes_policy_files(tmp_path: Path) -> None:
    root = tmp_path / ".codex"
    install_driver.run_install("codex", harness_root=root)
    install_driver.run_uninstall("codex", harness_root=root)
    assert not list((tmp_path / ".agents" / "skills").glob("*/agents/openai.yaml"))
