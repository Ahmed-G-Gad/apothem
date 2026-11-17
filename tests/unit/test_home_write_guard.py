# SPDX-License-Identifier: MIT

"""``apothem.lib.home_write_guard`` refuses writes into the real home during a test.

Every home these tests protect is a folder under ``tmp_path`` added with
``also_protect_home``, which adds a home and can never replace the account's
own, so nothing here names or writes the real home. The protected folders and
the three write primitives of ``apothem.lib.atomic_io`` are checked against that
fake home: a refused write leaves it empty, and a path outside the protected
folders writes as before.
"""

from __future__ import annotations

import contextlib
import copy
import ctypes
import os
import pickle
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from apothem.lib import (
    atomic_io,
    harness_registry,
    harness_registry_data,
    home_write_guard,
    propagation,
)

#: Every protected folder, and each protected file outside them, relative to a
#: home.
_ROOTS = (
    ".agents",
    ".antigravity/profile.yaml",
    ".apothem",
    ".claude",
    ".codebuddy",
    ".codex",
    ".config/apothem",
    ".config/opencode",
    ".gemini",
    ".hermes",
    ".kiro",
    ".openclaw",
    ".qwen",
    ".trae",
)


@pytest.fixture(autouse=True)
def _forget_fake_homes() -> Iterator[None]:
    """Drop the added homes, the refusals and the account home each test cached.

    A test that looks the account home up under fakes caches what it found. If
    that were a fake (a regression), clearing the cache here, after
    ``monkeypatch`` has undone the fakes, keeps the failure in that one test:
    the next lookup finds the real home again.
    """
    yield
    home_write_guard.clear_extra_homes()
    home_write_guard.drain_refusals()
    home_write_guard._os_account_home.cache_clear()


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    """Return an empty folder protected as an account home."""
    home = tmp_path / "account-home"
    home.mkdir()
    home_write_guard.also_protect_home(home)
    return home


def _under(home: Path, relative: str, *rest: str) -> Path:
    return home.joinpath(*relative.split("/"), *rest)


