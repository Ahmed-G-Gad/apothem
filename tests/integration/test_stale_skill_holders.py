# SPDX-License-Identifier: MIT

"""When an install whose folder is gone still vouches for a shared skill folder.

An install record vouches for the skill folders it lists in the user home while
its own folder is there and holds Apothem files. Otherwise it vouches only while
the skill folder holds exactly what it recorded. These tests pin what "live"
means (the folder answers and still holds one of the record's own files with
Apothem's content in it; a missing folder, an emptied one, one that keeps only
the operator's own file, and one on a drive that does not answer are not) and
what "exactly" means (no other file, no link). The fake corpus and rules come
from ``test_user_level_folders.py``.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared import install_driver_skillguard as skillguard
from apothem.lib import install_ledger
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget
from apothem.lib.propagation import user_home
from tests.integration.test_user_level_folders import (
    _SKILL_ALPHA,
    _adapter,
    _codex_root,
    _install,
    _install_codex,
    _project,
    _skills,
    _tree,
    world,  # noqa: F401  # fixture
)

pytestmark = pytest.mark.usefixtures("world")


def _dir_link(link: Path, target: Path) -> None:
    """Make *link* lead to the folder *target*: a symbolic link, or a junction."""
    target.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("this host cannot create a directory link")
        import _winapi

        _winapi.CreateJunction(str(target), str(link))


def _empty(project: Path) -> None:
    """Remove every Apothem file from *project* and keep the folder."""
    for child in project.iterdir():
        shutil.rmtree(child)


def _own_skill(folder: Path) -> dict[str, str]:
    """Replace *folder* with an operator skill of the same name; return its tree."""
    shutil.rmtree(folder)
    folder.mkdir()
    (folder / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: mine\n---\n", "utf-8"
    )
    return _tree(folder)


def _new_release() -> None:
    """Change alpha in the corpus, so the next install would rewrite the folder."""
    skill = install_driver.APOTHEM_SRC / "skills" / "alpha" / "SKILL.md"
    skill.write_text(_SKILL_ALPHA.replace("Body of alpha.", "New body."), "utf-8")


def _conflicts(run) -> list[Path]:  # the run type is internal
    """Return the skill folders *run* skipped with a ``skill_conflict`` warning."""
    return [Path(r.path) for r in run.results if r.operation == "skill_conflict"]


# --- an install folder that exists but holds no Apothem files ---------------


def test_an_emptied_project_counts_as_gone(tmp_path: Path) -> None:
    """A project folder with none of its recorded files left vouches for nothing."""
    emptied = _project(tmp_path, "emptied")
    _install("cursor", emptied)
    _empty(emptied)
    before = _own_skill(_skills() / "alpha")
    project = _project(tmp_path, "b")
    run = _install("cursor", project)
    assert _conflicts(run) == [_skills() / "alpha"]
    assert _tree(_skills() / "alpha") == before
    assert _adapter("cursor").verify(project=project) is False


def test_an_emptied_project_still_vouches_for_a_folder_as_it_wrote_it(
    tmp_path: Path,
) -> None:
    """Gone or emptied, the record still proves an unchanged folder."""
    emptied = _project(tmp_path, "emptied")
    _install("cursor", emptied)
    _empty(emptied)
    _new_release()
    run = _install("cursor", _project(tmp_path, "b"))
    assert _conflicts(run) == []
    assert "New body." in (_skills() / "alpha" / "SKILL.md").read_text("utf-8")


def test_a_project_with_one_recorded_file_left_still_vouches(tmp_path: Path) -> None:
    """One recorded file in place is enough: the install is still there."""
    kept = _project(tmp_path, "kept")
    _install("cursor", kept)
    shutil.rmtree(kept / ".apothem")  # data stores are not recorded targets
    assert (kept / ".cursor" / "rules" / "apothem-rules.mdc").is_file()
    _own_skill(_skills() / "alpha")
    run = _install("cursor", _project(tmp_path, "b"))
    assert _conflicts(run) == []
    replaced = next(r for r in run.results if Path(r.path) == _skills() / "alpha")
    assert replaced.outcome == "updated"
    assert replaced.backup_path is not None


def test_a_recorded_file_reached_through_a_link_does_not_count(
    tmp_path: Path,
) -> None:
    """A link inside the project is not the file Apothem wrote there."""
    linked = _project(tmp_path, "linked")
    _install("cursor", linked)
    elsewhere = tmp_path / "elsewhere-cursor"
    shutil.move(str(linked / ".cursor"), str(elsewhere))
    _dir_link(linked / ".cursor", elsewhere)
    assert (linked / ".cursor" / "rules" / "apothem-rules.mdc").is_file()
    before = _own_skill(_skills() / "alpha")
    run = _install("cursor", _project(tmp_path, "b"))
    assert _conflicts(run) == [_skills() / "alpha"]
    assert _tree(_skills() / "alpha") == before


def test_a_project_kept_behind_a_link_still_vouches(tmp_path: Path) -> None:
    """The install folder itself may be a link; the files behind it count."""
    linked = _project(tmp_path, "linked")
    _install("cursor", linked)
    real = tmp_path / "linked-real"
    shutil.move(str(linked), str(real))
    _dir_link(linked, real)
    _own_skill(_skills() / "alpha")
    run = _install("cursor", _project(tmp_path, "b"))
    assert _conflicts(run) == []
    replaced = next(r for r in run.results if Path(r.path) == _skills() / "alpha")
    assert replaced.outcome == "updated"


def test_holds_apothem_files_reads_only_the_record_s_own_targets(
    tmp_path: Path,
) -> None:
    """Root-local targets decide; a user-level target outside the root does not."""
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("a\n", "utf-8")
    (root / "sub" / "b.txt").write_text("b\n", "utf-8")
    shared = user_home() / ".agents" / "skills" / "alpha"
    shared.mkdir(parents=True)

    def record(*paths: Path) -> LedgerRecord:
        return LedgerRecord.create(
            harness="cursor",
            root=root,
            kind="install",
            targets=tuple(
                LedgerTarget(str(p), "write_text", "apothem-owned", outcome="created")
                for p in paths
            ),
        )

    both = record(root / "a.txt", root / "sub" / "b.txt", shared)
    assert skillguard.holds_apothem_files(root, both)
    (root / "a.txt").unlink()  # one recorded file left
    assert skillguard.holds_apothem_files(root, both)
    shutil.rmtree(root / "sub")  # none left; the shared folder does not count
    assert not skillguard.holds_apothem_files(root, both)
    # A record that lists nothing under its root leaves only the folder to go by.
    assert skillguard.holds_apothem_files(root, record(shared))


def test_an_operator_file_counts_only_while_it_shows_apothem_s_part(
    tmp_path: Path,
) -> None:
    """A file the operator owns counts by its recorded SHA-256, never by its name."""
    root = tmp_path / "root"
    root.mkdir()
    hooks = root / "hooks.json"
    hooks.write_text('{"hooks": {}}\n', "utf-8")
    digest = hashlib.sha256(hooks.read_bytes()).hexdigest()

    def record(ownership: str, digest: str | None) -> LedgerRecord:
        target = LedgerTarget(str(hooks), "native_hooks", ownership, digest=digest)
        return LedgerRecord.create(
            harness="cursor", root=root, kind="install", targets=(target,)
        )

    assert skillguard.holds_apothem_files(root, record("operator-owned", digest))
    # An earlier release recorded no digest: the name alone proves nothing.
    assert not skillguard.holds_apothem_files(root, record("operator-owned", None))
    # A file Apothem owns counts while it is there.
    assert skillguard.holds_apothem_files(root, record("apothem-owned", None))
    hooks.write_text('{"hooks": {"mine": []}}\n', "utf-8")  # the repository's own
    assert not skillguard.holds_apothem_files(root, record("operator-owned", digest))


def test_a_project_that_keeps_only_its_own_instructions_file_counts_as_gone(
    tmp_path: Path,
) -> None:
    """A re-cloned project keeps the file name, not Apothem's block in it."""
    cloned = _project(tmp_path, "cloned")
    instructions = cloned / ".github" / "copilot-instructions.md"
    instructions.parent.mkdir()
    instructions.write_text("# Team rules\n", "utf-8")
    _install("github-copilot", cloned)
    record = install_ledger.current_install_record("github_copilot", root=cloned)
    assert record is not None
    assert skillguard.holds_apothem_files(cloned, record)  # the block is there
    _empty(cloned)
    instructions.parent.mkdir()
    instructions.write_text("# Team rules\n", "utf-8")  # what the clone brings
    assert not skillguard.holds_apothem_files(cloned, record)
    before = _own_skill(_skills() / "alpha")
    run = _install("cursor", _project(tmp_path, "b"))
    assert _conflicts(run) == [_skills() / "alpha"]
    assert _tree(_skills() / "alpha") == before


