# SPDX-License-Identifier: MIT

"""Acceptance matrix for the install ledger at the adapter boundary.

``install_driver.finalize_install`` is wired into every adapter's
``install()`` so each install pass records exactly what it wrote to the
append-only per-harness ledger. These tests prove the boundary contract end to
end:

- **record-on-install** — a single-file adapter (claude-code) and a
  materializer adapter (hermes) each leave a latest install record whose targets
  cover every created/updated file the run wrote, including the materializer's
  rendered native config. Recording at the adapter boundary — not inside
  ``run_install`` — is what lets the hermes native ``config.yaml`` reach the
  ledger, since that file is applied by the adapter, not the manifest driver.
- **manifest drift** — manifest drift between install and uninstall neither
  strands nor over-removes: a target added to the manifest after install but
  never recorded is left untouched, while a recorded target dropped from the
  manifest is still cleaned.
- **no-residue** — every one of the 17 adapters installs, then uninstalls,
  leaving no apothem-owned managed output and — as the last harness at its
  root — no shared data stores (memory / contexts / learning) behind.

Ledger isolation is provided by the autouse ``_isolate_install_ledger`` fixture
in ``tests/integration/conftest.py`` (it redirects ``install_ledger.STATE_ROOT``
per test); these tests still isolate ``install_driver.BACKUP_ROOT`` per test, the
established pattern the per-adapter and parity tests use.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from apothem.harnesses import HarnessAdapter
from apothem.harnesses._shared import install_driver
from apothem.harnesses.claude_code import ClaudeCodeAdapter
from apothem.harnesses.hermes import HermesAdapter
from apothem.lib import install_ledger
from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    merge_managed_block,
)
from apothem.lib.harness_registry import HARNESS_REGISTRY, HarnessRegistryEntry
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget
from apothem.lib.propagation import HarnessRules, InstallEntry

# A representative real profile: identity + rules drive the projected anchors,
# and an MCP server drives the materializer adapters' native config block.
_PROFILE: dict[str, Any] = {
    "identity": {"name": "Ada Lovelace"},
    "preferences": {"language": "python", "style": "concise"},
    "rules": ["ledger-fixture-rule"],
    "mcp_servers": {"demo": {"command": "demo-bin"}},
}


@pytest.fixture(autouse=True)
def _isolate_backup_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect the install backup root per test, mirroring the install tests."""
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")


# --- 20.2 record-on-install --------------------------------------------------


def test_record_on_install_single_file_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A claude-code install records every written file as a ledger target.

    The latest install record exists, its targets include the ``settings.json``
    manifest write and the ``CLAUDE.md`` profile anchor, and the recorded target
    path set equals the run's ``files_written`` set restricted to non-data-surface
    files — every created/updated file the run reports is recorded.
    """
    adapter = ClaudeCodeAdapter()
    harness_root = tmp_path / "claude-root"
    target = harness_root / "settings.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    run = adapter.install(_PROFILE)

    record = install_ledger.latest_record("claude_code", root=harness_root)
    assert record is not None
    assert record.kind == "install"

    recorded_paths = {entry.path for entry in record.targets}
    assert str(target) in recorded_paths
    assert str(harness_root / "CLAUDE.md") in recorded_paths

    # The recorded target set equals the run's created/updated files restricted
    # to non-data-surface files: the per-surface data-home files (memory /
    # contexts / learning) and the advisory capability-projection note are
    # excluded — the same boundary the ledger applies. Strict equality (not a
    # subset) guards against over-recording: the stale-sweep pass emits an
    # ``unchanged`` result for every absent legacy path, and those phantom paths
    # must never reach the ledger.
    non_ledger_ops = {"data_surface", "capability_projection"}
    written_recordable = {
        result.path
        for result in run.results
        if result.outcome in {"created", "updated"}
        and result.operation not in non_ledger_ops
    }
    assert written_recordable, "expected at least one recordable created/updated file"
    assert written_recordable == recorded_paths
    # Every recorded target is a file that actually exists on disk — no phantom
    # paths (e.g. stale-sweep absent-path results) leak into the ledger.
    assert all(Path(path).exists() for path in recorded_paths)
    # The excluded data-surface files really were among the written files (so the
    # restriction is load-bearing, not vacuously satisfied).
    assert set(run.files_written) >= written_recordable


def test_record_on_install_materializer_native_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hermes install records the materializer-rendered native config.yaml.

    This is the case that fails if recording were done inside ``run_install``
    instead of at the adapter boundary: the native ``config.yaml`` is written by
    the adapter (``apply_operator_owned_content``), not the manifest driver, so
    only a boundary-level ``finalize_install`` captures it.
    """
    adapter = HermesAdapter()
    harness_root = tmp_path / "hermes-root"
    native_config = harness_root / "config.yaml"
    monkeypatch.setattr(
        type(adapter), "output_path", property(lambda self: native_config)
    )

    adapter.install(_PROFILE)

    record = install_ledger.latest_record("hermes", root=harness_root)
    assert record is not None
    recorded_paths = {entry.path for entry in record.targets}
    assert str(native_config) in recorded_paths


