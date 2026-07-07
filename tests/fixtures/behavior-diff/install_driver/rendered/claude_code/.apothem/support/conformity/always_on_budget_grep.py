# SPDX-License-Identifier: MIT

"""always-on-budget-grep: token-budget conformity matcher for always-on rules.

Why this enforcement exists. Always-on rules load into every session's
context as standing directives; aggregate body length is a multiplier on
every turn's cost. The token-budget-discipline rule caps each always-on
body at MAX_SUBSTANTIVE_TOKENS substantive tokens, with a pre-emptive
warn-band at WARN_BAND_THRESHOLD nudging authors to plan a path-filtered
companion sub-rule before the hard ceiling triggers. Bodies above the
ceiling are decomposed into the demand-load companion-sub-rule pattern
ratified at rules/context-management.md and its companion
rules/context-management-scratch.md.

Substantive-token counter. The count is a whitespace-separated token
count over the rule body with three regions excluded:

  1. YAML frontmatter — content between the opening `---` and the second
     `---` delimiters at file head. Frontmatter declares the rule's
     classification, not its directive content.
  2. The trailing `## Bindings (§0.j five-direction)` section — bindings
     are pointers to peer artifacts, not standing directives. They
     consume context but do not raise body-content load.
  3. Companion-sub-rule pointer lines — any line containing the literal
     string `(Companion Sub-Rule Anchor)`. The pointer line names a
     demand-load surface; the surface itself loads on path-filter match
     and counts against its own (path-filtered) sibling rule, not the
     parent always-on body.

Verdict matrix.
  pass — the rule is not always-on (alwaysApply false OR pathFilter
         non-empty), or the substantive-token count is at or below the
         MAX_SUBSTANTIVE_TOKENS ceiling. WARN_BAND_THRESHOLD-MAX
         counts produce an advisory in the finding payload but still
         pass the gate.
  FAIL — the substantive-token count exceeds MAX_SUBSTANTIVE_TOKENS;
         the rule must be decomposed into a path-filtered companion
         sub-rule with the parent body retaining only load-bearing
         anchors plus the `(Companion Sub-Rule Anchor)` pointer.

Invocation. The matcher accepts either a single rule path on argv, a
directory (recurses over `*.md`), or `--stdin` reading the
rule body. When invoked with no path, defaults to scanning `rules/`
relative to the current working directory.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------

GREP_NAME: Final[str] = "always-on-budget-grep"
RULE_ANCHOR: Final[str] = "D1 token-budget-discipline §Always-on body budget"
EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2
STDIN_FLAG: Final[str] = "--stdin"

# ---------------------------------------------------------------------------
# Budget constants
# ---------------------------------------------------------------------------

MAX_SUBSTANTIVE_TOKENS: Final[int] = 500
WARN_BAND_THRESHOLD: Final[int] = 450

# ---------------------------------------------------------------------------
# Region-exclusion markers
# ---------------------------------------------------------------------------

FRONTMATTER_DELIM: Final[str] = "---"
BINDINGS_HEADING_PREFIX: Final[str] = "## Bindings"
COMPANION_POINTER: Final[str] = "(Companion Sub-Rule Anchor)"
RULE_GLOB: Final[str] = "*.md"
DEFAULT_SCAN_DIR: Final[str] = "rules"


@dataclass(frozen=True)
class Finding:
    """One per-rule budget verdict."""

    path: str
    always_on: bool
    substantive_tokens: int
    over_budget: bool
    warn_band: bool
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result for a single always-on-budget sweep."""

    grep: str
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        payload = {
            "grep": self.grep,
            "passed": self.passed,
            "max-substantive-tokens": MAX_SUBSTANTIVE_TOKENS,
            "warn-band-threshold": WARN_BAND_THRESHOLD,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Split frontmatter from body.

    Args:
        content: full rule file content.

    Returns:
        Tuple of (frontmatter mapping, body text). Frontmatter values are
        stripped of surrounding quotes; missing keys yield an empty
        mapping. When no frontmatter is present, returns ({}, content).

    The parser tolerates a leading authorship-header banner (HTML comment
    block on Markdown rules) preceding the frontmatter — it locates the
    first `---` delimiter line that opens a YAML block whose immediate
    content lines look like `key: value` pairs.
    """
    lines = content.splitlines()
    start_index = -1
    for i, line in enumerate(lines):
        if line.strip() == FRONTMATTER_DELIM:
            start_index = i
            break
    if start_index == -1:
        return {}, content
    end_index = -1
    for i in range(start_index + 1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIM:
            end_index = i
            break
    if end_index == -1:
        return {}, content
    fm: dict[str, str] = {}
    for raw in lines[start_index + 1 : end_index]:
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        fm[key.strip()] = value.strip().strip('"').strip("'")
    body = "\n".join(lines[end_index + 1 :])
    return fm, body


def is_always_on(frontmatter: dict[str, str]) -> bool:
    """Classify a rule as always-on per its frontmatter.

    A rule is always-on iff `alwaysApply` is the literal string `true`
    AND `pathFilter` is empty (absent or whitespace-only). Path-filtered
    rules demand-load on glob match and are exempt from the body budget.
    """
    apply_value = frontmatter.get("alwaysApply", "").lower()
    path_filter = frontmatter.get("pathFilter", "").strip()
    return apply_value == "true" and path_filter == ""


def strip_bindings_section(body: str) -> str:
    """Remove the trailing `## Bindings (§0.j five-direction)` section.

    Bindings are reciprocal pointers to peer artifacts, not standing
    directives; they are excluded from the substantive token count per
    the rule's exclusion list.
    """
    lines = body.splitlines()
    cut = -1
    for i, line in enumerate(lines):
        if line.lstrip().startswith(BINDINGS_HEADING_PREFIX):
            cut = i
            break
    if cut == -1:
        return body
    return "\n".join(lines[:cut])


def strip_companion_pointers(body: str) -> str:
    """Remove every line containing the companion-sub-rule pointer.

    The pointer line names a demand-load surface; the surface itself is
    weighed against its own path-filtered sibling rule, not the parent
    always-on body.
    """
    return "\n".join(
        line for line in body.splitlines() if COMPANION_POINTER not in line
    )


def count_substantive_tokens(body: str) -> int:
    """Count whitespace-separated tokens in the post-exclusion body.

    The count is reproducible and platform-stable; markdown markers are
    counted as tokens because they consume context just as words do.
    """
    return len(body.split())


def measure(content: str) -> tuple[bool, int]:
    """Measure the always-on classification and the substantive token count.

    Returns:
        Tuple of (always_on, substantive_token_count). When the rule is
        not always-on, the count is still reported for transparency but
        the verdict is always pass.
    """
    frontmatter, body = parse_frontmatter(content)
    always_on = is_always_on(frontmatter)
    body_no_bindings = strip_bindings_section(body)
    body_no_pointers = strip_companion_pointers(body_no_bindings)
    return always_on, count_substantive_tokens(body_no_pointers)


def check_file(path: Path) -> Finding:
    """Apply the matcher to a single rule file."""
    content = path.read_text(encoding="utf-8")
    always_on, tokens = measure(content)
    over = always_on and tokens > MAX_SUBSTANTIVE_TOKENS
    warn = always_on and (not over) and tokens >= WARN_BAND_THRESHOLD
    return Finding(
        path=str(path),
        always_on=always_on,
        substantive_tokens=tokens,
        over_budget=over,
        warn_band=warn,
    )


def check(content: str, path: Path | None = None) -> GrepResult:
    """Per-Write dispatch entry consumed by `conformity/gate.py`.

    Measures one rule body's substantive-token count. The orchestrator
    invokes this on every Write/Edit; non-rule paths and non-always-on
    rules pass without a finding.

    Pre-conditions: `content` is the artifact about to be emitted; `path`
    is the target file path or None.
    Post-conditions: `result.passed` is True iff the artifact is not an
    over-budget always-on rule body.
    """
    path_str = str(path) if path is not None else "<stdin>"
    if path is not None and not path_str.endswith(".md"):
        return GrepResult(grep=GREP_NAME, passed=True, findings=[])
    always_on, tokens = measure(content)
    over = always_on and tokens > MAX_SUBSTANTIVE_TOKENS
    warn = always_on and (not over) and tokens >= WARN_BAND_THRESHOLD
    finding = Finding(
        path=path_str,
        always_on=always_on,
        substantive_tokens=tokens,
        over_budget=over,
        warn_band=warn,
    )
    if not over:
        return GrepResult(grep=GREP_NAME, passed=True, findings=[])
    return GrepResult(grep=GREP_NAME, passed=False, findings=[finding])


def discover_rule_files(target: Path) -> list[Path]:
    """Resolve a target into the rule files to inspect."""
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(target.rglob(RULE_GLOB))
    raise FileNotFoundError(f"target does not exist: {target}")


def _read_stdin_finding() -> Finding:
    content = sys.stdin.read()
    always_on, tokens = measure(content)
    over = always_on and tokens > MAX_SUBSTANTIVE_TOKENS
    warn = always_on and (not over) and tokens >= WARN_BAND_THRESHOLD
    return Finding(
        path="<stdin>",
        always_on=always_on,
        substantive_tokens=tokens,
        over_budget=over,
        warn_band=warn,
    )


def _resolve_target(argv: list[str]) -> Path:
    if len(argv) >= 2:
        return Path(argv[1])
    return Path(DEFAULT_SCAN_DIR)


def _main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == STDIN_FLAG:
        finding = _read_stdin_finding()
        result = GrepResult(
            grep=GREP_NAME,
            passed=not finding.over_budget,
            findings=[finding],
        )
        print(result.to_json())
        return EXIT_PASS if result.passed else EXIT_FAIL

    target = _resolve_target(argv)
    paths = discover_rule_files(target)
    findings = [check_file(p) for p in paths]
    failed = [f for f in findings if f.over_budget]
    result = GrepResult(
        grep=GREP_NAME,
        passed=not failed,
        findings=findings,
    )
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
