# SPDX-License-Identifier: MIT

"""Suite-wide pytest configuration: source bootstrap + state and HOME isolation.

The ``sys.path`` inserts make ``apothem`` importable from a plain checkout
(no editable install) for every test subtree — unit, integration, property,
packaging, hooks, conformity, scripts — instead of only the two subtrees
that used to carry their own copy of the insert, and make the repo root
importable so the cross-subtree test helpers under ``tests/_shared/``
resolve as ``tests._shared`` namespace-package imports regardless of how
pytest is invoked. The autouse ledger isolation applies suite-wide for the
same reason: any subtree's test may exercise an install path, and none may
write a real ledger under the developer's home.

The user home is isolated too. Some manifest targets sit in the user home
whatever the install root is (``${USER_HOME}/.agents/skills/``), so an install
into a temporary root still writes there. ``HOME`` and ``USERPROFILE`` are
redirected for the whole session and again for every test; ``Path.home()`` then
resolves under the temporary root. The session-wide redirect covers every fixture
of a narrower scope (module, class, package), because pytest sets up
higher-scoped fixtures first. It does not cover a session-scoped fixture that
pytest sets up before it: pytest sets up session-scoped autouse fixtures in the
order they were registered (a plugin's first, then a conftest's by name), not by
intent, so a session-scoped fixture that runs an install has to request
``_isolate_session_home`` as a parameter. ``apothem.lib.propagation.USER_HOME``
stays unset on purpose: ``Path.home`` is the one seam, so a test that patches it
keeps working.

Two install state roots are bound from ``Path.home()`` when their modules are
imported, which is while this file loads and before any fixture runs, so
redirecting ``HOME`` does not move them: ``install_ledger.STATE_ROOT``
(``~/.apothem/state``, which holds the ledgers and the install lock files) and
``install_driver.BACKUP_ROOT`` (``~/.apothem/backups``; the binding in
``install_driver_types`` that it re-exports moves with it). They are re-pointed
explicitly, twice. ``_isolate_session_home`` moves them into the session home for
the whole session, which covers module-scoped fixtures: those are built before
any function-scoped autouse fixture, and one that runs an install would
otherwise write its lock files, ledger lines and backups under the developer's
real ``~/.apothem``. ``_isolate_install_ledger`` and ``_isolate_backup_root``
then give each test its own. The one other home-derived module constant,
``apothem.conformity.gate._DEFAULT_CLAUDE_SCOPE``, only names a scope the gate
compares paths against; nothing writes through it.

Two environment variables decide where a write lands whatever ``HOME`` says, and
they are set twice in the same way. ``CODEX_HOME`` moves the Codex root, so a
developer's own setting would send a Codex install into their real Codex home;
it is cleared. ``APOTHEM_HOOK_STATE_DIR`` overrides the folder where the
session-end gate and the compaction tracker keep their per-session counters.
Without it that folder comes from ``CLAUDE_PLUGIN_DATA``, ``XDG_STATE_HOME`` or,
on Windows, ``LOCALAPPDATA``, none of which follows a redirected ``HOME``, so it
names a temporary folder. ``_isolate_session_home`` does both for the whole
session; ``_isolate_user_home`` and ``_isolate_hook_state`` do them again for
each test. Every home redirect also clears the four XDG base directories
(``XDG_CONFIG_HOME``, ``XDG_STATE_HOME``, ``XDG_DATA_HOME``, ``XDG_CACHE_HOME``),
so code and child processes that read them fall back to the temporary home.

``tests/unit/test_suite_state_isolation.py`` pins the session-level redirect and
fails on any module-level path that still names the real home, so a root added
later fails the suite until it is redirected here or listed there as read-only.
Writes made before any fixture runs (collection-time code, a plugin's
session-scoped fixture) are outside both redirects; the check for those is to run
pytest with ``HOME`` and ``USERPROFILE`` pointing at an empty folder and confirm
nothing appears in it afterwards. The ``home-isolation`` job in
``.github/workflows/ci.yml`` does that for the whole suite, with the XDG base
directories on empty folders too.

The isolation fixtures above are all named with a leading underscore, and a
``from <this module> import *`` skips such names. A probe folder whose conftest
star-imports this file therefore gets none of them, and its tests run Apothem
against the developer's real home: that once deleted a real install ledger and
overwrote a file under ``~/.config/apothem``. The real-home guard at the end of
this file stops such a test before its body runs.

The guard is ``pytest_real_home_guard``, a ``pytest_runtest_call`` hook wrapper.
Its name has no leading underscore, so a star import carries it, and pytest
registers the hooks of every conftest it loads, under whatever name the conftest
got them, so the guard runs wherever this file's names land. Its ``specname``
ties it to ``pytest_runtest_call`` under a name of its own, so a
``pytest_runtest_call`` that a star-importing conftest defines, or that this file
gains later, does not replace it. It is a hook, not an autouse fixture: a fixture
runs at a point in the setup that depends on its scope, its name and the order
the conftests were registered, and a fixture the test requests can still move
the home after it. A ``pytest_runtest_call`` wrapper starts once every fixture of
the test is set up, and this one is the last wrapper to start (``trylast``), so
it sees the environment the body will see. It fails the test before it yields,
so the body never starts.

The guard captures the real home once, when this file is imported and before
any fixture runs: ``HOME``, ``USERPROFILE``, ``HOMEDRIVE`` with ``HOMEPATH``, ``~``
and, on POSIX, the account's home from ``pwd``. When a job points ``HOME`` at a
temporary folder for the whole run, that folder is the real home. Before each
test body it fails the test when ``HOME``, ``USERPROFILE``, ``Path.home()``,
``propagation.user_home()``, the data home, the ``~/.config/apothem`` folder, the
install ledger root or the backup root, as Apothem computes them at that moment,
resolves to one of those homes, or into the ``.apothem`` or ``.config/apothem``
folder of one. A folder that only sits somewhere below a real home stays allowed:
the Windows temporary folder is under ``C:\\Users\\<name>``, and every test's
temporary home is in it. The guard uses ``os.path`` rather than
``Path.resolve()``, which on Python 3.10 to 3.12 calls ``Path.stat``, a method
some tests patch.

The guard cannot see what a test body changes after it starts, what a fixture
writes while it is set up or torn down, the environment a test builds for a
child process, or code that runs outside pytest.
``tests/unit/test_real_home_guard.py`` runs it in a pytester session, with this
file loaded as a plugin and with a probe conftest that star-imports it.
"""

