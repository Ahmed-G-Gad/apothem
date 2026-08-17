# SPDX-License-Identifier: MIT

"""Parallel file-sweep utilities backed by ProcessPoolExecutor.

Why this module exists. Many ecosystem tools sweep across hundreds of
files at a time (authorship-header sweeps at 200+ files, audit scanners
at 200+ files, link-checkers across the docs tree).
Sequential per-file processing on these tools dominates wall-clock
time on operations whose per-file work exceeds process-spawn overhead.
This module provides a generic ProcessPoolExecutor-backed parallel
helper plus a sequential fallback.

When to use vs. avoid. Parallelism helps when:

- Per-file work exceeds ProcessPoolExecutor spawn overhead (~50-200ms
  per worker on Windows, ~10-50ms on POSIX).
- File count is high (≥ 20 files for a noticeable wall-clock win).
- Per-file work is CPU-bound (matcher pattern-matching, regex, parse).

Parallelism HURTS when per-file work is sub-millisecond (for example,
the conformity-gate orchestrator's per-matcher work is below process
spawn overhead). Choose the API consciously; benchmark before committing.

Public API. Two callables — `parallel_grep` for pattern-matching across
files (returns Match records); `parallel_apply` for arbitrary per-file
function application (returns the function's per-file results). Both
honor `max_workers=1` as the sequential fallback signal.

Current production callers. None today. This module is kept available for
tools that meet the criteria above and is exercised by
``tests/unit/test_parallel_sweep.py``; the conformity-gate orchestrator runs
its matchers sequentially because their per-matcher work sits below
process-spawn overhead. The absence of a production caller is deliberate, not
neglect — adopt this module only after a benchmark confirms a win.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypeVar

T = TypeVar("T")

DEFAULT_MAX_WORKERS: Final[int] = os.cpu_count() or 4
SEQUENTIAL_THRESHOLD: Final[int] = 1


class ParallelSweepError(Exception):
    """Raised when a parallel-sweep invocation cannot complete.

    Wraps lower-level concurrent.futures errors with the originating
    file path so callers can route per-file failures without parsing
    the underlying executor's exception chain.
    """


@dataclass(frozen=True, slots=True)
class Match:
    """A single pattern match found in a file by `parallel_grep`.

    Attributes:
        path: The file the match was found in (relative or absolute,
            preserved from the input).
        line: 1-based line number of the match.
        text: The full text of the matching line, with trailing
            newline stripped.
    """

    path: Path
    line: int
    text: str


def parallel_grep(
    paths: list[Path],
    pattern: str,
    max_workers: int | None = None,
) -> list[Match]:
    """Search `paths` in parallel for lines matching `pattern`.

    Args:
        paths: Files to search. Directory paths are NOT recursed; the
            caller resolves directory expansion before invocation.
        pattern: Regular-expression pattern compiled with `re.compile`
            on each worker. The pattern is line-oriented; multiline
            patterns require pre-compilation by the caller and use of
            `parallel_apply` instead.
        max_workers: Worker process count. `None` resolves to
            `DEFAULT_MAX_WORKERS` (the host's CPU count, fallback 4).
            `1` activates the sequential fallback (no executor
            spawned; useful for measurement comparison or when the
            host disallows multi-process execution).

    Returns:
        A flat list of `Match` records across all files, ordered by
        the input path order then by line number within each file.

    Raises:
        ParallelSweepError: When a worker raises an unhandled exception
            on a file. The wrapped exception carries the file path.
    """
    workers = max_workers if max_workers is not None else DEFAULT_MAX_WORKERS
    if workers <= SEQUENTIAL_THRESHOLD:
        return _grep_sequential(paths, pattern)
    return _grep_parallel(paths, pattern, workers)


def parallel_apply(
    paths: list[Path],
    func: Callable[[Path], T],
    max_workers: int | None = None,
) -> list[T]:
    """Apply `func` to each path in `paths` in parallel.

    Args:
        paths: Files (or any path-like inputs) to apply `func` to.
        func: A pure callable taking one `Path` and returning a value.
            Must be picklable (defined at module scope, not a lambda
            or nested closure) for ProcessPoolExecutor marshalling.
        max_workers: Worker process count. `None` resolves to
            `DEFAULT_MAX_WORKERS`. `1` activates the sequential
            fallback.

    Returns:
        Per-path results in the input path order. The order invariant
        is enforced via path-keyed result collection (results gathered
        via `as_completed` then re-sorted).

    Raises:
        ParallelSweepError: When `func` raises on any path. The wrapped
            exception carries the file path.
    """
    workers = max_workers if max_workers is not None else DEFAULT_MAX_WORKERS
    if workers <= SEQUENTIAL_THRESHOLD:
        return [func(p) for p in paths]
    return _apply_parallel(paths, func, workers)


def _grep_sequential(paths: list[Path], pattern: str) -> list[Match]:
    """Sequential grep fallback (no executor)."""
    compiled = re.compile(pattern)
    matches: list[Match] = []
    for path in paths:
        matches.extend(_grep_one(path, compiled))
    return matches


def _grep_parallel(
    paths: list[Path],
    pattern: str,
    workers: int,
) -> list[Match]:
    """Parallel grep via ProcessPoolExecutor."""
    results: dict[Path, list[Match]] = {}
    with ProcessPoolExecutor(max_workers=workers) as executor:
        future_to_path = {
            executor.submit(_grep_one_compiled, path, pattern): path for path in paths
        }
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                results[path] = future.result()
            except Exception as exc:
                raise ParallelSweepError(
                    f"parallel_grep failed on {path}: {exc!r}",
                ) from exc
    flattened: list[Match] = []
    for path in paths:
        flattened.extend(results.get(path, []))
    return flattened


def _apply_parallel(
    paths: list[Path],
    func: Callable[[Path], T],
    workers: int,
) -> list[T]:
    """Parallel apply via ProcessPoolExecutor with order preservation."""
    # Key by position, not by path: a duplicate path in *paths* submits two
    # distinct futures, and keying results by path would collapse them — the
    # second result would overwrite the first and the output list would carry
    # one entry twice. Position keys preserve one result per input slot.
    results: dict[int, T] = {}
    with ProcessPoolExecutor(max_workers=workers) as executor:
        future_to_index = {
            executor.submit(func, path): index for index, path in enumerate(paths)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                raise ParallelSweepError(
                    f"parallel_apply failed on {paths[index]}: {exc!r}",
                ) from exc
    return [results[index] for index in range(len(paths))]


def _grep_one(path: Path, compiled: re.Pattern[str]) -> list[Match]:
    """Grep a single file (sequential-fallback path).

    Splits the read error path so non-UTF-8 byte content (binaries, mixed
    encodings) is still scanned with a lossy decode rather than silently
    dropped as "no matches" alongside legitimately unreadable files.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    return [
        Match(path=path, line=lineno, text=line)
        for lineno, line in enumerate(text.splitlines(), start=1)
        if compiled.search(line)
    ]


def _grep_one_compiled(path: Path, pattern: str) -> list[Match]:
    """Grep a single file in a worker process (compiles pattern per call).

    The pattern is recompiled per worker call rather than passed as a
    pre-compiled `re.Pattern` because compiled patterns are not always
    cleanly picklable across worker process boundaries on every Python
    runtime; recompilation per call is fast (microseconds) and removes
    the marshalling-fragility surface.
    """
    compiled = re.compile(pattern)
    return _grep_one(path, compiled)
