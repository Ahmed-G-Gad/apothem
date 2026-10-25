# SPDX-License-Identifier: MIT

"""User-level skill folders shared by several installs.

Codex and the project-scope adapters write the same absolute folders in the
user home (``~/.agents/skills/``, ``~/.config/apothem/``). These tests drive the
real install, uninstall, rollback and verify paths over a small fake corpus and
hand-built rules, with the home isolated per test, and pin the shared-folder
rules: one emission whoever writes, the install ledger as the reference count,
foreign folders left alone, the user folder written before the project, and one
lock from the first write to the ledger record.
"""

from __future__ import annotations

import contextlib
import hashlib
import shutil
import threading
import time
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import MaterializationError
from apothem.harnesses._shared.install_driver_shared import holder_index, shared_scope
from apothem.lib import install_ledger
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget
from apothem.lib.propagation import HarnessRules, InstallEntry, user_home

_SKILL_ALPHA = """---
name: alpha
description: Alpha skill.
userInvocable: true
version: "1.0.0"
updated: 2026-10-24
archetype: procedure
portability: portable
allowed-tools: Read, Grep
---

# Alpha

Body of alpha.
"""

_SKILL_BETA = """---
name: beta
description: Beta skill.
disable-model-invocation: true
---

# Beta
"""

_COMMAND = """---
description: A command.
---

Run the command.
"""

_EXCLUDE = ["__pycache__", "*.pyc", "README.md", "AGENTS.md"]


