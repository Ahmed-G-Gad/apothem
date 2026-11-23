# SPDX-License-Identifier: MIT

"""A whole uninstall, install, update or rollback stops at the real-home guard.

Each test fills a fake account home under ``tmp_path`` through the CLI first,
and only then protects it with ``also_protect_home``. The ledger and the
backups stay outside that home, so the refusal comes from the pass itself and
not from its bookkeeping. The command must raise
:class:`~apothem.lib.home_write_guard.RealHomeWriteError` (not report an
error row or a failed uninstall), change nothing in the home and record no
unfinished pass, unless an uninstall had already changed files outside the
protected folders: then an unfinished uninstall keeps their backups
referenced.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from apothem.cli import main
from apothem.harnesses._shared import (
    install_driver,
    install_driver_datahome,
    install_driver_digests,
    install_driver_lifecycle,
    install_driver_reversal,
)
from apothem.harnesses._shared.install_driver_types import _result
from apothem.harnesses._shared.wrapper_factories import make_native_config_uninstall
from apothem.harnesses.open_claw import rules_file
from apothem.lib import atomic_io, home_write_guard, install_ledger
from apothem.lib.harness_materializer import wrap_managed_block
from apothem.lib.harness_registry import get_harness_entry, iter_harness_entries
from apothem.lib.install_ledger import LedgerRecord

Refused = home_write_guard.RealHomeWriteError


@pytest.fixture(autouse=True)
def _forget_fake_homes() -> Iterator[None]:
    """Drop the added homes and the refusals each test logged."""
    yield
    home_write_guard.clear_extra_homes()
    home_write_guard.drain_refusals()


def _snapshot(folder: Path) -> dict[str, bytes | None]:
    """Map every path under *folder* to its bytes (``None`` for a folder)."""
    return {
        str(path): (path.read_bytes() if path.is_file() else None)
        for path in sorted(folder.rglob("*"))
    }


#: Variables that move a tool's folder or Apothem's state out of the home.
_ROOT_VARIABLES = (
    "XDG_CONFIG_HOME",
    "XDG_STATE_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "CODEX_HOME",
    "CLAUDE_CONFIG_DIR",
    "OPENCODE_CONFIG_DIR",
    "OPENCODE_CONFIG",
    "HOMEDRIVE",
    "HOMEPATH",
)

_PROFILE = (
    b"schema_version: 1\nidentity:\n  name: Ada Lovelace\n"
    b"  email: ada@analytical.engine\n  github: adalovelace\n"
)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make a fake home the process's home, with the ledger and backups outside it.

    The test sets every root itself instead of relying on ``tests/conftest.py``,
    so a copy of this file run without that conftest still installs only under
    ``tmp_path``, even if the guard regressed.
    """
    folder = tmp_path / "account-home"
    folder.mkdir()
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(folder))
    for name in _ROOT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APOTHEM_HOOK_STATE_DIR", str(tmp_path / "hook-state"))
    monkeypatch.setattr(install_ledger, "STATE_ROOT", tmp_path / "outside" / "state")
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "outside" / "backups")
    assert Path.home() == folder
    account = home_write_guard.account_home()
    assert account is None or os.path.normcase(account) != os.path.normcase(folder)
    return folder


@pytest.fixture
def profile(tmp_path: Path) -> Path:
    """Return a valid profile outside the fake home."""
    path = tmp_path / "outside" / "profile.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_PROFILE)
    return path


def _run(*argv: str) -> Result:
    return CliRunner().invoke(main, list(argv))


def _installed(*argv: str) -> None:
    """Run an install that must finish, before the home is protected."""
    result = _run("install", *argv)
    assert result.exit_code == 0, result.output
    assert home_write_guard.refusals() == ()


def _kinds(package_key: str) -> list[str]:
    return [record.kind for record in install_ledger.read_records(package_key)]


#: The project-scope harnesses whose install writes nothing in a protected
#: folder of the home: all of it lands in the project.
_PROJECT_ONLY = frozenset({"gemini-cli", "glm", "kimi-code"})

