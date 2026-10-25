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
redirected for the whole session (for module- and session-scoped fixtures that
run an install) and again for every test; ``Path.home()`` then resolves under
the temporary root. ``apothem.lib.propagation.USER_HOME`` stays unset on
purpose: ``Path.home`` is the one seam, so a test that patches it keeps working.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest

from apothem.harnesses._shared import install_driver
from apothem.lib import install_ledger


def _redirect_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    """Point every spelling of the user home at *home* and prove it took effect."""
    home.mkdir(parents=True, exist_ok=True)
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(home))
    # ``Path.home()`` reads USERPROFILE first on Windows, then HOMEDRIVE and
    # HOMEPATH; drop the latter so no fallback can name the real home.
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)
    resolved = Path.home().resolve()
    assert resolved == home.resolve(), (
        f"test HOME isolation failed: Path.home() is {resolved}, expected {home}"
    )


@pytest.fixture(scope="session", autouse=True)
def _isolate_session_home(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Redirect the user home for the whole session.

    Module- and session-scoped fixtures run before any function-scoped autouse
    fixture. One that runs an install would otherwise write the developer's
    real ``~/.agents/skills``; this keeps those writes inside a temporary
    directory. Each test then gets its own home from ``_isolate_user_home``.
    """
    with pytest.MonkeyPatch.context() as monkeypatch:
        _redirect_home(monkeypatch, tmp_path_factory.mktemp("session-home"))
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
    the Codex root.
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
    counters under ``hooks/lib/state_dir.py``'s per-user root (by default
    ``~/.local/state/apothem``). Without this redirect a hook test would write
    real state under the developer's home. Tests that set
    ``APOTHEM_HOOK_STATE_DIR`` themselves still override this default.
    """
    monkeypatch.setenv(
        "APOTHEM_HOOK_STATE_DIR", str(tmp_path_factory.mktemp("hook-state"))
    )