def _user_entries() -> list[InstallEntry]:
    support = "${USER_HOME}/.config/apothem"
    return [
        InstallEntry("rules/", f"{support}/rules/", "merge_tree_entries"),
        InstallEntry("skills/", "${USER_HOME}/.agents/skills/", "native_skills"),
        InstallEntry("commands/", "${USER_HOME}/.agents/skills/", "command_skills"),
        InstallEntry("templates/", f"{support}/templates/", "merge_tree_entries"),
    ]


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake package corpus, and rules that give four harnesses user-level entries."""
    real = install_driver.APOTHEM_SRC
    package = tmp_path / "package"
    (package / "skills" / "alpha").mkdir(parents=True)
    (package / "skills" / "alpha" / "SKILL.md").write_text(_SKILL_ALPHA, "utf-8")
    (package / "skills" / "alpha" / "extra.txt").write_text("extra\n", "utf-8")
    (package / "skills" / "beta").mkdir()
    (package / "skills" / "beta" / "SKILL.md").write_text(_SKILL_BETA, "utf-8")
    (package / "commands").mkdir()
    (package / "commands" / "cmd-one.md").write_text(_COMMAND, "utf-8")
    (package / "commands" / "alpha.md").write_text(_COMMAND, "utf-8")  # shadowed
    (package / "rules").mkdir()
    (package / "rules" / "r1.md").write_text("# Rule\n", "utf-8")
    (package / "templates").mkdir()
    (package / "templates" / "t1.md").write_text("# Template\n", "utf-8")
    anchors = {
        "cursor": (
            "harnesses/cursor/templates/apothem-rules.mdc",
            "${PROJECT_ROOT}/.cursor/rules/apothem-rules.mdc",
        ),
        "github_copilot": (
            "harnesses/github_copilot/templates/copilot-instructions.md",
            "${PROJECT_ROOT}/.github/copilot-instructions.md",
        ),
        "zed": ("harnesses/zed/templates/apothem-rules.md", "${PROJECT_ROOT}/.rules"),
    }
    custom: dict[str, HarnessRules] = {}
    for name, (source, target) in anchors.items():
        (package / source).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(real / source, package / source)
        anchor = InstallEntry(source, target, "sentinel_merge", "operator-owned")
        custom[name] = HarnessRules(
            install=[*_user_entries(), anchor], exclude=_EXCLUDE, stale_sweep=[]
        )
    source = "harnesses/codex/templates/AGENTS.md"
    (package / source).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(real / source, package / source)
    codex_anchor = InstallEntry(
        source, "${HARNESS_ROOT}/AGENTS.md", "sentinel_merge", "operator-owned"
    )
    custom["codex"] = HarnessRules(
        install=[codex_anchor, *_user_entries()], exclude=_EXCLUDE, stale_sweep=[]
    )

    original = install_driver.load_rules
    monkeypatch.setattr(install_driver, "APOTHEM_SRC", package)
    monkeypatch.setattr(
        install_driver, "load_rules", lambda name: custom.get(name) or original(name)
    )
    return package


def _adapter(public_id: str):  # the adapter classes are generated
    return load_adapter_class(get_harness_entry(public_id))()


def _project(tmp_path: Path, name: str) -> Path:
    project = tmp_path / name
    project.mkdir()
    return project


def _install(public_id: str, project: Path):
    return _adapter(public_id).install({}, project=project)


def _uninstall(package_key: str, project: Path):
    return install_driver.run_uninstall(package_key, project_root=project)


def _codex_root() -> Path:
    return user_home() / ".codex"


def _install_codex():
    root = _codex_root()
    return install_driver.finalize_install(
        install_driver.run_install("codex", harness_root=root), root=root
    )


def _skills() -> Path:
    return user_home() / ".agents" / "skills"


def _names(directory: Path) -> set[str]:
    return {p.name for p in directory.iterdir()} if directory.is_dir() else set()


def _tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _home_tree() -> dict[str, str]:
    return {
        **{f".agents/{k}": v for k, v in _tree(user_home() / ".agents").items()},
        **{
            f".config/apothem/{k}": v
            for k, v in _tree(user_home() / ".config" / "apothem").items()
        },
    }


_FOLDERS = {"alpha", "beta", "cmd-one"}


def test_an_install_writes_the_user_folders_before_the_project(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "proj")
    run = _install("cursor", project)
    home = user_home()
    paths = [
        Path(result.path)
        for result in run.results
        if result.operation != "capability_projection"
    ]
    first_project = next(i for i, p in enumerate(paths) if project in p.parents)
    assert all(home in p.parents for p in paths[:first_project])
    assert paths[:first_project], "no user-level result precedes the project writes"
    assert _names(_skills()) == _FOLDERS
    assert (home / ".config" / "apothem" / "rules" / "r1.md").is_file()
    assert (home / ".config" / "apothem" / "templates" / "t1.md").is_file()
    assert (project / ".cursor" / "rules" / "apothem-rules.mdc").is_file()
    assert not (project / ".agents").exists()


def test_the_dry_run_and_diff_list_the_home_targets(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "proj")
    run = _adapter("cursor").preview({}, project=project)
    by_path = {Path(r.path): r for r in run.results}
    assert by_path[_skills()].outcome == "created"
    assert by_path[user_home() / ".config" / "apothem" / "rules"].outcome == "created"
    assert not _skills().exists()
    _install("cursor", project)
    again = _adapter("cursor").preview({}, project=project)
    assert {Path(r.path): r.outcome for r in again.results}[_skills()] == "unchanged"


def test_every_writer_emits_the_same_bytes_in_either_order(
    world: Path, tmp_path: Path
) -> None:
    _install_codex()
    _install("cursor", _project(tmp_path, "a"))
    codex_first = _home_tree()
    shutil.rmtree(user_home() / ".agents")
    shutil.rmtree(user_home() / ".config")
    _install("cursor", _project(tmp_path, "b"))
    cursor_first = _home_tree()
    assert codex_first == cursor_first
    assert ".agents/skills/alpha/SKILL.md" in codex_first
    assert ".agents/skills/beta/agents/openai.yaml" in codex_first


def test_a_second_installer_leaves_the_folders_unchanged(
    world: Path, tmp_path: Path
) -> None:
    _install_codex()
    run = _install("cursor", _project(tmp_path, "a"))
    skill_ops = {"native_skills", "command_skills", "merge_tree_entries"}
    outcomes = {r.outcome for r in run.results if r.operation in skill_ops}
    assert outcomes == {"unchanged"}


def test_uninstalling_the_registered_owner_keeps_what_another_install_holds(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    _install_codex()
    _install("cursor", project)
    results = install_driver.run_uninstall("codex", harness_root=_codex_root())
    assert _names(_skills()) == _FOLDERS
    retained = [r for r in results if r.operation == "shared_retained"]
    assert retained
    assert all(r.outcome == "unchanged" for r in retained)
    assert all("cursor" in r.message and str(project) in r.message for r in retained)
    assert not (_codex_root() / "AGENTS.md").exists()
    # The last holder takes the folders and tidies the directories it created.
    _uninstall("cursor", project)
    assert _names(_skills()) == set()
    assert not (user_home() / ".config" / "apothem" / "rules" / "r1.md").exists()


def test_removal_waits_for_the_last_holder_across_projects_and_harnesses(
    world: Path, tmp_path: Path
) -> None:
    a, b = _project(tmp_path, "a"), _project(tmp_path, "b")
    _install("cursor", a)
    _install("cursor", b)
    _install("github-copilot", a)
    _uninstall("cursor", a)
    assert _names(_skills()) == _FOLDERS
    _uninstall("github_copilot", a)
    assert _names(_skills()) == _FOLDERS
    _uninstall("cursor", b)
    assert _names(_skills()) == set()
    assert not (user_home() / ".config" / "apothem" / "rules" / "r1.md").exists()


def test_the_last_uninstall_tidies_the_directories_it_created(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    foreign = user_home() / ".agents" / "keep" / "note.txt"
    _install("cursor", project)
    foreign.parent.mkdir(parents=True)
    foreign.write_text("mine\n", "utf-8")
    _uninstall("cursor", project)
    assert foreign.is_file()  # a non-empty directory is never removed
    assert not _skills().exists()
    assert not (user_home() / ".config" / "apothem").exists()
    shutil.rmtree(user_home() / ".agents")
    other = _project(tmp_path, "b")
    _install("cursor", other)
    _uninstall("cursor", other)
    assert not (user_home() / ".agents").exists()
    assert user_home().is_dir()


def test_a_cursor_only_machine_verifies_and_a_deleted_folder_does_not(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    cursor = _adapter("cursor")
    cursor.install({}, project=project)
    assert cursor.verify(project=project) is True
    shutil.rmtree(_skills() / "beta")
    assert cursor.verify(project=project) is False
    cursor.install({}, project=project)
    assert cursor.verify(project=project) is True


def test_verify_passes_for_a_folder_another_adapter_wrote(
    world: Path, tmp_path: Path
) -> None:
    _install_codex()
    project = _project(tmp_path, "a")
    _install("zed", project)
    assert _adapter("zed").verify(project=project) is True


def test_is_installed_ignores_skills_without_a_managed_block(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    _install_codex()
    assert _names(_skills()) == _FOLDERS
    assert _adapter("cursor").is_installed(project=project) is False
    _install("cursor", project)
    assert _adapter("cursor").is_installed(project=project) is True


def test_a_foreign_folder_is_skipped_with_a_warning_and_fails_verify(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    foreign = _skills() / "alpha" / "SKILL.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("---\nname: alpha\ndescription: mine\n---\n", "utf-8")
    before = _tree(_skills() / "alpha")
    run = _install("cursor", project)
    conflicts = [r for r in run.results if r.operation == "skill_conflict"]
    assert [Path(r.path) for r in conflicts] == [_skills() / "alpha"]
    assert conflicts[0].outcome == "warning"
    assert "rename or move it" in conflicts[0].message
    assert _tree(_skills() / "alpha") == before
    assert _names(_skills()) == _FOLDERS  # the others are written
    assert (project / ".cursor" / "rules" / "apothem-rules.mdc").is_file()
    assert _adapter("cursor").verify(project=project) is False
    # The skipped folder is not Apothem's, so it is not recorded, and an
    # uninstall leaves it be.
    record = install_ledger.current_install_record("cursor", root=project)
    assert record is not None
    assert str(_skills() / "alpha") not in {t.path for t in record.targets}
    _uninstall("cursor", project)
    assert _tree(_skills() / "alpha") == before


def test_the_dry_run_reports_a_foreign_folder(world: Path, tmp_path: Path) -> None:
    project = _project(tmp_path, "a")
    foreign = _skills() / "alpha" / "SKILL.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("mine\n", "utf-8")
    run = _adapter("cursor").preview({}, project=project)
    assert [Path(r.path) for r in run.results if r.operation == "skill_conflict"] == [
        _skills() / "alpha"
    ]
    assert foreign.read_text("utf-8") == "mine\n"


def test_a_folder_that_already_matches_is_adopted(world: Path, tmp_path: Path) -> None:
    _install_codex()
    shutil.rmtree(install_ledger.STATE_ROOT)  # the ledger is lost
    project = _project(tmp_path, "a")
    run = _install("cursor", project)
    assert not [r for r in run.results if r.operation == "skill_conflict"]
    assert _adapter("cursor").verify(project=project) is True


def _legacy_codex_record(path: Path) -> None:
    """Record a pre-USER_HOME Codex install that listed *path* through ``..``."""
    root = _codex_root()
    root.mkdir(parents=True, exist_ok=True)
    legacy = root / ".." / ".agents" / "skills" / path.name
    install_ledger.append_record(
        LedgerRecord.create(
            harness="codex",
            root=root,
            kind="install",
            targets=(
                LedgerTarget(
                    str(legacy), "native_skills", "apothem-owned", outcome="created"
                ),
            ),
        )
    )


def test_a_folder_a_legacy_codex_record_lists_is_replaced_with_a_backup(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    old = _skills() / "alpha" / "SKILL.md"
    old.parent.mkdir(parents=True)
    old.write_text("old codex copy\n", "utf-8")
    _legacy_codex_record(old.parent)
    preview = _adapter("cursor").preview({}, project=project)
    by_path = {Path(r.path): r for r in preview.results}
    assert by_path[_skills()].outcome == "updated"
    run = _install("cursor", project)
    replaced = next(r for r in run.results if Path(r.path) == _skills() / "alpha")
    assert replaced.outcome == "updated"
    assert replaced.backup_path is not None
    assert "name: alpha" in (_skills() / "alpha" / "SKILL.md").read_text("utf-8")
    # The backup of a home file taken during a project install is keyed apart
    # from the project's own files.
    key = Path(replaced.backup_path).relative_to(install_driver.BACKUP_ROOT)
    assert key.parts[2] == "__home__"
    assert Path(*key.parts[2:]) == Path("__home__/.agents/skills/alpha")


def test_restoring_a_home_backup_never_writes_into_the_project(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    old = _skills() / "alpha" / "SKILL.md"
    old.parent.mkdir(parents=True)
    old.write_text("old codex copy\n", "utf-8")
    _legacy_codex_record(old.parent)
    run = _install("cursor", project)
    replaced = next(r for r in run.results if Path(r.path) == _skills() / "alpha")
    stamp = Path(replaced.backup_path or "").relative_to(install_driver.BACKUP_ROOT)
    results = install_driver.restore_backup(
        "cursor", stamp.parts[0], project_root=project
    )
    assert [r.outcome for r in results if r.operation == "restore_backup"]
    assert old.read_text("utf-8") == "old codex copy\n"
    assert not (project / ".agents").exists()


def test_a_default_codex_install_keeps_its_backup_layout(
    world: Path, tmp_path: Path
) -> None:
    old = _skills() / "alpha" / "SKILL.md"
    old.parent.mkdir(parents=True)
    old.write_text("old codex copy\n", "utf-8")
    _legacy_codex_record(old.parent)
    run = _install_codex()
    # run is the pass-through of finalize_install
    replaced = next(r for r in run.results if Path(r.path) == _skills() / "alpha")
    key = Path(replaced.backup_path or "").relative_to(install_driver.BACKUP_ROOT)
    assert key.parts[2:] == (".agents", "skills", "alpha")


def test_a_rules_only_era_record_removes_nothing_in_the_home(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    anchor = project / ".cursor" / "rules" / "apothem-rules.mdc"
    anchor.parent.mkdir(parents=True)
    anchor.write_text("anchor\n", "utf-8")
    install_ledger.append_record(
        LedgerRecord.create(
            harness="cursor",
            root=project,
            kind="install",
            targets=(LedgerTarget(str(anchor), "sentinel_merge", "operator-owned"),),
        )
    )
    mine = _skills() / "alpha" / "SKILL.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("operator skill\n", "utf-8")
    _uninstall("cursor", project)
    assert mine.read_text("utf-8") == "operator skill\n"


def _link_or_skip(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not permitted on this host")


def test_a_dotfile_link_inside_the_home_is_followed(
    world: Path, tmp_path: Path
) -> None:
    # ~/.agents and ~/.config are often links into a dotfiles folder in the home.
    project = _project(tmp_path, "a")
    agents = user_home() / "dotfiles" / "agents"
    config = user_home() / "dotfiles" / "config"
    agents.mkdir(parents=True)
    config.mkdir(parents=True)
    _link_or_skip(user_home() / ".agents", agents)
    _link_or_skip(user_home() / ".config", config)
    _install("cursor", project)
    assert _names(agents / "skills") == _FOLDERS
    assert (config / "apothem" / "rules" / "r1.md").is_file()
    assert (project / ".cursor" / "rules" / "apothem-rules.mdc").is_file()
    _uninstall("cursor", project)
    assert _names(agents / "skills") == set()


def test_a_link_leaving_the_home_aborts_before_the_project_changes(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    elsewhere = tmp_path / "outside-the-home"
    elsewhere.mkdir()
    _link_or_skip(user_home() / ".agents", elsewhere)
    with pytest.raises(MaterializationError, match="escapes"):
        _install("cursor", project)
    assert list(project.iterdir()) == []
    assert list(elsewhere.iterdir()) == []


def _read_as_links(monkeypatch: pytest.MonkeyPatch, *links: Path) -> None:
    real = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: self in links or real(self))


def test_links_at_or_above_a_user_folder_are_allowed(
    world: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The same as above without needing the privilege to create a real link.
    project = _project(tmp_path, "a")
    agents = user_home() / ".agents"
    agents.mkdir()
    _read_as_links(monkeypatch, agents, agents / "skills", user_home() / ".config")
    _install("cursor", project)
    assert _names(_skills()) == _FOLDERS


def test_a_link_below_a_user_folder_still_aborts_before_the_project_changes(
    world: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install("cursor", _project(tmp_path, "a"))
    _read_as_links(monkeypatch, user_home() / ".config" / "apothem" / "rules" / "r1.md")
    project = _project(tmp_path, "b")
    with pytest.raises(MaterializationError, match="symlink"):
        _install("zed", project)
    assert list(project.iterdir()) == []


def test_a_linked_skill_folder_is_foreign_and_left_alone(
    world: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path, "a")
    inner = _skills() / "alpha"
    inner.mkdir(parents=True)
    _read_as_links(monkeypatch, inner)
    run = _install("cursor", project)
    assert [r.path for r in run.results if r.operation == "skill_conflict"] == [
        str(inner)
    ]
    assert not (inner / "SKILL.md").exists()


def test_a_file_where_a_user_folder_belongs_aborts_with_the_path(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    blocker = user_home() / ".agents"
    blocker.write_text("a file where a folder belongs\n", "utf-8")
    with pytest.raises(MaterializationError, match="is not a folder") as raised:
        _install("cursor", project)
    assert str(blocker) in str(raised.value)
    assert list(project.iterdir()) == []


def test_a_rollback_keeps_folders_another_install_holds(
    world: Path, tmp_path: Path
) -> None:
    a, b = _project(tmp_path, "a"), _project(tmp_path, "b")
    _install("cursor", a)
    _install("zed", b)
    record = install_ledger.current_install_record("cursor", root=a)
    assert record is not None
    results = install_driver.rollback_install(
        record, harness_name="cursor", project_root=a
    )
    assert _names(_skills()) == _FOLDERS
    assert any(r.operation == "shared_retained" for r in results)
    assert not (a / ".cursor" / "rules" / "apothem-rules.mdc").exists()


def test_a_rollback_by_the_only_holder_removes_what_the_install_created(
    world: Path, tmp_path: Path
) -> None:
    a = _project(tmp_path, "a")
    _install("cursor", a)
    record = install_ledger.current_install_record("cursor", root=a)
    assert record is not None
    install_driver.rollback_install(record, harness_name="cursor", project_root=a)
    assert _names(_skills()) == set()
    assert not (user_home() / ".agents").exists()


def test_a_custom_codex_home_still_writes_the_user_home(
    world: Path, tmp_path: Path
) -> None:
    custom = tmp_path / "elsewhere" / ".codex-work"
    legacy = custom.parent / ".agents" / "skills" / "alpha"
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text("pre-existing copy\n", "utf-8")
    install_driver.finalize_install(
        install_driver.run_install("codex", harness_root=custom), root=custom
    )
    assert _names(_skills()) == _FOLDERS
    assert (legacy / "SKILL.md").read_text("utf-8") == "pre-existing copy\n"
    install_driver.run_uninstall("codex", harness_root=custom)
    assert _names(_skills()) == set()
    assert (legacy / "SKILL.md").read_text("utf-8") == "pre-existing copy\n"


def test_the_lock_spans_the_write_and_the_ledger_record(
    world: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = _project(tmp_path, "a"), _project(tmp_path, "b")
    _install("github-copilot", b)  # holds the folders, recorded
    written, proceed = threading.Event(), threading.Event()
    real_finalize = install_driver.finalize_install

    def slow_finalize(run, **kwargs):  # noqa: ANN003
        written.set()
        assert proceed.wait(20)
        return real_finalize(run, **kwargs)

    monkeypatch.setattr(install_driver, "finalize_install", slow_finalize)
    failures: list[BaseException] = []

    def run(action) -> None:
        try:
            action()
        except BaseException as exc:
            failures.append(exc)

    installing = threading.Thread(target=run, args=(lambda: _install("cursor", a),))
    # From the other install's view it is the last holder until cursor@a is recorded.
    removing = threading.Thread(
        target=run,
        args=(lambda: (written.wait(20), _uninstall("github_copilot", b)),),
    )
    installing.start()
    removing.start()
    assert written.wait(20)
    time.sleep(0.5)
    assert removing.is_alive(), "the uninstall ran while the install was unrecorded"
    proceed.set()
    installing.join(30)
    removing.join(30)
    assert not failures
    assert _names(_skills()) == _FOLDERS
    held = holder_index().holders_of(_skills() / "alpha")
    assert [h.harness for h in held] == ["cursor"]


def test_concurrent_installs_and_uninstalls_do_not_deadlock(
    world: Path, tmp_path: Path
) -> None:
    projects = {name: _project(tmp_path, name) for name in ("a", "b", "c")}
    errors: list[BaseException] = []

    def cycle(public_id: str, package_key: str, project: Path) -> None:
        try:
            for _ in range(2):
                _install(public_id, project)
                _uninstall(package_key, project)
        except BaseException as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=cycle, args=("cursor", "cursor", projects["a"])),
        threading.Thread(
            target=cycle, args=("github-copilot", "github_copilot", projects["b"])
        ),
        threading.Thread(target=cycle, args=("zed", "zed", projects["c"])),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(120)
    assert not any(thread.is_alive() for thread in threads)
    assert not errors
    # Every pair ended uninstalled, so nothing holds the folders any more.
    assert _names(_skills()) == set()


def test_the_scope_is_a_no_op_without_user_level_entries() -> None:
    assert isinstance(shared_scope("claude_code"), contextlib.nullcontext)
    assert not isinstance(shared_scope("codex"), contextlib.nullcontext)


def test_the_real_codex_manifest_installs_into_the_user_home(tmp_path: Path) -> None:
    root = tmp_path / "custom" / ".codex"
    run = install_driver.run_install("codex", harness_root=root)
    written = {Path(r.path) for r in run.results}
    assert user_home() / ".agents" / "skills" in {p.parent for p in written}
    assert not (tmp_path / "custom" / ".agents").exists()
    assert (user_home() / ".agents" / "skills").is_dir()
    assert (user_home() / ".config" / "apothem" / "rules").is_dir()


# --- an interrupted write, a rollback of every holder, an unreadable ledger ------


def _fail_the_write_of(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Make the safe-write primitive fail on the file *name* in a generated folder."""
    from apothem.harnesses._shared import install_driver_treeops as treeops
    from apothem.harnesses._shared.install_driver_types import _result

    real = treeops.write_bytes_safely

    def failing(target: Path, *args, **kwargs):  # noqa: ANN003
        if target.name == name:
            return _result("error", "native_skills", target, "disk full")
        return real(target, *args, **kwargs)

    monkeypatch.setattr(treeops, "write_bytes_safely", failing)


