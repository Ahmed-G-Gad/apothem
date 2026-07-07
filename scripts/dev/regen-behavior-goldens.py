#!/usr/bin/env python
# SPDX-License-Identifier: MIT

"""Regenerate the behavior-diff golden corpus from the deterministic oracles.

The behavior-diff regression wall (``tests/integration/test_install_driver_behavior_diff.py``
and ``test_cli_behavior_diff.py``) compares freshly-captured behavior against a
committed golden corpus under ``tests/fixtures/behavior-diff/``. The corpus is
produced by two deterministic, HOME-isolated oracles:

- ``_install_driver_oracle.capture_full`` — plan + dry-run + real-install across
  every adapter (self-clears + rewrites ``install_driver/``).
- ``_cli_oracle.capture`` — every CLI matrix invocation (self-clears + rewrites
  ``cli/``).

Both oracles normalize machine-specific paths (``_normalize_text`` /
``_path_variants``) and write LF line-endings, and the comparison layer
(``_behavior_canon``) collapses the remaining platform-divergent dimensions
(Rich heavy-vs-light box-drawing, path-length-driven column widths, backslash
vs forward-slash, array ordering). Together these make the corpus portable: a
capture taken on ANY platform — Windows included — compares equal on every
platform. This script is therefore safe to run from a Windows checkout.

Workflow:

    python scripts/dev/regen-behavior-goldens.py          # regenerate in place
    python -m pytest tests/integration/test_install_driver_behavior_diff.py \\
                     tests/integration/test_cli_behavior_diff.py             # verify
    git diff --stat tests/fixtures/behavior-diff/          # review churn

A non-empty ``git diff`` after regeneration means the committed corpus was
captured on a different platform than this run; the canonicalized comparison
still passes, but the stored bytes flip to this platform's form. Prefer
regenerating on the platform that owns the committed corpus, or accept the
one-time churn — the tests stay green either way.

The ``--dest DIR`` flag writes to an alternate directory instead of the
committed corpus, so a capture can be diffed without touching the working tree.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = REPO_ROOT / "tests" / "integration"
GOLDEN_ROOT = REPO_ROOT / "tests" / "fixtures" / "behavior-diff"


def _load_oracle(module_name: str) -> ModuleType:
    """Load an oracle module under a synthetic package so relative imports resolve.

    The oracles share helpers via ``from ._oracle_norm import ...``; a relative
    import needs a parent package. ``tests/integration`` carries no
    ``__init__.py`` — pytest supplies the package context itself — so a plain
    file-path load leaves ``__package__`` empty and the relative import raises
    ``ImportError``. Registering a synthetic package rooted at that directory and
    importing each oracle as a submodule of it reproduces the package context,
    so ``._oracle_norm`` resolves the same way it does under pytest.
    """
    package = "_behavior_diff_oracles"
    if package not in sys.modules:
        parent = ModuleType(package)
        parent.__path__ = [str(INTEGRATION)]
        sys.modules[package] = parent
    qualified = f"{package}.{module_name}"
    path = INTEGRATION / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(qualified, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise SystemExit(f"cannot load oracle module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the behavior-diff golden corpus (Windows-capable)."
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=GOLDEN_ROOT,
        help="Destination root for the corpus (default: the committed corpus).",
    )
    args = parser.parse_args()

    # The engine package must be importable; the dedicated .venv install or a
    # `PYTHONPATH=src` invocation both satisfy this.
    if str(REPO_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "src"))

    install_oracle = _load_oracle("_install_driver_oracle")
    cli_oracle = _load_oracle("_cli_oracle")

    dest: Path = args.dest
    install_oracle.capture_full(dest / "install_driver")
    print(
        f"[OK] install_driver corpus -> {dest / 'install_driver'} "
        f"({len(install_oracle.ALL_ADAPTERS)} adapters)"
    )

    cli_count = cli_oracle.capture(dest / "cli")
    print(f"[OK] cli corpus -> {dest / 'cli'} ({cli_count} captures)")

    print(
        "\nRegenerated. Verify with:\n"
        "  python -m pytest tests/integration/test_install_driver_behavior_diff.py "
        "tests/integration/test_cli_behavior_diff.py\n"
        "  git diff --stat tests/fixtures/behavior-diff/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
