# SPDX-License-Identifier: MIT

"""Follow-ups to the link-leaving-home refusals.

- ``install --clean`` writes the profile back only when the clean-slate step
  removed it, and through the same link check as every other profile write;
  a removal that stops partway still writes it back.
- A linked project root follows the rule in ``test_project_root_links.py``.
- The case-fold probe compares file identity, not mere existence, and the
  containment check keeps case until the probe says the folder folds it.
- ``uninstall`` refuses before it asks for confirmation, and the refusals name
  the link and where it leads.
- The clean-slate routine and the write guard share one link test.

Creating a symbolic link needs a privilege some Windows hosts lack, so there
each link is a junction, which the guards also see as a link.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.cli._helpers import (
    _CliUserError,
    _materialization_error,
    _refuse_profile_outside_home,
)
from apothem.harnesses._shared import install_driver_pathsafety as pathsafety
from apothem.harnesses._shared.install_driver import (
    MaterializationError,
    MaterializationRun,
)
from apothem.harnesses.codex import CodexAdapter
from apothem.lib import clean_slate, links
from apothem.lib.clean_slate import (
    LinkLeavingHomeError,
    RemovalError,
    run_clean_slate,
)

_phase = importlib.import_module("apothem.cli._clean_slate_phase")

_PROFILE = b"identity:\n  name: Ada Lovelace\n  email: ada@example.invalid\n"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    return folder


def _link(link: Path, target: Path) -> None:
    """Make *link* lead to *target*: a symbolic link, or a junction on Windows."""
    target.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("this host cannot create a directory link")
        import _winapi

        _winapi.CreateJunction(str(target), str(link))


def _install_clean(profile: Path, *extra: str) -> object:
    return CliRunner().invoke(
        main,
        [
            "install",
            "--harness",
            "claude-code",
            "--profile",
            str(profile),
            "--clean",
            "--yes",
            *extra,
        ],
    )


# -- item 1: the clean-slate profile restore --------------------------------


def test_clean_leaves_a_profile_behind_a_link_out_of_the_home_alone(
    home: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside" / "ext"
    _link(home / "ext", outside)
    (outside / "profile.yaml").write_bytes(_PROFILE)
    before = (outside / "profile.yaml").stat()

    result = _install_clean(home / "ext" / "profile.yaml")

    assert result.exit_code == 0, result.output
    after = (outside / "profile.yaml").stat()
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
    assert (outside / "profile.yaml").read_bytes() == _PROFILE


def test_clean_does_not_rewrite_a_profile_it_did_not_remove(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = tmp_path / "elsewhere" / "profile.yaml"
    profile.parent.mkdir()
    profile.write_bytes(_PROFILE)
    writes: list[Path] = []
    monkeypatch.setattr(
        _phase, "write_bytes_atomically", lambda path, data: writes.append(path)
    )

    result = _install_clean(profile)

    assert result.exit_code == 0, result.output
    assert writes == []
    assert profile.read_bytes() == _PROFILE


def test_clean_restores_a_profile_it_removed(home: Path) -> None:
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_bytes(_PROFILE)

    result = _install_clean(profile)

    assert result.exit_code == 0, result.output
    assert profile.read_bytes() == _PROFILE


def test_a_refused_restore_names_the_copy_that_holds_the_profile(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_bytes(_PROFILE)

    def _refuse(path: Path) -> None:
        raise _CliUserError(
            code="profile.write_failed",
            message="refused",
            field="profile",
            reason="target path crosses a symlink: L leads outside",
            fix="-",
        )

    monkeypatch.setattr(_phase, "_refuse_profile_outside_home", _refuse)

    result = _install_clean(profile, "--format", "json")

    assert result.exit_code == 1, result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "clean_slate.profile_restore_refused"
    assert "crosses a symlink" in error["reason"]
    saved = re.search(r"saved at (.+?profile\.yaml)\. ", error["fix"])
    assert saved, error["fix"]
    assert Path(saved.group(1)).read_bytes() == _PROFILE
    # Copying the file back to its path would go through the refused link.
    assert "Copy it back to" not in error["fix"]
    assert "Replace that link with a real folder" in error["fix"]
    assert not (home / ".claude" / "settings.json").exists()


def test_the_real_link_check_refuses_a_restore_through_a_new_link(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The clean-slate step removed the profile, then ~/.config/apothem became
    # a link out of the home before the restore: the real check refuses it.
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_bytes(_PROFILE)
    outside = tmp_path / "outside" / "apothem"
    real_run = run_clean_slate

    def _run_then_link(*args: object, **kwargs: object) -> object:
        result = real_run(*args, **kwargs)  # type: ignore[arg-type]
        _link(home / ".config" / "apothem", outside)
        return result

    monkeypatch.setattr(_phase, "run_clean_slate", _run_then_link)

    result = _install_clean(profile, "--format", "json")

    assert result.exit_code == 1, result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "clean_slate.profile_restore_refused"
    assert list(outside.iterdir()) == []


def test_a_removal_that_stops_partway_restores_the_profile(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_bytes(_PROFILE)
    (home / ".claude").mkdir()
    real_remove = clean_slate._remove_path

    def _remove(path: Path) -> None:
        if path.name == ".claude":
            raise PermissionError(13, "in use", str(path))
        real_remove(path)

    monkeypatch.setattr(clean_slate, "_remove_path", _remove)
    # The profile goes first, so the failure comes after it is gone.
    order = [home / ".config" / "apothem", home / ".claude"]
    monkeypatch.setattr(clean_slate, "bounded_targets", lambda _home: order)

    result = _install_clean(profile, "--format", "json")

    assert result.exit_code == 1, result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "clean_slate.removal_failed"
    assert str(home / ".claude") in error["reason"]
    assert "backups" in error["fix"]
    assert profile.read_bytes() == _PROFILE


def test_run_clean_slate_names_the_backup_when_a_removal_fails(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (home / ".claude").mkdir()
    (home / ".claude" / "keep.txt").write_text("x", encoding="utf-8")

    def _remove(path: Path) -> None:
        raise PermissionError(13, "in use", str(path))

    monkeypatch.setattr(clean_slate, "_remove_path", _remove)

    with pytest.raises(RemovalError) as caught:
        run_clean_slate(home, assume_yes=True)

    backup = caught.value.backup_dir
    assert backup is not None
    assert (backup / ".claude" / "keep.txt").read_text(encoding="utf-8") == "x"


def test_the_spare_copy_is_written_when_the_backup_lacks_the_profile(
    tmp_path: Path,
) -> None:
    backup = tmp_path / "backup"
    backup.mkdir()
    result = clean_slate.CleanSlateResult(
        dry_run=False, backup_dir=backup, dispositions=()
    )

    copy = _phase._profile_copy(tmp_path / "x" / "profile.yaml", _PROFILE, result)

    assert copy == backup / "profile.yaml.not-restored"
    assert copy.read_bytes() == _PROFILE


def test_a_clean_slate_link_refusal_gives_a_link_fix(
    home: Path, tmp_path: Path
) -> None:
    _link(home / ".config", tmp_path / "outside" / "config")
    profile = tmp_path / "profile.yaml"
    profile.write_bytes(_PROFILE)

    result = _install_clean(profile, "--format", "json")

    assert result.exit_code == 1, result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "clean_slate.refused"
    assert "Replace the link" in error["fix"]
    assert str(home / ".config") in error["fix"]
    assert "interactively" not in error["fix"]


def test_run_clean_slate_names_the_link(home: Path, tmp_path: Path) -> None:
    _link(home / ".config", tmp_path / "outside" / "config")

    with pytest.raises(LinkLeavingHomeError) as caught:
        run_clean_slate(home, assume_yes=True)

    assert caught.value.link == home / ".config"
    assert isinstance(caught.value, clean_slate.UnsafeRootError)


# -- the restore fix and the profile refusal name where a link leads --------


def test_a_failed_restore_through_a_broken_link_says_it_is_broken(
    home: Path,
) -> None:
    # --profile reaches ~/.config/apothem through ~/prof; the clean-slate step
    # removes that folder, so the restore through ~/prof cannot be written.
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_bytes(_PROFILE)
    _link(home / "prof", home / ".config" / "apothem")
    alias = home / "prof" / "profile.yaml"

    result = _install_clean(alias, "--format", "json")

    assert result.exit_code == 1, result.output
    error = json.loads(result.output)["error"]
    assert error["code"] == "clean_slate.profile_restore_failed"
    assert f"The link {home / 'prof'} is broken" in error["fix"]
    assert "which does not exist" in error["fix"]
    assert f"Copy it back to {alias}" not in error["fix"]


def test_the_copy_back_fix_names_the_file_a_link_leads_to(home: Path) -> None:
    real = home / "dots" / "apothem"
    _link(home / "prof", real)
    copy = home / "backup" / "profile.yaml"

    fix = _phase._copy_back_fix(copy, home / "prof" / "profile.yaml")

    target = (real / "profile.yaml").resolve()
    assert f"Copy it back to {target}, where the link {home / 'prof'} leads" in fix


def test_the_copy_back_fix_names_a_missing_folder_below_a_working_link(
    home: Path,
) -> None:
    # ~/prof leads to ~/.config, which exists; only ~/.config/apothem, below
    # it, is gone. The link is not broken.
    config = home / ".config"
    config.mkdir()
    _link(home / "prof", config)

    fix = _phase._copy_back_fix(
        home / "copy.yaml", home / "prof" / "apothem" / "x.yaml"
    )

    real = config.resolve() / "apothem"
    assert "is broken" not in fix
    assert f"Create the folder {real}, then copy it back to {real / 'x.yaml'}" in fix
    assert f"where the link {home / 'prof'} leads" in fix


def test_the_copy_back_fix_without_a_link_names_the_profile_path(
    home: Path,
) -> None:
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)

    fix = _phase._copy_back_fix(home / "copy.yaml", profile)

    assert f"Copy it back to {profile}, or pass --profile PATH" in fix


def test_the_profile_refusal_names_where_the_link_leads(
    home: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside" / "config"
    _link(home / ".config", outside)

    with pytest.raises(_CliUserError) as caught:
        _refuse_profile_outside_home(home / ".config" / "apothem" / "profile.yaml")

    reason = caught.value.reason
    assert f"{home / '.config'} is a link to {outside.resolve()}" in reason
    assert "outside your home directory" in reason


# -- item 3: the case-fold probe ---------------------------------------------


def test_case_probe_reads_a_missing_swapped_name_as_case_sensitive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "Probe"
    folder.mkdir()
    real_lstat = os.lstat

    def _lstat(path: object) -> os.stat_result:
        if Path(str(path)).name == "pROBE":
            raise FileNotFoundError(path)
        return real_lstat(path)  # type: ignore[arg-type]

    monkeypatch.setattr(pathsafety, "_lstat", _lstat)

    assert pathsafety._filesystem_is_case_insensitive(folder / "x") is False


def test_case_probe_reads_a_distinct_sibling_as_case_sensitive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A sibling that differs only in case, on a case-sensitive volume: the
    # swapped name exists but is another entry.
    folder = tmp_path / "Probe"
    folder.mkdir()
    sibling = tmp_path / "other"
    sibling.mkdir()
    real_lstat = os.lstat

    def _lstat(path: object) -> os.stat_result:
        if Path(str(path)).name == "pROBE":
            return real_lstat(sibling)
        return real_lstat(path)  # type: ignore[arg-type]

    monkeypatch.setattr(pathsafety, "_lstat", _lstat)

    assert pathsafety._filesystem_is_case_insensitive(folder / "x") is False


def test_case_probe_reads_the_same_entry_as_case_folding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "Probe"
    folder.mkdir()
    real_lstat = os.lstat

    def _lstat(path: object) -> os.stat_result:
        if Path(str(path)).name == "pROBE":
            return real_lstat(folder)
        return real_lstat(path)  # type: ignore[arg-type]

    monkeypatch.setattr(pathsafety, "_lstat", _lstat)

    assert pathsafety._filesystem_is_case_insensitive(folder / "x") is True


def test_case_probe_on_this_volume_matches_a_real_case_variant(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "Probe"
    folder.mkdir()
    folds = (tmp_path / "pROBE").exists()
    if not folds:
        # A real sibling differing only in case must not read as folding.
        (tmp_path / "pROBE").mkdir()

    assert pathsafety._filesystem_is_case_insensitive(folder / "x") is folds


def test_case_probe_without_inode_numbers_falls_back_to_the_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "Probe"
    folder.mkdir()

    def _lstat(path: object) -> os.stat_result:
        return os.stat_result((0o40755, 0, 0, 1, 0, 0, 0, 0, 0, 0))

    monkeypatch.setattr(pathsafety, "_lstat", _lstat)

    expected = sys.platform in ("win32", "darwin")
    assert pathsafety._filesystem_is_case_insensitive(folder / "x") is expected


def _case_sensitive_folder(folder: Path) -> None:
    """Turn on Windows per-folder case sensitivity for *folder*, or skip."""
    if sys.platform != "win32":
        pytest.skip("per-folder case sensitivity is a Windows setting")
    folder.mkdir()
    try:
        done = subprocess.run(
            ["fsutil", "file", "setCaseSensitiveInfo", str(folder), "enable"],
            capture_output=True,
            check=False,
        )
    except OSError:
        pytest.skip("fsutil is not available")
    if done.returncode != 0:
        pytest.skip("this host cannot turn on per-folder case sensitivity")


def test_a_case_sibling_in_a_case_sensitive_windows_folder_is_outside(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "cs"
    _case_sensitive_folder(folder)
    (folder / "root").mkdir()
    (folder / "ROOT").mkdir()
    root = folder / "root"

    assert pathsafety._filesystem_is_case_insensitive(root) is False
    assert pathsafety._within_allowed_root(folder / "ROOT" / "x", root) is False
    assert pathsafety._within_allowed_root(root / "x", root) is True


def test_a_case_variant_on_a_case_folding_volume_is_inside(tmp_path: Path) -> None:
    root = tmp_path / "Root"
    root.mkdir()
    if not (tmp_path / "rOOT").exists():
        pytest.skip("this volume keeps case")

    assert pathsafety._within_allowed_root(tmp_path / "ROOT" / "x", root) is True


# -- item 5: uninstall order, link naming, one link test ---------------------


def _codex_installed_then_linked_out(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Install Codex below ``~/a``, then move ``~/a`` out behind a link."""
    monkeypatch.setenv("CODEX_HOME", str(home / "a" / "b" / "codex"))
    CodexAdapter().install({})
    outside = tmp_path / "outside" / "a"
    outside.parent.mkdir()
    (home / "a").rename(outside)
    _link(home / "a", outside)
    return outside


