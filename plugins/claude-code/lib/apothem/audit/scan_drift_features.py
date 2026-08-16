# SPDX-License-Identifier: MIT

"""Detect references to deprecated or renamed features.

Why this scan exists. Narrative artifacts (rules, agents, commands,
hook context, docs) accumulate references to vendor features as the
upstream surface evolves: model identifiers retire, tool names change,
flags are renamed, capabilities are deprecated. A reference to a
retired feature is functionally a broken pointer — it leads readers
toward behavior the runtime no longer supports. The scan walks every
narrative surface for tokens drawn from a curated deprecated list and
emits a finding per occurrence so the refit phases can replace them.

What this scan covers. Deprecated tokens live in
``src/apothem/audit/deprecated-tokens.txt`` (one token per line; comments
prefixed with ``#``; case-sensitive substring match). The list is
intentionally seeded empty: at first run there is no proof any specific
token is deprecated, and a populated allow-list with no evidence would
fabricate findings. Tokens are added when the operator confirms a
specific feature has retired; the file then becomes a living deprecation
ledger.

What this scan walks. Source code (``*.py``, ``*.sh``, ``*.ps1``)
is also walked because deprecated identifiers can appear as string
literals in tooling scaffolds. Memory and plan-artifact files are
excluded per the shared narrative-surface filter.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scan_lib import (
    CONTENT_ROOT,
    NARRATIVE_CLASSES,
    SEVERITY_MEDIUM,
    Hit,
    WalkCallback,
    emit_json,
    load_inventory,
    walk_narrative_surfaces,
)


def _load_deprecated_tokens(token_file: Path) -> list[str]:
    """Parse the deprecated-token catalog.

    Lines beginning with ``#`` or empty lines are comments. Returns an
    empty list when the file is absent — the scan then emits zero hits,
    which is correct (no deprecated tokens declared, no findings).
    """
    if not token_file.exists():
        return []
    tokens: list[str] = []
    for raw in token_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tokens.append(line)
    return tokens


def _scan_file(tokens: list[str]) -> WalkCallback:
    """Build a callback that records every line containing any token."""

    def _walk(path: Path, record: dict[str, Any], content: str) -> list[Hit]:
        if not tokens:
            return []
        hits: list[Hit] = []
        for lineno, line in enumerate(content.splitlines(), start=1):
            for token in tokens:
                if token in line:
                    hits.append(
                        Hit(
                            file=record["path"],
                            line=lineno,
                            signal=f"deprecated-feature-reference: {token}",
                            severity=SEVERITY_MEDIUM,
                            remediation=(
                                f"Replace '{token}' with the current vendor identifier;"
                                " consult the deprecated-tokens.txt catalog for the"
                                " replacement guidance."
                            ),
                        )
                    )
        return hits

    return _walk


def main(argv: list[str] | None = None) -> int:
    """Walk every narrative surface for deprecated-token references and write ``drift-feature-refs.json``.

    Loads the inventory and the deprecated-token catalog, records a hit per
    line containing any listed token across the narrative surfaces, emits the
    JSON envelope, and prints a hit summary.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(".audit/inventory.json"),
        help="Path to inventory.json (default: ./.audit/inventory.json)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=CONTENT_ROOT,
        help="Content root the inventory paths resolve against "
        "(default: the src/apothem package).",
    )
    parser.add_argument(
        "--tokens",
        type=Path,
        default=Path("src/apothem/audit/deprecated-tokens.txt"),
        help="Deprecated-token catalog (default: src/apothem/audit/deprecated-tokens.txt)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".audit/drift-feature-refs.json"),
        help="Output JSON path (default: ./.audit/drift-feature-refs.json)",
    )
    args = parser.parse_args(argv)

    if not args.inventory.exists():
        print(f"error: inventory not found at {args.inventory}", file=sys.stderr)
        return 1

    records, sha = load_inventory(args.inventory)
    tokens = _load_deprecated_tokens(args.tokens)
    hits = walk_narrative_surfaces(records, args.root, _scan_file(tokens))
    emit_json(args.output, "scan_drift_features", hits, sha)
    narrative_count = sum(1 for r in records if r.get("class") in NARRATIVE_CLASSES)
    print(
        f"scan_drift_features: {len(hits)} hit(s) across "
        f"{narrative_count} narrative files "
        f"(deprecated-token catalog: {len(tokens)} entries)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