def _everything_in(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*"))


def _write(path: Path) -> None:
    atomic_io.write_bytes_atomically(path, b"data")


def _append(path: Path) -> None:
    atomic_io.append_line_durably(path, "line")


def _lock(path: Path) -> None:
    with atomic_io.advisory_lock(path):
        pass


_PRIMITIVES: dict[str, Callable[[Path], None]] = {
    "write_bytes_atomically": _write,
    "append_line_durably": _append,
    "advisory_lock": _lock,
}


def test_nothing_is_refused_when_no_test_is_running(
    fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = fake_home / ".claude" / "settings.json"
    monkeypatch.delenv(home_write_guard.PYTEST_VARIABLE)
    monkeypatch.delenv(home_write_guard.PYTEST_SESSION_VARIABLE, raising=False)
    assert not home_write_guard.active()
    _write(target)
    assert target.read_bytes() == b"data"


def test_a_write_is_refused_while_a_test_runs(fake_home: Path) -> None:
    assert home_write_guard.active()
    with pytest.raises(home_write_guard.RealHomeWriteError):
        _write(fake_home / ".claude" / "settings.json")


def test_pytest_marks_the_whole_session_for_the_guard() -> None:
    """pytest 8.2 and later sets ``PYTEST_VERSION`` for the session.

    It is set before any conftest or plugin is imported and stays set through
    collection and the session hooks; an xdist worker inherits it.
    """
    assert home_write_guard.PYTEST_SESSION_VARIABLE in os.environ


def test_a_write_outside_any_test_is_refused_and_names_the_session(
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Collection, module-level code and session hooks run with no test id."""
    monkeypatch.delenv(home_write_guard.PYTEST_VARIABLE)
    monkeypatch.setenv(home_write_guard.PYTEST_SESSION_VARIABLE, pytest.__version__)
    assert home_write_guard.active()
    claude = fake_home / ".claude" / "settings.json"
    assert home_write_guard.would_refuse(claude)
    assert home_write_guard.would_refuse_project_root(fake_home)
    with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
        _write(claude)
    message = str(caught.value)
    assert "while pytest is running (the pytest session" in message
    assert "()" not in message
    assert "without PYTEST_CURRENT_TEST and PYTEST_VERSION" in message
    with pytest.raises(home_write_guard.RealHomeWriteError):
        _append(fake_home / ".claude" / "x.jsonl")
    with pytest.raises(home_write_guard.RealHomeWriteError) as project:
        home_write_guard.refuse_project_root_at_home(fake_home, operation="install")
    assert "the pytest session" in str(project.value)
    notices = [
        line
        for line in capsys.readouterr().err.splitlines()
        if line.startswith("RealHomeWriteError: ")
    ]
    # Once per protected folder in the session: the second .claude refusal is
    # logged but not written again; the home itself is a folder of its own.
    assert len(notices) == 2
    assert all("the pytest session" in line for line in notices)
    assert len(home_write_guard.drain_refusals()) == 3
    assert _everything_in(fake_home) == []


@pytest.mark.parametrize("primitive", sorted(_PRIMITIVES))
@pytest.mark.parametrize("root", _ROOTS)
def test_each_primitive_refuses_each_root_and_leaves_the_home_empty(
    fake_home: Path, root: str, primitive: str
) -> None:
    target = _under(fake_home, root, "state", "file.jsonl")
    with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
        _PRIMITIVES[primitive](target)
    assert caught.value.protected_root == str(_under(fake_home, root))
    assert _everything_in(fake_home) == []


@pytest.mark.parametrize(
    "relative",
    [
        "notes.txt",
        "Projects/x/file.txt",
        ".config/other/file.txt",
        ".claudex/file.txt",
        "AppData/Local/Temp/x/file.txt",
    ],
)
def test_a_path_outside_the_protected_folders_writes(
    fake_home: Path, relative: str
) -> None:
    target = fake_home.joinpath(*relative.split("/"))
    _write(target)
    _append(target.with_suffix(".log"))
    _lock(target.with_suffix(".lock"))
    assert target.read_bytes() == b"data"
    assert home_write_guard.refusals() == ()


def test_the_temporary_folder_writes(fake_home: Path, tmp_path: Path) -> None:
    target = tmp_path / "elsewhere" / "file.txt"
    _write(target)
    assert target.read_bytes() == b"data"


def test_a_tree_operation_on_a_folder_that_holds_a_root_is_refused(
    fake_home: Path,
) -> None:
    for holder in (fake_home, fake_home / ".config"):
        home_write_guard.refuse_real_home_write(holder, operation="remove")
        with pytest.raises(home_write_guard.RealHomeWriteError):
            home_write_guard.refuse_real_home_write(
                holder, operation="remove", tree=True
            )
        assert home_write_guard.would_refuse(holder, tree=True)
        assert not home_write_guard.would_refuse(holder)


def test_the_protected_folders_follow_the_registry_and_the_manifest() -> None:
    entries = harness_registry_data.HARNESS_REGISTRY
    folders = home_write_guard.derive_roots(
        [
            *(path for entry in entries for path in entry.target_paths),
            *(root.path for root in harness_registry_data.SHARED_ROOTS),
        ]
    )
    paths = home_write_guard.manifest_paths(propagation.load_manifest(), entries)
    derived = home_write_guard.narrowest_roots(folders, paths)
    # A new tool folder, or a manifest path outside every folder (an earlier
    # release's file a stale sweep removes), fails here until it is listed in
    # both places.
    assert set(derived) | set(home_write_guard.APOTHEM_ROOTS) == set(_ROOTS)
    assert derived == home_write_guard.FALLBACK_ROOTS
    assert "~/.antigravity/profile.yaml" in paths
    home_write_guard._derived_roots.cache_clear()
    assert home_write_guard._registry_roots() == home_write_guard.FALLBACK_ROOTS


def test_the_root_of_a_user_scope_harness_is_its_first_target_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stale-sweep entries are joined to this folder, the adapter's own root."""
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(tmp_path))
    for name in ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(name, raising=False)
    checked = []
    for entry in harness_registry.iter_harness_entries():
        if entry.scope != "user":
            continue
        adapter = harness_registry.load_adapter_class(entry)()
        output = Path(adapter.output_path)  # type: ignore[attr-defined]
        expected = tmp_path.joinpath(*entry.target_paths[0][2:].split("/"))
        assert os.path.normcase(output) == os.path.normcase(expected), entry.public_id
        checked.append(entry.package_key)
    assert "antigravity" in checked


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("${USER_HOME}/.agents/skills/", ["~/.agents/skills"]),
        ("${HARNESS_ROOT}/config/plugins/apothem/", ["~/.tool/config/plugins/apothem"]),
        ("${HARNESS_ROOT}/agents/*.toml", ["~/.tool/agents"]),
        ("${HARNESS_ROOT}/../${NAME}/x", []),
        ("${HARNESS_ROOT}/../../outside.txt", []),
        ("${PROJECT_ROOT}/.tool/rules/", []),
    ],
)
def test_manifest_targets_name_home_paths_of_user_scope_harnesses(
    target: str, expected: list[str]
) -> None:
    entries = [
        SimpleNamespace(
            package_key="tool", scope="user", target_paths=("~/.tool/a.md",)
        )
    ]
    rules = SimpleNamespace(install=[SimpleNamespace(target=target)], stale_sweep=[])
    assert home_write_guard.manifest_paths({"tool": rules}, entries) == expected


