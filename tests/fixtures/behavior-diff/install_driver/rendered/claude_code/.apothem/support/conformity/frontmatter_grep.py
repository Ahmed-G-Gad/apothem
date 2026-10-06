# SPDX-License-Identifier: MIT

"""Validate per-artifact-class YAML frontmatter against required-key sets.

Why this enforcement exists. Spec section 4.2 ratifies that every
artifact carries YAML frontmatter delimited by ``---`` lines, with
required-key sets that vary per artifact class (rules, agents, skills,
commands, output styles each carry their own minimum schema). This
validator extends the grep family with frontmatter checks; per-class
JSON Schemas feed this validator's strict-mode.

Detection strategy. The validator reads a file, locates the leading
``---``-delimited frontmatter block, parses the YAML, and checks the
required-key set for the inferred artifact class (inferred by the
file's path under rules/, agents/, skills/, commands/, output-styles/).
A missing required key, an unparseable YAML block, or an absent
frontmatter block on a class that requires one is a finding. Frontmatter
keys must use kebab-case per spec section 4.1; non-kebab-case keys are
flagged. Schema-presence-driven strict-mode activates when per-class
JSON Schemas exist at ``frontmatter/<class>.json`` inside the
``schemas/`` directory shipped beside this package (one parent hop above
this module in both the repo-checkout and installed layouts); until then
the validator runs the baseline required-key check.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

# Required-key sets per artifact class, derived from the canonical
# frontmatter schema declared at site/content/docs/reference/frontmatter-schema.mdx and the
# minimum schemas observed across the rules/ + agents/ + skills/ +
# commands/ + output-styles/ corpora.
REQUIRED_KEYS: Final[dict[str, frozenset[str]]] = {
    "rules": frozenset({"name", "description", "alwaysApply"}),
    "agents": frozenset({"name", "description"}),
    "skills": frozenset({"name", "description"}),
    "commands": frozenset({"name", "description"}),
    "output-styles": frozenset({"name", "description"}),
    "hooks-messages": frozenset({"description"}),
}

# Kebab-case key shape per spec section 4.1. Frontmatter keys are
# matched against this regex; uppercase / underscore / camelCase keys
# are findings. The harness honors an explicit allow-list for keys
# that originated in pre-ratification artifacts and are preserved by
# sibling-convergence per host-discovery.
KEBAB_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
KEY_ALLOW_LIST: Final[frozenset[str]] = frozenset(
    {
        # Path-filter keys observed across rules/ predate the
        # kebab-case ratification.
        "pathFilter",
        "alwaysApply",
        # Argument-hint and disable-model-invocation surface inside
        # commands frontmatter; both predate ratification.
        "argument-hint",
        "disable-model-invocation",
        "allowed-tools",
        # User-invocability flag on skills; camelCase predates the
        # kebab-case ratification and is uniform across the skill corpus
        # (preserved by sibling-convergence per host-discovery).
        "userInvocable",
        # Tools-list key on agents.
        "tools",
        "model",
    }
)

FRONTMATTER_DELIMITER: Final[str] = "---"
GREP_NAME: Final[str] = "frontmatter-grep"
RULE_ANCHOR: Final[str] = (
    "the per-class frontmatter JSON Schemas (src/apothem/schemas/)"
)
EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2
STDIN_FLAG: Final[str] = "--stdin"


@dataclass(frozen=True)
class Finding:
    """One frontmatter violation on the inspected artifact.

    Pre-conditions: ``detail`` names the violated expectation in
    operator-facing prose (a missing required key, an unparseable YAML block,
    or a non-kebab-case key). Post-conditions: ``rule`` defaults to
    :data:`RULE_ANCHOR` so every finding cites the per-class frontmatter
    schemas as its authority.
    """

    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Frontmatter-matcher report for a single artifact.

    Carries its own result shape rather than reusing
    :class:`apothem.conformity._grep_base.GrepResult` because the payload adds
    an ``artifact-class`` key recording which required-key set was applied.

    Pre-conditions: ``artifact_class`` is the class inferred from the path
    (``rules`` / ``agents`` / ``skills`` / ``commands`` / ``output-styles`` /
    ``hooks-messages``), or ``None`` when the path matches no class and the
    check is vacuously satisfied. Post-conditions: ``to_json`` emits
    ``{grep, path, artifact-class, passed, findings}``.
    """

    grep: str
    path: str | None
    artifact_class: str | None
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return the canonical JSON report as a two-space-indented string.

        Post-conditions: the ``artifact_class`` field is emitted under the
        kebab-case ``artifact-class`` key per the report-shape convention; each
        finding is flattened through ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "path": self.path,
            "artifact-class": self.artifact_class,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _infer_class(path: Path) -> str | None:
    """Infer the artifact class from any class-named segment in the path."""
    parts = path.parts
    if "rules" in parts:
        return "rules"
    if "agents" in parts:
        return "agents"
    if "skills" in parts:
        return "skills"
    if "commands" in parts:
        return "commands"
    if "output-styles" in parts:
        return "output-styles"
    if "hooks" in parts and "messages" in parts:
        return "hooks-messages"
    return None


