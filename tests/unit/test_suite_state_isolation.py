# SPDX-License-Identifier: MIT

"""A module-scoped fixture writes into the session's temp tree, not the real home.

``install_ledger.STATE_ROOT`` and ``install_driver.BACKUP_ROOT`` are built from
``Path.home()`` when their modules are imported, which is before any fixture
runs, so redirecting ``HOME`` afterwards cannot move them. A module-scoped
fixture is built before the function-scoped autouse fixtures that re-point them
for each test, so one that installs a harness would write its ``*.install.lock``
files and its ledger line under the developer's real ``~/.apothem/state``. The
session-scoped ``_isolate_session_home`` in ``tests/conftest.py`` re-points both
for the whole session, and these tests pin that.

A test cannot read the session-level values itself, because the per-test
redirects are already in place when it runs. The fixture below records them
during module setup, the point at which an install fixture in any other module
uses them. The temporary directory can sit inside the user home (on Windows it
normally does), so the check against the real tree names the ``.apothem``
folder, not the whole home.

Two environment variables place a write whatever ``HOME`` says: ``CODEX_HOME``
(the Codex root) and ``APOTHEM_HOOK_STATE_DIR`` (the hooks' state folder). The
same fixture records both, and the session fixture must have cleared the first
and pointed the second into the temp tree. A developer who never sets
``CODEX_HOME`` would see that check pass whatever the session fixture does, so
one more test runs the two checks again in a child pytest started with both
variables set to a developer's own folders.

Those roots are the ones that exist today. The last tests look for any other:
the same fixture scans the ``apothem`` modules the process holds for a
module-level path that still names the home the process started with, so a root
added later fails here until it is redirected in ``_isolate_session_home`` or
listed in ``_READ_ONLY``.

The scan reads ``sys.modules`` and imports nothing. A module first imported
during a fixture computes its roots from the home that is already redirected, so
it cannot hold a path to the real one; only a module imported before the first
fixture runs (by ``tests/conftest.py`` or by collecting a test file) can. The
checkout is exempt, so a home that sits inside it hides everything under it from
the scan; the tests that name the two roots do not depend on the scan and still
catch them.
"""

from __future__ import annotations

import os
import subprocess
import sys
import types
from collections.abc import Collection, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePath

import pytest

import apothem
from apothem.harnesses._shared import install_driver
from apothem.lib import install_ledger

# A test module is imported while pytest collects, before any fixture has run, so
# ``Path.home()`` here is still the home this process started with.
_STARTUP_HOME = Path.home()
_STARTUP_APOTHEM_TREE = _STARTUP_HOME / ".apothem"
# The conftest home redirects clear these, so nothing that reads them can write
# outside the temporary home.
_XDG_BASE_DIRECTORIES = (
    "XDG_CONFIG_HOME",
    "XDG_STATE_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
)

# Module-level paths built from ``__file__`` sit under the home whenever the
# checkout does: the package itself, and the repo root that the benchmarks name.
_CHECKOUT = Path(__file__).resolve().parents[2]
_PACKAGE_DIR = Path(apothem.__file__).resolve().parent

#: Module-level names that hold a path under the real home and keep it, because
#: nothing writes through them. The reason sits beside each name.
_READ_ONLY = {
    "apothem.conformity.gate._DEFAULT_CLAUDE_SCOPE": (
        "the scope root the gate compares write targets with; it is only read"
    ),
}

#: How many containers deep the scan looks inside a module-level value.
_SCAN_DEPTH = 3


@dataclass(frozen=True)
class _SeenDuringModuleSetup:
    """The user home and the install state roots, as module setup sees them."""

    home: Path
    state_root: Path
    backup_root: Path
    # The two environment variables that place a write whatever ``HOME`` says.
    codex_home: str | None
    hook_state_dir: str | None
    # XDG base-directory name -> value, for each one still set.
    xdg_set: dict[str, str]
    # ``module.name`` -> path, for each module-level path still under the startup home.
    module_level_paths: dict[str, str]


def _is_first_party(module_name: str) -> bool:
    return module_name == "apothem" or module_name.startswith("apothem.")


def _path_texts(value: object, depth: int = 0) -> Iterator[str]:
    """Yield the text of each path or string *value* holds, a few levels down.

    Reaches the shapes a module-level root takes: the value itself, a member of a
    tuple, list, set or dict, a function default, and a class attribute.
    """
    if isinstance(value, (str, PurePath)):
        yield str(value)
    elif depth >= _SCAN_DEPTH:
        return
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _path_texts(item, depth + 1)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _path_texts(item, depth + 1)
    elif isinstance(value, types.FunctionType):
        defaults = (*(value.__defaults__ or ()), *(value.__kwdefaults__ or {}).values())
        yield from _path_texts(defaults, depth + 1)
    elif isinstance(value, type) and _is_first_party(value.__module__ or ""):
        for item in vars(value).values():
            yield from _path_texts(item, depth + 1)


