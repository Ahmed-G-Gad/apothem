# SPDX-License-Identifier: MIT

"""GitHub Copilot and Cursor install, verify, update and uninstall their native subagents.

Copilot writes one ``<name>.agent.md`` custom agent profile per Apothem agent into
``<project>/.github/agents/``; Cursor writes one ``<name>.md`` subagent into
``<project>/.cursor/agents/``. Neither writes a user-level agents folder, the
shared ``.agents/agents`` root or a copy in the Claude Code folder. These tests
drive the real manifest over the real agents corpus with the user home isolated
per test (``tests/conftest.py``).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_agent_copilot_cursor import (
    copilot_agent_text,
    cursor_agent_text,
)
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class
from apothem.lib.propagation import user_home

#: public id -> (project folder, agent-mode name, file suffix, renderer)
_HARNESSES: dict[str, tuple[str, str, str, Callable[[Path], str]]] = {
    "cursor": (".cursor", "cursor_agents", ".md", cursor_agent_text),
    "github-copilot": (
        ".github",
        "copilot_agents",
        ".agent.md",
        copilot_agent_text,
    ),
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


def _names(public_id: str) -> list[str]:
    suffix = _HARNESSES[public_id][2]
    return sorted(f"{s.stem}{suffix}" for s in _SOURCES)


@pytest.mark.parametrize("public_id", _IDS)
def test_install_writes_one_native_file_per_agent_into_the_project(
    public_id: str, tmp_path: Path
) -> None:
    render = _HARNESSES[public_id][3]
    suffix = _HARNESSES[public_id][2]
    project = _project(tmp_path)
    _adapter(public_id).install({}, project=project)

    agents = _agents_dir(project, public_id)
    assert sorted(p.name for p in agents.iterdir()) == _names(public_id)
    assert len(_SOURCES) == 14
    for source in _SOURCES:
        data = (agents / f"{source.stem}{suffix}").read_bytes()
        assert data == render(source).encode("utf-8"), source.name
        assert not data.startswith(b"\xef\xbb\xbf"), "no BOM"
        assert b"\r" not in data, "LF only"


def test_copilot_files_carry_the_double_extension_and_no_plain_md_copy(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter("github-copilot").install({}, project=project)
    agents = _agents_dir(project, "github-copilot")
    assert all(p.name.endswith(".agent.md") for p in agents.iterdir())
    # The instructions file beside the folder is untouched by the agents entry.
    assert (project / ".github" / "copilot-instructions.md").is_file()


def test_cursor_flags_readonly_on_exactly_the_five_agents_that_cannot_run_commands(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter("cursor").install({}, project=project)
    agents = _agents_dir(project, "cursor")
    flagged = sorted(
        p.stem
        for p in agents.glob("*.md")
        if "\nreadonly: true\n" in p.read_text(encoding="utf-8")
    )
    assert flagged == [
        "citation-auditor",
        "convention-auditor",
        "fact-checker",
        "memory-auditor",
        "research-scout",
    ]
    for path in agents.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        head = text[: text.index("\n---\n", 4)]
        assert "\ntools:" not in head, path.name
        assert "\nmodel:" not in head, path.name


@pytest.mark.parametrize("public_id", _IDS)
def test_no_other_agents_location_is_written(public_id: str, tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter(public_id).install({}, project=project)

    # The shared cross-tool root and the Claude Code folder stay unwritten, in the
    # project and in the user home.
    for root in (project, user_home()):
        assert not (root / ".agents" / "agents").exists()
        assert not (root / ".claude" / "agents").exists()
    # The user-level agents folders of both vendors stay unwritten.
    for name in (".cursor", ".copilot"):
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
    folder, mode, _, _ = _HARNESSES[public_id]
    key = get_harness_entry(public_id).package_key
    plan = install_driver.build_plan(key, project_root=tmp_path)
    entries = [e for e in plan if e["mode"] == mode]
    assert len(entries) == 1
    assert Path(entries[0]["target"]) == tmp_path / folder / "agents"


@pytest.mark.parametrize("public_id", _IDS)
def test_install_update_verify_and_uninstall_round_trip(
    public_id: str, tmp_path: Path
) -> None:
    mode = _HARNESSES[public_id][1]
    suffix = _HARNESSES[public_id][2]
    project = _project(tmp_path)
    adapter = _adapter(public_id)
    agents = _agents_dir(project, public_id)
    # Files the operator already keeps there: one an Apothem agent will replace,
    # one it never touches.
    agents.mkdir(parents=True)
    (agents / f"test-runner{suffix}").write_text(
        "operator test-runner\n", encoding="utf-8"
    )
    (agents / f"my-agent{suffix}").write_text("operator my-agent\n", encoding="utf-8")

    first = adapter.install({}, project=project)
    assert adapter.is_installed(project=project) is True
    assert adapter.verify(project=project) is True
    outcomes = {
        Path(r.path).name: r.outcome for r in first.results if r.operation == mode
    }
    assert len(outcomes) == len(_SOURCES)
    assert outcomes[f"test-runner{suffix}"] == "updated"  # the operator's, backed up
    assert (agents / f"my-agent{suffix}").read_text(encoding="utf-8") == (
        "operator my-agent\n"
    )
    assert "operator" not in (agents / f"test-runner{suffix}").read_text(
        encoding="utf-8"
    )

    # An update over an unchanged install rewrites nothing.
    update = adapter.update({}, project=project)
    assert {r.outcome for r in update.results if r.operation == mode} == {"unchanged"}

    # A missing agents folder fails verify, and an update restores it.
    shutil.rmtree(agents)
    assert adapter.verify(project=project) is False
    adapter.update({}, project=project)
    assert adapter.verify(project=project) is True
    assert len(list(agents.glob(f"*{suffix}"))) == len(_SOURCES)
    (agents / f"my-agent{suffix}").write_text("operator my-agent\n", encoding="utf-8")

    # An edit to one of Apothem's files is overwritten by the next update.
    (agents / f"fact-checker{suffix}").write_text("edited\n", encoding="utf-8")
    adapter.update({}, project=project)
    assert (agents / f"fact-checker{suffix}").read_bytes().startswith(b"---\nname:")

    # The uninstall removes Apothem's files and keeps the operator's.
    adapter.uninstall(project=project)
    assert adapter.is_installed(project=project) is False
    assert sorted(p.name for p in agents.iterdir()) == [f"my-agent{suffix}"]


@pytest.mark.parametrize("public_id", _IDS)
def test_uninstall_leaves_no_agents_folder_when_the_operator_kept_nothing(
    public_id: str, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    adapter = _adapter(public_id)
    adapter.install({}, project=project)
    adapter.uninstall(project=project)
    assert not _agents_dir(project, public_id).exists()


def test_copilot_uninstall_keeps_the_operators_instructions_and_other_github_files(
    tmp_path: Path,
) -> None:
    """The ``.github`` folder is shared with workflows and the instructions file."""
    project = _project(tmp_path)
    workflows = project / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    adapter = _adapter("github-copilot")
    adapter.install({}, project=project)
    adapter.uninstall(project=project)
    assert (workflows / "ci.yml").read_text(encoding="utf-8") == "name: ci\n"
    assert not _agents_dir(project, "github-copilot").exists()


def test_the_cursor_and_copilot_copies_do_not_collide_in_one_project(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter("cursor").install({}, project=project)
    _adapter("github-copilot").install({}, project=project)
    assert len(list(_agents_dir(project, "cursor").iterdir())) == 14
    assert len(list(_agents_dir(project, "github-copilot").iterdir())) == 14
    _adapter("cursor").uninstall(project=project)
    assert not _agents_dir(project, "cursor").exists()
    assert len(list(_agents_dir(project, "github-copilot").iterdir())) == 14
