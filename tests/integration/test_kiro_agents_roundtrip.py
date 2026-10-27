# SPDX-License-Identifier: MIT

"""Kiro installs, verifies, updates and uninstalls its native custom agents.

Kiro (IDE 1.0 and CLI V3) reads Markdown agents from ``<project>/.kiro/agents/``;
the install writes one ``<name>.md`` per Apothem agent there, all fourteen, and no
JSON profile. It writes no user-level agents folder (``~/.kiro/agents/``), no copy in
the Claude Code folder and no shared ``.agents/agents`` root. These tests drive the
real manifest over the real agents corpus with the user home isolated per test
(``tests/conftest.py``).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_agent_kiro import kiro_agent_text
from apothem.lib import propagation
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class
from apothem.lib.propagation import user_home

_SOURCES = sorted(
    p
    for p in (Path(install_driver.APOTHEM_SRC) / "agents").glob("*.md")
    if p.name not in {"README.md", "AGENTS.md"}
)
_NAMES = sorted(p.name for p in _SOURCES)
_MODE = "kiro_agents"


def _adapter():  # the adapter classes are generated
    return load_adapter_class(get_harness_entry("kiro"))()


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project


def _agents(project: Path) -> Path:
    return project / ".kiro" / "agents"


def test_install_writes_one_markdown_file_per_agent_into_the_project(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    agents = _agents(project)
    assert len(_NAMES) == 14
    assert sorted(p.name for p in agents.iterdir()) == _NAMES
    for source in _SOURCES:
        data = (agents / source.name).read_bytes()
        assert data == kiro_agent_text(source).encode("utf-8"), source.name
        assert not data.startswith(b"\xef\xbb\xbf"), "no BOM"
        assert b"\r" not in data, "LF only"


def test_no_json_profile_and_no_cli_2x_key_is_written(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    assert list((project / ".kiro").rglob("*.json")) == []
    for path in _agents(project).glob("*.md"):
        text = path.read_text(encoding="utf-8")
        head = text[: text.index("\n---\n", 4)]
        assert head.startswith("---\nname: "), path.name
        assert "\ntools: [" in head, path.name
        for banned in (
            "\nmodel:",
            "\nallowedTools:",
            "\ntoolsSettings:",
            "\npermissions:",
            "\nexcludedTools:",
            "\nresources:",
            "\nhooks:",
            "\ndisallowedTools:",
            "\nmaxTurns:",
        ):
            assert banned not in head, (path.name, banned)


def test_every_agent_keeps_its_read_only_tag_set(tmp_path: Path) -> None:
    """The write tag reaches only the two agents that edit files."""
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    with_write = {
        path.stem
        for path in _agents(project).glob("*.md")
        if '"write"' in path.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    }
    assert with_write == {"mcp-builder", "refactor-surgeon"}


def test_no_other_agents_location_is_written(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)

    # The shared cross-tool root and the Claude Code folder stay unwritten, in the
    # project and in the user home, and so does Kiro's own user-level folder.
    for root in (project, user_home()):
        assert not (root / ".agents" / "agents").exists()
        assert not (root / ".claude" / "agents").exists()
    assert not (user_home() / ".kiro" / "agents").exists()
    # The project gains the vendor folder and the data home it always had.
    assert {p.name for p in project.iterdir()} <= {".kiro", ".apothem"}
    assert sorted(p.name for p in (project / ".kiro").iterdir()) == [
        "agents",
        "steering",
    ]


def test_the_steering_anchor_names_the_agents_folder(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    anchor = (project / ".kiro" / "steering" / "apothem-rules.md").read_text(
        encoding="utf-8"
    )
    assert ".kiro/agents/" in anchor
    assert "definitions and hook helpers are not installed" not in anchor


def test_dry_run_lists_the_agents_and_writes_nothing(tmp_path: Path) -> None:
    project = _project(tmp_path)
    run = _adapter().preview({}, project=project)
    # The preview classifies the entry once: it would create the cohort.
    agents = [r for r in run.results if r.operation == _MODE]
    assert [r.outcome for r in agents] == ["created"]
    assert list(project.iterdir()) == []


def test_the_plan_names_the_project_agents_folder_only(tmp_path: Path) -> None:
    plan = install_driver.build_plan("kiro", project_root=tmp_path)
    entries = [e for e in plan if e["mode"] == _MODE]
    assert len(entries) == 1
    assert Path(entries[0]["target"]) == tmp_path / ".kiro" / "agents"
    # The user-level agents folder is not a plan target.
    assert not [
        e for e in plan if Path(e["target"]) == user_home() / ".kiro" / "agents"
    ]


def test_manifest_has_no_stale_sweep_because_no_release_shipped_kiro_agents() -> None:
    rules = propagation.load_manifest()["kiro"]
    assert not rules.stale_sweep
    agents = [e for e in rules.install if e.source == "agents/"]
    assert [(e.mode, e.target, e.ownership_class) for e in agents] == [
        (_MODE, "${PROJECT_ROOT}/.kiro/agents/", "apothem-owned")
    ]


def test_install_update_verify_and_uninstall_round_trip(tmp_path: Path) -> None:
    project = _project(tmp_path)
    adapter = _adapter()
    agents = _agents(project)
    # Files the operator already keeps there: one an Apothem agent will replace,
    # one it never touches, and a Kiro JSON profile it never touches either.
    agents.mkdir(parents=True)
    (agents / "test-runner.md").write_text("operator test-runner\n", encoding="utf-8")
    (agents / "my-agent.md").write_text("operator my-agent\n", encoding="utf-8")
    (agents / "legacy.json").write_text('{"name": "legacy"}\n', encoding="utf-8")

    first = adapter.install({}, project=project)
    assert adapter.is_installed(project=project) is True
    assert adapter.verify(project=project) is True
    outcomes = {
        Path(r.path).name: r.outcome for r in first.results if r.operation == _MODE
    }
    assert len(outcomes) == len(_NAMES)
    assert outcomes["test-runner.md"] == "updated"  # the operator's, backed up
    assert (agents / "my-agent.md").read_text(encoding="utf-8") == (
        "operator my-agent\n"
    )
    assert (agents / "legacy.json").read_text(encoding="utf-8") == (
        '{"name": "legacy"}\n'
    )
    assert "operator" not in (agents / "test-runner.md").read_text(encoding="utf-8")

    # An update over an unchanged install rewrites nothing.
    update = adapter.update({}, project=project)
    assert {r.outcome for r in update.results if r.operation == _MODE} == {"unchanged"}

    # A missing agents folder fails verify, and an update restores it.
    shutil.rmtree(agents)
    assert adapter.verify(project=project) is False
    adapter.update({}, project=project)
    assert adapter.verify(project=project) is True
    assert len(list(agents.glob("*.md"))) == len(_NAMES)
    (agents / "my-agent.md").write_text("operator my-agent\n", encoding="utf-8")

    # An edit to one of Apothem's files is overwritten by the next update.
    (agents / "memory-auditor.md").write_text("edited\n", encoding="utf-8")
    adapter.update({}, project=project)
    assert (agents / "memory-auditor.md").read_bytes().startswith(b"---\nname:")

    # The uninstall removes Apothem's files and keeps the operator's.
    adapter.uninstall(project=project)
    assert adapter.is_installed(project=project) is False
    assert sorted(p.name for p in agents.iterdir()) == ["my-agent.md"]


def test_uninstall_leaves_no_agents_folder_when_the_operator_kept_nothing(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    adapter = _adapter()
    adapter.install({}, project=project)
    adapter.uninstall(project=project)
    assert not _agents(project).exists()


@pytest.mark.parametrize("stem", ["research-scout", "fact-checker", "citation-auditor"])
def test_the_web_agents_install_with_the_web_tag(stem: str, tmp_path: Path) -> None:
    """Unlike Devin Local, Kiro names a web tag, so none of the fourteen is held back."""
    project = _project(tmp_path)
    _adapter().install({}, project=project)
    text = (_agents(project) / f"{stem}.md").read_text(encoding="utf-8")
    assert 'tools: ["read", "web"]\n' in text
