# SPDX-License-Identifier: MIT

"""Pins for the agent-emission registry (``install_driver_agent_emitters``).

Every agent install mode is one :class:`AgentEmitter` row. These tests hold the
rows to what the install driver did before the registry existed, and hold the
four places that act on a row (the dispatcher, the plan, the dry-run preview and
the uninstall enumeration) to the same answer, so a later mode is added as one
row without a second edit that could drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared import (
    install_driver_converters as converters,
)
from apothem.harnesses._shared import (
    install_driver_planvalidation as planvalidation,
)
from apothem.harnesses._shared.install_driver_agent_apply import apply_agent_emitter
from apothem.harnesses._shared.install_driver_agent_emitters import (
    AGENT_EMITTERS,
    AgentEmitter,
)
from apothem.harnesses._shared.install_driver_types import _INSTALL_ENTRY_MODES
from apothem.lib.claude_agent_mcp import claude_agent_text
from apothem.lib.propagation import HarnessRules, InstallEntry

_REGISTERED_MODES = {
    "codex_agents",
    "gemini_agents",
    "opencode_agents",
    "qwen_agents",
    "antigravity_agents",
    "claude_agents",
}


def test_registry_holds_exactly_the_modes_that_were_agent_emissions() -> None:
    assert set(AGENT_EMITTERS) == _REGISTERED_MODES
    for mode, emitter in AGENT_EMITTERS.items():
        assert emitter.mode == mode


def test_every_registered_mode_is_installable_and_labelled() -> None:
    """A row without an entry in the literal tables would reach neither plan nor UI."""
    for mode in AGENT_EMITTERS:
        assert mode in _INSTALL_ENTRY_MODES, f"{mode} missing from _INSTALL_ENTRY_MODES"
        assert install_driver.OPERATION_LABELS[mode] == "Install agents"


def test_rows_keep_the_renderers_and_target_names_they_always_had() -> None:
    expected = {
        "codex_agents": (converters._codex_agent_text, "toml", True),
        "gemini_agents": (converters._gemini_agent_text, None, False),
        "opencode_agents": (converters._opencode_agent_text, None, False),
        "qwen_agents": (converters._qwen_agent_text, None, False),
        "antigravity_agents": (converters._antigravity_agent_text, None, False),
        "claude_agents": (claude_agent_text, None, False),
    }
    for mode, (renderer, extension, stale) in expected.items():
        emitter = AGENT_EMITTERS[mode]
        assert emitter.renderer is renderer, mode
        assert emitter.target_extension == extension, mode
        assert emitter.remove_stale_markdown is stale, mode
        assert emitter.exclude == frozenset(), mode


def test_target_name_follows_the_extension() -> None:
    source = Path("agents/code-reviewer.md")
    assert AGENT_EMITTERS["codex_agents"].target_name(source) == "code-reviewer.toml"
    assert AGENT_EMITTERS["qwen_agents"].target_name(source) == "code-reviewer.md"
    double = AgentEmitter("x_agents", lambda _p: "", target_extension="agent.md")
    assert double.target_name(source) == "code-reviewer.agent.md"


@pytest.fixture
def cohort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A source ``agents/`` cohort with a documentation companion and a held agent."""
    package = tmp_path / "package"
    agents = package / "agents"
    agents.mkdir(parents=True)
    for name in ("alpha", "beta", "gamma"):
        (agents / f"{name}.md").write_text(f"source {name}\n", encoding="utf-8")
    (agents / "README.md").write_text("companion\n", encoding="utf-8")
    (agents / "AGENTS.md").write_text("companion\n", encoding="utf-8")
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", package)
    return tmp_path / "project"


def _register(
    monkeypatch: pytest.MonkeyPatch,
    *,
    target_extension: str | None = None,
    remove_stale_markdown: bool = False,
    exclude: frozenset[str] = frozenset(),
) -> tuple[AgentEmitter, InstallEntry]:
    emitter = AgentEmitter(
        "probe_agents",
        lambda path: f"native {path.stem}\n",
        target_extension=target_extension,
        remove_stale_markdown=remove_stale_markdown,
        exclude=exclude,
    )
    monkeypatch.setitem(AGENT_EMITTERS, emitter.mode, emitter)
    entry = InstallEntry(
        source="agents/", target="${PROJECT_ROOT}/.probe/agents/", mode=emitter.mode
    )
    return emitter, entry


def _names(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir())


def test_a_registered_mode_installs_through_the_dispatcher(
    cohort: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, entry = _register(monkeypatch, target_extension="agent.md")
    cohort.mkdir()
    rules = HarnessRules(install=[entry], exclude=[], stale_sweep=[])

    results = install_driver._dispatch_install_entry(
        entry,
        install_driver.make_ignore([], {}),
        rules,
        harness_root=None,
        project_root=cohort,
        harness_name="probe",
    )

    out = cohort / ".probe" / "agents"
    assert _names(out) == ["alpha.agent.md", "beta.agent.md", "gamma.agent.md"]
    assert (out / "alpha.agent.md").read_text(encoding="utf-8") == "native alpha\n"
    assert {r.operation for r in results} == {"probe_agents"}
    assert {r.outcome for r in results} == {"created"}


def test_exclude_holds_an_agent_back_everywhere_the_mode_is_read(
    cohort: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Install, plan, dry-run and uninstall enumeration agree on the held agent."""
    emitter, entry = _register(
        monkeypatch, target_extension="agent.md", exclude=frozenset({"beta"})
    )
    cohort.mkdir()
    out = cohort / ".probe" / "agents"

    apply_agent_emitter(emitter, entry, project_root=cohort, harness_name="probe")

    assert _names(out) == ["alpha.agent.md", "gamma.agent.md"]
    listed = install_driver.generated_targets_for_entry(
        entry, harness_root=None, project_root=cohort, exclude=[]
    )
    assert sorted(p.name for p in listed) == ["alpha.agent.md", "gamma.agent.md"]

    rules = HarnessRules(install=[entry], exclude=[], stale_sweep=[])
    preview = planvalidation._dry_run_results(
        rules,
        root=cohort,
        harness_root=None,
        project_root=cohort,
        harness_name="probe",
        profile_body=None,
    )
    entry_outcomes = [r.outcome for r in preview if r.operation == "probe_agents"]
    assert entry_outcomes == ["unchanged"], "the preview counted a held agent"


def test_stale_markdown_is_retired_only_where_the_row_asks_for_it(
    cohort: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    emitter, entry = _register(
        monkeypatch, target_extension="toml", remove_stale_markdown=True
    )
    out = cohort / ".probe" / "agents"
    out.mkdir(parents=True)
    (out / "alpha.md").write_text("earlier layout\n", encoding="utf-8")

    apply_agent_emitter(emitter, entry, project_root=cohort, harness_name="probe")
    assert not (out / "alpha.md").exists()
    assert (out / "alpha.toml").is_file()

    # Nothing differs now, so the preview is quiet ...
    rules = HarnessRules(install=[entry], exclude=[], stale_sweep=[])

    def outcomes() -> list[str]:
        return [
            r.outcome
            for r in planvalidation._dry_run_results(
                rules,
                root=cohort,
                harness_root=None,
                project_root=cohort,
                harness_name="probe",
                profile_body=None,
            )
            if r.operation == "probe_agents"
        ]

    assert outcomes() == ["unchanged"]
    # ... until an earlier ``.md`` reappears: the install would remove it.
    (out / "alpha.md").write_text("earlier layout\n", encoding="utf-8")
    assert outcomes() == ["updated"]
