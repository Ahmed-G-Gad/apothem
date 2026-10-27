# SPDX-License-Identifier: MIT

"""Kimi Code and Windsurf install, verify, update and uninstall their native subagents.

Kimi Code writes one ``<name>.md`` sub-agent per Apothem agent into
``<project>/.kimi-code/agents/``; Windsurf (Devin Local) writes eleven of them into
``<project>/.devin/agents/`` and holds back the three that need web tools. Neither
writes a user-level agents folder, the shared ``.agents/agents`` root or a copy in
the Claude Code folder. The Kimi tests also cover the move from the layout earlier
releases used, which kept the agents in the support tree. These tests drive the real
manifest over the real agents corpus with the user home isolated per test
(``tests/conftest.py``).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_agent_kimi_devin import (
    devin_agent_text,
    kimi_agent_text,
)
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class
from apothem.lib.propagation import user_home

_HELD_BACK = frozenset({"citation-auditor", "fact-checker", "research-scout"})

#: public id -> (project folder, agent-mode name, renderer, stems not installed)
_HARNESSES: dict[str, tuple[str, str, Callable[[Path], str], frozenset[str]]] = {
    "kimi-code": (".kimi-code", "kimi_agents", kimi_agent_text, frozenset()),
    "windsurf": (".devin", "devin_agents", devin_agent_text, _HELD_BACK),
}
_IDS = sorted(_HARNESSES)
_SOURCES = sorted(
    p
    for p in (Path(install_driver.APOTHEM_SRC) / "agents").glob("*.md")
    if p.name not in {"README.md", "AGENTS.md"}
)
_LEGACY_KIMI_AGENTS = Path(".kimi-code") / ".apothem" / "support" / "agents"


def _adapter(public_id: str):  # the adapter classes are generated
    return load_adapter_class(get_harness_entry(public_id))()


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project


def _agents_dir(project: Path, public_id: str) -> Path:
    return project / _HARNESSES[public_id][0] / "agents"


def _names(public_id: str) -> list[str]:
    held = _HARNESSES[public_id][3]
    return sorted(f"{s.stem}.md" for s in _SOURCES if s.stem not in held)


def _installed_sources(public_id: str) -> list[Path]:
    held = _HARNESSES[public_id][3]
    return [s for s in _SOURCES if s.stem not in held]


@pytest.mark.parametrize("public_id", _IDS)
def test_install_writes_one_native_file_per_agent_into_the_project(
    public_id: str, tmp_path: Path
) -> None:
    render = _HARNESSES[public_id][2]
    project = _project(tmp_path)
    _adapter(public_id).install({}, project=project)

    agents = _agents_dir(project, public_id)
    assert sorted(p.name for p in agents.iterdir()) == _names(public_id)
    for source in _installed_sources(public_id):
        data = (agents / source.name).read_bytes()
        assert data == render(source).encode("utf-8"), source.name
        assert not data.startswith(b"\xef\xbb\xbf"), "no BOM"
        assert b"\r" not in data, "LF only"


def test_kimi_installs_all_fourteen_and_windsurf_eleven() -> None:
    assert len(_SOURCES) == 14
    assert len(_names("kimi-code")) == 14
    assert len(_names("windsurf")) == 11


def test_windsurf_holds_back_exactly_the_three_web_agents(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _adapter("windsurf").install({}, project=project)
    present = {p.stem for p in _agents_dir(project, "windsurf").iterdir()}
    assert {s.stem for s in _SOURCES} - present == _HELD_BACK


def test_kimi_files_carry_no_model_override_or_template_variable(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter("kimi-code").install({}, project=project)
    for path in _agents_dir(project, "kimi-code").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        head = text[: text.index("\n---\n", 4)]
        for banned in ("\nmodel:", "\noverride:", "\nsubagents:", "\nmaxTurns:"):
            assert banned not in head, (path.name, banned)
        assert "${" not in text, path.name
        if path.stem in _HELD_BACK:
            assert '"FetchURL"' in head, path.name


def test_windsurf_files_carry_lowercase_allowed_tools_and_no_model(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter("windsurf").install({}, project=project)
    for path in _agents_dir(project, "windsurf").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        head = text[: text.index("\n---\n", 4)]
        assert "\nallowed-tools:\n" in head, path.name
        for banned in ("\nmodel:", "\nmax-nesting:", "\ntools:", "\ndisallowedTools:"):
            assert banned not in head, (path.name, banned)


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
    assert not (user_home() / ".kimi-code" / "agents").exists()
    assert not (user_home() / ".config" / "devin" / "agents").exists()
    assert not (user_home() / "AppData" / "Roaming" / "devin" / "agents").exists()
    # The project gains the vendor folder, the data home it always had and, for
    # Kimi Code, the AGENTS.md anchor.
    folder = _HARNESSES[public_id][0]
    allowed = {folder, ".apothem"} | (
        {"AGENTS.md"} if public_id == "kimi-code" else set()
    )
    assert {p.name for p in project.iterdir()} <= allowed


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
    # No plan entry still targets the Kimi support-tree agents folder.
    assert not [
        e for e in plan if "support/agents" in str(e["target"]).replace("\\", "/")
    ]


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
    assert len(outcomes) == len(_names(public_id))
    assert outcomes["test-runner.md"] == "updated"  # the operator's, backed up
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
    assert len(list(agents.glob("*.md"))) == len(_names(public_id))
    (agents / "my-agent.md").write_text("operator my-agent\n", encoding="utf-8")

    # An edit to one of Apothem's files is overwritten by the next update.
    (agents / "memory-auditor.md").write_text("edited\n", encoding="utf-8")
    adapter.update({}, project=project)
    assert (agents / "memory-auditor.md").read_bytes().startswith(b"---\nname:")

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


def test_windsurf_never_touches_an_operator_agent_with_a_held_back_name(
    tmp_path: Path,
) -> None:
    """A held-back agent is not Apothem's here, so install, update and uninstall leave it."""
    project = _project(tmp_path)
    adapter = _adapter("windsurf")
    agents = _agents_dir(project, "windsurf")
    agents.mkdir(parents=True)
    mine = agents / "research-scout.md"
    mine.write_text("operator research-scout\n", encoding="utf-8")

    adapter.install({}, project=project)
    assert mine.read_text(encoding="utf-8") == "operator research-scout\n"
    adapter.update({}, project=project)
    assert mine.read_text(encoding="utf-8") == "operator research-scout\n"
    assert adapter.verify(project=project) is True
    adapter.uninstall(project=project)
    assert mine.read_text(encoding="utf-8") == "operator research-scout\n"
    assert sorted(p.name for p in agents.iterdir()) == ["research-scout.md"]


