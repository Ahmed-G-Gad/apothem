# SPDX-License-Identifier: MIT

"""Shared scaffolding for path-based conformity matchers.

Why this module exists. The path-based conformity matchers
(``check(content, path) -> GrepResult``) each defined a byte-identical
``GrepResult`` dataclass, an identical ``to_json`` serialiser, and a
near-identical ``_read_input`` / ``_main`` / ``__main__`` skeleton. Hoisting
that boilerplate here removes the duplication while preserving every matcher's
observable behaviour: the JSON report shape, the exit codes, and the
stdin-or-path input contract are unchanged.

Scope. This base serves two matcher shapes. The path-based matchers
(``check(content, path) -> GrepResult``) whose canonical report payload is
exactly ``{grep, path, passed, findings}`` — optionally carrying a ``note``
emitted only when present — use :class:`GrepResult` / :func:`run_grep`. The
root-based standalone matchers (``check(root) -> RootGrepResult``) whose
canonical payload is ``{grep, root, passed, advisory, findings}`` use
:class:`RootGrepResult` / :func:`run_root_grep`. Matchers with extra report
keys or a bespoke ``_main`` (custom flags such as ``--staged`` / ``--strict``)
keep their own result dataclass because their serialised shape or CLI diverges
from these two.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final, Protocol

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2
STDIN_FLAG: Final[str] = "--stdin"


# ---------------------------------------------------------------------------
# Shared prose-line stripper
# ---------------------------------------------------------------------------
#
# The Markdown-prose matchers (hedging, completion_claim, agnosticism,
# freshness_token, binding_reciprocity) each re-implemented the identical
# fenced-code toggle loop: walk the lines, flip an ``inside_fence`` flag on a
# fence delimiter, skip fenced lines, and — for the two matchers that also
# exclude inline-code spans — blank those spans column-preservingly before
# scanning. The families diverge only in two parameters (the fence-delimiter
# regex and whether inline-code spans are blanked), so the loop is hoisted here
# as a parametrized generator. Each matcher passes its own regexes, preserving
# its exact matching behaviour: the column-0 fence form (``^```) or the
# indent-tolerant form (``^[ \t]*```), with or without inline blanking.
def _blank_span(match: re.Match[str]) -> str:
    """Replace a matched span with equal-length spaces (column-preserving)."""
    return " " * len(match.group(0))


def iter_prose_lines(
    lines: Iterable[str],
    *,
    fence_re: re.Pattern[str],
    inline_blank_re: re.Pattern[str] | None = None,
    start: int = 1,
) -> Iterator[tuple[int, str, str]]:
    """Yield ``(line_number, raw_line, scanned_line)`` for non-fenced lines.

    Pre-conditions: ``lines`` is an iterable of already-split lines (no trailing
    newlines); ``fence_re`` matches a fenced-code delimiter; ``inline_blank_re``,
    when given, matches an inline-code span to blank column-preservingly.
    Post-conditions: a line inside a fenced block (delimited by ``fence_re``,
    opening and closing fences both toggling the state) is skipped; every other
    line is yielded with a 1-based number offset by ``start``. ``scanned_line``
    is ``raw_line`` with each ``inline_blank_re`` span replaced by equal-length
    spaces when ``inline_blank_re`` is supplied, else ``raw_line`` unchanged.
    """
    inside_fence = False
    for line_number, raw_line in enumerate(lines, start=start):
        if fence_re.match(raw_line):
            inside_fence = not inside_fence
            continue
        if inside_fence:
            continue
        scanned = (
            inline_blank_re.sub(_blank_span, raw_line)
            if inline_blank_re is not None
            else raw_line
        )
        yield line_number, raw_line, scanned


class _Finding(Protocol):
    """Structural marker for a per-matcher finding dataclass.

    Documentation only — not enforced at runtime or by the type checker:
    ``GrepResult.findings`` is typed loosely and each frozen finding dataclass
    is serialized by duck-typing through ``dataclasses.asdict``. This Protocol
    records the shape matcher findings are expected to satisfy; it is not wired
    as a bound on ``findings``.
    """


@dataclass(frozen=True)
class GrepResult:
    """Canonical path-based matcher report.

    Pre-conditions: ``findings`` holds the matcher-specific finding dataclasses
    (each a frozen ``@dataclass``). Post-conditions: ``to_json`` emits the
    canonical ``{grep, path, passed, findings}`` payload, including ``note``
    only when it is not ``None``.
    """

    grep: str
    path: str | None
    passed: bool
    findings: list[Any] = field(default_factory=list)
    note: str | None = None

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, path, passed,
        findings}``; each finding is flattened through ``dataclasses.asdict``.

        ``note`` is emitted only when it is not ``None``.
        """
        payload: dict[str, object] = {
            "grep": self.grep,
            "path": self.path,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        if self.note is not None:
            payload["note"] = self.note
        return json.dumps(payload, indent=2)


def read_input(argv: list[str]) -> tuple[str, Path | None]:
    """Return ``(content, path)`` from a path argument or stdin.

    Pre-conditions: ``argv`` is ``sys.argv`` (``argv[0]`` is the script name).
    Post-conditions: when ``argv[1]`` is a path (not ``--stdin``), the file is
    read and returned with its ``Path``; otherwise stdin is read with a
    ``None`` path.
    """
    if len(argv) >= 2 and argv[1] != STDIN_FLAG:
        path = Path(argv[1])
        return path.read_text(encoding="utf-8"), path
    return sys.stdin.read(), None


def run_grep(
    check: Callable[[str, Path | None], GrepResult],
    argv: list[str],
) -> int:
    """Run ``check`` over the resolved input, print the report, return the exit.

    Pre-conditions: ``check`` returns a :class:`GrepResult`. Post-conditions:
    the JSON report is printed to stdout; the return is ``EXIT_PASS`` when the
    result passed, ``EXIT_FAIL`` otherwise.
    """
    content, path = read_input(argv)
    result = check(content, path)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


# ---------------------------------------------------------------------------
# Root-based standalone matchers
# ---------------------------------------------------------------------------
#
# The corpus-level standalone validators (``check(root) -> RootGrepResult``)
# each re-implement a byte-near-identical ``root``-based ``GrepResult`` +
# ``to_json`` + ``_read_input`` / ``_main`` skeleton. The types below hoist that
# boilerplate the same way ``GrepResult`` / ``run_grep`` hoist the path-based
# skeleton, preserving the observable behaviour: the ``{grep, root, passed,
# advisory, findings}`` payload shape, the ``EXIT_PASS`` / ``EXIT_FAIL`` exit
# codes, and the ``argv[1]``-or-cwd root resolution are unchanged.


@dataclass(frozen=True)
class RootGrepResult:
    """Canonical root-based standalone-matcher report.

    Pre-conditions: ``findings`` holds the matcher-specific finding dataclasses
    (each a frozen ``@dataclass``). Post-conditions: ``to_json`` emits the
    canonical ``{grep, root, passed, advisory, findings}`` payload. ``advisory``
    is always serialised (unlike ``GrepResult.note``, which is conditional) so a
    consumer can read the advisory disposition without inferring it.
    """

    grep: str
    root: str
    passed: bool
    advisory: bool = False
    findings: list[Any] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, passed, advisory,
        findings}``; each finding is flattened through ``dataclasses.asdict``.
        """
        payload: dict[str, object] = {
            "grep": self.grep,
            "root": self.root,
            "passed": self.passed,
            "advisory": self.advisory,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def read_root(argv: list[str]) -> Path:
    """Return the root directory from ``argv[1]`` or the current directory.

    Pre-conditions: ``argv`` is ``sys.argv`` (``argv[0]`` is the script name).
    Post-conditions: when ``argv[1]`` is supplied it is returned as a ``Path``;
    otherwise the current working directory is returned.
    """
    if len(argv) >= 2:
        return Path(argv[1])
    return Path.cwd()


def run_root_grep(
    check: Callable[[Path], RootGrepResult],
    argv: list[str],
) -> int:
    """Run a root-based ``check``, print the report, return the exit code.

    Pre-conditions: ``check`` returns a :class:`RootGrepResult`. Post-conditions:
    the JSON report is printed to stdout; the return is ``EXIT_PASS`` when the
    result passed, ``EXIT_FAIL`` otherwise. This mirrors :func:`run_grep`'s
    non-advisory exit contract; a matcher whose ``--strict``-gated advisory
    posture differs keeps its own ``_main`` and calls only the dataclass.
    """
    root = read_root(argv)
    result = check(root)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL
