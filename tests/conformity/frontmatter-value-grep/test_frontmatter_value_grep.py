# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""Unit tests for the frontmatter-value matcher.

The matcher validates frontmatter VALUES against the per-class JSON Schema's
``enum`` / ``pattern`` constraints — the gap the sibling ``frontmatter_grep``
(keys only) and the doc-example test (example keys only) leave open. The
headline scenario is the documented drift: an agent shipping
``permissionMode: "ask"`` when ``ask`` is not in the schema enum.

These tests exercise the branch logic against the real shipped schemas, the
``check(root)`` walk against synthetic cohort trees, the absence-tolerant pass,
the no-frontmatter skip, and the gate registration. The real-repo-root pass is
exercised in-process by ``tests/conformity/test_standalone_greps_inprocess.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from apothem.conformity import frontmatter_value_grep as fvg
from apothem.conformity import gate

_AGENT_FM = """\
---
name: "{name}"
version: "{version}"
updated: "{updated}"
description: "A synthetic agent fixture."
effort: "{effort}"
permissionMode: "{permission_mode}"
memory: {memory}
---

<!-- SPDX-License-Identifier: MIT -->

System prompt body.
"""

_SKILL_FM = """\
---
name: "{name}"
version: "0.1.0"
updated: "2026-06-23"
description: "A synthetic skill fixture."
archetype: "{archetype}"
userInvocable: true
disable-model-invocation: true
allowed-tools: "Read, Grep"
effort: "{effort}"
---

<!-- SPDX-License-Identifier: MIT -->

Skill body.
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _agent(
    *,
    name: str = "synthetic-agent",
    version: str = "0.1.0",
    updated: str = "2026-06-23",
    effort: str = "high",
    permission_mode: str = "default",
    memory: str = "false",
) -> str:
    return _AGENT_FM.format(
        name=name,
        version=version,
        updated=updated,
        effort=effort,
        permission_mode=permission_mode,
        memory=memory,
    )


def _skill(
    *,
    name: str = "synthetic-skill",
    archetype: str = "audit-template",
    effort: str = "high",
) -> str:
    return _SKILL_FM.format(name=name, archetype=archetype, effort=effort)


# --- Schema-driven branch logic against the real shipped schemas ------------


def _agent_property(key: str) -> dict[str, object]:
    schema = json.loads((fvg.SCHEMAS_DIR / "agent.schema.json").read_text("utf-8"))
    return schema["properties"][key]


def test_enum_branch_accepts_in_enum_rejects_out_of_enum() -> None:
    """A direct string enum (``permissionMode``) accepts members, rejects others.

    This is the documented gap: ``ask`` is not in the schema enum.
    """
    prop = _agent_property("permissionMode")
    assert fvg._value_valid("default", prop)
    assert fvg._value_valid("plan", prop)
    assert not fvg._value_valid("ask", prop)


def test_oneof_branch_accepts_string_enum_or_boolean() -> None:
    """The ``memory`` ``oneOf`` accepts a string enum member OR a boolean."""
    prop = _agent_property("memory")
    assert fvg._value_valid(False, prop)  # boolean branch
    assert fvg._value_valid("project", prop)  # string-enum branch
    assert not fvg._value_valid("everywhere", prop)  # neither branch
    assert not fvg._value_valid(3, prop)  # neither branch


def test_pattern_branch_accepts_semver_rejects_malformed() -> None:
    """A ``pattern`` property (``version``) accepts SemVer, rejects a partial."""
    prop = _agent_property("version")
    assert fvg._value_valid("1.2.3", prop)
    assert not fvg._value_valid("0.1", prop)
    assert not fvg._value_valid("v1.2.3", prop)


# --- check(root) walk against synthetic cohort trees ------------------------


def test_clean_agent_corpus_passes(tmp_path: Path) -> None:
    """A conformant agent file passes and is counted as inspected."""
    _write(tmp_path / "src" / "apothem" / "agents" / "good.md", _agent())

    result = fvg.check(tmp_path)

    assert result.passed is True
    assert result.findings == []
    assert result.files_inspected == 1


def test_bad_permission_mode_is_flagged(tmp_path: Path) -> None:
    """The documented drift — ``permissionMode: ask`` — is a finding."""
    _write(
        tmp_path / "src" / "apothem" / "agents" / "drift.md",
        _agent(permission_mode="ask"),
    )

    result = fvg.check(tmp_path)

    assert result.passed is False
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.key == "permissionMode"
    assert finding.artifact_class == "agents"
    assert finding.surface == str(Path("src/apothem/agents/drift.md"))
    assert "ask" in finding.detail


def test_bad_version_pattern_is_flagged(tmp_path: Path) -> None:
    """A non-SemVer ``version`` value is a pattern finding."""
    _write(
        tmp_path / "src" / "apothem" / "agents" / "ver.md",
        _agent(version="0.1"),
    )

    result = fvg.check(tmp_path)

    assert result.passed is False
    assert [f.key for f in result.findings] == ["version"]


def test_bad_memory_oneof_value_is_flagged(tmp_path: Path) -> None:
    """A ``memory`` value matching neither oneOf branch is a finding."""
    _write(
        tmp_path / "src" / "apothem" / "agents" / "mem.md",
        _agent(memory='"everywhere"'),
    )

    result = fvg.check(tmp_path)

    assert result.passed is False
    assert [f.key for f in result.findings] == ["memory"]


def test_skill_pattern_is_flagged(tmp_path: Path) -> None:
    """A skill with a bad ``archetype`` pattern is flagged.

    The skill schema admits no enum-constrained key (``effort`` was removed
    under the agnostic posture), so the pattern-constrained ``archetype`` is
    the skill class's value-constraint surface.
    """
    _write(
        tmp_path / "src" / "apothem" / "skills" / "bad" / "SKILL.md",
        _skill(archetype="weird-shape"),
    )

    result = fvg.check(tmp_path)

    assert result.passed is False
    flagged = {f.key for f in result.findings}
    assert flagged == {"archetype"}
    assert all(f.artifact_class == "skills" for f in result.findings)


def test_clean_skill_corpus_passes(tmp_path: Path) -> None:
    """A conformant skill file passes and is counted."""
    _write(tmp_path / "src" / "apothem" / "skills" / "ok" / "SKILL.md", _skill())

    result = fvg.check(tmp_path)

    assert result.passed is True
    assert result.files_inspected == 1


def test_file_without_frontmatter_is_skipped(tmp_path: Path) -> None:
    """A README-shaped file with no frontmatter is not inspected, not flagged.

    Presence and parse integrity are owned by ``frontmatter_grep``; this matcher
    only constrains values of a present, parseable frontmatter mapping.
    """
    _write(
        tmp_path / "src" / "apothem" / "agents" / "README.md",
        "<!-- SPDX-License-Identifier: MIT -->\n\n# Agents\n\nProse, no frontmatter.\n",
    )

    result = fvg.check(tmp_path)

    assert result.passed is True
    assert result.findings == []
    assert result.files_inspected == 0


def test_empty_corpus_is_absence_tolerant_pass(tmp_path: Path) -> None:
    """No governed artifact under root → a clean, informational pass."""
    result = fvg.check(tmp_path)

    assert result.passed is True
    assert result.files_inspected == 0
    assert result.informational is not None


def test_multiple_violations_across_classes_aggregate(tmp_path: Path) -> None:
    """Violations across agents and skills aggregate into one result."""
    _write(
        tmp_path / "src" / "apothem" / "agents" / "a.md", _agent(permission_mode="ask")
    )
    _write(
        tmp_path / "src" / "apothem" / "skills" / "s" / "SKILL.md",
        _skill(archetype="weird-shape"),
    )

    result = fvg.check(tmp_path)

    assert result.passed is False
    classes = {f.artifact_class for f in result.findings}
    assert classes == {"agents", "skills"}
    assert result.files_inspected == 2


# --- Gate registration ------------------------------------------------------


def test_matcher_registered_as_standalone() -> None:
    """The matcher is wired into the gate's standalone registry."""
    assert "frontmatter-value-grep" in gate.STANDALONE_MODULES


# REUSE-IgnoreEnd
