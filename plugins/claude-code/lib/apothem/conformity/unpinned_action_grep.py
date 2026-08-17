# SPDX-License-Identifier: MIT

"""Flag GitHub Actions workflows that pin actions to mutable refs.

Why this enforcement exists. The production-ready discipline M15 + the
supply-chain posture preservation clause require third-party action
references to be pinned to a 40-character commit SHA rather than a
floating tag. A `uses: actions/checkout@v4` reference can silently
re-point to a malicious release; a `uses: actions/checkout@<40-char-sha>`
reference cannot. The pre-emission gate's mechanical bar 15 (M15 supply-chain) catches the
mutable-ref shapes (`@main`, `@master`, `@latest`, `@v1`, `@v1.x.y`,
`@<branch>`) and surfaces each occurrence so the operator pins to a
SHA in the same change-set.

Detection strategy. The grep parses every line beginning with
`uses: <owner>/<action>@<ref>` (whitespace-tolerant) and inspects the
`<ref>`. A 40-character lowercase-hex SHA is the only conformant form;
anything else is flagged with the parsed action name and the offending
ref so the operator can rewrite to the SHA pin.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

# `uses: <owner>/<action>(/<sub>)*@<ref>` shape per the GitHub Actions
# workflow YAML specification. The optional sub-path matches actions like
# `actions/cache/save@v3`. The capture groups isolate the action name and
# the ref so the finding can name both. A trailing `# ...` comment is
# tolerated so inline exemption markers (see `EXEMPTION_RE`) sit on the
# same line as the declaration without causing the regex to miss-match.
USES_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*-?\s*uses:\s*([\w./-]+)@([\w./+-]+)\s*(?:#.*)?$"
)

# Canonical SHA shape — exactly forty lowercase hex characters. No upper-
# case, no shorter prefixes (those are abbreviations, not pins).
COMMIT_SHA_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")

# Inline exemption marker. A `uses:` line carrying a trailing comment of
# the form `# action-pinning-exempt: <reason>` is exempt from the SHA-pin
# requirement. The reason is required (audit-trail discipline) — bare
# `# action-pinning-exempt` without a reason is not honored. Canonical
# use case: SLSA reusable-workflow references where the Sigstore policy
# forbids SHA-pinning and the `@<tag>` form is the trust anchor rather
# than a mutable ref.
EXEMPTION_RE: Final[re.Pattern[str]] = re.compile(r"#\s*action-pinning-exempt:\s*\S")

# Local-action references (path within the same repository) start with
# `./` and are out of scope — they're not third-party supply-chain risks.
LOCAL_ACTION_PREFIX: Final[str] = "./"

GREP_NAME: Final[str] = "unpinned-action-grep"
RULE_ANCHOR: Final[str] = "M15 production-ready §Supply-chain"


@dataclass(frozen=True)
class Finding:
    """One unpinned-action occurrence."""

    line: int
    action: str
    ref: str
    rule: str = RULE_ANCHOR


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan content; return a structured result.

    Pre-conditions: `content` is the YAML body of a workflow file about
    to be emitted. The grep accepts content from any source — the
    operator points it at a single workflow file or pipes a multi-file
    bundle via stdin.
    Post-conditions: `result.passed` is True iff every `uses: <action>@<ref>`
    declaration's ref is a 40-character commit SHA, or the action is a
    local in-repo reference exempt from supply-chain pinning.
    """
    findings: list[Finding] = []
    for line_index, line in enumerate(content.splitlines(), start=1):
        match = USES_LINE_RE.match(line)
        if match is None:
            continue
        action, ref = match.group(1), match.group(2)
        if action.startswith(LOCAL_ACTION_PREFIX):
            continue
        if COMMIT_SHA_RE.match(ref) is not None:
            continue
        if EXEMPTION_RE.search(line) is not None:
            continue
        findings.append(
            Finding(
                line=line_index,
                action=action,
                ref=ref,
            )
        )
    return GrepResult(
        grep=GREP_NAME,
        path=str(path) if path is not None else None,
        passed=not findings,
        findings=findings,
    )


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
