# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The always-on rule set is four core rules plus the rule index, and no more.

Every rule file that carries ``alwaysApply: true`` is loaded into every session
by a harness that honours the key, so the set is held small by decision. This
module is the gate on that decision:

* the always-on set equals the core list below, so promoting a rule is an
  explicit edit to this file (and, if the bytes need it, to the matcher's
  ceilings), reviewed as a change to what loads in every session;
* the loaded text of that set stays under the byte ceilings;
* every other rule is path-scoped (``alwaysApply: false`` with a real
  ``pathFilter``), and a companion never reaches a file its parent does not;
* the demoted rules do not match the generic source paths of a host project,
  and no scoped rule is unconditional in Claude Code (a ``paths`` list of
  ``**`` alone loads at launch like a rule with none);
* the rule index names every parent rule and only rules that exist, so a rule
  added without an index mention fails here instead of going unreachable.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from apothem.conformity import always_on_budget_grep as budget
from apothem.harnesses._shared.install_driver import apply_claude_rules
from apothem.harnesses._shared.install_driver_converters import (
    _antigravity_rule_text,
    _claude_rule_text,
)
from apothem.lib.propagation import InstallEntry
from tests._shared.claude_rule_scope import (
    loads_at_launch_text,
    matches,
    unconditional,
)

_REPO: Final[Path] = Path(__file__).resolve().parents[2]
_RULES: Final[Path] = _REPO / "src" / "apothem" / "rules"

#: The four core rules. Promoting a rule edits this set.
CORE: Final[frozenset[str]] = frozenset(
    {"agnostic-posture", "authority-inquiry", "session-closure", "context-management"}
)
INDEX: Final[str] = "apothem-rule-index"
ALWAYS_ON: Final[frozenset[str]] = CORE | {INDEX}

#: The rules that were always-on before the core was cut to four. Each one now
#: carries a path scope; its companions follow its filter.
DEMOTED: Final[tuple[str, ...]] = (
    "agent-orchestration",
    "agile-sprints",
    "auto-memory",
    "authoritative-referencing",
    "canonical-layout",
    "clean-room-generation",
    "cognitive-identity",
    "definitiveness",
    "disclosure-ledger",
    "etc-extension",
    "expertise-posture",
    "freshness-facade",
    "host-discovery",
    "interactive-questions",
    "multi-agent-workflow",
    "operational-mandates",
    "option-annotation",
    "persistent-conventions-vigilance",
    "pre-emission-gate",
    "production-ready-prs",
    "source-accessibility",
    "systemic-participation",
    "ten-dimension-check",
    "tool-use-discipline",
)

#: Ceilings, pinned here so that raising one is a visible edit to this file.
EXPECTED_ALWAYS_ON_CEILING: Final[int] = 40_250
EXPECTED_INDEX_CEILING: Final[int] = 5_250

#: Paths that stand for generic source files in a host project.
GENERIC_PATHS: Final[tuple[str, ...]] = (
    "src/app/main.py",
    "tests/test_main.py",
    "scripts/build.sh",
    "web/App.tsx",
    "src/agents/planner.py",
    "src/services/update.py",
    "src/cli/install.ts",
    "lib/install.rb",
    "pkg/uninstall.go",
    "app/update.js",
)

