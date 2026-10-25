# SPDX-License-Identifier: MIT

"""The seven rules-file adapters install, update, verify and uninstall their skills.

Each adapter writes a rules file into the project and, ahead of it, the skills
and commands-as-skills in a user-level folder plus the rules and templates
corpus in ``~/.config/apothem/``. These tests drive the real manifest over the
real corpus with the user home isolated per test (``tests/conftest.py``), and
check the cross-adapter rule: every install that names a folder writes the same
bytes, and the install ledger decides which uninstall removes it.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import MaterializationError
from apothem.harnesses._shared.install_driver_layout import REFERENCE_NOTE_HEADING
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class
from apothem.lib.propagation import user_home

#: public id -> (home-relative skills folder, anchor path inside the project)
_ADAPTERS = {
    "cursor": (".agents/skills", ".cursor/rules/apothem-rules.mdc"),
    "github-copilot": (".agents/skills", ".github/copilot-instructions.md"),
    "windsurf": (".agents/skills", ".devin/rules/apothem-rules.md"),
    "zed": (".agents/skills", ".rules"),
    "codebuddy": (".codebuddy/skills", ".codebuddy/rules/apothem-rules.md"),
    "kiro": (".kiro/skills", ".kiro/steering/apothem-rules.md"),
    "trae": (".trae/skills", ".trae/rules/apothem-rules.md"),
}
_IDS = sorted(_ADAPTERS)
_CORPUS_EXCLUDED = {"README.md", "AGENTS.md"}


def _adapter(public_id: str):  # the adapter classes are generated
    return load_adapter_class(get_harness_entry(public_id))()


def _project(tmp_path: Path, name: str = "project") -> Path:
    project = tmp_path / name
    project.mkdir()
    return project


def _skills_dir(public_id: str) -> Path:
    return user_home() / _ADAPTERS[public_id][0]


def _corpus(name: str) -> Path:
    return user_home() / ".config" / "apothem" / name


def _expected_skill_names() -> set[str]:
    """The folder names an install writes: skills, plus commands no skill shadows."""
    src = install_driver.APOTHEM_SRC
    names = {path.parent.name for path in (src / "skills").glob("*/SKILL.md")}
    names |= {
        path.stem
        for path in (src / "commands").glob("*.md")
        if path.name not in _CORPUS_EXCLUDED
    }
    return names


def _folders(directory: Path) -> set[str]:
    if not directory.is_dir():
        return set()
    return {path.name for path in directory.iterdir() if path.is_dir()}


def _source_files(cohort: str) -> set[str]:
    root = install_driver.APOTHEM_SRC / cohort
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and path.name not in _CORPUS_EXCLUDED
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }


def _installed_files(directory: Path) -> set[str]:
    return {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _digest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _home_snapshot() -> dict[str, str]:
    """Every file below the user home, keyed by relative path."""
    return _digest(user_home())


def _top_level(project: Path) -> set[str]:
    return {path.name for path in project.iterdir()}


@pytest.mark.parametrize("public_id", _IDS)
def test_install_places_the_skills_the_corpus_and_the_anchor(
    public_id: str, tmp_path: Path
) -> None:
    folder, anchor = _ADAPTERS[public_id]
    project = _project(tmp_path)
    _adapter(public_id).install({}, project=project)

    skills = _skills_dir(public_id)
    assert _folders(skills) == _expected_skill_names()
    assert all((skills / name / "SKILL.md").is_file() for name in _folders(skills))
    assert _installed_files(_corpus("rules")) == _source_files("rules")
    assert _installed_files(_corpus("templates")) == _source_files("templates")

    # Only the folder this adapter documents is written; the others stay absent.
    for other in {f for f, _ in _ADAPTERS.values()} - {folder}:
        assert not (user_home() / other).exists(), other

    # The project gains the adapter's rules file and the data home it always had,
    # and no skills or corpus.
    assert (project / anchor).is_file()
    assert _top_level(project) <= {Path(anchor).parts[0], ".apothem"}
    assert not (project / ".agents").exists()
    assert not (project / folder).exists()


@pytest.mark.parametrize("public_id", _IDS)
def test_the_anchor_tells_the_model_where_the_skills_and_rules_are(
    public_id: str, tmp_path: Path
) -> None:
    folder, anchor = _ADAPTERS[public_id]
    project = _project(tmp_path)
    _adapter(public_id).install({}, project=project)

    text = (project / anchor).read_text(encoding="utf-8")
    flat = " ".join(text.split())
    assert f"`~/{folder}/`" in flat  # the skills, from the template prose
    assert "## Apothem support files" in text
    assert "- `rules/<path>` is `~/.config/apothem/rules/<path>`" in text
    assert "- `templates/<path>` is `~/.config/apothem/templates/<path>`" in text
    # Not specific to this machine, and no placeholder survives.
    assert user_home().as_posix() not in text
    assert str(user_home()) not in text
    assert "${" not in text
    assert "relative to this project" not in text


@pytest.mark.parametrize("public_id", _IDS)
def test_command_skills_carry_one_machine_independent_reference_note(
    public_id: str, tmp_path: Path
) -> None:
    _adapter(public_id).install({}, project=_project(tmp_path))
    notes = [
        text
        for skill in sorted(_skills_dir(public_id).glob("*/SKILL.md"))
        if REFERENCE_NOTE_HEADING in (text := skill.read_text(encoding="utf-8"))
    ]
    assert notes
    for text in notes:
        assert text.count(REFERENCE_NOTE_HEADING) == 1
        assert user_home().as_posix() not in text
        assert "`rules/<path>` is `~/.config/apothem/rules/<path>`" in text


@pytest.mark.parametrize("public_id", _IDS)
def test_dry_run_lists_the_home_targets_and_writes_nothing(
    public_id: str, tmp_path: Path
) -> None:
    folder, anchor = _ADAPTERS[public_id]
    project = _project(tmp_path)
    run = _adapter(public_id).preview({}, project=project)
    by_path = {Path(result.path): result.outcome for result in run.results}
    assert by_path[user_home() / folder] == "created"
    assert by_path[_corpus("rules")] == "created"
    assert by_path[_corpus("templates")] == "created"
    assert by_path[project / anchor] == "created"
    assert _home_snapshot() == {}
    assert list(project.iterdir()) == []


@pytest.mark.parametrize("public_id", _IDS)
def test_install_update_verify_and_uninstall_round_trip(
    public_id: str, tmp_path: Path
) -> None:
    folder, anchor = _ADAPTERS[public_id]
    project = _project(tmp_path)
    adapter = _adapter(public_id)
    assert adapter.is_installed(project=project) is False

    adapter.install({}, project=project)
    assert adapter.is_installed(project=project) is True
    assert adapter.verify(project=project) is True
    installed = _home_snapshot()

    # An update over an unchanged install rewrites nothing.
    update = adapter.update({}, project=project)
    user_level = [
        result
        for result in update.results
        if result.operation in {"native_skills", "command_skills", "merge_tree_entries"}
    ]
    assert user_level
    assert {result.outcome for result in user_level} == {"unchanged"}
    assert _home_snapshot() == installed

    # A folder removed by hand fails verify, and an update restores it.
    victim = sorted(_folders(_skills_dir(public_id)))[0]
    shutil.rmtree(_skills_dir(public_id) / victim)
    assert adapter.verify(project=project) is False
    adapter.update({}, project=project)
    assert adapter.verify(project=project) is True
    assert _home_snapshot() == installed

    # The only install that holds the folders removes them, and tidies up.
    adapter.uninstall(project=project)
    assert adapter.is_installed(project=project) is False
    assert not (user_home() / folder).exists()
    assert not (user_home() / Path(folder).parts[0]).exists()
    assert not (user_home() / ".config" / "apothem").exists()
    anchor_path = project / anchor
    assert not anchor_path.exists() or "APOTHEM MANAGED BLOCK" not in (
        anchor_path.read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("public_id", _IDS)
def test_a_failure_writing_the_user_folder_leaves_the_project_untouched(
    public_id: str, tmp_path: Path
) -> None:
    folder, _ = _ADAPTERS[public_id]
    project = _project(tmp_path)
    blocker = user_home() / Path(folder).parts[0]
    blocker.write_text("in the way\n", encoding="utf-8")  # a file where a folder goes
    # The error names the path in the way, not a raw platform traceback.
    with pytest.raises(MaterializationError, match="is not a folder") as raised:
        _adapter(public_id).install({}, project=project)
    assert str(blocker) in str(raised.value)
    assert list(project.iterdir()) == []


@pytest.mark.parametrize("public_id", ["cursor", "kiro"])
def test_a_foreign_skill_folder_is_skipped_and_kept(
    public_id: str, tmp_path: Path
) -> None:
    project = _project(tmp_path)
    foreign = _skills_dir(public_id) / "workflow"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("---\nname: workflow\n---\nmine\n", "utf-8")
    run = _adapter(public_id).install({}, project=project)
    conflicts = [r for r in run.results if r.operation == "skill_conflict"]
    assert len(conflicts) == 1
    assert conflicts[0].outcome == "warning"
    assert (foreign / "SKILL.md").read_text("utf-8").endswith("mine\n")
    # The other skills are still written, and verify reports the held name.
    assert "plan-generate" in _folders(_skills_dir(public_id))
    assert _adapter(public_id).verify(project=project) is False


def test_the_shared_agents_skills_copy_has_one_set_of_bytes_whoever_writes_it(
    tmp_path: Path,
) -> None:
    # Cursor alone, then the same folder written by every adapter that uses it.
    solo = _project(tmp_path, "solo")
    _adapter("cursor").install({}, project=solo)
    alone = _digest(user_home() / ".agents")
    assert alone

    for public_id in ("github-copilot", "windsurf", "zed"):
        run = _adapter(public_id).install(
            {}, project=_project(tmp_path, f"project-{public_id}")
        )
        outcomes = {
            result.outcome
            for result in run.results
            if result.operation in {"native_skills", "command_skills"}
        }
        assert outcomes == {"unchanged"}, public_id
    assert _digest(user_home() / ".agents") == alone


def test_codex_and_the_rules_adapters_write_the_same_agents_skills_bytes(
    tmp_path: Path,
) -> None:
    codex_root = user_home() / ".codex"
    install_driver.finalize_install(
        install_driver.run_install("codex", harness_root=codex_root), root=codex_root
    )
    codex_first = _digest(user_home() / ".agents")
    run = _adapter("zed").install({}, project=_project(tmp_path))
    assert {r.outcome for r in run.results if r.operation in {"native_skills"}} == {
        "unchanged"
    }
    assert _digest(user_home() / ".agents") == codex_first


def test_removal_waits_for_the_last_install_that_holds_the_agents_skills_folder(
    tmp_path: Path,
) -> None:
    a, b = _project(tmp_path, "a"), _project(tmp_path, "b")
    cursor, zed = _adapter("cursor"), _adapter("zed")
    cursor.install({}, project=a)
    zed.install({}, project=b)
    names = _expected_skill_names()

    cursor.uninstall(project=a)
    assert _folders(user_home() / ".agents" / "skills") == names
    assert _installed_files(_corpus("rules")) == _source_files("rules")
    assert zed.verify(project=b) is True
    assert not (a / ".cursor" / "rules" / "apothem-rules.mdc").exists()

    zed.uninstall(project=b)
    assert not (user_home() / ".agents").exists()
    assert not (user_home() / ".config" / "apothem").exists()


def test_adapters_with_their_own_folder_share_only_the_corpus(tmp_path: Path) -> None:
    a, b = _project(tmp_path, "a"), _project(tmp_path, "b")
    cursor, kiro = _adapter("cursor"), _adapter("kiro")
    cursor.install({}, project=a)
    kiro.install({}, project=b)
    assert _folders(user_home() / ".agents" / "skills") == _expected_skill_names()
    assert _folders(user_home() / ".kiro" / "skills") == _expected_skill_names()

    # Cursor's uninstall removes its own skills folder; the corpus stays for Kiro.
    cursor.uninstall(project=a)
    assert not (user_home() / ".agents").exists()
    assert _folders(user_home() / ".kiro" / "skills") == _expected_skill_names()
    assert _installed_files(_corpus("rules")) == _source_files("rules")
    assert _installed_files(_corpus("templates")) == _source_files("templates")
    assert kiro.verify(project=b) is True

    kiro.uninstall(project=b)
    assert not (user_home() / ".kiro").exists()
    assert not (user_home() / ".config" / "apothem").exists()


def test_two_projects_of_one_adapter_are_two_holders(tmp_path: Path) -> None:
    a, b = _project(tmp_path, "a"), _project(tmp_path, "b")
    trae = _adapter("trae")
    trae.install({}, project=a)
    trae.install({}, project=b)
    trae.uninstall(project=a)
    assert _folders(user_home() / ".trae" / "skills") == _expected_skill_names()
    assert trae.verify(project=b) is True
    trae.uninstall(project=b)
    assert not (user_home() / ".trae").exists()


def test_codex_uninstall_keeps_what_a_rules_adapter_still_holds(
    tmp_path: Path,
) -> None:
    codex_root = user_home() / ".codex"
    install_driver.finalize_install(
        install_driver.run_install("codex", harness_root=codex_root), root=codex_root
    )
    project = _project(tmp_path)
    _adapter("windsurf").install({}, project=project)
    results = install_driver.run_uninstall("codex", harness_root=codex_root)
    retained = [r for r in results if r.operation == "shared_retained"]
    assert retained
    assert _folders(user_home() / ".agents" / "skills") == _expected_skill_names()
    assert _adapter("windsurf").verify(project=project) is True
