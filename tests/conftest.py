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
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest

from apothem.harnesses._shared import install_driver, install_driver_types
from apothem.lib import install_ledger

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
    """
    home = tmp_path_factory.mktemp("user-home")
    _redirect_home(monkeypatch, home)
    monkeypatch.delenv("CODEX_HOME", raising=False)
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
