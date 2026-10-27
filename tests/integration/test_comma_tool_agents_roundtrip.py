# SPDX-License-Identifier: MIT

"""CodeBuddy and Trae install, verify, update and uninstall their native subagents.

Both adapters write one Markdown subagent file per Apothem agent into the
project (``.codebuddy/agents/`` and ``.trae/agents/``) and nothing else for the
agents cohort: no user-level agents folder, no shared ``.agents/agents`` root,
and no copy in the Claude Code folder. These tests drive the real manifest over
the real agents corpus with the user home isolated per test
(``tests/conftest.py``).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_agent_comma_tools import (
    codebuddy_agent_text,
    trae_agent_text,
)
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class
from apothem.lib.propagation import user_home

#: public id -> (project folder, agent-mode name, renderer)
_HARNESSES: dict[str, tuple[str, str, Callable[[Path], str]]] = {
    "codebuddy": (".codebuddy", "codebuddy_agents", codebuddy_agent_text),
    "trae": (".trae", "trae_agents", trae_agent_text),
}
_IDS = sorted(_HARNESSES)
_SOURCES = sorted(
    p
    for p in (Path(install_driver.APOTHEM_SRC) / "agents").glob("*.md")
    if p.name not in {"README.md", "AGENTS.md"}
)


def _adapter(public_id: str):  # the adapter classes are generated
    return load_adapter_class(get_harness_entry(public_id))()


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project


def _agents_dir(project: Path, public_id: str) -> Path:
    return project / _HARNESSES[public_id][0] / "agents"


@pytest.mark.parametrize("public_id", _IDS)
def test_install_writes_one_native_file_per_agent_into_the_project(
    public_id: str, tmp_path: Path
) -> None:
    _, _, render = _HARNESSES[public_id]
    project = _project(tmp_path)
    _adapter(public_id).install({}, project=project)

    agents = _agents_dir(project, public_id)
    assert sorted(p.name for p in agents.iterdir()) == [s.name for s in _SOURCES]
    assert len(_SOURCES) == 14
    for source in _SOURCES:
        data = (agents / source.name).read_bytes()
        assert data == render(source).encode("utf-8"), source.name
        assert not data.startswith(b"\xef\xbb\xbf"), "no BOM"
        assert b"\r" not in data, "LF only"


@pytest.mark.parametrize("public_id", _IDS)
def test_no_other_agents_location_is_written(public_id: str, tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter(public_id).install({}, project=project)

    # The shared cross-tool root and the Claude Code folder stay unwritten, in the
    # project and in the user home.
    for root in (project, user_home()):
        assert not (root / ".agents" / "agents").exists()
        assert not (root / ".claude" / "agents").exists()
    # The user-level agents folders (and Trae's .trae-cn spelling) stay unwritten.
    for name in (".codebuddy", ".trae", ".trae-cn"):
        assert not (user_home() / name / "agents").exists(), name
    # The project gains the vendor folder and the data home it always had.
    folder = _HARNESSES[public_id][0]
    assert {p.name for p in project.iterdir()} <= {folder, ".apothem"}


@pytest.mark.parametrize("public_id", _IDS)
def test_dry_run_lists_the_agents_and_writes_nothing(
    public_id: str, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    run = _adapter(public_id).preview({}, project=project)
    # The preview classifies the entry once: it would create the cohort.
    agents = [r for r in run.results if r.operation == _HARNESSES[public_id][1]]
    assert [r.outcome for r in agents] == ["created"]
    assert list(project.iterdir()) == []


@pytest.mark.parametrize("public_id", _IDS)
def test_the_plan_names_the_project_agents_folder(
    public_id: str, tmp_path: Path
) -> None:
    folder, mode, _ = _HARNESSES[public_id]
    plan = install_driver.build_plan(public_id, project_root=tmp_path)
    entries = [e for e in plan if e["mode"] == mode]
    assert len(entries) == 1
    assert Path(entries[0]["target"]) == tmp_path / folder / "agents"


@pytest.mark.parametrize("public_id", _IDS)
def test_install_update_verify_and_uninstall_round_trip(
    public_id: str, tmp_path: Path
) -> None:
    mode = _HARNESSES[public_id][1]
    project = _project(tmp_path)
    adapter = _adapter(public_id)
    agents = _agents_dir(project, public_id)
    # Files the operator already keeps there: one an Apothem agent will replace,
    # one it never touches.
    agents.mkdir(parents=True)
    (agents / "test-runner.md").write_text("operator test-runner\n", encoding="utf-8")
    (agents / "my-agent.md").write_text("operator my-agent\n", encoding="utf-8")

    first = adapter.install({}, project=project)
    assert adapter.is_installed(project=project) is True
    assert adapter.verify(project=project) is True
    outcomes = {
        Path(r.path).name: r.outcome for r in first.results if r.operation == mode
    }
    assert len(outcomes) == len(_SOURCES)
    assert outcomes["test-runner.md"] == "updated"  # the operator's file, backed up
    assert (agents / "my-agent.md").read_text(encoding="utf-8") == (
        "operator my-agent\n"
    )
    assert "operator" not in (agents / "test-runner.md").read_text(encoding="utf-8")

    # An update over an unchanged install rewrites nothing.
    update = adapter.update({}, project=project)
    assert {r.outcome for r in update.results if r.operation == mode} == {"unchanged"}

    # A missing agents folder fails verify, and an update restores it.
    shutil.rmtree(agents)
    assert adapter.verify(project=project) is False
    adapter.update({}, project=project)
    assert adapter.verify(project=project) is True
    assert len(list(agents.glob("*.md"))) == len(_SOURCES)
    (agents / "my-agent.md").write_text("operator my-agent\n", encoding="utf-8")

    # An edit to one of Apothem's files is overwritten by the next update.
    (agents / "fact-checker.md").write_text("edited\n", encoding="utf-8")
    adapter.update({}, project=project)
    assert (agents / "fact-checker.md").read_bytes().startswith(b"---\nname:")

    # The uninstall removes Apothem's files and keeps the operator's.
    adapter.uninstall(project=project)
    assert adapter.is_installed(project=project) is False
    assert sorted(p.name for p in agents.iterdir()) == ["my-agent.md"]


@pytest.mark.parametrize("public_id", _IDS)
def test_uninstall_leaves_no_agents_folder_when_the_operator_kept_nothing(
    public_id: str, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    adapter = _adapter(public_id)
    adapter.install({}, project=project)
    adapter.uninstall(project=project)
    assert not _agents_dir(project, public_id).exists()
