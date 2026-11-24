# SPDX-License-Identifier: MIT

"""Every numbered fix Apothem prints for its marker lines, followed literally.

A property test, written apart from the code that builds the fixes. It makes
Markdown files from a fixed seed (prose, blank lines, backtick and tilde code
blocks at indent 0 to 3 with and without an info string, list items, indented
code, one to three marker pairs, BEGIN markers that start no pair, marker
lines anywhere, a BEGIN marker above a block with an END marker below it)
plus six fixed shapes. For each file it asks every caller
for its warning, through the functions those callers use and with what they
pass: the install and update warning (the file written or left as it is, a
dry run too, with and without an install record), the verify and doctor
note, the uninstall's warnings (with and without a record, and the warning
for a file no record lists) and the OpenClaw rules-file retire.

Each message is read with this file's own patterns, written from the step
formats on the troubleshooting page (``site/content/docs/install/
troubleshooting.mdx``, "Follow a numbered fix"); no class, pattern or check
of the renderer is used. A numbered step those patterns cannot read fails.
Each fix's steps are then applied in the order printed, each line number
taken as it stands, to a copy of the file, and the test holds that:

0. reading each line number as the line's number before any step gives the
   same file (the message says no step moves a line a later step names);
1. the fix's promise holds: the file holds exactly the block the fix calls
   Apothem's (or none); the next update (``merge_managed_block``, with and
   without a record, for each rule body in :data:`BODIES`) gives exactly one
   whole block; the next uninstall (``remove_managed_block``) leaves none,
   and no line of the operator's. A fix that says its block is then the one
   block in the file is held to the next update as well as the uninstall;
2. every line of the operator's that is left reads in a CommonMark viewer
   (markdown-it) as it did before: as text, as code, or as the line that
   opens or closes a code block (blank lines have no role; the lines of the
   block the fix calls Apothem's, and the lines its steps name, are not the
   operator's), after the steps and after the uninstall;
3. no line outside a range a step deletes is gone.

A message with no numbered fix (the fallback) is held to its own promise:
change every marker line, and the next update gives one whole block.

``APOTHEM_ADVICE_PROPERTY_FILES`` sets how many random files to make (default
:data:`DEFAULT_FILES`). ``APOTHEM_ADVICE_PROPERTY_REPORT`` names a file each
shard appends its counts to, as one JSON line.
"""

from __future__ import annotations

import json
import os
import random
import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pytest
from markdown_it import MarkdownIt

from apothem.cli._stray_begin_report import stray_begin_note
from apothem.harnesses._shared.install_driver_blocks import (
    UNINSTALL_AGAIN,
    _install_warning,
    another_block_at,
    another_block_warning,
    endless_block_warning,
    markers_to_fix_at,
    sentinel_refusal,
    unclear_block_warning,
)
from apothem.harnesses._shared.install_driver_blocktext import TAKES_OUT
from apothem.harnesses._shared.install_driver_retention import unlisted_block_warnings
from apothem.harnesses.open_claw.rules_file import _RETRIED, RETIRE
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    has_stray_begin,
    merge_managed_block,
    remove_managed_block,
    uncertain_pairs,
    whole_blocks,
)

B, E = APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END
MARKERS = frozenset({B, E})

#: Random files made when ``APOTHEM_ADVICE_PROPERTY_FILES`` is not set.
DEFAULT_FILES = 1000
#: The test runs in this many parts, so pytest-xdist can spread them.
SHARDS = 8
SEED = 20261124
#: Every caller whose advice a shard must see at least once.
CALLERS = frozenset({"install/update", "verify/doctor", "uninstall", "openclaw retire"})

#: Bodies the next update writes: plain, a closed code block, and a rule
#: that opens a code block and never closes it (the merge closes it).
BODIES = (
    "Apothem probe rule.",
    "Run:\n```sh\nnpm test\n```",
    "Run:\n```sh\nnpm test",
)

_BLOCK = [B, "rule one", "rule two", E]

