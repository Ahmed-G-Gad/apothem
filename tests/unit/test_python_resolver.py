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