#: One path per demoted rule that its filter is meant to match.
INTENDED_PATH: Final[dict[str, str]] = {
    "agent-orchestration": ".claude/agents/reviewer.md",
    "agile-sprints": ".apothem/plans/suite/MASTER-PLAN.md",
    # A project-local path. Claude Code matches a rule only against files inside
    # the working directory, so the real auto-memory directory (under the
    # user's Claude home) never path-loads this rule; it reaches a session
    # through the rule index.
    "auto-memory": "memory/MEMORY.md",
    "authoritative-referencing": "docs/guide.md",
    "canonical-layout": ".apothem/plans/suite/phases/01-setup/REPORT.md",
    "clean-room-generation": ".claude/skills/review/SKILL.md",
    "cognitive-identity": "CLAUDE.md",
    "definitiveness": "src/apothem/rules/definitiveness.md",
    "disclosure-ledger": ".claude/commands/ship.md",
    "etc-extension": "AGENTS.md",
    "expertise-posture": ".claude/agents/reviewer.md",
    "freshness-facade": "README.md",
    "host-discovery": "pyproject.toml",
    "interactive-questions": ".claude/commands/ship.md",
    "multi-agent-workflow": ".claude/commands/workflow.md",
    "operational-mandates": "CLAUDE.md",
    "option-annotation": ".claude/output-styles/terse.md",
    "persistent-conventions-vigilance": ".claude/hooks/notes.md",
    "pre-emission-gate": ".claude/skills/review/SKILL.md",
    "production-ready-prs": "CHANGELOG.md",
    "source-accessibility": "site/content/docs/index.mdx",
    "systemic-participation": "src/pkg/__init__.py",
    "ten-dimension-check": ".claude/commands/ship.md",
    "tool-use-discipline": ".claude/agents/reviewer.md",
}


def _read(stem: str) -> str:
    return (_RULES / f"{stem}.md").read_text(encoding="utf-8")


def _fields(stem: str) -> dict[str, str]:
    return budget.parse_frontmatter(_read(stem))[0]