from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Callable, Generator, Iterable, Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest

from apothem.harnesses._shared import install_driver, install_driver_types
from apothem.lib import install_ledger, propagation
from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.profile import DEFAULT_PROFILE_PATH

_XDG_BASE_DIRECTORIES = (
    "XDG_CONFIG_HOME",
    "XDG_STATE_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
)


def _redirect_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    """Point every spelling of the user home at *home* and prove it took effect."""
    home.mkdir(parents=True, exist_ok=True)
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(home))
    # ``Path.home()`` reads USERPROFILE first on Windows, then HOMEDRIVE and
    # HOMEPATH; drop the latter so no fallback can name the real home.
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)
    # The code under test and the tools a test launches (pwsh, git, node) read
    # the XDG base directories before they fall back to the home, so a
    # developer's own setting would send their writes out of *home*. pwsh, for
    # one, keeps its startup profile and telemetry id in $XDG_CACHE_HOME.
    for name in _XDG_BASE_DIRECTORIES:
        monkeypatch.delenv(name, raising=False)
    resolved = Path.home().resolve()
    assert resolved == home.resolve(), (
        f"test HOME isolation failed: Path.home() is {resolved}, expected {home}"
    )


@pytest.fixture(scope="session", autouse=True)
def _isolate_session_home(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Redirect the user home and the install state roots for the whole session.

    Pytest sets this fixture up before every module-, class- and package-scoped
    fixture, and those before any function-scoped autouse fixture. A fixture of
    that kind that runs an install would otherwise write the developer's real
    ``~/.agents/skills``; this keeps those writes inside a temporary directory.
    Each test then gets its own home from ``_isolate_user_home``.

    ``HOME`` and ``USERPROFILE`` cannot move ``install_ledger.STATE_ROOT`` or
    ``install_driver.BACKUP_ROOT``: both were computed from ``Path.home()`` when
    their modules were imported, so they still name the developer's
    ``~/.apothem`` after the redirect. They are set to the same places under the
    session home here, in the same ``MonkeyPatch`` context, so the install lock
    files, ledger lines and backups of a module-scoped install fixture land in
    the temporary directory too. Each test then gets its own roots from
    ``_isolate_install_ledger`` and ``_isolate_backup_root``.

    The same goes for the two environment variables that place a write whatever
    ``HOME`` says: ``CODEX_HOME`` is cleared, so a module-scoped fixture that
    installs for Codex writes into the session home rather than a developer's
    own Codex root, and ``APOTHEM_HOOK_STATE_DIR`` names a session folder, so one
    that runs a stateful hook keeps its counters there rather than in the
    developer's own hook state folder. Each test then gets the same from
    ``_isolate_user_home`` and ``_isolate_hook_state``.

    A session-scoped fixture that runs an install has to request this fixture as
    a parameter. pytest sets up session-scoped autouse fixtures in the order they
    were registered, a plugin's first and then a conftest's by name, so one named
    ``_install_...`` would run before ``_isolate_session_home`` and write under
    the real home.
    """
    with pytest.MonkeyPatch.context() as monkeypatch:
        home = tmp_path_factory.mktemp("session-home")
        _redirect_home(monkeypatch, home)
        monkeypatch.delenv("CODEX_HOME", raising=False)
        # A developer's own OPENCODE_CONFIG_DIR would add an OpenCode install
        # note to every OpenCode install a fixture runs.
        monkeypatch.delenv("OPENCODE_CONFIG_DIR", raising=False)
        monkeypatch.setenv(
            "APOTHEM_HOOK_STATE_DIR", str(tmp_path_factory.mktemp("session-hook-state"))
        )
        monkeypatch.setattr(install_ledger, "STATE_ROOT", home / ".apothem" / "state")
        # ``install_driver.BACKUP_ROOT`` is the name every reader goes through. It
        # is a copy of the binding ``install_driver_types`` defines, so that one
        # moves too: no copy of the default is left naming the real home.
        for module in (install_driver, install_driver_types):
            monkeypatch.setattr(module, "BACKUP_ROOT", home / ".apothem" / "backups")
        yield


@pytest.fixture(autouse=True)
def _isolate_user_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Give every test its own user home, a sibling of its ``tmp_path``.

    The home is created with ``tmp_path_factory`` rather than under the
    per-test ``tmp_path`` so a file-set snapshot of ``tmp_path`` never picks it
    up. A test that wants the home reads ``Path.home()`` or requests this
    fixture. ``CODEX_HOME`` is cleared so a developer's own setting cannot move
    the Codex root; ``_isolate_session_home`` has already cleared it for the
    session, and this clears it again in case a fixture set it.
    ``OPENCODE_CONFIG_DIR`` is cleared the same way, so a developer's own
    setting cannot add an OpenCode install note (``_redirect_home`` clears
    ``XDG_CONFIG_HOME``, which would move the OpenCode root).
    """
    home = tmp_path_factory.mktemp("user-home")
    _redirect_home(monkeypatch, home)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("OPENCODE_CONFIG_DIR", raising=False)
    return home


@pytest.fixture(autouse=True)
def _isolate_install_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect the install ledger to a per-test directory.

    ``install_ledger.STATE_ROOT`` defaults to ``~/.apothem/state``; without this
    a test that installs would write a real ledger under the developer's home and
    a later test's ledger-driven uninstall could read stale cross-test records.
    Mirrors the per-test ``BACKUP_ROOT`` isolation ``_isolate_backup_root`` gives.

    The default is bound when ``install_ledger`` is imported, so it does not
    follow the redirected ``HOME``. This fixture covers the test itself; the
    module-, class- and package-scoped fixtures built before it get the
    session-wide root from ``_isolate_session_home``.
    """
    monkeypatch.setattr(install_ledger, "STATE_ROOT", tmp_path / "apothem-ledger-state")


@pytest.fixture(autouse=True)
def _isolate_backup_root(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redirect the backup root to a per-test directory for every test.

    ``install_driver.BACKUP_ROOT`` defaults to ``~/.apothem/backups``. A test that
    triggers a write (any install/update over an existing target) captures a
    backup set there; without this redirect the suite leaks hundreds of backup
    trees into the developer's real home. Redirecting it suite-wide guarantees no
    test writes under the real home, whether or not the individual test remembered
    to monkeypatch it.

    The default is bound when ``install_driver`` is imported, so it does not
    follow the redirected ``HOME``. This fixture covers the test itself; the
    module-, class- and package-scoped fixtures built before it get the
    session-wide root from ``_isolate_session_home``.

    The redirect target comes from ``tmp_path_factory`` rather than the per-test
    ``tmp_path`` so it is a sibling of — never a child of — the tree a test walks
    for a materialized-file snapshot; a content-fidelity walk over ``tmp_path``
    therefore never picks up backup residue. Tests that set ``BACKUP_ROOT``
    themselves still override this default; their explicit target simply wins.
    """
    monkeypatch.setattr(
        install_driver,
        "BACKUP_ROOT",
        tmp_path_factory.mktemp("apothem-backups-default"),
    )


@pytest.fixture(autouse=True)
def _isolate_hook_state(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redirect the per-user hook state directory for every test.

    The session-end gate and the proactive-compaction tracker keep per-session
    counters under ``hooks/lib/state_dir.py``'s per-user root: ``<data>/state``
    when ``CLAUDE_PLUGIN_DATA`` is set, ``$XDG_STATE_HOME/apothem`` when that is
    set, else ``%LOCALAPPDATA%\\apothem\\state`` on Windows and
    ``~/.local/state/apothem`` elsewhere. Without this redirect a hook test would
    write real state there. ``_isolate_session_home`` points the variable at a
    session folder for the fixtures built before this one. Tests that set
    ``APOTHEM_HOOK_STATE_DIR`` themselves still override this default.
    """
    monkeypatch.setenv(
        "APOTHEM_HOOK_STATE_DIR", str(tmp_path_factory.mktemp("hook-state"))
    )


# --- Real-home guard --------------------------------------------------------
#
# pytest calls ``pytest_real_home_guard``, the one name in this section a star
# import carries. The helpers keep their leading underscore: the hook reaches
# them through this module's globals, wherever the hook itself was imported to.

#: The harness name the guard asks ``install_ledger.ledger_path`` about. Any name
#: gives the same root; this one is not a real harness, so it cannot be mistaken
#: for a ledger the test made.
_GUARD_HARNESS = "real-home-guard"


def _resolved(path: str, known: dict[str, str] | None = None) -> str:
    """Return *path* with its links resolved and its case normalized.

    *known* maps each absolute path one check has resolved to its result. A path
    below one of them that does not exist is not passed to ``os.path.realpath``,
    which costs a few hundred microseconds on Windows: a missing folder holds no
    link, so the path resolves to its folder's result plus its own name, and one
    ``lstat`` call settles that. The data home and the ``~/.config/apothem``
    folder below a test's own home cost one or two such calls instead of a
    ``realpath`` each.

    ``os.path.realpath`` and ``os.path.lexists`` read the disk through
    ``os.lstat``; a fixture can patch that, so a failure falls back to a full
    ``realpath`` and then to the absolute path, instead of failing the test for a
    reason of its own. ``Path.resolve()`` is not used: on Python 3.10 to 3.12 it
    calls ``Path.stat``, which some tests patch.
    """
    path = os.path.abspath(path)  # noqa: PTH100 - text only, no Path.stat
    if known is None:
        return _realpath_key(path)
    if path not in known:
        folder, name = os.path.split(path)
        if name and _at_or_below(folder, known) and not _lexists(path):
            above = _resolved(folder, known).rstrip(os.sep)
            known[path] = above + os.sep + os.path.normcase(name)
        else:
            known[path] = _realpath_key(path)
    return known[path]


def _realpath_key(path: str) -> str:
    try:
        resolved = os.path.realpath(path)
    except Exception:
        resolved = path
    return os.path.normcase(resolved)


def _at_or_below(folder: str, known: dict[str, str]) -> bool:
    """Return whether *folder* or a folder above it is in *known*."""
    while folder not in known:
        folder, name = os.path.split(folder)
        if not name:
            return False
    return True


def _lexists(path: str) -> bool:
    try:
        return os.path.lexists(path)
    except Exception:
        return True  # unsure: let realpath decide


def _startup_homes() -> dict[str, str]:
    """Map each spelling of the home this process started with to how it reads.

    The keys are resolved and case-normalized for comparing; the values keep the
    resolved path's own case for the failure message.
    """
    candidates = [os.environ.get("HOME"), os.environ.get("USERPROFILE")]
    # Windows falls back to these two when USERPROFILE is unset.
    drive, path = os.environ.get("HOMEDRIVE"), os.environ.get("HOMEPATH")
    if drive and path:
        candidates.append(drive + path)
    # Path.expanduser raises RuntimeError when no home can be determined.
    with contextlib.suppress(RuntimeError):
        candidates.append(str(Path("~").expanduser()))
    if sys.platform != "win32":
        import pwd

        # POSIX falls back to the account's home when HOME is unset. KeyError:
        # the uid has no passwd entry, as in some containers.
        with contextlib.suppress(KeyError):
            candidates.append(pwd.getpwuid(os.getuid()).pw_dir)
    homes: dict[str, str] = {}
    for home in candidates:
        if home and not home.startswith("~"):
            homes.setdefault(_resolved(home), _shown(home))
    return homes


def _shown(path: str) -> str:
    """Return *path* resolved, in its own case, for a failure message."""
    try:
        return os.path.realpath(path)
    except Exception:
        return path


def _startup_apothem_folders(
    homes: Iterable[str],
) -> tuple[tuple[str, str, str], ...]:
    """Return ``(key, key prefix, shown)`` for each folder Apothem writes in a home.

    Each home's ``.apothem`` (the data home, which holds the ledgers and the
    backups) and ``.config/apothem`` (the support folder the install manifest
    names, and the default profile's folder) are listed as spelled and as
    resolved, in case the real folder is a link. The ledger and backup roots as
    the product bound them at import are listed too: they come from
    ``Path.home()`` at that moment, which is the real home unless something
    imported them earlier under a different one. The key prefix is the key with
    one trailing separator, for the "inside" test.
    """
    folders: dict[str, str] = {}
    spelled = [
        str(folder)
        for home in homes
        for folder in (
            resolve_shared_data_home(base=Path(home)).root,
            Path(home, ".config", "apothem"),
        )
    ]
    for folder in spelled:
        folders.setdefault(os.path.normcase(folder), folder)
    for folder in [
        *spelled,
        str(install_ledger.ledger_path(_GUARD_HARNESS).parent.parent),
        str(install_driver.BACKUP_ROOT),
    ]:
        folders.setdefault(_resolved(folder), _shown(folder))
    return tuple(
        (key, key.rstrip(os.sep) + os.sep, shown) for key, shown in folders.items()
    )


_REAL_HOMES = _startup_homes()
_REAL_APOTHEM_FOLDERS = _startup_apothem_folders(_REAL_HOMES.values())
# Bound now, so a test that patches the module attribute with a mock neither sees
# an extra call nor changes what the guard computes.
_ledger_path = install_ledger.ledger_path


def _real_location(path: str, resolved: str) -> str | None:
    """Say which real home or Apothem folder *path* names, else ``None``.

    *resolved* is *path* as ``_resolved`` returns it. Only an exact home counts,
    and an Apothem folder in one or anything inside it. A folder elsewhere below
    a real home, such as the Windows temporary folder, does not.
    """
    shown = _REAL_HOMES.get(resolved)
    if shown is not None:
        return _naming("the real home", shown, path)
    for folder, prefix, shown in _REAL_APOTHEM_FOLDERS:
        if resolved == folder:
            return _naming("the real Apothem folder", shown, path)
        if resolved.startswith(prefix):
            return f"inside the real Apothem folder {shown}"
    return None


def _naming(what: str, shown: str, path: str) -> str:
    """Return *what*, followed by *shown* unless *path* already reads the same."""
    spelled = os.path.abspath(path)  # noqa: PTH100 - text only, no Path.stat
    if os.path.normcase(spelled) == os.path.normcase(shown):
        return what
    return f"{what} {shown}"


def _called(function: Callable[[], object]) -> str | None:
    """Return the path *function* gives, as text, or ``None`` when it gives none."""
    try:
        return str(os.fspath(function()))
    except Exception:  # a test patched it to fail, or removed every home variable
        return None


def _current_locations() -> list[tuple[str, str | None]]:
    """Return ``(name, path)`` for each place Apothem would use right now.

    Each comes from the function or attribute the product reads at call time:
    ``Path.home()`` for the data home (``resolve_install_data_home``),
    ``propagation.user_home()`` for every ``${USER_HOME}`` target the install
    manifest names, such as ``~/.config/apothem/rules``, ``ledger_path()`` for
    the install ledgers and lock files, and ``install_driver.BACKUP_ROOT`` for
    the backups.
    """
    home = _called(Path.home)
    user_home = _called(propagation.user_home)
    return [
        ("HOME", os.environ.get("HOME")),
        ("USERPROFILE", os.environ.get("USERPROFILE")),
        ("Path.home()", home),
        ("propagation.user_home()", user_home),
        (
            "the data home",
            home and _called(lambda: resolve_shared_data_home(base=Path(home)).root),
        ),
        (
            "the support folder ~/.config/apothem",
            user_home and str(Path(user_home, ".config", "apothem")),
        ),
        (
            "the default profile's folder",
            _called(lambda: DEFAULT_PROFILE_PATH.expanduser().parent),
        ),
        (
            "the install ledger root (install_ledger.STATE_ROOT)",
            _called(lambda: _ledger_path(_GUARD_HARNESS).parent.parent),
        ),
        (
            "the backup root (install_driver.BACKUP_ROOT)",
            _called(lambda: install_driver.BACKUP_ROOT),
        ),
    ]


def _real_home_findings(locations: Iterable[tuple[str, str | None]]) -> list[str]:
    """Return one line per path that names a real home or an Apothem folder in one.

    Names that share a path share a line, and each path is resolved once. In a
    test with its own home that is five paths: the home, two folders below it
    (settled with ``lstat`` while they do not exist), the ledger root and the
    backup root, so three ``realpath`` calls.
    """
    names_by_path: dict[str, list[str]] = {}
    for name, path in locations:
        if path and not path.startswith("~"):
            names_by_path.setdefault(path, []).append(name)
    known: dict[str, str] = {}
    findings = []
    for path, names in names_by_path.items():
        real = _real_location(path, _resolved(path, known))
        if real is not None:
            findings.append(f"{', '.join(names)}: {path} is {real}")
    return findings


def _guard_message(findings: list[str]) -> str:
    lines = "\n".join(f"  - {finding}" for finding in findings)
    return (
        "real-home guard: stopped before the test body ran, because Apothem "
        "would use the real home.\n"
        f"{lines}\n"
        "The real home is the one this process had when tests/conftest.py was "
        "imported. Tests under tests/ get a temporary home from the isolation "
        "fixtures in tests/conftest.py, unless a fixture undoes them. A conftest "
        "that star-imports tests/conftest.py does not get those fixtures, "
        "because a star import skips names that start with '_'. Never "
        "star-import a conftest: put the probe under tests/. A test that has to "
        "live elsewhere points HOME and USERPROFILE at a temporary folder and "
        "re-points install_ledger.STATE_ROOT and install_driver.BACKUP_ROOT in a "
        "fixture of its own. See tests/README.md."
    )


@pytest.hookimpl(wrapper=True, trylast=True, specname="pytest_runtest_call")
def pytest_real_home_guard() -> Generator[None, object, object]:
    """Fail the test before its body runs when Apothem would use the real home.

    pytest runs this ``pytest_runtest_call`` wrapper once every fixture of the
    test is set up, as the last wrapper to start, right before it calls the
    test. Failing before ``yield`` means the body never starts.
    """
    findings = _real_home_findings(_current_locations())
    if findings:
        pytest.fail(_guard_message(findings), pytrace=False)
    return (yield)
