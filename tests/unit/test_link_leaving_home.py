# SPDX-License-Identifier: MIT

"""No write leaves the home through a link, past the install commands.

``apothem rollback`` and every profile write follow the rule the installs
follow: a folder spelled inside the home that a link leads out of it is
refused before anything changes; one spelled outside the home is followed.
Creating a symbolic link needs a privilege some Windows hosts lack, so there
each link is a junction, which the guards also see as a link.
"""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import (
    install_driver,
    install_driver_homelink,
)
from apothem.harnesses.codex import CodexAdapter
from apothem.harnesses.opencode import OpenCodeAdapter
from apothem.lib import atomic_io, install_ledger
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget, OwnedEntry


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
            raise
        import _winapi

        _winapi.CreateJunction(str(target), str(link))


def _snapshot(folder: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(folder)): path.read_bytes()
        for path in folder.rglob("*")
        if path.is_file()
    }


def _folders(folder: Path) -> set[str]:
    return {
        str(path.relative_to(folder)) for path in folder.rglob("*") if path.is_dir()
    }


# -- rollback ---------------------------------------------------------------


def _install_then_link_out(
    harness: str, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """Install below ``~/a`` while it is a folder, then move it out behind a link.

    Returns the install root as spelled and the folder ``~/a`` now leads to.
    """
    if harness == "codex":
        monkeypatch.setenv("CODEX_HOME", str(home / "a" / "b" / "codex"))
        CodexAdapter().install({})
        root = home / "a" / "b" / "codex"
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "a" / "b"))
        OpenCodeAdapter().install({})
        root = home / "a" / "b" / "opencode"
    assert install_ledger.current_install_record(harness, root=root) is not None
    outside = tmp_path / "outside" / "a"
    outside.parent.mkdir()
    (home / "a").rename(outside)
    _link(home / "a", outside)
    return root, outside


