# SPDX-License-Identifier: MIT

"""Block emission of artifacts containing hardcoded credentials.

Why this enforcement exists. The production-ready discipline M15 + the
code-craft security sub-discipline M13.8 both forbid hardcoded secrets in
source. A leaked AWS access key, GitHub token, JWT, or RSA private key
costs hours of credential rotation and may produce a real-world breach.
The pre-emission gate's mechanical bar 15 (M15 supply-chain) catches the literal patterns
distinctive enough that false-positive rate is acceptable while
true-positive coverage is high. The patterns curated below are the
common vendor-issued credential prefixes plus a generic high-entropy
fallback.

Detection strategy. The grep applies a list of named patterns each
tagged with the credential class. A hit on any pattern produces a
finding with the line, the redacted match (first eight characters
plus ellipsis to avoid re-leaking the secret in the report), and the
class label. Fenced code blocks are NOT excluded — secrets pasted
into a code block are still secrets in source control. The
canonical-banner allow-list now lives here (merged from the retired
secret-scan matcher): lines carrying a verbatim authorship-banner
identifier are exempted from both the pattern and entropy checks.
"""

from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep


@dataclass(frozen=True)
class SecretPattern:
    """One named credential-class regex with its display label."""

    label: str
    pattern: re.Pattern[str]


# Curated credential-class patterns. Each label names the issuer or class
# so the operator can route the rotation. Patterns are anchored on the
# distinctive vendor prefix where one exists; the entropy heuristic catches
# the rest.
SECRET_PATTERNS: Final[tuple[SecretPattern, ...]] = (
    SecretPattern("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    SecretPattern(
        "GitHub personal access token", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")
    ),
    SecretPattern("GitHub OAuth access token", re.compile(r"\bgho_[A-Za-z0-9]{36}\b")),
    SecretPattern(
        "GitHub server-to-server token", re.compile(r"\bghs_[A-Za-z0-9]{36}\b")
    ),
    SecretPattern(
        "GitHub app/refresh token",
        re.compile(r"\b(?:ghu|ghr)_[A-Za-z0-9]{36}\b"),
    ),
    SecretPattern("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    SecretPattern("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    SecretPattern(
        "JWT (JSON Web Token)",
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    ),
    SecretPattern(
        "RSA private key header",
        re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----"),
    ),
    SecretPattern("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
)

# Canonical-banner identifiers. Lines containing any of these substrings
# are exempted from secret findings (both pattern and entropy checks)
# because the banner is a verbatim authorship surface, not a credential.
# Merged from the retired secret-scan matcher.
BANNER_ALLOW_LIST: Final[tuple[str, ...]] = (
    "ahmedgad.com",
    "me@ahmedgad.com",
    "github.com/ahmed-g-gad",
    "Ahmed G. Gad",
    "@ahmed-g-gad",
)

# Vendor-published documentation placeholders. AWS documents this access-key
# id and secret access key as the example values for its credential formats
# (IAM user guide, "Manage access keys"); they grant nothing, and docs or code
# samples quote them verbatim. Only an exact match is exempt: the rest of the
# line is still scanned, and any other key — including one that merely
# resembles a placeholder — is still reported.
DOCUMENTATION_EXAMPLE_CREDENTIALS: Final[frozenset[str]] = frozenset(
    {
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    }
)

# Generic high-entropy heuristic. A standalone alphanumeric token of this
# minimum length whose Shannon entropy exceeds the threshold is suspect.
# These thresholds favor precision over recall — common identifier shapes
# (kebab-case names, hex-coded constants) sit well below the entropy bar.
ENTROPY_TOKEN_MIN_LENGTH: Final[int] = 32
ENTROPY_BITS_PER_CHAR_THRESHOLD: Final[float] = 4.5
ENTROPY_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"\b[A-Za-z0-9_+/=-]{32,}\b")

# How many leading characters to keep when redacting the matched value
# in the finding report. Leaking the full secret in the audit log defeats
# the grep's purpose.
REDACT_PREFIX_LENGTH: Final[int] = 8

GREP_NAME: Final[str] = "secret-leak-grep"
RULE_ANCHOR: Final[str] = "M13.8 security + M15 production-ready"


@dataclass(frozen=True)
class Finding:
    """One credential-leak occurrence."""

    line: int
    label: str
    redacted_match: str
    rule: str = RULE_ANCHOR


def _line_in_banner(line: str) -> bool:
    """True iff the line carries a canonical-banner identifier."""
    return any(token in line for token in BANNER_ALLOW_LIST)


def _redact(value: str) -> str:
    """Show the first few characters; mask the rest."""
    if len(value) <= REDACT_PREFIX_LENGTH:
        return "***"
    return f"{value[:REDACT_PREFIX_LENGTH]}…(redacted, {len(value)} chars)"


def _shannon_entropy_bits_per_char(value: str) -> float:
    """Compute Shannon entropy in bits per character."""
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    total = len(value)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan content; return a structured result.

    Pre-conditions: `content` is the artifact body about to be emitted.
    Post-conditions: `result.passed` is True iff zero credential patterns
    matched and no high-entropy token exceeded the heuristic threshold. A
    match that is exactly a vendor-published documentation placeholder
    (:data:`DOCUMENTATION_EXAMPLE_CREDENTIALS`) is not a finding.
    """
    findings: list[Finding] = []
    lines = content.splitlines()
    for line_index, line in enumerate(lines, start=1):
        # Canonical-banner allow-list: a line carrying a verbatim
        # authorship-banner identifier is exempted from both the pattern
        # and entropy checks (merged from the retired secret-scan matcher).
        if _line_in_banner(line):
            continue
        named_hit = False
        for secret in SECRET_PATTERNS:
            for match in secret.pattern.finditer(line):
                if match.group() in DOCUMENTATION_EXAMPLE_CREDENTIALS:
                    continue
                named_hit = True
                findings.append(
                    Finding(
                        line=line_index,
                        label=secret.label,
                        redacted_match=_redact(match.group()),
                    )
                )
        # Generic high-entropy fallback. Skip lines already covered by a
        # named pattern to avoid double-reporting the same token.
        if named_hit:
            continue
        for match in ENTROPY_TOKEN_RE.finditer(line):
            token = match.group()
            if token in DOCUMENTATION_EXAMPLE_CREDENTIALS:
                continue
            entropy = _shannon_entropy_bits_per_char(token)
            if entropy >= ENTROPY_BITS_PER_CHAR_THRESHOLD:
                findings.append(
                    Finding(
                        line=line_index,
                        label=(
                            f"high-entropy token "
                            f"({entropy:.2f} bits/char ≥ "
                            f"{ENTROPY_BITS_PER_CHAR_THRESHOLD})"
                        ),
                        redacted_match=_redact(token),
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
