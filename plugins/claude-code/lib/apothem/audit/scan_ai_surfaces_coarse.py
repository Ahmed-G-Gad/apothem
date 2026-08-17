# SPDX-License-Identifier: MIT

"""Coarse map of AI-conventions surfaces present in the working tree.

Why this scan exists. The ecosystem ships an AI-conventions surface
that spans multiple files, each authoritative within its own scope:
``AGENTS.md`` for the canonical project voice, ``CLAUDE.md`` for the
Claude Code mirror, ``.github/copilot-instructions.md`` for GitHub Copilot, optional surfaces
(``site/content/docs/architecture/agents.mdx``, ``.cursorrules``,
``.windsurfrules``) per the operator's opt-in. The detailed
section-presence map (``ai-surfaces.json``) is produced by a deeper
follow-up scan; this coarse pre-scan tells the deeper pass which
surfaces exist before it begins its content walk.

What this scan covers. Existence-and-presence checks for the
candidate surface paths plus the four mandatory-behavior blocks
that should appear inside ``AGENTS.md`` and mirror into ``CLAUDE.md``:

- ``AGENTS.md`` / ``CLAUDE.md`` mandatory blocks: `structured inquiry` discipline,
  Plans Discipline, Authorship Header, Multi-Surface AI Conventions.
  Each block's presence is detected by header / phrase heuristics.
- ``.github/copilot-instructions.md``: present / absent.
- Optional surfaces: presence flags only (no content scan).

What this scan reports. A single hit per detected absence or per
detected partial-presence. The output drives the deeper section-
presence pass and the optional-surface opt-in inquiry.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scan_lib import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    Hit,
    load_inventory,
    read_text_safely,
)

# Mandatory instruction-surface behavior blocks. Each is detected by a header
# phrase or canonical paragraph that signals the block's presence.
# Heuristic-driven; the deeper section-presence scan confirms
# structural conformance.
_MANDATORY_BLOCKS: Final[dict[str, list[str]]] = {
    "structured-inquiry discipline": [
        "structured inquiry",
        "interactive-questions",
        "structured-inquiry",
    ],
    "plans-discipline": [
        "plans-discipline",
        "Plans Discipline",
        ".plans/ at",
        "no-global-plans",
    ],
    "authorship-header": [
        "authorship-header",
        "Authorship Header",
        "authorship banner",
        "five canonical lines",
    ],
    "multi-surface-AI-conventions": [
        "multi-surface",
        "Multi-Surface",
        "AI conventions",
        "copilot-instructions",
    ],
}

# Optional opt-in AI-conventions surfaces. Each is a path probed for
# existence; absence is informational, not a finding. The operator
# ratifies which subset to materialize.
_OPTIONAL_SURFACES: Final[list[str]] = [
    "site/content/docs/architecture/agents.mdx",
    ".cursorrules",
    ".windsurfrules",
]

# The Copilot instructions surface is authored by the dedicated
# AI-conventions author pass.
_COPILOT_PATH: Final[str] = ".github/copilot-instructions.md"

# AGENTS.md is the canonical project voice surface; CLAUDE.md is the
# Claude Code mirror. Absence of either mandatory surface is fatal.
_AGENTS_PATH: Final[str] = "AGENTS.md"
_CLAUDE_PATH: Final[str] = "CLAUDE.md"


def _scan_instruction_surface(path: str, content: str) -> list[Hit]:
    """Detect missing mandatory blocks inside an instruction surface."""
    hits: list[Hit] = []
    for block_name, signals in _MANDATORY_BLOCKS.items():
        if not any(signal in content for signal in signals):
            hits.append(
                Hit(
                    file=path,
                    line=1,
                    signal=f"instruction-surface-missing-block: {block_name}",
                    severity=SEVERITY_HIGH,
                    remediation=(
                        f"Author the '{block_name}' block in {path} per"
                        " the spec's mandatory-behavior catalog; the"
                        " block carries the canonical project directive"
                        " for that surface."
                    ),
                )
            )
    return hits


def _scan_optional_surfaces(root: Path) -> list[Hit]:
    """Emit informational hits for opt-in surfaces present on disk."""
    hits: list[Hit] = []
    for path in _OPTIONAL_SURFACES:
        if (root / path).exists():
            hits.append(
                Hit(
                    file=path,
                    line=0,
                    signal=f"optional-surface-present: {path}",
                    severity=SEVERITY_LOW,
                    remediation=(
                        "The deeper section-presence scan confirms"
                        " structure; the opt-in inquiry recovers the"
                        " operator's ratification for keep / refit /"
                        " remove."
                    ),
                )
            )
    return hits


def main(argv: list[str] | None = None) -> int:
    """Coarse-scan the mandatory and optional AI-conventions surfaces and write ``drift-ai-surfaces-coarse.json``.

    Probes AGENTS.md / CLAUDE.md (presence plus mandatory-block coverage), the
    Copilot instructions surface, and the opt-in surfaces; emits one hit per
    absence or partial-presence and prints a presence summary.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(".audit/inventory.json"),
    )
    parser.add_argument("--root", type=Path, default=Path())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".audit/drift-ai-surfaces-coarse.json"),
    )
    args = parser.parse_args(argv)

    if not args.inventory.exists():
        print(
            f"error: inventory not found at {args.inventory}",
            file=sys.stderr,
        )
        return 1

    _, sha = load_inventory(args.inventory)
    hits: list[Hit] = []

    # Mandatory instruction-surface presence and block coverage.
    agents_path = args.root / _AGENTS_PATH
    claude_path = args.root / _CLAUDE_PATH
    if not agents_path.exists():
        hits.append(
            Hit(
                file=_AGENTS_PATH,
                line=0,
                signal="agents-md-absent",
                severity=SEVERITY_HIGH,
                remediation=(
                    "Author AGENTS.md at the repository root; this is the"
                    " canonical project instruction surface and its absence"
                    " disables downstream AI-conventions discipline."
                ),
            )
        )
    else:
        hits.extend(
            _scan_instruction_surface(_AGENTS_PATH, read_text_safely(agents_path))
        )

    if not claude_path.exists():
        hits.append(
            Hit(
                file=_CLAUDE_PATH,
                line=0,
                signal="claude-md-absent",
                severity=SEVERITY_HIGH,
                remediation=(
                    "Author CLAUDE.md as the Claude Code mirror of AGENTS.md;"
                    " its absence leaves that harness without the shared"
                    " instruction discipline."
                ),
            )
        )
    else:
        hits.extend(
            _scan_instruction_surface(_CLAUDE_PATH, read_text_safely(claude_path))
        )

    # Copilot instructions presence.
    copilot_path = args.root / _COPILOT_PATH
    if not copilot_path.exists():
        hits.append(
            Hit(
                file=_COPILOT_PATH,
                line=0,
                signal="copilot-instructions-absent",
                severity=SEVERITY_MEDIUM,
                remediation=(
                    "The AI-conventions author pass produces"
                    " .github/copilot-instructions.md per the canonical"
                    " nine-section structure. Until then the Copilot"
                    " surface defaults to its built-in heuristics without"
                    " the ecosystem's directive overlay."
                ),
            )
        )

    # Optional opt-in surfaces.
    hits.extend(_scan_optional_surfaces(args.root))

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "scanner": "scan_ai_surfaces_coarse",
        "inventory-source-sha256": sha,
        "agents-md-present": agents_path.exists(),
        "claude-md-present": claude_path.exists(),
        "copilot-instructions-present": copilot_path.exists(),
        "optional-surfaces-present": [
            p for p in _OPTIONAL_SURFACES if (args.root / p).exists()
        ],
        "hit-count": len(hits),
        "hits": [asdict(h) for h in hits],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"scan_ai_surfaces_coarse: AGENTS.md={agents_path.exists()},"
        f" CLAUDE.md={claude_path.exists()},"
        f" copilot-instructions={copilot_path.exists()},"
        f" optional={len(payload['optional-surfaces-present'])} of"
        f" {len(_OPTIONAL_SURFACES)}; total hits={len(hits)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
