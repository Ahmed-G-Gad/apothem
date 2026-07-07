# SPDX-License-Identifier: MIT

"""Verify the repo-root ``.gitattributes`` carries the canonical contract.

Why this validator exists. The supply-chain release contract requires
the repository to ship a ``.gitattributes`` file at its root that pins
line-ending normalisation (``* text=auto eol=lf``), declares binary
asset classes (``*.png binary``, ``*.jpg`` or ``*.jpeg`` ``binary``),
preserves SVG as text for diffability (``*.svg text``), and applies
``export-ignore`` to ephemeral / developer-only trees (``.plans/``,
``tests/``, ``.github/``) so source-archive consumers receive only
shippable content. Absence of any one of these contract elements is a
supply-chain drift class that this validator surfaces at the
pre-emission gate.

Detection strategy. Open ``<root>/.gitattributes``; tokenise on lines
(comments and blanks ignored); look for each required pattern via a
permissive whitespace-tolerant regex. Each missing element produces a
finding whose ``drift_class`` field names the violation. The validator
does NOT attempt to enforce ordering, repetition, or stylistic
consistency — only presence.

Exit semantics. Exits 0 (PASS) when every required contract element is
present; exits 2 (FAIL) on any drift class. The exit-2 convention
matches the conformity-gate orchestrator's ``EXIT_FAIL`` constant.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "gitattributes-presence-grep"
RULE_ANCHOR: Final[str] = "supply-chain .gitattributes contract"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

GITATTRIBUTES_FILENAME: Final[str] = ".gitattributes"

# Drift class identifiers — surface in findings so the operator can
# route each failure to its remediation path without re-parsing prose.
DRIFT_FILE_ABSENT: Final[str] = "file-absent"
DRIFT_MISSING_TEXT_EOL_BASELINE: Final[str] = "missing-text-eol-baseline"
DRIFT_MISSING_BINARY_DECLARATION: Final[str] = "missing-binary-declaration"
DRIFT_MISSING_EXPORT_IGNORE: Final[str] = "missing-export-ignore"

# Required-element regexes. Each pattern is whitespace-tolerant so the
# operator may freely align columns; none require a specific order.
# ``re.MULTILINE`` lets ``^`` match at line starts so commented-out
# variants (lines beginning with ``#``) are not matched.
_TEXT_EOL_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*\*\s+text=auto\s+eol=lf\b",
    re.MULTILINE,
)
_PNG_BINARY_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*\*\.png\s+binary\b",
    re.MULTILINE,
)
# Accept either ``*.jpg`` or ``*.jpeg`` as the JPEG declaration.
_JPG_BINARY_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*\*\.jpe?g\s+binary\b",
    re.MULTILINE,
)
_SVG_TEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*\*\.svg\s+text\b",
    re.MULTILINE,
)

# Export-ignore patterns. Accept both trailing-slash (``.plans/``) and
# bare-name (``.plans``) glob forms — git honours both.
_EXPORT_IGNORE_PATHS: Final[tuple[str, ...]] = (".plans", "tests", ".github")


def _export_ignore_re(path: str) -> re.Pattern[str]:
    """Compile a permissive export-ignore matcher for *path*.

    Accepts ``.plans/ export-ignore`` and ``.plans export-ignore`` forms,
    plus glob variants like ``.plans/** export-ignore``. The leading
    anchor is ``^`` under MULTILINE so commented lines do not match.
    """
    escaped = re.escape(path)
    return re.compile(
        rf"^\s*{escaped}(?:/\S*|/?)\s+export-ignore\b",
        re.MULTILINE,
    )


@dataclass(frozen=True)
class Finding:
    """One missing-contract-element occurrence."""

    drift_class: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    grep: str
    root: str
    path: str | None
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        payload = {
            "grep": self.grep,
            "root": self.root,
            "path": self.path,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def check(root: Path) -> GrepResult:
    """Inspect ``<root>/.gitattributes`` and return a structured verdict.

    Pre-conditions: *root* names a directory the operator wishes to
    audit (typically the repository root).
    Post-conditions: ``result.passed`` is True iff the file exists and
    contains every required contract element; otherwise ``findings``
    enumerates each drift class.
    """
    path = root / GITATTRIBUTES_FILENAME
    if not path.is_file():
        finding = Finding(
            drift_class=DRIFT_FILE_ABSENT,
            detail=(
                f"{GITATTRIBUTES_FILENAME} is absent at repository root "
                f"({path}); the supply-chain contract requires it"
            ),
        )
        return GrepResult(
            grep=GREP_NAME,
            root=str(root),
            path=str(path),
            passed=False,
            findings=[finding],
        )

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        finding = Finding(
            drift_class=DRIFT_FILE_ABSENT,
            detail=f"{GITATTRIBUTES_FILENAME} unreadable at {path}: {exc}",
        )
        return GrepResult(
            grep=GREP_NAME,
            root=str(root),
            path=str(path),
            passed=False,
            findings=[finding],
        )

    findings: list[Finding] = []

    if not _TEXT_EOL_RE.search(content):
        findings.append(
            Finding(
                drift_class=DRIFT_MISSING_TEXT_EOL_BASELINE,
                detail=(
                    "baseline `* text=auto eol=lf` declaration missing; "
                    "line-ending normalisation is unpinned"
                ),
            )
        )

    if not _PNG_BINARY_RE.search(content):
        findings.append(
            Finding(
                drift_class=DRIFT_MISSING_BINARY_DECLARATION,
                detail="`*.png binary` declaration missing",
            )
        )

    if not _JPG_BINARY_RE.search(content):
        findings.append(
            Finding(
                drift_class=DRIFT_MISSING_BINARY_DECLARATION,
                detail="`*.jpg binary` (or `*.jpeg binary`) declaration missing",
            )
        )

    if not _SVG_TEXT_RE.search(content):
        findings.append(
            Finding(
                drift_class=DRIFT_MISSING_BINARY_DECLARATION,
                detail=(
                    "`*.svg text` declaration missing; SVG must be kept "
                    "diffable as text rather than treated as binary"
                ),
            )
        )

    for ignore_path in _EXPORT_IGNORE_PATHS:
        if not _export_ignore_re(ignore_path).search(content):
            findings.append(
                Finding(
                    drift_class=DRIFT_MISSING_EXPORT_IGNORE,
                    detail=(
                        f"`{ignore_path}/ export-ignore` declaration "
                        "missing; ephemeral / developer-only tree would "
                        "leak into source archives"
                    ),
                )
            )

    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        path=str(path),
        passed=not findings,
        findings=findings,
    )


def _read_input(argv: list[str]) -> Path:
    if len(argv) >= 2:
        return Path(argv[1])
    return Path.cwd()


def _main(argv: list[str]) -> int:
    root = _read_input(argv)
    result = check(root)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