def test_a_root_whose_files_cannot_be_read_is_not_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Python 3.10 and 3.11 raise ``PermissionError`` there; it proves nothing."""
    locked = _project(tmp_path, "locked")
    _install("cursor", locked)
    alpha = _skills() / "alpha"
    (alpha / "SKILL.md").write_text("edited\n", "utf-8")
    below = str(locked / ".cursor")
    record = install_ledger.current_install_record("cursor", root=locked)
    assert record is not None
    real_exists, real_is_symlink = Path.exists, Path.is_symlink

    def refuse(real):  # the Path method type is internal to pathlib
        def method(self: Path, *args: object, **kwargs: object) -> bool:
            if str(self).startswith(below):
                raise PermissionError(13, "access denied", str(self))
            return real(self, *args, **kwargs)

        return method

    monkeypatch.setattr(Path, "exists", refuse(real_exists))
    monkeypatch.setattr(Path, "is_symlink", refuse(real_is_symlink))
    assert not skillguard.holds_apothem_files(locked, record)
    conflict = skillguard.SkillGuard.load().check(alpha, matches=False)
    assert conflict is not None
    assert conflict.operation == "skill_conflict"


# --- a drive or share that does not answer ----------------------------------


def _stat_raising(monkeypatch: pytest.MonkeyPatch, path: Path, error: OSError) -> None:
    """Make ``Path.stat`` raise *error* for *path* alone."""
    real = Path.stat

    def stat(self: Path, *args: object, **kwargs: object):
        if self == path:
            raise error
        return real(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "stat", stat)


def test_a_root_on_a_drive_that_does_not_answer_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A drive or share whose root cannot be read leaves the folder unknown."""
    root = tmp_path / "on-a-share" / "project"
    anchor = Path(root.anchor)
    _stat_raising(monkeypatch, anchor, OSError(53, "network path not found"))
    assert skillguard.root_state(root) == "unknown"


