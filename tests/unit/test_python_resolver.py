# SPDX-License-Identifier: MIT

"""Unit tests for the install-time CPython interpreter resolver.

``python_resolver.resolve_python_bin`` supplies the absolute interpreter path the
adapter substitutes for ``${PYTHON_BIN}`` in hook wiring. It must never return a
bare name or a Microsoft Store WindowsApps launcher stub. The module prefers
``sys.executable``, then walks ``PATH`` (rejecting stubs plus, on Windows only,
sub-1024-byte shims, version-probing each survivor against the ``>= 3.10``
floor), and raises when no real interpreter is found.

Direct, fully-isolated coverage of every branch the indirect happy-path tests
miss: WindowsApps / small-file / missing-file stub detection, the six
``_probe_version`` failure modes, the floor predicate, the ``PATH`` walk, and the
three ``resolve_python_bin`` resolution paths. ``subprocess`` and the filesystem
are mocked, so the suite never spawns a real interpreter and is host-agnostic.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from apothem.lib import python_resolver as pr


class _FakeCompleted:
    """Stand-in for ``subprocess.CompletedProcess`` (returncode + stdout only)."""

    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


class TestIsWindowsappsStub:
    """Recognising the Windows Store interpreter stub.

    Covers the path segment marking a stub regardless of size, the sub-floor
    byte size counting as a stub only on Windows, and a real large interpreter
    not being one — the stub is an execution alias that would fail on launch.
    """

    def test_windowsapps_path_segment_is_stub_regardless_of_size(
        self, tmp_path: Path
    ) -> None:
        binary = tmp_path / "Microsoft" / "WindowsApps" / "python.exe"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"x" * 4096)  # large, yet a stub by its path
        assert pr._is_windowsapps_stub(binary) is True

    def test_sub_floor_byte_size_is_stub_on_windows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The size floor exists for near-empty WindowsApps reparse stubs.
        monkeypatch.setattr(pr, "_is_windows", lambda: True)
        binary = tmp_path / "python"
        binary.write_bytes(b"x" * 10)  # under _MIN_INTERPRETER_BYTES
        assert pr._is_windowsapps_stub(binary) is True

    def test_sub_floor_byte_size_is_not_stub_on_posix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Tiny POSIX shims (pyenv/asdf shell scripts) are real interpreters;
        # the Windows-only size heuristic must not reject them.
        monkeypatch.setattr(pr, "_is_windows", lambda: False)
        binary = tmp_path / "python"
        binary.write_bytes(b"x" * 10)  # under _MIN_INTERPRETER_BYTES
        assert pr._is_windowsapps_stub(binary) is False

    def test_real_large_interpreter_is_not_stub(self, tmp_path: Path) -> None:
        binary = tmp_path / "python"
        binary.write_bytes(b"x" * (pr._MIN_INTERPRETER_BYTES + 1))
        assert pr._is_windowsapps_stub(binary) is False

    @pytest.mark.parametrize("is_windows", [True, False])
    def test_missing_file_is_stub_on_every_platform(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, is_windows: bool
    ) -> None:
        # stat() raises OSError on an absent path -> conservatively a stub.
        monkeypatch.setattr(pr, "_is_windows", lambda: is_windows)
        assert pr._is_windowsapps_stub(tmp_path / "absent") is True


_STORE_FAMILY = "PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0"


def _store_alias(root: Path, name: str = "python.exe") -> Path:
    """Return the path the Store build of CPython reports as ``sys.executable``."""
    return (
        root / "AppData" / "Local" / "Microsoft" / "WindowsApps" / _STORE_FAMILY / name
    )


def _forbid_path_walk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if the resolver falls through to the ``PATH`` walk."""

    def _no_path_walk() -> Path | None:
        raise AssertionError("the PATH walk must not run for the Store CPython")

    monkeypatch.setattr(pr, "_resolve_from_path", _no_path_walk)