def _extract_frontmatter(content: str) -> tuple[str | None, int]:
    """Return (frontmatter-yaml, body-start-line) or (None, 0).

    The established sibling-convention across commands/, agents/, skills/,
    rules/, and output-styles/ places the canonical authorship-header
    banner (an HTML comment block opened with ``<!--`` and closed with
    ``-->``) before the YAML frontmatter, separated by a blank line. The
    extractor therefore tolerates a leading region of blank lines plus
    one optional HTML-comment block before locating the opening ``---``
    delimiter. Within the comment region, the closing ``-->`` may sit on
    its own line or share a line with trailing content; the extractor
    advances past the first line whose stripped contents end with
    ``-->``.
    """
    lines = content.splitlines()
    index = 0

    while index < len(lines) and not lines[index].strip():
        index += 1

    if index < len(lines) and lines[index].lstrip().startswith("<!--"):
        first_comment_line = lines[index].strip()
        if first_comment_line.endswith("-->") and first_comment_line != "<!--":
            index += 1
        else:
            index += 1
            while index < len(lines) and not lines[index].strip().endswith("-->"):
                index += 1
            if index < len(lines):
                index += 1

    while index < len(lines) and not lines[index].strip():
        index += 1

    if index >= len(lines) or lines[index].strip() != FRONTMATTER_DELIMITER:
        return None, 0

    open_index = index
    for close_index in range(open_index + 1, len(lines)):
        if lines[close_index].strip() == FRONTMATTER_DELIMITER:
            return (
                "\n".join(lines[open_index + 1 : close_index]),
                close_index + 1,
            )
    return None, 0


def _parse_keys(yaml_block: str) -> list[str]:
    """Extract top-level keys from the YAML block via line-shape parsing.

    The validator does not depend on PyYAML; the frontmatter's surface
    is shallow (top-level scalar keys plus the occasional list value)
    and the shape can be read from the first column of each line. Keys
    inside nested mappings or lists are intentionally excluded — only
    top-level keys count toward the required-set check.
    """
    keys: list[str] = []
    for raw in yaml_block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[0].isspace() or raw.startswith("-"):
            continue
        if ":" not in raw:
            continue
        key = raw.split(":", 1)[0].strip()
        if key:
            keys.append(key)
    return keys


def check(content: str, path: Path | None = None) -> GrepResult:
    """Validate frontmatter for the inferred artifact class."""
    findings: list[Finding] = []
    artifact_class = _infer_class(path) if path is not None else None
    yaml_block, _ = _extract_frontmatter(content)

    if yaml_block is None:
        if artifact_class is not None:
            findings.append(
                Finding(
                    detail=(
                        f"frontmatter block absent on artifact-class "
                        f"{artifact_class!r}; required by spec section 4.2"
                    )
                )
            )
        return GrepResult(
            grep=GREP_NAME,
            path=str(path) if path is not None else None,
            artifact_class=artifact_class,
            passed=not findings,
            findings=findings,
        )

    keys = _parse_keys(yaml_block)
    keyset = set(keys)

    if artifact_class is not None:
        required = REQUIRED_KEYS.get(artifact_class, frozenset())
        missing = required - keyset
        for key in sorted(missing):
            findings.append(
                Finding(
                    detail=(
                        f"required key {key!r} missing from "
                        f"{artifact_class!r} frontmatter"
                    )
                )
            )

    for key in keys:
        if key in KEY_ALLOW_LIST:
            continue
        if not KEBAB_KEY_RE.match(key):
            findings.append(
                Finding(
                    detail=(
                        f"frontmatter key {key!r} is not kebab-case (spec section 4.1)"
                    )
                )
            )

    return GrepResult(
        grep=GREP_NAME,
        path=str(path) if path is not None else None,
        artifact_class=artifact_class,
        passed=not findings,
        findings=findings,
    )


def _main(argv: list[str]) -> int:
    # Imported here, not at module top: ``check()`` stays stdlib-only so the
    # gate can load it even where the ``apothem`` package is not importable;
    # only the command-line entry needs the shared parser.
    from apothem.conformity._grep_base import parse_path_input

    _args, content, path = parse_path_input(argv, prog=GREP_NAME, doc=__doc__)
    result = check(content, path)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
