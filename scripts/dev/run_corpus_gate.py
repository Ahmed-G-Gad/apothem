#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Repo-root entry point for the per-Write conformity corpus runner.

Why this wrapper exists. The pre-commit ``conformity-corpus-perwrite`` hook
must invoke ``apothem.conformity.gate`` without depending on the developer's
active environment having apothem installed — the apothem repo is self-
contained and runs from the checkout (``PYTHONPATH=src python -m apothem``).
A pre-commit ``language: python`` hook runs in an isolated venv where the
package is not on ``sys.path``; this wrapper prepends the checkout's ``src/``
directory to ``sys.path`` and dispatches to ``gate.main`` so the corpus runner
resolves from a plain checkout the same way the engine does.

The wrapper forwards every CLI argument to ``gate.main`` unchanged, so it is a
transparent shim: ``python scripts/dev/run_corpus_gate.py --all-perwrite . --strict``
behaves identically to ``python -m apothem.conformity.gate --all-perwrite . --strict``
when apothem is importable.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The checkout's ``src/`` directory sits two parents above this file
# (scripts/dev/run_corpus_gate.py -> scripts/dev -> scripts -> repo root).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from apothem.conformity.gate import main  # noqa: E402, I001 — import deliberately placed after the sys.path bootstrap above (the package is only importable once src/ is on the path); E402 allows the late import, I001 keeps ruff from reordering it back above the bootstrap

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
