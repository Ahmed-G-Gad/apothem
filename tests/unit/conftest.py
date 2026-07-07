# SPDX-License-Identifier: MIT

"""Shared fixtures and markers for the unit suite.

Two duplication seams are hoisted here so the per-file copies collapse to a
single source:

* ``runner`` — a bare ``CliRunner`` used by every ``test_cli_*`` module.
* ``mock_adapter`` — a ``MagicMock`` shaped like a ``HarnessAdapter``, used by
  the CLI surface and confirmation-gate suites.

The ``benchmark`` marker is registered (``--strict-markers`` is on) so the
wall-clock, real-subprocess benchmark drivers in ``test_benchmarks.py`` can be
routed to a dedicated job with ``-m "not benchmark"`` on loaded runners without
being deselected under a plain ``pytest tests/unit`` run.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "benchmark: wall-clock / real-subprocess budget assertion; opt-out with "
        '-m "not benchmark" on loaded CI runners.',
    )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_adapter(tmp_path: Path) -> MagicMock:
    a = MagicMock()
    a.name = "test-harness"
    a.output_path = tmp_path / "test_config.json"
    a.is_installed.return_value = True
    a.install.return_value = None
    a.uninstall.return_value = None
    a.verify.return_value = True
    return a
