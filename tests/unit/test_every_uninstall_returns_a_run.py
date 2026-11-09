# SPDX-License-Identifier: MIT

"""Every registered adapter's uninstall returns a ``MaterializationRun``.

``apothem uninstall`` reports the run's warnings and fails a harness on its
errors; an adapter that returned nothing would hide both.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.cli._helpers import _invoke_with_project
from apothem.harnesses._shared.install_driver import MaterializationRun
from apothem.lib.harness_registry import (
    HarnessRegistryEntry,
    iter_harness_entries,
    load_adapter_class,
)

ENTRIES = list(iter_harness_entries())


@pytest.mark.parametrize("entry", ENTRIES, ids=[e.public_id for e in ENTRIES])
def test_uninstall_returns_a_run(entry: HarnessRegistryEntry, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    adapter = load_adapter_class(entry)()

    run = _invoke_with_project(adapter.uninstall, project=project)

    assert isinstance(run, MaterializationRun)
    assert not run.errors
