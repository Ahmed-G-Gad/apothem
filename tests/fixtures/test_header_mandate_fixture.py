# SPDX-License-Identifier: MIT

"""Self-test for the byte-exact Authorship Header directive fixture.

The fixture at ``tests/fixtures/header-mandate.txt`` is the canonical
byte-exact form the ``file-header`` validator matches against the
Authorship Header directive in CLAUDE.md and ``.github/copilot-instructions.md``.
Drift in the fixture content corrupts the validator's narrative-presence
check, so the directive is locked here by exact-string match plus SHA-256
anchor.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
FIXTURE_PATH: Final[Path] = REPO_ROOT / "tests" / "fixtures" / "header-mandate.txt"
CHECKSUM_LEDGER: Final[Path] = REPO_ROOT / ".audit" / "fixture-checksums.txt"

# Canonical directive — byte-exact form per spec §5.1.
EXPECTED_DIRECTIVE: Final[str] = (
    "Every new applicable file you create MUST begin with the canonical "
    "authorship-header banner per site/content/docs/reference/authorship-header.mdx. Use "
    "scripts/inject-header.* if available; otherwise emit the banner "
    "verbatim from the variant table at §4.6.2."
)

# SHA-256 anchor — locked at fixture authoring time. Update alongside
# any deliberate edit to EXPECTED_DIRECTIVE.
EXPECTED_SHA256: Final[str] = (
    "1e95fc737bdbd7e77f7b37b147140692c7e308378891fa4dbc1333b5bec703e9"
)


def test_fixture_exists_and_is_non_empty() -> None:
    """The fixture file is present and carries non-empty content."""
    assert FIXTURE_PATH.is_file(), f"missing fixture: {FIXTURE_PATH}"
    raw = FIXTURE_PATH.read_bytes()
    assert raw, "fixture is empty"


def test_fixture_holds_canonical_directive_as_sole_content() -> None:
    """The directive is the file's sole content (single trailing newline only)."""
    content = FIXTURE_PATH.read_text(encoding="utf-8")
    assert content == EXPECTED_DIRECTIVE + "\n", (
        "fixture content diverges from the canonical Authorship Header "
        "directive — surrounding text or whitespace detected"
    )


def test_fixture_sha256_matches_anchor() -> None:
    """The fixture's SHA-256 matches the in-test anchor."""
    # Normalize CRLF→LF so the check is platform-independent (Windows
    # git checkouts with core.autocrlf=true produce CRLF bytes on disk).
    content = FIXTURE_PATH.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(content).hexdigest()
    assert digest == EXPECTED_SHA256, (
        f"fixture SHA-256 drift; expected {EXPECTED_SHA256}, got {digest}"
    )


def test_checksum_ledger_records_match_when_present() -> None:
    """When the audit ledger exists, the recorded SHA-256 matches the fixture."""
    if not CHECKSUM_LEDGER.is_file():
        return
    rel = "tests/fixtures/header-mandate.txt"
    pattern = re.compile(rf"^([0-9a-f]{{64}})\s+{re.escape(rel)}\s*$", re.MULTILINE)
    text = CHECKSUM_LEDGER.read_text(encoding="utf-8")
    match = pattern.search(text)
    if match is None:
        return
    digest = hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()
    assert match.group(1) == digest, (
        f"audit ledger SHA-256 diverges from fixture; "
        f"ledger={match.group(1)} fixture={digest}"
    )
