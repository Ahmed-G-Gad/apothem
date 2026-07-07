# SPDX-License-Identifier: MIT

"""Memory-tier health audit for the apothem ecosystem.

Scope
-----
Walks two memory tiers, reporting the state of each MEMORY.md index and its
topic files:

* **Project memory** — ``{root}/projects/*/memory/`` (one subtree per project).
* **Global memory** — ``{root}/memory/`` when present.

Checks
------
For each memory tree with a ``MEMORY.md`` file:

1. **Line budget** — MEMORY.md must be ≤ 200 lines. Anything beyond is
   ignored by loaders per the auto-memory rule.
2. **Topic index integrity** — every topic file referenced from MEMORY.md
   must exist on disk.
3. **Orphan topic files** — every ``.md`` sibling of MEMORY.md (other than
   itself) should appear in the index.
4. **Frontmatter freshness** — when a topic file declares an ``updated:``
   field, it must parse as ISO ``YYYY-MM-DD``.

Exit codes
----------
* ``0`` — no findings.
* ``1`` — at least one warning (e.g. ``--fix`` did mechanical trims).
* ``2`` — at least one hard failure (broken reference, malformed date,
  missing MEMORY.md on a populated memory tree).

``--fix``
---------
Mechanical only: truncates MEMORY.md to 200 lines when over budget.
Never rewrites topic files, never touches frontmatter, never invents index
entries. Every structural issue is reported for the operator to resolve.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Final

_LINE_LIMIT: Final[int] = 200
_ISO_DATE: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MD_LINK: Final[re.Pattern[str]] = re.compile(r"\[[^\]]+\]\(([^)]+\.md)\)")
_FRONTMATTER: Final[re.Pattern[str]] = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)
_UPDATED: Final[re.Pattern[str]] = re.compile(
    r'^updated\s*:\s*["\']?([^"\'\n]+?)["\']?\s*$', re.MULTILINE
)


@dataclass
class Finding:
    """A single audit observation."""

    severity: str  # "info" | "warn" | "fail"
    tree: Path
    message: str


@dataclass
class TreeReport:
    """Audit result for a single memory tree."""

    root: Path
    findings: list[Finding] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.findings.append(Finding("fail", self.root, message))

    def warn(self, message: str) -> None:
        self.findings.append(Finding("warn", self.root, message))

    def info(self, message: str) -> None:
        self.findings.append(Finding("info", self.root, message))

    @property
    def fails(self) -> int:
        return sum(1 for f in self.findings if f.severity == "fail")

    @property
    def warns(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warn")


def discover_memory_trees(root: Path) -> list[Path]:
    """Return every directory that should be audited as a memory tree."""
    trees: list[Path] = []
    global_tree = root / "memory"
    if global_tree.is_dir():
        trees.append(global_tree)
    projects = root / "projects"
    if projects.is_dir():
        for sub in sorted(projects.iterdir()):
            candidate = sub / "memory"
            if candidate.is_dir():
                trees.append(candidate)
    return trees


def _topic_references(index_text: str) -> list[str]:
    """Extract markdown link targets that look like topic file paths."""
    return [m.group(1) for m in _MD_LINK.finditer(index_text)]


def _updated_value(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = _FRONTMATTER.match(text)
    if match is None:
        return None
    upd = _UPDATED.search(match.group(1))
    return upd.group(1).strip() if upd else None


def _check_iso_date(value: str) -> bool:
    if not _ISO_DATE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def audit_tree(tree: Path, *, apply_fix: bool) -> TreeReport:
    """Run every check against a single memory tree."""
    report = TreeReport(root=tree)
    index = tree / "MEMORY.md"
    if not index.is_file():
        # If the tree has any markdown content, absence of MEMORY.md is a fail.
        has_content = any(p.suffix == ".md" for p in tree.rglob("*.md"))
        if has_content:
            report.fail("MEMORY.md missing but topic files exist")
        else:
            report.info("empty memory tree")
        return report

    lines = index.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) > _LINE_LIMIT:
        if apply_fix:
            trimmed = lines[:_LINE_LIMIT]
            index.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
            report.warn(f"MEMORY.md trimmed from {len(lines)} to {_LINE_LIMIT} lines")
        else:
            report.fail(
                f"MEMORY.md is {len(lines)} lines (limit {_LINE_LIMIT}); "
                "run with --fix to truncate"
            )

    index_text = "\n".join(lines)
    references = _topic_references(index_text)
    declared: set[Path] = set()
    for ref in references:
        resolved = (tree / ref).resolve()
        try:
            resolved.relative_to(tree.resolve())
        except ValueError:
            report.warn(f"topic reference escapes tree: {ref}")
            continue
        declared.add(resolved)
        if not resolved.is_file():
            report.fail(f"topic referenced but missing on disk: {ref}")

    actual_topics = {
        p.resolve() for p in tree.rglob("*.md") if p.resolve() != index.resolve()
    }
    for orphan in sorted(actual_topics - declared):
        try:
            rel = orphan.relative_to(tree.resolve())
        except ValueError:
            rel = orphan
        report.warn(f"topic file not indexed in MEMORY.md: {rel}")

    for topic in actual_topics:
        value = _updated_value(topic)
        if value is None:
            continue
        if not _check_iso_date(value):
            try:
                rel = topic.relative_to(tree.resolve())
            except ValueError:
                rel = topic
            report.fail(f"topic {rel} has malformed updated: {value!r}")

    return report


def format_finding(finding: Finding, ecosystem_root: Path) -> str:
    """Render a single finding as a single line."""
    marker = {
        "fail": "[FAIL]",
        "warn": "[WARN]",
        "info": "[INFO]",
    }[finding.severity]
    try:
        rel = finding.tree.relative_to(ecosystem_root)
    except ValueError:
        rel = finding.tree
    return f"{marker} {rel}: {finding.message}"


def report(
    tree_reports: Iterable[TreeReport],
    *,
    ecosystem_root: Path,
) -> int:
    """Emit findings and return an exit code in {0, 1, 2}."""
    total_fail = 0
    total_warn = 0
    total_trees = 0
    for rep in tree_reports:
        total_trees += 1
        for finding in rep.findings:
            sys.stdout.write(format_finding(finding, ecosystem_root) + "\n")
        total_fail += rep.fails
        total_warn += rep.warns

    sys.stdout.write(
        f"\nMemory audit: trees={total_trees}, "
        f"failures={total_fail}, warnings={total_warn}\n"
    )
    if total_fail:
        return 2
    if total_warn:
        return 1
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(prog="memory_audit")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent,
        help="Ecosystem root (defaults to the repo containing this script).",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply mechanical fixes (currently: trim MEMORY.md to "
        f"{_LINE_LIMIT} lines).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    trees = discover_memory_trees(args.root)
    if not trees:
        sys.stdout.write("No memory trees found; nothing to audit.\n")
        return 0
    reports = [audit_tree(tree, apply_fix=args.fix) for tree in trees]
    return report(reports, ecosystem_root=args.root)


if __name__ == "__main__":
    sys.exit(main())
