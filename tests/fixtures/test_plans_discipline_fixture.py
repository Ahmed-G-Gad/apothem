# SPDX-License-Identifier: MIT

"""Self-test for the byte-exact Plans Discipline directive fixture.

The fixture at ``tests/fixtures/plans-discipline.txt`` is the canonical
byte-exact form the ``plans-discipline-language`` validator matches against
the Plans Discipline directive in AGENTS.md, CLAUDE.md, the default
output-style, and ``.github/copilot-instructions.md``. Drift in the fixture content corrupts
the validator's narrative-presence check, so the directive is locked here
by exact-string match plus SHA-256 anchor.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
FIXTURE_PATH: Final[Path] = REPO_ROOT / "tests" / "fixtures" / "plans-discipline.txt"
CHECKSUM_LEDGER: Final[Path] = REPO_ROOT / ".audit" / "fixture-checksums.txt"

# Canonical directive — byte-exact form per spec §3.6 (1). The sole canonical
# plans home is `<project-root>/.apothem/plans/`; a legacy
# `<project-root>/.plans/` tree is upgraded via `apothem migrate-workspace`.
EXPECTED_DIRECTIVE: Final[str] = (
    "Planning artifacts are written to <project-root>/.apothem/plans/, never to "
    "any harness configuration directory (for example ~/.codex/ or ~/.claude/) "
    "and never to a global location. This rule is non-negotiable; "
    "cite §3 of the project spec on every related decision."
)

# SHA-256 anchor — locked at fixture authoring time. Update alongside
# any deliberate edit to EXPECTED_DIRECTIVE.
EXPECTED_SHA256: Final[str] = (
    "5e26e193975fdac7cfc1fe1630ad2d6df36c8242f72a7b9e6f040f0181ebf0e1"
)


def test_fixture_exists_and_is_non_empty() -> None:
    """The fixture file is present and carries non-empty content."""
    assert FIXTURE_PATH.is_file(), f"missing fixture: {FIXTURE_PATH}"
    raw = FIXTURE_PATH.read_bytes()
    assert raw, "fixture is empty"


def test_fixture_holds_canonical_directive_as_sole_content() -> None:
    """The directive is the file's sole content (single trailing newline only)."""
    content = FIXTURE_PATH.read_text(encoding="utf-8")
    # Allow exactly one trailing newline; anything else is surrounding text.
    assert content == EXPECTED_DIRECTIVE + "\n", (
        "fixture content diverges from the canonical Plans Discipline "
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
        # The audit ledger is gitignored working evidence; absence is
        # routine in fresh checkouts and CI environments.
        return
    rel = "tests/fixtures/plans-discipline.txt"
    pattern = re.compile(rf"^([0-9a-f]{{64}})\s+{re.escape(rel)}\s*$", re.MULTILINE)
    text = CHECKSUM_LEDGER.read_text(encoding="utf-8")
    match = pattern.search(text)
    if match is None:
        # The ledger may be present but pre-Phase-04C; absence of the row
        # is not a self-test failure (Phase 04C.6 is the row's authoring
        # task).
        return
    digest = hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()
    assert match.group(1) == digest, (
        f"audit ledger SHA-256 diverges from fixture; "
        f"ledger={match.group(1)} fixture={digest}"
    )