def test_a_failed_skill_write_leaves_no_half_written_folder(
    world: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path, "a")
    with monkeypatch.context() as patched:
        # alpha: SKILL.md is written, then extra.txt fails
        _fail_the_write_of(patched, "extra.txt")
        with pytest.raises(MaterializationError, match="disk full"):
            _install("cursor", project)
    assert list(project.iterdir()) == []
    assert "alpha" not in _names(_skills())
    assert not [n for n in _names(_skills()) if n.endswith(".apothem-staging")]
    # The retry finds nothing of its own to mistake for an operator's folder.
    run = _install("cursor", project)
    assert not [r for r in run.results if r.operation == "skill_conflict"]
    assert _names(_skills()) == _FOLDERS
    assert _adapter("cursor").verify(project=project) is True
    _uninstall("cursor", project)
    assert not (user_home() / ".agents").exists()


def test_a_staging_folder_an_interrupted_write_left_is_replaced_and_tidied(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    stale = _skills() / ".alpha.apothem-staging"
    stale.mkdir(parents=True)
    (stale / "SKILL.md").write_text("half\n", "utf-8")
    other = _skills() / ".gamma.apothem-staging"
    other.mkdir()
    _install("cursor", project)
    assert not stale.exists()  # the write of the same skill replaced it
    assert other.exists()  # a name that was not written again waits for the tidy
    _uninstall("cursor", project)
    assert not other.exists()
    assert not (user_home() / ".agents").exists()


def _rollback(package_key: str, project: Path) -> list:
    """Roll back the latest install the way the command does, record included."""
    record = install_ledger.current_install_record(package_key, root=project)
    assert record is not None
    results = install_driver.rollback_install(
        record, harness_name=package_key, project_root=project
    )
    if not any(r.outcome == "error" for r in results):
        install_ledger.append_record(
            LedgerRecord.create(
                harness=package_key,
                root=project,
                kind="rollback",
                targets=install_driver.backup_ledger_targets(results),
                install_id=record.install_id,
            )
        )
    return results


def test_rolling_back_every_holder_leaves_nothing_behind(
    world: Path, tmp_path: Path
) -> None:
    a, b = _project(tmp_path, "a"), _project(tmp_path, "b")
    _install("cursor", a)
    _install("zed", b)  # finds every folder in place: its outcomes are `unchanged`
    first = _rollback("cursor", a)
    assert any(r.operation == "shared_retained" for r in first)
    assert _names(_skills()) == _FOLDERS
    _rollback("zed", b)
    assert _names(_skills()) == set()
    assert not (user_home() / ".config" / "apothem" / "rules").exists()
    assert not (user_home() / ".agents").exists()


def test_rolling_back_a_later_install_keeps_the_folders_the_first_made(
    world: Path, tmp_path: Path
) -> None:
    a = _project(tmp_path, "a")
    _install("cursor", a)
    _install("cursor", a)  # a second pass over the same project: all `unchanged`
    _rollback("cursor", a)
    assert _names(_skills()) == _FOLDERS  # the first install still holds them
    _rollback("cursor", a)
    assert _names(_skills()) == set()


def _corrupt_ledger(package_key: str) -> Path:
    path = install_ledger.ledger_path(package_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json\n{}\n", encoding="utf-8")
    return path


def test_an_unreadable_ledger_of_an_unrelated_harness_does_not_block(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    _install("cursor", project)
    _corrupt_ledger("claude_code")
    results = _uninstall("cursor", project)
    assert not [r for r in results if r.outcome == "error"]
    assert _names(_skills()) == set()


def test_an_unreadable_ledger_stops_an_uninstall_before_it_changes_anything(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    _install("cursor", project)
    before = _home_tree()
    anchor = project / ".cursor" / "rules" / "apothem-rules.mdc"
    broken = _corrupt_ledger("zed")
    results = _uninstall("cursor", project)
    assert [r.outcome for r in results] == ["error"]
    assert "ledger could not be read" in results[0].message
    assert _home_tree() == before
    assert anchor.is_file()
    # The install is still recorded, so once the ledger is repaired the same
    # command finishes the job and the folders do not become orphans.
    broken.unlink()
    assert not [r for r in _uninstall("cursor", project) if r.outcome == "error"]
    assert _names(_skills()) == set()
    assert not anchor.exists()


def test_an_unreadable_ledger_stops_a_rollback_before_it_changes_anything(
    world: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    _install("cursor", project)
    before = _home_tree()
    broken = _corrupt_ledger("zed")
    results = _rollback("cursor", project)
    assert [r.outcome for r in results] == ["error"]
    assert _home_tree() == before
    broken.unlink()
    assert not [r for r in _rollback("cursor", project) if r.outcome == "error"]
    assert _names(_skills()) == set()


# --- content tokens in the shared corpus ------------------------------------------

_TOKENS = "root ${HARNESS_ROOT} project ${PROJECT_ROOT}\n"


def test_the_shared_corpus_leaves_content_tokens_unrendered_whoever_writes(
    world: Path, tmp_path: Path
) -> None:
    # The bytes of a user-level corpus file cannot depend on the installing
    # harness or project, or two installs would rewrite each other's copy.
    (world / "rules" / "tokens.md").write_text(_TOKENS, "utf-8")
    written = user_home() / ".config" / "apothem" / "rules" / "tokens.md"
    a, b = _project(tmp_path, "a"), _project(tmp_path, "b")
    _install("cursor", a)
    assert written.read_text("utf-8") == _TOKENS
    preview = _adapter("zed").preview({}, project=b)
    folder = {Path(r.path): r.outcome for r in preview.results}[written.parent]
    assert folder == "unchanged"
    run = _install("zed", b)
    assert {Path(r.path): r.outcome for r in run.results}[written] == "unchanged"
    assert written.read_text("utf-8") == _TOKENS
    codex = install_driver.run_install("codex", harness_root=_codex_root())
    assert {Path(r.path): r.outcome for r in codex.results}[written] == "unchanged"
    assert written.read_text("utf-8") == _TOKENS
