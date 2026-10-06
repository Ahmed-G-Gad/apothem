# SPDX-License-Identifier: MIT

"""Verify the three console entry points are reachable via ``python -m``.

These tests exercise the registry-free invocation path: each entry point
runs as a subprocess with ``PYTHONPATH`` pointed at this worktree's
``src/`` directory, so no installed console script is required.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_SRC: Path = Path(__file__).resolve().parents[2] / "src"


def _env() -> dict[str, str]:
    """Return an environment with the worktree ``src/`` on ``PYTHONPATH``."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{_SRC}{os.pathsep}{existing}" if existing else str(_SRC)
    return env


def test_apothem_module_help_exits_zero() -> None:
    """``python -m apothem --help`` exits 0 and prints a CLI usage marker."""
    result = subprocess.run(
        [sys.executable, "-m", "apothem", "--help"],
        capture_output=True,
        text=True,
        env=_env(),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Usage" in result.stdout


def test_apothem_module_help_emits_utf8_through_pipe() -> None:
    """``--help`` Unicode round-trips as UTF-8 when stdout is a pipe.

    Regression guard for the legacy-codepage portability bug: Click emits
    ``--help`` from eager-option handling *before* the group callback runs, so
    the UTF-8 stdio reconfigure must fire at the ``python -m apothem`` entry
    (``apothem/__main__.py``), not only inside the callback. The group
    docstring's em-dash (U+2014) must reach a piped stdout as its UTF-8
    encoding ``b"\\xe2\\x80\\x94"`` rather than a lone legacy-codepage byte
    (e.g. ``0x97`` under cp1252/cp1256). On Windows the subprocess forces a
    non-UTF-8 pipe codepage to prove the reconfigure overrides it; elsewhere
    the interpreter's default pipe encoding is already UTF-8.
    """
    env = _env()
    if sys.platform == "win32":
        # Without the entry-point reconfigure, a legacy Windows codepage would
        # encode U+2014 as the single byte 0x97 on a piped stdout.
        env["PYTHONIOENCODING"] = "cp1256"
    result = subprocess.run(
        [sys.executable, "-m", "apothem", "--help"],
        capture_output=True,  # bytes — inspect the wire encoding directly
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    # The em-dash is present as its UTF-8 encoding, and the whole stream
    # decodes cleanly as UTF-8 (a lone 0x97 would raise UnicodeDecodeError).
    assert b"\xe2\x80\x94" in result.stdout, result.stdout
    result.stdout.decode("utf-8")


def test_conformity_gate_module_runs_non_crashing() -> None:
    """``python -m apothem.conformity.gate`` runs to a controlled exit.

    The gate is a stdin-driven orchestrator, not an argparse CLI, so it
    has no ``--help``. The registry-free contract is that the module is
    reachable via ``python -m`` and runs to completion: it reads content
    from stdin (``--stdin``), emits a structured JSON report, and exits
    with a controlled code (0 = clean, 2 = findings) — never an uncaught
    Python traceback. This test asserts the non-crashing property.
    """
    result = subprocess.run(
        [sys.executable, "-m", "apothem.conformity.gate", "--stdin"],
        input="# SPDX-License-Identifier: MIT\n\nx = 1\n",
        capture_output=True,
        text=True,
        env=_env(),
        check=False,
    )
    # Controlled exit, not a crash: 0 (clean) or 2 (findings blocked the
    # write). A 1 with a traceback on stderr would signal an uncaught
    # exception in the entry point.
    assert result.returncode in (0, 2), result.stderr
    assert "Traceback" not in result.stderr
    assert '"orchestrator": "conformity-gate"' in result.stdout


def test_hooks_dispatch_importable_with_main() -> None:
    """``apothem.hooks.dispatch`` imports and exposes a callable ``main``."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import apothem.hooks.dispatch as d; assert callable(d.main); print('ok')",
        ],
        capture_output=True,
        text=True,
        env=_env(),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


# -----------------------------------------------------------------------
# Host prerequisites and the vendored dependency path.
# -----------------------------------------------------------------------

#: Packages the engine imports from the host interpreter (not vendored), and
#: the third-party modules ``rich`` itself needs at import time.
_HOST_PACKAGES = ("click", "rich", "markdown_it", "mdurl", "pygments")


def _host_only_dir(tmp_path: Path) -> Path:
    """Return a directory that exposes only click, rich, and rich's own deps.

    Combined with ``python -S`` (no site-packages), this models a host whose
    interpreter has the two documented prerequisites and nothing else: no
    PyYAML, no jsonschema. The packages are symlinked from the test
    interpreter's own environment.
    """
    import importlib.util

    host = tmp_path / "host-site"
    host.mkdir()
    for name in _HOST_PACKAGES:
        spec = importlib.util.find_spec(name)
        assert spec is not None, name
        assert spec.submodule_search_locations, name
        source = Path(next(iter(spec.submodule_search_locations)))
        (host / name).symlink_to(source, target_is_directory=True)
    return host


def test_missing_prerequisites_report_a_structured_error() -> None:
    """A bare interpreter without click and rich gets a fix, not a traceback.

    ``python -S`` drops site-packages, so neither prerequisite is importable.
    The entry point must name both packages and the exact pip command for
    the running interpreter, exit 1, and print no Python traceback.
    """
    result = subprocess.run(
        [sys.executable, "-S", "-m", "apothem", "--version"],
        capture_output=True,
        text=True,
        env=_env(),
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert "click" in result.stderr
    assert "rich" in result.stderr
    assert f"{sys.executable} -m pip install" in result.stderr
    assert '"click==8.4.2"' in result.stderr
    assert result.stdout == ""


def test_missing_prerequisites_honor_json_mode() -> None:
    """``--json`` callers get one parseable error envelope on stdout."""
    import json

    result = subprocess.run(
        [sys.executable, "-S", "-m", "apothem", "doctor", "--json"],
        capture_output=True,
        text=True,
        env=_env(),
        check=False,
    )
    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "runtime.dependency_missing"
    assert payload["schema_version"] == 1
    assert f"{sys.executable} -m pip install" in payload["error"]["fix"]


def test_prerequisite_pins_match_the_project_dependencies() -> None:
    """The pip command the entry point prints installs the declared versions."""
    tomllib = pytest.importorskip("tomllib")

    from apothem import __main__ as entry

    pyproject = tomllib.loads(
        (_SRC.parent / "pyproject.toml").read_text(encoding="utf-8")
    )
    declared = set(pyproject["project"]["dependencies"])
    for _module, spec in entry.HOST_PREREQUISITES:
        assert spec in declared, spec


@pytest.mark.skipif(sys.platform == "win32", reason="symlinked host model is POSIX")
def test_pythonpath_src_resolves_the_vendored_dependencies(tmp_path: Path) -> None:
    """``PYTHONPATH=src python -m apothem`` needs only click and rich on the host.

    The documented checkout command must find PyYAML and jsonschema in
    ``src/apothem/_vendor`` without the caller adding that directory.
    """
    env = _env()
    env["PYTHONPATH"] = f"{_SRC}{os.pathsep}{_host_only_dir(tmp_path)}"
    result = subprocess.run(
        [sys.executable, "-S", "-m", "apothem", "--version"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Apothem, version" in result.stdout
