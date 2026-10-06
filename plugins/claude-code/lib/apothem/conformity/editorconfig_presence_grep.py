# SPDX-License-Identifier: MIT

"""Verify a canonical .editorconfig is present at the project root.

Why this enforcement exists. The supply-chain SOTA-rigor
cohort requires every repository to ship a ratified ``.editorconfig`` so
every contributor's editor materializes whitespace, indentation, line
ending, charset, and final-newline conventions identically regardless of
local editor configuration. Silent drift at the editor layer surfaces as
mixed-line-ending diffs, trailing-whitespace noise, and indent-character
mismatches that cost reviewer attention; a ratified ``.editorconfig`` at
the repo root pre-empts the entire class of failures. This standalone
validator confirms the file exists with the canonical contract
(``root = true`` declaration, the global ``[*]`` section with the six
canonical keys, the ``[*.{yml,yaml,json}]`` two-space override for
data-shaped files, and the ``[*.md]`` trailing-whitespace exemption for
Markdown's two-space hard-break convention).

Scope. Standalone corpus-level validator. Reads ``<root>/.editorconfig``
from a single ``main(root)`` entry point and exits 0 (PASS) or 2 (FAIL)
with a structured JSON report listing every drift class observed.
Invoked via ``python -m apothem.conformity.gate --all .`` or
``python -m apothem.conformity.gate --check editorconfig-presence-grep
<root>``.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "editorconfig-presence-grep"
RULE_ANCHOR: Final[str] = "supply-chain SOTA-rigor §editorconfig"
EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

EDITORCONFIG_FILENAME: Final[str] = ".editorconfig"

# The canonical key/value pairs every conformant ``[*]`` section carries.
# Each value is the verbatim literal the editorconfig spec admits for the
# key; the matcher compares case-insensitively for value tokens but the
# key itself is matched literally per the editorconfig grammar.
GLOBAL_REQUIRED_KEYS: Final[dict[str, str]] = {
    "charset": "utf-8",
    "indent_style": "space",
    "indent_size": "4",
    "end_of_line": "lf",
    "insert_final_newline": "true",
    "trim_trailing_whitespace": "true",
}

# Per-language overrides. Each entry maps the section header (literal
# bracketed string) to the (key, expected-value) pair the section MUST
# declare for the override to be canonical.
PER_LANGUAGE_OVERRIDES: Final[dict[str, dict[str, str]]] = {
    "[*.{yml,yaml,json}]": {"indent_size": "2"},
    "[*.md]": {"trim_trailing_whitespace": "false"},
}

# Matches a section header line such as ``[*]`` or ``[*.md]``. Trailing
# inline comments (``[*]  ; comment``) are tolerated by the editorconfig
# grammar; we strip them before classification.
SECTION_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\[[^\]]+\])\s*(?:[;#].*)?$")

# Matches a ``key = value`` declaration inside a section. The
# editorconfig grammar admits whitespace on either side of the ``=`` and
# a trailing comment introduced by ``;`` or ``#``.
KEY_VALUE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^;#]+?)\s*(?:[;#].*)?$"
)

# The ``root = true`` declaration. Matched anywhere in the file (it lives
# above the first section header by convention but the spec admits any
# pre-section position).
ROOT_DECLARATION_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*root\s*=\s*true\s*(?:[;#].*)?$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class Finding:
    """One editorconfig drift observation."""

    drift_class: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Matcher report for a single sweep of this validator.

    Pre-conditions: ``findings`` holds this module's frozen ``Finding``
    dataclasses. Post-conditions: ``passed`` is ``True`` exactly when
    ``findings`` is empty; :meth:`to_json` emits the serialised payload.
    """

    grep: str
    path: str | None
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, path, passed,
        findings}``; each finding is flattened through ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "path": self.path,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _parse_sections(text: str) -> dict[str, dict[str, str]]:
    """Parse an editorconfig body into ``{section-header: {key: value}}``.

    The pre-section preamble (where ``root = true`` lives) is collected
    under the empty-string key so callers can inspect it uniformly.
    """
    sections: dict[str, dict[str, str]] = {"": {}}
    current = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith((";", "#")):
            continue
        section_match = SECTION_RE.match(line)
        if section_match is not None:
            current = section_match.group(1)
            sections.setdefault(current, {})
            continue
        kv_match = KEY_VALUE_RE.match(line)
        if kv_match is not None:
            key = kv_match.group(1)
            value = kv_match.group(2).strip().lower()
            sections[current][key] = value
    return sections


