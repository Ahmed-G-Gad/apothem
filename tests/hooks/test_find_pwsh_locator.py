# SPDX-License-Identifier: MIT

"""Tests for the find-pwsh paired locator.

The bash locator at ``src/apothem/hooks/lib/find-pwsh.sh`` is exercised here via
subprocess invocation. The PowerShell sibling at ``src/apothem/hooks/lib/find-pwsh.ps1``
mirrors the bash shape per M14 sibling-convergence; testing it from
pytest would require a working pwsh-7 to host the test, which is the
very binary the locator is meant to find — chicken-and-egg. The
sibling's correctness rests on structural parity with the bash locator,
verified by the parity test below.

Four behaviors are asserted:

1. WindowsApps stub rejection — when the only ``pwsh`` on PATH is a
   fake WindowsApps stub, the locator returns exit 1 (no candidate).
2. Real-pwsh resolution — when a working pwsh exists at a non-
   WindowsApps path, the locator prints its absolute path and exits 0.
3. Fake-pwsh resolution — the same positive contract without a pwsh on the
   host: a script that prints a major version stands in for pwsh, and the
   locator walks past a Store-stub directory, a candidate under the size
   guard, one below the version floor, and one whose probe exits non-zero.
4. Paired-template parity — find-pwsh.sh's documented contract mirrors
   find-python.sh's shape per CLAUDE.md §11.4.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

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
    # Check the exit code before the skip decision: a locator that cannot be
    # sourced must fail here, not skip with the [ -x ] reason below.
    assert baseline.returncode == 0, (
        f"the locator did not run cleanly (stderr={baseline.stderr!r})"
    )
    if "pwsh" not in baseline.stdout:
        pytest.skip(
            "host shell does not report the cwd file as executable under [ -x ]; "
            "the empty-segment contrast is untestable here"
        )

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


def _assert_locator_defines_find_real_pwsh(env: dict[str, str]) -> None:
    """Fail unless find-pwsh.sh defines ``find_real_pwsh``.

    An empty result from ``_run_locator`` proves nothing on its own: a locator
    that never loaded also exits 1 with empty stdout. ``type -t`` prints
    ``function`` only when the sourced file defined the function.
    """
    if _BASH is None:
        pytest.skip(SKIP_REASON)
    probe = subprocess.run(
        [_BASH, "-c", f". {LOCATOR_SH.as_posix()} && type -t find_real_pwsh"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert probe.stdout.strip() == "function", (
        "find-pwsh.sh did not define find_real_pwsh, so an empty result proves "
        f"nothing (rc={probe.returncode}, stderr={probe.stderr!r})"
    )


def test_stub_only_path_returns_no_candidate(stub_only_path: dict[str, str]) -> None:
    _assert_locator_defines_find_real_pwsh(stub_only_path)
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


# The locator rejects any candidate under 1024 bytes as a Store stub, so a fake
# pwsh that is meant to reach the version probe is padded past that size.
_STUB_SIZE_FLOOR = 1024


def _write_fake_pwsh(
    directory: Path, *, major: int, exit_code: int = 0, padded: bool = True
) -> Path:
    """Write a ``pwsh`` stand-in that answers the locator's version probe.

    The locator runs ``pwsh -NoProfile -Command '$PSVersionTable...Major'`` and
    reads the major version from stdout, so the script prints *major* and exits
    with *exit_code*. *padded* sizes it past the locator's stub guard.
    """
    directory.mkdir(parents=True, exist_ok=True)
    fake = directory / "pwsh"
    lines = ["#!/bin/sh"]
    if padded:
        lines.append("# " + "padding " * (_STUB_SIZE_FLOOR // 8 + 1))
    lines += [f"printf '%s\\n' {major}", f"exit {exit_code}"]
    fake.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    fake.chmod(0o755)
    # Fail here, not as a confusing locator result, if the padding ever drifts.
    assert (fake.stat().st_size >= _STUB_SIZE_FLOOR) == padded
    return fake


class _Decoy(NamedTuple):
    """One unusable candidate, listed ahead of the usable fake on PATH."""

    directory: str
    major: int
    exit_code: int = 0
    padded: bool = True


# Every decoy prints a version the locator would accept, apart from
# "below-the-version-floor", so exactly one guard is responsible for rejecting it.
_DECOYS = [
    pytest.param(None, id="no-decoy"),
    pytest.param(_Decoy("WindowsApps", major=7), id="store-stub-directory"),
    pytest.param(
        _Decoy("under-size-guard", major=7, padded=False), id="under-the-size-guard"
    ),
    pytest.param(_Decoy("below-floor", major=6), id="below-the-version-floor"),
    pytest.param(
        _Decoy("exits-nonzero", major=7, exit_code=1), id="probe-exits-nonzero"
    ),
]


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "git-bash reads a multi-directory PATH through its own drive-letter "
        "conversion, which this test does not model; the Windows runner still "
        "covers stub rejection in test_stub_only_path_returns_no_candidate"
    ),
)
@pytest.mark.parametrize("decoy", _DECOYS)
def test_locator_resolves_fake_pwsh_past_decoys(
    tmp_path: Path, decoy: _Decoy | None
) -> None:
    """A fake pwsh resolves on any POSIX host, whatever else is on the machine.

    test_locator_skips_stub_finds_real_pwsh needs a real pwsh and runs on Linux
    only, so a locator that rejects every candidate passes the other tests on a
    host without one. This test supplies its own pwsh: PATH holds only the
    directories built here plus the one that holds ``wc``. Each decoy case puts
    one unusable candidate first and asserts the locator walks past it to the
    usable fake.
    """
    wc = shutil.which("wc")
    if not wc:
        pytest.skip("No wc on this host; the locator's stub-size guard needs it")

    real = _write_fake_pwsh(tmp_path / "real-pwsh-bin", major=7)
    path_dirs = [real.parent, Path(wc).parent]
    if decoy is not None:
        fake_decoy = _write_fake_pwsh(
            tmp_path / decoy.directory,
            major=decoy.major,
            exit_code=decoy.exit_code,
            padded=decoy.padded,
        )
        path_dirs.insert(0, fake_decoy.parent)

    result = _run_locator({"PATH": os.pathsep.join(str(d) for d in path_dirs)})
    assert result.returncode == 0, (
        f"locator found no pwsh; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert result.stdout.strip() == real.as_posix(), (
        f"locator chose {result.stdout.strip()!r}, expected the usable fake "
        f"{real.as_posix()!r}"
    )


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
    _assert_locator_defines_find_real_pwsh(env)
    result = _run_locator(env)
    assert result.returncode == 1
    assert result.stdout.strip() == ""
