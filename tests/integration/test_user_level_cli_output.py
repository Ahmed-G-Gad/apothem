# SPDX-License-Identifier: MIT

"""What the CLI says about the shared user-home folders.

Seven project-scope adapters write skills, and the rules and templates they cite,
to folders in the user home that Codex and other installs write too. The CLI
tells the operator three things, and these tests pin each over the real
install, uninstall and verify paths with the home isolated per test:

* an install, update or dry run names the folders it writes outside ``--project``;
* an uninstall says which folders it kept because another install still uses
  them, and which it removed;
* a failed verify says which user-home folder is missing or is not Apothem's.

The fake corpus and rules come from ``test_user_level_folders.py``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.lib.propagation import user_home
from tests.integration.test_user_level_folders import world  # noqa: F401  # fixture

# The fake corpus and the rules that give four harnesses user-level entries.
pytestmark = pytest.mark.usefixtures("world")

_PROFILE = "identity:\n  name: Test User\nseriousness: PERSONAL_USE\n"
_FOLDERS = {"alpha", "beta", "cmd-one"}


@pytest.fixture
def profile(tmp_path: Path) -> Path:
    path = tmp_path / "profile.yaml"
    path.write_text(_PROFILE, encoding="utf-8")
    return path


def _project(tmp_path: Path, name: str) -> Path:
    project = tmp_path / name
    project.mkdir()
    return project


def _skills() -> Path:
    return user_home() / ".agents" / "skills"


def _invoke(*args: str):  # the Click result type is not exported
    return CliRunner().invoke(main, [*args, "--no-color"])


def _json(*args: str) -> tuple[int, dict[str, object]]:
    result = CliRunner().invoke(main, [*args, "--format", "json"])
    return result.exit_code, json.loads(result.output)


def _install(profile: Path, harness: str, project: Path | None = None) -> None:
    args = ["install", "--harness", harness, "--profile", str(profile)]
    if project is not None:
        args += ["--project", str(project)]
    result = _invoke(*args)
    assert result.exit_code == 0, result.output


def _advisories(
    payload: dict[str, object], operation: str, **match: object
) -> list[dict[str, object]]:
    warnings = payload["warnings"]
    assert isinstance(warnings, list)
    return [
        w
        for w in warnings
        if w.get("operation") == operation
        and all(w.get(key) == value for key, value in match.items())
    ]


def _uninstall(harness: str, project: Path | None = None) -> dict[str, object]:
    args = ["uninstall", "--harness", harness, "--yes"]
    if project is not None:
        args += ["--project", str(project)]
    code, payload = _json(*args)
    assert code == 0, payload
    return payload


# --- install, update and dry run ---------------------------------------------


def test_an_install_names_the_folders_it_writes_outside_the_project(
    profile: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    code, payload = _json(
        "install", "--harness", "cursor", "--profile", str(profile),
        "--project", str(project),
    )  # fmt: skip
    assert code == 0, payload
    [note] = _advisories(payload, "user_level_write", harness="cursor")
    home = user_home()
    assert set(note["paths"]) == {  # type: ignore[arg-type]
        str(home / ".agents" / "skills"),
        str(home / ".config" / "apothem" / "rules"),
        str(home / ".config" / "apothem" / "templates"),
    }
    message = str(note["message"])
    assert message.startswith("Cursor also writes outside --project: ~/")
    assert "~/.agents/skills/" in message
    assert "other tools that load them" in message
    assert str(home) not in message  # a copied report holds no username
    assert note["outcome"] == "advisory"


def test_the_plain_install_prints_the_note(profile: Path, tmp_path: Path) -> None:
    project = _project(tmp_path, "a")
    result = _invoke(
        "install", "--harness", "cursor", "--profile", str(profile),
        "--project", str(project),
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "Note: cursor - Cursor also writes outside --project: ~/" in flat
    assert "A write failure there stops this install before the project changes" in flat


def test_a_dry_run_and_an_update_say_it_too(profile: Path, tmp_path: Path) -> None:
    project = _project(tmp_path, "a")
    args = ["--harness", "cursor", "--profile", str(profile), "--project", str(project)]
    code, dry = _json("install", *args, "--dry-run")
    assert code == 0, dry
    assert _advisories(dry, "user_level_write", harness="cursor")
    assert not _skills().exists()  # a dry run writes nothing

    _install(profile, "cursor", project)
    code, updated = _json("update", *args)
    assert code == 0, updated
    assert _advisories(updated, "user_level_write", harness="cursor")


def test_a_harness_with_its_own_folder_says_it_is_shared_by_projects_only(
    profile: Path, tmp_path: Path
) -> None:
    from apothem.cli._user_level_report import user_level_write_advisory

    note = user_level_write_advisory("kiro")
    assert note is not None
    assert "~/.kiro/skills/" in str(note["message"])
    assert "shared by every project that installs it" in str(note["message"])
    assert "other tools" not in str(note["message"])
    assert user_level_write_advisory("claude-code") is None


def test_a_user_scope_install_has_no_outside_project_note(profile: Path) -> None:
    code, payload = _json("install", "--harness", "codex", "--profile", str(profile))
    assert code == 0, payload
    assert _advisories(payload, "user_level_write") == []


def test_the_holder_note_names_the_installs_using_the_folder_and_the_owner_of_record(
    profile: Path, tmp_path: Path
) -> None:
    _install(profile, "codex")
    project = _project(tmp_path, "a")
    code, payload = _json(
        "install", "--harness", "cursor", "--profile", str(profile),
        "--project", str(project),
    )  # fmt: skip
    assert code == 0, payload
    [holder] = _advisories(payload, "shared_root", role="holder", harness="cursor")
    assert holder["holders"] == ["codex", "cursor"]
    assert holder["owner_of_record"] == "codex"
    assert str(holder["message"]).endswith("Installs using it now: Codex, Cursor.")


def test_a_foreign_skill_folder_is_reported_as_a_warning(
    profile: Path, tmp_path: Path
) -> None:
    foreign = _skills() / "beta"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("mine\n", encoding="utf-8")
    project = _project(tmp_path, "a")
    code, payload = _json(
        "install", "--harness", "cursor", "--profile", str(profile),
        "--project", str(project),
    )  # fmt: skip
    assert code == 0, payload
    [conflict] = _advisories(payload, "skill_conflict", outcome="warning")
    assert conflict["harness"] == "cursor"
    assert conflict["path"] == str(foreign)
    assert "rename or move it, then run apothem update" in str(conflict["message"])
    assert (foreign / "SKILL.md").read_text(encoding="utf-8") == "mine\n"

    plain = _invoke(
        "install", "--harness", "cursor", "--profile", str(profile),
        "--project", str(project),
    )  # fmt: skip
    assert "Warning: cursor - skipped" in " ".join(plain.output.split())


# --- uninstall ---------------------------------------------------------------


def test_uninstalling_the_registered_owner_says_what_another_install_keeps(
    profile: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    _install(profile, "codex")
    _install(profile, "cursor", project)
    payload = _uninstall("codex")
    retained = _advisories(payload, "shared_root", role="retained")
    assert {a["path"] for a in retained} == {
        str(_skills()),
        str(user_home() / ".config" / "apothem" / "rules"),
        str(user_home() / ".config" / "apothem" / "templates"),
    }
    for advisory in retained:
        assert advisory["outcome"] == "advisory"
        assert advisory["harness"] == "codex"
        assert advisory["kept"] == advisory["total"]
        assert advisory["holders"] == [f"cursor ({project})"]
        assert "was kept: still used by cursor" in str(advisory["message"])
    assert {p.name for p in _skills().iterdir()} == _FOLDERS  # nothing moved

    last = _uninstall("cursor", project)
    released = _advisories(last, "shared_root", role="released")
    assert len(released) == 3
    assert all(
        "no other Apothem install uses it" in str(a["message"]) for a in released
    )
    assert not _skills().exists()


def test_uninstall_prints_the_notes_in_plain_mode(
    profile: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    _install(profile, "codex")
    _install(profile, "cursor", project)
    result = _invoke("uninstall", "--harness", "codex", "--yes")
    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "Uninstalled codex" in flat
    assert "Note: codex - ~/.agents/skills/ was kept: still used by cursor (" in flat
    last = " ".join(
        _invoke("uninstall", "--harness", "cursor", "--project", str(project), "--yes")
        .output.split()
    )  # fmt: skip
    assert "Note: cursor - ~/.agents/skills/ was removed: no other Apothem" in last


def test_two_projects_of_one_harness_release_only_at_the_last_uninstall(
    profile: Path, tmp_path: Path
) -> None:
    a, b = _project(tmp_path, "a"), _project(tmp_path, "b")
    _install(profile, "cursor", a)
    _install(profile, "cursor", b)
    first = _uninstall("cursor", a)
    [skills] = [
        n for n in _advisories(first, "shared_root", role="retained")
        if n["path"] == str(_skills())
    ]  # fmt: skip
    assert skills["holders"] == [f"cursor ({b})"]
    assert {p.name for p in _skills().iterdir()} == _FOLDERS
    second = _uninstall("cursor", b)
    assert {n["role"] for n in _advisories(second, "shared_root")} == {"released"}
    assert not _skills().exists()


def test_an_install_in_a_deleted_project_is_ignored_and_named(
    profile: Path, tmp_path: Path
) -> None:
    a, b = _project(tmp_path, "a"), _project(tmp_path, "b")
    _install(profile, "cursor", a)
    _install(profile, "cursor", b)
    shutil.rmtree(b)
    payload = _uninstall("cursor", a)
    [skills] = [
        n for n in _advisories(payload, "shared_root", role="released")
        if n["path"] == str(_skills())
    ]  # fmt: skip
    assert skills["stale"] == [f"cursor ({b})"]
    assert "no longer exists" in str(skills["message"])
    assert not _skills().exists()


def test_an_unreadable_ledger_keeps_the_folders_and_says_so(
    profile: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apothem.cli import _user_level_report as report

    project = _project(tmp_path, "a")
    _install(profile, "cursor", project)
    monkeypatch.setattr(report.LedgerView, "load", classmethod(lambda cls: None))
    preview = report.preview_uninstall("cursor", project)
    advisories = report.uninstall_advisories("cursor", preview)
    assert {a["role"] for a in advisories} == {"retained"}
    assert all("ledger could not be read" in str(a["message"]) for a in advisories)


def test_an_uninstall_without_an_install_record_says_nothing(
    profile: Path, tmp_path: Path
) -> None:
    from apothem.cli import _user_level_report as report

    project = _project(tmp_path, "a")
    assert report.preview_uninstall("cursor", project) is None
    assert report.uninstall_advisories("cursor", None) == []
    assert report.preview_uninstall("claude-code", project) is None


# --- verify ------------------------------------------------------------------


def test_verify_names_a_missing_skill_folder(profile: Path, tmp_path: Path) -> None:
    project = _project(tmp_path, "a")
    _install(profile, "cursor", project)
    args = ["verify", "--harness", "cursor", "--project", str(project)]
    assert _json(*args)[0] == 0

    shutil.rmtree(_skills() / "beta")
    code, payload = _json(*args)
    assert code != 0
    [row] = payload["results"]  # type: ignore[misc]
    assert row["verified"] is False
    assert row["user_level"]["missing"] == [str(_skills() / "beta")]
    assert row["user_level"]["unlisted"] == []
    assert "run apothem install to restore them" in row["message"]

    plain = _invoke(*args)
    assert plain.exit_code != 0
    assert "Note: 1 expected folder(s) are missing under ~/.agents/skills/" in " ".join(
        plain.output.split()
    )
    # install restores it, and verify passes again
    _install(profile, "cursor", project)
    assert _json(*args)[0] == 0


def test_verify_names_a_folder_no_apothem_install_lists(
    profile: Path, tmp_path: Path
) -> None:
    foreign = _skills() / "beta"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("mine\n", encoding="utf-8")
    project = _project(tmp_path, "a")
    _install(profile, "cursor", project)
    code, payload = _json("verify", "--harness", "cursor", "--project", str(project))
    assert code != 0
    [row] = payload["results"]  # type: ignore[misc]
    assert row["user_level"]["unlisted"] == [str(foreign)]
    assert "not listed by any Apothem install" in row["user_level"]["message"]
    assert "rename or move them, then run apothem update" in row["message"]


def test_a_failed_verify_without_a_user_home_cause_adds_nothing(
    profile: Path, tmp_path: Path
) -> None:
    project = _project(tmp_path, "a")
    _install(profile, "cursor", project)
    (project / ".cursor" / "rules" / "apothem-rules.mdc").unlink()
    code, payload = _json("verify", "--harness", "cursor", "--project", str(project))
    assert code != 0
    [row] = payload["results"]  # type: ignore[misc]
    assert "user_level" not in row
    assert row["message"] == "managed targets missing or invalid"