#: The shapes the reviewer named (see the PR #244 round-5 findings), and
#: "revealed": a block whose rule leaves a code block open, inside a code
#: block of the operator's that no line closes, with a BEGIN marker above it
#: and an END marker below it that make another block once it is out.
SHAPES: dict[str, list[str]] = {
    # The 32,000-file pass found this one: deleting the one whole block (a
    # list item's BEGIN marker, an END marker at the margin), as the
    # uninstall's text for a file no record lists once said in prose, lets
    # the list item take the operator's code block, and the pair quoted in
    # it then reads as a whole block.
    "unlisted": ["- item KEEP1", f"  {B}", E, "   ~~~md", B, E, "   ~~~~"],
    "revealed": ["```md", "code KEEP", B, B, "Run:", "~~~", "npm test", E, "", "", E],
    "sA2": [
        "My notes:",
        "```",
        "make test",
        "",
        *_BLOCK,
        "```",
        "my text KEEP1",
        "```sh",
        "ls KEEP2",
        "```",
        "my tail KEEP3",
    ],
    "plain": [
        "My notes:",
        "```",
        "make test",
        "",
        *_BLOCK,
        "```",
        "my text KEEP1",
        "my tail KEEP3",
    ],
    "sF": [
        "# mine KEEP0",
        B,
        "old rule",
        "```",
        "old code",
        *_BLOCK,
        "```",
        "tail KEEP1",
        "KEEP2",
        "KEEP3",
        "KEEP4",
        "KEEP5",
        "KEEP6",
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
}

# --- reading a message ---------------------------------------------------------

_FIX_HEAD = re.compile(
    r"Fix (?P<letter>[A-Z]{1,2}), if (?:lines (?P<first>\d+) to (?P<last>\d+) "
    r"are (?P<case>Apothem's block|text of yours)|none of these pairs is "
    r"Apothem's block):"
)
_LABEL = re.compile(r"(?<![\w.])([A-Z]{1,2})(\d+)\.(?=\s)")
_STEPS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("change", re.compile(r"Change line (\d+): add a word inside its comment\.")),
    ("copy", re.compile(r"(Above|Below) line (\d+), add a copy of line (\d+)\.")),
    (
        "fence",
        re.compile(
            r"(Above|Below) line (\d+), add a line of (\d+) (backticks|tildes)"
            r"(?:, indented (\d+) spaces?)?\."
        ),
    ),
    ("move", re.compile(r"Move line (\d+) to just above line (\d+)\.")),
    ("delete", re.compile(r"Delete lines (\d+) to (\d+)\.")),
)
_PROMISES: tuple[tuple[re.Pattern[str], bool], ...] = (
    (re.compile(r"The next update then replaces Apothem's block\."), True),
    (re.compile(r"The next update then adds Apothem's block to the file\."), False),
    (re.compile(r"Lines (\d+) to (\d+) are then the one block in the file\."), True),
    (
        re.compile(
            r"The next install, update or uninstall then takes Apothem's block out\."
        ),
        True,
    ),
    (re.compile(r"No Apothem block is then left in this file\."), False),
    (re.compile(r"The uninstall run again then takes Apothem's block out\."), True),
    (
        re.compile(
            r"The uninstall run again then finds no Apothem block in this file\."
        ),
        False,
    ),
)
_FALLBACK = "Apothem has no step-by-step fix it could check for this file"
_FALLBACK_PROMISE = re.compile(
    r"(The next update then adds Apothem's block to the file|No Apothem block "
    r"is then left in this file|The uninstall run again then finds no Apothem "
    r"block in this file); old Apothem text between those lines is yours to "
    r"delete\."
)
#: A sentence outside the numbered steps that tells the operator to edit a
#: numbered line: every such edit must be a numbered step.
_EDIT_VERB = re.compile(r"\b(delete|move|add|change|remove|close|cut)\b", re.I)
_LINE_NUMBER = re.compile(r"\blines? \d+")


@dataclass(frozen=True)
class Step:
    """One step read from a message: its kind and the numbers and text it names."""

    kind: str
    numbers: tuple[int, ...]
    text: str = ""


@dataclass
class Fix:
    """One fix read from a message."""

    letter: str
    block: tuple[int, int] | None
    steps: list[Step]
    keeps: bool | None
    promise_block: tuple[int, int] | None = None


class UnreadableError(Exception):
    """A message part this test's patterns cannot read."""


def _read_step(kind: str, match: re.Match[str]) -> Step:
    """Return the step *match* of *kind* reads."""
    groups = match.groups()
    if kind == "change":
        return Step(kind, (int(groups[0]),))
    if kind == "copy":
        return Step(kind, (int(groups[1]), int(groups[2])), groups[0])
    if kind == "fence":
        count, indent = int(groups[2]), int(groups[4] or 0)
        char = "`" if groups[3] == "backticks" else "~"
        return Step(
            kind, (int(groups[1]),), f"{groups[0]}|{' ' * indent}{char * count}"
        )
    return Step(kind, (int(groups[0]), int(groups[1])))


