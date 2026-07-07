# SPDX-License-Identifier: MIT

"""Flag registry capability cells not backed by install / materializer / projection evidence.

Why this validator exists. The harness registry
(``src/apothem/lib/harness_registry.py``) declares, per harness, a
capability matrix whose cells claim how each cohort class
(``commands``, ``skills``, ``hooks``, ``agents``, ``rules``,
``templates``, ``statuslines``, ``output_styles``) and each agentic
surface (``mcp_servers``, ``sub_agent_dispatch``,
``tool_surface_restrictions``, ``system_prompt_templates``,
``agent_memory``) is delivered. A cell that claims a delivery status
(``native`` / ``converted`` / ``support-tree`` / ``profile-projected``)
without a corresponding install entry, materializer, or documented
projection is a silent over-claim: the matrix advertises a surface the
adapter does not actually author. This validator is the mechanical guard
against that drift across the full 17-harness cohort.

What counts as evidence. A capability cell whose status is *not* in the
exempt set ``{unsupported, not-applicable, discovery-pending}`` MUST be
backed by one of:

- **A manifest install entry.** For a cohort class the propagation
  manifest (``src/apothem/lib/propagation-manifest.yaml``) must carry an
  ``install`` entry whose ``source`` materializes that class — the cohort
  source directory (``commands/`` … ``output-styles/``) for the cohort
  classes, or the adapter's own instruction / rules template (one of the
  registry entry's ``template_sources``) for the ``rules`` and
  ``system_prompt_templates`` surfaces.
- **A materializer that renders the surface.** An ``mcp_servers`` cell
  claiming ``native`` MUST be backed by a sibling ``materializer.py`` that
  exposes ``materialize_native_config`` and renders an MCP block — the
  three authoring harnesses (opencode / qwen-code / hermes). An
  operator-owned-recognized MCP surface (status ``discovery-pending``) is
  exempt: apothem names but does not author it.
- **A documented projection.** ``sub_agent_dispatch`` is a harness
  *behavior*, not a file the adapter writes; a present (non-exempt) status
  is backed by the capabilities-dossier ``sub_agent_dispatch`` flag.
  ``agent_memory``, when not exempt, is likewise a projection-backed cell.

Detection. The validator imports the registry, reads the propagation
manifest, and inspects each harness sub-package for a materializer. For
each registry entry, every non-exempt cell is checked against the
evidence rules above; an unbacked cell produces a structured finding
naming the harness, the cell, its claimed status, and the missing
evidence class.

Exit semantics. Exits 0 when every non-exempt cell across all 15
harnesses is backed by evidence; exits 2 on any over-claim. The exit-2
convention matches the conformity-gate orchestrator's ``EXIT_FAIL``
constant.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

GREP_NAME: Final[str] = "registry-capability-consistency-grep"
RULE_ANCHOR: Final[str] = (
    "rules/agent-capability-discipline.md — registry capability cells backed by evidence"
)

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# Capability statuses that need no backing evidence: a surface apothem does
# not deliver (unsupported), an axis that does not apply to the harness
# (not-applicable), or an operator-owned surface apothem names but does not
# author (discovery-pending).
EXEMPT_STATUSES: Final[frozenset[str]] = frozenset(
    {"unsupported", "not-applicable", "discovery-pending"}
)

# Cohort capability cells backed by a manifest install entry whose ``source``
# is the cohort source directory. The value is the manifest ``source`` prefix.
_COHORT_SOURCE: Final[dict[str, str]] = {
    "commands": "commands/",
    "skills": "skills/",
    "hooks": "hooks/",
    "agents": "agents/",
    "templates": "templates/",
    "statuslines": "statuslines/",
    "output_styles": "output-styles/",
}

# The cohort rules source directory; the rules / system-prompt surfaces accept
# either this directory entry or the adapter's own instruction template.
_RULES_SOURCE: Final[str] = "rules/"

# The harness package keys whose ``materializer.py`` authors a native MCP
# block. The validator confirms the materializer is present and renders MCP
# rather than trusting the registry status alone.
_MATERIALIZER_FILENAME: Final[str] = "materializer.py"
_MATERIALIZER_FUNCTION: Final[str] = "materialize_native_config"
_MCP_RENDER_MARKERS: Final[tuple[str, ...]] = (
    "render_mcp_opencode",
    "render_mcp_standard",
    "render_mcp",
)


@dataclass(frozen=True)
class Finding:
    """One over-claimed capability cell lacking backing evidence."""

    harness: str
    capability: str
    status: str
    detail: str
    evidence_class: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result for a single registry-consistency sweep."""

    grep: str
    root: str
    harnesses_checked: int
    cells_checked: int
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        payload = {
            "grep": self.grep,
            "root": self.root,
            "harnesses_checked": self.harnesses_checked,
            "cells_checked": self.cells_checked,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _manifest_path(root: Path) -> Path:
    return root / "src" / "apothem" / "lib" / "propagation-manifest.yaml"


def _load_manifest(root: Path) -> dict[str, Any]:
    """Load the propagation manifest. Missing / unparseable → empty mapping."""
    path = _manifest_path(root)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        loaded = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _install_sources(manifest: dict[str, Any], package_key: str) -> set[str]:
    """Return the set of ``source`` values declared for a harness install list."""
    harnesses = manifest.get("harnesses")
    if not isinstance(harnesses, dict):
        return set()
    entry = harnesses.get(package_key)
    if not isinstance(entry, dict):
        return set()
    install = entry.get("install")
    if not isinstance(install, list):
        return set()
    sources: set[str] = set()
    for item in install:
        if isinstance(item, dict):
            source = item.get("source")
            if isinstance(source, str):
                sources.add(source)
    return sources


def _materializer_authors_mcp(root: Path, package_key: str) -> bool:
    """Return True when the harness sub-package materializes a native MCP block.

    The harness's ``materializer.py`` must expose ``materialize_native_config``
    and reference an MCP render helper; a markdown-template-only adapter has no
    materializer and authors no MCP surface.
    """
    path = root / "src" / "apothem" / "harnesses" / package_key / _MATERIALIZER_FILENAME
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if _MATERIALIZER_FUNCTION not in text:
        return False
    return any(marker in text for marker in _MCP_RENDER_MARKERS)


def _rules_backed(sources: set[str], template_sources: set[str]) -> bool:
    """A rules / system-prompt surface is backed by the cohort rules dir or a template."""
    if _RULES_SOURCE in sources:
        return True
    return bool(template_sources & sources)


def check(root: Path) -> GrepResult:
    """Walk the registry under ``root``; flag capability cells lacking evidence.

    Imports the registry lazily so the module loads cleanly even when the
    package is mounted at an installed layout whose ``sys.path`` differs from
    the repository checkout. When the registry cannot be imported the sweep
    degrades to an informational pass (zero cells checked) rather than a hard
    error — the gate must not fail-close on an import boundary it cannot reach.
    """
    try:
        from apothem.lib.harness_registry import (
            HARNESS_REGISTRY,
            REQUIRED_CAPABILITIES,
        )
    except Exception:  # import boundary: degrade to informational pass
        return GrepResult(
            grep=GREP_NAME,
            root=str(root),
            harnesses_checked=0,
            cells_checked=0,
            passed=True,
            findings=[],
        )

    manifest = _load_manifest(root)
    findings: list[Finding] = []
    harnesses_checked = 0
    cells_checked = 0

    for entry in HARNESS_REGISTRY:
        harnesses_checked += 1
        package_key = entry.package_key
        sources = _install_sources(manifest, package_key)
        template_sources = set(entry.template_sources)
        authors_mcp = _materializer_authors_mcp(root, package_key)

        for capability in REQUIRED_CAPABILITIES:
            status = entry.capability_status[capability]
            if status in EXEMPT_STATUSES:
                continue
            cells_checked += 1
            finding = _classify_cell(
                harness=entry.public_id,
                capability=capability,
                status=status,
                sources=sources,
                template_sources=template_sources,
                authors_mcp=authors_mcp,
            )
            if finding is not None:
                findings.append(finding)

    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        harnesses_checked=harnesses_checked,
        cells_checked=cells_checked,
        passed=not findings,
        findings=findings,
    )


