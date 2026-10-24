# SPDX-License-Identifier: MIT

"""Qwen Code reads a skill's tool allow-list from ``allowedTools``, as an array.

Qwen Code reads the camelCase ``allowedTools`` frontmatter key and ignores the
hyphenated ``allowed-tools`` key other agents use; a value that is not an array
throws (``parseAllowedToolsField`` in ``packages/core/src/skills/types.ts`` at
v0.26.0, retrieved 2026-10-24). The source corpus writes ``allowed-tools`` as
one comma-separated string, so the ``qwen_code`` install rewrites it as a list.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared import install_driver
from apothem.lib.frontmatter import field_value
from apothem.lib.qwen_skill_frontmatter import translate_allowed_tools

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"


def _frontmatter(text: str) -> dict[str, object]:
    assert text.startswith("---\n")
    data = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    assert isinstance(data, dict)
    return data


def _skill(allowed: str) -> str:
    return f'---\nname: "demo"\n{allowed}\ndescription: "Demo."\n---\n\nBody.\n'


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('allowed-tools: "Read, Glob, Grep"', ["Read", "Glob", "Grep"]),
        ("allowed-tools: 'Read, Glob'", ["Read", "Glob"]),
        ("allowed-tools: Read, Glob", ["Read", "Glob"]),
        ('allowed-tools: "Read,Glob ,  Grep"', ["Read", "Glob", "Grep"]),
        ('allowed-tools: "Read" # why', ["Read"]),
        ("allowed-tools: Read # why", ["Read"]),
        ('allowed-tools: "Read, , Glob,"', ["Read", "Glob"]),
        ('allowed-tools: ""', []),
    ],
)
def test_scalar_becomes_a_list(line: str, expected: list[str]) -> None:
    emitted = translate_allowed_tools(_skill(line))
    meta = _frontmatter(emitted)
    assert meta["allowedTools"] == expected
    assert "allowed-tools" not in meta


def test_a_comma_inside_parentheses_stays_in_its_entry() -> None:
    line = 'allowed-tools: "Read, Bash(git log --format=a,b *), Glob"'
    meta = _frontmatter(translate_allowed_tools(_skill(line)))
    assert meta["allowedTools"] == ["Read", "Bash(git log --format=a,b *)", "Glob"]


def test_pattern_entries_are_carried_verbatim() -> None:
    line = 'allowed-tools: "Read, Bash(git status *), Bash(git diff *)"'
    meta = _frontmatter(translate_allowed_tools(_skill(line)))
    assert meta["allowedTools"] == ["Read", "Bash(git status *)", "Bash(git diff *)"]


def test_other_keys_and_body_are_byte_identical() -> None:
    source = _skill('allowed-tools: "Read, Glob"')
    emitted = translate_allowed_tools(source)
    kept = [line for line in source.split("\n") if not line.startswith("allowed-tools")]
    emitted_lines = emitted.split("\n")
    assert [line for line in emitted_lines if line in kept] == kept
    assert emitted.endswith("\n---\n\nBody.\n")


def test_key_position_is_kept() -> None:
    emitted = translate_allowed_tools(_skill('allowed-tools: "Read, Glob"'))
    assert list(_frontmatter(emitted)) == ["name", "allowedTools", "description"]


def test_a_flow_list_only_changes_its_key() -> None:
    emitted = translate_allowed_tools(_skill("allowed-tools: [Read, Glob]"))
    assert "allowedTools: [Read, Glob]\n" in emitted
    assert _frontmatter(emitted)["allowedTools"] == ["Read", "Glob"]


def test_a_block_list_only_changes_its_key() -> None:
    source = _skill("allowed-tools:\n  - Read\n  - Glob")
    emitted = translate_allowed_tools(source)
    assert _frontmatter(emitted)["allowedTools"] == ["Read", "Glob"]
    assert emitted == source.replace("allowed-tools:", "allowedTools:")


@pytest.mark.parametrize("indicator", [">", ">-", "|", "|-", ">+"])
def test_a_block_scalar_value_is_returned_unchanged(indicator: str) -> None:
    # The scalar's text sits on the lines below. Splitting the indicator would
    # break the YAML, and renaming only the key would hand Qwen Code a string it
    # rejects, so the hyphenated key (which Qwen Code ignores) stays as written.
    source = _skill(f"allowed-tools: {indicator}\n  Read,\n  Glob")
    emitted = translate_allowed_tools(source)
    assert emitted is source
    assert "allowed-tools" in _frontmatter(emitted)


def test_text_without_the_key_is_returned_unchanged() -> None:
    source = '---\nname: "demo"\ndescription: "Demo."\n---\n\nBody.\n'
    assert translate_allowed_tools(source) is source


def test_text_without_frontmatter_is_returned_unchanged() -> None:
    source = "allowed-tools: Read\n\nBody.\n"
    assert translate_allowed_tools(source) is source


def test_an_indented_key_inside_a_block_scalar_is_not_touched() -> None:
    source = '---\nname: "demo"\ndescription: |\n  allowed-tools: Read\n---\n\nBody.\n'
    assert translate_allowed_tools(source) is source


def test_the_body_is_never_touched() -> None:
    source = _skill('allowed-tools: "Read"') + 'allowed-tools: "Glob"\n'
    emitted = translate_allowed_tools(source)
    assert emitted.endswith('Body.\nallowed-tools: "Glob"\n')


def test_translation_is_idempotent() -> None:
    once = translate_allowed_tools(_skill('allowed-tools: "Read, Glob"'))
    assert translate_allowed_tools(once) == once


def test_an_existing_allowed_tools_key_is_kept_as_is() -> None:
    source = _skill('allowed-tools: "Read"').replace(
        'description: "Demo."', 'allowedTools: ["Glob"]\ndescription: "Demo."'
    )
    assert translate_allowed_tools(source) is source


def test_crlf_line_endings_are_kept() -> None:
    source = _skill('allowed-tools: "Read, Glob"').replace("\n", "\r\n")
    emitted = translate_allowed_tools(source)
    assert emitted.count("\r\n") == emitted.count("\n")
    assert _frontmatter(emitted.replace("\r\n", "\n"))["allowedTools"] == [
        "Read",
        "Glob",
    ]


def _source_skills() -> dict[str, Path]:
    return {
        p.parent.name: p
        for p in sorted((_PKG / "skills").glob("*/SKILL.md"))
        if field_value(p, "allowed-tools") is not None
    }


@pytest.fixture(scope="module")
def qwen_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    home = tmp_path_factory.mktemp("home")
    install_driver.run_install("qwen_code", harness_root=home / ".qwen")
    return home / ".qwen"


def test_installed_skills_carry_allowed_tools_as_a_list(qwen_home: Path) -> None:
    sources = _source_skills()
    assert sources, "corpus has no skill with an allow-list; the test would be vacuous"
    for name, source in sources.items():
        installed = _frontmatter(
            (qwen_home / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        )
        listed = installed.get("allowedTools")
        assert isinstance(listed, list), name
        assert "allowed-tools" not in installed, name
        assert all(isinstance(entry, str) for entry in listed), name
        # The corpus separates entries with ", ", so the list joins back to the
        # source string: no entry is lost, split inside a pattern, or reworded.
        original = _frontmatter(source.read_text(encoding="utf-8"))["allowed-tools"]
        assert ", ".join(listed) == original, name


def test_installed_skills_keep_every_other_key_and_the_body(qwen_home: Path) -> None:
    for name, source in _source_skills().items():
        original = source.read_text(encoding="utf-8")
        installed = (qwen_home / "skills" / name / "SKILL.md").read_text(
            encoding="utf-8"
        )
        before = _frontmatter(original)
        after = _frontmatter(installed)
        before.pop("allowed-tools")
        after.pop("allowedTools")
        assert after == before, name
        assert (
            installed[installed.index("\n---\n", 4) :]
            == original[original.index("\n---\n", 4) :]
        ), name


def test_support_files_beside_skill_md_are_copied_byte_for_byte(
    qwen_home: Path,
) -> None:
    compared = 0
    for source in sorted((_PKG / "skills").glob("*/**/*")):
        if not source.is_file() or source.name == "SKILL.md":
            continue
        relative = source.relative_to(_PKG / "skills")
        if any(part in {"__pycache__"} for part in relative.parts):
            continue
        installed = qwen_home / "skills" / relative
        assert installed.read_bytes() == source.read_bytes(), relative
        compared += 1
    assert compared


def test_reinstall_and_dry_run_report_unchanged(tmp_path: Path) -> None:
    root = tmp_path / ".qwen"
    install_driver.run_install("qwen_code", harness_root=root)
    run = install_driver.run_install("qwen_code", harness_root=root)
    outcomes = {r.outcome for r in run.results if r.operation == "native_skills"}
    assert outcomes == {"unchanged"}
    preview = install_driver.run_install("qwen_code", harness_root=root, dry_run=True)
    previewed = {r.outcome for r in preview.results if r.operation == "native_skills"}
    assert previewed == {"unchanged"}


def test_uninstall_removes_the_installed_skills(tmp_path: Path) -> None:
    root = tmp_path / ".qwen"
    install_driver.run_install("qwen_code", harness_root=root)
    assert list((root / "skills").glob("*/SKILL.md"))
    install_driver.run_uninstall("qwen_code", harness_root=root)
    assert not list((root / "skills").glob("*/SKILL.md"))
