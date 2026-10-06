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

Command-line contract. Every conformity entry point parses its arguments with
the one minimal parser built here (:func:`make_parser`), so they share one
behaviour: ``--help`` prints usage and exits 0; an unknown flag, a missing
file, or a root directory that does not exist is a usage error that prints a
one-line message and exits :data:`EXIT_USAGE` (3), never a traceback. A
root-based validator resolves its root to an absolute path before scanning, so
``.`` and the absolute form inspect the same tree, and its report carries an
``inspected`` count (:func:`finish_root_report`). A validator that inspected
nothing cannot pass unless it declares that an empty scope is expected.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final, NoReturn, Protocol

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2
# A command-line usage error (unknown flag, missing file or root): distinct
# from EXIT_FAIL so a caller can tell "invoked wrong" from "found a problem".
EXIT_USAGE: Final[int] = 3
STDIN_FLAG: Final[str] = "--stdin"

# Report key every root-based validator emits: how many targets it inspected.
INSPECTED_KEY: Final[str] = "inspected"
# Report key emitted only when nothing was inspected: whether the validator
# declared that an empty scope is expected (True) or not (False, a failure).
EMPTY_SCOPE_KEY: Final[str] = "empty_scope_expected"


# ---------------------------------------------------------------------------
# Shared command-line parser
# ---------------------------------------------------------------------------


class UsageParser(argparse.ArgumentParser):
    """An ``ArgumentParser`` whose usage errors exit :data:`EXIT_USAGE`.

    ``argparse`` exits 2 on a usage error by default, which collides with the
    conformity findings-block code :data:`EXIT_FAIL`. This subclass prints the
    usage line plus a one-line message to stderr and exits 3 instead.
    """

    def error(self, message: str) -> NoReturn:
        """Report a usage error on stderr and exit :data:`EXIT_USAGE`."""
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _summary(doc: str | None) -> str | None:
    """Return the first paragraph of a module docstring for ``--help``."""
    if not doc:
        return None
    return doc.strip().split("\n\n", 1)[0]


def make_parser(prog: str, doc: str | None = None) -> UsageParser:
    """Return the shared conformity parser for one entry point.

    Pre-conditions: ``prog`` is the name shown in usage text; ``doc`` is the
    module docstring (its first paragraph becomes the description).
    Post-conditions: abbreviated flags are rejected (``allow_abbrev=False``)
    so ``--al`` never silently means ``--all``.
    """
    return UsageParser(prog=prog, description=_summary(doc), allow_abbrev=False)


def _entry_identity(
    check: Callable[..., Any], argv: list[str]
) -> tuple[str, str | None]:
    """Return ``(prog, docstring)`` for the module that defines ``check``."""
    module = sys.modules.get(getattr(check, "__module__", "") or "")
    doc = getattr(module, "__doc__", None)
    prog = getattr(module, "GREP_NAME", None)
    if not isinstance(prog, str):
        prog = Path(argv[0]).stem if argv and argv[0] else "conformity-grep"
    return prog, doc if isinstance(doc, str) else None


