# SPDX-License-Identifier: MIT

"""Multi-harness parity integration test.

Verifies cross-adapter protocol conformance and structural consistency:
every registered apothem harness adapter exposes the same interface,
returns type-correct values, and has a unique name.

Install-smoke coverage confirms every adapter accepts an empty profile.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from apothem.harnesses import HarnessAdapter
from apothem.harnesses._shared import install_driver
from apothem.lib.harness_registry import (
    HARNESS_REGISTRY,
    REQUIRED_CAPABILITIES,
    SUPPORTED_HARNESS_COUNT,
    HarnessRegistryEntry,
    get_harness_entry,
    load_adapter_class,
)

# The adapter roster, the backend-provider set, the project-scope predicate, and
# the sandbox-install helper are hoisted to ``conftest.py`` so every integration
# module shares one registry-derived source with no cross-test-module private
# import. Re-exported here for the historical import surface these tests use.
from .conftest import (  # noqa: F401 — re-exported for sibling test modules
    ALL_ADAPTERS,
    BACKEND_PROVIDER_HARNESSES,
    install_into_sandbox,
)
from .conftest import (
    is_project_scope as _is_project_scope,
)


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_protocol_conformance(adapter: object) -> None:
    assert isinstance(adapter, HarnessAdapter)


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_name_is_kebab_case_string(adapter: HarnessAdapter) -> None:
    name = adapter.name
    assert isinstance(name, str)
    assert name == name.lower()
    assert " " not in name


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_output_path_is_absolute_path(adapter: HarnessAdapter) -> None:
    if getattr(adapter, "requires_project", False):
        # Project-scope adapters expose a relative display sentinel via
        # output_path; the concrete target is absolute once resolved under
        # an operator-supplied project root.
        resolved = adapter.resolve_output_path(Path.cwd())
        assert isinstance(resolved, Path)
        assert resolved.is_absolute()
    else:
        assert isinstance(adapter.output_path, Path)
        assert adapter.output_path.is_absolute()


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_is_installed_returns_bool(adapter: HarnessAdapter) -> None:
    assert isinstance(adapter.is_installed(), bool)


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_install_accepts_empty_profile(
    adapter: HarnessAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if getattr(adapter, "requires_project", False):
        # Project-scope adapter: target resolved under --project.
        adapter.install({}, project=tmp_path)  # must not raise
    else:
        target = tmp_path / "config"
        monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
        adapter.install({})  # must not raise


def test_all_adapter_names_are_unique() -> None:
    names = [a.name for a in ALL_ADAPTERS]
    assert len(names) == len(set(names)), f"duplicate adapter names: {names}"


def test_adapter_count() -> None:
    # The roster is registry-derived, so its size is asserted against the
    # registry's own count constant rather than a hand-copied literal: adding an
    # adapter to the registry lifts both sides together (the whole cohort — 17
    # adapters today — stays covered without editing this test).
    assert len(ALL_ADAPTERS) == SUPPORTED_HARNESS_COUNT
    assert SUPPORTED_HARNESS_COUNT == 17


def test_all_output_paths_are_distinct() -> None:
    # Resolve every adapter to a comparable absolute target. User-scope
    # adapters expose an absolute output_path directly; project-scope
    # adapters (requires_project=True) expose a relative display sentinel
    # and resolve to an absolute path under a project root, so we resolve
    # them under a common synthetic project to compare like-for-like.
    common_project = Path("/synthetic-project-root")
    resolved_paths = [
        a.resolve_output_path(common_project)
        if getattr(a, "requires_project", False)
        else a.output_path
        for a in ALL_ADAPTERS
    ]
    # Since gemini-cli became a project-scope adapter, it no longer shares
    # antigravity's user-global ~/.gemini/GEMINI.md surface (it now resolves
    # under the project root). Every adapter's resolved target is distinct.
    assert len(resolved_paths) == len(set(resolved_paths)), (
        f"duplicate output paths across adapters: {resolved_paths}"
    )


def _install_into_tmp(
    adapter: HarnessAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Install *adapter* into the temp tree and return per-scope call kwargs.

    A thin wrapper over the shared ``install_into_sandbox`` conftest helper that
    keeps the lifecycle suite's contract: backups are redirected under the temp
    tree so no real HOME state is touched, and only the per-scope call kwargs
    are returned. Re-exported for the sibling ``test_update_over_edit`` module.
    """
    kwargs, _root = install_into_sandbox(
        adapter, tmp_path, monkeypatch, redirect_backup_root=True
    )
    return kwargs


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_update_runs_and_is_idempotent_after_install(
    adapter: HarnessAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: a clean install into the temp tree.
    kwargs = _install_into_tmp(adapter, tmp_path, monkeypatch)

    # Act: update twice — the second pass must reproduce the first end state.
    adapter.update({}, **kwargs)
    first_state = adapter.is_installed(**kwargs)
    adapter.update({}, **kwargs)
    second_state = adapter.is_installed(**kwargs)

    # Assert: update never raises and the end state is stable across passes.
    assert first_state is True
    assert second_state == first_state


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_verify_returns_truthy_after_install(
    adapter: HarnessAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: install into the temp tree.
    kwargs = _install_into_tmp(adapter, tmp_path, monkeypatch)

    # Act / Assert: verify confirms a valid materialized configuration.
    assert adapter.verify(**kwargs) is True


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_verify_returns_false_when_a_manifest_target_is_missing(
    adapter: HarnessAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: a clean, verifying install.
    kwargs = _install_into_tmp(adapter, tmp_path, monkeypatch)
    assert adapter.verify(**kwargs) is True

    # Resolve the install root the manifest walk uses.
    if _is_project_scope(adapter):
        harness_root, project_root = None, kwargs["project"]
    else:
        harness_root, project_root = tmp_path, None
    rules = install_driver.load_rules(adapter.name.replace("-", "_"))

    # Delete one materialized manifest target (prefer a non-primary cohort dir).
    resolved = [
        install_driver.resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        )
        for entry in rules.install
    ]
    dirs = [p for p in resolved if p.is_dir()]
    files = [p for p in resolved if p.is_file()]
    if dirs:
        shutil.rmtree(dirs[0])
    else:
        files[0].unlink()

    # Act / Assert: the shared verifier now reports the half-installed tree.
    assert adapter.verify(**kwargs) is False


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_uninstall_removes_managed_output_after_install(
    adapter: HarnessAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: install into the temp tree, confirm it landed.
    kwargs = _install_into_tmp(adapter, tmp_path, monkeypatch)
    assert adapter.is_installed(**kwargs) is True

    # Act: uninstall the managed configuration.
    adapter.uninstall(**kwargs)

    # Assert: the primary managed output is gone after uninstall.
    assert adapter.is_installed(**kwargs) is False


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_uninstall_is_idempotent(
    adapter: HarnessAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: install into the temp tree.
    kwargs = _install_into_tmp(adapter, tmp_path, monkeypatch)

    # Act: uninstall, then uninstall a second time. The second pass must be a
    # no-op that does not raise even though the managed output is already gone.
    adapter.uninstall(**kwargs)
    assert adapter.is_installed(**kwargs) is False
    adapter.uninstall(**kwargs)  # must not raise

    # Assert: the end state is stable — still not installed after both passes.
    assert adapter.is_installed(**kwargs) is False


def _file_set(root: Path) -> set[str]:
    """Return the set of regular-file paths under *root*, relative to it."""
    if not root.exists():
        return set()
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_uninstall_leaves_no_apothem_file_residue(
    adapter: HarnessAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    populated_profile: dict,
) -> None:
    """Uninstall leaves no apothem-owned file under the root, and removes the
    shared data stores when this is the last harness (RB-4).

    The driver's documented uninstall contract surgically removes the files it
    wrote and — when it is the last harness referencing the shared
    ``<root>/.apothem/`` home — rmtree-removes the data stores (``memory/``,
    ``contexts/``, ``learning/``), but it reverses directory surfaces
    child-by-child rather than pruning the now-empty operator-shaped container
    directories (``.cursor/rules/``, ``apothem/hooks/``, the bare ``.apothem``
    parent left after the data stores are removed, etc.). Those empty skeletons
    carry no apothem content, so the meaningful no-residue invariant is at the
    FILE level: the post-uninstall file set under the root equals the pre-install
    file set, and the shared data stores are gone. A regression that stranded a
    stale apothem file or left the data-home records behind would fail this
    assertion.
    """
    from apothem.lib import install_ledger
    from apothem.lib.data_home import resolve_shared_data_home

    # The install root is a dedicated subtree so the snapshot never picks up the
    # sibling backup root or the per-test ledger state (both rooted elsewhere
    # under tmp_path), which would otherwise read as phantom residue. The ledger
    # state is redirected so the last-harness uninstall guard reads only this
    # test's records, not the operator's real install ledger.
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    monkeypatch.setattr(install_ledger, "STATE_ROOT", tmp_path / "ledger-state")

    # Snapshot files under the root that the install will write into.
    if _is_project_scope(adapter):
        root = tmp_path / "project"
        root.mkdir()
        pre_files = _file_set(root)
        adapter.install(populated_profile, project=root)
        kwargs: dict[str, Any] = {"project": root}
    else:
        root = tmp_path / "root"
        root.mkdir()
        target = root / adapter.output_path.name
        monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
        pre_files = _file_set(root)
        adapter.install(populated_profile)
        kwargs = {}

    home = resolve_shared_data_home(base=root)
    assert home.memory.is_dir(), f"{adapter.name}: data home absent after install"
    assert adapter.is_installed(**kwargs) is True

    # Act: uninstall the managed configuration.
    adapter.uninstall(**kwargs)

    # Assert: no apothem-owned file residue, and — this being the last harness
    # at the root — the shared data stores are gone.
    post_files = _file_set(root)
    residue = sorted(post_files - pre_files)
    assert residue == [], (
        f"{adapter.name}: apothem file residue after uninstall: {residue}"
    )
    assert not home.memory.exists(), (
        f"{adapter.name}: shared memory store survived uninstall: {home.memory}"
    )
    assert not home.contexts.exists(), (
        f"{adapter.name}: shared contexts store survived uninstall: {home.contexts}"
    )
    assert not home.learning.exists(), (
        f"{adapter.name}: shared learning store survived uninstall: {home.learning}"
    )


@pytest.mark.parametrize("adapter", ALL_ADAPTERS, ids=lambda a: a.name)
def test_capabilities_yml_declares_every_required_key(
    adapter: HarnessAdapter,
) -> None:
    # Arrange: locate the adapter's capability dossier from the registry.
    entry = get_harness_entry(adapter.name)
    caps_path = (
        Path(install_driver.APOTHEM_SRC)
        / "harnesses"
        / entry.package_key
        / "capabilities.yml"
    )
    caps = yaml.safe_load(caps_path.read_text(encoding="utf-8"))

    # Assert: the supplemental dossier carries every cross-harness key.
    required_keys = {
        "mcp_servers",
        "sub_agent_dispatch",
        "custom_command_support",
        "recommended_postfix_rendering",
        "long_context_compaction",
        "context_ignore_surface",
        "layered_context_surface",
        "lsp_symbol_navigation",
        "hook_learning_capture",
        "standard_convention_pin",
        "tool_surface_restrictions",
        "system_prompt_template_path",
        "agent_memory_surface",
    }
    assert required_keys.issubset(caps.keys()), (
        f"{adapter.name} capabilities.yml missing "
        f"{sorted(required_keys.difference(caps.keys()))}"
    )


@pytest.mark.parametrize("entry", HARNESS_REGISTRY, ids=lambda e: e.public_id)
def test_capabilities_yml_agrees_with_registry_matrix(
    entry: HarnessRegistryEntry,
) -> None:
    # Arrange: read the adapter's capability dossier.
    caps_path = (
        Path(install_driver.APOTHEM_SRC)
        / "harnesses"
        / entry.package_key
        / "capabilities.yml"
    )
    caps = yaml.safe_load(caps_path.read_text(encoding="utf-8"))

    # The registry matrix covers exactly the required-capability axes.
    assert set(entry.capability_status.keys()) == set(REQUIRED_CAPABILITIES)

    # Cross-check 1 — sub-agent dispatch. A truthy capabilities flag must
    # correspond to a present (non-unsupported) registry capability, and a
    # false flag to an absent one.
    dispatch_present = entry.capability_status["sub_agent_dispatch"] not in {
        "unsupported",
        "not-applicable",
        "discovery-pending",
    }
    assert bool(caps["sub_agent_dispatch"]) == dispatch_present, (
        f"{entry.public_id}: sub_agent_dispatch flag disagrees with registry"
    )

    # Cross-check 2 — MCP servers (surface existence). The capabilities list
    # names the harness's native MCP *surface* (where MCP lives), so it is
    # non-empty whenever a file MCP surface exists — whether apothem authors it
    # ('native') or only names the operator-owned surface ('discovery-pending').
    # It is empty only when there is no file MCP surface (service/CLI →
    # unsupported / not-applicable).
    mcp_surface = entry.capability_status["mcp_servers"] in {
        "native",
        "discovery-pending",
    }
    assert bool(caps["mcp_servers"]) == mcp_surface, (
        f"{entry.public_id}: mcp_servers surface disagrees with registry"
    )

    # Cross-check 3 — MCP authorship (authored vs operator-owned-recognized).
    # A registry 'native' mcp cell means apothem's materializer AUTHORS the
    # native MCP block; a mere recognized operator-owned surface
    # ('discovery-pending') does NOT satisfy 'native'. The capabilities dossier
    # distinguishes the two with the explicit ``mcp_servers_authored`` flag, so
    # the cross-check requires an adapter-authored surface before permitting a
    # 'native' cell — closing the recognized-vs-authored loophole where a
    # non-empty operator-owned surface list previously looked like authorship.
    mcp_authored = entry.capability_status["mcp_servers"] == "native"
    assert "mcp_servers_authored" in caps, (
        f"{entry.public_id}: capabilities.yml lacks the mcp_servers_authored flag"
    )
    assert bool(caps["mcp_servers_authored"]) == mcp_authored, (
        f"{entry.public_id}: mcp_servers_authored flag disagrees with registry "
        f"'native' status (authored={bool(caps['mcp_servers_authored'])}, "
        f"registry-native={mcp_authored})"
    )


# --- CT-2: profile-fidelity verify (faithful vs drifted vs missing) ----------

_FIDELITY_PROFILE: dict = {
    "identity": {"name": "Ada Lovelace"},
    "preferences": {"language": "python", "style": "concise"},
    "rules": ["fidelity-rule-unique"],
}


@pytest.mark.parametrize(
    "package_key",
    [
        "claude_code",  # bolt-on CLAUDE.md anchor
        "codex",  # sentinel_merge AGENTS.md anchor
        "opencode",  # config adapter, profile-doc anchor
        "qwen_code",  # config adapter + QWEN.md sentinel anchor
    ],
)
def test_verify_reports_faithful_then_drift(
    package_key: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """check_fidelity reports faithful right after install and drifted after a
    profile-derived on-disk edit — proving verify checks fidelity, not mere
    existence (CT-2). All four adapters here are user-scope. The adapter class is
    resolved from the registry by package key rather than imported directly, so
    this test carries no hand-maintained adapter-class import."""
    adapter = load_adapter_class(get_harness_entry(package_key))()
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    target = tmp_path / "root" / adapter.output_path.name
    monkeypatch.setattr(
        type(adapter), "output_path", property(lambda self, t=target: t)
    )
    adapter.install(_FIDELITY_PROFILE)
    harness_root = target.parent

    results = install_driver.check_fidelity(
        package_key, harness_root=harness_root, profile=_FIDELITY_PROFILE
    )
    assert results, f"{package_key}: no profile anchors found"
    assert install_driver.fidelity_is_faithful(results), (
        f"{package_key}: not faithful immediately after install: {results}"
    )

    # Mutate a profile-derived value on disk in a faithful anchor.
    drifted = Path(results[0].target)
    text = drifted.read_text(encoding="utf-8")
    assert "Ada Lovelace" in text
    drifted.write_text(
        text.replace("Ada Lovelace", "Mutated Operator"), encoding="utf-8"
    )

    after = install_driver.check_fidelity(
        package_key, harness_root=harness_root, profile=_FIDELITY_PROFILE
    )
    assert not install_driver.fidelity_is_faithful(after), (
        f"{package_key}: drift not detected after on-disk edit: {after}"
    )
    assert any(r.status == "drifted" for r in after), (
        f"{package_key}: expected a drifted anchor, got {after}"
    )