#: Every other registered harness writes into a protected folder of the home
#: (a user-scope tool folder, ``~/.agents/skills`` or ``~/.config/apothem``),
#: so its uninstall reaches the guard.
_PROTECTED_WRITERS = tuple(
    entry.public_id
    for entry in iter_harness_entries()
    if entry.public_id not in _PROJECT_ONLY
)


@pytest.mark.parametrize("harness", _PROTECTED_WRITERS)
def test_a_cli_uninstall_raises_the_refusal_and_records_nothing(
    home: Path, profile: Path, harness: str
) -> None:
    entry = get_harness_entry(harness)
    project = ("--project", str(home / "project")) if entry.scope == "project" else ()
    if project:
        (home / "project").mkdir()
    empty = _snapshot(home)
    _installed("--harness", harness, "--profile", str(profile), *project)
    before = _snapshot(home)
    kinds = _kinds(entry.package_key)
    home_write_guard.also_protect_home(home)
    written = [path for path in before if path not in empty]
    assert any(home_write_guard.would_refuse(path) for path in written), harness

    result = _run("uninstall", "--harness", harness, "--yes", *project)

    assert isinstance(result.exception, Refused), (result.exit_code, result.output)
    assert _snapshot(home) == before
    assert _kinds(entry.package_key) == kinds
    assert "uninstall-incomplete" not in kinds


def _retired_antigravity_files(home: Path) -> Path:
    """Write what earlier Antigravity installs left; return the retired profile.

    ``~/.antigravity/profile.yaml`` sits outside every tool folder the
    registry names, and the plugin folder before the move to
    ``~/.gemini/config/plugins/`` sits in ``~/.gemini``. The stale sweep of an
    uninstall removes both, the profile first. The old plugin's support files
    alone show an install, so an uninstall runs without a current one.
    """
    retired = home / ".antigravity" / "profile.yaml"
    retired.parent.mkdir(parents=True)
    retired.write_bytes(_PROFILE)
    (home / ".antigravity" / "argv.json").write_bytes(b"{}\n")
    plugin = home / ".gemini" / "antigravity-cli" / "plugins" / "apothem"
    support = plugin / ".apothem" / "support" / "templates"
    support.mkdir(parents=True)
    (plugin / "plugin.json").write_bytes(b'{"name": "apothem"}\n')
    (support / "plan.md").write_bytes(b"# Plan\n")
    return retired


@pytest.mark.parametrize("installed", [True, False])
def test_an_antigravity_uninstall_is_refused_before_its_stale_sweep(
    home: Path, profile: Path, installed: bool
) -> None:
    """The retired profile outside ``~/.gemini`` is refused first, so nothing moves.

    Without a current install, the old plugin folder alone is the install.
    """
    if installed:
        _installed("--harness", "antigravity", "--profile", str(profile))
    retired = _retired_antigravity_files(home)
    before = _snapshot(home)
    kinds = _kinds("antigravity")
    home_write_guard.also_protect_home(home)
    assert home_write_guard.would_refuse(retired)
    assert not home_write_guard.would_refuse(retired.parent / "argv.json")

    result = _run("uninstall", "--harness", "antigravity", "--yes")

    assert isinstance(result.exception, Refused), (result.exit_code, result.output)
    assert result.exception.protected_root == str(retired)
    assert _snapshot(home) == before
    assert _kinds("antigravity") == kinds
    assert not install_driver.BACKUP_ROOT.exists() or not any(
        install_driver.BACKUP_ROOT.rglob("profile.yaml")
    )


def test_a_tmp_path_write_and_the_checkout_stay_allowed_beside_the_retired_file(
    home: Path, tmp_path: Path
) -> None:
    _retired_antigravity_files(home)
    home_write_guard.also_protect_home(home)
    elsewhere = tmp_path / "outside" / ".antigravity" / "profile.yaml"
    assert not home_write_guard.would_refuse(elsewhere)
    assert not home_write_guard.would_refuse(Path(__file__), tree=True)
    assert not home_write_guard.would_refuse(Path(__file__).parents[2], tree=True)
    atomic_io.write_bytes_atomically(elsewhere, b"data")
    assert elsewhere.read_bytes() == b"data"