def add_path_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the path-or-stdin input arguments of a per-file matcher."""
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="file to scan (omit, or pass --stdin, to read the content from stdin)",
    )
    parser.add_argument(
        STDIN_FLAG,
        dest="stdin",
        action="store_true",
        help="read the content from stdin instead of a file",
    )


def read_path_arguments(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> tuple[str, Path | None]:
    """Return ``(content, path)`` from parsed path-or-stdin arguments.

    Post-conditions: a ``path`` that is not an existing regular file is a
    usage error (exit :data:`EXIT_USAGE`); a ``path`` combined with
    ``--stdin`` is a usage error; with neither, stdin is read.
    """
    if args.path is not None and args.stdin:
        parser.error("pass either a file path or --stdin, not both")
    if args.path is None:
        return sys.stdin.read(), None
    path = Path(args.path)
    if not path.is_file():
        parser.error(f"not an existing file: {path}")
    try:
        return path.read_text(encoding="utf-8"), path
    except (OSError, UnicodeDecodeError) as exc:
        parser.error(f"cannot read {path}: {exc}")


def parse_root_args(
    argv: list[str],
    *,
    prog: str,
    doc: str | None = None,
    configure: Callable[[argparse.ArgumentParser], None] | None = None,
) -> argparse.Namespace:
    """Parse a root-based validator's arguments; resolve and check the root.

    Pre-conditions: ``argv`` is ``sys.argv`` (``argv[0]`` is the script
    name). ``configure``, when given, adds validator-specific flags.
    Post-conditions: ``namespace.root`` is the absolute, resolved root (the
    current directory when omitted). A root that is not an existing directory,
    or an unknown flag, exits :data:`EXIT_USAGE`; ``--help`` exits 0.
    """
    parser = make_parser(prog, doc)
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="directory to inspect (default: the current directory)",
    )
    if configure is not None:
        configure(parser)
    args = parser.parse_args(argv[1:])
    root = Path(args.root) if args.root is not None else Path.cwd()
    if not root.is_dir():
        parser.error(f"root is not an existing directory: {root}")
    args.root = root.resolve()
    return args


def finish_root_report(
    report_json: str,
    *,
    passed: bool,
    inspected: int,
    empty_scope_expected: bool = False,
    advisory: bool = False,
) -> int:
    """Stamp the ``inspected`` count on a root report, print it, return the exit.

    Pre-conditions: ``report_json`` is the validator's JSON object report;
    ``passed`` is its verdict; ``inspected`` is how many targets it examined;
    ``empty_scope_expected`` is True only when the validator documents that
    an empty scope is legitimate (for example a gitignored plans tree that a
    clean checkout does not carry). ``advisory`` validators report findings
    without failing.
    Post-conditions: the printed payload carries ``inspected``. When nothing
    was inspected it also carries ``empty_scope_expected``; an unexpected empty
    scope sets ``passed`` to false and returns :data:`EXIT_FAIL` even for an
    advisory validator, because a validator that inspected nothing has not
    earned a pass. Otherwise the return is :data:`EXIT_PASS` for a pass or an
    advisory validator, and :data:`EXIT_FAIL` for a failing blocking one.
    """
    payload = json.loads(report_json)
    payload[INSPECTED_KEY] = inspected
    vacuous = inspected == 0 and not empty_scope_expected
    if inspected == 0:
        payload[EMPTY_SCOPE_KEY] = empty_scope_expected
    if vacuous:
        payload["passed"] = False
    print(json.dumps(payload, indent=2))
    if vacuous:
        return EXIT_FAIL
    if advisory or passed:
        return EXIT_PASS
    return EXIT_FAIL


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


def parse_path_input(
    argv: list[str],
    *,
    prog: str,
    doc: str | None = None,
    configure: Callable[[argparse.ArgumentParser], None] | None = None,
) -> tuple[argparse.Namespace, str, Path | None]:
    """Parse a per-file matcher's arguments and read its input.

    Pre-conditions: ``argv`` is ``sys.argv``. ``configure`` adds
    matcher-specific flags.
    Post-conditions: returns ``(namespace, content, path)``; ``--help`` exits
    0 and a usage error (unknown flag, missing file) exits :data:`EXIT_USAGE`.
    """
    parser = make_parser(prog, doc)
    add_path_arguments(parser)
    if configure is not None:
        configure(parser)
    args = parser.parse_args(argv[1:])
    content, path = read_path_arguments(parser, args)
    return args, content, path


def run_grep(
    check: Callable[[str, Path | None], GrepResult],
    argv: list[str],
) -> int:
    """Run ``check`` over the resolved input, print the report, return the exit.

    Pre-conditions: ``check`` returns a :class:`GrepResult`. Post-conditions:
    the JSON report is printed to stdout; the return is ``EXIT_PASS`` when the
    result passed, ``EXIT_FAIL`` otherwise. ``--help`` and usage errors follow
    the shared command-line contract (exit 0 and :data:`EXIT_USAGE`).
    """
    prog, doc = _entry_identity(check, argv)
    _args, content, path = parse_path_input(argv, prog=prog, doc=doc)
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
# skeleton: the ``{grep, root, passed, advisory, findings}`` payload shape and
# the ``EXIT_PASS`` / ``EXIT_FAIL`` exit codes. The root comes from
# :func:`parse_root_args` (resolved, and required to exist) and the printed
# report carries the ``inspected`` count from :func:`finish_root_report`.


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
    # How many targets the run examined. Not part of ``to_json``: the CLI
    # stamps it on the printed report through :func:`finish_root_report`.
    inspected: int = 0

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


def run_root_grep(
    check: Callable[[Path], RootGrepResult],
    argv: list[str],
) -> int:
    """Run a root-based ``check``, print the report, return the exit code.

    Pre-conditions: ``check`` returns a :class:`RootGrepResult` whose
    ``inspected`` counts the targets the run examined. Post-conditions: the root is
    parsed and resolved per :func:`parse_root_args`; the JSON report, stamped
    with ``inspected``, is printed per :func:`finish_root_report`, whose exit
    contract this returns. A matcher whose ``--strict``-gated advisory posture
    differs keeps its own ``_main`` and calls only the dataclass.
    """
    prog, doc = _entry_identity(check, argv)
    root = parse_root_args(argv, prog=prog, doc=doc).root
    result = check(root)
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=result.inspected,
        advisory=result.advisory,
    )
