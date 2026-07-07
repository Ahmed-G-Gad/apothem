# SPDX-License-Identifier: MIT

"""Validate frontmatter VALUES against the per-class JSON Schema enum/pattern constraints.

Why this validator exists. The sibling ``frontmatter_grep`` matcher checks
that an artifact carries the required frontmatter *keys* (and that the keys are
kebab-case); it deliberately does not parse or constrain the *values* — and it
rejects camelCase keys, so it is not run against the agent corpus whose schema
declares camelCase optional fields (``permissionMode``, ``disallowedTools``,
``maxTurns``, …). The doc-example test ``tests/unit/docs/test_frontmatter_examples.py``
checks documented example *keys* against the shipped-agent key union, not the
values either. The result is a real gap: nothing enforced that an enum-
constrained value stayed inside its enum. Every shipped agent carried
``permissionMode: "ask"`` for an extended period even though ``ask`` is not in
the schema's ``permissionMode`` enum
(``["default", "acceptEdits", "auto", "dontAsk", "bypassPermissions", "plan"]``,
mirroring the Claude Code vendor canon) — the drift went undetected because no
gate enforced enum values. This validator closes that gap.

What it checks. For each governed artifact class it loads the class's JSON
Schema from the ``schemas/`` sibling and, for every property that declares a
value constraint — an ``enum`` and/or a ``pattern``, directly or inside a
``oneOf`` / ``anyOf`` branch — validates that the artifact's frontmatter value
satisfies the constraint. The governed classes and their schemas:

- ``agents``  → ``agent.schema.json``  (enums: ``permissionMode``, ``effort``,
  ``isolation``, ``color``, and the ``memory`` ``oneOf`` string-enum/boolean;
  patterns: ``name``, ``version``, ``updated``).
- ``commands`` → ``command.schema.json`` (patterns: ``name``, ``version``,
  ``updated``). ``additionalProperties: false``, but key/required validation is
  owned by ``frontmatter_grep`` and the doc-example test — this validator adds
  the value-level pattern enforcement those surfaces lack.
- ``skills``  → ``skill.schema.json``  (enum: ``effort``; patterns: ``name``,
  ``version``, ``updated``, ``archetype``).

Scope boundary. This validator is value-only and schema-driven: it never
hardcodes a field list (a new enum/pattern property added to a schema is picked
up automatically), and it raises no finding for a *missing* key or an *absent*
frontmatter block — presence is owned by ``frontmatter_grep``. Type / required /
``additionalProperties`` / ``maxLength`` enforcement are deliberately out of
scope here; only ``enum`` and ``pattern`` value constraints are checked, which is
exactly the class of drift the documented gap names. A frontmatter block that
does not parse as a YAML mapping is skipped (its parse failure is a
``frontmatter_grep`` concern), so every finding this validator emits is an
enum/pattern value violation a fix can clear.

Detection. For each class, glob the corpus under ``root`` (``src/apothem/
agents/*.md``, ``src/apothem/commands/*.md``, ``src/apothem/skills/*/SKILL.md``),
extract the leading ``---``-delimited frontmatter block (tolerating an optional
leading HTML-comment banner per the sibling-convention), parse it with PyYAML,
and validate each constraint-bearing property present in the mapping.

Exit semantics. Exits 0 when every governed artifact's constrained values
satisfy their schema, OR when no governed artifact is present under ``root``
(an installed tree with no source cohort). Exits 2 on any enum/pattern value
violation. The exit-2 convention matches the conformity-gate orchestrator's
``EXIT_FAIL``; the gate runs this validator (blocking, like
``agent_capability_grep``) via subprocess in ``--all`` mode.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

GREP_NAME: Final[str] = "frontmatter-value-grep"
RULE_ANCHOR: Final[str] = "per-class JSON Schema enum/pattern value constraints"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# Schema/data files ride beside the conformity package in both the repo
# checkout (``src/apothem/{conformity,schemas}``) and the installed tree
# (``<install-root>/apothem/{conformity,schemas}``). Resolve one parent hop
# above this module so the same code finds its schemas in both shapes — the
# dual-shape anchor convention shared with ``file_header_grep`` /
# ``reference_token_grep`` and asserted by
# ``tests/conformity/test_schema_anchor_resolution.py``.
SCHEMAS_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "schemas"

FRONTMATTER_DELIMITER: Final[str] = "---"

# Governed artifact classes: (class, schema filename, corpus glob under root).
# Schema-driven — the constrained properties are read from each schema's
# ``properties`` block, never hardcoded here, so a new enum/pattern property
# added to a schema is enforced without editing this validator.
_COHORTS: Final[tuple[tuple[str, str, str], ...]] = (
    ("agents", "agent.schema.json", "src/apothem/agents/*.md"),
    ("commands", "command.schema.json", "src/apothem/commands/*.md"),
    ("skills", "skill.schema.json", "src/apothem/skills/*/SKILL.md"),
)

# JSON Schema ``type`` -> the Python type(s) a conforming value carries. Only
# the types that appear in the governed schemas need exact handling; ``integer``
# and ``boolean`` need the bool/int disambiguation Python's ``isinstance``
# otherwise blurs (``bool`` is a subclass of ``int``).
_JSON_SCALAR_TYPES: Final[frozenset[str]] = frozenset(
    {"string", "boolean", "integer", "number", "array", "object", "null"}
)


@dataclass(frozen=True)
class Finding:
    """One frontmatter value that violates its schema enum/pattern constraint."""

    surface: str
    artifact_class: str
    key: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result for one corpus sweep."""

    grep: str
    root: str
    files_inspected: int
    passed: bool
    informational: str | None = None
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        payload = {
            "grep": self.grep,
            "root": self.root,
            "files_inspected": self.files_inspected,
            "passed": self.passed,
            "informational": self.informational,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _extract_frontmatter(content: str) -> str | None:
    """Return the leading ``---``-delimited YAML block, or None when absent.

    Mirrors the sibling-convention extractor: tolerate a leading region of
    blank lines plus one optional HTML-comment banner before the opening
    ``---`` delimiter, then return the text between the opening and the next
    ``---`` line. The governed cohorts place frontmatter first; the optional
    leading-comment tolerance keeps the extractor robust to the
    banner-then-frontmatter ordering some surfaces use.
    """
    lines = content.splitlines()
    index = 0

    while index < len(lines) and not lines[index].strip():
        index += 1

    if index < len(lines) and lines[index].lstrip().startswith("<!--"):
        first = lines[index].strip()
        if first.endswith("-->") and first != "<!--":
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
        return None

    open_index = index
    for close_index in range(open_index + 1, len(lines)):
        if lines[close_index].strip() == FRONTMATTER_DELIMITER:
            return "\n".join(lines[open_index + 1 : close_index])
    return None


def _branches(prop_schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a property's alternative schemas: its ``oneOf`` / ``anyOf`` branch
    list, or ``[prop_schema]`` when the property is a single un-branched schema.
    A value is conforming when it satisfies at least one alternative."""
    for combinator in ("oneOf", "anyOf"):
        branches = prop_schema.get(combinator)
        if isinstance(branches, list):
            return [b for b in branches if isinstance(b, dict)]
    return [prop_schema]


def _carries_value_constraint(prop_schema: dict[str, Any]) -> bool:
    """True iff the property declares an ``enum`` or ``pattern`` in any branch."""
    return any(
        ("enum" in branch or "pattern" in branch) for branch in _branches(prop_schema)
    )


def _type_matches(value: Any, json_type: str) -> bool:  # noqa: ANN401 - duck-typed YAML scalar
    """True iff *value* satisfies the JSON Schema scalar ``type``.

    Disambiguates ``bool`` from ``int``/``number`` (a Python ``bool`` is an
    ``int`` subclass, but JSON treats them as distinct types). Unknown types are
    not constrained (return True) so a future schema type never fail-closes.
    """
    if json_type not in _JSON_SCALAR_TYPES:
        return True
    if json_type == "boolean":
        return isinstance(value, bool)
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if json_type == "string":
        return isinstance(value, str)
    if json_type == "array":
        return isinstance(value, list)
    if json_type == "object":
        return isinstance(value, dict)
    return value is None  # "null"


def _branch_accepts(value: Any, branch: dict[str, Any]) -> bool:  # noqa: ANN401 - duck-typed YAML scalar
    """True iff *value* satisfies one branch's type + enum + pattern constraints."""
    json_type = branch.get("type")
    if isinstance(json_type, str) and not _type_matches(value, json_type):
        return False
    enum = branch.get("enum")
    if isinstance(enum, list) and value not in enum:
        return False
    pattern = branch.get("pattern")
    # JSON Schema ``pattern`` is an unanchored search; the governed schemas all
    # carry their own ``^...$`` anchors, so search == full match here.
    if isinstance(pattern, str):
        return isinstance(value, str) and re.search(pattern, value) is not None
    return True


def _value_valid(value: Any, prop_schema: dict[str, Any]) -> bool:  # noqa: ANN401 - duck-typed YAML scalar
    """True iff *value* satisfies at least one of the property's alternatives."""
    return any(_branch_accepts(value, branch) for branch in _branches(prop_schema))


def _expected_summary(prop_schema: dict[str, Any]) -> str:
    """Human-readable summary of a property's accepted forms, for the finding."""
    parts: list[str] = []
    for branch in _branches(prop_schema):
        enum = branch.get("enum")
        pattern = branch.get("pattern")
        if isinstance(enum, list):
            parts.append("one of " + ", ".join(repr(v) for v in enum))
        if isinstance(pattern, str):
            parts.append(f"a string matching /{pattern}/")
        if enum is None and pattern is None and isinstance(branch.get("type"), str):
            parts.append(f"a {branch['type']}")
    return " or ".join(parts) if parts else "a schema-conformant value"


def _load_value_constraints(schema_path: Path) -> dict[str, dict[str, Any]]:
    """Return ``{property: schema}`` for every constraint-bearing property.

    A missing or unparseable schema yields an empty constraint map (the cohort
    is then skipped with no findings) rather than fail-closing the whole sweep.
    """
    try:
        raw = schema_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        schema = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return {}
    return {
        name: prop
        for name, prop in properties.items()
        if isinstance(prop, dict) and _carries_value_constraint(prop)
    }


def _check_file(
    path: Path,
    root: Path,
    artifact_class: str,
    constraints: dict[str, dict[str, Any]],
) -> tuple[bool, list[Finding]]:
    """Validate one artifact file's constrained frontmatter values.

    Returns ``(inspected, findings)``: ``inspected`` is True when the file
    carried a parseable frontmatter mapping (and was therefore value-checked).
    A file with no frontmatter block, or a block that does not parse to a
    mapping, is not inspected and contributes no findings — presence and parse
    integrity are owned by ``frontmatter_grep``.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False, []
    block = _extract_frontmatter(content)
    if block is None:
        return False, []
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError:
        return False, []
    if not isinstance(parsed, dict):
        return False, []

    try:
        surface = str(path.relative_to(root))
    except ValueError:
        surface = str(path)

    findings: list[Finding] = []
    for key, prop_schema in constraints.items():
        if key not in parsed:
            continue
        value = parsed[key]
        if _value_valid(value, prop_schema):
            continue
        findings.append(
            Finding(
                surface=surface,
                artifact_class=artifact_class,
                key=key,
                detail=(
                    f"{key!r} value {value!r} violates the {artifact_class} schema: "
                    f"expected {_expected_summary(prop_schema)}"
                ),
            )
        )
    return True, findings


def check(root: Path) -> GrepResult:
    """Walk every governed cohort under *root*; flag enum/pattern value violations."""
    findings: list[Finding] = []
    files_inspected = 0
    for artifact_class, schema_filename, glob_pattern in _COHORTS:
        constraints = _load_value_constraints(SCHEMAS_DIR / schema_filename)
        if not constraints:
            continue
        for path in sorted(root.glob(glob_pattern)):
            if not path.is_file():
                continue
            inspected, file_findings = _check_file(
                path, root, artifact_class, constraints
            )
            if inspected:
                files_inspected += 1
            findings.extend(file_findings)

    informational: str | None = None
    if files_inspected == 0:
        informational = (
            "no governed artifact (agent / command / skill) carrying frontmatter "
            f"found under {root}; validator is in an absence-tolerant pass"
        )
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        files_inspected=files_inspected,
        passed=not findings,
        informational=informational,
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