def test_an_open_claw_uninstall_is_refused_before_a_workspace_outside_its_folder(
    home: Path, profile: Path
) -> None:
    """A workspace the operator moved out of ``~/.openclaw`` keeps its rules file.

    The uninstall strips Apothem's block from each workspace's rules file before
    it changes ``openclaw.json``. With the native config protected, it is refused
    before that first step.
    """
    workspace = home / "agent-workspace"
    workspace.mkdir()
    config = home / ".openclaw" / "openclaw.json"
    config.parent.mkdir()
    settings = {"agents": {"defaults": {"workspace": workspace.as_posix()}}}
    config.write_bytes(json.dumps(settings).encode() + b"\n")
    _installed("--harness", "open-claw", "--profile", str(profile))
    rules_file = workspace / "apothem" / "AGENTS.md"
    assert rules_file.is_file()
    before = _snapshot(home)
    kinds = _kinds("open_claw")
    home_write_guard.also_protect_home(home)
    assert not home_write_guard.would_refuse(rules_file)

    result = _run("uninstall", "--harness", "open-claw", "--yes")

    assert isinstance(result.exception, Refused), (result.exit_code, result.output)
    assert result.exception.protected_root == str(home / ".openclaw")
    assert _snapshot(home) == before
    assert _kinds("open_claw") == kinds


@pytest.mark.parametrize("ledger_refuses", [False, True])
def test_a_refusal_after_removals_elsewhere_records_the_unfinished_uninstall(
    home: Path,
    profile: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ledger_refuses: bool,
) -> None:
    """The removed project files keep their backups referenced in the ledger.

    The data home is removed last, after the project files. A refusal there
    still reaches the CLI unchanged, also when the record itself is refused.
    """
    project = tmp_path / "project"
    project.mkdir()
    _installed(
        "--harness", "gemini-cli", "--project", str(project), "--profile", str(profile)
    )
    assert _kinds("gemini_cli") == ["install"]

    def refused(*_args: object, **_kwargs: object) -> None:
        raise Refused("the probe's refusal", path="", protected_root="", operation="")

    monkeypatch.setattr(install_driver_lifecycle, "_remove_data_home", refused)
    if ledger_refuses:
        monkeypatch.setattr(install_ledger, "append_record", refused)

    result = _run(
        "uninstall", "--harness", "gemini-cli", "--yes", "--project", str(project)
    )

    assert isinstance(result.exception, Refused), (result.exit_code, result.output)
    assert str(result.exception) == "the probe's refusal"
    records = install_ledger.read_records("gemini_cli")
    if ledger_refuses:
        assert [record.kind for record in records] == ["install"]
        return
    assert [record.kind for record in records] == ["install", "uninstall-incomplete"]
    backups = [target.backup_ref for target in records[-1].targets]
    assert backups
    assert all(ref and Path(ref).exists() for ref in backups)


def _operator_home(home: Path) -> Path:
    """Put operator-owned anchors in *home*; return the home."""
    (home / "AGENTS.md").write_bytes(b"# My agents\n")
    (home / "GEMINI.md").write_bytes(b"# My Gemini notes\n")
    return home


@pytest.mark.parametrize("harness", ["kimi-code", "gemini-cli"])
def test_an_install_with_the_home_as_project_root_writes_nothing(
    home: Path, profile: Path, harness: str
) -> None:
    _operator_home(home)
    before = _snapshot(home)
    home_write_guard.also_protect_home(home)
    for verb in ("install", "update"):
        result = _run(
            verb,
            "--harness",
            harness,
            "--project",
            str(home),
            "--profile",
            str(profile),
        )
        assert isinstance(result.exception, Refused), (verb, result.output)
        assert "with the project root" in str(result.exception)
        assert _snapshot(home) == before
    assert install_ledger.read_records(get_harness_entry(harness).package_key) == []