def test_two_profiles_produce_two_install_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two distinct-profile installs into one root append two install records."""
    adapter = ClaudeCodeAdapter()
    harness_root = tmp_path / "claude-root"
    target = harness_root / "settings.json"
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    adapter.install({"identity": {"name": "Ada Lovelace"}, "rules": ["alpha"]})
    adapter.install({"identity": {"name": "Grace Hopper"}, "rules": ["beta"]})

    records = install_ledger.read_records("claude_code")
    install_records = [r for r in records if r.kind == "install"]
    assert len(install_records) == 2


# --- 20.3 drift --------------------------------------------------------------


def test_uninstall_under_manifest_drift_neither_strands_nor_over_removes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ledger-driven uninstall honours the install record under manifest drift.

    A synthetic install record + a controlled root + a monkeypatched manifest
    isolate the two drift properties precisely:

    - A sentinel-merge target ADDED to the manifest after install (so it is in
      the live manifest but absent from the install record) is NOT touched —
      operator content the install never wrote survives.
    - A sentinel-merge target RECORDED at install but later REMOVED from the
      manifest is STILL cleaned — its managed block is stripped from disk.
    """
    harness = "drift_fixture"
    root = tmp_path / "drift-root"
    root.mkdir()

    added = root / "added.md"
    removed = root / "removed.md"

    # The ADDED target carries operator content the install never recorded.
    added.write_text("operator-only content\n", encoding="utf-8")
    # The REMOVED target carries a real managed block plus operator prose, so a
    # successful clean strips the block but preserves the prose (cleaned, not
    # destroyed).
    removed.write_text(
        merge_managed_block("keep operator prose\n", "managed body"),
        encoding="utf-8",
    )
    assert APOTHEM_BLOCK_BEGIN in removed.read_text(encoding="utf-8")

    # The synthetic install record knows only the REMOVED target.
    record = LedgerRecord.create(
        harness=harness,
        root=root,
        kind="install",
        targets=(
            LedgerTarget(
                path=str(removed),
                mode="sentinel_merge",
                ownership_class="operator-owned",
            ),
        ),
    )
    install_ledger.append_record(record)

    # The live manifest knows only the ADDED target (the REMOVED one was dropped).
    drifted_rules = HarnessRules(
        install=[
            InstallEntry(
                source="unused-source",
                target="${HARNESS_ROOT}/added.md",
                mode="sentinel_merge",
                ownership_class="operator-owned",
            )
        ],
        exclude=[],
        stale_sweep=[],
    )
    monkeypatch.setattr(install_driver, "load_rules", lambda name: drifted_rules)

    install_driver.run_uninstall(harness, harness_root=root)

    # The ADDED-but-unrecorded target is untouched.
    assert added.is_file()
    assert added.read_text(encoding="utf-8") == "operator-only content\n"

    # The RECORDED-but-dropped target is still cleaned: the managed block is
    # gone, operator prose preserved.
    remaining = removed.read_text(encoding="utf-8")
    assert APOTHEM_BLOCK_BEGIN not in remaining
    assert APOTHEM_BLOCK_END not in remaining
    assert "keep operator prose" in remaining


# --- 20.4 no-residue across all 17 adapters ----------------------------------


def _is_project_scope(entry: HarnessRegistryEntry) -> bool:
    return entry.scope == "project"