def read_fixes(message: str) -> list[Fix]:
    """Return the fixes *message* gives, each with its steps in printed order.

    Raises :class:`UnreadableError` when a numbered step or a promise does not
    read as one of the documented formats, or a step label is left over.
    """
    heads = list(_FIX_HEAD.finditer(message))
    fixes: list[Fix] = []
    parsed_labels = 0
    for index, head in enumerate(heads):
        stop = heads[index + 1].start() if index + 1 < len(heads) else len(message)
        part = message[head.end() : stop]
        letter = head["letter"]
        block = (
            (int(head["first"]), int(head["last"]))
            if head["case"] == "Apothem's block"
            else None
        )
        steps: list[Step] = []
        rest = part.lstrip()
        number = 1
        while True:
            label = re.match(rf"{letter}{number}\.\s+", rest)
            if label is None:
                break
            rest = rest[label.end() :]
            for kind, pattern in _STEPS:
                found = pattern.match(rest)
                if found is not None:
                    steps.append(_read_step(kind, found))
                    rest = rest[found.end() :].lstrip()
                    break
            else:
                raise UnreadableError(f"step {letter}{number}: {rest[:120]!r}")
            parsed_labels += 1
            number += 1
        keeps: bool | None = None
        promise_block = None
        for pattern, kept in _PROMISES:
            found = pattern.match(rest)
            if found is not None:
                keeps = kept
                if found.groups():
                    promise_block = (int(found[1]), int(found[2]))
                break
        if keeps is None:
            raise UnreadableError(f"promise of fix {letter}: {rest[:120]!r}")
        fixes.append(Fix(letter, block, steps, keeps, promise_block))
    labels = len(_LABEL.findall(message))
    if labels != parsed_labels:
        raise UnreadableError(f"{labels - parsed_labels} step label(s) read as no step")
    return fixes


def _outside_steps(message: str) -> str:
    """Return *message* with each fix's head and numbered steps cut out."""
    cut = _FIX_HEAD.sub(" ", message)
    for _, pattern in _STEPS:
        cut = pattern.sub(" ", cut)
    return _LABEL.sub(" ", cut)


def stray_edits(message: str) -> list[str]:
    """Return each sentence outside the steps that edits a numbered line.

    A sentence that says what not to do ("Do not delete ...") is no edit.
    """
    found = []
    for sentence in re.split(r"(?<=[.;:])\s+", _outside_steps(message)):
        if sentence.lstrip().startswith(("Do not", "do not")):
            continue
        if _EDIT_VERB.search(sentence) and _LINE_NUMBER.search(sentence):
            found.append(sentence.strip())
    return found


# --- applying steps and reading roles ------------------------------------------

_MD = MarkdownIt("commonmark")


def roles(lines: Sequence[str]) -> list[str | None]:
    """Return how a CommonMark viewer reads each line of *lines*.

    ``None`` for a blank line, ``"code"`` for a line in a code block,
    ``"opener"`` and ``"closer"`` for the lines that open and close a fenced
    one, ``"text"`` for every other line. A fence is closed when its content
    holds every line between its first and last line (an unclosed fence runs
    to the end of the text and holds its last line too).
    """
    text = "".join(f"{line}\n" for line in lines)
    out: list[str | None] = [None if not line.strip() else "text" for line in lines]
    for token in _MD.parse(text):
        if token.map is None or token.type not in {"fence", "code_block"}:
            continue
        first, stop = token.map
        for index in range(first, min(stop, len(lines))):
            if lines[index].strip():
                out[index] = "code"
        if token.type == "fence":
            out[first] = "opener"
            if stop - first >= 2 and token.content.count("\n") == stop - first - 2:
                out[stop - 1] = "closer"
    return out


def reword(line: str) -> str:
    """Return the marker *line* with a word added inside its comment."""
    cut = line.rfind("-->")
    return f"{line[:cut].rstrip()} (kept) {line[cut:]}"


@dataclass
class Applied:
    """A file after a fix's steps: its lines, and each line's first number."""

    lines: list[str]
    tags: list[int | None]
    named: set[int] = field(default_factory=set)
    deleted: set[int] = field(default_factory=set)


def apply_steps(lines: Sequence[str], steps: Sequence[Step]) -> Applied:
    """Apply *steps* in order, each number the line at that place now.

    Raises :class:`UnreadableError` for a step that names a line that is not
    there, a move down, a backwards range, or a change of a line that is not
    a marker line.
    """
    done = Applied(list(lines), list(range(len(lines))))
    texts, tags = done.lines, done.tags

    def at(number: int) -> int:
        if not 0 < number <= len(texts):
            raise UnreadableError(
                f"line {number} is not in a file of {len(texts)} lines"
            )
        return number - 1

    for step in steps:
        if step.kind == "change":
            here = at(step.numbers[0])
            if texts[here].strip() not in MARKERS:
                raise UnreadableError(f"line {step.numbers[0]} is not a marker line")
            texts[here] = reword(texts[here])
            tag = tags[here]
            if tag is not None:
                done.named.add(tag)
        elif step.kind == "delete":
            first, last = at(step.numbers[0]), at(step.numbers[1])
            if last < first:
                raise UnreadableError(f"range {step.numbers} runs backwards")
            gone = {tag for tag in tags[first : last + 1] if tag is not None}
            done.deleted |= gone
            done.named |= gone
            del texts[first : last + 1], tags[first : last + 1]
        elif step.kind == "move":
            here, target = at(step.numbers[0]), at(step.numbers[1])
            if target >= here:
                raise UnreadableError(f"move {step.numbers} does not go up")
            tag = tags[here]
            if tag is not None:
                done.named.add(tag)
            texts.insert(target, texts.pop(here))
            tags.insert(target, tags.pop(here))
        else:
            here = at(step.numbers[0])
            if step.kind == "copy":
                where = step.text
                added = texts[at(step.numbers[1])]
            else:
                where, added = step.text.split("|", 1)
            spot = here + 1 if where == "Below" else here
            texts.insert(spot, added)
            tags.insert(spot, None)
    return done