@pytest.mark.parametrize("harness", ["kimi-code", "gemini-cli"])
def test_an_uninstall_or_rollback_of_a_project_at_the_home_writes_nothing(
    home: Path, profile: Path, harness: str
) -> None:
    _operator_home(home)
    _installed("--harness", harness, "--project", str(home), "--profile", str(profile))
    package_key = get_harness_entry(harness).package_key
    before = _snapshot(home)
    kinds = _kinds(package_key)
    home_write_guard.also_protect_home(home)
    for argv in (
        ("uninstall", "--harness", harness, "--yes"),
        ("rollback", "--harness", harness, "--yes"),
    ):
        result = _run(*argv, "--project", str(home))
        assert isinstance(result.exception, Refused), (argv, result.output)
        assert "with the project root" in str(result.exception)
        assert _snapshot(home) == before
        assert _kinds(package_key) == kinds


@pytest.mark.parametrize("verb", ["uninstall", "rollback"])
@pytest.mark.parametrize("kept", ["backups", "state"])
@pytest.mark.parametrize("harness", ["kimi-code", "gemini-cli"])
def test_a_pass_whose_backups_or_ledger_are_protected_changes_nothing(
    home: Path,
    profile: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    harness: str,
    kept: str,
    verb: str,
) -> None:
    """The backup root and the ledger are checked before the first change.

    These harnesses write only into the project, so the backups and the
    ledger record are all that would reach the home: without the check the
    pass reversed the project and was refused at its first backup or its
    record, with those changes unrecorded.
    """
    project = tmp_path / "project"
    project.mkdir()
    argv = ("--harness", harness, "--project", str(project))
    _installed(*argv, "--profile", str(profile))
    package_key = get_harness_entry(harness).package_key
    if kept == "state":
        moved = home / ".apothem" / "state"
        shutil.copytree(install_ledger.STATE_ROOT, moved)
        monkeypatch.setattr(install_ledger, "STATE_ROOT", moved)
    else:
        backups = home / ".apothem" / "backups"
        monkeypatch.setattr(install_driver, "BACKUP_ROOT", backups)
    kinds = _kinds(package_key)
    before = (_snapshot(home), _snapshot(project), _snapshot(tmp_path / "outside"))
    home_write_guard.also_protect_home(home)

    result = _run(verb, *argv, "--yes")

    assert isinstance(result.exception, Refused), (result.exit_code, result.output)
    assert "backups or ledger record" in str(result.exception)
    assert result.exception.protected_root == str(home / ".apothem")
    after = (_snapshot(home), _snapshot(project), _snapshot(tmp_path / "outside"))
    assert after == before
    assert _kinds(package_key) == kinds


