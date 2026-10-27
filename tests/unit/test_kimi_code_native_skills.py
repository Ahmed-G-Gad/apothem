# SPDX-License-Identifier: MIT

"""Native skills layout of the kimi_code harness adapter.

Skills and commands (installed as skills) land in Kimi Code's native project
skills directory, ``<project>/.kimi-code/skills/``, and agents in its native
project agents directory, ``<project>/.kimi-code/agents/``. Hooks stay out of
Kimi Code's own locations, and an install made with the earlier layout (skills
in the support tree) is migrated by ``update`` and cleaned by ``uninstall``. The
agents move from the support tree is covered by
``tests/integration/test_kimi_devin_agents_roundtrip.py``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses.kimi_code import KimiCodeAdapter
from apothem.lib import propagation
from apothem.lib.harness_registry import get_harness_entry

_SRC = install_driver.APOTHEM_SRC
_KIMI = ".kimi-code"
_SUPPORT_SKILLS = Path(_KIMI) / ".apothem" / "support" / "skills"
_NATIVE_SKILLS = Path(_KIMI) / "skills"
_OPERATOR_SKILL = "my-own-skill"
_OPERATOR_FILE = "operator-notes.md"
_OPERATOR_FILE_TEXT = """Notes only the operator wrote.
"""


def _source_skills() -> list[str]:
    return sorted(
        child.name
        for child in (_SRC / "skills").iterdir()
        if (child / "SKILL.md").is_file()
    )


def _command_only_names() -> list[str]:
    """Return the commands no source skill shadows; each installs as a skill."""
    shadowed = set(_source_skills())
    return sorted(
        path.stem
        for path in (_SRC / "commands").glob("*.md")
        if path.name not in {"README.md", "AGENTS.md"} and path.stem not in shadowed
    )


def _skill_files(project: Path) -> list[Path]:
    """Return every ``SKILL.md`` under *project*, wherever it sits."""
    return sorted(project.rglob("SKILL.md"))


def _add_operator_skill(project: Path) -> Path:
    skill = project / _NATIVE_SKILLS / _OPERATOR_SKILL / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: my-own-skill\ndescription: Operator skill.\n---\n\nMine.\n",
        encoding="utf-8",
    )
    return skill


def _add_same_name_skill(project: Path) -> tuple[str, Path]:
    """Add an operator skill that shares its name with an Apothem skill.

    The operator skill carries a file of its own beside ``SKILL.md``, so a
    replacement shows in both the skill text and the directory contents.
    """
    name = _source_skills()[0]
    skill_dir = project / _NATIVE_SKILLS / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"""---
name: {name}
description: Operator skill.
---