class TestIsStorePythonAlias:
    """Recognising the Microsoft Store build of CPython by its own alias path.

    The Store build reports ``sys.executable`` as
    ``%LOCALAPPDATA%\\Microsoft\\WindowsApps\\<package family>\\python.exe``. Only
    that shape is the interpreter itself. Every other ``WindowsApps`` path is
    the Store launcher stub, another package, or the install directory.
    """

    # CPython reports python.exe or pythonw.exe. The matcher also takes the
    # versioned alias names the package ships, so it does not depend on which
    # of them a given build reports.
    @pytest.mark.parametrize("name", ["python.exe", "pythonw.exe", "python3.12.exe"])
    def test_store_package_alias_is_recognised(self, tmp_path: Path, name: str) -> None:
        assert pr._is_store_python_alias(_store_alias(tmp_path, name)) is True

    def test_match_ignores_case(self, tmp_path: Path) -> None:
        # Windows paths are case-insensitive; a differently cased spelling of
        # the same directories is still the Store alias.
        path = (
            tmp_path
            / "microsoft"
            / "windowsapps"
            / _STORE_FAMILY.lower()
            / "PYTHON.EXE"
        )
        assert pr._is_store_python_alias(path) is True

    @pytest.mark.parametrize(
        "parts",
        [
            # The not-installed redirector and the generic aliases sit directly
            # in WindowsApps, with no package directory between.
            ("Microsoft", "WindowsApps", "python.exe"),
            ("Microsoft", "WindowsApps", "python3.exe"),
            # The redirector's own package is not a Python.
            (
                "Microsoft",
                "WindowsApps",
                "Microsoft.DesktopAppInstaller_8wekyb3d8bbwe",
                "python.exe",
            ),
            # The install-manager app is not an interpreter either.
            (
                "Microsoft",
                "WindowsApps",
                "PythonSoftwareFoundation.PythonManager_qbz5n2kfra8p0",
                "python.exe",
            ),
            # The package install directory is not the alias directory: it is
            # not under Microsoft\WindowsApps.
            ("Program Files", "WindowsApps", _STORE_FAMILY, "python.exe"),
            # The family name outside WindowsApps proves nothing.
            ("Microsoft", "Elsewhere", _STORE_FAMILY, "python.exe"),
            ("Other", "WindowsApps", _STORE_FAMILY, "python.exe"),
            # Other files in the package directory are not the interpreter. The
            # name must start with "python" and end with ".exe", so each of
            # these fails one of the two.
            ("Microsoft", "WindowsApps", _STORE_FAMILY, "pip.exe"),
            ("Microsoft", "WindowsApps", _STORE_FAMILY, "pydoc.exe"),
            ("Microsoft", "WindowsApps", _STORE_FAMILY, "pyw.exe"),
            ("Microsoft", "WindowsApps", _STORE_FAMILY, "python.dll"),
        ],
    )
    def test_other_windowsapps_paths_are_not_the_store_alias(
        self, tmp_path: Path, parts: tuple[str, ...]
    ) -> None:
        assert pr._is_store_python_alias(tmp_path.joinpath(*parts)) is False

    @pytest.mark.parametrize(
        "path",
        [
            Path("python.exe"),
            Path("WindowsApps/python.exe"),
            # One segment short of the four the shape needs: the boundary.
            Path("Microsoft/WindowsApps/python.exe"),
        ],
    )
    def test_path_with_fewer_than_four_parts_is_not_the_store_alias(
        self, path: Path
    ) -> None:
        assert pr._is_store_python_alias(path) is False


class TestProbeVersion:
    """Probing a candidate interpreter for its version.

    Covers the parse of a major/minor pair against every none-returning case: a
    non-zero exit, output too short to parse, and unparseable output.
    """

    def test_parses_major_minor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            pr.subprocess, "run", lambda *a, **k: _FakeCompleted(0, "3 12")
        )
        assert pr._probe_version(Path("python")) == (3, 12)

    def test_nonzero_exit_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            pr.subprocess, "run", lambda *a, **k: _FakeCompleted(1, "3 12")
        )
        assert pr._probe_version(Path("python")) is None

    def test_short_output_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            pr.subprocess, "run", lambda *a, **k: _FakeCompleted(0, "3")
        )
        assert pr._probe_version(Path("python")) is None

    def test_unparseable_output_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            pr.subprocess, "run", lambda *a, **k: _FakeCompleted(0, "x y")
        )
        assert pr._probe_version(Path("python")) is None

    def test_oserror_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a: object, **_k: object) -> _FakeCompleted:
            raise OSError("not executable")

        monkeypatch.setattr(pr.subprocess, "run", boom)
        assert pr._probe_version(Path("python")) is None

    def test_subprocess_error_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*_a: object, **_k: object) -> _FakeCompleted:
            raise subprocess.TimeoutExpired("python", 10)

        monkeypatch.setattr(pr.subprocess, "run", boom)
        assert pr._probe_version(Path("python")) is None


class TestSatisfiesFloor:
    """The minimum-version predicate."""

    @pytest.mark.parametrize(
        ("major", "minor", "expected"),
        [
            (3, 10, True),  # exactly the floor
            (3, 12, True),  # above the floor on minor
            (4, 0, True),  # above the floor on major
            (3, 9, False),  # below the floor on minor
            (2, 7, False),  # below the floor on major
        ],
    )
    def test_floor_predicate(self, major: int, minor: int, expected: bool) -> None:
        assert pr._satisfies_floor(major, minor) is expected