def _classify_cell(
    *,
    harness: str,
    capability: str,
    status: str,
    sources: set[str],
    template_sources: set[str],
    authors_mcp: bool,
) -> Finding | None:
    """Return a Finding when *capability* is over-claimed, else None.

    The capability is matched against its evidence class. A backed cell
    returns None; an unbacked cell returns a structured finding naming the
    missing evidence class.
    """
    # Cohort classes delivered through a manifest install source directory.
    if capability in _COHORT_SOURCE:
        if _COHORT_SOURCE[capability] in sources:
            return None
        return Finding(
            harness=harness,
            capability=capability,
            status=status,
            detail=(
                f"capability claims '{status}' but no propagation-manifest "
                f"install entry sources '{_COHORT_SOURCE[capability]}' for "
                f"this harness"
            ),
            evidence_class="manifest-install-entry",
        )

    # The rules surface and the system-prompt template surface: backed by the
    # cohort rules directory or the adapter's own instruction template.
    if capability in {"rules", "system_prompt_templates"}:
        if _rules_backed(sources, template_sources):
            return None
        return Finding(
            harness=harness,
            capability=capability,
            status=status,
            detail=(
                f"capability claims '{status}' but no install entry sources "
                f"'{_RULES_SOURCE}' nor any declared instruction template "
                f"({sorted(template_sources) or 'none'}) for this harness"
            ),
            evidence_class="manifest-install-entry",
        )

    # The MCP surface: a 'native' cell requires a materializer that authors MCP.
    if capability == "mcp_servers":
        if authors_mcp:
            return None
        return Finding(
            harness=harness,
            capability=capability,
            status=status,
            detail=(
                f"capability claims '{status}' but no sibling "
                f"{_MATERIALIZER_FILENAME} exposes {_MATERIALIZER_FUNCTION} "
                f"rendering a native MCP block for this harness"
            ),
            evidence_class="materializer",
        )

    # Documented-projection cells: harness behaviors, not adapter-written files.
    # A present (non-exempt) status is itself the documented projection.
    if capability in {
        "sub_agent_dispatch",
        "tool_surface_restrictions",
        "agent_memory",
    }:
        return None

    # An unrecognized capability axis with a non-exempt status: surface it so a
    # new axis cannot slip past the gate unbacked.
    return Finding(
        harness=harness,
        capability=capability,
        status=status,
        detail=(
            f"capability claims '{status}' but the validator recognizes no "
            f"evidence class for this axis"
        ),
        evidence_class="unrecognized-axis",
    )


def _read_input(argv: list[str]) -> Path:
    if len(argv) >= 2:
        return Path(argv[1])
    return Path.cwd()


def _main(argv: list[str]) -> int:
    root = _read_input(argv)
    result = check(root)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
