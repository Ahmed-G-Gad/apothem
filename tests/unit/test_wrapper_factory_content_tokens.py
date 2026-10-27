# SPDX-License-Identifier: MIT

"""Tests for the install-time tokens a project-scope install can render.

``make_project_scope_install`` takes an optional ``content_tokens`` resolver. It
is how a project-scope adapter whose template carries ``${PYTHON_BIN}`` gets the
interpreter written in, the way the user-scope Claude Code and Codex installs do.
The resolver runs before any write, covers the preview as well as the install,
and, left out, changes nothing.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver, wrapper_factories
from apothem.harnesses._shared.install_driver import MaterializationRun
from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_update_project,
    python_bin_tokens,
)

_TEMPLATE = '"${PYTHON_BIN}" "${PROJECT_ROOT}/hooks/dispatch.py" SessionStart'
_ERROR = "probe adapter requires --project <path>"


class _Driver:
    """Stand-ins for the driver entry points, recording what each call rendered."""

    def __init__(self, project: Path) -> None:
        self.project = project
        self.calls: list[str] = []
        self.rendered: list[str] = []

    def _render(self) -> str:
        return install_driver.render_content_tokens(
            _TEMPLATE, harness_root=None, project_root=self.project
        )

    def capture_missing_dirs(self, *_args: object, **_kwargs: object) -> tuple[()]:
        self.calls.append("capture_missing_dirs")
        return ()

    def run_install(
        self, harness_name: str, *, dry_run: bool = False, **_kwargs: object
    ) -> MaterializationRun:
        self.calls.append("run_install(dry)" if dry_run else "run_install")
        self.rendered.append(self._render())
        return MaterializationRun(harness_name, dry_run, ())

    def finalize_install(self, run: MaterializationRun, **_kwargs: object) -> object:
        self.calls.append("finalize_install")
        return run


@pytest.fixture
def driver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Driver:
    fake = _Driver(tmp_path)
    for name in ("capture_missing_dirs", "run_install", "finalize_install"):
        monkeypatch.setattr(install_driver, name, getattr(fake, name))
    monkeypatch.setattr(
        wrapper_factories, "shared_scope", lambda _name: contextlib.nullcontext()
    )
    return fake


def _rendered_pattern(python: str, project: Path) -> str:
    return f'"{python}" "{project.resolve().as_posix()}/hooks/dispatch.py" SessionStart'


@pytest.mark.parametrize("dry_run", [False, True])
def test_the_resolved_tokens_are_rendered_into_the_install_and_the_preview(
    driver: _Driver, dry_run: bool
) -> None:
    install = make_project_scope_install(
        "probe",
        error_message=_ERROR,
        content_tokens=lambda: {"PYTHON_BIN": "/opt/py/bin/python"},
    )

    install(Path("unused"), {}, project=driver.project, dry_run=dry_run)

    assert driver.rendered == [_rendered_pattern("/opt/py/bin/python", driver.project)]


def test_the_update_built_on_the_install_renders_the_same_tokens(
    driver: _Driver,
) -> None:
    install = make_project_scope_install(
        "probe",
        error_message=_ERROR,
        content_tokens=lambda: {"PYTHON_BIN": "/opt/py/bin/python"},
    )

    make_update_project(install)(Path("unused"), {}, project=driver.project)

    assert driver.rendered == [_rendered_pattern("/opt/py/bin/python", driver.project)]


@pytest.mark.parametrize("dry_run", [False, True])
def test_without_a_resolver_the_placeholder_is_left_as_the_template_wrote_it(
    driver: _Driver, dry_run: bool
) -> None:
    install = make_project_scope_install("probe", error_message=_ERROR)

    install(Path("unused"), {}, project=driver.project, dry_run=dry_run)

    assert driver.rendered == [
        f'"${{PYTHON_BIN}}" "{driver.project.resolve().as_posix()}'
        '/hooks/dispatch.py" SessionStart'
    ]


@pytest.mark.parametrize("dry_run", [False, True])
def test_a_resolver_that_fails_stops_the_install_before_anything_is_touched(
    driver: _Driver, dry_run: bool
) -> None:
    def no_interpreter() -> dict[str, str]:
        raise RuntimeError("no real CPython 3.10 or newer found")

    install = make_project_scope_install(
        "probe", error_message=_ERROR, content_tokens=no_interpreter
    )

    with pytest.raises(RuntimeError, match="no real CPython"):
        install(Path("unused"), {}, project=driver.project, dry_run=dry_run)

    assert driver.calls == []


def test_the_tokens_do_not_outlive_the_install(driver: _Driver) -> None:
    install = make_project_scope_install(
        "probe",
        error_message=_ERROR,
        content_tokens=lambda: {"PYTHON_BIN": "/opt/py/bin/python"},
    )

    install(Path("unused"), {}, project=driver.project)
    after = driver._render()

    assert after.startswith('"${PYTHON_BIN}"')


def test_a_missing_project_is_still_rejected_before_the_resolver_runs() -> None:
    resolved: list[str] = []

    def resolver() -> dict[str, str]:
        resolved.append("called")
        return {}

    install = make_project_scope_install(
        "probe", error_message=_ERROR, content_tokens=resolver
    )

    with pytest.raises(ValueError, match="requires --project"):
        install(Path("unused"), {}, project=None)

    assert resolved == []


def test_python_bin_tokens_name_the_interpreter_the_resolver_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        wrapper_factories, "resolve_python_bin", lambda: Path("C:/Py/python.exe")
    )

    assert python_bin_tokens() == {"PYTHON_BIN": "C:/Py/python.exe"}
