# SPDX-License-Identifier: MIT

"""Pass + fail regression fixture for the registry-capability-consistency matcher.

The matcher asserts that every registry capability cell whose status is not in
``{unsupported, not-applicable, discovery-pending}`` is backed by evidence — a
propagation-manifest install entry, a materializer that authors the surface, or
a documented projection. This fixture pins one passing case (the corrected
post-CT-3 matrix passes clean against the real repository) and one failing case
(an over-claimed ``mcp_servers='native'`` cell on a harness whose sub-package
authors no MCP block).

The richer behaviour contract lives at
``tests/conformity/test_registry_capability_consistency.py``; this in-directory
fixture exists so the matcher-coverage loop resolves a ``test_*.py`` under
``registry-capability-consistency-grep/`` for the matcher.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_MODULE_PATH: Final[Path] = (
    _REPO_ROOT
    / "src"
    / "apothem"
    / "conformity"
    / "registry_capability_consistency_grep.py"
)


def _load() -> ModuleType:
    """Load the hyphen-named matcher module via an importlib spec."""
    spec = importlib.util.spec_from_file_location(
        "registry_capability_consistency_grep", _MODULE_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["registry_capability_consistency_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def test_pass_corrected_matrix_is_clean() -> None:
    """The corrected post-CT-3 matrix passes clean against the real repository."""
    result = _MOD.check(_REPO_ROOT)

    assert result.passed is True, [
        f"{f.harness}:{f.capability}={f.status}" for f in result.findings
    ]
    assert result.findings == []
    # The full 17-harness cohort is swept and a non-trivial number of
    # non-exempt cells is exercised (guards a silently-empty sweep).
    assert result.harnesses_checked == 17
    assert result.cells_checked > 0


def test_fail_over_claimed_mcp_native_without_materializer() -> None:
    """An mcp 'native' claim with no authoring materializer is a finding."""
    finding = _MOD._classify_cell(
        harness="claude-code",
        capability="mcp_servers",
        status="native",
        sources={"rules/", "skills/"},
        template_sources=set(),
        authors_mcp=False,  # no materializer renders MCP
    )

    assert finding is not None
    assert finding.harness == "claude-code"
    assert finding.capability == "mcp_servers"
    assert finding.status == "native"
    assert finding.evidence_class == "materializer"