# --- Kimi Code: the move out of the support tree ------------------------------


def _revert_agents_to_the_support_tree(project: Path) -> Path:
    """Rebuild the agents layout every earlier release wrote.

    Releases v1.0.1 to v1.4.0 copied the source agents to
    ``.kimi-code/.apothem/support/agents/``; the native folder did not exist.
    """
    legacy = project / _LEGACY_KIMI_AGENTS
    legacy.mkdir(parents=True)
    for source in _SOURCES:
        shutil.copyfile(source, legacy / source.name)
    shutil.rmtree(_agents_dir(project, "kimi-code"))
    return legacy


def test_update_over_the_support_tree_layout_moves_the_agents_to_the_native_folder(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    adapter = _adapter("kimi-code")
    adapter.install({}, project=project)
    legacy = _revert_agents_to_the_support_tree(project)
    marker = legacy / "legacy-only-agent.md"
    marker.write_text("---\nname: legacy-only-agent\n---\n", encoding="utf-8")
    assert not _agents_dir(project, "kimi-code").exists()

    adapter.update({}, project=project)

    # Kimi Code scans both folders only by name, so a leftover copy would shadow
    # nothing, but it would be an orphan: the sweep retires it, after a backup.
    assert not legacy.exists()
    assert not marker.exists()
    assert list(install_driver.BACKUP_ROOT.rglob("legacy-only-agent.md")), (
        "the swept directory must be backed up first"
    )
    assert sorted(p.name for p in _agents_dir(project, "kimi-code").iterdir()) == (
        _names("kimi-code")
    )
    assert adapter.verify(project=project) is True
    # The rest of the support tree is untouched by the sweep.
    support = project / ".kimi-code" / ".apothem" / "support"
    assert sorted(p.name for p in support.iterdir()) == ["hooks", "rules", "templates"]


def test_uninstall_over_the_support_tree_layout_leaves_no_agent_copy(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    adapter = _adapter("kimi-code")
    adapter.install({}, project=project)
    legacy = _revert_agents_to_the_support_tree(project)
    assert legacy.is_dir()

    adapter.uninstall(project=project)

    assert not legacy.exists()
    assert not (project / ".kimi-code" / ".apothem").exists()
    assert not _agents_dir(project, "kimi-code").exists()
    assert list(project.rglob("*-auditor.md")) == []
    assert list(install_driver.BACKUP_ROOT.rglob("convention-auditor.md")), (
        "the swept directory must be backed up first"
    )


def test_a_fresh_kimi_install_never_creates_the_support_tree_agents_folder(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _adapter("kimi-code").install({}, project=project)
    assert not (project / _LEGACY_KIMI_AGENTS).exists()
    assert (project / ".kimi-code" / "agents").is_dir()