def test_a_native_uninstall_with_its_ledger_protected_runs_no_step(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The step before the native config does not run: its removals could not be recorded."""
    root = tmp_path / "openclaw"
    root.mkdir()
    config = root / "openclaw.json"
    config.write_bytes(b"{}\n")
    monkeypatch.setattr(install_ledger, "STATE_ROOT", home / ".apothem" / "state")
    home_write_guard.also_protect_home(home)
    steps: list[Path] = []

    def first_step(
        output_path: Path,
    ) -> tuple[install_driver.MaterializationResult, ...]:
        steps.append(output_path)
        return ()

    uninstall = make_native_config_uninstall(
        "open_claw", lambda profile: "{}", before_fn=first_step
    )
    with pytest.raises(Refused, match="backups or ledger record"):
        uninstall(config)
    assert steps == []
    assert config.read_bytes() == b"{}\n"
    assert list(home.rglob("*")) == []


def test_the_driver_refuses_the_home_as_project_root_before_writing(
    home: Path,
) -> None:
    _operator_home(home)
    before = _snapshot(home)
    home_write_guard.also_protect_home(home)
    preview = install_driver.run_install("kimi_code", project_root=home, dry_run=True)
    assert preview.dry_run
    record = LedgerRecord.create(harness="kimi_code", root=home, kind="install")
    for call in (
        lambda: install_driver.run_install("kimi_code", project_root=home),
        lambda: install_driver.run_uninstall("kimi_code", project_root=home),
        lambda: install_driver_reversal.rollback_install(
            record, harness_name="kimi_code", project_root=home
        ),
    ):
        with pytest.raises(Refused, match="with the project root"):
            call()
    assert _snapshot(home) == before
    assert install_ledger.read_records("kimi_code") == []


def _store(home: Path) -> Path:
    data_home = home / ".apothem"
    (data_home / "memory").mkdir(parents=True)
    (data_home / "memory" / "note.md").write_bytes(b"kept\n")
    return data_home


#: A profile whose data home sits right in the home, under a name of its own.
_USER_HOME_PROFILE = (
    _PROFILE + b"workspace:\n  scope: user-home\n  directory_name: apothem-data\n"
)


def test_a_data_home_right_in_the_home_is_refused_under_any_name(
    home: Path, profile: Path, tmp_path: Path
) -> None:
    profile.write_bytes(_USER_HOME_PROFILE)
    project = tmp_path / "project"
    project.mkdir()
    argv = ("--harness", "gemini-cli", "--project", str(project))
    _installed(*argv, "--profile", str(profile))
    data_home = home / "apothem-data"
    assert (data_home / "memory").is_dir()
    before = _snapshot(home)
    home_write_guard.also_protect_home(home)
    assert not home_write_guard.would_refuse(data_home / "memory", tree=True)

    for verb in ("install", "uninstall"):
        extra = ("--profile", str(profile)) if verb == "install" else ("--yes",)
        result = _run(verb, *argv, *extra)
        assert isinstance(result.exception, Refused), (verb, result.output)
        assert "a data home right in" in str(result.exception)
        assert result.exception.protected_root == str(home)
        assert _snapshot(home) == before


def test_a_data_home_right_in_the_home_is_not_created(
    home: Path, profile: Path, tmp_path: Path
) -> None:
    profile.write_bytes(_USER_HOME_PROFILE)
    project = tmp_path / "project"
    project.mkdir()
    home_write_guard.also_protect_home(home)
    result = _run(
        "install", "--harness", "gemini-cli", "--project", str(project),
        "--profile", str(profile),
    )  # fmt: skip
    assert isinstance(result.exception, Refused), result.output
    assert _snapshot(home) == {}


def test_a_kept_shared_data_home_raises_nothing(home: Path) -> None:
    data_home = _store(home)
    (home / ".codex").mkdir()
    install_ledger.append_record(
        LedgerRecord.create(
            harness="codex",
            root=home / ".codex",
            kind="install",
            data_home=str(data_home),
        )
    )
    before = _snapshot(home)
    home_write_guard.also_protect_home(home)
    result = install_driver_datahome._remove_data_home(
        "claude_code", root=home / ".claude", allowed_root=home, home=data_home
    )
    assert result is not None
    assert result.outcome == "unchanged"
    assert home_write_guard.refusals() == ()
    assert _snapshot(home) == before


def test_removing_the_last_data_home_in_the_home_raises(home: Path) -> None:
    data_home = _store(home)
    before = _snapshot(home)
    home_write_guard.also_protect_home(home)
    with pytest.raises(Refused):
        install_driver_datahome._remove_data_home(
            "claude_code", root=home / ".claude", allowed_root=home, home=data_home
        )
    assert _snapshot(home) == before
    assert not install_driver.BACKUP_ROOT.exists()


def test_a_stopped_native_uninstall_raises_its_refused_record(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install_ledger, "STATE_ROOT", home / ".apothem" / "state")
    root = home / ".openclaw"
    root.mkdir()
    install_ledger.append_record(
        LedgerRecord.create(harness="open_claw", root=root, kind="install")
    )
    before = _snapshot(home)
    home_write_guard.also_protect_home(home)

    def stuck(output_path: Path) -> tuple[install_driver.MaterializationResult, ...]:
        return (_result("error", "rules_file", output_path, "clear this by hand"),)

    uninstall = make_native_config_uninstall(
        "open_claw", lambda profile: "{}", before_fn=stuck
    )
    with pytest.raises(Refused):
        uninstall(root / "openclaw.json")
    assert _snapshot(home) == before


def test_a_rollback_with_the_project_outside_is_refused_before_any_change(
    home: Path, profile: Path, tmp_path: Path
) -> None:
    """The project files stay as they are when a later target is protected.

    Cursor's install writes its project files and the shared skills in
    ``~/.agents/skills``. The rollback reverses the project files first, so
    every target is checked before the first one changes.
    """
    project = tmp_path / "project"
    project.mkdir()
    _installed(
        "--harness", "cursor", "--project", str(project), "--profile", str(profile)
    )
    record = install_ledger.read_records("cursor")[-1]
    before = (_snapshot(home), _snapshot(project), _snapshot(tmp_path / "outside"))
    home_write_guard.also_protect_home(home)
    assert any(not home_write_guard.would_refuse(t.path) for t in record.targets)
    assert any(home_write_guard.would_refuse(t.path) for t in record.targets)

    result = _run("rollback", "--harness", "cursor", "--project", str(project), "--yes")

    assert isinstance(result.exception, Refused), (result.exit_code, result.output)
    assert (_snapshot(home), _snapshot(project), _snapshot(tmp_path / "outside")) == (
        before
    )
    assert _kinds("cursor") == ["install"]


def test_a_rollback_checks_the_data_stores_it_would_remove_first(
    home: Path, tmp_path: Path
) -> None:
    """Stores the rollback removes last are refused before any target changes.

    The data home sits right in the home under a name of its own, so only the
    store check refuses it, not the check of the targets and folders.
    """
    project = tmp_path / "project"
    (project / "notes").mkdir(parents=True)
    written = project / "notes" / "a.md"
    written.write_bytes(b"made by the install\n")
    data_home = home / "apothem-data"
    (data_home / "memory").mkdir(parents=True)
    (data_home / "memory" / "note.md").write_bytes(b"kept\n")
    record = LedgerRecord.create(
        harness="gemini_cli",
        root=project,
        kind="install",
        targets=(
            install_ledger.LedgerTarget(
                str(written),
                "write_text",
                "apothem-owned",
                outcome="created",
                digest=install_driver_digests.file_digest(written),
            ),
        ),
        created_dirs=(str(data_home / "memory"),),
        data_home=str(data_home),
    )
    before = (_snapshot(home), _snapshot(project))
    home_write_guard.also_protect_home(home)
    assert not home_write_guard.would_refuse(data_home / "memory", tree=True)

    with pytest.raises(Refused, match="a data home right in"):
        install_driver_reversal.rollback_install(
            record, harness_name="gemini_cli", project_root=project
        )
    assert (_snapshot(home), _snapshot(project)) == before


def test_a_rollback_checks_the_home_folders_it_would_tidy_first(
    home: Path, tmp_path: Path
) -> None:
    """A record that names no home path is still refused before any change.

    Cursor's rollback ends by tidying ``~/.agents/skills`` and ``~/.agents``,
    which a record from before the shared skills does not name. With them in
    a protected folder, the rollback is refused before the project changes.
    """
    project = tmp_path / "project"
    (project / ".cursor").mkdir(parents=True)
    written = project / ".cursor" / "a.md"
    written.write_bytes(b"made by the install\n")
    (home / ".agents" / "skills").mkdir(parents=True)
    record = LedgerRecord.create(
        harness="cursor",
        root=project,
        kind="install",
        targets=(
            install_ledger.LedgerTarget(
                str(written),
                "write_text",
                "apothem-owned",
                outcome="created",
                digest=install_driver_digests.file_digest(written),
            ),
        ),
    )
    before = (_snapshot(home), _snapshot(project))
    home_write_guard.also_protect_home(home)
    assert not any(home_write_guard.would_refuse(t.path) for t in record.targets)

    with pytest.raises(Refused) as caught:
        install_driver_reversal.rollback_install(
            record, harness_name="cursor", project_root=project
        )
    assert caught.value.protected_root == str(home / ".agents")
    assert (_snapshot(home), _snapshot(project)) == before


def test_a_stale_sweep_is_refused_before_its_first_removal(home: Path) -> None:
    first = home / "old-layout.txt"
    first.write_bytes(b"an earlier layout\n")
    protected = home / ".claude" / "old-layout"
    protected.mkdir(parents=True)
    (protected / "file.md").write_bytes(b"kept\n")
    before = _snapshot(home)
    home_write_guard.also_protect_home(home)
    assert not home_write_guard.would_refuse(first)

    with pytest.raises(Refused):
        install_driver.sweep_stale(
            ["old-layout.txt", ".claude/old-layout"], home, harness_name="claude_code"
        )
    assert _snapshot(home) == before


@pytest.mark.parametrize("stop", ["refused", "error"])
def test_a_native_uninstall_stopped_after_its_first_step_records_the_backups(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: str
) -> None:
    """What the step before the native config removed stays referenced.

    The native-config step stops on a refusal of the guard, or on an ordinary
    error such as a file the system will not let it change. The ordinary
    error is raised as a stopped uninstall that carries what the first step
    removed, with the error as its cause, so the CLI reports it as partial;
    the refusal is raised as it is.
    """
    root = home / ".openclaw"
    root.mkdir()
    config = root / "openclaw.json"
    config.write_bytes(b"{}\n")
    install_ledger.append_record(
        LedgerRecord.create(harness="open_claw", root=root, kind="install")
    )
    elsewhere = tmp_path / "workspace" / "AGENTS.md"
    elsewhere.parent.mkdir()
    elsewhere.write_bytes(b"rules\n")
    home_write_guard.also_protect_home(home)
    assert not home_write_guard.would_refuse(elsewhere)

    def remove_elsewhere(
        output_path: Path,
    ) -> tuple[install_driver.MaterializationResult, ...]:
        backup = install_driver.backup_existing(
            elsewhere,
            install_root=output_path.parent,
            harness_name="open_claw",
            allowed_root=elsewhere.parent,
        )
        elsewhere.unlink()
        return (
            _result("updated", "rules_file", elsewhere, "removed", backup_path=backup),
        )

    def stopped(*_args: object, **_kwargs: object) -> None:
        raise PermissionError(13, "denied", str(config))

    if stop != "refused":
        monkeypatch.setattr(
            install_driver, "surgically_remove_materialized_config", stopped
        )
    expected: type[BaseException] = {
        "refused": Refused,
        "error": install_driver.MaterializationError,
    }[stop]
    uninstall = make_native_config_uninstall(
        "open_claw", lambda profile: "{}", before_fn=remove_elsewhere
    )
    with pytest.raises(expected) as caught:
        uninstall(config)
    if stop == "error":
        assert isinstance(caught.value, install_driver.MaterializationError)
        assert isinstance(caught.value.__cause__, PermissionError)
        assert [result.path for result in caught.value.run.results] == [str(elsewhere)]
    assert config.read_bytes() == b"{}\n"
    records = install_ledger.read_records("open_claw")
    assert [record.kind for record in records] == ["install", "uninstall-incomplete"]
    backups = [target.backup_ref for target in records[-1].targets]
    assert backups
    assert all(ref and Path(ref).read_bytes() == b"rules\n" for ref in backups)


def test_an_open_claw_uninstall_checks_every_rules_file_first(home: Path) -> None:
    """A rules file in a protected folder is refused before any other changes."""
    root = home / "openclaw-state"
    root.mkdir()
    config = root / "openclaw.json"
    config.write_bytes(b"{}\n")
    files = [
        home / "workspace" / "apothem" / "AGENTS.md",
        home / ".claude" / "workspace" / "apothem" / "AGENTS.md",
    ]
    for path in files:
        path.parent.mkdir(parents=True)
        path.write_bytes(wrap_managed_block("rules").encode())
    install_ledger.append_record(
        LedgerRecord.create(
            harness="open_claw",
            root=root,
            kind="install",
            targets=tuple(
                install_ledger.LedgerTarget(
                    str(path), "sentinel_merge", "apothem-owned", outcome="created"
                )
                for path in files
            ),
        )
    )
    before = _snapshot(home)
    home_write_guard.also_protect_home(home)
    assert not home_write_guard.would_refuse(files[0])

    with pytest.raises(Refused):
        rules_file.before_uninstall(config)
    assert _snapshot(home) == before
