# SPDX-License-Identifier: MIT

"""Follow every printed marker fix, literally, on generated files.

The marker warnings give numbered fixes of one kind: "Change line N: add a
word inside its comment." rewords a marker line in place, and one more step,
"Below line N, add a line of K backticks." (or tildes), closes a code block
the file ends in. This test reads each message only as an operator would: it
parses the printed text with patterns of its own, applies the steps of each
fix in the printed order, and checks three things on the result:

1. The fix's closing sentence holds. ``merge_managed_block``, with and
   without an install record, for rule bodies that hold backtick, tilde and
   four-backtick code blocks, gives exactly one whole block (at the end of
   the file when the sentence says the next update writes it there), and
   ``remove_managed_block`` leaves none.
2. No line of the operator's changes how a CommonMark viewer (markdown-it)
   reads it: text, heading, rule, HTML, code, fence opener or fence closer.
   The reworded marker lines are not the operator's.
3. No line of the operator's is gone, after the steps and after the update or
   uninstall the fix promises.

A step the test cannot read, a step that moves, copies or deletes a line, a
"Change line" step on a line that is no marker line, and a closing line a
viewer reads as a fence opener each fail too. Where Apothem's reading and a
viewer's part at a limit the docs name (lazy list-item lines, HTML blocks),
the added closing line can stay inside a code or HTML block as a viewer reads
it, or Apothem's block can read as code there; no line of the operator's
reads differently then, so those cases are counted, not failed. So is a block
replaced in place that re-pairs a fence its old text opened or closed, the
merge's own behaviour.

The messages come from every caller, through the public function each caller
uses: install and update warnings (with and without an install record, and
in a dry run), verify and doctor notes, the uninstall's warnings and summary
lines, and OpenClaw's retire warnings and size refusal. Nothing here reads
the code that builds the fixes.

``APOTHEM_ADVICE_PROPERTY_FILES`` raises the number of generated files from
its default, which fits a CI run.
"""

from __future__ import annotations

import ctypes
import functools
import json
import os
import random
import re
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from markdown_it import MarkdownIt

from apothem.cli import _cmd_uninstall
from apothem.cli._stray_begin_report import stray_begin_note
from apothem.harnesses._shared.install_driver_blocks import (
    RETIRED_WHY,
    UNINSTALL_AGAIN,
    another_block_at,
    another_block_warning,
    endless_block_warning,
    markers_to_fix_at,
    sentinel_refusal,
    stray_begin_install_warnings,
    stray_begin_warnings,
    unclear_block_warning,
)
from apothem.harnesses._shared.install_driver_blocktext import TAKES_OUT
from apothem.harnesses._shared.install_driver_retention import (
    unlisted_block_warnings,
)
from apothem.harnesses._shared.install_driver_types import MaterializationResult
from apothem.harnesses.open_claw import rules_file
from apothem.lib import harness_materializer as materializer
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    complete_managed_block,
)

B, E = APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END

# The same texts come back from many fixes and callers; each reading is a
# pure function of the text, so it is kept.
whole_blocks = functools.lru_cache(maxsize=8192)(materializer.whole_blocks)
has_stray_begin = functools.lru_cache(maxsize=8192)(materializer.has_stray_begin)
uncertain_pairs = functools.lru_cache(maxsize=8192)(materializer.uncertain_pairs)

#: How long a strip may take before the test calls it stuck, in seconds.
_DEADLINE = 3.0

#: The texts whose strip did not return in time.
_STUCK: set[str] = set()


def _stop(thread: threading.Thread) -> None:
    """End *thread*, stuck in a Python loop, by raising ``SystemExit`` in it."""
    ident = ctypes.c_ulong(thread.ident or 0)
    ctypes.pythonapi.PyThreadState_SetAsyncExc(ident, ctypes.py_object(SystemExit))
    thread.join(_DEADLINE)


@functools.lru_cache(maxsize=8192)
def remove_managed_block(text: str) -> str:
    """Return :func:`materializer.remove_managed_block`'s result, or fail when stuck.

    The strip runs in a thread so a text it never finishes fails the test
    with that text instead of hanging the run; the thread is then stopped.
    """
    if text in _STUCK:
        raise BrokenFixError(
            "strip-hangs", f"remove_managed_block({text!r}) never returns"
        )
    found: list[str] = []
    errors: list[BaseException] = []

    def strip() -> None:
        try:
            found.append(materializer.remove_managed_block(text))
        except Exception as error:  # re-raised below
            errors.append(error)
        except SystemExit:
            return  # stopped by _stop

    thread = threading.Thread(target=strip, daemon=True)
    thread.start()
    thread.join(_DEADLINE)
    if thread.is_alive():
        _stop(thread)
        _STUCK.add(text)
        raise BrokenFixError(
            "strip-hangs", f"remove_managed_block({text!r}) never returns"
        )
    if errors:
        raise errors[0]
    return found[0]


@functools.lru_cache(maxsize=16384)
def merge_managed_block(existing: str, body: str, *, recorded: bool = False) -> str:
    """Return :func:`materializer.merge_managed_block`'s result, kept per input."""
    return materializer.merge_managed_block(existing, body, recorded=recorded)


#: Rule bodies the next update may write: plain text, and closed and open
#: code blocks of three backticks, three tildes and four backticks.
BODIES = (
    "Apothem rule.",
    "Run:\n```sh\nnpm test\n```",
    "Run:\n```sh\nnpm test",
    "Run:\n~~~sh\nnpm test\n~~~",
    "Run:\n~~~\nnpm test",
    "Example:\n````md\n```\nx\n```\n````",
    "Example:\n````md\nx",
)

#: The body the simulated install and update write.
INSTALL_BODY = "Apothem rule one.\nRun:\n```sh\nmake test\n```"

#: What the OpenClaw retire path gives as the step after a fix.
_RETRY = "the next install, update or uninstall then takes Apothem's block out"

# -- The printed text, read with this test's own patterns -------------------

_HEADER = re.compile(r"Fix (?P<id>[A-Z]+)(?:, (?P<case>[^:]+))?: ")
_NUMBER = re.compile(r"(?<![\w\\/])(?P<id>[A-Z]+)(?P<n>\d+)\.(?=\s)")
_CHANGE = re.compile(r" Change line (?P<line>\d+): add a word inside its comment\.")
_CLOSE = re.compile(
    r" Below line (?P<line>\d+), add a line of (?P<count>\d+) "
    r"(?P<kind>backticks|tildes)(?:, indented (?P<indent>\d+) spaces?)?\."
)
_CASE_BLOCK = re.compile(r"if lines (\d+) to (\d+) are Apothem's block")
_CASE_YOURS = re.compile(r"if lines (\d+) to (\d+) are text of yours")
_SENTENCE = re.compile(r"\s*(?P<s>.+?\.)(?=\s|$)", re.DOTALL)