def test_a_root_that_cannot_be_read_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A permission error on the folder itself proves neither way."""
    root = tmp_path / "locked"
    root.mkdir()
    _stat_raising(monkeypatch, root, PermissionError(13, "access denied"))
    assert skillguard.root_state(root) == "unknown"


def test_a_missing_root_on_a_reachable_drive_is_gone(tmp_path: Path) -> None:
    """Missing, a file in its place, or below a file: gone; a folder: present."""
    assert skillguard.root_state(tmp_path / "missing") == "gone"
    (tmp_path / "a-file").write_text("x\n", "utf-8")
    assert skillguard.root_state(tmp_path / "a-file") == "gone"
    assert skillguard.root_state(tmp_path / "a-file" / "below") == "gone"
    assert skillguard.root_state(tmp_path) == "present"


def _offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Install cursor in a project, then make its drive stop answering.

    The project stays on disk, so only the ``"unknown"`` answer keeps that
    install from vouching as a live one.
    """
    offline = _project(tmp_path, "offline")
    _install("cursor", offline)
    real = skillguard.root_state
    monkeypatch.setattr(
        skillguard,
        "root_state",
        lambda root: "unknown" if root == offline else real(root),
    )


def test_an_unreachable_root_does_not_vouch_for_an_edited_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An offline drive says nothing about the folder, so it is left alone."""
    _offline(tmp_path, monkeypatch)
    edited = _skills() / "alpha" / "SKILL.md"
    edited.write_text("edited\n", "utf-8")
    run = _install("cursor", _project(tmp_path, "b"))
    assert _conflicts(run) == [_skills() / "alpha"]
    assert edited.read_text("utf-8") == "edited\n"


def test_an_unreachable_root_still_vouches_for_a_folder_as_it_wrote_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Its record still proves an unchanged folder, so an update refreshes it."""
    _offline(tmp_path, monkeypatch)
    _new_release()
    run = _install("cursor", _project(tmp_path, "b"))
    assert _conflicts(run) == []
    assert "New body." in (_skills() / "alpha" / "SKILL.md").read_text("utf-8")


# --- what "exactly as recorded" means ---------------------------------------


def test_a_file_added_to_the_folder_makes_it_unproven(
    tmp_path: Path,
) -> None:
    """A replace would move the operator's file into the backup, so it is skipped."""
    gone = _project(tmp_path, "gone")
    _install("cursor", gone)
    shutil.rmtree(gone)
    note = _skills() / "alpha" / "my-notes.md"
    note.write_text("mine\n", "utf-8")
    before = _tree(_skills() / "alpha")
    _new_release()
    run = _install("cursor", _project(tmp_path, "b"))
    assert _conflicts(run) == [_skills() / "alpha"]
    assert _tree(_skills() / "alpha") == before


def test_a_linked_skill_folder_with_the_recorded_files_is_unproven(
    tmp_path: Path,
) -> None:
    """A gone install never vouches for a skill folder that is a link."""
    gone = _project(tmp_path, "gone")
    _install("cursor", gone)
    shutil.rmtree(gone)
    folder = _skills() / "alpha"
    elsewhere = user_home() / "kept-alpha"
    shutil.move(str(folder), str(elsewhere))
    _dir_link(folder, elsewhere)
    before = _tree(elsewhere)
    _new_release()
    run = _install("cursor", _project(tmp_path, "b"))
    assert _conflicts(run) == [folder]
    assert _tree(elsewhere) == before


