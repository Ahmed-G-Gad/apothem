# SPDX-License-Identifier: MIT

"""Tests for the find-pwsh paired locator.

The bash locator at ``src/apothem/hooks/lib/find-pwsh.sh`` is exercised here via
subprocess invocation. The PowerShell sibling at ``src/apothem/hooks/lib/find-pwsh.ps1``
mirrors the bash shape per M14 sibling-convergence; testing it from
pytest would require a working pwsh-7 to host the test, which is the
very binary the locator is meant to find — chicken-and-egg. The
sibling's correctness rests on structural parity with the bash locator,
verified by the parity test below.

Three behaviors are asserted:

1. WindowsApps stub rejection — when the only ``pwsh`` on PATH is a
   fake WindowsApps stub, the locator returns exit 1 (no candidate).
2. Real-pwsh resolution — when a working pwsh exists at a non-
   WindowsApps path, the locator prints its absolute path and exits 0.
3. Paired-template parity — find-pwsh.sh's documented contract mirrors
   find-python.sh's shape per CLAUDE.md §11.4.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCATOR_SH = REPO_ROOT / "src" / "apothem" / "hooks" / "lib" / "find-pwsh.sh"
PYTHON_LOCATOR_SH = REPO_ROOT / "src" / "apothem" / "hooks" / "lib" / "find-python.sh"

# Resolve a usable bash once at import time (on Windows a git-bash, never the
# WSL launcher) so subprocess can find it even when _run_locator passes a
# restricted PATH env to the child.
_BASH: str | None = find_test_bash()


def _run_locator(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Source the bash locator and call find_real_pwsh under the given env."""
    if _BASH is None:
        pytest.skip(SKIP_REASON)
    script = f". {LOCATOR_SH.as_posix()} && find_real_pwsh"
    return subprocess.run(
        [_BASH, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _list_candidates(path_value: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Source find-pwsh.sh and list ``pwsh`` candidates under *path_value*."""
    if _BASH is None:
        pytest.skip(SKIP_REASON)
    env = {"PATH": path_value}
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    script = f". {LOCATOR_SH.as_posix()} && _find_pwsh_path_candidates pwsh"
    return subprocess.run(
        [_BASH, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
        check=False,
    )


def _make_executable(directory: Path, name: str = "pwsh") -> Path:
    """Create a small executable named *name* in *directory*."""
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / name
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary


def test_empty_segment_skipped_but_explicit_dot_honored(tmp_path: Path) -> None:
    """An empty PATH segment is skipped; an explicit '.' entry is still honored.

    find-pwsh.sh's Phase-1 probe replaced ``type -ap`` (which maps an empty
    PATH segment to cwd) with the empty-segment-skipping ``_find_pwsh_path_candidates``
    walk ported from find-python.sh. A cwd-planted ``pwsh`` reached only through
    a doubled / leading / trailing ``:`` separator would otherwise be
    version-probed (executed) and returned — the cwd-execution footgun this
    guard closes. The two halves form a self-validating contrast: the same cwd
    interpreter is discoverable through a non-empty ``.`` entry but NOT through
    an empty segment.
    """
    _make_executable(tmp_path, "pwsh")

    # Control: an explicit "." entry resolves the cwd interpreter, establishing
    # that the host shell reports the cwd file as executable under ``[ -x ]``.
    baseline = _list_candidates(".", cwd=tmp_path)
    if "pwsh" not in baseline.stdout:
        pytest.skip(
            "host shell does not report the cwd file as executable under [ -x ]; "
            "the empty-segment contrast is untestable here"
        )
    assert baseline.returncode == 0

    # The fix: a doubled (empty) PATH segment is SKIPPED, not resolved to cwd.
    # The two probe directories do not exist, so the only would-be match is cwd
    # via the empty middle segment.
    hardened = _list_candidates("/nonexistent_a::/nonexistent_b", cwd=tmp_path)
    assert hardened.returncode == 0
    assert hardened.stdout.strip() == "", (
        "an empty PATH segment was resolved to cwd; the cwd interpreter must be "
        f"skipped (got: {hardened.stdout!r})"
    )


@pytest.fixture
def stub_only_path(tmp_path: Path) -> dict[str, str]:
    """Build an env where the only ``pwsh`` on PATH is a tiny stub."""
    stub_dir = tmp_path / "WindowsApps"
    stub_dir.mkdir()
    stub = stub_dir / "pwsh"
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    env = {"PATH": str(stub_dir)}
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return env


def test_stub_only_path_returns_no_candidate(stub_only_path: dict[str, str]) -> None:
    result = _run_locator(stub_only_path)
    assert result.returncode == 1, (
        f"Expected exit 1 when only WindowsApps stub is on PATH, got "
        f"{result.returncode} with stdout={result.stdout!r}"
    )
    assert result.stdout.strip() == ""


def test_locator_skips_stub_finds_real_pwsh(tmp_path: Path) -> None:
    """When PATH contains both a stub and a real pwsh, the stub is skipped."""
    if sys.platform != "linux":
        pytest.skip(
            "Success-path needs a real, locator-probeable pwsh>=7 (a >1024-byte "
            "binary resolvable under a restricted stub+PATH harness). This holds "
            "on the Linux runner, where it runs. The Windows runner's git-bash "
            "PATH separator (drive-letter colon vs ':') and the macOS runner's "
            "wrapper/symlink pwsh (which trips the stub-size guard under the "
            "restricted harness) do not satisfy it. The locator's stub-rejection "
            "safety contract still runs on every platform "
            "(test_stub_only_path_returns_no_candidate); its real-pwsh "
            "resolution runs against the full PATH in production."
        )
    real_pwsh = shutil.which("pwsh")
    if not real_pwsh:
        pytest.skip(
            "No real pwsh installed on this host (locator's success-path is environment-dependent)"
        )
    # On Windows hosts where pwsh-7 is not actually installed, shutil.which
    # may resolve to the WindowsApps stub itself. Skip then.
    if "WindowsApps" in real_pwsh:
        pytest.skip(
            "pwsh on PATH resolves to the WindowsApps stub; no real pwsh-7 to test against"
        )
    # The locator's stub-size guard runs `wc -c` and rejects the candidate when
    # `wc` is missing, so the restricted PATH below must also reach `wc`.
    wc = shutil.which("wc")
    if not wc:
        pytest.skip("No wc on this host; the locator's stub-size guard needs it")

    stub_dir = tmp_path / "WindowsApps"
    stub_dir.mkdir()
    stub = stub_dir / "pwsh"
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    real_dir = Path(real_pwsh).parent
    wc_dir = Path(wc).parent

    # Inherit the full environment but override PATH to the stub dir, then the
    # real pwsh dir, then the `wc` dir. The stub stays first, so the test still
    # proves it is skipped. The `wc` dir is listed on its own because pwsh from
    # the release tarball (/usr/local/bin) or a snap (/snap/bin) does not sit
    # beside coreutils. The locator's version probe actually launches pwsh, which
    # needs HOME / TMPDIR / etc. to initialize; a PATH-only env makes pwsh fail
    # to start on macOS, so the candidate would be wrongly rejected.
    env = {
        **os.environ,
        "PATH": os.pathsep.join([str(stub_dir), str(real_dir), str(wc_dir)]),
    }
    result = _run_locator(env)
    assert result.returncode == 0, (
        f"locator failed to resolve a real pwsh; stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    resolved = result.stdout.strip()
    assert "WindowsApps" not in resolved
    assert resolved.endswith("pwsh") or resolved.endswith("pwsh.exe")


def test_paired_template_parity_with_find_python() -> None:
    """find-pwsh.sh exports find_real_pwsh; find-python.sh exports find_real_python."""
    pwsh_text = LOCATOR_SH.read_text(encoding="utf-8")
    python_text = PYTHON_LOCATOR_SH.read_text(encoding="utf-8")

    assert "find_real_pwsh()" in pwsh_text
    assert "find_real_python()" in python_text

    # Both locators share the WindowsApps-rejection idiom.
    assert "WindowsApps" in pwsh_text
    assert "WindowsApps" in python_text

    # Both honor the size-check pattern (reject zero-byte stubs).
    assert "size" in pwsh_text
    assert "1024" in pwsh_text
    assert "size" in python_text
    assert "1024" in python_text

    # Both walk PATH manually and skip empty segments rather than resolving
    # them to cwd (the shared cwd-execution guard). Neither INVOKES `type -ap`
    # as a probe — it maps an empty segment to the current directory, the
    # footgun both locators close by iterating $PATH under IFS=: with an
    # empty-segment continue. (Both mention `type -ap` only in prose, explaining
    # what the manual walk stands in for, so the assertion targets the command
    # form `type -ap "<name>"`, not the bare token.)
    assert 'type -ap "' not in pwsh_text
    assert 'type -ap "' not in python_text
    assert "IFS=:" in pwsh_text
    assert "IFS=:" in python_text
    assert '[[ -z "$dir" ]]' in pwsh_text
    assert '[ -z "$_fpc_dir" ]' in python_text


def test_help_path_returns_no_candidate_when_pwsh_absent() -> None:
    """When PATH is empty / pwsh-absent, the locator returns 1 cleanly."""
    env = {"PATH": "/nonexistent-path-fragment-for-test"}
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    result = _run_locator(env)
    assert result.returncode == 1
    assert result.stdout.strip() == ""
