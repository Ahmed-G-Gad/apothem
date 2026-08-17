# SPDX-License-Identifier: MIT

"""Detect secrets, PII tokens, and host-specific absolute paths.

Why this scan exists. Three risks live in the same scan because they
share the same enforcement surface (a pre-commit / pre-emission gate).
A leaked secret is a credential breach. A PII token embedded in
narrative violates the canonical-contact allow-list and may expose
contact data outside the operator's intent. An absolute path naming the
operator's home directory or username binds the artifact to a single
machine and breaks portability across operator hosts.

What this scan covers per finding.

- **Secret patterns.** API keys (AWS / GitHub / Stripe / Slack / generic
  PEM blocks / OpenAI / Anthropic). Pattern set is curated per
  upstream-vendor token shapes; any literal occurrence is HIGH severity.
- **PII tokens.** Email addresses (``_EMAIL_RE``). Banner-allowed
  contacts (the canonical email constant) are exempt.
- **Absolute home paths.** ``/Users/<name>/`` (macOS), ``/home/<name>/``
  (Linux), ``C:\\\\Users\\\\<name>\\\\`` (Windows). The operator's
  username is the hard-coded ``BANNER_USERNAME`` constant, used as the
  comparison anchor; non-operator usernames in test fixtures are also
  flagged separately because they bind the artifact to that specific
  test scenario.

Scope. All three scans (secrets, PII, paths) are restricted to the
narrative artifact classes (``NARRATIVE_CLASSES``); non-narrative
records are not scanned.
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
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    Hit,
    emit_json,
    load_inventory,
    read_text_safely,
)

# The canonical banner email is allow-listed for PII detection: a match
# on this exact address is the operator's own disclosure surface, not a
# leaked contact. Any other email token is still flagged for review.
BANNER_EMAIL: Final[str] = "me@ahmedgad.com"
# The operator's home-directory username, the comparison anchor that
# splits operator- from non-operator-home paths in the path scan.
BANNER_USERNAME: Final[str] = "Gad"

# Secret-pattern catalog. Each entry is a (label, regex) pair. The
# regexes are intentionally narrow to limit false positives; broader
# scanning is the gitleaks pre-commit hook's job at the hook-install
# pass.
_SECRET_PATTERNS: Final[list[tuple[str, re.Pattern[str]]]] = [
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws-secret-access-key", re.compile(r"\b[A-Za-z0-9/+=]{40}\b(?=.{0,80}aws)")),
    ("github-pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b")),
    ("anthropic-api-key", re.compile(r"\bsk-ant-[A-Za-z0-9-_]{30,}\b")),
    ("openai-api-key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe-key", re.compile(r"\b(?:sk|pk)_(?:test|live)_[0-9a-zA-Z]{24,}\b")),
    (
        "private-key-block",
        re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY-----"),
    ),
    (
        "generic-bearer-token",
        re.compile(
            r"\b(?:bearer|token|api[_-]?key|secret)\s*[:=]\s*[\"']?[A-Za-z0-9_-]{24,}[\"']?",
            re.IGNORECASE,
        ),
    ),
]

# Absolute-path patterns. The operator's actual username is interpolated
# at scan time so non-operator usernames in test fixtures show up as a
# distinct (lower-severity) class.
_PATH_USERS_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w/])(?:/Users/|/home/|[A-Z]:[\\/]Users[\\/])(?P<user>[A-Za-z0-9._-]+)[/\\]"
)

# Email pattern matching anywhere; the BANNER_EMAIL is allow-listed.
_EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


def _scan_secrets(rel: str, content: str) -> list[Hit]:
    """Walk content for secret-pattern matches."""
    hits: list[Hit] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        for label, pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                hits.append(
                    Hit(
                        file=rel,
                        line=lineno,
                        signal=f"secret-candidate: {label}",
                        severity=SEVERITY_HIGH,
                        remediation=(
                            "Treat as a credential leak: rotate the secret"
                            " upstream, remove the literal from the working"
                            " tree, and verify git-history removal before"
                            " any push to a remote."
                        ),
                    )
                )
                break  # one finding per line is enough
    return hits


def _scan_pii(rel: str, content: str) -> list[Hit]:
    """Walk content for non-banner email occurrences."""
    hits: list[Hit] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        for match in _EMAIL_RE.finditer(line):
            email = match.group(0)
            if email == BANNER_EMAIL:
                continue
            hits.append(
                Hit(
                    file=rel,
                    line=lineno,
                    signal=f"non-banner-email: {email}",
                    severity=SEVERITY_MEDIUM,
                    remediation=(
                        "Replace with a vendor-neutral placeholder"
                        " (example.com), the canonical banner email, or"
                        " remove the contact data if not load-bearing."
                    ),
                )
            )
    return hits


def _scan_paths(rel: str, content: str) -> list[Hit]:
    """Walk content for absolute home-directory paths."""
    hits: list[Hit] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        for match in _PATH_USERS_RE.finditer(line):
            user = match.group("user")
            severity = SEVERITY_MEDIUM if user == BANNER_USERNAME else SEVERITY_LOW
            sig_kind = (
                "operator-home-path"
                if user == BANNER_USERNAME
                else "non-operator-home-path"
            )
            hits.append(
                Hit(
                    file=rel,
                    line=lineno,
                    signal=f"{sig_kind}: {match.group(0)}",
                    severity=severity,
                    remediation=(
                        "Replace the absolute path with a portable form"
                        " (~/, $HOME, %USERPROFILE%, or the host-discovered"
                        " environment variable that names the home root)."
                    ),
                )
            )
    return hits


def _scan_record(record: dict[str, Any], root: Path) -> list[Hit]:
    """Run all three scans against one inventory record.

    All three scans (secrets, PII, paths) are restricted to narrative
    classes. Memory JSONL session logs and plan-artifact files bind
    per-machine state by design — flagging them as portability concerns
    would generate noise that obscures the real findings in narrative
    artifacts that DO get shared across hosts.
    """
    cls = record.get("class", "")
    if cls not in NARRATIVE_CLASSES:
        return []
    rel = record["path"]
    path = root / rel
    content = read_text_safely(path)
    if not content:
        return []
    hits: list[Hit] = []
    hits.extend(_scan_secrets(rel, content))
    hits.extend(_scan_pii(rel, content))
    hits.extend(_scan_paths(rel, content))
    return hits


def main(argv: list[str] | None = None) -> int:
    """Scan narrative surfaces for secrets, PII, and host-absolute paths and write ``drift-secrets-pii.json``.

    Loads the inventory, runs the secret-pattern, non-banner-email, and
    home-path scans across each narrative record, emits the envelope, and
    prints a per-signal summary.
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
        default=Path(".audit/drift-secrets-pii.json"),
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
    emit_json(args.output, "scan_secrets_pii", hits, sha)
    by_signal: dict[str, int] = {}
    for h in hits:
        kind = h.signal.split(":", 1)[0]
        by_signal[kind] = by_signal.get(kind, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_signal.items()))
    print(f"scan_secrets_pii: {len(hits)} hit(s) [{summary or 'none'}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
