# SPDX-License-Identifier: MIT

"""Install-all resolution-sweep runtime benchmark per the per-class budget in
`src/apothem/rules/performance-discipline.md` §1.

Budget: 0.25 seconds for a dry-run install-all resolution sweep across every
registered adapter (propagation-rule resolution + capability projection, no
filesystem mutation).

The sweep resolves each adapter's propagation rules and capability-projection
warnings — the O(adapter-count) phase of an install-all that reads the shared
propagation manifest. With the TR-1 manifest-parse cache
(``load_manifest``'s ``lru_cache``) in place the manifest is parsed once for the
whole sweep; with the cache reverted each adapter re-parses it, pushing the
sweep roughly two orders of magnitude over and tripping this budget — the
regression this benchmark exists to catch.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Final

from apothem.harnesses._shared import install_driver
from apothem.lib.harness_registry import HARNESS_REGISTRY

# Seconds for the full install-all resolution sweep. A cold process parses the
# manifest once (~tens of ms) plus per-adapter resolution; the cache keeps the
# whole sweep well under this budget while a reverted cache (one parse per
# adapter) blows past it.
_BUDGET: Final[float] = 0.25


def _time_resolution_sweep() -> float:
    """Return wall-clock seconds to resolve rules + capabilities for all adapters."""
    names = [entry.package_key for entry in HARNESS_REGISTRY]
    start = time.monotonic()
    for name in names:
        install_driver.load_rules(name)
        install_driver._capability_projection_results(name)
    return time.monotonic() - start


def main(argv: list[str] | None = None) -> int:
    """Time the whole-registry adapter resolution sweep; return the exit code.

    Pre-conditions: ``argv`` is the argument vector without the program name
    (``None`` reads ``sys.argv``). The parser takes no flags — it exists so the
    sweep honours ``--help`` and rejects stray arguments like its siblings.

    Post-conditions: returns ``0`` when resolving every registered adapter
    stays inside the install budget, non-zero when it exceeds it.
    """
    argparse.ArgumentParser(prog="bench_install").parse_args(argv)
    elapsed = _time_resolution_sweep()
    label = f"install-all resolution sweep ({len(HARNESS_REGISTRY)} adapters)"
    if elapsed <= _BUDGET:
        print(f"PASS: {label} = {elapsed:.3f}s (budget {_BUDGET}s)")
        return 0
    print(f"FAIL: {label} = {elapsed:.3f}s exceeds budget {_BUDGET}s", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