def apply_in_original(lines: Sequence[str], steps: Sequence[Step]) -> list[str]:
    """Apply *steps* in order, each number the line's number before any step.

    The other way to read the numbers: the message says no step moves a line
    that a later step names, so both ways must give the same file. Raises
    :class:`UnreadableError` for a step that names a line an earlier step
    deleted.
    """
    texts = list(lines)
    tags: list[int | None] = list(range(len(lines)))

    def at(number: int) -> int:
        if number - 1 not in tags:
            raise UnreadableError(f"line {number} is gone by then")
        return tags.index(number - 1)

    for step in steps:
        if step.kind == "change":
            here = at(step.numbers[0])
            texts[here] = reword(texts[here])
        elif step.kind == "delete":
            first, last = at(step.numbers[0]), at(step.numbers[1])
            del texts[first : last + 1], tags[first : last + 1]
        elif step.kind == "move":
            here, target = at(step.numbers[0]), at(step.numbers[1])
            text, tag = texts.pop(here), tags.pop(here)
            target = target if target < here else target - 1
            texts.insert(target, text)
            tags.insert(target, tag)
        else:
            here = at(step.numbers[0])
            if step.kind == "copy":
                where, added = step.text, texts[at(step.numbers[1])]
            else:
                where, added = step.text.split("|", 1)
            spot = here + 1 if where == "Below" else here
            texts.insert(spot, added)
            tags.insert(spot, None)
    return texts


# --- the checks ----------------------------------------------------------------


@dataclass
class Tally:
    """What one run saw: messages, fallbacks, and violations by class."""

    files: int = 0
    messages: int = 0
    advice: int = 0
    fallback: int = 0
    numbered: int = 0
    prose_only: int = 0
    callers: dict[str, int] = field(default_factory=dict)
    violations: dict[str, dict[str, str]] = field(default_factory=dict)

    def flag(
        self, caller: str, kind: str, text: str, message: str, problem: str
    ) -> None:
        """Keep the shortest file for each kind of violation and caller."""
        key = f"{kind} | {caller.split(' (')[0]}"
        known = self.violations.get(key)
        if known is None or len(text) < len(known["file_text"]):
            self.violations[key] = {
                "caller": caller,
                "kind": kind,
                "file_text": text,
                "message": message,
                "problem": problem,
            }


def _joined(lines: Sequence[str]) -> str:
    return "".join(f"{line}\n" for line in lines)


def _state(text: str) -> tuple[list[tuple[int, int]], bool, bool]:
    return whole_blocks(text), has_stray_begin(text), bool(uncertain_pairs(text))


@lru_cache(maxsize=65536)
def _next_runs(fixed: str, *, removes: bool) -> str | None:
    """Return what is wrong with the run a fix promises, on *fixed*.

    For an update (with and without an install record): exactly one whole
    block, no BEGIN marker that starts none and no unplaced pair, and an
    uninstall after it leaves no block. With *removes*, an uninstall of
    *fixed* leaves no block, no such BEGIN marker and no unplaced pair.
    """
    if removes:
        candidates = [("next uninstall", fixed)]
    else:
        candidates = []
        # The operator's profile may hold any of these rules, whichever one
        # the message came from.
        for rules in BODIES:
            for recorded in (True, False):
                merged = merge_managed_block(fixed, rules, recorded=recorded)
                blocks, stray, unclear = _state(merged)
                if len(blocks) != 1 or stray or unclear:
                    return (
                        f"next update (recorded={recorded}, rules {rules!r}) "
                        f"gives blocks {blocks}, stray BEGIN {stray}, "
                        f"unplaced pairs {unclear}"
                    )
                candidates.append(
                    (f"uninstall after the update ({recorded}, {rules!r})", merged)
                )
    for name, text in candidates:
        blocks, stray, unclear = _state(remove_managed_block(text))
        if blocks or stray or unclear:
            return (
                f"{name} leaves blocks {blocks}, stray BEGIN {stray}, "
                f"unplaced pairs {unclear}"
            )
    return None