#: Step wordings and prose edits that move, copy or delete a line.
_FORBIDDEN = re.compile(
    r"Move line|Delete line|add a copy|Above line|[Dd]elete (?:the )?lines? \d"
    r"|[Mm]ove (?:the )?lines? \d"
)

#: The OpenClaw size refusal's prose steps: a closing line, then the changes.
_PROSE_CLOSE = re.compile(
    r"add a line of (?P<count>\d+) (?P<kind>backticks|tildes)"
    r"(?:, indented (?P<indent>\d+) spaces?,?)? below line (?P<line>\d+)"
)
_PROSE_CHANGE = re.compile(
    r"change (?:line (?P<one>\d+)|lines (?P<many>[\d, ]+ and \d+)) by adding a "
    r"word inside (?:its|each) comment"
)

_LINES_OR_BLOCK = r"(?:Apothem's block|lines (?P<a>\d+) to (?P<b>\d+))"

#: What a fix for an OpenClaw rules file adds: the update writes it only while
#: it fits OpenClaw's per-file limit.
_FITS = (
    r"(?: if the file then fits OpenClaw's per-file limit \(bootstrapMaxChars\), "
    r"which old Apothem text you keep counts against)?"
)

#: Each closing sentence, and what it promises: a block that stays (``keep``)
#: or no block, with the next update's block at the end (``none``).
_PROMISES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(rf"The next update then replaces {_LINES_OR_BLOCK}{_FITS}\."), "keep"),
    (
        re.compile(
            rf"The next update then writes {_LINES_OR_BLOCK} if the file fits\."
        ),
        "fits",
    ),
    (
        re.compile(
            rf"The next install, update or uninstall then takes {_LINES_OR_BLOCK} out\."
        ),
        "keep",
    ),
    (
        re.compile(
            r"Lines (?P<a>\d+) to (?P<b>\d+) are then the one block in the file"
            rf"(?:, and the next update replaces it{_FITS})?\."
        ),
        "keep",
    ),
    (
        re.compile(rf"The uninstall run again then takes {_LINES_OR_BLOCK} out\."),
        "keep",
    ),
    (re.compile(r"Apothem then finds no block of its own in this file\."), "none"),
    (
        re.compile(
            r"Apothem then reads none of these lines as its markers, and the next "
            rf"update writes its block at the end of the file{_FITS}\."
        ),
        "none",
    ),
    (
        re.compile(rf"The next update then adds Apothem's block to the file{_FITS}\."),
        "none",
    ),
    (re.compile(r"No Apothem block is then left in this file\."), "none"),
)


@dataclass
class Step:
    """One printed step: a changed line, or a closing fence line added."""

    kind: str
    line: int
    fence: str = ""


@dataclass
class Fix:
    """One printed fix: its label, case, steps and closing sentence."""

    label: str
    case: str
    steps: list[Step] = field(default_factory=list)
    promise: str = ""


class BrokenFixError(AssertionError):
    """A printed fix that breaks the change-only contract."""

    def __init__(self, kind: str, problem: str) -> None:
        super().__init__(f"{kind}: {problem}")
        self.kind = kind
        self.problem = problem


def parse_fixes(message: str) -> list[Fix]:
    """Return the fixes *message* prints; raise :class:`BrokenFixError` on text it cannot read."""
    found = _FORBIDDEN.search(message)
    if found:
        raise BrokenFixError("forbidden-step", f"the message says {found.group(0)!r}")
    headers = list(_HEADER.finditer(message))
    fixes: list[Fix] = []
    consumed: set[int] = set()
    for index, header in enumerate(headers):
        stop = headers[index + 1].start() if index + 1 < len(headers) else len(message)
        fix = Fix(label=header["id"], case=header["case"] or "")
        at = header.end() - 1
        expected = 1
        while True:
            number = _NUMBER.match(message, at + 1)
            if number is None or number.start() >= stop:
                break
            if number["id"] != fix.label or int(number["n"]) != expected:
                raise BrokenFixError(
                    "unparsed-step",
                    f"step {number.group(0)!r} out of order in fix {fix.label}",
                )
            consumed.add(number.start())
            rest = number.end()
            change = _CHANGE.match(message, rest)
            close = _CLOSE.match(message, rest)
            if change:
                fix.steps.append(Step("change", int(change["line"])))
                at = change.end()
            elif close:
                char = "`" if close["kind"] == "backticks" else "~"
                indent = " " * int(close["indent"] or 0)
                fix.steps.append(
                    Step(
                        "close", int(close["line"]), indent + char * int(close["count"])
                    )
                )
                at = close.end()
            else:
                snippet = message[number.start() : number.start() + 80]
                raise BrokenFixError("unparsed-step", f"cannot read step {snippet!r}")
            expected += 1
        if not fix.steps:
            raise BrokenFixError("no-steps", f"fix {fix.label} gives no numbered step")
        sentence = _SENTENCE.match(message, at)
        fix.promise = sentence["s"].strip() if sentence else ""
        fixes.append(fix)
    for number in _NUMBER.finditer(message):
        if number.start() not in consumed:
            snippet = message[number.start() : number.start() + 80]
            raise BrokenFixError("unparsed-step", f"a number no fix holds: {snippet!r}")
    return fixes


def prose_steps(message: str) -> list[Step]:
    """Return the steps the OpenClaw size refusal gives, in the order it gives them.

    A closing line it names comes first, then the changed lines, highest
    first; an "add a line" this test cannot read fails.
    """
    steps: list[Step] = []
    close = _PROSE_CLOSE.search(message)
    if close is not None:
        char = "`" if close["kind"] == "backticks" else "~"
        indent = " " * int(close["indent"] or 0)
        fence = indent + char * int(close["count"])
        steps.append(Step("close", int(close["line"]), fence))
    if message.count("add a line") != (close is not None):
        raise BrokenFixError(
            "unparsed-step", "the size refusal adds a line it cannot read"
        )
    found = _PROSE_CHANGE.search(message)
    if found is None:
        return steps
    if found["one"]:
        lines = [int(found["one"])]
    else:
        lines = [int(part) for part in re.findall(r"\d+", found["many"])]
    return steps + [Step("change", line) for line in sorted(lines, reverse=True)]


# -- Applying steps, and reading lines as a viewer does ----------------------