def test_stale_sweep_entries_are_joined_to_the_harness_root() -> None:
    entries = [
        SimpleNamespace(
            package_key="user_tool", scope="user", target_paths=("~/.gemini/G.md",)
        ),
        SimpleNamespace(
            package_key="project_tool",
            scope="project",
            target_paths=("<project>/AGENTS.md", "~/.agents/skills/"),
        ),
    ]
    stale = ["../.antigravity/profile.yaml", "old/plugins/apothem", "../../x", ".."]
    manifest = {
        "user_tool": SimpleNamespace(install=[], stale_sweep=stale),
        "project_tool": SimpleNamespace(install=[], stale_sweep=[".kimi/old"]),
        "unregistered": SimpleNamespace(install=[], stale_sweep=["../.other/x"]),
    }
    paths = home_write_guard.manifest_paths(manifest, entries)
    assert paths == ["~/.antigravity/profile.yaml", "~/.gemini/old/plugins/apothem"]
    assert home_write_guard.narrowest_roots((".gemini",), paths) == (
        ".antigravity/profile.yaml",
        ".gemini",
    )


def test_the_registry_fallback_is_used_when_the_registry_cannot_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(name: str) -> object:
        raise ImportError(name)

    home_write_guard._derived_roots.cache_clear()
    monkeypatch.setattr(home_write_guard.importlib, "import_module", refuse)
    try:
        assert home_write_guard._registry_roots() == home_write_guard.FALLBACK_ROOTS
        assert home_write_guard._derived_roots.cache_info().currsize == 0
    finally:
        monkeypatch.undo()
        home_write_guard._derived_roots.cache_clear()


def test_the_fallback_is_used_when_the_manifest_cannot_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing() -> object:
        raise FileNotFoundError("propagation-manifest.yaml")

    home_write_guard._derived_roots.cache_clear()
    monkeypatch.setattr(propagation, "load_manifest", missing)
    try:
        assert home_write_guard._registry_roots() == home_write_guard.FALLBACK_ROOTS
        assert home_write_guard._derived_roots.cache_info().currsize == 0
    finally:
        monkeypatch.undo()
        home_write_guard._derived_roots.cache_clear()


def test_a_protected_file_refuses_its_own_writes_and_removals_above_it(
    fake_home: Path, tmp_path: Path
) -> None:
    """``.antigravity/profile.yaml`` is protected; the rest of its folder is not."""
    profile = fake_home / ".antigravity" / "profile.yaml"
    for path, tree in ((profile, False), (profile.parent, True)):
        with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
            home_write_guard.refuse_real_home_write(path, operation="remove", tree=tree)
        assert caught.value.protected_root == str(profile)
        assert "a protected path in this account's real home" in str(caught.value)
    sibling = fake_home / ".antigravity" / "extensions" / "x.json"
    assert not home_write_guard.would_refuse(sibling)
    assert not home_write_guard.would_refuse(profile.parent)
    _write(sibling)
    _write(tmp_path / "elsewhere" / "profile.yaml")
    assert sibling.read_bytes() == b"data"