def test_uninstall_refuses_before_it_asks(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = _codex_installed_then_linked_out(home, tmp_path, monkeypatch)
    asked: list[str] = []

    def _confirm(text: str, **kwargs: object) -> bool:
        asked.append(text)
        return True

    monkeypatch.setattr("click.confirm", _confirm)
    monkeypatch.setattr("apothem.cli._stdin_is_interactive", lambda: True)

    result = CliRunner().invoke(main, ["uninstall", "--harness", "codex"])

    assert result.exit_code == 1, result.output
    assert asked == []
    assert "uninstall refused" in " ".join(result.output.split())
    # Rich wraps a long path, so compare with the whitespace removed.
    assert "".join(str(home / "a").split()) in "".join(result.output.split())
    assert "Replace the link" in " ".join(result.output.split())
    assert (outside / "b" / "codex" / "AGENTS.md").is_file()


def test_the_refusal_names_the_link_and_where_it_leads(
    home: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside" / "a"
    _link(home / "a", outside)

    with pytest.raises(MaterializationError) as caught:
        pathsafety.refuse_link_leaving_home(
            "codex", home / "a" / "b" / "codex", operation="codex_home"
        )

    message = str(caught.value)
    assert str(home / "a") in message
    assert f"to {outside.resolve()}" in message
    error = _materialization_error(caught.value, files_written=[])
    assert str(home / "a") in str(error["reason"])
    assert "Replace the link" in str(error["fix"])


def test_install_json_names_the_link_and_where_it_leads(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside" / "a"
    _link(home / "a", outside)
    monkeypatch.setenv("CODEX_HOME", str(home / "a" / "b" / "codex"))

    result = CliRunner().invoke(
        main, ["install", "--harness", "codex", "--yes", "--format", "json"]
    )

    assert result.exit_code != 0, result.output
    error = json.loads(result.output)["error"]
    link = home / "a"
    assert f"{link} is a link to {outside.resolve()}" in error["reason"]
    assert "outside your home directory" in error["reason"]
    assert error["fix"].startswith(f"Replace the link {link}")
    assert list(outside.iterdir()) == []


def test_a_rollback_refusal_carries_the_fix(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _codex_installed_then_linked_out(home, tmp_path, monkeypatch)

    result = CliRunner().invoke(main, ["rollback", "--harness", "codex", "--yes"])

    assert result.exit_code == 1, result.output
    flat = " ".join(result.output.split())
    assert "rollback refused" in flat
    assert "Replace the link" in flat


def test_a_guard_link_error_names_the_link_in_the_cli_reason(
    home: Path, tmp_path: Path
) -> None:
    # A link inside the harness folder that stays inside the home.
    root = home / ".tool"
    _link(root / "skills", home / "elsewhere")
    refusal = pathsafety._validate_target_path(
        root / "skills" / "x.md",
        allowed_root=pathsafety._allowed_write_root(root, None),
        operation="t",
    )
    assert refusal is not None
    run = MaterializationRun(harness="t", dry_run=False, results=(refusal,))

    error = _materialization_error(
        MaterializationError("failed", run), files_written=[]
    )

    assert str(root / "skills") in str(error["reason"])
    assert "is a link to" in str(error["reason"])
    assert "Replace the link" in str(error["fix"])


def test_one_link_test_is_shared() -> None:
    assert pathsafety._is_link is links.is_link
    assert clean_slate.is_link is links.is_link
    assert not hasattr(clean_slate, "_is_link")