def split(text: str) -> tuple[list[str], bool]:
    """Return *text*'s lines (LF only here) and whether it ends in a newline."""
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
        return lines, True
    return lines, False


def join(lines: list[str], newline: bool) -> str:
    """Return the text of *lines*."""
    return "\n".join(lines) + ("\n" if newline and lines else "")


def reword(line: str) -> str:
    """Return the marker *line* with a word added inside its comment."""
    at = line.rfind("-->")
    return f"{line[:at]}(changed) {line[at:]}"


def apply_steps(basis: str, steps: list[Step]) -> tuple[str, set[int], int | None]:
    """Return *basis* after *steps*, the changed line indexes, and an added line's index."""
    lines, newline = split(basis)
    count = len(lines)
    changed: set[int] = set()
    added: int | None = None
    last = count + 1
    for step in steps:
        if step.line > last:
            raise BrokenFixError("not-bottom-up", f"line {step.line} after line {last}")
        last = step.line
        if step.kind == "close":
            if step.line != count:
                raise BrokenFixError(
                    "close-not-last",
                    f"closing line added below line {step.line} of {count}",
                )
            if added is not None:
                raise BrokenFixError("two-closers", "two closing lines in one fix")
            added = len(lines)
            lines.append(step.fence)
            continue
        index = step.line - 1
        if not 0 <= index < count:
            raise BrokenFixError("bad-line", f"line {step.line} of {count}")
        if lines[index].strip() not in (B, E):
            raise BrokenFixError(
                "not-a-marker", f"line {step.line} is {lines[index]!r}, no marker line"
            )
        if index in changed:
            raise BrokenFixError("changed-twice", f"line {step.line}")
        lines[index] = reword(lines[index])
        changed.add(index)
    return join(lines, newline), changed, added


_MD = MarkdownIt("commonmark")
_LEAVES = {"paragraph_open": "text", "heading_open": "heading", "hr": "hr"}


def roles(text: str) -> list[str]:
    """Return how a CommonMark viewer reads each line of *text*."""
    return list(_roles(text))


@functools.lru_cache(maxsize=4096)
def _roles(text: str) -> tuple[str, ...]:
    lines, newline = split(text)
    found = ["blank" if not line.strip() else "none" for line in lines]
    # A fence closed on the last line counts its lines the same with or
    # without a newline after it, so the text is read with one.
    for token in _MD.parse(text if newline else text + "\n"):
        if token.map is None:
            continue
        first, after = token.map
        if token.type in _LEAVES:
            for index in range(first, after):
                found[index] = _LEAVES[token.type]
        elif token.type == "html_block":
            for index in range(first, after):
                found[index] = "html"
        elif token.type == "code_block":
            for index in range(first, after):
                found[index] = "code"
        elif token.type == "fence":
            closed = (after - first - 1) - token.content.count("\n") == 1
            found[first] = "opener"
            for index in range(first + 1, after):
                found[index] = "code"
            if closed:
                found[after - 1] = "closer"
    return tuple(found)


# -- Checking one fix --------------------------------------------------------


def _line_of_end(text: str) -> int:
    return len(split(text)[0])


def check_fix(
    basis: str,
    fix: Fix,
    scratch: Path,
    *,
    info: dict[str, int],
    kind: str | None = None,
) -> None:
    """Follow *fix* on *basis* and check the three properties; raise on a break.

    *kind* stands for the promise when the message prints no closing sentence.
    """
    fixed, changed, added = apply_steps(basis, fix.steps)
    before, after = roles(basis), roles(fixed)
    base_lines = split(basis)[0]
    for index in range(len(before)):
        if index not in changed and before[index] != after[index]:
            raise BrokenFixError(
                "role-after-steps",
                f"fix {fix.label}: line {index + 1} {base_lines[index]!r} reads "
                f"{before[index]} before the steps and {after[index]} after",
            )
    if added is not None and after[added] in ("code", "html"):
        # The file ends in a code block, or an HTML block, as a viewer reads
        # it, so the added line stays inside it: a reading limit the docs
        # name (lazy list-item lines, HTML blocks), and no line of the
        # operator's reads differently.
        info[f"close-reads-{after[added]}"] = (
            info.get(f"close-reads-{after[added]}", 0) + 1
        )
    elif added is not None and after[added] != "closer":
        raise BrokenFixError(
            f"close-reads-{after[added]}",
            f"fix {fix.label}: the added line {fix.steps[0].fence!r} reads "
            f"{after[added]}, not a fence closer",
        )
    span = None
    if kind is None:
        kind, span = _promise(fix)
    _check_promise(fixed, fix, kind, span, scratch, info=info)


def _promise(fix: Fix) -> tuple[str, tuple[int, int] | None]:
    for pattern, kind in _PROMISES:
        found = pattern.fullmatch(fix.promise)
        if found is None:
            continue
        groups = found.groupdict()
        span = None
        if groups.get("a"):
            span = (int(groups["a"]), int(groups["b"]))
        else:
            case = _CASE_BLOCK.search(fix.case)
            if case:
                span = (int(case[1]), int(case[2]))
        if kind == "fits":
            kind = "keep" if span is not None else "fits"
        if kind == "keep" and _CASE_YOURS.search(fix.case):
            raise BrokenFixError(
                "promise-case", f"fix {fix.label} keeps a block for {fix.case!r}"
            )
        return kind, span
    raise BrokenFixError("unknown-promise", f"fix {fix.label} ends {fix.promise!r}")


