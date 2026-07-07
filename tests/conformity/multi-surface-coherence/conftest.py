# SPDX-License-Identifier: MIT

"""Shared fixtures for the multi-surface-coherence validator self-tests.

Each test runs against an isolated fake-ecosystem rooted at ``tmp_path``.
The fixture seeds a minimal ``tests/fixtures/multi-surface-claims.yaml``
plus stub ``AGENTS.md``, ``CLAUDE.md``, and
``.github/copilot-instructions.md`` files and
patches the module-level ``ECOSYSTEM_ROOT`` anchor so the working tree's
real surfaces are never consulted during a unit test.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "multi_surface_coherence_grep.py"
)


SINGLE_CLAIM_FIXTURE: Final[str] = (
    "claims:\n"
    "  - id: header.canonical\n"
    "    claim: every applicable new file begins with the canonical banner\n"
    "    required-in:\n"
    "      - AGENTS.md\n"
    "      - CLAUDE.md\n"
    "      - .github/copilot-instructions.md\n"
    "    optional-in: []\n"
    "    semantic-equivalence-tokens:\n"
    "      - canonical banner\n"
    "      - applicable\n"
    "      - new file\n"
)


def _load_grep_module() -> ModuleType:
    """Load the multi-surface-coherence grep module via its source path."""
    spec = importlib.util.spec_from_file_location(
        "multi_surface_coherence_grep", _GREP_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load grep module at {_GREP_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["multi_surface_coherence_grep"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def grep_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> ModuleType:
    """Provide a freshly loaded grep module rooted at ``tmp_path``.

    The fixture creates the canonical claim-list directory shape and seeds
    the single-claim fixture; tests may overwrite the YAML body to exercise
    multi-claim scenarios.
    """
    module = _load_grep_module()
    fixtures_dir = tmp_path / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True)
    (fixtures_dir / "multi-surface-claims.yaml").write_text(
        SINGLE_CLAIM_FIXTURE, encoding="utf-8"
    )
    (tmp_path / ".github").mkdir()
    monkeypatch.setattr(module, "ECOSYSTEM_ROOT", tmp_path)
    return module


@pytest.fixture
def write_surface(tmp_path: Path) -> Callable[[str, str], Path]:
    """Return a helper that writes a surface body at the given relative path."""

    def _writer(relative: str, body: str) -> Path:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        return target

    return _writer