def _role_changes(
    before: Sequence[str | None],
    lines: Sequence[str],
    tags: Sequence[int | None],
    skip: set[int],
) -> list[str]:
    after = roles(lines)
    return [
        f"line {tag + 1} read as {before[tag]}, now {after[at]}"
        for at, tag in enumerate(tags)
        if tag is not None
        and tag not in skip
        and before[tag] is not None
        and after[at] != before[tag]
    ]


@lru_cache(maxsize=65536)
def check_fix(
    original: tuple[str, ...],
    before: tuple[str | None, ...],
    steps: tuple[Step, ...],
    *,
    block: tuple[int, int] | None,
    keeps: bool,
    removes: bool = False,
    lasting: bool = False,
) -> tuple[str, str] | None:
    """Return the kind and text of what is wrong with a fix, followed literally.

    Several callers print the same fix, so each result is kept and reused.

    With *removes* (the fix's next run is an uninstall), the operator's lines
    must also read as before once the uninstall takes the block out. For an
    update the block stays, so only no line of theirs may go then. With
    *lasting* (the fix says its block is then the one block in the file),
    the next update must hold as well as the next uninstall: an uninstall
    with no install record leaves that block, and a later install merges.
    """
    try:
        done = apply_steps(original, steps)
    except UnreadableError as error:
        return "step-names-no-such-line", str(error)
    try:
        other = apply_in_original(original, steps)
    except UnreadableError as error:
        return "line-numbers-shift", str(error)
    if other != done.lines:
        return (
            "line-numbers-shift",
            "the steps give another file when each number is read as it was "
            "before any step",
        )
    gone = set(range(len(original))) - done.deleted - set(done.tags)
    if gone:
        return "operator-line-gone", f"lines {sorted(t + 1 for t in gone)} are gone"
    fixed = _joined(done.lines)
    blocks, stray, unclear = _state(fixed)
    want: list[tuple[int, int]] = []
    if keeps and block is not None:
        first, last = block[0] - 1, block[1] - 1
        if first not in done.tags or last not in done.tags:
            return "promised-block-gone", f"block {block} is not in the file"
        want = [(done.tags.index(first) + 1, done.tags.index(last) + 1)]
    if blocks != want or stray or unclear:
        return (
            "promise-not-held",
            f"file then holds blocks {blocks} (want {want}), stray BEGIN {stray}, "
            f"unplaced pairs {unclear}",
        )
    wrong = _next_runs(fixed, removes=removes)
    if wrong is None and removes and lasting:
        wrong = _next_runs(fixed, removes=False)
    if wrong is not None:
        return "next-run-not-held", wrong
    skip = set(done.named)
    if block is not None:
        skip |= set(range(block[0] - 1, block[1]))
    changes = _role_changes(before, done.lines, done.tags, skip)
    if changes:
        return "operator-line-role-changed", "; ".join(changes[:4])
    if want:
        return _after_uninstall(before, done, want[0], skip if removes else None)
    return None


def _after_uninstall(
    before: Sequence[str | None],
    done: Applied,
    block: tuple[int, int],
    skip: set[int] | None,
) -> tuple[str, str] | None:
    """Return what is wrong with the file once the uninstall takes *block* out.

    No line of the operator's may go; with *skip* (the lines that are not
    theirs), each must also read as before.
    """
    lines = remove_managed_block(_joined(done.lines)).split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    kept = [
        (text, tag)
        for at, (text, tag) in enumerate(zip(done.lines, done.tags, strict=True))
        if not block[0] - 1 <= at <= block[1] - 1 and text.strip()
    ]
    rest = [text for text in lines if text.strip()]
    if rest != [text for text, _ in kept]:
        return "uninstall-cut-operator-text", f"left {rest!r}"
    if skip is None:
        return None
    positions = [at for at, text in enumerate(lines) if text.strip()]
    tags: list[int | None] = [None] * len(lines)
    for at, (_, tag) in zip(positions, kept, strict=True):
        tags[at] = tag
    changes = _role_changes(before, lines, tags, skip)
    if changes:
        return "role-changed-after-uninstall", "; ".join(changes[:4])
    return None