def _check_promise(
    fixed: str,
    fix: Fix,
    kind: str,
    span: tuple[int, int] | None,
    scratch: Path,
    *,
    info: dict[str, int],
) -> None:
    blocks = whole_blocks(fixed)
    if kind == "keep" and (
        len(blocks) != 1 or (span is not None and blocks[0] != span)
    ):
        raise BrokenFixError(
            "promise-block",
            f"fix {fix.label} promises {span or 'one block'}; the steps leave whole "
            f"blocks {blocks}",
        )
    if kind == "none" and blocks:
        raise BrokenFixError(
            "promise-none",
            f"fix {fix.label} promises no block; the steps leave whole blocks {blocks}",
        )
    if len(blocks) > 1:
        raise BrokenFixError("promise-fits", f"fix {fix.label} leaves {blocks}")
    if has_stray_begin(fixed):
        raise BrokenFixError(
            "stray-left",
            f"fix {fix.label}: a BEGIN marker that starts no block is left",
        )
    pairs = uncertain_pairs(fixed)
    if pairs:
        # No whole block and a marker pair in code: a merge with an install
        # record then leaves the file as it is, and an uninstall with one
        # stops at the pair.
        named = [(pair.begin.line, pair.end.line) for pair in pairs]
        raise BrokenFixError(
            "pair-in-code-left",
            f"fix {fix.label} ({fix.promise[:40]}...) leaves the marker pairs {named}, "
            "whose BEGIN lines no step changes",
        )
    keep = blocks[0] if blocks else None
    lines = split(fixed)[0]
    fixed_roles = roles(fixed)
    for body in BODIES:
        for recorded in (False, True):
            merged = merge_managed_block(fixed, body, recorded=recorded)
            where = f"fix {fix.label}, rule body {body!r}, recorded={recorded}"
            _check_merged(fixed, merged, keep, lines, fixed_roles, where, info)
    # The uninstall, through the function it uses, with and without a record.
    remove_managed_block(fixed)  # the uninstall below strips it too
    _put(scratch, fixed)
    for recorded in (False, True):
        refusal = sentinel_refusal(scratch, recorded=recorded)
        if refusal is not None:
            raise BrokenFixError(
                "promise-uninstall",
                f"fix {fix.label}, recorded={recorded}: the uninstall then still "
                f"refuses: {refusal.message[-160:]!r}",
            )
    removed = remove_managed_block(fixed)
    if whole_blocks(removed) or has_stray_begin(removed):
        raise BrokenFixError(
            "promise-remove", f"fix {fix.label}: the uninstall then leaves markers"
        )
    _check_kept(lines, keep, split(removed)[0], f"fix {fix.label}, the uninstall")


def _check_merged(
    fixed: str,
    merged: str,
    keep: tuple[int, int] | None,
    lines: list[str],
    fixed_roles: list[str],
    where: str,
    info: dict[str, int],
) -> None:
    blocks = whole_blocks(merged)
    if len(blocks) != 1 or has_stray_begin(merged) or uncertain_pairs(merged):
        raise BrokenFixError(
            "promise-update",
            f"{where}: the update leaves whole blocks {blocks}, a stray BEGIN "
            f"{has_stray_begin(merged)}, unclear pairs {bool(uncertain_pairs(merged))}",
        )
    merged_roles = roles(merged)
    begin, end = blocks[0]
    if keep is None:
        if not merged.startswith(fixed) or end != _line_of_end(merged):
            raise BrokenFixError("promise-end", f"{where}: the block is not at the end")
        if merged_roles[: len(fixed_roles)] != fixed_roles:
            raise BrokenFixError(
                "role-after-update", f"{where}: appending changed how a line reads"
            )
    else:
        if begin != keep[0]:
            raise BrokenFixError(
                "promise-update", f"{where}: the block moved from {keep} to {blocks[0]}"
            )
        new = split(merged)[0]
        if new[: begin - 1] != lines[: begin - 1] or new[end:] != lines[keep[1] :]:
            raise BrokenFixError(
                "line-gone", f"{where}: the update changed a line of yours"
            )
        shift = end - keep[1]
        for index, role in enumerate(fixed_roles):
            if keep[0] - 1 <= index < keep[1]:
                continue
            if merged_roles[index if index < begin - 1 else index + shift] != role:
                # The block replaced in place re-pairs a fence its old text
                # opened or closed: the merge's own behaviour (advice-7).
                info["in-place-update-role"] = info.get("in-place-update-role", 0) + 1
                break
    if {merged_roles[begin - 1], merged_roles[end - 1]} & {"code", "opener", "closer"}:
        # A viewer reads the block as code, though Apothem reads it whole: a
        # reading limit the docs name (lazy list-item lines, HTML blocks), not
        # one of the three properties.
        info["viewer-block-in-code"] = info.get("viewer-block-in-code", 0) + 1
    if merge_managed_block(merged, "Another rule.", recorded=True) == merged:
        raise BrokenFixError(
            "update-stuck", f"{where}: the update after it leaves the file"
        )
    removed = remove_managed_block(merged)
    if whole_blocks(removed) or has_stray_begin(removed):
        raise BrokenFixError(
            "promise-remove", f"{where}: the uninstall after the update leaves markers"
        )
    _check_kept(lines, keep, split(removed)[0], f"{where}, the uninstall after it")


def _check_kept(
    lines: list[str], keep: tuple[int, int] | None, after: list[str], where: str
) -> None:
    """Check every line of the operator's outside the block is still there, in order."""
    mine = [
        line
        for index, line in enumerate(lines)
        if line.strip() and (keep is None or not keep[0] - 1 <= index < keep[1])
    ]
    left = iter(line for line in after if line.strip())
    if not all(any(line == other for other in left) for line in mine):
        raise BrokenFixError("line-gone", f"{where}: a line of yours is gone")


# -- Messages from every caller ----------------------------------------------


@dataclass
class Message:
    """One printed message, the caller that printed it, and the file it numbers."""

    caller: str
    basis: str
    text: str


def _result(path: Path, outcome: str, operation: str) -> MaterializationResult:
    return MaterializationResult(
        outcome=outcome, operation=operation, path=str(path), message=""
    )