def _module_level_paths_under(
    modules: Iterable[types.ModuleType],
    homes: Collection[Path],
    exempt: Collection[Path],
) -> dict[str, str]:
    """Map ``module.name`` to the path each module-level binding holds under a home.

    A path inside an *exempt* root is left out, whichever way it is spelled.
    """
    found: dict[str, str] = {}
    for module in modules:
        for name, value in list(vars(module).items()):
            if name.startswith("__") or isinstance(value, types.ModuleType):
                continue
            if (
                isinstance(value, (types.FunctionType, type))
                and value.__module__ != module.__name__
            ):
                continue  # imported from another module, which reports it
            for text in _path_texts(value):
                path = Path(text)
                if not any(path.is_relative_to(home) for home in homes):
                    continue
                if not any(
                    spelling.is_relative_to(root)
                    for spelling in (path, path.resolve())
                    for root in exempt
                ):
                    found[f"{module.__name__}.{name}"] = text
    return found


def _first_party_modules() -> list[types.ModuleType]:
    """The ``apothem`` modules this process holds now (the vendored tree is not ours)."""
    return [
        module
        for name, module in list(sys.modules.items())
        if _is_first_party(name)
        and "._vendor" not in name
        and isinstance(module, types.ModuleType)
    ]


@pytest.fixture(scope="module")
def seen_during_module_setup(
    tmp_path_factory: pytest.TempPathFactory,
) -> _SeenDuringModuleSetup:
    """Record the home and the state roots while the module's fixtures are built.

    Module-scoped fixtures are built after the session-scoped autouse ones and
    before every function-scoped one, so these are the values an install
    fixture in another module would write through.
    """
    # Paths under the home that are not a root still naming the real home: the
    # redirected roots (they sit in the pytest temp tree, which is under the home
    # on Windows), the checkout and the package, and the interpreter.
    exempt = (
        tmp_path_factory.getbasetemp(),
        _CHECKOUT,
        _PACKAGE_DIR,
        Path(sys.prefix),
        Path(sys.base_prefix),
    )
    return _SeenDuringModuleSetup(
        home=Path.home(),
        state_root=install_ledger.STATE_ROOT,
        backup_root=install_driver.BACKUP_ROOT,
        codex_home=os.environ.get("CODEX_HOME"),
        hook_state_dir=os.environ.get("APOTHEM_HOOK_STATE_DIR"),
        xdg_set={
            name: os.environ[name]
            for name in _XDG_BASE_DIRECTORIES
            if name in os.environ
        },
        module_level_paths=_module_level_paths_under(
            _first_party_modules(),
            homes={_STARTUP_HOME, _STARTUP_HOME.resolve()},
            exempt={*exempt, *(root.resolve() for root in exempt)},
        ),
    )


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def test_the_user_home_is_redirected_during_module_setup(
    seen_during_module_setup: _SeenDuringModuleSetup,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    home = seen_during_module_setup.home
    assert _inside(home, tmp_path_factory.getbasetemp()), (
        f"Path.home() is {home} during module setup, outside the pytest temp "
        f"tree {tmp_path_factory.getbasetemp()}"
    )
    assert home.resolve() != _STARTUP_HOME.resolve(), (
        f"Path.home() is still the startup home {_STARTUP_HOME} during module setup"
    )


@pytest.mark.parametrize("name", ["state_root", "backup_root"])
def test_an_install_state_root_is_redirected_during_module_setup(
    name: str,
    seen_during_module_setup: _SeenDuringModuleSetup,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    root = getattr(seen_during_module_setup, name)
    assert _inside(root, tmp_path_factory.getbasetemp()), (
        f"{name} is {root} during module setup, outside the pytest temp tree "
        f"{tmp_path_factory.getbasetemp()}: a module-scoped install fixture "
        f"would write there"
    )
    assert not _inside(root, _STARTUP_APOTHEM_TREE), (
        f"{name} is {root} during module setup, inside the startup home's "
        f"{_STARTUP_APOTHEM_TREE}"
    )


def test_codex_home_is_cleared_during_module_setup(
    seen_during_module_setup: _SeenDuringModuleSetup,
) -> None:
    assert seen_during_module_setup.codex_home is None, (
        f"CODEX_HOME is {seen_during_module_setup.codex_home} during module setup: "
        "a module-scoped fixture that installs for Codex would write there"
    )


def test_the_xdg_base_directories_are_cleared_during_module_setup(
    seen_during_module_setup: _SeenDuringModuleSetup,
) -> None:
    assert seen_during_module_setup.xdg_set == {}, (
        f"{seen_during_module_setup.xdg_set} still set during module setup: code and "
        "the tools a fixture launches (pwsh keeps its cache in $XDG_CACHE_HOME) "
        "would write there instead of the temporary home"
    )


def test_the_xdg_base_directories_are_cleared_in_each_test() -> None:
    still_set = {
        name: os.environ[name] for name in _XDG_BASE_DIRECTORIES if name in os.environ
    }
    assert still_set == {}, f"{still_set} still set inside a test"


def test_the_hook_state_dir_is_redirected_during_module_setup(
    seen_during_module_setup: _SeenDuringModuleSetup,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    state_dir = seen_during_module_setup.hook_state_dir
    assert state_dir, (
        "APOTHEM_HOOK_STATE_DIR is unset during module setup: a module-scoped "
        "fixture that runs a stateful hook would write the developer's own hook state"
    )
    assert _inside(Path(state_dir), tmp_path_factory.getbasetemp()), (
        f"APOTHEM_HOOK_STATE_DIR is {state_dir} during module setup, outside the "
        f"pytest temp tree {tmp_path_factory.getbasetemp()}"
    )


#: The checks above that read the environment, re-run by the next test.
_ENVIRONMENT_CHECKS = (
    "test_codex_home_is_cleared_during_module_setup",
    "test_the_hook_state_dir_is_redirected_during_module_setup",
)


def test_a_developers_codex_home_and_hook_state_do_not_reach_module_setup(
    tmp_path: Path,
) -> None:
    """Run the environment checks in a child pytest that starts with both set.

    The values sit outside the child's temp tree, so the checks pass only if the
    child's session fixture clears ``CODEX_HOME`` and re-points
    ``APOTHEM_HOOK_STATE_DIR`` before module setup. The child gets no xdist
    worker variables, so it runs as a plain session of its own.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PYTEST_XDIST_", "PYTEST_CURRENT_TEST"))
    }
    env["CODEX_HOME"] = str(tmp_path / "developer-codex")
    env["APOTHEM_HOOK_STATE_DIR"] = str(tmp_path / "developer-hook-state")
    module = Path(__file__).resolve()
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *(f"{module}::{name}" for name in _ENVIRONMENT_CHECKS),
            "-n",
            "0",
            "-p",
            "no:cacheprovider",
            "-q",
            "--basetemp",
            str(tmp_path / "child-basetemp"),
        ],
        cwd=_CHECKOUT,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    report = f"{done.stdout}\n{done.stderr}"
    assert done.returncode == 0, report
    assert f"{len(_ENVIRONMENT_CHECKS)} passed" in done.stdout, report


def test_no_other_module_level_path_names_the_startup_home(
    seen_during_module_setup: _SeenDuringModuleSetup,
) -> None:
    still_real = {
        name: path
        for name, path in seen_during_module_setup.module_level_paths.items()
        if name not in _READ_ONLY
    }
    assert not still_real, (
        "these module-level paths still name the home the process started with "
        "while module-scoped fixtures run, so an install through them writes "
        "under the developer's real home: re-point each in "
        "tests/conftest.py::_isolate_session_home, or list it in _READ_ONLY with "
        f"the reason when nothing writes through it: {still_real}"
    )


def test_the_scan_finds_every_shape_a_module_level_root_takes(tmp_path: Path) -> None:
    """The scan is not vacuous: it reports each shape and skips what it should."""
    home = tmp_path / "home"
    checkout = home / "work" / "repo"
    module = types.ModuleType("apothem.scan_probe")

    def with_default(root: Path = home / ".apothem" / "default") -> Path:
        return root

    def imported_from_elsewhere(root: Path = home / ".apothem" / "elsewhere") -> Path:
        return root

    with_default.__module__ = module.__name__
    settings = type(
        "Settings",
        (),
        {"root": home / ".apothem" / "attribute", "__module__": module.__name__},
    )
    vars(module).update(
        PLAIN=home / ".apothem" / "plain",
        TEXT=str(home / ".apothem" / "text"),
        IN_TUPLE=("label", home / ".apothem" / "tuple"),
        IN_DICT={"key": [home / ".apothem" / "dict"]},
        with_default=with_default,
        Settings=settings,
        imported_from_elsewhere=imported_from_elsewhere,
        OUTSIDE=tmp_path / "elsewhere",
        IN_CHECKOUT=checkout / "src",
        UNEXPANDED="~/.apothem/state",
    )

    found = _module_level_paths_under([module], homes={home}, exempt={checkout})

    assert sorted(found) == sorted(
        f"{module.__name__}.{name}"
        for name in (
            "PLAIN",
            "TEXT",
            "IN_TUPLE",
            "IN_DICT",
            "with_default",
            "Settings",
        )
    )