def check_message(
    tally: Tally, caller: str, text: str, message: str, body: str
) -> None:
    """Read *message*, follow each fix it gives on *text*, and flag what fails."""
    tally.messages += 1
    original = tuple(text.split("\n")[:-1])
    before = tuple(roles(original))
    for sentence in stray_edits(message):
        tally.flag(caller, "unnumbered-line-edit", text, message, sentence)
    try:
        fixes = read_fixes(message)
    except UnreadableError as error:
        tally.flag(caller, "unreadable-step", text, message, str(error))
        return
    if _FALLBACK in message:
        tally.advice += 1
        tally.fallback += 1
        family = caller.split(" (")[0]
        tally.callers[family] = tally.callers.get(family, 0) + 1
        if fixes or _LABEL.search(message):
            tally.flag(caller, "fallback-names-a-step", text, message, "numbered step")
        if not _FALLBACK_PROMISE.search(message):
            tally.flag(caller, "fallback-promise-unread", text, message, "no promise")
        steps = tuple(
            Step("change", (number,))
            for number, line in enumerate(original, 1)
            if line.strip() in MARKERS
        )
        found = check_fix(
            original,
            before,
            steps,
            block=None,
            keeps=False,
            removes="next update" not in message,
        )
        if found is not None:
            tally.flag(caller, f"fallback-{found[0]}", text, message, found[1])
        return
    if not fixes:
        tally.prose_only += 1
        return
    tally.advice += 1
    tally.numbered += 1
    family = caller.split(" (")[0]
    tally.callers[family] = tally.callers.get(family, 0) + 1
    removes = "uninstall again" in message or "takes Apothem's block out" in message
    for fix in fixes:
        if fix.promise_block is not None and fix.promise_block != fix.block:
            tally.flag(
                caller,
                "promise-names-another-block",
                text,
                message,
                f"fix {fix.letter}: {fix.promise_block} vs {fix.block}",
            )
        found = check_fix(
            original,
            before,
            tuple(fix.steps),
            block=fix.block,
            keeps=bool(fix.keeps),
            removes=removes,
            lasting=fix.promise_block is not None,
        )
        if found is not None:
            problem = f"fix {fix.letter}: {found[1]} (update body {body!r})"
            tally.flag(caller, found[0], text, message, problem)


# --- the callers ---------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def caller_messages(text: str, body: str, home: Path) -> Iterator[tuple[str, str, str]]:
    """Yield (caller, message, the file text its line numbers count) for *text*.

    Each caller is driven through the function it calls, with what it passes.
    """
    path = home / "AGENTS.md"
    for recorded in (True, False):
        merged = merge_managed_block(text, body, recorded=recorded)
        unchanged = merged == text
        for dry_run in (False, True):
            on_disk = text if dry_run or unchanged else merged
            _write(path, on_disk)
            found = _install_warning(str(path), unchanged=unchanged, dry_run=dry_run)
            if found is not None:
                caller = (
                    f"install/update (record {recorded}, left {unchanged}, "
                    f"dry run {dry_run})"
                )
                yield caller, found[0], on_disk
        if not unchanged and recorded:
            yield from _verify_messages(merged, path, "after the write")
    yield from _verify_messages(text, path, "as found")
    _write(path, text)
    for recorded in (True, False):
        refusal = sentinel_refusal(path, recorded=recorded)
        if refusal is not None:
            yield f"uninstall (record {recorded})", refusal.message, text
    root = home / "unlisted"
    _write(root / "CLAUDE.md", text)
    for warning in unlisted_block_warnings(root):
        yield "uninstall (no record, bolt-on anchor)", warning.message, text
    yield from _retire_messages(path, text)


def _verify_messages(
    text: str, path: Path, when: str
) -> Iterator[tuple[str, str, str]]:
    _write(path, text)
    if not markers_to_fix_at(path):
        return
    for listed in (True, False):
        note = stray_begin_note(
            [path],
            then="run apothem update and apothem verify again",
            listed=_always(listed),
        )
        yield f"verify/doctor (listed {listed}, {when})", note, text


def _always(listed: bool) -> Callable[[Path], bool]:
    """Return a record lookup that answers *listed* for every file."""

    def lookup(_path: Path) -> bool:
        return listed

    return lookup


def _retire_messages(path: Path, text: str) -> Iterator[tuple[str, str, str]]:
    for strict, dry_run in ((False, False), (False, True), (True, False)):
        unclear = unclear_block_warning(
            path, RETIRE, outcome=None if strict else TAKES_OUT, dry_run=dry_run
        )
        name = f"openclaw retire (strict {strict}, dry run {dry_run})"
        if unclear is not None:
            yield name, unclear.message, text
            continue
        endless = endless_block_warning(path, RETIRE, dry_run=dry_run)
        if endless is not None:
            yield name, endless.message, text
            continue
        if another_block_at(path):
            then = UNINSTALL_AGAIN if strict else _RETRIED
            warning = another_block_warning(
                path, operation=RETIRE, then=then, dry_run=dry_run
            )
            yield name, warning.message, text


# --- making files --------------------------------------------------------------