def _put(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def messages(root: Path, text: str) -> Iterator[Message]:
    """Yield each message every caller prints for a managed-block file holding *text*."""
    target = root / "CLAUDE.md"
    for recorded in (False, True):
        merged = merge_managed_block(text, INSTALL_BODY, recorded=recorded)
        outcome = "unchanged" if merged == text else "updated"
        for dry in (False, True):
            basis = text if dry else merged
            _put(target, basis)
            for warning in stray_begin_install_warnings(
                [_result(target, outcome, "sentinel_merge")], dry_run=dry
            ):
                name = f"install(recorded={recorded}, dry_run={dry})"
                yield Message(name, basis, warning.message)
    _put(target, text)
    if markers_to_fix_at(target):
        for listed in (False, True):
            for limited in (False, True):
                note = stray_begin_note(
                    [target],
                    then="run apothem update",
                    listed=lambda _path, value=listed: value,
                    limited=lambda _path, value=limited: value,
                )
                yield Message(f"verify(listed={listed}, limited={limited})", text, note)
    for recorded in (False, True):
        refusal = sentinel_refusal(target, recorded=recorded)
        if refusal is not None:
            yield Message(f"uninstall(recorded={recorded})", text, refusal.message)
    yield from _after_strip(target, text)
    yield from _openclaw(root, target, text)
    unlisted = root / "unlisted"
    unlisted.mkdir(exist_ok=True)
    _put(unlisted / "CLAUDE.md", text)
    for warning in unlisted_block_warnings(unlisted):
        yield Message("uninstall-unlisted", text, warning.message)


def _after_strip(target: Path, text: str) -> Iterator[Message]:
    """Yield the warnings for a BEGIN marker left once Apothem's block is out."""
    stripped = remove_managed_block(text) if complete_managed_block(text) else text
    _put(target, stripped)
    for operation, why in (
        ("surgical_uninstall", None),
        (rules_file.RETIRE, RETIRED_WHY),
    ):
        results = [_result(target, "updated", operation)]
        found = (
            stray_begin_warnings(results)
            if why is None
            else stray_begin_warnings(results, why=why)
        )
        for warning in found:
            yield Message(f"stray-left({operation})", stripped, warning.message)
    _put(target, text)


def _openclaw(root: Path, target: Path, text: str) -> Iterator[Message]:
    """Yield OpenClaw's retire warnings and its size refusal for *text*."""
    unclear = unclear_block_warning(target, rules_file.RETIRE, outcome=TAKES_OUT)
    if unclear is not None:
        yield Message("openclaw-retire-unclear", text, unclear.message)
    endless = endless_block_warning(target, rules_file.RETIRE)
    if endless is not None:
        yield Message("openclaw-retire-endless", text, endless.message)
    if another_block_at(target):
        for dry in (False, True):
            another = another_block_warning(
                target, operation=rules_file.RETIRE, then=_RETRY, dry_run=dry
            )
            yield Message(
                f"openclaw-retire-another(dry_run={dry})", text, another.message
            )
            another = another_block_warning(target, dry_run=dry, then=UNINSTALL_AGAIN)
            yield Message(f"uninstall-another(dry_run={dry})", text, another.message)
    workspace = rules_file.Workspace(root / "workspace")
    workspace.rules_file.parent.mkdir(parents=True, exist_ok=True)
    _put(workspace.rules_file, text)
    config = {"agents": {"defaults": {"bootstrapMaxChars": 1}}}
    would = merge_managed_block(text, INSTALL_BODY)
    reason = rules_file.refusal(would, config, workspace)
    if reason is not None and "by adding a word" in reason:
        yield Message("openclaw-size-refusal", text, reason)


def check_message(
    message: Message, scratch: Path, info: dict[str, int], seen: set[tuple[str, str]]
) -> int:
    """Follow every fix *message* prints; return how many fixes were followed."""
    if message.caller == "openclaw-size-refusal":
        if _FORBIDDEN.search(message.text):
            raise BrokenFixError("forbidden-step", message.text)
        steps = prose_steps(message.text)
        if not any(step.kind == "change" for step in steps):
            raise BrokenFixError(
                "unparsed-step", "the size refusal names no line to change"
            )
        # The refusal names no closing sentence: its fix leaves no BEGIN
        # marker that starts no block, so the next update replaces the one
        # block left, or writes its block at the end of the file.
        fixed, _, _ = apply_steps(message.basis, steps)
        if has_stray_begin(fixed):
            raise BrokenFixError(
                "promise-refusal", "a stray BEGIN is left after the change"
            )
        promise = "keep" if whole_blocks(fixed) else "none"
        check_fix(
            message.basis, Fix("prose", "", steps), scratch, info=info, kind=promise
        )
        return 1
    fixes = parse_fixes(message.text)
    for fix in fixes:
        steps = tuple((step.kind, step.line, step.fence) for step in fix.steps)
        key = (message.basis, repr((steps, fix.case, fix.promise)))
        if key in seen:
            continue
        seen.add(key)
        check_fix(message.basis, fix, scratch, info=info)
    return len(fixes)


# -- Generated files ---------------------------------------------------------


def _fence(rng: random.Random, opener: str | None = None) -> list[str]:
    indent = " " * rng.choice([0, 0, 0, 1, 2, 3])
    mark = opener or rng.choice(["```", "~~~", "````"])
    info = rng.choice(["", "", "sh", "md", "text title"])
    lines = [f"{indent}{mark}{info}", f"code K{rng.randint(0, 99)}"]
    if rng.random() < 0.15:
        lines.append(rng.choice([B, E, "    " + B]))
    roll = rng.random()
    if roll < 0.55:
        lines.append(" " * rng.choice([0, 0, 1, 3]) + mark)
    elif roll < 0.7:
        lines.append(mark[0] * (len(mark) + 1))
    elif roll < 0.8:
        lines.append(mark[0] * max(len(mark) - 1, 1))
    return lines


def _end_marker(rng: random.Random) -> list[str]:
    roll = rng.random()
    if roll < 0.6:
        return [E]
    if roll < 0.72:
        return [" " * rng.randint(1, 3) + E]
    if roll < 0.82:
        return [f"{E} trailing text"]
    if roll < 0.88:
        return ["    " + E]
    return []


def _pair(rng: random.Random) -> list[str]:
    lines = [" " * rng.choice([0, 0, 0, 1, 3]) + B]
    for _ in range(rng.randint(0, 3)):
        roll = rng.random()
        if roll < 0.5:
            lines.append(f"rule K{rng.randint(0, 99)}")
        elif roll < 0.8:
            lines.extend(_fence(rng))
        else:
            lines.append(rng.choice(["", "- rule item", "# Rule head", "---"]))
    return lines + _end_marker(rng)


_ITEMS: tuple[Callable[[random.Random], list[str]], ...] = (
    lambda rng: [f"text K{rng.randint(0, 99)}"],
    lambda rng: [f"text K{rng.randint(0, 99)}", "more text"],
    lambda rng: [f"# Head K{rng.randint(0, 99)}"],
    lambda rng: [f"Title K{rng.randint(0, 99)}", rng.choice(["===", "---"])],
    lambda rng: [rng.choice(["---", "***", "___"])],
    lambda rng: (
        [f"- item K{rng.randint(0, 99)}", *rng.choice([[], ["  more"], ["lazy"]])]
    ),
    lambda rng: [f"{rng.choice(['1.', '2)'])} item K{rng.randint(0, 99)}"],
    lambda rng: [f"    code K{rng.randint(0, 99)}"],
    _fence,
    _fence,
    lambda rng: rng.choice(
        [
            ["<div>", "html K", "</div>"],
            ["<!-- note -->"],
            ["<!-- draft"],
            ["-->"],
            ["<pre>", "pre K", "</pre>"],
            ["<pre>"],
            ["<?x", "?>"],
            ["<my-tag>"],
        ]
    ),
    lambda rng: [""],
    lambda rng: [""],
    _pair,
    _pair,
    lambda rng: [" " * rng.choice([0, 1, 2]) + B, f"old K{rng.randint(0, 99)}"],
    lambda rng: [E],
    lambda rng: [B, "rule one", E],
)


def generate(rng: random.Random) -> str:
    """Return a random file with marker lines in it."""
    lines: list[str] = []
    for _ in range(rng.randint(2, 9)):
        lines.extend(rng.choice(_ITEMS)(rng))
    for _ in range(rng.randint(1, 3)):
        at = rng.randint(0, len(lines))
        lines[at:at] = rng.choice([_pair(rng), [B, "rule one", E], [B]])
    return join(lines, rng.random() < 0.85)


#: Text of the operator's with no marker line, in the shapes a long file holds
#: between its marker problems: paragraphs, headings, tight and loose lists,
#: list items holding a code block, closed code blocks at the margin and
#: indented, HTML blocks and quotes.
_FILLER_ITEMS: tuple[Callable[[random.Random], list[str]], ...] = (
    lambda rng: [f"A line of mine K{rng.randint(0, 99)}.", "", ""][: rng.randint(1, 2)],
    lambda rng: [f"## Notes K{rng.randint(0, 99)}", ""],
    lambda rng: ["- first", "- second", *rng.choice([[], [""], ["  lazy"]])],
    lambda rng: ["1. step", "   ```sh", "   run", "   ```", ""],
    lambda rng: ["```py", "print(1)", "", "x = 2", "```"],
    lambda rng: ["", "~~~text", "plain", "~~~", ""],
    lambda rng: ["  ````md", "  ```", "  inner", "  ```", "  ````"],
    lambda rng: ["", "    indented code", ""],
    lambda rng: ["<div>", "some html", "</div>", ""],
    lambda rng: ["> a quote", "> more", ""],
    lambda rng: ["Title", "-----", ""],
)


def generate_long(rng: random.Random) -> str:
    """Return a file of a few hundred lines: generated parts with text between.

    The marker reading passes over lines that can leave no lasting state,
    and how often it tries to depends on how many lines need reading, so
    these files put the marker problems far apart in long runs of plain
    text, lists and code.
    """
    lines: list[str] = []
    for _ in range(rng.randint(2, 5)):
        for _ in range(rng.randint(5, 60)):
            lines.extend(rng.choice(_FILLER_ITEMS)(rng))
        part = generate(rng)
        lines.extend(split(part)[0])
    if rng.random() < 0.5:
        for _ in range(rng.randint(5, 60)):
            lines.extend(rng.choice(_FILLER_ITEMS)(rng))
    return join(lines, rng.random() < 0.85)


BLOCK = [B, "rule one", E]

#: The shapes the reviewers named (sA2, plain, sF, sE-b), and the ones from
#: the round 6a findings.
SHAPES = {
    "sA2": [
        "My notes:",
        "```",
        "make test",
        "",
        *BLOCK,
        "```",
        "my text KEEP1",
        "```sh",
        "ls KEEP2",
        "```",
        "my tail KEEP3",
    ],
    "plain": ["My notes:", "```", "make test", "", *BLOCK, "```", "my text KEEP1"],
    "sF": [
        "# mine KEEP0",
        B,
        "old rule",
        "```",
        "old code",
        *BLOCK,
        "```",
        "tail KEEP1",
        "KEEP2",
    ],
    "sE-b": [
        "# mine KEEP0",
        B,
        "old rule text",
        "Run:",
        "```sh",
        "npm test",
        E,
        "```",
        "my text KEEP1",
        "Example KEEP2:",
        B,
        "example body KEEPX",
        E,
    ],
    "reopen": [
        "My notes:",
        "```",
        "make test",
        B,
        "rule",
        "```",
        "old cmd",
        E,
        "tail text KEEP1",
        "",
        "more KEEP3",
    ],
    "tilde-open": [
        "My notes:",
        "~~~",
        "make test KEEP0",
        "",
        *BLOCK,
        "",
        "tail KEEP1",
        B,
    ],
    "four-open": ["   ````", "   ````", " ````", "  " + B, E, B],
    "list-fence": ["2) item", "prose", "   `````text title", B, E, " `````"],
    "html-end": ["<!-- END APOTHEM MANAGED BLOCK", "~~~md", B],
    "hr-below": ["Intro text KEEP1", B, "rule", E, "---", "more KEEP2"],
    "open-comment": ["notes", "<!-- draft", B, "rule", E, "", "tail KEEP1"],
    "two-indented": [
        "  " + B,
        "rule K1",
        E,
        "",
        " " + B,
        "rule K2",
        "   " + E,
        "",
        "  " + B,
    ],
    # Two whole blocks, each followed by a "---" line, then a BEGIN marker:
    # the text after the first block reads as YAML frontmatter.
    "strip-loop": [B, "r", E, "---", B, "r", E, "---", B],
}


def _files_wanted() -> int:
    return int(os.environ.get("APOTHEM_ADVICE_PROPERTY_FILES", "640"))


#: Generated files are split over this many test cases, so xdist spreads them.
_CHUNKS = 32


@dataclass
class Tally:
    """What one run checked."""

    files: int = 0
    messages: int = 0
    fixes: int = 0
    callers: dict[str, int] = field(default_factory=dict)
    info: dict[str, int] = field(default_factory=dict)
    failures: list[tuple[Message, BrokenFixError]] = field(default_factory=list)


def run_files(root: Path, texts: list[str]) -> Tally:
    """Check every message for each of *texts*."""
    tally = Tally()
    seen: set[tuple[str, str]] = set()
    scratch = root / "followed" / "CLAUDE.md"
    scratch.parent.mkdir(exist_ok=True)
    for text in texts:
        tally.files += 1
        try:
            # Every caller below strips the file or its merge; one whose strip
            # never returns would hang them.
            for recorded in (False, True):
                remove_managed_block(text)
                remove_managed_block(
                    merge_managed_block(text, INSTALL_BODY, recorded=recorded)
                )
        except BrokenFixError as broken:
            note = "(no message: the uninstall's strip of this file never returns)"
            tally.failures.append((Message("uninstall", text, note), broken))
            continue
        for message in messages(root, text):
            tally.messages += 1
            caller = message.caller.split("(")[0]
            tally.callers[caller] = tally.callers.get(caller, 0) + 1
            try:
                tally.fixes += check_message(message, scratch, tally.info, seen)
            except BrokenFixError as broken:
                tally.failures.append((message, broken))
    return tally


def _report(tally: Tally) -> str:
    """Return each class of break once, with its smallest file and its message."""
    smallest: dict[str, tuple[Message, BrokenFixError]] = {}
    callers: dict[str, set[str]] = {}
    for message, broken in tally.failures:
        callers.setdefault(broken.kind, set()).add(message.caller)
        best = smallest.get(broken.kind)
        if best is None or len(message.basis) < len(best[0].basis):
            smallest[broken.kind] = (message, broken)
    parts = [
        f"{len(tally.failures)} broken fixes in {tally.messages} messages "
        f"({tally.files} files)"
    ]
    for kind, (message, broken) in sorted(smallest.items()):
        count = sum(1 for _, other in tally.failures if other.kind == kind)
        parts.append(
            f"\n== {kind} x{count} from {sorted(callers[kind])}\n"
            f"caller: {message.caller}\nfile: {message.basis!r}\n"
            f"problem: {broken.problem}\nmessage: {message.text}"
        )
    return "".join(parts)


def _save(tally: Tally, name: str) -> None:
    """Write *tally* as JSON under ``APOTHEM_ADVICE_PROPERTY_REPORT``, when it is set."""
    folder = os.environ.get("APOTHEM_ADVICE_PROPERTY_REPORT")
    if not folder:
        return
    found = [
        {
            "caller": message.caller,
            "kind": broken.kind,
            "file_text": message.basis,
            "message": message.text,
            "problem": broken.problem,
        }
        for message, broken in tally.failures
    ]
    record = {
        "files": tally.files,
        "messages": tally.messages,
        "fixes": tally.fixes,
        "callers": tally.callers,
        "info": tally.info,
        "failures": found,
    }
    Path(folder).mkdir(parents=True, exist_ok=True)
    (Path(folder) / f"{name}.json").write_text(json.dumps(record), encoding="utf-8")


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_every_fix_for_a_named_shape_holds(tmp_path: Path, name: str) -> None:
    tally = run_files(tmp_path, [join(SHAPES[name], True)])
    _save(tally, f"shape-{name}")
    assert not tally.failures, _report(tally)


@pytest.mark.parametrize("chunk", range(_CHUNKS))
def test_every_fix_for_generated_files_holds(tmp_path: Path, chunk: int) -> None:
    wanted = _files_wanted()
    rng = random.Random(f"apothem-advice-{chunk}")  # noqa: S311 - seeded test input
    texts = [generate(rng) for _ in range(chunk, wanted, _CHUNKS)]
    tally = run_files(tmp_path, texts)
    _save(tally, f"chunk-{chunk}")
    assert tally.messages > 0
    assert not tally.failures, _report(tally)


#: Long generated files are split over this many test cases.
_LONG_CHUNKS = 8


@pytest.mark.parametrize("chunk", range(_LONG_CHUNKS))
def test_every_fix_for_long_generated_files_holds(tmp_path: Path, chunk: int) -> None:
    wanted = max(_files_wanted() // 20, _LONG_CHUNKS)
    rng = random.Random(f"apothem-advice-long-{chunk}")  # noqa: S311 - seeded test input
    texts = [generate_long(rng) for _ in range(chunk, wanted, _LONG_CHUNKS)]
    tally = run_files(tmp_path, texts)
    _save(tally, f"long-{chunk}")
    assert tally.messages > 0
    assert not tally.failures, _report(tally)


def test_the_uninstall_summary_names_no_line_edit() -> None:
    """The summary lines point at the warnings' fixes and give no edit of their own."""
    summaries = [
        value
        for value in vars(_cmd_uninstall).values()
        if isinstance(value, str) and "marker" in value
    ]
    assert summaries
    for text in summaries:
        assert not _FORBIDDEN.search(text), text
        assert not _NUMBER.search(text), text


# -- Timing ------------------------------------------------------------------

#: A paragraph, a list and a closed code block, about 100 bytes.
_FILLER = (
    "Some text of mine about the project, with a few words.\n\n- item one\n"
    "- item two\n\n```sh\nmake test\n```\n\n"
)


def _large(shape: str) -> str:
    """Return a file of about 1 MB with several marker problems."""
    part = _FILLER * (250_000 // len(_FILLER))
    quoted = f"```md\n{B}\nexample\n{E}\n```\n\n"
    return {
        "two-blocks-and-stray": (
            f"{part}{B}\nold\n\n{part}{quoted}{B}\nrule\n{E}\n\n{part}"
            f"{B}\nother\n{E}\n\n{part}{B}\nlast\n"
        ),
        "unclear-and-lone": (
            f"{part}```\n{B}\nrule\n{E}\n```\n\n{part}{B}\nold\n\n{part}"
            f"```md\n{B}\nex\n{E}\n```\n\n{part}"
        ),
        "endless-in-list": f"{part}{part}{quoted}{part}- item\n  ```\n  code\n{part}{B}\nold\n",
    }[shape]


#: The most one message, or one command's reading of the file, may take for
#: a 1 MB file, in seconds. On main a command's reading of such a file takes a
#: few milliseconds (merge about 1 ms, the uninstall's strip about 3 ms, its
#: check 2 to 7 ms), so this leaves a wide margin for a slow runner and still
#: fails a reading that walks the whole file line by line.
_BOUND = 0.5


def _timer(
    tmp_path: Path, text: str
) -> tuple[Path, Path, Callable[[Callable[[str], object]], float]]:
    """Return the file, the unlisted folder, and a timer for builds on *text*.

    Each timed run writes a text no earlier run read (its first line
    differs), as a fresh command reads it, so a reading kept from an earlier
    run cannot hide the cost. A run under the bound counts, so a pause
    elsewhere does not fail the test; at most three runs are timed.
    """
    target = tmp_path / "CLAUDE.md"
    unlisted = tmp_path / "unlisted"
    unlisted.mkdir()
    runs = iter(range(1_000))

    def fresh() -> str:
        variant = f"Run {next(runs)} of my notes.\n\n{text}"
        _put(target, variant)
        _put(unlisted / "CLAUDE.md", variant)
        return variant

    def timed(build: Callable[[str], object]) -> float:
        took = []
        for _ in range(3):
            variant = fresh()
            start = time.perf_counter()
            build(variant)
            took.append(time.perf_counter() - start)
            if took[-1] < _BOUND:
                break
        return round(min(took), 3)

    return target, unlisted, timed


@pytest.mark.parametrize(
    "shape", ["two-blocks-and-stray", "unclear-and-lone", "endless-in-list"]
)
def test_the_advice_for_a_1_mb_file_is_built_well_under_a_second(
    tmp_path: Path, shape: str
) -> None:
    """lifecycle-r6-1, advice-3: one warning took 17 to 50 s on a 1 MB file.

    Each caller's message is timed through its public function, file read
    included, as a run builds it: the install warning, the uninstall's
    refusal with and without a record, the verify note and the warning for
    a file no record lists.
    """
    text = _large(shape)
    assert len(text) > 900_000
    target, unlisted, timed = _timer(tmp_path, text)

    def built(build: Callable[[], object]) -> Callable[[str], object]:
        def run(_variant: str) -> object:
            found = build()
            assert found, "the file has marker problems, so a message is printed"
            return found

        return run

    builds = {
        "install": built(
            lambda: stray_begin_install_warnings(
                [_result(target, "unchanged", "sentinel_merge")]
            )
        ),
        "uninstall-recorded": built(lambda: sentinel_refusal(target, recorded=True)),
        "uninstall": built(lambda: sentinel_refusal(target)),
        "verify": built(lambda: stray_begin_note([target], then="run apothem update")),
        "unlisted": built(lambda: unlisted_block_warnings(unlisted)),
    }
    took = {name: timed(build) for name, build in builds.items()}
    reading = timed(materializer.whole_blocks)
    slow = {name: seconds for name, seconds in took.items() if seconds >= _BOUND}
    assert not slow, f"seconds per message: {took}; one whole_blocks read: {reading}"


@pytest.mark.parametrize("where", ["end", "top"])
def test_a_command_on_a_1_mb_file_with_one_block_reads_it_as_fast_as_on_main(
    tmp_path: Path, where: str
) -> None:
    """lifecycle-r6-1: the marker checks must not slow every command down.

    The file holds one whole block and no marker problem, as a normal
    install leaves it. Each command's reading of the file is timed through
    the public functions it uses: the update's merge and its check for
    marker warnings, verify's check, the uninstall's check and strip, and
    the check for a block no record lists.
    """
    part = _FILLER * (1_000_000 // len(_FILLER))
    block = f"{B}\nApothem rule.\n{E}\n"
    text = f"{part}{block}" if where == "end" else f"{block}\n{part}"
    target, unlisted, timed = _timer(tmp_path, text)

    def update(variant: str) -> None:
        merged = merge_managed_block(variant, INSTALL_BODY, recorded=True)
        _put(target, merged)
        warnings = stray_begin_install_warnings(
            [_result(target, "updated", "sentinel_merge")]
        )
        assert not warnings

    def uninstall(variant: str) -> None:
        assert sentinel_refusal(target, recorded=True) is None
        assert B not in materializer.remove_managed_block(variant)

    commands: dict[str, Callable[[str], object]] = {
        "update": update,
        "verify": lambda _variant: markers_to_fix_at(target),
        "uninstall": uninstall,
        "unlisted": lambda _variant: unlisted_block_warnings(unlisted),
    }
    took = {name: timed(command) for name, command in commands.items()}
    parts = {
        "merge": timed(
            lambda variant: materializer.merge_managed_block(
                variant, INSTALL_BODY, recorded=True
            )
        ),
        "strip": timed(materializer.remove_managed_block),
    }
    slow = {name: seconds for name, seconds in took.items() if seconds >= _BOUND}
    assert not slow, f"seconds per command: {took}; of which {parts}"


# -- The reader itself -------------------------------------------------------


def test_the_reader_flags_a_step_it_cannot_read() -> None:
    with pytest.raises(BrokenFixError, match="unparsed-step"):
        parse_fixes("Fix A: A1. Change line 3: add a word. Done.")
    with pytest.raises(BrokenFixError, match="forbidden-step"):
        parse_fixes("Fix A: A1. Move line 6 to just above line 4. Done.")
    with pytest.raises(BrokenFixError, match="unparsed-step"):
        parse_fixes("Something B2. Change line 3: add a word inside its comment.")


def test_the_reader_reads_both_step_kinds_and_the_promise() -> None:
    [fix] = parse_fixes(
        "Fix A, if lines 3 to 5 are text of yours: A1. Below line 6, add a line of "
        "4 tildes, indented 2 spaces. A2. Change line 3: add a word inside its "
        "comment. The next update then adds Apothem's block to the file. More."
    )
    assert fix.steps == [Step("close", 6, "  ~~~~"), Step("change", 3)]
    assert fix.promise == "The next update then adds Apothem's block to the file."


def test_the_reader_reads_the_size_refusal_steps() -> None:
    text = (
        "it counts against the limit: add a line of 4 backticks below line 6, "
        "change lines 1, 4 and 5 by adding a word inside each comment, and delete "
        "that old text by hand"
    )
    assert prose_steps(text) == [
        Step("close", 6, "````"),
        Step("change", 5),
        Step("change", 4),
        Step("change", 1),
    ]
    assert prose_steps("change line 2 by adding a word inside its comment") == [
        Step("change", 2)
    ]
    with pytest.raises(BrokenFixError, match="unparsed-step"):
        prose_steps("add a line of fences below line 3, change line 2 by adding")


def test_the_role_reader_tells_each_role_apart() -> None:
    text = join(
        ["# h", "t", "", "---", "<div>", "</div>", "", "    c", "", "```", "x", "```"],
        True,
    )
    assert roles(text) == [
        "heading",
        "text",
        "blank",
        "hr",
        "html",
        "html",
        "blank",
        "code",
        "blank",
        "opener",
        "code",
        "closer",
    ]
    assert roles("~~~\nx\n")[-1] == "code"


def test_the_checker_catches_a_promise_that_does_not_hold(tmp_path: Path) -> None:
    basis = join([B, "rule K1", E, B, "rule K2", E], True)
    scratch = tmp_path / "CLAUDE.md"
    holds = parse_fixes(
        "Fix A: A1. Change line 1: add a word inside its comment. Lines 4 to 6 "
        "are then the one block in the file."
    )
    check_fix(basis, holds[0], scratch, info={})
    wrong = parse_fixes(
        "Fix A: A1. Change line 1: add a word inside its comment. Lines 1 to 3 "
        "are then the one block in the file."
    )
    with pytest.raises(BrokenFixError, match="promise-block"):
        check_fix(basis, wrong[0], scratch, info={})
    with pytest.raises(BrokenFixError, match="not-a-marker"):
        check_fix(
            basis,
            parse_fixes("Fix A: A1. Change line 2: add a word inside its comment. X.")[
                0
            ],
            scratch,
            info={},
        )


def test_the_checker_catches_a_line_that_reads_differently(tmp_path: Path) -> None:
    """A closing line added where no code block is open opens one."""
    basis = join(["text", B, "rule"], True)
    fix = parse_fixes(
        "Fix A: A1. Below line 3, add a line of 3 backticks. A2. Change line 2: add "
        "a word inside its comment. Apothem then finds no block of its own in this "
        "file."
    )[0]
    with pytest.raises(BrokenFixError, match="close-reads-opener"):
        check_fix(basis, fix, tmp_path / "CLAUDE.md", info={})
