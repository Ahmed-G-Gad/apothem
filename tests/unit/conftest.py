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

import ctypes
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from apothem.lib import python_resolver


class FakeGetShortPathNameW:
    """Stand-in for kernel32's ``GetShortPathNameW``, honouring its two-call contract.

    ``names`` maps a long path to its short form. A path missing from the map has
    no short name, so the call returns the long path unchanged, as Windows does
    when short-name generation is disabled on the volume. A ``None`` value fails
    the call, returning 0. ``calls`` records the buffer size of every invocation,
    so ``0`` marks the length probe that passes no buffer.
    """

    def __init__(self, names: dict[str, str | None]) -> None:
        self.names = names
        self.calls: list[int] = []
        self.argtypes: list[object] = []
        self.restype: object = None

    def __call__(
        self, long_path: str, buffer: ctypes.Array[ctypes.c_wchar] | None, size: int
    ) -> int:
        self.calls.append(size)
        short = self.names.get(long_path, long_path)
        if short is None:
            return 0
        needed = len(short) + 1
        if size < needed:
            return needed
        buffer.value = short
        return len(short)


@pytest.fixture
def windows_short_names(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[dict[str, str | None]], FakeGetShortPathNameW]:
    """Pretend to run on Windows, with ``GetShortPathNameW`` mocked through ctypes.

    Call the returned factory with a long-to-short path map. It reports Windows
    from the resolver and replaces ``ctypes.WinDLL`` (absent off Windows, hence
    ``raising=False``) with a fake ``kernel32``, then returns the fake so a test
    can inspect the calls it received.
    """

    def install(names: dict[str, str | None]) -> FakeGetShortPathNameW:
        fake = FakeGetShortPathNameW(names)
        kernel32 = SimpleNamespace(GetShortPathNameW=fake)
        monkeypatch.setattr(python_resolver, "_is_windows", lambda: True)
        monkeypatch.setattr(
            python_resolver.ctypes,
            "WinDLL",
            lambda _name, **_kwargs: kernel32,
            raising=False,
        )
        return fake

    return install


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
