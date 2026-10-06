# SPDX-License-Identifier: MIT

"""Tests for EN-4 prose reconciliation and bootstrap-stub hardening.

Three concerns:

1. ``validate_hooks.validate_hook_command_shape`` asserts the actual
   settings.json entry shape — every hook ``command`` is ``${PYTHON_BIN}`` or
   an absolute interpreter path, never a bare ``python`` / ``python3``.
2. ``bootstrap.sh`` emits the intended "no Python interpreter found" envelope
   on the expected no-interpreter path (not the ERR-trap's "unexpected error
   at line N").
3. ``bootstrap.ps1``'s trap writes its JSON envelope to STDOUT (matching
   bootstrap.sh and the stub's stated stdout contract), reserving STDERR for
   the human-readable diagnostic.

Shell-dependent behavioral tests skip when their interpreter is unavailable,
mirroring ``tests/hooks/test_find_pwsh_locator.py``.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
_LIB_DIR = _REPO_ROOT / "src" / "apothem" / "lib"
for _p in (_SCRIPTS_DEV, _LIB_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from reporter import Reporter  # noqa: E402
from validate_hooks import (  # noqa: E402
    validate_hook_command_shape,
    validate_no_hardcoded_paths,
)

_BOOTSTRAP_SH = _REPO_ROOT / "src" / "apothem" / "hooks" / "lib" / "bootstrap.sh"
_BOOTSTRAP_PS1 = _REPO_ROOT / "src" / "apothem" / "hooks" / "lib" / "bootstrap.ps1"
_HOOKS_SRC = _REPO_ROOT / "src" / "apothem"

# A usable bash (on Windows a git-bash, never the WSL launcher).
_BASH = find_test_bash()
_PWSH = shutil.which("pwsh") or shutil.which("powershell")


@pytest.fixture
def reporter() -> Reporter:
    """Return a Reporter writing to an in-memory stream."""
    return Reporter(stream=io.StringIO())


# --- validate_hook_command_shape ---------------------------------------------


def _hooks_block(command: str) -> dict[str, object]:
    """Return a minimal hooks block whose single command is *command*."""
    return {
        "PreToolUse": [
            {
                "matcher": "Write",
                "hooks": [{"type": "command", "command": command, "args": ["x.py"]}],
            }
        ]
    }


def test_placeholder_command_passes(reporter: Reporter) -> None:
    """A ``${PYTHON_BIN}`` placeholder command passes."""
    validate_hook_command_shape(_hooks_block("${PYTHON_BIN}"), "t", reporter)
    assert reporter.failed == 0
    assert reporter.passed == 1


def test_absolute_command_passes(reporter: Reporter) -> None:
    """An absolute interpreter path passes."""
    absolute = "C:/Python/python.exe" if sys.platform == "win32" else "/usr/bin/python3"
    validate_hook_command_shape(_hooks_block(absolute), "t", reporter)
    assert reporter.failed == 0
    assert reporter.passed == 1


def test_bare_python_command_fails(reporter: Reporter) -> None:
    """A bare ``python`` command fails (PATH may resolve a WindowsApps stub)."""
    validate_hook_command_shape(_hooks_block("python"), "t", reporter)
    assert reporter.failed == 1
    assert any("bare interpreter" in err for err in reporter.errors)


def test_bare_python3_command_fails(reporter: Reporter) -> None:
    """A bare ``python3`` command fails for the same reason."""
    validate_hook_command_shape(_hooks_block("python3"), "t", reporter)
    assert reporter.failed == 1


def test_shipped_template_command_shape_passes(reporter: Reporter) -> None:
    """The shipped claude_code template carries the ${PYTHON_BIN} shape."""
    import json

    template = (
        _REPO_ROOT
        / "src"
        / "apothem"
        / "harnesses"
        / "claude_code"
        / "templates"
        / "settings.json"
    )
    data = json.loads(template.read_text(encoding="utf-8"))
    validate_hook_command_shape(data["hooks"], "template", reporter)
    assert reporter.failed == 0


def test_shipped_native_install_command_shape_passes(reporter: Reporter) -> None:
    """The native-install example carries the ${PYTHON_BIN} shape."""
    import json

    example = (
        _REPO_ROOT
        / "examples"
        / "harnesses"
        / "claude-code"
        / "native-install"
        / "settings.json"
    )
    data = json.loads(example.read_text(encoding="utf-8"))
    validate_hook_command_shape(data["hooks"], "native-install", reporter)
    assert reporter.failed == 0


# --- bootstrap.sh no-interpreter diagnostic ----------------------------------


def _python_free_path(tmp_path: Path, coreutils_dir: Path) -> str:
    """Return a PATH with working coreutils but no real python.

    A WindowsApps-shaped near-empty ``python`` stub (rejected by the locator)
    is the only python-named candidate; *coreutils_dir* supplies working
    coreutils for the locator's probes. Both entries are rendered in POSIX
    form and joined with ``:`` so the git-bash / POSIX shell parses them
    regardless of host.
    """
    stub_dir = tmp_path / "WindowsApps"
    stub_dir.mkdir()
    stub = stub_dir / "python"
    stub.write_text("", encoding="utf-8")
    stub.chmod(0o755)
    # Assemble a coreutils dir holding ONLY the tools the locator and stub probe
    # with, deliberately excluding any python-named binary that co-resides in
    # *coreutils_dir* — e.g. ``/usr/bin/python3`` on Linux runners, where bash
    # and the system interpreter share ``/usr/bin``. Linking the real dir would
    # make the PATH python-bearing, so ``find_real_python`` would resolve a real
    # interpreter and the no-interpreter diagnostic path would never run.
    clean_dir = tmp_path / "coreutils"
    clean_dir.mkdir()
    for tool in (
        "wc",
        "tr",
        "cut",
        "cat",
        "head",
        "dirname",
        "basename",
        "env",
        "sed",
        "grep",
        "printf",
        "sh",
    ):
        for candidate in (coreutils_dir / tool, coreutils_dir / f"{tool}.exe"):
            if candidate.exists():
                link = clean_dir / candidate.name
                try:
                    link.symlink_to(candidate)
                except OSError:
                    shutil.copy2(candidate, link)
                break
    return f"{stub_dir.as_posix()}:{clean_dir.as_posix()}"


@pytest.mark.skipif(_BASH is None, reason=SKIP_REASON)
def test_bootstrap_sh_no_interpreter_diagnostic(tmp_path: Path) -> None:
    """The no-interpreter path emits "no Python interpreter found".

    Not the ERR-trap's "unexpected error at line N". Runs the stub with the
    project root pointed at ``src/apothem`` (so the locator is found) and a
    python-free PATH (so no real interpreter is resolved). The coreutils the
    locator probes with come from the resolved shell's own directory, so the
    harness is host-portable (it does not assume ``/usr/bin``).

    The shell is ``bash`` specifically: the regression this guards against is
    the ERR trap firing on the expected no-interpreter path, and the ERR trap
    is a bash feature (``dash`` ignores ``trap ... ERR`` entirely, so it cannot
    exercise the bug). The ``if !`` guard is what makes the path correct under
    both shells.
    """
    shell = _BASH
    assert shell is not None
    coreutils_dir = Path(shell).parent
    if not (coreutils_dir / "wc").exists() and not (coreutils_dir / "wc.exe").exists():
        pytest.skip("resolved shell dir lacks coreutils for the locator probe")
    env = {
        "PATH": _python_free_path(tmp_path, coreutils_dir),
        "CLAUDE_PROJECT_DIR": str(_HOOKS_SRC),
    }
    result = subprocess.run(
        [shell, str(_BOOTSTRAP_SH), "SessionStart"],
        capture_output=True,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert result.returncode == 0, f"stub must exit 0; stderr={result.stderr!r}"
    assert "no Python interpreter found" in result.stdout, (
        f"expected the intended diagnostic; got stdout={result.stdout!r}"
    )
    assert "unexpected error at line" not in result.stdout, (
        "the ERR trap fired on the expected no-interpreter path; "
        f"stdout={result.stdout!r}"
    )


# --- bootstrap.ps1 stdout-trap -----------------------------------------------


@pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host")
def test_bootstrap_ps1_trap_writes_envelope_to_stdout(tmp_path: Path) -> None:
    """An unexpected error routes the JSON envelope to STDOUT, not STDERR.

    A locator that throws at dot-source time triggers the bare ``trap`` (outside
    the explicit try/catch around ``Find-RealPython``). The trap must emit its
    JSON envelope on stdout (the hook-runtime contract); stderr carries only the
    human-readable diagnostic.

    The stub takes its root from its own location, never from the project, so
    the throwing locator sits beside a copy of the stub in its own tree.
    """
    assert _PWSH is not None
    root = tmp_path / "ps-root"
    lib = root / "hooks" / "lib"
    lib.mkdir(parents=True)
    (root / "hooks" / "dispatch.py").write_text("import sys\n", encoding="utf-8")
    stub = lib / "bootstrap.ps1"
    shutil.copyfile(_BOOTSTRAP_PS1, stub)
    # Locator throws at dot-source time -> the bare trap fires.
    (lib / "find-python.ps1").write_text(
        'throw "boom from locator load"\n', encoding="utf-8"
    )
    project = tmp_path / "project"
    project.mkdir()
    result = subprocess.run(
        [
            _PWSH,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(stub),
            "-Event",
            "SessionStart",
        ],
        capture_output=True,
        text=True,
        env={**_os_environ(), "CLAUDE_PROJECT_DIR": str(project)},
        check=False,
    )
    assert result.returncode == 0, f"stub must exit 0; stderr={result.stderr!r}"
    assert "systemMessage" in result.stdout, (
        f"the trap envelope must be on stdout; stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert "unexpected error" in result.stdout


def _os_environ() -> dict[str, str]:
    """Return a copy of the process environment for subprocess injection."""
    import os

    return dict(os.environ)


# --- validate_no_hardcoded_paths ---------------------------------------------


def _hook_with(tmp_path: Path, body: str) -> Path:
    """Write a one-line hook module under a fresh hooks dir and return it."""
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "handler.py").write_text(body, encoding="utf-8")
    return hooks


@pytest.mark.parametrize(
    "literal",
    [
        pytest.param('HOME = "/home/someone/.apothem"', id="posix-home"),
        pytest.param('HOME = "/Users/someone/.apothem"', id="macos-users"),
        pytest.param('HOME = "/root/.apothem"', id="posix-root"),
        pytest.param('HOME = "C:\\\\Users\\\\someone\\\\.apothem"', id="windows-back"),
        pytest.param('HOME = "C:/Users/someone/.apothem"', id="windows-forward"),
    ],
)
def test_absolute_user_path_is_reported(
    literal: str, reporter: Reporter, tmp_path: Path
) -> None:
    """Every platform's home root is caught, not just the Windows backslash form.

    The scan reports "No hardcoded absolute paths" when it finds nothing, so a
    root it cannot match is worse than no check: it is an affirmative clean
    bill. Only the backslash Windows form was matched before, which left the
    POSIX roots — and the forward-slash Windows form — passing silently.
    """
    validate_no_hardcoded_paths(_hook_with(tmp_path, literal), reporter)

    assert reporter.failed == 1, f"expected a FAIL for {literal!r}"
    assert "handler.py" in reporter.errors[0]


def test_relative_and_env_derived_paths_pass(
    reporter: Reporter, tmp_path: Path
) -> None:
    """The intended idiom — resolve the home at runtime — is not flagged."""
    body = 'from pathlib import Path\nHOME = Path.home() / ".apothem"\n'
    validate_no_hardcoded_paths(_hook_with(tmp_path, body), reporter)

    assert reporter.failed == 0, reporter.errors
    assert reporter.passed == 1


def test_shipped_hook_scripts_carry_no_absolute_home_path(
    reporter: Reporter,
) -> None:
    """The widened pattern still passes against the real hooks tree."""
    validate_no_hardcoded_paths(_HOOKS_SRC / "hooks", reporter)

    assert reporter.failed == 0, reporter.errors