class TestPathCandidates:
    """Enumerating interpreter candidates from the search path.

    Covers matches returned in path order, and the security-relevant distinction
    between an empty path entry — skipped rather than resolved to the working
    directory — and an explicit dot entry, which does search it.
    """

    @staticmethod
    def _make_executable(directory: Path, name: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        suffix = ".exe" if os.name == "nt" else ""
        binary = directory / f"{name}{suffix}"
        binary.write_bytes(b"#!/usr/bin/env python\n" + b"x" * 2048)
        binary.chmod(0o755)
        return binary

    def test_returns_all_matches_in_path_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first = self._make_executable(tmp_path / "d1", "python3")
        second = self._make_executable(tmp_path / "d2", "python3")
        monkeypatch.setenv(
            "PATH", str(tmp_path / "d1") + os.pathsep + str(tmp_path / "d2")
        )
        monkeypatch.setenv("PATHEXT", ".EXE")

        found = pr._path_candidates("python3")

        assert first in found
        assert second in found
        assert found.index(first) < found.index(second)  # PATH precedence

    def test_empty_path_entry_is_skipped_not_resolved_to_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defense in depth: an empty PATH segment (a doubled separator, or a
        # leading/trailing one) is SKIPPED, never resolved to the current
        # directory. A cwd-resident interpreter must not be discoverable here —
        # it would be version-probed (executed) and wired into the hook command.
        self._make_executable(tmp_path, "python3")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PATH", "")  # one empty segment -> skipped, not cwd
        monkeypatch.setenv("PATHEXT", ".EXE")

        found = pr._path_candidates("python3")

        assert found == []  # cwd is not searched via an empty PATH segment

    def test_explicit_dot_entry_still_searches_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Only EMPTY segments are skipped. A user who genuinely wants the
        # current directory searched adds an explicit "." entry, which is
        # non-empty and still honored — the documented "lists all matches"
        # behavior is unchanged; only cwd-from-empty-segment changes.
        self._make_executable(tmp_path, "python3")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PATH", ".")  # explicit cwd entry -> honored
        monkeypatch.setenv("PATHEXT", ".EXE")

        found = pr._path_candidates("python3")

        assert any(c.name.startswith("python3") for c in found)

    def test_no_match_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "empty").mkdir()
        monkeypatch.setenv("PATH", str(tmp_path / "empty"))
        assert pr._path_candidates("python3") == []


class TestResolveFromPath:
    """Selecting an interpreter from the path candidates.

    Covers the first floor-satisfying candidate winning, the skip chain past a
    stub and an unprobeable binary to reach a real one, the skip of a
    below-floor interpreter, and none when no candidate qualifies.
    """

    def test_returns_first_floor_satisfying_resolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        good = tmp_path / "python3"
        good.write_bytes(b"x" * 2048)
        monkeypatch.setattr(
            pr, "_path_candidates", lambda name: [good] if name == "python" else []
        )
        monkeypatch.setattr(pr, "_is_windowsapps_stub", lambda _p: False)
        monkeypatch.setattr(pr, "_probe_version", lambda _p: (3, 12))

        assert pr._resolve_from_path() == good.resolve()

    def test_skips_stub_then_unprobeable_then_takes_real(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = tmp_path / "stub"
        noprobe = tmp_path / "noprobe"
        real = tmp_path / "real"
        for binary in (stub, noprobe, real):
            binary.write_bytes(b"x" * 2048)
        candidates = {"python": [stub], "python3": [noprobe], "python3.14": [real]}
        monkeypatch.setattr(
            pr, "_path_candidates", lambda name: candidates.get(name, [])
        )
        monkeypatch.setattr(pr, "_is_windowsapps_stub", lambda p: p == stub)
        monkeypatch.setattr(
            pr, "_probe_version", lambda p: (3, 12) if p == real else None
        )

        assert pr._resolve_from_path() == real.resolve()

    def test_skips_below_floor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        old = tmp_path / "old-python"
        old.write_bytes(b"x" * 2048)
        monkeypatch.setattr(
            pr, "_path_candidates", lambda name: [old] if name == "python" else []
        )
        monkeypatch.setattr(pr, "_is_windowsapps_stub", lambda _p: False)
        monkeypatch.setattr(pr, "_probe_version", lambda _p: (3, 9))  # under the floor

        assert pr._resolve_from_path() is None

    def test_returns_none_when_no_candidate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pr, "_path_candidates", lambda _name: [])
        assert pr._resolve_from_path() is None


class TestResolvePythonBin:
    """Resolving the interpreter to run with.

    Covers preferring a real running interpreter, falling back to the search
    path when that interpreter is a stub or empty, and raising when nothing
    resolves — the caller is told rather than handed an unusable path.
    """

    def test_prefers_real_sys_executable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        exe = tmp_path / "python"
        exe.write_bytes(b"x" * 4096)
        monkeypatch.setattr(pr.sys, "executable", str(exe))

        assert pr.resolve_python_bin() == exe.resolve()

    def test_falls_back_to_path_when_sys_executable_is_stub(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = tmp_path / "Microsoft" / "WindowsApps" / "python.exe"
        stub.parent.mkdir(parents=True)
        stub.write_bytes(b"x" * 4096)
        fallback = tmp_path / "real-python"
        monkeypatch.setattr(pr.sys, "executable", str(stub))
        monkeypatch.setattr(pr, "_resolve_from_path", lambda: fallback)

        assert pr.resolve_python_bin() == fallback

    def test_uses_store_python_alias_as_reported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The Store build of CPython reports an app-execution alias under
        # WindowsApps as sys.executable. It is the running interpreter, so
        # neither the WindowsApps segment nor the Windows size floor may reject
        # it, and the PATH walk must not be consulted. An empty file is the
        # smallest case the size floor would reject.
        alias = _store_alias(tmp_path)
        alias.parent.mkdir(parents=True)
        alias.write_bytes(b"")
        monkeypatch.setattr(pr, "_is_windows", lambda: True)
        monkeypatch.setattr(pr.sys, "executable", str(alias))
        _forbid_path_walk(monkeypatch)

        assert pr.resolve_python_bin() == alias

    def test_does_not_resolve_the_store_alias(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The alias is the path CPython reports and other processes launch.
        # It is returned as reported rather than depending on how resolution
        # treats a reparse point, which was not checked on Windows. This spy
        # pins that without needing symbolic links.
        alias = _store_alias(tmp_path)
        alias.parent.mkdir(parents=True)
        alias.write_bytes(b"")
        monkeypatch.setattr(pr.sys, "executable", str(alias))
        _forbid_path_walk(monkeypatch)

        def _no_resolve(self: Path, *args: object, **kwargs: object) -> Path:
            raise AssertionError("the Store alias must be returned without resolve()")

        monkeypatch.setattr(Path, "resolve", _no_resolve)

        assert pr.resolve_python_bin() == alias

    def test_keeps_store_alias_path_instead_of_resolving_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The same rule end to end: a symbolic link at the alias path comes back
        # as the alias, not as its target.
        target = tmp_path / "package" / "python3.12.exe"
        target.parent.mkdir()
        target.write_bytes(b"x" * 4096)
        alias = _store_alias(tmp_path)
        alias.parent.mkdir(parents=True)
        try:
            alias.symlink_to(target)
        except (OSError, NotImplementedError):
            pytest.skip("symbolic links are unavailable on this host")
        monkeypatch.setattr(pr.sys, "executable", str(alias))
        _forbid_path_walk(monkeypatch)

        resolved = pr.resolve_python_bin()

        assert resolved == alias
        assert resolved != target.resolve()

    def test_returns_an_absolute_path_for_a_relative_store_alias(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The result is substituted into hook commands, so it must be absolute
        # even when sys.executable is not.
        alias = _store_alias(tmp_path)
        alias.parent.mkdir(parents=True)
        alias.write_bytes(b"")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(pr.sys, "executable", str(alias.relative_to(tmp_path)))
        _forbid_path_walk(monkeypatch)

        resolved = pr.resolve_python_bin()

        assert resolved.is_absolute()
        assert resolved == alias

    def test_falls_back_when_store_alias_is_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The alias shape alone is not trusted: the file must exist.
        fallback = tmp_path / "real-python"
        monkeypatch.setattr(pr.sys, "executable", str(_store_alias(tmp_path)))
        monkeypatch.setattr(pr, "_resolve_from_path", lambda: fallback)

        assert pr.resolve_python_bin() == fallback

    def test_falls_back_when_sys_executable_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fallback = Path("/usr/bin/python3")
        monkeypatch.setattr(pr.sys, "executable", "")
        monkeypatch.setattr(pr, "_resolve_from_path", lambda: fallback)

        assert pr.resolve_python_bin() == fallback

    def test_raises_when_nothing_resolves(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pr.sys, "executable", "")
        monkeypatch.setattr(pr, "_resolve_from_path", lambda: None)

        with pytest.raises(RuntimeError, match="no real CPython"):
            pr.resolve_python_bin()