@pytest.mark.parametrize("harness", ["codex", "opencode"])
def test_a_rollback_through_a_link_leaving_the_home_changes_nothing(
    harness: str, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The write guard's floor is the folder above the install root, so only
    # the separate check sees ~/a.
    root, outside = _install_then_link_out(harness, home, tmp_path, monkeypatch)
    before = _snapshot(outside), _folders(outside), _snapshot(home)
    records = len(install_ledger.read_records(harness))

    result = CliRunner().invoke(main, ["rollback", "--harness", harness, "--yes"])

    assert result.exit_code == 1, result.output
    assert "Rolled back" not in result.output
    assert (_snapshot(outside), _folders(outside), _snapshot(home)) == before
    assert len(install_ledger.read_records(harness)) == records
    assert install_ledger.current_install_record(harness, root=root) is not None


def test_a_refused_rollback_asks_no_confirmation(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_then_link_out("codex", home, tmp_path, monkeypatch)
    asked: list[str] = []

    def _confirm(text: str, **kwargs: object) -> bool:
        asked.append(text)
        return True

    monkeypatch.setattr("click.confirm", _confirm)
    monkeypatch.setattr("apothem.cli._stdin_is_interactive", lambda: True)

    result = CliRunner().invoke(main, ["rollback", "--harness", "codex"])

    assert result.exit_code == 1, result.output
    assert asked == []
    assert "rollback refused" in " ".join(result.output.split())


def test_rollback_install_names_the_link_it_refuses(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _install_then_link_out("codex", home, tmp_path, monkeypatch)
    record = install_ledger.current_install_record("codex", root=root)
    assert record is not None

    results = install_driver.rollback_install(
        record, harness_name="codex", harness_root=root
    )

    assert [(r.outcome, r.operation) for r in results] == [
        ("error", "rollback_refused")
    ]
    assert results[0].detail["symlink"] == str(home / "a")
    assert results[0].message.startswith("rollback refused:")


def test_a_rollback_spelled_outside_the_home_is_followed(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "outside" / "codex"
    monkeypatch.setenv("CODEX_HOME", str(folder))
    CodexAdapter().install({})
    assert (folder / "AGENTS.md").is_file()

    result = CliRunner().invoke(main, ["rollback", "--harness", "codex", "--yes"])

    assert result.exit_code == 0, result.output
    assert not (folder / "AGENTS.md").exists()


# -- profile writes ---------------------------------------------------------


def _profile_behind_a_link(home: Path, tmp_path: Path) -> Path:
    """Link ``~/.config`` out of the home with a profile there; return the profile."""
    outside = tmp_path / "outside" / "config"
    _link(home / ".config", outside)
    profile = outside / "apothem" / "profile.yaml"
    # Spelled outside the home, the operator names that place: it is written.
    result = CliRunner().invoke(main, ["profile", "init", "--profile", str(profile)])
    assert result.exit_code == 0, result.output
    return profile


def test_profile_set_through_a_link_leaving_the_home_creates_no_folder(
    home: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside" / "config"
    _link(home / ".config", outside)

    result = CliRunner().invoke(main, ["profile", "set", "identity.name", "Ada"])

    assert result.exit_code == 1, result.output
    assert "Apothem could not create the starter profile" in result.output
    assert "apothem profile init --profile PATH" in " ".join(result.output.split())
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    "command",
    [
        ["profile", "set", "identity.name", "Ada"],
        ["profile", "init", "--force"],
        ["profile", "edit"],
        ["profile", "set", "identity.name", "Ada", "--profile", "~default"],
    ],
)
def test_an_existing_profile_behind_a_link_leaving_the_home_is_not_rewritten(
    command: list[str], home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = _profile_behind_a_link(home, tmp_path)
    before = profile.read_bytes()
    opened: list[object] = []
    monkeypatch.setattr("click.edit", lambda **kwargs: opened.append(kwargs))
    default = str(home / ".config" / "apothem" / "profile.yaml")
    args = [default if part == "~default" else part for part in command]

    result = CliRunner().invoke(main, args)

    assert result.exit_code == 1, result.output
    assert "Apothem could not write the profile" in result.output
    assert "--profile PATH" in result.output
    assert profile.read_bytes() == before
    assert opened == []
    shown = CliRunner().invoke(main, ["profile", "show"])
    assert shown.exit_code == 0, shown.output


def test_a_profile_path_spelled_inside_the_home_through_a_link_is_refused(
    home: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside" / "w"
    _link(home / "w", outside)

    result = CliRunner().invoke(
        main, ["profile", "init", "--profile", str(home / "w" / "profile.yaml")]
    )

    assert result.exit_code == 1, result.output
    assert list(outside.iterdir()) == []


def test_a_profile_file_that_is_a_link_out_of_the_home_is_named_as_the_link(
    home: Path, tmp_path: Path
) -> None:
    real = tmp_path / "dotfiles" / "profile.yaml"
    made = CliRunner().invoke(main, ["profile", "init", "--profile", str(real)])
    assert made.exit_code == 0, made.output
    link = home / ".config" / "apothem" / "profile.yaml"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(real)
    except OSError as exc:  # pragma: no cover - platform dependent
        pytest.skip(f"file symlinks unavailable on this platform: {exc}")
    before = real.read_bytes()

    result = CliRunner().invoke(main, ["profile", "set", "identity.name", "Ada"])

    text = " ".join(result.output.split())
    assert result.exit_code == 1, result.output
    assert "Apothem could not write the profile" in text
    assert f"is a link to {real.resolve()}, outside your home directory" in text
    assert "the path the link leads to" in text
    assert real.read_bytes() == before


# -- install --clean ----------------------------------------------------------


def test_install_clean_through_a_config_link_leaving_the_home_changes_nothing(
    home: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside" / "config"
    profile = outside / "apothem" / "profile.yaml"
    made = CliRunner().invoke(main, ["profile", "init", "--profile", str(profile)])
    assert made.exit_code == 0, made.output
    (outside / "apothem" / "keep.txt").write_text("keep", encoding="utf-8")
    _link(home / ".config", outside)
    before = _snapshot(outside)

    result = CliRunner().invoke(
        main, ["install", "--harness", "claude-code", "--clean", "--yes"]
    )

    assert result.exit_code == 1, result.output
    assert "Clean-slate removal was refused" in result.output
    assert _snapshot(outside) == before
    assert not (home / ".claude").exists()
    assert not (home / ".apothem" / "backups").exists()


# -- the OpenCode install recorded under another spelling ---------------------


def _move_config_out_of_the_home(home: Path, tmp_path: Path) -> Path:
    outside = tmp_path / "outside" / "config"
    outside.parent.mkdir(exist_ok=True)
    (home / ".config").rename(outside)
    _link(home / ".config", outside)
    return outside


def test_the_earlier_spelling_is_closed_with_a_backup_and_its_folders(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = OpenCodeAdapter()
    adapter.install({})
    spelling = home / ".config" / "opencode"
    record = install_ledger.current_install_record("opencode", root=spelling)
    assert record is not None
    created = [
        Path(path).relative_to(spelling)
        for path in record.created_dirs
        if Path(path).is_relative_to(spelling)
    ]
    outside = _move_config_out_of_the_home(home, tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(outside))
    # The install there finds opencode.json in place; its uninstall leaves the
    # skeleton the earlier install created, which closing that install removes.
    adapter.install({})

    adapter.uninstall()

    config = outside / "opencode"
    assert not (config / "opencode.json").exists()
    closing = install_ledger.read_records("opencode")[-1]
    assert (closing.root, closing.kind) == (str(spelling), "uninstall")
    backups = {
        Path(target.path).name: Path(target.backup_ref)
        for target in closing.targets
        if target.backup_ref
    }
    skeleton = json.loads(backups["opencode.json"].read_text(encoding="utf-8"))
    assert set(skeleton) <= {"$schema", "instructions"}
    assert created
    assert [path for path in created if (config / path).is_dir()] == []


def test_the_earlier_spelling_is_closed_under_the_install_lock(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = OpenCodeAdapter()
    adapter.install({})
    spelling = home / ".config" / "opencode"
    outside = _move_config_out_of_the_home(home, tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(outside))
    lock = install_driver._install_lock_path("opencode", outside / "opencode")
    held: list[Path] = []
    real_lock = atomic_io.advisory_lock

    @contextlib.contextmanager
    def tracked(path: Path, **kwargs: float) -> Iterator[None]:
        with real_lock(path, **kwargs):
            held.append(path)
            try:
                yield
            finally:
                held.remove(path)

    appended: list[tuple[str, str, bool]] = []
    real_append = install_ledger.append_record

    def append(record: LedgerRecord, **kwargs: Path | None) -> Path:
        appended.append((record.root, record.kind, lock in held))
        return real_append(record, **kwargs)

    monkeypatch.setattr(atomic_io, "advisory_lock", tracked)
    monkeypatch.setattr(install_ledger, "append_record", append)

    adapter.uninstall()

    assert (str(spelling), "uninstall", True) in appended


def test_the_other_spellings_are_read_before_the_uninstall(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # After the uninstall the folder may be gone, and then the spellings no
    # longer match on a volume that ignores case (macOS); stand that in.
    from apothem.harnesses.opencode import uninstall as opencode_uninstall

    adapter = OpenCodeAdapter()
    adapter.install({})
    spelling = home / ".config" / "opencode"
    outside = _move_config_out_of_the_home(home, tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(outside))
    adapter.install({})
    done: list[Path] = []
    real_uninstall = opencode_uninstall._uninstall
    real_same = opencode_uninstall._names_same_folder

    def _uninstall(output_path: Path) -> install_driver.MaterializationRun:
        run = real_uninstall(output_path)
        done.append(output_path)
        return run

    def _same(first: Path, second: Path) -> bool:
        return not done and real_same(first, second)

    monkeypatch.setattr(opencode_uninstall, "_uninstall", _uninstall)
    monkeypatch.setattr(opencode_uninstall, "_names_same_folder", _same)

    adapter.uninstall()

    assert done
    assert install_ledger.active_install_records("opencode", root=spelling) == []


def test_a_held_install_lock_fails_the_uninstall_cleanly(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = OpenCodeAdapter()
    adapter.install({})
    outside = _move_config_out_of_the_home(home, tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(outside))
    real_lock = atomic_io.advisory_lock
    lock = install_driver._install_lock_path("opencode", outside / "opencode")

    @contextlib.contextmanager
    def held(path: Path, **kwargs: float) -> Iterator[None]:
        if path == lock:
            raise TimeoutError(f"timed out acquiring {path}")
        with real_lock(path, **kwargs):
            yield

    monkeypatch.setattr(atomic_io, "advisory_lock", held)

    run = adapter.uninstall()

    assert any("install lock" in error.message for error in run.errors)


# -- the relocated entries of a record that owned nothing ---------------------


def test_a_record_that_owned_nothing_is_asked_for_relocated_entries(
    tmp_path: Path,
) -> None:
    # adjust_prior asks for an empty ownership on install; uninstall agrees.
    root = tmp_path / "cfg"
    root.mkdir()
    target = root / "config.json"
    target.write_text(json.dumps({"keep": 1, "moved": "apothem"}), encoding="utf-8")
    recorded = LedgerTarget(
        path=str(target),
        mode="write_text",
        ownership_class="operator-owned",
        outcome="unchanged",
        created=False,
        owned=(),
    )
    install_ledger.append_record(
        LedgerRecord.create(
            harness="opencode", root=root, kind="install", targets=(recorded,)
        )
    )
    asked: list[tuple[OwnedEntry, ...]] = []

    def relocated(
        owned: tuple[OwnedEntry, ...], current: str | None
    ) -> tuple[OwnedEntry, ...]:
        del current
        asked.append(owned)
        return (OwnedEntry(("moved",), "key", "apothem"),)

    install_driver.surgically_remove_materialized_config(
        target, "{}", install_root=root, harness_name="opencode", relocated=relocated
    )

    assert asked == [()]
    assert json.loads(target.read_text(encoding="utf-8")) == {"keep": 1}


# -- the link check itself ----------------------------------------------------


def test_a_link_loop_on_the_way_up_is_refused(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Python 3.10-3.12 raise RuntimeError resolving a link loop.
    _link(home / ".config", home / "dotfiles" / "config")

    def loop(root: Path) -> Path | None:
        raise RuntimeError(f"Symlink loop from {root!r}")

    monkeypatch.setattr(install_driver_homelink, "_link_leaving_home", loop)
    root = home / ".config" / "opencode"

    with pytest.raises(install_driver.MaterializationError) as caught:
        install_driver_homelink.refuse_link_leaving_home(
            "opencode", root, operation="opencode_config"
        )

    assert caught.value.run.results[0].detail["symlink"] == str(home / ".config")
    runner = CliRunner()
    for args in (["status"], ["doctor"], ["harnesses", "list"]):
        result = runner.invoke(main, args)
        assert result.exit_code == 0, (args, result.output)
    verify = runner.invoke(main, ["verify", "--harness", "opencode"])
    assert verify.exit_code in (0, 1), verify.output
    assert "Traceback" not in verify.output


@pytest.mark.skipif(sys.platform == "win32", reason="a real link loop needs POSIX")
def test_an_install_through_a_real_link_loop_stops_without_a_traceback(
    home: Path,
) -> None:
    # Python 3.10-3.12 raise RuntimeError resolving the loop, and the link
    # check refuses it; from 3.13 resolving does not raise, and the write
    # that follows cannot pass through the loop.
    (home / ".config").symlink_to(home / ".config-loop")
    (home / ".config-loop").symlink_to(home / ".config")

    result = CliRunner().invoke(main, ["install", "--harness", "opencode", "--yes"])

    assert result.exit_code != 0, result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert (home / ".config").is_symlink()


@pytest.mark.parametrize("inner", ["outside", "inside"])
def test_the_link_named_is_the_highest_leading_out_of_the_home(
    inner: str, home: Path, tmp_path: Path
) -> None:
    # outside: ~/a leads out and so does ~/a/b below it; ~/a is named.
    # inside: ~/a leads to ~/c, inside the home, and ~/c/b leads out; ~/a/b
    # is named.
    if inner == "outside":
        _link(home / "a", tmp_path / "out1")
        _link(tmp_path / "out1" / "b", tmp_path / "out2")
        expected = home / "a"
    else:
        _link(home / "a", home / "c")
        _link(home / "c" / "b", tmp_path / "out")
        expected = home / "a" / "b"
    root = home / "a" / "b" / "codex"

    assert install_driver_homelink._link_leaving_home(root) == expected
    with pytest.raises(install_driver.MaterializationError, match="symlink"):
        install_driver_homelink.refuse_link_leaving_home(
            "codex", root, operation="codex_home"
        )
