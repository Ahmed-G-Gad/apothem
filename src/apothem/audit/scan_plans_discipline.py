# SPDX-License-Identifier: MIT

"""Detect references to a global user-scope plans directory as a write target.

Why this scan exists. The harness-agnostic plans discipline forbids any
agent from writing plan artifacts to a global user-config root in any
host project — plans belong under ``<project-root>/.plans/``. For the
Claude Code harness specifically, the user-config root carries an
unfortunate recursion: the apothem plan-suite itself lives under
``~/.claude/.plans/`` during authoring, while the discipline being
installed forbids any agent from writing to that path in any host
project. The recursion is resolved by gitignoring the suite folder
once the migration is complete; before that, every directive that
points an agent at ``~/.claude/.plans/...`` (or any other harness's
global plans path) as a WRITE target is a discipline violation that
the refit phases need to remove. Read-references inside the discipline
documentation (rules, site docs, plan-suite specs) are exempt because they
describe the discipline itself.

What this scan covers per finding. Lines mentioning
``~/.claude/.plans/``, ``$CLAUDE_PROJECT_DIR/.plans/``, or equivalent
global-plans path variants in a directive context. The scan flags
write-intent verbs adjacent to the path (``write to``, ``create at``,
``store under``, ``save to``, ``emit at``, ``land at``) as HIGH
severity; bare references without write intent are flagged at MEDIUM
because the operator may be using the path as a documentation pointer.

What this scan excludes. Lines inside fenced code blocks (which
document, rather than direct, the path). Files explicitly classified
as discipline documentation (``src/apothem/rules/persistent-conventions-vigilance``,
``site/content/docs/reference/plans-discipline.mdx``, the plan-suite specs themselves) are
walked but their hits carry an ``is-discipline-doc`` flag in the extra
field so the synthesis pass can rank them lower.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scan_lib import (
    CONTENT_ROOT,
    NARRATIVE_CLASSES,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    Hit,
    emit_json,
    load_inventory,
    read_text_safely,
)

# Path patterns that indicate a reference to the user-scope plans dir.
_PLANS_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:~/\.claude/\.plans/|\$HOME/\.claude/\.plans/|\$CLAUDE_PROJECT_DIR/\.plans/"
    r"|%USERPROFILE%[\\/]\.claude[\\/]\.plans[\\/])",
    re.IGNORECASE,
)

# Verbs that indicate a write-intent directive — adjacency raises the
# severity classification.
_WRITE_INTENT_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:write|writes|writing|create|creates|creating|store|stores|"
    r"storing|save|saves|saving|emit|emits|emitting|land|lands|"
    r"landing|generate|generates|generating|persist|persists|persisting|"
    r"output|outputs|outputting|append|appends|appending|materialize|"
    r"materializes|materializing|materialize|materializes|materializing"
    r")\b",
    re.IGNORECASE,
)

# Files whose entire purpose is to document the plans-discipline; their
# references are read-targets, not write-targets, but the scan still
# flags them so the synthesis pass can decide. Paths are content-root-
# relative to match the inventory's record paths (the inventory is built
# with the content root as --root, so its paths carry bare top-level
# prefixes — `rules/...`, not `src/apothem/rules/...`). Surfaces outside
# the content root (`site/`, the repo-root `CLAUDE.md`) are not in the
# inventory and so never reach this scan; they are retained here only as
# an intent record for the day the scan scope widens.
_DISCIPLINE_DOC_PATHS: Final[frozenset[str]] = frozenset(
    {
        "rules/persistent-conventions-vigilance.md",
        "site/content/docs/reference/plans-discipline.mdx",
        "CLAUDE.md",
    }
)


def _is_discipline_doc(rel: str) -> bool:
    return rel in _DISCIPLINE_DOC_PATHS or rel.startswith(".plans/")


def _scan_file(rel: str, content: str) -> list[Hit]:
    """Walk a single narrative artifact for plans-discipline hits."""
    hits: list[Hit] = []
    in_fence = False
    is_doc = _is_discipline_doc(rel)
    for lineno, line in enumerate(content.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not _PLANS_PATH_RE.search(line):
            continue
        write_intent = bool(_WRITE_INTENT_RE.search(line))
        severity = SEVERITY_HIGH if write_intent else SEVERITY_MEDIUM
        kind = "plans-write-target" if write_intent else "plans-path-reference"
        hits.append(
            Hit(
                file=rel,
                line=lineno,
                signal=f"{kind}: {line.strip()[:120]}",
                severity=severity,
                remediation=(
                    "Replace the user-scope plans path with a"
                    " host-project-relative path (e.g.,"
                    " '<project>/.plans/'); the discipline forbids the"
                    " ecosystem from emitting plan artifacts under the"
                    " user-config root."
                ),
                extra={"is-discipline-doc": is_doc},
            )
        )
    return hits


def _scan_record(record: dict[str, Any], root: Path) -> list[Hit]:
    """Run the plans-discipline scan against one inventory record."""
    cls = record.get("class", "")
    if cls not in NARRATIVE_CLASSES:
        return []
    rel = record["path"]
    path = root / rel
    content = read_text_safely(path)
    if not content:
        return []
    return _scan_file(rel, content)


def main(argv: list[str] | None = None) -> int:
    """Scan narrative surfaces for global-plans-path references and write ``drift-plans-discipline.json``.

    Loads the inventory, flags every mention of a user-scope plans path
    (HIGH when a write-intent verb is adjacent, MEDIUM otherwise, tagging
    discipline-doc context), emits the envelope, and prints a summary.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(".audit/inventory.json"),
    )
    parser.add_argument("--root", type=Path, default=CONTENT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".audit/drift-plans-discipline.json"),
    )
    args = parser.parse_args(argv)

    if not args.inventory.exists():
        print(
            f"error: inventory not found at {args.inventory}",
            file=sys.stderr,
        )
        return 1

    records, sha = load_inventory(args.inventory)
    hits: list[Hit] = []
    for record in records:
        hits.extend(_scan_record(record, args.root))
    emit_json(args.output, "scan_plans_discipline", hits, sha)
    by_signal: dict[str, int] = {}
    for h in hits:
        kind = h.signal.split(":", 1)[0]
        by_signal[kind] = by_signal.get(kind, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_signal.items()))
    discipline_doc_share = sum(1 for h in hits if h.extra.get("is-discipline-doc"))
    print(
        f"scan_plans_discipline: {len(hits)} hit(s) "
        f"[{summary or 'none'}]; discipline-doc context: "
        f"{discipline_doc_share}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
