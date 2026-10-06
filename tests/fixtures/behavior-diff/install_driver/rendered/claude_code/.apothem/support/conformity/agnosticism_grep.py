# SPDX-License-Identifier: MIT

"""Flag harness bias and re-introduced enforcement presets in shipped surfaces.

Why this enforcement exists. The agnostic-posture rule
(``rules/agnostic-posture.md``) requires every shipped surface to be
harness-neutral and free of imposed enforcement: a clean install privileges
no harness and pre-sets no model, effort, or workflow. This sweep is the
mechanical guard for that posture's two failure classes — it is the
agnosticism counterpart of ``plain_language_grep`` (the two sweeps are paired
by the phase that introduces them).

Scope. Corpus-level standalone validator. Walks the working tree under the
supplied root and inspects ONLY the four shipped-surface directories:

- ``src/apothem/rules/`` — behavioral instruction files.
- ``src/apothem/commands/`` — slash-command definitions.
- ``src/apothem/output-styles/`` — output-style definitions.
- ``src/apothem/statuslines/`` — statusline definitions.

Every other path is out of scope: tests, plans, harness adapter packages
(whose per-harness catalog content legitimately names every harness), and
all source code outside the four prose surfaces.

Detection — two closed classes.

1. **Harness bias.** The brand phrase ``Claude Code`` and the branded model
   names ``Claude Opus`` / ``Claude Sonnet`` / ``Claude Haiku`` are
   privileging forms: they tailor a shipped surface to one harness. The
   canonical slug ``claude_code`` is the neutral catalog identifier — a line
   that carries the slug is a per-harness catalog row (one entry among the
   registered harnesses) and is exempt. Matches inside fenced code
   blocks are excluded (a fenced example is not shipped prose).

2. **Enforcement preset.** A shipped command, skill, or agent that
   re-introduces an ``effort:`` or ``model:`` frontmatter default imposes a
   preference the end user is meant to supply in conversation. The sweep
   flags any non-empty ``effort:`` / ``model:`` key inside the YAML
   frontmatter block of a command, skill, or agent definition.

Exit semantics. Exits 0 when zero findings across every in-scope file;
exits 2 on any finding. The exit-2 convention matches the conformity-gate
orchestrator's EXIT_FAIL constant. The gate renders this sweep as an
advisory by default; ``--strict`` (or ``APOTHEM_CONFORMITY_STRICT``)
restores blocking, per the agnostic-posture advisory-gate discipline.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import (
    finish_root_report,
    iter_prose_lines,
    parse_root_args,
)

GREP_NAME: Final[str] = "agnosticism-grep"
RULE_ANCHOR: Final[str] = (
    "rules/agnostic-posture.md §3 (harness neutrality) + §1 (default-off)"
)

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# The four shipped-surface directories, relative to the repository root.
# A candidate Markdown file is in scope iff its POSIX-normalized relative
# path begins with one of these prefixes.
_SCOPE_PREFIXES: Final[tuple[str, ...]] = (
    "src/apothem/rules/",
    "src/apothem/commands/",
    "src/apothem/output-styles/",
    "src/apothem/statuslines/",
)
# Enforcement-preset scope. The shipped surfaces that carry an end-user-facing
# YAML frontmatter where a model/effort preset would impose a preference: the
# slash-commands, the skill definitions, and the agent definitions. The bias
# scan keeps its own (``_SCOPE_PREFIXES``) reach; the preset scan reaches all
# three so a re-introduced ``effort:`` / ``model:`` key is caught wherever a
# definition declares one.
_PRESET_PREFIXES: Final[tuple[str, ...]] = (
    "src/apothem/commands/",
    "src/apothem/skills/",
    "src/apothem/agents/",
)

# Per-folder agent-companion files are agnostic shipped surfaces too: every
# AGENTS.md must privilege no single harness. They are swept for harness bias
# wherever they live in the tree. The rendered harness-output template fixture
# under a `templates/` leaf is NOT a companion — it is materialized output.
_COMPANION_BASENAME: Final[str] = "AGENTS.md"
_TEMPLATE_LEAF_FRAGMENT: Final[str] = "/templates/"

# Harness-bias forms. ``Claude Code`` (the brand phrase) and the branded
# model names privilege one harness; the slug ``claude_code`` is the
# neutral catalog identifier and is matched separately as the exemption
# signal. Whitespace between the two words is flexible so a line-wrapped
# brand phrase is still caught.
_BIAS_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\bClaude\s+(?:Code|Opus|Sonnet|Haiku)\b"
)

# A line carrying the canonical slug is a per-harness catalog row (one
# entry among the registered harnesses) and is exempt from the
# bias scan — the slug is the neutral identifier the agnostic posture
# permits.
_CATALOG_SLUG: Final[str] = "claude_code"

# Enforcement-preset frontmatter keys. A shipped command that pre-sets one
# of these imposes a preference the end user is meant to supply.
_PRESET_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^(effort|model):\s*\S")

# Fenced code block delimiter — a line beginning with ``` at column 0.
_CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^```")

# YAML frontmatter delimiter — a line that is exactly ``---``.
_FRONTMATTER_DELIM: Final[str] = "---"

_MARKDOWN_SUFFIX: Final[str] = ".md"


@dataclass(frozen=True)
class Finding:
    """One agnosticism violation discovered in a shipped surface."""

    path: str
    line: int
    match: str
    context: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result for a single corpus sweep."""

    grep: str
    root: str
    scanned_count: int
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, scanned_count,
        passed, findings}``; each finding is flattened through
        ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "scanned_count": self.scanned_count,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _relative_posix(path: Path, root: Path) -> str | None:
    """Return ``path`` relative to ``root`` in POSIX form, or None."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _in_scope(rel_posix: str) -> bool:
    """Return True iff a relative path is a shipped-surface Markdown file.

    Two surface classes are in scope: the four prose-surface directories
    (rules / commands / output-styles / statuslines) and every per-folder
    agent-companion file (``AGENTS.md``) wherever it lives — the companions
    are agnostic shipped surfaces per the per-folder-AGENTS.md convention. A
    rendered harness-output template fixture under a ``templates/`` leaf is
    materialized output, not a companion, and is excluded.
    """
    if "/" in rel_posix and rel_posix.rsplit("/", 1)[-1] == _COMPANION_BASENAME:
        return _TEMPLATE_LEAF_FRAGMENT not in rel_posix
    if not rel_posix.endswith(_MARKDOWN_SUFFIX):
        return False
    return rel_posix.startswith(_SCOPE_PREFIXES)


def _scan_bias(rel_posix: str, content: str) -> list[Finding]:
    """Flag privileging harness-brand phrases outside fenced code blocks.

    A line carrying the canonical slug ``claude_code`` is a per-harness
    catalog row and is exempt.
    """
    findings: list[Finding] = []
    # ``iter_prose_lines`` walks the fence-toggle loop; a fenced example is not
    # shipped prose. No inline-code blanking here — the bias scan reads raw
    # lines, and the ``_CATALOG_SLUG`` exemption stays per-line below. The
    # column-0 fence form is preserved.
    for line_index, line, _scanned in iter_prose_lines(
        content.splitlines(), fence_re=_CODE_FENCE_RE
    ):
        if _CATALOG_SLUG in line.lower():
            continue
        for match in _BIAS_RE.finditer(line):
            findings.append(
                Finding(
                    path=rel_posix,
                    line=line_index,
                    match=match.group(),
                    context=line.strip(),
                    detail=(
                        "harness-bias: privileging brand reference in a shipped "
                        "surface — name the harness by its slug (claude_code) as "
                        "one catalog entry among the registered harnesses, or genericize to "
                        "'the harness'"
                    ),
                )
            )
    return findings


def _scan_enforcement_preset(rel_posix: str, content: str) -> list[Finding]:
    """Flag a re-introduced ``effort:`` / ``model:`` frontmatter preset.

    Scans only the leading YAML frontmatter block (delimited by a pair of
    ``---`` lines) of a command / skill / agent definition. Pre-setting
    effort or model imposes a preference the end user is meant to supply in
    conversation.
    """
    if not rel_posix.startswith(_PRESET_PREFIXES):
        return []
    lines = content.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        return []
    findings: list[Finding] = []
    for line_index, line in enumerate(lines[1:], start=2):
        if line.strip() == _FRONTMATTER_DELIM:
            break
        if _PRESET_KEY_RE.match(line):
            findings.append(
                Finding(
                    path=rel_posix,
                    line=line_index,
                    match=line.strip(),
                    context=line.strip(),
                    detail=(
                        "enforcement-preset: shipped surface pre-sets a "
                        "model/effort preference — strip the frontmatter key so "
                        "the preference resolves only from an in-conversation "
                        "end-user choice"
                    ),
                )
            )
    return findings


def _scan_file(path: Path, rel_posix: str) -> list[Finding]:
    """Scan one Markdown file for the applicable finding classes.

    The bias scan applies only to the four prose surfaces and the AGENTS.md
    companions (``_in_scope``); the enforcement-preset scan additionally
    reaches the skill and agent definitions (``_PRESET_PREFIXES``), so the
    two classes are gated independently.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    findings: list[Finding] = []
    if _in_scope(rel_posix):
        findings.extend(_scan_bias(rel_posix, content))
    findings.extend(_scan_enforcement_preset(rel_posix, content))
    return findings


def check(root: Path) -> GrepResult:
    """Walk the shipped surfaces under ``root``; flag agnosticism violations.

    Pre-conditions: ``root`` is the repository root (or an arbitrary subtree
    containing ``src/apothem/{rules,commands,output-styles,statuslines}/``).
    Post-conditions: ``result.passed`` is True iff every in-scope shipped
    surface is free of privileging harness-brand references (outside fenced
    code) and re-introduced enforcement presets.
    """
    findings: list[Finding] = []
    scanned = 0
    for path in sorted(root.rglob(f"*{_MARKDOWN_SUFFIX}")):
        if not path.is_file():
            continue
        rel_posix = _relative_posix(path, root)
        if rel_posix is None:
            continue
        if not (_in_scope(rel_posix) or rel_posix.startswith(_PRESET_PREFIXES)):
            continue
        scanned += 1
        findings.extend(_scan_file(path, rel_posix))
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        scanned_count=scanned,
        passed=not findings,
        findings=findings,
    )


def _main(argv: list[str]) -> int:
    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    result = check(root)
    return finish_root_report(
        result.to_json(), passed=result.passed, inspected=result.scanned_count
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
