# SPDX-License-Identifier: MIT

"""Manifest parse is memoized; materializer installs call run_install once.

Two performance/dedup invariants:

1. ``propagation.load_manifest`` memoizes the parse per process (keyed by the
   manifest path + mtime), so a batch command that resolves rules once per
   harness parses the manifest only once — while preserving the
   ``FileNotFoundError`` / ``ValueError`` contract.
2. The four materializer adapters (opencode, hermes, open_claw, qwen_code) call
   ``install_driver.run_install`` exactly once per install — the throwaway
   ``dry_run=True`` preview was replaced by a direct
   ``capability_projection_results`` call, so the capability-projection warnings
   are identical without the second pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses.hermes import HermesAdapter
from apothem.harnesses.open_claw import OpenClawAdapter
from apothem.harnesses.opencode import OpenCodeAdapter
from apothem.harnesses.qwen_code import QwenCodeAdapter
from apothem.lib import propagation


def test_load_manifest_parses_once_per_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fifteen resolutions in one process parse the manifest exactly once."""
    propagation._load_manifest_cached.cache_clear()
    calls = {"n": 0}
    real_parse = propagation._parse_manifest_text

    def counting(text: str) -> dict[str, propagation.HarnessRules]:
        calls["n"] += 1
        return real_parse(text)

    monkeypatch.setattr(propagation, "_parse_manifest_text", counting)
    results = [propagation.load_manifest() for _ in range(15)]
    assert calls["n"] == 1, f"manifest parsed {calls['n']} times (expected 1)"
    assert all("claude_code" in rules for rules in results)


def test_load_manifest_raises_file_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An absent manifest still raises FileNotFoundError (before the cache).

    ``load_manifest`` resolves the manifest as ``files("apothem.lib") /
    _MANIFEST_FILENAME`` inside an ``as_file`` context; redirecting the
    package traversable to an empty ``tmp_path`` leaves the manifest absent.
    """
    monkeypatch.setattr(propagation, "files", lambda _package: tmp_path)
    with pytest.raises(FileNotFoundError):
        propagation.load_manifest()


def test_load_manifest_raises_value_error_on_malformed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A manifest missing the top-level 'harnesses' key still raises ValueError."""
    bad = tmp_path / propagation._MANIFEST_FILENAME
    bad.write_text("version: 1\nnot_harnesses: {}\n", encoding="utf-8")
    monkeypatch.setattr(propagation, "files", lambda _package: tmp_path)
    propagation._load_manifest_cached.cache_clear()
    with pytest.raises(ValueError, match="harnesses"):
        propagation.load_manifest()


_MATERIALIZER_ADAPTERS = [
    OpenCodeAdapter,
    HermesAdapter,
    OpenClawAdapter,
    QwenCodeAdapter,
]


@pytest.mark.parametrize(
    "adapter_cls", _MATERIALIZER_ADAPTERS, ids=lambda c: c.__name__
)
def test_materializer_install_calls_run_install_once(
    adapter_cls: type,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each materializer install drives run_install exactly once, same warnings."""
    adapter = adapter_cls()
    target = tmp_path / Path(adapter.output_path).name
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))

    calls = {"n": 0}
    real_run_install = install_driver.run_install

    def spy(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        return real_run_install(*args, **kwargs)

    monkeypatch.setattr(install_driver, "run_install", spy)
    run = adapter.install({})

    assert calls["n"] == 1, (
        f"{adapter.name} called run_install {calls['n']} times (expected exactly 1)"
    )
    # The capability-projection warnings carried by the install match the direct
    # projection call that replaced the dry-run preview — same set by capability.
    expected = {
        result.detail["capability"]
        for result in install_driver.capability_projection_results(adapter.name)
    }
    got = {
        result.detail["capability"]
        for result in run.results
        if result.outcome == "warning" and result.operation == "capability_projection"
    }
    assert got == expected