def test_a_data_home_right_in_a_home_is_refused_whatever_its_name(
    fake_home: Path, tmp_path: Path
) -> None:
    for name in ("apothem-data", ".apothem", "Work Data"):
        with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
            home_write_guard.refuse_data_home_in_home(
                fake_home / name, operation="create the data home"
            )
        assert caught.value.protected_root == str(fake_home)
        assert "a data home right in" in str(caught.value)
    for allowed in (
        fake_home / "project" / ".apothem",
        fake_home / ".gemini" / ".apothem",
        tmp_path / "apothem-data",
        fake_home,
    ):
        home_write_guard.refuse_data_home_in_home(
            allowed, operation="create the data home"
        )
    assert _everything_in(fake_home) == []


def _fresh_account_home() -> str | None:
    home_write_guard._os_account_home.cache_clear()
    return home_write_guard.account_home()


def test_the_account_home_comes_from_the_system_not_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    found = _fresh_account_home()
    assert found is not None
    assert Path(found).is_absolute()
    assert Path(found).is_dir()
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(tmp_path))
    assert _fresh_account_home() == found
    for name in ("HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"):
        monkeypatch.delenv(name, raising=False)
    assert _fresh_account_home() == found


def _suite_conftest(config: pytest.Config) -> ModuleType:
    """Return ``tests/conftest.py`` as pytest registered it in this session."""
    conftest = Path(__file__).resolve().parents[1] / "conftest.py"
    for plugin in config.pluginmanager.get_plugins():
        location = getattr(plugin, "__file__", None)
        if location and Path(location).resolve() == conftest:
            return plugin
    raise AssertionError(f"pytest has not registered {conftest}")


def test_the_account_home_is_the_home_this_process_started_with(
    request: pytest.FixtureRequest,
) -> None:
    # tests/conftest.py records every spelling of the home the process started
    # with (HOME, USERPROFILE, HOMEDRIVE and HOMEPATH, ``~``, and the passwd
    # entry on POSIX) before it moves the home. A lookup that named another
    # folder, a parent of the home say, would leave the real home unprotected
    # while every test with a fake home still passed.
    if os.name != "nt":
        pwd = pytest.importorskip("pwd")
        try:
            pwd.getpwuid(os.geteuid())
        except KeyError:
            pytest.skip("the system has no passwd entry for this account")
    startup_homes = _suite_conftest(request.config)._REAL_HOMES
    found = _fresh_account_home()
    assert found is not None
    assert os.path.normcase(os.path.realpath(found)) in startup_homes, (
        found,
        startup_homes,
    )
    assert home_write_guard.would_refuse(Path(found) / ".apothem" / "x")
    assert home_write_guard.would_refuse(Path(found) / ".claude")
    assert not home_write_guard.would_refuse(Path(found) / "Documents" / "x")


def test_a_lookup_that_fails_in_any_way_falls_through_to_the_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    found = _fresh_account_home()
    assert found is not None

    def broken() -> str:
        raise TypeError("a fake that cannot be called this way")

    first = "_windows_profile" if os.name == "nt" else "_passwd_home_effective"
    monkeypatch.setattr(home_write_guard, first, broken)
    assert _fresh_account_home() == found
    monkeypatch.undo()
    assert _fresh_account_home() == found


@pytest.mark.skipif(sys.platform != "win32", reason="the profile lookup is Windows")
def test_a_function_in_place_of_kernel32_does_not_break_the_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    found = _fresh_account_home()
    windll = ctypes.windll  # type: ignore[attr-defined,unused-ignore]
    monkeypatch.setattr(windll, "kernel32", lambda *_args: 0, raising=False)
    assert _fresh_account_home() == found
    assert home_write_guard._windows_profile() == found
    monkeypatch.undo()
    _fresh_account_home()