Mine.
""",
        encoding="utf-8",
    )
    (skill_dir / _OPERATOR_FILE).write_text(_OPERATOR_FILE_TEXT, encoding="utf-8")
    return name, skill_dir


def _backed_up_operator_files() -> list[Path]:
    return list(install_driver.BACKUP_ROOT.rglob(_OPERATOR_FILE))


def _revert_to_support_tree_layout(project: Path) -> Path:
    """Rebuild the layout an install made before the native directory left.

    The earlier release wrote the same skill directories to
    ``.kimi-code/.apothem/support/skills/``; moving the native directory there
    reproduces its disk state.
    """
    legacy = project / _SUPPORT_SKILLS
    legacy.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(project / _NATIVE_SKILLS), str(legacy))
    return legacy


@pytest.fixture
def adapter() -> KimiCodeAdapter:
    return KimiCodeAdapter()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


def test_install_writes_the_native_layout(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    adapter.install({}, project=project)

    # Skills land in the native directory, one SKILL.md per skill, text
    # unchanged: the vendor's SKILL.md key policy is an open question
    # (TODO(clarify) in the convention pin), so no Kimi-specific translation
    # applies.
    native = project / _NATIVE_SKILLS
    for name in _source_skills():
        installed = native / name / "SKILL.md"
        assert installed.is_file(), name
        assert (
            installed.read_bytes() == (_SRC / "skills" / name / "SKILL.md").read_bytes()
        )
    # Each command no skill shadows lands beside them as a skill of its own.
    for name in _command_only_names():
        assert (native / name / "SKILL.md").is_file(), name

    # No skill and no agent remains in the support tree, which keeps the cohorts
    # that have no native install.
    assert not (project / _SUPPORT_SKILLS).exists()
    support = project / _KIMI / ".apothem" / "support"
    assert sorted(path.name for path in support.iterdir()) == [
        "hooks",
        "rules",
        "templates",
    ]

    # ``.agents/`` is shared with other tools, so it is never written; the agents
    # are native in ``.kimi-code/agents/`` and hooks stay out of Kimi Code's own
    # locations (pin: Open Questions).
    assert not (project / ".agents").exists()
    assert (project / _KIMI / "agents").is_dir()
    assert not list(project.rglob("*.toml"))
    assert sorted(path.name for path in (project / _KIMI).iterdir()) == [
        ".apothem",
        "agents",
        "skills",
    ]

    # The anchor points at the native directory, not the support tree.
    anchor = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert ".kimi-code/skills/" in anchor
    assert ".apothem/support/skills" not in anchor
    assert ".apothem/support/agents" not in anchor
    assert ".kimi-code/agents/" in anchor


def test_install_keeps_operator_skills_beside_apothem_skills(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    operator_skill = _add_operator_skill(project)
    text = operator_skill.read_text(encoding="utf-8")

    adapter.install({}, project=project)

    assert operator_skill.read_text(encoding="utf-8") == text


def test_install_replaces_a_same_name_operator_skill_after_a_backup(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    # The docs and the convention pin state this: only skills with other names
    # are kept. A skill named like an Apothem skill is replaced, and the
    # operator's copy survives in the backup tree.
    name, skill_dir = _add_same_name_skill(project)
    other = _add_operator_skill(project)
    other_text = other.read_text(encoding="utf-8")

    adapter.install({}, project=project)

    assert (skill_dir / "SKILL.md").read_bytes() == (
        _SRC / "skills" / name / "SKILL.md"
    ).read_bytes()
    assert not (skill_dir / _OPERATOR_FILE).exists()
    saved = _backed_up_operator_files()
    assert saved, "the replaced operator skill must be backed up first"
    assert saved[0].read_text(encoding="utf-8") == _OPERATOR_FILE_TEXT
    assert other.read_text(encoding="utf-8") == other_text


def test_update_replaces_a_same_name_operator_skill_after_a_backup(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    adapter.install({}, project=project)
    name = _source_skills()[0]
    skill_dir = project / _NATIVE_SKILLS / name
    (skill_dir / _OPERATOR_FILE).write_text(_OPERATOR_FILE_TEXT, encoding="utf-8")

    adapter.update({}, project=project)

    assert not (skill_dir / _OPERATOR_FILE).exists()
    saved = _backed_up_operator_files()
    assert saved, "the replaced skill directory must be backed up first"
    assert saved[0].read_text(encoding="utf-8") == _OPERATOR_FILE_TEXT


def test_install_is_idempotent(adapter: KimiCodeAdapter, project: Path) -> None:
    adapter.install({}, project=project)
    first = {
        path.relative_to(project).as_posix(): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }

    adapter.install({}, project=project)

    second = {
        path.relative_to(project).as_posix(): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }
    assert second == first


# ---------------------------------------------------------------------------
# update: migration from the support-tree layout
# ---------------------------------------------------------------------------


def test_update_migrates_support_tree_skills_to_the_native_directory(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    adapter.install({}, project=project)
    legacy = _revert_to_support_tree_layout(project)
    assert not (project / _NATIVE_SKILLS).exists()

    adapter.update({}, project=project)

    assert not legacy.exists()
    for name in _source_skills():
        assert (project / _NATIVE_SKILLS / name / "SKILL.md").is_file(), name
    # Each skill is present once, so Kimi Code loads none of them twice.
    names = [path.parent.name for path in _skill_files(project)]
    assert len(names) == len(set(names))
    anchor = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert ".apothem/support/skills" not in anchor


def test_update_backs_up_the_swept_support_tree_skills(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    adapter.install({}, project=project)
    legacy = _revert_to_support_tree_layout(project)
    marker = legacy / "legacy-only-skill" / "SKILL.md"
    marker.parent.mkdir()
    marker.write_text("---\nname: legacy-only-skill\n---\n", encoding="utf-8")

    adapter.update({}, project=project)

    assert not marker.exists()
    backups = list(install_driver.BACKUP_ROOT.rglob("legacy-only-skill"))
    assert backups, "the swept directory must be backed up first"


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


def test_uninstall_removes_the_native_skills_and_keeps_operator_skills(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    adapter.install({}, project=project)
    operator_skill = _add_operator_skill(project)

    adapter.uninstall(project=project)

    native = project / _NATIVE_SKILLS
    assert operator_skill.is_file()
    assert [path.name for path in native.iterdir()] == [_OPERATOR_SKILL]
    assert not (project / _KIMI / ".apothem").exists()
    assert not (project / "AGENTS.md").exists()


def test_uninstall_removes_a_same_name_skill_with_its_operator_files_after_a_backup(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    adapter.install({}, project=project)
    skill_dir = project / _NATIVE_SKILLS / _source_skills()[0]
    (skill_dir / _OPERATOR_FILE).write_text(_OPERATOR_FILE_TEXT, encoding="utf-8")

    adapter.uninstall(project=project)

    assert not skill_dir.exists()
    saved = _backed_up_operator_files()
    assert saved, "the removed skill directory must be backed up first"
    assert saved[0].read_text(encoding="utf-8") == _OPERATOR_FILE_TEXT


def test_uninstall_removes_an_empty_native_skills_directory_it_created(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    adapter.install({}, project=project)

    adapter.uninstall(project=project)

    assert not (project / _NATIVE_SKILLS).exists()


def test_uninstall_over_the_support_tree_layout_removes_its_skills(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    # An install from before the move, uninstalled without an update in between:
    # no install entry targets the support-tree skills directory any longer.
    adapter.install({}, project=project)
    legacy = _revert_to_support_tree_layout(project)
    assert legacy.is_dir()

    adapter.uninstall(project=project)

    assert not legacy.exists()
    assert not (project / _KIMI / ".apothem").exists()
    assert _skill_files(project) == []
    backups = list(install_driver.BACKUP_ROOT.rglob("SKILL.md"))
    assert backups, "the swept directory must be backed up first"


def test_uninstall_is_a_noop_for_a_project_without_an_install(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    (project / "notes.txt").write_text("keep\n", encoding="utf-8")

    adapter.uninstall(project=project)

    assert (project / "notes.txt").read_text(encoding="utf-8") == "keep\n"
    assert sorted(path.name for path in project.iterdir()) == ["notes.txt"]


# ---------------------------------------------------------------------------
# verify and detection
# ---------------------------------------------------------------------------


def test_verify_passes_after_install_and_fails_without_the_skills(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    adapter.install({}, project=project)
    assert adapter.verify(project=project) is True

    shutil.rmtree(project / _NATIVE_SKILLS)

    assert adapter.verify(project=project) is False


def test_support_tree_layout_reads_installed_but_unverified_until_updated(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    adapter.install({}, project=project)
    _revert_to_support_tree_layout(project)

    assert adapter.is_installed(project=project) is True
    assert adapter.verify(project=project) is False

    adapter.update({}, project=project)

    assert adapter.verify(project=project) is True


def test_preview_reports_the_native_directory_and_writes_nothing(
    adapter: KimiCodeAdapter, project: Path
) -> None:
    run = adapter.preview({}, project=project)

    assert run.dry_run is True
    assert not any(project.iterdir())
    targets = {Path(result.path).as_posix() for result in run.results}
    native = (project / _NATIVE_SKILLS).as_posix()
    assert any(target.startswith(native) for target in targets)


# ---------------------------------------------------------------------------
# manifest and registry
# ---------------------------------------------------------------------------


def test_manifest_targets_the_native_skills_directory() -> None:
    rules = propagation.load_manifest()["kimi_code"]
    by_source = {entry.source.rstrip("/"): entry for entry in rules.install}

    skills = by_source["skills"]
    commands = by_source["commands"]
    assert skills.target == commands.target == "${PROJECT_ROOT}/.kimi-code/skills/"
    assert skills.mode == "native_skills"
    assert commands.mode == "command_skills"
    assert skills.ownership_class == commands.ownership_class == "apothem-owned"
    # Agents install natively, in the tool-specific folder.
    agents = by_source["agents"]
    assert agents.target == "${PROJECT_ROOT}/.kimi-code/agents/"
    assert agents.mode == "kimi_agents"
    assert agents.ownership_class == "apothem-owned"
    # Cohorts with an open question or no native surface keep the support tree.
    for source in ("hooks", "rules", "templates"):
        assert by_source[source].target.startswith(
            "${PROJECT_ROOT}/.kimi-code/.apothem/support/"
        ), source


def test_manifest_never_writes_a_shared_or_user_scope_root() -> None:
    rules = propagation.load_manifest()["kimi_code"]

    for entry in rules.install:
        assert entry.target.startswith("${PROJECT_ROOT}/"), entry.target
        assert ".agents" not in entry.target, entry.target
        assert not entry.target.endswith(".toml"), entry.target


def test_manifest_sweeps_the_support_tree_skills_and_agents_directories() -> None:
    rules = propagation.load_manifest()["kimi_code"]

    assert ".kimi-code/.apothem/support/skills" in rules.stale_sweep
    assert ".kimi-code/.apothem/support/agents" in rules.stale_sweep
    # The sweep never names a live install target.
    live = {
        entry.target.removeprefix("${PROJECT_ROOT}/").rstrip("/")
        for entry in rules.install
    }
    assert not live & set(rules.stale_sweep)


def test_registry_records_the_native_skills_surface() -> None:
    entry = get_harness_entry("kimi-code")

    assert entry.capability_status["skills"] == "native"
    assert entry.capability_status["commands"] == "converted"
    assert entry.capability_status["hooks"] == "support-tree"
    assert entry.capability_status["agents"] == "converted"
    assert "<project>/.kimi-code/skills/" in entry.target_paths
    assert "<project>/.kimi-code/agents/" in entry.target_paths
