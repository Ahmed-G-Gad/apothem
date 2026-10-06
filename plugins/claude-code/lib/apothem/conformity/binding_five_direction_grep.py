# SPDX-License-Identifier: MIT

"""Require the five-direction Bindings section on every rule, command, agent, and skill.

Why this enforcement exists. The bidirectional-binding rule (M10) closes every
structural artifact with a ``## Bindings (§0.j five-direction)`` section that
places it in the reference graph. The rules, commands, agents, and skills carry
the full set — **Drives →**, **Satisfies →**, **Established by ↑**, **Gated by
←**, **Cross-bound with ↔** — and each hook-message context carries the subset
its event shape supports (**Drives →**, **Established by ↑**, **Cross-bound with
↔**). The per-file ``binding_reciprocity_grep`` checks the arrow notation inside
a section that exists, and ``binding_reciprocity_corpus_grep`` checks ↔
reciprocity between rules; neither notices a section that is missing. This
corpus walker does, so a new rule or agent without bindings fails ``gate --all
--strict`` instead of passing silently.

Scope. The walker resolves the content root from a repository checkout
(``<root>/src/apothem``) or an installed harness tree (``<root>``) and inspects
``rules/*.md``, ``commands/*.md``, ``agents/*.md``, ``skills/**/SKILL.md``, and
``hooks/messages/*.md``. A folder ``README.md`` in the rules, commands, or
agents directory is in scope too: it is that folder's operating contract and
binds the folder into the same graph. The section is located outside fenced
code, and each direction is looked up as a bullet label inside the section,
so a fenced example or a direction named in the body prose does not count.

Posture — blocking. The corpus ships with every section present, so a finding
fails the validator and ``gate --all --strict`` exits non-zero on it. The
developer-script check ``scripts/dev/validate_ecosystem.py --check
binding-five-direction`` delegates here.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import (
    RootGrepResult,
    finish_root_report,
    iter_prose_lines,
    parse_root_args,
)

__all__ = ["DIRECTIONS_FULL", "DIRECTIONS_HOOK_MESSAGE", "Finding", "check"]

GREP_NAME: Final[str] = "binding-five-direction-grep"
RULE_ANCHOR: Final[str] = (
    "M10 bidirectional-binding §1 (five-direction Bindings section)"
)

# Content-root candidates, tried in order: the repository checkout keeps the
# convention directories under ``src/apothem``; an installed harness tree
# keeps them at its root.
_CONTENT_SUBTREES: Final[tuple[tuple[str, ...], ...]] = (("src", "apothem"), ())

# The direction labels each stratum requires, in canonical order. Hook messages
# are directional outputs of hook events, so Satisfies and Gated by collapse.
DIRECTIONS_FULL: Final[tuple[str, ...]] = (
    "Drives →",
    "Satisfies →",
    "Established by ↑",
    "Gated by ←",
    "Cross-bound with ↔",
)
DIRECTIONS_HOOK_MESSAGE: Final[tuple[str, ...]] = (
    "Drives →",
    "Established by ↑",
    "Cross-bound with ↔",
)

_BINDINGS_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+Bindings\b")
_NEXT_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^##?\s+\S")
_CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^[ \t]*(```|~~~)")
# A direction bullet opens with a bold label, e.g. ``- **Gated by ←** ...``.
_DIRECTION_BULLET_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*[-*]\s*\*\*\s*(?P<label>[^*]+?)\s*\*\*"
)
_WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")


@dataclass(frozen=True)
class Finding:
    """One artifact whose Bindings section is absent or incomplete.

    ``path`` is relative to the content root (``rules/x.md``); ``missing``
    lists the absent direction labels (every required label when the section
    itself is absent).
    """

    path: str
    detail: str
    missing: list[str] = field(default_factory=list)
    rule: str = RULE_ANCHOR


def _content_root(root: Path) -> Path | None:
    """Return the directory holding the convention strata, or None."""
    for parts in _CONTENT_SUBTREES:
        candidate = root.joinpath(*parts)
        if any((candidate / name).is_dir() for name in ("rules", "commands", "agents")):
            return candidate
    return None


def _targets(content: Path) -> list[tuple[Path, tuple[str, ...]]]:
    """Return every in-scope artifact paired with its required directions."""
    targets: list[tuple[Path, tuple[str, ...]]] = []
    for stratum in ("rules", "commands", "agents"):
        targets.extend(
            (path, DIRECTIONS_FULL)
            for path in sorted((content / stratum).glob("*.md"))
            if path.is_file()
        )
    targets.extend(
        (path, DIRECTIONS_FULL)
        for path in sorted((content / "skills").rglob("SKILL.md"))
        if path.is_file()
    )
    targets.extend(
        (path, DIRECTIONS_HOOK_MESSAGE)
        for path in sorted((content / "hooks" / "messages").glob("*.md"))
        if path.is_file()
    )
    return targets


def _section_labels(text: str) -> set[str] | None:
    """Return the direction labels of the Bindings section, or None if absent.

    The section is the first ``## Bindings`` heading outside fenced code and
    runs to the next ``#`` / ``##`` heading. Labels are whitespace-normalised.
    """
    inside = False
    found = False
    labels: set[str] = set()
    for _number, line, _scanned in iter_prose_lines(
        text.splitlines(), fence_re=_CODE_FENCE_RE
    ):
        if _BINDINGS_HEADING_RE.match(line):
            if found:
                break
            inside = found = True
            continue
        if inside and _NEXT_HEADING_RE.match(line):
            break
        if not inside:
            continue
        match = _DIRECTION_BULLET_RE.match(line)
        if match:
            labels.add(_WHITESPACE_RE.sub(" ", match.group("label").strip()))
    return labels if found else None


def check(root: Path) -> RootGrepResult:
    """Walk the content strata under *root*; report every incomplete section.

    Pre-conditions: *root* is a repository root or an installed harness tree.
    Post-conditions: ``result.inspected`` counts the artifacts examined (0 when
    no stratum exists under *root*); ``result.passed`` is True iff every
    examined artifact carries its stratum's required directions inside a
    ``## Bindings`` section.
    """
    content = _content_root(root)
    if content is None:
        return RootGrepResult(grep=GREP_NAME, root=str(root), passed=True)
    findings: list[Finding] = []
    targets = _targets(content)
    for path, required in targets:
        rel = path.relative_to(content).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(
                Finding(path=rel, detail=f"unreadable: {exc}", missing=list(required))
            )
            continue
        labels = _section_labels(text)
        if labels is None:
            findings.append(
                Finding(
                    path=rel,
                    detail=(
                        "no ## Bindings section; close the file with a "
                        "'## Bindings (§0.j five-direction)' section carrying "
                        + ", ".join(required)
                    ),
                    missing=list(required),
                )
            )
            continue
        missing = [label for label in required if label not in labels]
        if missing:
            findings.append(
                Finding(
                    path=rel,
                    detail="Bindings section lacks " + ", ".join(missing),
                    missing=missing,
                )
            )
    return RootGrepResult(
        grep=GREP_NAME,
        root=str(root),
        passed=not findings,
        findings=findings,
        inspected=len(targets),
    )


def _main(argv: list[str]) -> int:
    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    result = check(root)
    # Blocking posture: a missing or incomplete section is a gating
    # regression. A root with no content strata inspects nothing and fails.
    return finish_root_report(
        result.to_json(), passed=result.passed, inspected=result.inspected
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
