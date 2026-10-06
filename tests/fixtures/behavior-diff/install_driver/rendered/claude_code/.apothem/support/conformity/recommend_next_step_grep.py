# SPDX-License-Identifier: MIT

"""Verify every command file carries a `## Recommended Next Step` block.

Why this enforcement exists. Per `rules/recommend-next-step.md`, every
`commands/*.md` artifact terminates its working trace with a
Recommended-Next-Step block so the operator's onward path is named at
the close of every command. The block lands in one of two canonical
forms: the singular `## Recommended Next Step` heading followed by
substantive prose, or the multi-action `## Next Steps` heading whose
option list carries exactly one `**Recommended**` marker.

Detection strategy. The validator walks two terminal-surface classes —
`src/apothem/commands/*.md` (excluding `README.md` — the command-class
index is not itself a command) and `src/apothem/skills/*/SKILL.md` — to
match the rule's declared command-and-skill scope. For each surface it
locates either of the two heading forms; absence is a finding. For the
singular form the validator verifies the heading is followed by at least
one non-empty prose line. For the multi-action form the validator counts
`**Recommended**` markers between the heading and the next sibling H2 (or
end of file); exactly one is admissible. Zero or two-plus markers is a
finding.

Exit semantics. Exits 0 when every command file passes; exits 2 on any
finding. The exit-2 convention matches the conformity-gate
orchestrator's EXIT_FAIL constant.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "recommend-next-step-grep"
RULE_ANCHOR: Final[str] = "rules/recommend-next-step.md"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# Terminal-surface roots relative to the repository root supplied at invocation.
COMMANDS_DIR: Final[str] = "src/apothem/commands"
SKILLS_DIR: Final[str] = "src/apothem/skills"

# Filenames excluded from the sweep — folder-companion docs, not commands:
# the human-facing directory index and the agent-facing companion.
EXCLUDED_FILES: Final[frozenset[str]] = frozenset({"README.md", "AGENTS.md"})

# Heading patterns. The singular form is the dominant convention; the
# multi-action `## Next Steps` form is admissible when the command's
# close branches across several options.
SINGULAR_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^##\s+Recommended\s+Next\s+Step\s*$"
)
MULTI_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+Next\s+Steps\s*$")

# Any H2 heading — used to scope the multi-action block's option list to
# the region between its own heading and the next sibling H2.
ANY_H2_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+\S")

# Recommended marker. The convention is the literal `**Recommended**`
# bolded token, matching the canonical option-annotation discipline.
RECOMMENDED_MARKER_RE: Final[re.Pattern[str]] = re.compile(r"\*\*Recommended\*\*")


@dataclass(frozen=True)
class Finding:
    """One command file that lacks a valid Recommended-Next-Step block."""

    surface: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated sweep result across every command file."""

    grep: str
    root: str
    files_inspected: int
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, files_inspected,
        passed, findings}``; each finding is flattened through
        ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "files_inspected": self.files_inspected,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _has_substantive_prose(lines: list[str], start_index: int) -> bool:
    """Return True iff at least one non-empty prose line follows the heading.

    The scan stops at the next H2 (sibling heading) or end of file.
    Empty lines, whitespace-only lines, and HTML-comment lines do not
    count as substantive content.
    """
    for line in lines[start_index + 1 :]:
        if ANY_H2_RE.match(line):
            return False
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("<!--") or stripped.startswith("-->"):
            continue
        return True
    return False


def _count_recommended_markers(lines: list[str], start_index: int) -> int:
    """Count `**Recommended**` markers between heading and next H2."""
    count = 0
    for line in lines[start_index + 1 :]:
        if ANY_H2_RE.match(line):
            break
        count += len(RECOMMENDED_MARKER_RE.findall(line))
    return count


def _classify_command_file(path: Path) -> Finding | None:
    """Return a finding when the command file lacks a valid block."""
    try:
        body = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Finding(
            surface=str(path),
            detail=f"could not read command file: {exc}",
        )
    lines = body.splitlines()
    singular_index = next(
        (i for i, line in enumerate(lines) if SINGULAR_HEADING_RE.match(line)),
        None,
    )
    multi_index = next(
        (i for i, line in enumerate(lines) if MULTI_HEADING_RE.match(line)),
        None,
    )
    if singular_index is None and multi_index is None:
        return Finding(
            surface=str(path),
            detail=(
                "no `## Recommended Next Step` or `## Next Steps` heading "
                "found; the command must close with the canonical block"
            ),
        )
    if singular_index is not None:
        if not _has_substantive_prose(lines, singular_index):
            return Finding(
                surface=str(path),
                detail=(
                    "`## Recommended Next Step` heading present but block is "
                    "empty; the canonical form carries at least one prose line"
                ),
            )
        return None
    # Multi-action form: verify exactly one Recommended marker.
    # singular_index is None here (else returned above) and not both were None,
    # so multi_index is necessarily set; the guard narrows the type and is
    # unreachable in practice.
    if multi_index is None:  # pragma: no cover
        return None
    marker_count = _count_recommended_markers(lines, multi_index)
    if marker_count == 0:
        return Finding(
            surface=str(path),
            detail=(
                "`## Next Steps` block carries zero `**Recommended**` markers; "
                "the multi-action form requires exactly one"
            ),
        )
    if marker_count > 1:
        return Finding(
            surface=str(path),
            detail=(
                f"`## Next Steps` block carries {marker_count} `**Recommended**` "
                f"markers; the multi-action form admits exactly one"
            ),
        )
    return None


def check(root: Path) -> GrepResult:
    """Sweep every command and skill surface under root for the block."""
    findings: list[Finding] = []
    files_inspected = 0

    commands_dir = root / COMMANDS_DIR
    if not commands_dir.is_dir():
        findings.append(
            Finding(
                surface=COMMANDS_DIR,
                detail=(f"commands directory absent at canonical path {commands_dir}"),
            )
        )
    else:
        for path in sorted(commands_dir.glob("*.md")):
            if path.name in EXCLUDED_FILES:
                continue
            files_inspected += 1
            finding = _classify_command_file(path)
            if finding is not None:
                findings.append(finding)

    skills_dir = root / SKILLS_DIR
    if not skills_dir.is_dir():
        findings.append(
            Finding(
                surface=SKILLS_DIR,
                detail=(f"skills directory absent at canonical path {skills_dir}"),
            )
        )
    else:
        for path in sorted(skills_dir.glob("*/SKILL.md")):
            files_inspected += 1
            finding = _classify_command_file(path)
            if finding is not None:
                findings.append(finding)

    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        files_inspected=files_inspected,
        passed=not findings,
        findings=findings,
    )


def _main(argv: list[str]) -> int:
    # Imported here, not at module top: ``check()`` stays stdlib-only; only
    # the command-line entry needs the shared parser and report stamp.
    from apothem.conformity._grep_base import finish_root_report, parse_root_args

    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    result = check(root)
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=result.files_inspected,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