class Maker:
    """Random Markdown files with Apothem marker lines, from one seed."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)  # noqa: S311 - seeded test input
        self.count = 0

    def keep(self) -> str:
        self.count += 1
        return f"KEEP{self.count}"

    def marker(self, which: str) -> str:
        return " " * self.rng.choice((0, 0, 0, 0, 1, 2, 3)) + which

    def opener(self) -> tuple[str, str, int]:
        char = self.rng.choice("`~")
        size = self.rng.choice((3, 3, 3, 4, 5))
        info = self.rng.choice(("", "", "sh", "md", "text title"))
        return " " * self.rng.randint(0, 3) + char * size + info, char, size

    def closer(self, char: str, size: int) -> str:
        extra = self.rng.choice((0, 0, 0, 1))
        return " " * self.rng.randint(0, 3) + char * (size + extra)

    def body(self) -> list[str]:
        return list(
            self.rng.choice(
                (
                    [f"rule {self.keep()}"],
                    [f"rule {self.keep()}", f"rule {self.keep()}"],
                    ["Run:", "```sh", "npm test", "```"],
                    ["Run:", "```sh", "npm test"],
                    ["Run:", "~~~", "npm test"],
                    [],
                )
            )
        )

    def block(self) -> list[str]:
        return [self.marker(B), *self.body(), self.marker(E)]

    def plain(self) -> list[str]:
        rng, keep = self.rng, self.keep
        choice = rng.randrange(9)
        if choice == 0:
            return [f"text {keep()}" for _ in range(rng.randint(1, 3))]
        if choice == 1:
            return [f"# head {keep()}"]
        if choice == 2:
            item = [f"- item {keep()}"]
            if rng.random() < 0.5:
                item.append(f"  more {keep()}")
            if rng.random() < 0.3:
                item.append(f"1. step {keep()}")
            return item
        if choice in (3, 4):
            opener, char, size = self.opener()
            lines = [opener, *(f"code {keep()}" for _ in range(rng.randint(0, 3)))]
            if rng.random() < 0.8:
                lines.append(self.closer(char, size))
            return lines
        if choice == 5:
            return ["", f"    code {keep()}", f"    code {keep()}", ""]
        if choice == 6:
            return [f"- item {keep()}", "  ```", f"  code {keep()}", "  ```"]
        if choice == 7:
            return [f"Example {keep()}:", "```sh", f"ls {keep()}", "```"]
        return [""]

    def marked(self) -> list[str]:
        rng, keep = self.rng, self.keep
        choice = rng.randrange(11)
        if choice in (0, 1):
            return self.block()
        if choice == 10:
            # A BEGIN marker above a block and an END marker below it.
            return [self.marker(B), *self.block(), *[""] * rng.randint(0, 2), E]
        if choice in (2, 3):
            opener, char, size = self.opener()
            lines = [opener]
            if rng.random() < 0.6:
                lines += [f"code {keep()}", *([""] if rng.random() < 0.5 else [])]
            lines += self.block()
            if rng.random() < 0.4:
                lines += [*([""] if rng.random() < 0.5 else []), f"code {keep()}"]
            if rng.random() < 0.85:
                lines.append(self.closer(char, size))
            return lines
        if choice == 4:
            opener, char, size = self.opener()
            return [opener, B, f"example {keep()}", E, self.closer(char, size)]
        if choice == 5:
            return ["", f"    {B}", f"    example {keep()}", f"    {E}", ""]
        if choice == 6:
            return [f"text {keep()}", f"    {B}", f"    x {keep()}", f"    {E}"]
        if choice == 7:
            return [self.marker(B), f"old rule {keep()}"]
        if choice == 8:
            return [f"- item {keep()}", f"  {B}", f"  rule {keep()}", f"  {E}"]
        return [self.marker(E)]

    def file(self) -> str:
        rng = self.rng
        parts = [self.plain() for _ in range(rng.randint(1, 5))]
        parts += [self.marked() for _ in range(rng.randint(1, 3))]
        rng.shuffle(parts)
        lines: list[str] = []
        for part in parts:
            lines += part
            if rng.random() < 0.6:
                lines.append("")
        for _ in range(rng.choice((0, 0, 0, 1, 2))):
            spot = rng.randint(0, len(lines))
            lines.insert(spot, " " * rng.choice((0, 0, 2, 4)) + rng.choice((B, E)))
        while lines and not lines[-1].strip():
            lines.pop()
        return _joined(lines)


def _files() -> int:
    return int(os.environ.get("APOTHEM_ADVICE_PROPERTY_FILES", DEFAULT_FILES))


def run_files(texts: Sequence[str], home: Path, bodies: Callable[[int], str]) -> Tally:
    """Check every message every caller gives for each of *texts*."""
    tally = Tally()
    for index, text in enumerate(texts):
        tally.files += 1
        body = bodies(index)
        for caller, message, on_disk in caller_messages(text, body, home):
            check_message(tally, caller, on_disk, message, body)
    return tally


def _report(tally: Tally, label: str) -> None:
    target = os.environ.get("APOTHEM_ADVICE_PROPERTY_REPORT")
    if not target:
        return
    row = {
        "label": label,
        "files": tally.files,
        "messages": tally.messages,
        "advice": tally.advice,
        "fallback": tally.fallback,
        "numbered": tally.numbered,
        "prose_only": tally.prose_only,
        "callers": tally.callers,
        "violations": list(tally.violations.values()),
    }
    with Path(target).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row) + "\n")


def _summary(tally: Tally) -> str:
    rate = tally.fallback / tally.advice if tally.advice else 0.0
    lines = [
        f"{tally.files} files, {tally.messages} messages, {tally.advice} with advice, "
        f"{tally.fallback} fallbacks (rate {rate:.4f})"
    ]
    for kind, found in sorted(tally.violations.items()):
        lines += [
            f"--- {kind} ({found['caller']}): {found['problem']}",
            f"file: {found['file_text']!r}",
            f"message: {found['message']}",
        ]
    return "\n".join(lines)


@pytest.mark.parametrize("shard", range(SHARDS))
def test_every_printed_fix_holds_when_followed_literally(
    shard: int, tmp_path: Path
) -> None:
    """Each fix any caller prints for a random file holds what it promises."""
    maker = Maker(SEED * 100 + shard)
    count = -(-_files() // SHARDS)
    texts = [maker.file() for _ in range(count)]
    rng = random.Random(SEED + shard)  # noqa: S311 - seeded test input
    tally = run_files(texts, tmp_path, lambda _index: rng.choice(BODIES))
    _report(tally, f"shard {shard}")
    assert set(tally.callers) >= CALLERS, (
        f"no advice from {CALLERS - set(tally.callers)}"
    )
    assert not tally.violations, _summary(tally)


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_named_shapes_hold_and_code_blocks_get_numbered_fixes(
    name: str, tmp_path: Path
) -> None:
    """The reviewer's shapes hold; sA2 and plain get numbered fixes, no fallback."""
    text = _joined(SHAPES[name])
    tally = Tally()
    numbered: list[bool] = []
    for body in BODIES:
        for caller, message, on_disk in caller_messages(text, body, tmp_path):
            check_message(tally, caller, on_disk, message, body)
            if _FALLBACK in message or _FIX_HEAD.search(message):
                numbered.append(_FALLBACK not in message)
        tally.files += 1
    _report(tally, f"shape {name}")
    assert not tally.violations, _summary(tally)
    assert numbered, f"{name}: no caller gave advice"
    if name in {"sA2", "plain"}:
        assert all(numbered), f"{name}: a caller gave the fallback\n{_summary(tally)}"


