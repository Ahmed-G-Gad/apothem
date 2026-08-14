# SPDX-License-Identifier: MIT

"""Tests for src/apothem/lib/parallel_sweep.

The module backs the multi-file conformity-sweep that runs as a PreToolUse
hook on every Write/Edit. Both the sequential fallback and the
ProcessPoolExecutor path are exercised here; the previously-uncovered
binary/non-UTF-8 read path is locked in by
``test_binary_file_lossy_decodes``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apothem.lib.parallel_sweep import (
    Match,
    ParallelSweepError,
    _grep_one,
    _grep_one_compiled,
    parallel_apply,
    parallel_grep,
)


# Module-scope picklable functions -- required by ProcessPoolExecutor on
# Windows (spawn semantics cannot pickle lambdas or nested functions).
def _identity_path(path: Path) -> str:
    return str(path)


def _read_size(path: Path) -> int:
    return path.stat().st_size


def _always_raises(path: Path) -> None:
    msg = f"deliberate failure for {path}"
    raise RuntimeError(msg)


class TestMatchDataclass:
    """The match record.

    Covers that it is frozen and carries its three fields.
    """

    def test_match_is_frozen_with_three_fields(self):
        m = Match(path=Path("a.txt"), line=1, text="hello")
        assert m.path == Path("a.txt")
        assert m.line == 1
        assert m.text == "hello"
        with pytest.raises(AttributeError):
            m.line = 2


class TestGrepOneSequential:
    """Scanning a single file.

    Covers matches in a UTF-8 file, the two empty-result inputs (no matches, an
    empty file), the missing file yielding empty rather than raising, and a
    binary file decoding lossily so it cannot abort the sweep.
    """

    def test_finds_matches_in_utf8_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("alpha\nBETA match\ngamma\nBETA again\n", encoding="utf-8")
        out = _grep_one(f, re.compile("BETA"))
        assert len(out) == 2
        assert out[0].line == 2
        assert out[0].text == "BETA match"
        assert out[1].line == 4

    def test_returns_empty_on_missing_file(self, tmp_path):
        missing = tmp_path / "does-not-exist.txt"
        out = _grep_one(missing, re.compile("anything"))
        assert out == []

    def test_binary_file_lossy_decodes(self, tmp_path):
        f = tmp_path / "binary.dat"
        f.write_bytes(b"valid ASCII line\n\xff\xfe\xfdgarbled\nFINDME\n")
        out = _grep_one(f, re.compile("FINDME"))
        assert len(out) == 1
        assert out[0].text == "FINDME"

    def test_no_matches_yields_empty_list(self, tmp_path):
        f = tmp_path / "plain.txt"
        f.write_text("nothing here\nor here\n", encoding="utf-8")
        assert _grep_one(f, re.compile("ABSENT")) == []

    def test_empty_file_yields_empty_list(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        assert _grep_one(f, re.compile(".")) == []


class TestGrepOneCompiledWorker:
    """Pattern compilation inside the worker.

    Covers that the worker compiles its pattern per call — a compiled pattern
    cannot be assumed to survive the process boundary.
    """

    def test_worker_grep_one_compiles_pattern_per_call(self, tmp_path):
        f = tmp_path / "worker.txt"
        f.write_text("first\nsecond\nthird\n", encoding="utf-8")
        out = _grep_one_compiled(f, "second")
        assert len(out) == 1
        assert out[0].line == 2


class TestParallelGrepSequentialPath:
    """The single-worker sequential path.

    Covers matching with one worker, preservation of input path order, and the
    empty input yielding empty.
    """

    def test_sequential_path_with_single_worker(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f1.write_text("foo match\nbar\n", encoding="utf-8")
        f2 = tmp_path / "b.txt"
        f2.write_text("baz\nfoo also\n", encoding="utf-8")
        out = parallel_grep([f1, f2], "foo", max_workers=1)
        assert len(out) == 2
        assert {m.path for m in out} == {f1, f2}

    def test_sequential_preserves_input_path_order(self, tmp_path):
        files = [tmp_path / f"f{i}.txt" for i in range(5)]
        for f in files:
            f.write_text("match\n", encoding="utf-8")
        out = parallel_grep(files, "match", max_workers=1)
        assert [m.path for m in out] == files

    def test_empty_paths_yields_empty(self):
        assert parallel_grep([], "anything", max_workers=1) == []


class TestParallelGrepParallelPath:
    """The multi-worker parallel path.

    Covers matching across workers, the no-match result, and a worker exception
    being wrapped rather than lost — a crashed worker surfaces to the caller.
    """

    def test_parallel_path_with_multiple_workers(self, tmp_path):
        files = []
        for i in range(10):
            f = tmp_path / f"f{i}.txt"
            f.write_text(f"line zero\nMARKER number {i}\nline two\n", encoding="utf-8")
            files.append(f)
        out = parallel_grep(files, "MARKER", max_workers=2)
        assert len(out) == 10
        assert [m.path for m in out] == files

    def test_parallel_path_with_no_matches(self, tmp_path):
        files = []
        for i in range(4):
            f = tmp_path / f"g{i}.txt"
            f.write_text("nothing\n", encoding="utf-8")
            files.append(f)
        out = parallel_grep(files, "ABSENT", max_workers=2)
        assert out == []

    def test_parallel_path_wraps_worker_exception(self, tmp_path):
        # The worker recompiles the pattern per call (re.error is not among
        # the OSError/UnicodeDecodeError reads the worker tolerates), so an
        # invalid regex raises inside the worker; the parallel path wraps it
        # as ParallelSweepError carrying the offending path. max_workers=2
        # forces the executor path (the sequential path would raise re.error
        # in-process, unwrapped).
        f = tmp_path / "any.txt"
        f.write_text("content\n", encoding="utf-8")
        with pytest.raises(ParallelSweepError) as excinfo:
            parallel_grep([f], "[unterminated", max_workers=2)
        assert "parallel_grep failed on" in str(excinfo.value)
        assert "any.txt" in str(excinfo.value)


class TestParallelApplySequentialPath:
    """Sequential application of a callable.

    Covers results returned in input order and the empty input.
    """

    def test_sequential_apply_returns_results_in_input_order(self, tmp_path):
        files = []
        for i in range(3):
            f = tmp_path / f"size-{i}.txt"
            f.write_text("x" * (i + 1), encoding="utf-8")
            files.append(f)
        out = parallel_apply(files, _read_size, max_workers=1)
        assert out == [1, 2, 3]

    def test_sequential_apply_empty_list(self):
        assert parallel_apply([], _identity_path, max_workers=1) == []


class TestParallelApplyParallelPath:
    """Parallel application of a callable.

    Covers that input order is preserved despite out-of-order completion, and
    that a worker exception is wrapped.
    """

    def test_parallel_apply_preserves_input_order(self, tmp_path):
        files = []
        for i in range(8):
            f = tmp_path / f"p{i}.txt"
            f.write_text(f"{i}", encoding="utf-8")
            files.append(f)
        out = parallel_apply(files, _identity_path, max_workers=2)
        assert out == [str(f) for f in files]

    def test_parallel_apply_wraps_worker_exception(self, tmp_path):
        f = tmp_path / "any.txt"
        f.write_text("content", encoding="utf-8")
        with pytest.raises(ParallelSweepError) as excinfo:
            parallel_apply([f], _always_raises, max_workers=2)
        assert "parallel_apply failed on" in str(excinfo.value)
        assert "any.txt" in str(excinfo.value)