def check(root: Path) -> GrepResult:
    """Verify ``<root>/.editorconfig`` carries the canonical contract.

    Pre-conditions: ``root`` is the project root (the directory holding
    ``pyproject.toml`` or its closest ancestor).
    Post-conditions: ``result.passed`` is True iff the editorconfig file
    exists with the ``root = true`` declaration, the six canonical
    ``[*]`` keys at their ratified values, and the two per-language
    overrides at their ratified values.
    """
    findings: list[Finding] = []
    target = root / EDITORCONFIG_FILENAME
    if not target.is_file():
        findings.append(
            Finding(
                drift_class="file-absent",
                detail=(
                    f"no .editorconfig at {target}; author a canonical file "
                    "per the supply-chain SOTA-rigor contract"
                ),
            )
        )
        return GrepResult(
            grep=GREP_NAME,
            path=str(root),
            passed=False,
            findings=findings,
        )

    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        findings.append(
            Finding(
                drift_class="file-absent",
                detail=f"could not read {target}: {exc!r}",
            )
        )
        return GrepResult(
            grep=GREP_NAME,
            path=str(root),
            passed=False,
            findings=findings,
        )

    if ROOT_DECLARATION_RE.search(text) is None:
        findings.append(
            Finding(
                drift_class="missing-root-declaration",
                detail=(
                    "no `root = true` declaration; the editorconfig spec "
                    "requires this token to halt the upward walk for "
                    "ancestor .editorconfig files"
                ),
            )
        )

    sections = _parse_sections(text)

    global_section = sections.get("[*]")
    if global_section is None:
        findings.append(
            Finding(
                drift_class="missing-global-section",
                detail="no `[*]` section; the global override is mandatory",
            )
        )
    else:
        for key, expected in GLOBAL_REQUIRED_KEYS.items():
            if key not in global_section:
                findings.append(
                    Finding(
                        drift_class="missing-global-section",
                        detail=(
                            f"[*] section is missing required key {key!r} "
                            f"(expected value: {expected!r})"
                        ),
                    )
                )
                continue
            actual = global_section[key]
            if actual != expected.lower():
                findings.append(
                    Finding(
                        drift_class="wrong-value",
                        detail=(
                            f"[*].{key} = {actual!r}; expected "
                            f"{expected!r} per the canonical contract"
                        ),
                    )
                )

    for header, required in PER_LANGUAGE_OVERRIDES.items():
        section = sections.get(header)
        if section is None:
            findings.append(
                Finding(
                    drift_class="missing-per-language-override",
                    detail=(
                        f"no {header} section; canonical contract requires "
                        f"this override declaring {required!r}"
                    ),
                )
            )
            continue
        for key, expected in required.items():
            if key not in section:
                findings.append(
                    Finding(
                        drift_class="missing-per-language-override",
                        detail=(
                            f"{header} section is missing key {key!r} "
                            f"(expected value: {expected!r})"
                        ),
                    )
                )
                continue
            actual = section[key]
            if actual != expected.lower():
                findings.append(
                    Finding(
                        drift_class="wrong-value",
                        detail=(
                            f"{header}.{key} = {actual!r}; expected "
                            f"{expected!r} per the canonical contract"
                        ),
                    )
                )

    return GrepResult(
        grep=GREP_NAME,
        path=str(root),
        passed=not findings,
        findings=findings,
    )


def main(root: Path) -> int:
    """Run the check over *root*, print the report, return the exit code.

    Pre-conditions: ``root`` is the repository root to inspect.
    Post-conditions: the JSON report, stamped with ``inspected`` (1 when the
    ``.editorconfig`` file was read), is written to stdout; the return is
    :data:`EXIT_PASS` when the sweep passed and :data:`EXIT_FAIL` otherwise.
    """
    # Imported here, not at module top: ``check()`` stays stdlib-only.
    from apothem.conformity._grep_base import finish_root_report

    result = check(root)
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=int((root / EDITORCONFIG_FILENAME).is_file()),
    )


def _main(argv: list[str]) -> int:
    from apothem.conformity._grep_base import parse_root_args

    return main(parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root)


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