def test_the_reader_reads_every_documented_step_format() -> None:
    """This test's own patterns read each step format the docs list."""
    message = (
        "Fix A, if lines 2 to 5 are Apothem's block: A1. Change line 9: add a "
        "word inside its comment. A2. Below line 5, add a copy of line 1. A3. "
        "Above line 2, add a line of 4 tildes, indented 2 spaces. A4. Above "
        "line 2, add a line of 3 backticks. A5. Move line 7 to just above line "
        "2. The next update then replaces Apothem's block. Fix B, if lines 2 to "
        "5 are text of yours: B1. Delete lines 2 to 5. No Apothem block is then "
        "left in this file."
    )
    fixes = read_fixes(message)
    assert [step.kind for step in fixes[0].steps] == [
        "change",
        "copy",
        "fence",
        "fence",
        "move",
    ]
    assert fixes[0].steps[2].text == "Above|  ~~~~"
    assert fixes[1].steps == [Step("delete", (2, 5))]
    with pytest.raises(UnreadableError):
        read_fixes("Fix A, if lines 2 to 5 are Apothem's block: A1. Delete line 4.")
    assert stray_edits("Then delete line 4 by hand.") == ["Then delete line 4 by hand."]
    # The uninstall's old text for a block no record lists: an edit in prose.
    assert stray_edits(
        "the uninstall leaves it as it is; delete lines 2 to 3, from "
        f"{B} to {E}, by hand if you no longer want them"
    )


def test_both_readings_of_the_line_numbers_agree_only_bottom_up() -> None:
    """Steps from the bottom up give one file both ways; top down they do not."""
    lines = ["a", B, "b", E, "c", "d"]
    bottom_up = [Step("delete", (5, 6)), Step("change", (2,))]
    assert apply_steps(lines, bottom_up).lines == apply_in_original(lines, bottom_up)
    top_down = [Step("delete", (1, 1)), Step("change", (4,))]
    with pytest.raises(UnreadableError):
        apply_steps(lines, top_down)  # line 4 is "c" by then: not a marker line
    lines = [B, E, B, E]
    shifted = [Step("delete", (1, 1)), Step("change", (2,))]
    assert apply_steps(lines, shifted).lines != apply_in_original(lines, shifted)
