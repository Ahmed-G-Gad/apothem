# SPDX-License-Identifier: MIT

"""The CLI's report on the shared user-home folders, without an install.

``_user_level_report`` reads the install ledger and the manifest to say where an
install writes outside ``--project``, what an uninstall keeps, and why a verify
failed. These tests build the inputs by hand: manifest folders from the real
rules, and ledger views and previews from small values. The integration tests
(``tests/integration/test_user_level_cli_output.py``) cover the same messages
through the CLI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.cli import _user_level_report as report
from apothem.lib import install_ledger
from apothem.lib.propagation import user_home

_SEVEN = ("cursor", "github-copilot", "windsurf", "zed", "codebuddy", "kiro", "trae")


def _tilde_paths(harness_id: str) -> list[str]:
    return [
        "~/" + folder.relative_to(user_home()).as_posix()
        for folder in report.user_level_dirs(harness_id)
    ]


@pytest.mark.parametrize(
    ("harness_id", "skills"),
    [
        ("cursor", "~/.agents/skills"),
        ("github-copilot", "~/.agents/skills"),
        ("windsurf", "~/.agents/skills"),
        ("zed", "~/.agents/skills"),
        ("codex", "~/.agents/skills"),
        ("codebuddy", "~/.codebuddy/skills"),
        ("kiro", "~/.kiro/skills"),
        ("trae", "~/.trae/skills"),
    ],
)
def test_the_manifest_folders_are_the_skills_folder_and_the_corpus(
    harness_id: str, skills: str
) -> None:
    assert sorted(_tilde_paths(harness_id)) == sorted(
        [skills, "~/.config/apothem/rules", "~/.config/apothem/templates"]
    )


@pytest.mark.parametrize("harness_id", ["claude-code", "qwen-code", "glm", "hermes"])
def test_a_harness_without_user_level_entries_has_no_folders(harness_id: str) -> None:
    assert report.user_level_dirs(harness_id) == ()
    assert report.user_level_write_advisory(harness_id) is None
    assert report.preview_uninstall(harness_id, Path("anywhere")) is None


def test_only_project_scope_adapters_are_listed_as_shared_folder_writers() -> None:
    class ProjectScope:
        def resolve_output_path(self, project: Path | None) -> Path:
            return project or Path()

    class UserScope:
        output_path = Path("x")

    listed = report.shared_folders(
        [("cursor", ProjectScope()), ("codex", UserScope()), ("kiro", ProjectScope())]
    )
    assert [harness_id for harness_id, _ in listed] == ["cursor"] * 3 + ["kiro"] * 3
    assert {folder.name for _, folder in listed} == {"skills", "rules", "templates"}
    assert report.shared_folders([("codex", UserScope())]) == []


@pytest.mark.parametrize("harness_id", _SEVEN)
def test_the_write_note_names_each_folder_without_the_home_path(
    harness_id: str,
) -> None:
    note = report.user_level_write_advisory(harness_id)
    assert note is not None
    assert note["operation"] == "user_level_write"
    assert note["outcome"] == "advisory"
    assert len(note["paths"]) == 3  # type: ignore[arg-type]
    message = str(note["message"])
    assert str(user_home()) not in message
    for tilde in _tilde_paths(harness_id):
        assert f"{tilde}/" in message


def _use(**overrides: object) -> report.FolderUse:
    values: dict[str, object] = {
        "folder": user_home() / ".agents" / "skills",
        "total": 4,
        "kept": 0,
        "holders": (),
        "stale": (),
    }
    values.update(overrides)
    return report.FolderUse(**values)  # type: ignore[arg-type]


def _one(use: report.FolderUse, *, unreadable: bool = False) -> dict[str, object]:
    [advisory] = report.uninstall_advisories(
        "cursor", report.UninstallPreview((use,), unreadable)
    )
    return advisory


def test_no_preview_gives_no_advisory() -> None:
    assert report.uninstall_advisories("cursor", None) == []
    assert report.uninstall_advisories("cursor", report.UninstallPreview(())) == []


def test_a_folder_nothing_else_holds_is_reported_released() -> None:
    advisory = _one(_use())
    assert advisory["role"] == "released"
    assert advisory["message"] == (
        "~/.agents/skills/ was removed: no other Apothem install uses it."
    )
    assert advisory["operation"] == "shared_root"
    assert advisory["outcome"] == "advisory"
    assert advisory["harness"] == "cursor"
    assert advisory["path"] == str(user_home() / ".agents" / "skills")


def test_a_folder_another_install_holds_is_reported_retained() -> None:
    advisory = _one(_use(kept=4, holders=("zed (a)", "codex (b)")))
    assert advisory["role"] == "retained"
    assert advisory["message"] == (
        "~/.agents/skills/ was kept: still used by zed (a), codex (b). It is "
        "removed when the last Apothem install that uses it is uninstalled."
    )
    assert (advisory["kept"], advisory["total"]) == (4, 4)


def test_a_partly_held_folder_says_how_much_stayed() -> None:
    advisory = _one(_use(kept=1, holders=("zed (a)",)))
    assert advisory["role"] == "retained"
    assert advisory["message"] == (
        "~/.agents/skills/: kept 1 of 4 entries that zed (a) still use, and "
        "removed the rest."
    )


def test_many_holders_are_counted_not_listed() -> None:
    holders = tuple(f"cursor (p{n})" for n in range(5))
    message = str(_one(_use(kept=4, holders=holders))["message"])
    assert "cursor (p0), cursor (p1), cursor (p2) and 2 more." in message


def test_an_install_in_a_deleted_project_is_named_as_ignored() -> None:
    advisory = _one(_use(stale=("cursor (gone)",)))
    assert advisory["role"] == "released"
    assert advisory["stale"] == ["cursor (gone)"]
    assert str(advisory["message"]).endswith(
        "Ignored because its project folder no longer exists: cursor (gone)."
    )


def test_an_unreadable_ledger_never_reports_a_removal() -> None:
    advisory = _one(_use(total=0), unreadable=True)
    assert advisory["role"] == "retained"
    assert str(advisory["message"]).startswith("~/.agents/skills/ was kept: the ")
    assert "could not be read" in str(advisory["message"])


def test_holders_come_back_oldest_first_one_per_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills = user_home() / ".agents" / "skills"
    live = tmp_path / "live"
    live.mkdir()
    gone = tmp_path / "gone"

    def install(harness: str, root: Path, stamp: str) -> install_ledger.LedgerRecord:
        target = install_ledger.LedgerTarget(
            path=str(skills / "alpha"),
            mode="native_skills",
            ownership_class="apothem-owned",
        )
        return install_ledger.LedgerRecord(
            install_id=f"{harness}-{stamp}",
            timestamp=stamp,
            harness=harness,
            root=str(root),
            kind="install",
            targets=(target,),
        )

    records = {
        "zed": [install("zed", live, "2026-10-02")],
        "cursor": [
            install("cursor", live, "2026-10-03"),
            install("cursor", gone, "2026-10-01"),
        ],
        "codex": [install("codex", live, "2026-10-04")],
    }
    monkeypatch.setattr(
        install_ledger, "read_records", lambda key, **_kw: records.get(key, [])
    )
    monkeypatch.setattr(
        install_ledger,
        "current_install_record",
        lambda key, *, root, **_kw: next(
            (r for r in records.get(key, []) if r.root == str(root)), None
        ),
    )
    holders = report.ledger_holders()
    assert holders is not None
    # A project that is gone does not count; the order is by install time.
    assert holders(skills) == ["zed", "cursor", "codex"]
    assert holders(skills / "alpha") == ["zed", "cursor", "codex"]
    assert holders(user_home() / ".agents" / "other") == []


def test_an_unreadable_ledger_gives_no_holders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*_args: object, **_kw: object) -> list[object]:
        raise install_ledger.LedgerError("corrupt")

    monkeypatch.setattr(install_ledger, "read_records", broken)
    assert report.ledger_holders() is None
    preview = report.preview_uninstall("cursor", Path("p"))
    assert preview is not None
    assert preview.unreadable is True
    assert len(preview.uses) == 3