def test_a_refusal_survives_a_copy_and_a_pickle(fake_home: Path) -> None:
    with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
        _write(fake_home / ".claude" / "x")
    error = caught.value
    for twin in (
        copy.copy(error),
        copy.deepcopy(error),
        pickle.loads(pickle.dumps(error)),  # noqa: S301 - our own bytes
    ):
        assert type(twin) is home_write_guard.RealHomeWriteError
        assert str(twin) == str(error)
        assert (twin.path, twin.protected_root, twin.operation) == (
            error.path,
            error.protected_root,
            error.operation,
        )


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_patched_platform_and_windll_change_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str
) -> None:
    found = _fresh_account_home()
    monkeypatch.setattr(atomic_io.sys, "platform", platform)
    fake_kernel32 = SimpleNamespace(GetShortPathNameW=lambda *_args: 0)
    monkeypatch.setattr(
        ctypes, "WinDLL", lambda _name, **_kwargs: fake_kernel32, raising=False
    )
    assert _fresh_account_home() == found
    target = tmp_path / "file.txt"
    _write(target)
    assert target.read_bytes() == b"data"


def test_a_failed_lookup_protects_only_added_homes_and_is_tried_again(
    fake_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    found = _fresh_account_home()
    assert found is not None

    def fail() -> str:
        raise OSError("no record")

    for name in (
        "_windows_profile",
        "_volatile_profile",
        "_passwd_home_effective",
        "_passwd_home_real",
    ):
        monkeypatch.setattr(home_write_guard, name, fail)
    assert _fresh_account_home() is None
    assert set(home_write_guard.protected_roots()) == {
        str(_under(fake_home, root)) for root in _ROOTS
    }
    with pytest.raises(home_write_guard.RealHomeWriteError):
        _write(fake_home / ".codex" / "AGENTS.md")
    _write(tmp_path / "other" / "file.txt")
    monkeypatch.undo()
    # The failure was not cached: the next check finds the home again.
    assert home_write_guard.account_home() == found


def _link_folder(link: Path, target: Path) -> None:
    """Make *link* a folder link to *target*, or skip when the host cannot."""
    target.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("this host cannot create a folder link")
        import _winapi

        try:
            _winapi.CreateJunction(str(target), str(link))
        except OSError as exc:
            pytest.skip(f"this host cannot create a junction: {exc}")


def test_a_link_into_a_protected_folder_is_refused(tmp_path: Path) -> None:
    home = tmp_path / "account-home"
    alias = tmp_path / "alias"
    _link_folder(alias, home / ".claude")
    home_write_guard.also_protect_home(home)
    with pytest.raises(home_write_guard.RealHomeWriteError):
        _write(alias / "settings.json")
    assert _everything_in(home / ".claude") == []


def test_a_linked_config_folder_is_protected_under_both_spellings(
    tmp_path: Path,
) -> None:
    home = tmp_path / "account-home"
    _link_folder(home / ".config", home / "dotfiles" / "config")
    home_write_guard.also_protect_home(home)
    for target in (
        home / ".config" / "apothem" / "profile.yaml",
        home / "dotfiles" / "config" / "apothem" / "profile.yaml",
    ):
        with pytest.raises(home_write_guard.RealHomeWriteError):
            _write(target)
    assert _everything_in(home / "dotfiles" / "config") == []


def _short_name(path: Path) -> str | None:
    """Return the 8.3 spelling of *path*, or None when the volume has none."""
    loader = type(ctypes.windll.kernel32)  # type: ignore[attr-defined]
    kernel32 = loader("kernel32")
    buffer = ctypes.create_unicode_buffer(1024)
    size = kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    if not size or buffer.value.lower() == str(path).lower():
        return None
    return str(buffer.value)


@pytest.mark.skipif(sys.platform != "win32", reason="8.3 names are a Windows thing")
def test_a_short_name_spelling_and_a_deep_missing_path_are_refused(
    tmp_path: Path,
) -> None:
    home = tmp_path / "a rather long account home name"
    (home / ".claude").mkdir(parents=True)
    short = _short_name(home)
    if short is None:
        pytest.skip("this volume keeps no 8.3 names")
    home_write_guard.also_protect_home(home)
    with pytest.raises(home_write_guard.RealHomeWriteError):
        _write(Path(short) / ".claude" / "settings.json")
    with pytest.raises(home_write_guard.RealHomeWriteError):
        _write(home / ".claude" / "a" / "b" / "c" / "settings.json")
    assert _everything_in(home / ".claude") == []


def test_the_refusal_names_the_path_the_folder_the_test_and_the_fix(
    fake_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = fake_home / ".apothem" / "state" / "ledger.jsonl"
    with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
        _write(target)
    error = caught.value
    root = str(fake_home / ".apothem")
    message = str(error)
    assert str(target) in message
    assert root in message
    # Only the protected folder is known to be untouched, so only it is named.
    assert f"Nothing in {root} was changed." in message
    assert "Nothing was changed" not in message
    assert os.environ[home_write_guard.PYTEST_VARIABLE] in message
    assert "tests/conftest.py" in message
    assert "without PYTEST_CURRENT_TEST" in message
    assert isinstance(error, OSError)
    assert error.errno is None
    assert error.path == str(target)
    assert error.protected_root == root
    assert error.operation == "write"
    assert home_write_guard.refusals() == (error,)
    with pytest.raises(home_write_guard.RealHomeWriteError):
        _append(target)
    with pytest.raises(home_write_guard.RealHomeWriteError):
        _lock(fake_home / ".claude" / "x.lock")
    lines = capsys.readouterr().err.splitlines()
    assert [line for line in lines if root in line] == [
        f"RealHomeWriteError: {message}"
    ]
    assert len([line for line in lines if "RealHomeWriteError" in line]) == 2
    assert len(home_write_guard.drain_refusals()) == 3
    assert home_write_guard.refusals() == ()


def test_would_refuse_never_raises_and_logs_nothing(fake_home: Path) -> None:
    assert home_write_guard.would_refuse(fake_home / ".claude" / "x")
    assert not home_write_guard.would_refuse(fake_home / "x")
    assert home_write_guard.refusals() == ()


def test_adding_a_home_keeps_the_account_home_protected(fake_home: Path) -> None:
    account = home_write_guard.account_home()
    roots = home_write_guard.protected_roots()
    assert str(_under(fake_home, ".claude")) in roots
    if account is not None:
        assert str(Path(account) / ".claude") in roots
    home_write_guard.clear_extra_homes()
    assert str(_under(fake_home, ".claude")) not in home_write_guard.protected_roots()


def test_a_refusal_is_written_once_per_folder_in_each_test(
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    claude = fake_home / ".claude" / "x"
    apothem = fake_home / ".apothem" / "x"
    phases = [
        ("probe.py::test_one (setup)", claude),
        ("probe.py::test_one (call)", claude),
        ("probe.py::test_one (call)", apothem),
        ("probe.py::test_one (teardown)", claude),
        ("probe.py::test_two (call)", claude),
        ("probe.py::test_two (teardown)", claude),
        ("probe.py::test_one (call)", claude),
    ]
    for current, target in phases:
        monkeypatch.setenv(home_write_guard.PYTEST_VARIABLE, current)
        with pytest.raises(home_write_guard.RealHomeWriteError):
            home_write_guard.refuse_real_home_write(target, operation="write")
    notices = [
        line
        for line in capsys.readouterr().err.splitlines()
        if line.startswith("RealHomeWriteError: ")
    ]
    # One notice for each protected folder in each test, whatever the phase; a
    # test that refuses again after another one ran is announced again.
    assert [
        (
            line.split(" (probe.py::")[1].split(" (")[0],
            str(fake_home / ".claude") in line,
        )
        for line in notices
    ] == [
        ("test_one", True),
        ("test_one", False),
        ("test_two", True),
        ("test_one", True),
    ]
    assert len(home_write_guard.drain_refusals()) == len(phases)


def _fake_open_key(*_args: object) -> contextlib.AbstractContextManager[object]:
    return contextlib.nullcontext(object())


def test_a_faked_system_lookup_neither_changes_nor_poisons_the_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    found = _fresh_account_home()
    assert found is not None
    fake = str(tmp_path / "fake-home")
    if os.name == "nt":
        import winreg

        def fake_dll(*_args: object, **_kwargs: object) -> object:
            raise OSError("a fake library")

        monkeypatch.setattr(ctypes, "WinDLL", fake_dll, raising=False)
        monkeypatch.setattr(
            ctypes, "windll", SimpleNamespace(_dlltype=fake_dll), raising=False
        )
        monkeypatch.setattr(winreg, "OpenKey", _fake_open_key)
        monkeypatch.setattr(winreg, "QueryValueEx", lambda *_args: (fake, 1))
        # The fakes answer for anyone who looks the home up through them.
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "x") as key:
            assert winreg.QueryValueEx(key, "USERPROFILE")[0] == fake
    else:
        pwd = pytest.importorskip("pwd")
        monkeypatch.setattr(pwd, "getpwuid", lambda _uid: SimpleNamespace(pw_dir=fake))
        monkeypatch.setattr(os, "geteuid", lambda: 0)
        monkeypatch.setattr(os, "getuid", lambda: 0)
        assert pwd.getpwuid(os.geteuid()).pw_dir == fake
    assert _fresh_account_home() == found
    monkeypatch.undo()
    # The lookup made under the fakes is the one cached, and it is the real home.
    assert home_write_guard.account_home() == found
    assert _fresh_account_home() == found


def test_the_system_functions_are_bound_without_a_path() -> None:
    bound = home_write_guard._SYSTEM
    expected = (
        {"ctypes.WinDLL", "winreg.QueryValueEx", "uuid.UUID"}
        if os.name == "nt"
        else {"pwd.getpwuid", "os.geteuid", "os.getuid"}
    )
    assert expected <= set(bound)
    assert not [value for value in bound.values() if isinstance(value, (str, Path))]


def test_a_project_root_at_the_home_is_refused(
    fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    link = tmp_path / "home-link"
    _link_folder(link, fake_home)
    spellings: list[str | Path] = [
        fake_home,
        str(fake_home) + os.sep,
        fake_home / "Projects" / "..",
        link,
    ]
    if os.name == "nt":
        spellings.append("\\\\?\\" + str(fake_home))
        drive, rest = os.path.splitdrive(str(fake_home))
        if drive.endswith(":"):
            spellings.append(f"\\\\localhost\\{drive[0]}${rest}")
    for spelling in spellings:
        assert home_write_guard.would_refuse_project_root(spelling), spelling
        with pytest.raises(home_write_guard.RealHomeWriteError) as caught:
            home_write_guard.refuse_project_root_at_home(spelling, operation="install")
        error = caught.value
        assert error.protected_root == str(fake_home)
        assert error.operation == "install"
        assert error.path == str(spelling)
        message = str(error)
        assert f"it is {fake_home}, this account's real home" in message
        assert "stopped before writing anything for this project" in message
        assert "Nothing was changed" not in message
    assert len(home_write_guard.drain_refusals()) == len(spellings)
    assert _everything_in(fake_home) == []


def test_a_project_folder_other_than_the_home_is_allowed(
    fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for allowed in (
        fake_home / "Projects" / "x",
        fake_home / "x",
        tmp_path,
        tmp_path / "project",
        fake_home.parent,
    ):
        assert not home_write_guard.would_refuse_project_root(allowed), allowed
        home_write_guard.refuse_project_root_at_home(allowed, operation="update")
    # A project inside a protected folder is the write checks' business.
    inside = fake_home / ".claude" / "project"
    assert not home_write_guard.would_refuse_project_root(inside)
    assert home_write_guard.would_refuse(inside / "AGENTS.md")
    monkeypatch.delenv(home_write_guard.PYTEST_VARIABLE)
    monkeypatch.delenv(home_write_guard.PYTEST_SESSION_VARIABLE, raising=False)
    assert not home_write_guard.would_refuse_project_root(fake_home)
    home_write_guard.refuse_project_root_at_home(fake_home, operation="uninstall")
    assert home_write_guard.refusals() == ()


def test_the_account_home_itself_is_refused_as_a_project_root() -> None:
    account = home_write_guard.account_home()
    if account is None:
        pytest.skip("the system has no record of this account's home")
    assert home_write_guard.would_refuse_project_root(account)
    assert not home_write_guard.would_refuse_project_root(
        Path(account) / "Projects" / "x"
    )
    assert home_write_guard.refusals() == ()
