# SPDX-License-Identifier: MIT

"""Tests for the harness-adapter discovery conformance utility.

Discovery is a registry-vs-filesystem PARITY check, not the runtime resolver
(the static ``HARNESS_REGISTRY`` is authoritative at runtime; see the
"Harness Adapter Pattern" canon in CLAUDE.md / AGENTS.md). The parity test below
asserts the discovered adapter set equals the static registry, and the
coverage-regression test proves a convention-correct but unregistered adapter is
caught rather than silently resolved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.lib.harness_registry import (
    SUPPORTED_HARNESS_COUNT,
    SUPPORTED_HARNESS_IDS,
    AdapterDiscoveryError,
    discover_adapters,
    discovered_adapter_map,
)

_ADAPTER_PROTOCOL_MEMBERS = (
    "name",
    "output_path",
    "install",
    "update",
    "uninstall",
    "is_installed",
    "verify",
)


def test_discover_finds_all_supported_adapters() -> None:
    """Discovery over the real package finds exactly the supported cohort."""
    discovered = discovered_adapter_map()

    assert len(discovered) == SUPPORTED_HARNESS_COUNT
    assert set(discovered) == set(SUPPORTED_HARNESS_IDS)


def test_discover_ordering_is_deterministic() -> None:
    """Two discovery passes yield identically-ordered maps."""
    first = discovered_adapter_map()
    second = discovered_adapter_map()

    assert list(first) == list(second)
    assert list(first) == sorted(first)


def test_discovered_values_implement_adapter_protocol() -> None:
    """Every resolved class exposes the HarnessAdapter protocol surface."""
    discovered = discovered_adapter_map()

    for name, adapter_class in discovered.items():
        assert isinstance(adapter_class, type), name
        # HarnessAdapter is a runtime_checkable Protocol with non-method
        # members (``name``, ``output_path``), so ``issubclass`` against it is
        # unsupported. Assert the protocol surface by member presence instead.
        for member in _ADAPTER_PROTOCOL_MEMBERS:
            assert hasattr(adapter_class, member), f"{name}: missing {member}"


def test_github_copilot_resolves_with_internal_capital_h() -> None:
    """The casing-gotcha regression: github_copilot -> GitHubCopilotAdapter."""
    discovered = discovered_adapter_map()

    adapter_class = discovered["github-copilot"]
    assert adapter_class.__name__ == "GitHubCopilotAdapter"


def _write_package(directory: Path, body: str) -> None:
    """Create a minimal harness sub-package directory with the given module body."""
    directory.mkdir(parents=True)
    (directory / "__init__.py").write_text(body, encoding="utf-8")


def test_missing_adapter_class_raises_naming_dir(tmp_path: Path) -> None:
    """A sub-package with no *Adapter class raises AdapterDiscoveryError."""
    harnesses = tmp_path / "harnesses"
    _write_package(
        harnesses / "brokenadapter",
        "# SPDX-License-Identifier: MIT\n\nVALUE = 1\n",
    )

    with pytest.raises(AdapterDiscoveryError) as excinfo:
        discover_adapters(tmp_path)

    assert "brokenadapter" in str(excinfo.value)


def test_multiple_adapter_classes_raise_naming_dir(tmp_path: Path) -> None:
    """A sub-package with two *Adapter classes raises AdapterDiscoveryError."""
    harnesses = tmp_path / "harnesses"
    _write_package(
        harnesses / "doubleadapter",
        (
            "# SPDX-License-Identifier: MIT\n\n"
            "class FirstAdapter:\n    pass\n\n\n"
            "class SecondAdapter:\n    pass\n"
        ),
    )

    with pytest.raises(AdapterDiscoveryError) as excinfo:
        discover_adapters(tmp_path)

    assert "doubleadapter" in str(excinfo.value)


def test_unregistered_convention_correct_adapter_breaks_parity(tmp_path: Path) -> None:
    """A convention-correct but unregistered adapter is caught, not silently run.

    Resolution B keeps the static ``HARNESS_REGISTRY`` authoritative at runtime
    and uses discovery only as a parity check. This proves the coverage-regression
    guarantee that motivates keeping discovery at all: an adapter added on disk
    without registering it is surfaced by discovery, so it diverges from the
    static registry — exactly what ``test_discover_finds_all_supported_adapters``
    asserts against the real tree.
    """
    harnesses = tmp_path / "harnesses"
    _write_package(
        harnesses / "frobtool",
        "# SPDX-License-Identifier: MIT\n\nclass FrobtoolAdapter:\n    pass\n",
    )

    discovered = discover_adapters(tmp_path)

    assert len(discovered) == 1
    (discovered_id,) = discovered
    assert discovered_id not in set(SUPPORTED_HARNESS_IDS)
    assert set(discovered) != set(SUPPORTED_HARNESS_IDS)