def test_a_link_inside_the_skill_folder_makes_it_unproven(
    tmp_path: Path,
) -> None:
    """A link the install never wrote is not part of what it recorded."""
    gone = _project(tmp_path, "gone")
    _install("cursor", gone)
    shutil.rmtree(gone)
    folder = _skills() / "alpha"
    _dir_link(folder / "linked", tmp_path / "outside")
    _new_release()
    run = _install("cursor", _project(tmp_path, "b"))
    assert _conflicts(run) == [folder]
    assert (folder / "linked").exists()
    assert "Body of alpha." in (folder / "SKILL.md").read_text("utf-8")


# --- a project at the home folder, and one installed again in place ----------


def test_a_project_at_the_home_folder_does_not_stay_live_through_shared_folders(
    tmp_path: Path,
) -> None:
    """The shared skills and support folders under the home are not its files."""
    home = user_home()
    _install("cursor", home)
    record = install_ledger.current_install_record("cursor", root=home)
    assert record is not None
    assert skillguard.holds_apothem_files(home, record)
    shutil.rmtree(home / ".cursor")  # the project's own files are gone
    assert not skillguard.holds_apothem_files(home, record)
    before = _own_skill(_skills() / "alpha")
    run = _install("cursor", _project(tmp_path, "b"))
    assert _conflicts(run) == [_skills() / "alpha"]
    assert _tree(_skills() / "alpha") == before


def test_an_install_again_in_the_same_emptied_project_keeps_it_unproven(
    tmp_path: Path,
) -> None:
    """The new record does not list a skipped folder; the verdict stays unproven."""
    project = _project(tmp_path, "p1")
    _install("cursor", project)
    _empty(project)
    before = _own_skill(_skills() / "alpha")
    guard = skillguard.SkillGuard.load()
    assert guard.verdict(_skills() / "alpha") == skillguard.UNPROVEN
    for _ in range(2):  # the install, then an update in the same folder
        run = _install("cursor", project)
        assert _conflicts(run) == [_skills() / "alpha"]
        [conflict] = [r for r in run.results if r.operation == "skill_conflict"]
        assert "which Apothem cannot prove it wrote" in conflict.message
        guard = skillguard.SkillGuard.load()
        assert guard.verdict(_skills() / "alpha") == skillguard.UNPROVEN
    assert _tree(_skills() / "alpha") == before


def test_a_codex_install_after_its_folder_is_gone_keeps_the_operator_skill() -> None:
    """Codex's own writes in this run do not make its old record live again.

    The dry run and the install both judge ``~/.codex`` as it was before the
    install wrote into it, so both skip the folder.
    """
    _install_codex()
    shutil.rmtree(_codex_root())
    folder = _skills() / "alpha"
    before = _own_skill(folder)
    dry = install_driver.run_install("codex", harness_root=_codex_root(), dry_run=True)
    assert _conflicts(dry) == [folder]
    run = _install_codex()
    assert _conflicts(run) == [folder]
    assert _tree(folder) == before
    assert (_codex_root() / "AGENTS.md").is_file()


def test_an_earlier_record_that_proves_the_folder_lets_it_be_updated(
    tmp_path: Path,
) -> None:
    """A skipped folder put back as an earlier install wrote it is Apothem's again."""
    project = _project(tmp_path, "p1")
    _install("cursor", project)
    folder = _skills() / "alpha"
    written = {p.name: p.read_bytes() for p in folder.iterdir()}
    _empty(project)
    (folder / "SKILL.md").write_text("edited\n", "utf-8")
    run = _install("cursor", project)  # skipped: the new record does not list it
    assert _conflicts(run) == [folder]
    for name, data in written.items():
        (folder / name).write_bytes(data)
    assert skillguard.SkillGuard.load().verdict(folder) is None
    _new_release()
    run = _install("cursor", project)
    assert _conflicts(run) == []
    assert "New body." in (folder / "SKILL.md").read_text("utf-8")


def test_a_target_that_cannot_be_read_does_not_hide_the_next_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whatever order the record lists them in, a readable Apothem file counts."""
    root = tmp_path / "root"
    root.mkdir()
    locked = root / "rules.md"
    locked.write_text("text\n", "utf-8")
    owned = root / "owned.md"
    owned.write_text("apothem\n", "utf-8")
    targets = (
        LedgerTarget(str(locked), "sentinel_merge", "operator-owned"),
        LedgerTarget(str(owned), "write_text", "apothem-owned"),
    )
    real = Path.read_text

    def read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == locked:
            raise PermissionError(13, "access denied", str(self))
        return real(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", read_text)
    for order in (targets, targets[::-1]):
        record = LedgerRecord.create(
            harness="cursor", root=root, kind="install", targets=order
        )
        assert skillguard.holds_apothem_files(root, record)
