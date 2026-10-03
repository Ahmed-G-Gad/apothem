# SPDX-License-Identifier: MIT

"""Structural checks for the behavioural eval suite under ``evals/``.

Running an eval costs model calls, so a malformed case should fail here, for
free, instead of at the start of a paid run. The suite is plain data (the
plugin-eval case format) meant to outlive any one runner, so these checks pin
both the format and the coverage contract:

* every case validates against ``evals/case.schema.json`` (unknown keys fail a
  real run at load time), has at least one grader, a unique name, and only
  regex patterns that compile and use ``flags`` rather than inline modifiers;
* every model-invocable component (commands and skills without
  ``disable-model-invocation: true``, and every subagent) has a should-trigger
  and a should-not-trigger case, and each command that is user-invoked by
  maintainer decision has a should-not-auto-trigger case instead;
* a "never fires" grader is scored in both arms, so the no-plugin baseline is
  comparable;
* every stage of the plan, research and audit pipelines has an outcome case;
* rule-effect cases come in pairs that differ only by ``append_system_prompt``,
  which equals the rule's runtime text (the rule-scoping regression set).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

_REPO = Path(__file__).resolve().parents[2]
_EVALS = _REPO / "evals"
_SCHEMA = _EVALS / "case.schema.json"
_CORPUS = _REPO / "src" / "apothem"
_SCRIPTS_DEV = _REPO / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import sync_eval_rule_cases as rule_sync  # noqa: E402

# Commands that stay user-invoked only by maintainer decision: the model
# must not start them on its own, whatever their frontmatter says today.
_USER_INVOKED_BY_DECISION = frozenset(
    {"freshify", "github-deploy-fresh", "github-deploy-next"}
)

# The eleven dimensions /audit dispatches (commands/audit.md).
_AUDIT_DIMENSIONS = (
    "code-review",
    "code-audit",
    "architecture-review",
    "docs-review",
    "security-audit",
    "dependency-audit",
    "supply-chain-audit",
    "threat-model-audit",
    "perf-audit",
    "a11y-audit",
    "ux-review",
)

_KINDS = frozenset(
    {"trigger", "no-trigger", "no-auto-trigger", "outcome", "rule-effect"}
)


@dataclass
class Case:
    """One case directory and what it declares."""

    path: Path
    frontmatter: dict[str, Any]
    body: str
    case_yaml: dict[str, Any] | None
    graders: dict[str, dict[str, Any]] = field(default_factory=dict)
    grader_bodies: dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        declared = self.frontmatter.get("name") or (self.case_yaml or {}).get("name")
        return str(declared or self.path.name)

    @property
    def tags(self) -> list[str]:
        return [str(tag) for tag in self.frontmatter.get("tags", [])]

    def tag_values(self, prefix: str) -> list[str]:
        return [
            tag.split(":", 1)[1] for tag in self.tags if tag.startswith(f"{prefix}:")
        ]

    @property
    def kind(self) -> str:
        kinds = [tag for tag in self.tags if tag in _KINDS]
        assert len(kinds) == 1, f"{self.path}: exactly one kind tag of {sorted(_KINDS)}"
        return kinds[0]


def _load_cases() -> list[Case]:
    cases = []
    for directory in sorted(
        {p.parent for p in _EVALS.rglob("prompt.md")}
        | {p.parent for p in _EVALS.rglob("case.yaml")}
    ):
        prompt = directory / "prompt.md"
        frontmatter, body = (
            rule_sync.split_markdown(prompt) if prompt.is_file() else ({}, "")
        )
        case_file = directory / "case.yaml"
        case_yaml = (
            yaml.safe_load(case_file.read_text(encoding="utf-8"))
            if case_file.is_file()
            else None
        )
        case = Case(directory, frontmatter, body, case_yaml)
        for grader in sorted((directory / "graders").glob("*.md")):
            fields, grader_body = rule_sync.split_markdown(grader)
            case.graders[grader.stem] = fields
            case.grader_bodies[grader.stem] = grader_body
        for entry in (case_yaml or {}).get("graders", []):
            case.graders[str(entry["name"])] = entry
        cases.append(case)
    return cases


_CASES = _load_cases() if _EVALS.is_dir() else []


def _frontmatter_of(path: Path) -> dict[str, Any]:
    fields, _body = rule_sync.split_markdown(path)
    return fields


def _model_invocable() -> set[str]:
    names = set()
    for path in (_CORPUS / "commands").glob("*.md"):
        fields = _frontmatter_of(path)
        if fields and fields.get("disable-model-invocation") is not True:
            names.add(path.stem)
    for path in (_CORPUS / "skills").glob("*/SKILL.md"):
        fields = _frontmatter_of(path)
        if fields and fields.get("disable-model-invocation") is not True:
            names.add(path.parent.name)
    names.update(
        p.stem for p in (_CORPUS / "agents").glob("*.md") if p.stem != "README"
    )
    return names - _USER_INVOKED_BY_DECISION


def _by_kind(kind: str) -> list[Case]:
    return [case for case in _CASES if case.kind == kind]


def _components(kind: str) -> set[str]:
    return {name for case in _by_kind(kind) for name in case.tag_values("component")}


def test_suite_exists() -> None:
    assert _EVALS.is_dir(), "evals/ is missing"
    assert _CASES, "evals/ holds no case (no prompt.md or case.yaml)"


def test_schema_is_a_valid_draft_2020_12_schema() -> None:
    Draft202012Validator.check_schema(json.loads(_SCHEMA.read_text(encoding="utf-8")))


def test_every_case_validates_against_the_schema() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    defs = schema["$defs"]

    def validator(name: str) -> Draft202012Validator:
        return Draft202012Validator({"$defs": defs, "$ref": f"#/$defs/{name}"})

    errors = []
    for case in _CASES:
        checks = [("promptFrontmatter", case.frontmatter)]
        if case.case_yaml is not None:
            checks.append(("caseYaml", case.case_yaml))
        checks.extend(("grader", grader) for grader in case.graders.values())
        for definition, instance in checks:
            errors.extend(
                f"{case.path.relative_to(_REPO)} [{definition}]: {error.message}"
                for error in validator(definition).iter_errors(instance)
            )
    assert not errors, "\n".join(errors)


def test_every_case_has_a_grader_a_prompt_and_a_unique_name() -> None:
    seen: dict[str, Path] = {}
    for case in _CASES:
        assert case.graders, f"{case.path}: a case without a grader fails to load"
        assert case.body.strip() or (case.case_yaml or {}).get("execution", {}).get(
            "prompt"
        ), case.path
        assert case.name == case.path.name, (
            f"{case.path}: keep the case name equal to its directory"
        )
        assert case.name not in seen, f"{case.name}: duplicate of {seen.get(case.name)}"
        seen[case.name] = case.path


def test_llm_graders_carry_a_rubric() -> None:
    for case in _CASES:
        for name, grader in case.graders.items():
            if grader["type"] == "llm":
                rubric = case.grader_bodies.get(name, "") or grader.get("criteria", "")
                message = f"{case.path}/{name}: state concrete PASS and FAIL conditions"
                assert re.search(r"\bPASS\b", rubric), message
                assert re.search(r"\bFAIL\b", rubric), message


def test_regex_patterns_compile_and_use_flags() -> None:
    for case in _CASES:
        for name, grader in case.graders.items():
            for key in ("pattern", "input_match"):
                pattern = grader.get(key)
                if pattern is None:
                    continue
                assert "(?i" not in pattern, (
                    f"{case.path}/{name}: put i in flags, not (?i)"
                )
                re.compile(pattern)


def test_scaffold_scripts_exist() -> None:
    for case in _CASES:
        script = ((case.case_yaml or {}).get("context") or {}).get("scaffold_script")
        if script is None:
            continue
        path = case.path / script
        assert path.is_file(), f"{case.path}: scaffold {script} missing"
        assert path.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash\n"), (
            path
        )


def test_model_invocable_components_have_trigger_and_no_trigger_cases() -> None:
    expected = _model_invocable()
    assert not expected - _components("trigger"), "missing should-trigger cases"
    assert not expected - _components("no-trigger"), "missing should-not-trigger cases"


def test_user_invoked_commands_have_no_auto_trigger_cases() -> None:
    assert _components("no-auto-trigger") >= _USER_INVOKED_BY_DECISION
    assert _components("no-trigger") >= _USER_INVOKED_BY_DECISION


def test_trigger_suite_size() -> None:
    trigger_kinds = ("trigger", "no-trigger", "no-auto-trigger")
    assert sum(len(_by_kind(kind)) for kind in trigger_kinds) >= 64


def test_trigger_graders_name_their_component() -> None:
    for kind in ("trigger", "no-trigger", "no-auto-trigger"):
        for case in _by_kind(kind):
            (component,) = case.tag_values("component")
            matches = [g.get("input_match", "") for g in case.graders.values()]
            assert any(component in m for m in matches), (
                f"{case.path}: grader names {component}"
            )
            assert f"/{component}" not in case.body, (
                f"{case.path}: phrase it as a user would"
            )


def test_never_fire_graders_score_in_both_arms() -> None:
    for case in _CASES:
        for name, grader in case.graders.items():
            if grader["type"] == "tool_used" and grader.get("max") == 0:
                assert grader.get("arm") == "both", f"{case.path}/{name}: set arm: both"
                assert grader.get("min") == 0, f"{case.path}/{name}: set min: 0"


@pytest.mark.parametrize(
    ("pipeline", "stages"),
    [
        ("plan", sorted(p.stem for p in (_CORPUS / "commands").glob("plan-*.md"))),
        (
            "research",
            sorted(p.stem for p in (_CORPUS / "commands").glob("research-*.md")),
        ),
        ("audit", sorted(_AUDIT_DIMENSIONS)),
    ],
)
def test_every_pipeline_stage_has_an_outcome_case(
    pipeline: str, stages: list[str]
) -> None:
    for stage in stages:
        assert (_CORPUS / "commands" / f"{stage}.md").is_file(), stage
    covered = {
        stage
        for case in _by_kind("outcome")
        if case.tag_values("pipeline") == [pipeline]
        for stage in case.tag_values("component")
    }
    assert set(stages) <= covered, (
        f"{pipeline}: no outcome case for {sorted(set(stages) - covered)}"
    )


def test_pipeline_stage_counts() -> None:
    assert len(list((_CORPUS / "commands").glob("plan-*.md"))) == 8
    assert len(list((_CORPUS / "commands").glob("research-*.md"))) == 13


def test_rule_effect_cases_are_paired() -> None:
    pairs: dict[str, dict[str, Case]] = {}
    for case in _by_kind("rule-effect"):
        (rule,) = case.tag_values("rule")
        (arm,) = case.tag_values("arm")
        assert "rule-scoping-regression" in case.tags, case.path
        assert arm not in pairs.setdefault(rule, {}), f"{rule}: two {arm} cases"
        pairs[rule][arm] = case
    assert len(pairs) >= 6, "sample at least six always-on rules"
    for rule, arms in pairs.items():
        assert set(arms) == {"rule-on", "rule-off"}, (
            f"{rule}: needs one rule-on and one rule-off case"
        )
        on, off = arms["rule-on"], arms["rule-off"]
        source = _frontmatter_of(_CORPUS / "rules" / f"{rule}.md")
        assert source.get("alwaysApply") is True, (
            f"{rule}: the rule-scoping set samples always-on rules"
        )
        assert on.frontmatter.get("append_system_prompt"), on.path
        assert "append_system_prompt" not in off.frontmatter, off.path
        assert on.body == off.body, (
            f"{rule}: the pair differs only by append_system_prompt"
        )
        assert on.graders == off.graders, f"{rule}: the pair is graded the same way"
        strip = {"append_system_prompt", "tags", "description"}
        assert {k: v for k, v in on.frontmatter.items() if k not in strip} == {
            k: v for k, v in off.frontmatter.items() if k not in strip
        }, f"{rule}: run limits and tools match across the pair"


def test_rule_on_text_matches_the_rule_source() -> None:
    drift = rule_sync.sync(_EVALS, _CORPUS / "rules", check=True)
    assert not drift, (
        "\n".join(drift) + "\nrun: python scripts/dev/sync_eval_rule_cases.py"
    )


def test_importing_the_sync_script_leaves_sys_path_alone() -> None:
    # This module imports the sync script; if the import put the vendored tree
    # first on sys.path, every later test in the same worker would load the
    # vendored jsonschema and yaml instead of the installed ones.
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); before = list(sys.path); "
        "import sync_eval_rule_cases; "
        "raise SystemExit(0 if sys.path == before else 1)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code, str(_SCRIPTS_DEV)],
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr.decode()


def test_results_are_not_committed() -> None:
    assert not (_EVALS / "results").exists(), (
        "evals/results/ is run output; keep it out of git"
    )