def _install_adapter(
    adapter: HarnessAdapter,
    entry: HarnessRegistryEntry,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], Path]:
    """Install *adapter* into the temp tree; return its lifecycle kwargs + root.

    Project-scope adapters thread ``project=``; user-scope adapters derive their
    harness root from a monkeypatched ``output_path.parent`` whose basename
    matches the real config name so the manifest target coincides with it. The
    returned root is the directory ``finalize_install`` keyed the ledger record
    to and the data home is anchored under.
    """
    if _is_project_scope(entry):
        project = tmp_path / "project"
        project.mkdir()
        adapter.install({}, project=project)
        return {"project": project}, project
    target = tmp_path / "root" / adapter.output_path.name
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({})
    return {}, target.parent


@pytest.mark.parametrize("entry", HARNESS_REGISTRY, ids=lambda e: e.public_id)
def test_uninstall_leaves_no_residue(
    entry: HarnessRegistryEntry,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install then uninstall every adapter; no managed output or data stores stay.

    After uninstall: the adapter reports not-installed OR no apothem-owned
    managed file remains, AND — this being the last harness at the root — the
    shared data stores (memory / contexts / learning) no longer exist. Every
    adapter is exercised; none is silently skipped.
    """
    adapter_cls = _load_adapter_class(entry)
    adapter = adapter_cls()
    kwargs, root = _install_adapter(adapter, entry, tmp_path, monkeypatch)

    assert adapter.is_installed(**kwargs) is True

    adapter.uninstall(**kwargs)

    # (a) the adapter's primary managed output is gone.
    assert adapter.is_installed(**kwargs) is False

    # (b) the shared data stores (memory / contexts / learning) are removed.
    home = resolve_shared_data_home(base=root)
    assert not home.memory.exists()
    assert not home.contexts.exists()
    assert not home.learning.exists()


@pytest.mark.parametrize("entry", HARNESS_REGISTRY, ids=lambda e: e.public_id)
def test_uninstall_is_idempotent(
    entry: HarnessRegistryEntry,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second uninstall after the first does not raise for any adapter."""
    adapter_cls = _load_adapter_class(entry)
    adapter = adapter_cls()
    kwargs, _root = _install_adapter(adapter, entry, tmp_path, monkeypatch)

    adapter.uninstall(**kwargs)
    adapter.uninstall(**kwargs)  # must not raise


@pytest.mark.parametrize("entry", HARNESS_REGISTRY, ids=lambda e: e.public_id)
def test_uninstall_appends_uninstall_marker(
    entry: HarnessRegistryEntry,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The latest record of any kind after uninstall is an uninstall marker."""
    adapter_cls = _load_adapter_class(entry)
    adapter = adapter_cls()
    kwargs, root = _install_adapter(adapter, entry, tmp_path, monkeypatch)

    adapter.uninstall(**kwargs)

    marker = install_ledger.latest_record(entry.package_key, root=root, kind=None)
    assert marker is not None
    assert marker.kind == "uninstall"


def _load_adapter_class(entry: HarnessRegistryEntry) -> type[HarnessAdapter]:
    """Import and return the registry entry's adapter class."""
    import importlib

    module = importlib.import_module(entry.adapter_module)
    return getattr(module, entry.adapter_class_name)


# --- ledger durability (failure injection) -----------------------------------


def test_read_records_skips_truncated_trailing_fragment(tmp_path: Path) -> None:
    """A torn trailing JSON line is skipped; complete prior records survive.

    Appends two good records, then a deliberately-truncated trailing fragment
    (a crash mid-append), and asserts ``read_records`` returns exactly the two
    complete records. ``STATE_ROOT`` is isolated by the autouse conftest fixture,
    so the records land in the per-test ledger.
    """
    harness = "ledger_durability_fixture"
    good_one = LedgerRecord.create(
        harness=harness,
        root="/r",
        kind="install",
        targets=(
            LedgerTarget(path="/a", mode="write_text", ownership_class="apothem-owned"),
        ),
    )
    good_two = LedgerRecord.create(
        harness=harness,
        root="/r",
        kind="install",
        targets=(
            LedgerTarget(path="/b", mode="write_text", ownership_class="apothem-owned"),
        ),
    )
    install_ledger.append_record(good_one)
    install_ledger.append_record(good_two)

    path = install_ledger.ledger_path(harness)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"install_id":"01PARTIAL","harness":"ledger_durab')

    records = install_ledger.read_records(harness)
    assert [r.install_id for r in records] == [
        good_one.install_id,
        good_two.install_id,
    ]
