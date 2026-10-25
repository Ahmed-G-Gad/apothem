# SPDX-License-Identifier: MIT

"""The ``${USER_HOME}`` manifest placeholder and the rules that bound it.

A ``${USER_HOME}`` target is a folder in the user home that several installs
share, so the parser limits it to a closed set of folders, resolution never
leaves it as a literal, and plan validation refuses any target that still holds
a placeholder (a literal would be normalized against the working directory).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_planvalidation import (
    _validate_install_plan,
)
from apothem.harnesses._shared.install_driver_shared import (
    check_resolved_target,
    emission_name,
    entry_write_root,
)
from apothem.lib import propagation
from apothem.lib.propagation import (
    USER_LEVEL_PREFIXES,
    HarnessRules,
    InstallEntry,
    _parse_manifest_text,
    load_manifest,
    resolve_target,
    user_home,
    user_level_prefix,
)

_SKILLS = '"${USER_HOME}/.agents/skills/"'


def _block(*entries: str, project: bool = False) -> str:
    anchor = (
        "      - source: harnesses/x/templates/a.md\n"
        '        target: "${PROJECT_ROOT}/a.md"\n'
        "        mode: sentinel_merge\n"
        "        ownership_class: operator-owned\n"
        if project
        else ""
    )
    return "version: 1\nharnesses:\n  demo:\n    install:\n" + "".join(entries) + anchor


def _entry(target: str, mode: str, source: str, owner: str = "apothem-owned") -> str:
    return (
        f"      - source: {source}\n"
        f"        target: {target}\n"
        f"        mode: {mode}\n"
        f"        ownership_class: {owner}\n"
    )


def test_user_home_resolves_against_the_home() -> None:
    assert resolve_target("${USER_HOME}/.agents/skills/") == user_home() / (
        ".agents/skills"
    )


def test_user_home_follows_path_home_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert propagation.USER_HOME is None
    fixed = Path.home() / "elsewhere"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fixed))
    assert user_home() == fixed


def test_user_home_override_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(propagation, "USER_HOME", tmp_path)
    assert resolve_target("${USER_HOME}/x") == tmp_path / "x"


def test_user_home_never_survives_as_a_literal() -> None:
    resolved = resolve_target("${USER_HOME}/.agents/skills/", harness_root=None)
    assert "${" not in str(resolved)


def test_unknown_placeholders_still_raise() -> None:
    with pytest.raises(ValueError, match="unknown placeholder"):
        resolve_target("${USERHOME}/.agents/skills/")


def test_user_level_flag_follows_the_target() -> None:
    assert InstallEntry(
        "skills/", "${USER_HOME}/.agents/skills/", "native_skills"
    ).user_level
    assert not InstallEntry(
        "skills/", "${HARNESS_ROOT}/skills/", "native_skills"
    ).user_level


@pytest.mark.parametrize("prefix", sorted(USER_LEVEL_PREFIXES))
def test_every_allowed_prefix_is_recognised(prefix: str) -> None:
    assert user_level_prefix(f"${{USER_HOME}}/{prefix}/") == prefix
    assert user_level_prefix(f"${{USER_HOME}}/{prefix}") == prefix


@pytest.mark.parametrize(
    "template",
    [
        "${USER_HOME}/.ssh/",
        "${USER_HOME}/.agents/skills/../../.ssh/",
        "${USER_HOME}/.agents",
        "${USER_HOME}/.agents/skills/extra/",
        "${USER_HOME}/${HARNESS_ROOT}/.agents/skills/",
        "${HARNESS_ROOT}/${USER_HOME}/.agents/skills/",
        "${USER_HOME}.agents/skills/",
        "${USER_HOME}",
    ],
)
def test_parser_rejects_a_folder_outside_the_allowlist(template: str) -> None:
    text = _block(_entry(f'"{template}"', "native_skills", "skills/"))
    with pytest.raises(ValueError, match="user-level"):
        _parse_manifest_text(text)


def test_parser_accepts_the_allowed_folders() -> None:
    text = _block(
        _entry(_SKILLS, "native_skills", "skills/"),
        _entry(_SKILLS, "command_skills", "commands/"),
        _entry('"${USER_HOME}/.config/apothem/rules/"', "merge_tree_entries", "rules/"),
        _entry(
            '"${USER_HOME}/.config/apothem/templates/"',
            "merge_tree_entries",
            "templates/",
        ),
        project=True,
    )
    rules = _parse_manifest_text(text)["demo"]
    assert [entry.user_level for entry in rules.install] == [True] * 4 + [False]


@pytest.mark.parametrize("mode", ["write_text", "replace_tree", "sentinel_merge"])
def test_parser_rejects_a_user_level_target_on_the_wrong_mode(mode: str) -> None:
    text = _block(_entry(_SKILLS, mode, "skills/"))
    with pytest.raises(ValueError, match="not allowed for mode"):
        _parse_manifest_text(text)


def test_parser_rejects_a_skills_mode_on_a_support_folder() -> None:
    text = _block(
        _entry('"${USER_HOME}/.config/apothem/rules/"', "native_skills", "skills/")
    )
    with pytest.raises(ValueError, match="skills folder"):
        _parse_manifest_text(text)


def test_parser_rejects_a_support_mode_on_a_skills_folder() -> None:
    text = _block(_entry(_SKILLS, "merge_tree_entries", "rules/"))
    with pytest.raises(ValueError, match="support folder"):
        _parse_manifest_text(text)


def test_parser_rejects_a_source_that_does_not_match_the_folder() -> None:
    text = _block(_entry(_SKILLS, "native_skills", "agents/"))
    with pytest.raises(ValueError, match="source"):
        _parse_manifest_text(text)
    text = _block(
        _entry('"${USER_HOME}/.config/apothem/rules/"', "merge_tree_entries", "agents/")
    )
    with pytest.raises(ValueError, match="source"):
        _parse_manifest_text(text)


@pytest.mark.parametrize("owner", ["operator-owned", "generated", "vendor-reserved"])
def test_parser_requires_apothem_owned(owner: str) -> None:
    text = _block(_entry(_SKILLS, "native_skills", "skills/", owner))
    with pytest.raises(ValueError, match="apothem-owned"):
        _parse_manifest_text(text)


def test_parser_requires_one_target_for_skills_and_commands() -> None:
    text = _block(
        _entry(_SKILLS, "native_skills", "skills/"),
        _entry('"${USER_HOME}/.kiro/skills/"', "command_skills", "commands/"),
    )
    with pytest.raises(ValueError, match="share one target"):
        _parse_manifest_text(text)


def test_parser_puts_user_level_entries_first_in_a_project_block() -> None:
    anchor = _block(project=True).split("install:\n", 1)[1]
    text = (
        "version: 1\nharnesses:\n  demo:\n    install:\n"
        + anchor
        + _entry(_SKILLS, "native_skills", "skills/")
    )
    with pytest.raises(ValueError, match="before the project entries"):
        _parse_manifest_text(text)


def test_codex_skills_and_corpus_are_user_level() -> None:
    user_level = {
        entry.target.rstrip("/"): entry.mode
        for entry in load_manifest()["codex"].install
        if entry.user_level
    }
    assert user_level == {
        "${USER_HOME}/.agents/skills": "command_skills",
        "${USER_HOME}/.config/apothem/rules": "merge_tree_entries",
        "${USER_HOME}/.config/apothem/templates": "merge_tree_entries",
    }
    assert [
        entry.mode
        for entry in load_manifest()["codex"].install
        if entry.target.rstrip("/").endswith(".agents/skills")
    ] == ["native_skills", "command_skills"]


def test_no_project_block_names_the_harness_root() -> None:
    # A literal ${HARNESS_ROOT} in a project block would be normalized against
    # the working directory and write into the repository.
    for name, rules in load_manifest().items():
        targets = [entry.target for entry in rules.install]
        if any("${PROJECT_ROOT}" in target for target in targets):
            assert not any("${HARNESS_ROOT}" in target for target in targets), name


def test_plan_validation_fails_on_a_residual_placeholder(tmp_path: Path) -> None:
    rules = HarnessRules(
        install=[
            InstallEntry("rules/", "${HARNESS_ROOT}/rules/", "merge_tree_entries")
        ],
        exclude=[],
        stale_sweep=[],
    )
    errors = _validate_install_plan(
        rules, root=tmp_path, harness_root=None, project_root=tmp_path
    )
    assert [error.message for error in errors] == [
        "target still contains an unresolved placeholder"
    ]


def test_plan_validation_rechecks_a_user_level_target_against_the_home(
    tmp_path: Path,
) -> None:
    entry = InstallEntry("skills/", "${USER_HOME}/.agents/skills/", "native_skills")
    assert check_resolved_target(entry, resolve_target(entry.target)) is None
    elsewhere = tmp_path / "other"
    error = check_resolved_target(entry, elsewhere)
    assert error is not None
    assert "not an allowed folder" in error.message


def test_entry_write_root_is_the_home_for_user_level_entries(tmp_path: Path) -> None:
    skills = InstallEntry("skills/", "${USER_HOME}/.agents/skills/", "native_skills")
    anchor = InstallEntry("a.md", "${PROJECT_ROOT}/a.md", "sentinel_merge")
    assert entry_write_root(skills, None, tmp_path) == user_home().resolve()
    assert entry_write_root(anchor, None, tmp_path) == tmp_path.resolve()
    assert emission_name(skills, "cursor") == "shared_skills"
    assert emission_name(anchor, "cursor") == "cursor"


def test_build_plan_names_the_home_for_codex(tmp_path: Path) -> None:
    plan = install_driver.build_plan("codex", harness_root=tmp_path / ".codex")
    skills = [item for item in plan if item["mode"] == "native_skills"]
    assert Path(skills[0]["target"]) == user_home() / ".agents" / "skills"