def _globs(stem: str) -> list[str]:
    raw = _fields(stem).get("pathFilter", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _stems() -> list[str]:
    return sorted(p.stem for p in _RULES.glob("*.md") if p.name != "README.md")


def _is_parent(stem: str, stems: list[str]) -> bool:
    """A parent has no other rule's stem as a prefix before a hyphen."""
    return not any(stem != other and stem.startswith(other + "-") for other in stems)


def _companions(parent: str) -> list[str]:
    return [s for s in _stems() if s.startswith(parent + "-")]


def _index_body() -> str:
    """The index text before its ``## Bindings`` section."""
    return budget.strip_bindings_section(budget.parse_frontmatter(_read(INDEX))[1])


# --- the always-on set --------------------------------------------------


def test_always_on_set_is_the_core_plus_the_index() -> None:
    actual = {stem for stem in _stems() if budget.is_always_on(_fields(stem))}
    assert actual == ALWAYS_ON, (
        "the always-on set changed; edit CORE in this module in the same "
        f"change-set as the promotion. Unexpected: {sorted(actual - ALWAYS_ON)}; "
        f"missing: {sorted(ALWAYS_ON - actual)}"
    )


def test_ceilings_are_the_reviewed_values() -> None:
    assert budget.MAX_ALWAYS_ON_LOADED_BYTES == EXPECTED_ALWAYS_ON_CEILING
    assert budget.MAX_INDEX_LOADED_BYTES == EXPECTED_INDEX_CEILING
    assert budget.INDEX_RULE_STEM == INDEX


def test_always_on_set_fits_the_byte_ceiling() -> None:
    loaded = {stem: budget.measure_loaded(_read(stem))[0] for stem in ALWAYS_ON}
    assert sum(loaded.values()) <= budget.MAX_ALWAYS_ON_LOADED_BYTES, loaded
    assert loaded[INDEX] <= budget.MAX_INDEX_LOADED_BYTES, loaded[INDEX]


def test_every_always_on_body_is_under_the_word_budget() -> None:
    for stem in sorted(ALWAYS_ON):
        _, words = budget.measure(_read(stem))
        assert words <= budget.MAX_SUBSTANTIVE_WORDS, (stem, words)


def test_every_other_rule_is_path_scoped() -> None:
    for stem in _stems():
        if stem in ALWAYS_ON:
            continue
        fields = _fields(stem)
        assert fields.get("alwaysApply", "").lower() == "false", stem
        assert _globs(stem), f"{stem}: a scoped rule needs a non-empty pathFilter"


def test_core_and_index_carry_no_path_scope() -> None:
    for stem in sorted(ALWAYS_ON):
        fields = _fields(stem)
        assert fields.get("pathFilter", "").strip() == "", stem
        assert fields.get("alwaysApply", "").lower() == "true", stem


# --- the demoted rules' filters ------------------------------------------


def test_demoted_list_names_existing_scoped_parents() -> None:
    stems = _stems()
    assert len(set(DEMOTED)) == len(DEMOTED) == 24
    for stem in DEMOTED:
        assert stem in stems, stem
        assert _is_parent(stem, stems), stem
        assert stem not in ALWAYS_ON, stem


def test_companions_never_reach_a_file_their_parent_does_not() -> None:
    for parent in DEMOTED:
        parent_globs = set(_globs(parent))
        for companion in _companions(parent):
            extra = set(_globs(companion)) - parent_globs
            assert not extra, (
                f"{companion} would load without {parent} on: {sorted(extra)}"
            )


@pytest.mark.parametrize("path", GENERIC_PATHS)
def test_demoted_rules_do_not_match_generic_source_paths(path: str) -> None:
    for stem in DEMOTED:
        assert not matches(_globs(stem), path), f"{stem} matches {path}"
        for companion in _companions(stem):
            assert not matches(_globs(companion), path), f"{companion} matches {path}"


def test_no_scoped_rule_is_unconditional_in_claude_code() -> None:
    # Claude Code loads a rule at launch when its ``paths`` list is empty after
    # a trailing ``/**`` is stripped, or is ``**`` alone. Such a rule would load
    # in every session while ``alwaysApply: false`` kept it out of the budget.
    catch_all = {"**", "**/*", "*", "**/*.*"}
    for stem in _stems():
        if stem in ALWAYS_ON:
            continue
        globs = _globs(stem)
        assert not unconditional(globs), f"{stem} loads at launch: {globs}"
        assert not catch_all & set(globs), stem


def test_code_craft_conventions_is_scoped_and_covers_its_ui_companion() -> None:
    globs = _globs("code-craft-conventions")
    assert set(_globs("code-craft-ui")) <= set(globs)
    for path in ("src/app/main.py", "scripts/build.sh", "docs/guide.md", "README.md"):
        assert not matches(globs, path), path
    for path in ("web/app.ts", "cmd/main.go", "src/lib.rs", "Cargo.toml", "ui/App.tsx"):
        assert matches(globs, path), path


def test_installer_scripts_still_match_production_ready_prs() -> None:
    globs = _globs("production-ready-prs")
    assert globs == _globs("production-ready-prs-surfaces")
    for path in (
        "install.sh",
        "install.ps1",
        "bin/update.sh",
        "scripts/installer/uninstall.ps1",
        ".github/workflows/ci.yml",
    ):
        assert matches(globs, path), path


def test_demoted_rules_match_the_surface_they_govern() -> None:
    assert set(INTENDED_PATH) == set(DEMOTED)
    for stem, path in INTENDED_PATH.items():
        assert matches(_globs(stem), path), f"{stem} does not match {path}"


def test_glob_helper_semantics() -> None:
    assert matches(["**/rules/**/*.md"], "rules/x.md")
    assert matches(["**/rules/**/*.md"], "src/apothem/rules/x.md")
    assert not matches(["**/rules/**/*.md"], "src/apothem/rules/x.py")
    assert matches(["**/README.md"], "README.md")
    assert matches(["**/docs/**"], "docs/a/b.md")
    assert not matches(["**/docs/**"], "src/documents/b.md")


def test_glob_helper_uses_gitignore_semantics_for_bare_patterns() -> None:
    # Claude Code matches rule globs the way .gitignore does: a pattern with no
    # slash matches at any depth, so ``update.*`` is not a root-only pattern.
    assert matches(["update.*"], "src/services/update.py")
    assert matches(["*.md"], "docs/b.md")
    assert matches(["/update.*"], "update.sh")
    assert not matches(["/update.*"], "src/services/update.py")
    assert not unconditional(["/update.*"])


# --- the rule index ------------------------------------------------------


def test_index_names_every_parent_rule() -> None:
    stems = _stems()
    body = _index_body()
    missing = [
        stem
        for stem in stems
        if _is_parent(stem, stems) and stem != INDEX and f"`{stem}`" not in body
    ]
    assert not missing, (
        f"add these rules to src/apothem/rules/{INDEX}.md under the situation "
        f"that calls for each: {missing}"
    )


def test_index_names_only_rules_that_exist() -> None:
    stems = set(_stems())
    named = set(re.findall(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`", _index_body()))
    assert named, "the index names no rules"
    assert not named - stems, f"the index names missing rules: {sorted(named - stems)}"


def test_index_names_no_companion() -> None:
    stems = _stems()
    named = set(re.findall(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`", _index_body()))
    companions = {s for s in named if not _is_parent(s, stems)}
    assert not companions, (
        f"companions are opened from their parent: {sorted(companions)}"
    )


def test_index_names_the_core_rules() -> None:
    body = _index_body()
    for stem in CORE:
        assert f"`{stem}`" in body, stem


def test_index_does_not_say_the_core_is_loaded_unconditionally() -> None:
    # Some harnesses load no rule file at launch (and the Claude Code plugin
    # used alone loads none), so the index cannot tell the reader the core is
    # already in context. It tells the reader to read the core where it is not.
    section = _index_body().split("## What loads", 1)[1].split("## When to read", 1)[0]
    assert "MUST read them now" in section
    lowered = section.lower()
    for phrase in ("always on", "always-on", "loads with them", "already in context"):
        assert phrase not in lowered, phrase


def test_index_is_harness_neutral() -> None:
    text = _read(INDEX)
    for brand in ("Claude Code", "Claude Opus", "Claude Sonnet", "Claude Haiku"):
        assert brand not in text, brand


# --- what each harness loads ---------------------------------------------


def test_claude_copy_scopes_every_rule_but_the_core_and_index() -> None:
    launch = {
        stem
        for stem in _stems()
        if loads_at_launch_text(_claude_rule_text(_RULES / f"{stem}.md"))
    }
    assert launch == ALWAYS_ON


def test_engine_install_leaves_only_the_core_and_index_unscoped(
    tmp_path: Path,
) -> None:
    entry = InstallEntry(
        source="rules/", target="${HARNESS_ROOT}/rules/", mode="claude_rules"
    )
    root = tmp_path / ".claude"
    results = apply_claude_rules(entry, harness_root=root, harness_name="claude_code")
    assert results
    assert all(r.outcome in {"created", "updated", "unchanged"} for r in results), [
        (r.outcome, r.message) for r in results if r.outcome == "error"
    ]
    installed = sorted((root / "rules").glob("*.md"))
    assert installed
    launch = {
        p.stem for p in installed if loads_at_launch_text(p.read_text(encoding="utf-8"))
    }
    assert launch == ALWAYS_ON


def test_antigravity_marks_exactly_the_five_always_on() -> None:
    always_on_bytes = 0
    triggers: dict[str, str] = {}
    for stem in _stems():
        rendered = _antigravity_rule_text(_RULES / f"{stem}.md")
        match = re.search(r"^trigger: (\w+)$", rendered, re.MULTILINE)
        assert match, stem
        triggers[stem] = match.group(1)
        if match.group(1) == "always_on":
            always_on_bytes += len(rendered.encode("utf-8"))
    assert {s for s, t in triggers.items() if t == "always_on"} == ALWAYS_ON
    assert {t for s, t in triggers.items() if s not in ALWAYS_ON} == {"glob"}
    # The vendor shares 20,000 tokens across the always-on rule files.
    assert always_on_bytes / 3.5 < 20_000


# REUSE-IgnoreEnd
