# SPDX-License-Identifier: MIT

"""Advisory: flag plan-suite gate claims that lack a command, an exit status or
output, and a HEAD SHA beside them, and fifteen-bar attestations that omit a
field of the rule's schema.

Why this validator exists. ``commands/plan-execute.md`` (Gate evidence) makes a
gate claim valid only when three items sit beside it in the phase report and
the progress file: the command that ran, its output (exit status plus summary
lines), and the SHA of HEAD when it ran. A claim missing any of the three is
unverified, whatever it says. The contract is prose, so nothing mechanical
caught a report that wrote "lint, types and tests pass" and recorded none of
it. This validator reads the plan-suite files that carry such claims and
reports each claim that lacks the three items.

Two checks run, one per contract.

1. **Gate claims** (``commands/plan-execute.md``, Gate evidence). A claim is a
   table row, list item (with its nested lines), paragraph, or heading section
   that names a gate and asserts a pass. Gate names: lint, format, type-check,
   tests, build, security scan, coverage, CI, conformity, pre-emission and the
   like. Pass assertions: ``PASS``, ``passed``, ``green``, ``clean``, ``OK``, a
   bare check mark, ``0 errors``. A check mark next to a status word such as
   "Complete" is a phase status, not a gate claim. A line that reports a
   failure, is an unticked box, or is directive ("must pass") is not a
   claim. The evidence is looked up in the claim itself (with any pasted
   block under it), the headings above it, and the earlier paragraphs and list items of the
   same section that make no pass claim of their own, so one recorded run can
   back a table of results while a claim never leans on another gate's run:

   - *command*: a backticked command (``python -m pytest``, ``make check``),
     a ``command:`` field, a ``$``-prompted line in a pasted block, or
     "ran ``pytest``";
   - *output*: an exit status (``exit 0``, ``rc=0``, ``exit: 0``), a summary
     line carrying a count (``412 passed``), pasted output under the claim, or
     a pointer to the full output (an ``output:`` field, a log path, a CI run
     link). A bare verdict word (``clean``, ``OK``) is not output;
   - *sha*: a 7 to 64 character hex SHA, or a number after ``HEAD`` / ``SHA``
     / ``commit``.

   A table row also reads its own ``Command``, ``Exit``, ``Output`` and
   ``SHA`` columns. A report-header ``Commit(s):`` line does not count: it
   names the commits the phase produced, while the contract asks for HEAD at
   the moment the gate ran, so it must sit in the claim's own section.
   An ``ecosystem-version`` line never counts either; it names the rule set
   in force, not the project HEAD. A list item or record whose nested
   children are two or more separate gate claims is judged child by child;
   each child also reads its non-claim siblings (``command:``, ``exit:`` and
   ``head:`` keys written beside ``lint: pass``, or a ``Run: ...`` bullet
   above ``- Lint: pass``), so one recorded run backs the claims beside it. A
   ticked exit-criteria checkbox, or a claim that names only "the gates" in
   general, is a roll-up: it is supported when the same file holds at least
   one claim with all three items, and flagged when it holds none.

2. **Attestation blocks** (``rules/pre-emission-gate-bars.md`` section 2). A
   ``conformity-attestation:`` block, in a fenced YAML block or an
   ``attestation.yml`` file, must carry ``artifact``, a filled
   ``ecosystem-version``, an ISO-8601 ``date``, the three explicit arrays
   (``surfaced-gaps``, ``unresolved-inquiries``, ``amendments-disclosed``), all
   fifteen ``M1`` to ``M15`` bar lines, and a reason on every ``n/a``. The
   reason may follow ``n/a`` in parentheses or sit in a trailing ``# comment``.
   The block is judged by this schema alone: its ``pass`` lines are verdicts of
   the fifteen-bar sweep, most of them reasoned with no command behind them,
   and the schema has no field for a command, an exit status or a SHA, so the
   block is not also read as a prose gate claim. A run of the conformity gate
   that backs the attestation is a gate claim of its own, and check 1 judges it
   wherever it is written.

   Known noise (advisory by design). Recognising a gate claim in free prose is
   a heuristic. A gate noun used as a modifier beside a check mark (a table
   row reading "docs build notes" with a check mark) and a gate noun in a
   sentence whose "pass" is about something else ("coverage of the spec is
   complete: all 14 sections pass") can be flagged. The cure for a false
   positive is to reword the line or to record the command beside it.

Scope. ``PROGRESS.md``, ``COMPLETION.md``, every ``REPORT.md``,
``attestation.yml`` / ``attestation.yaml`` and ``_inputs/handoff-manifest.yml``
under each suite in ``<root>/.apothem/plans/``. The root may also be the plans
directory or a single suite. Plan suites are gitignored working state, so a
clean checkout holds none and an empty scope is expected.

Advisory by default. The contract states the three items as mandatory, but
recognising a gate claim in free Markdown is a heuristic, and the shared gate
posture keeps quality gates advisory. ``_main`` therefore prints the report and
exits 0 regardless of findings; ``--strict`` exits 2 on findings. The
``check()`` verdict (``passed = not findings``) is honest either way.

Out of scope. Comparing a recorded SHA with the current HEAD (the contract's
staleness rule) needs the repository state at phase exit and cannot be judged
from a file read later. Whether a recorded SHA exists in the repository, and
whether the quoted output is genuine, are likewise not checked.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field, replace
from itertools import pairwise
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import finish_root_report, parse_root_args

GREP_NAME: Final[str] = "gate-evidence-grep"
RULE_ANCHOR: Final[str] = (
    "commands/plan-execute.md Gate evidence; "
    "rules/pre-emission-gate-bars.md section 2 (attestation schema)"
)

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2
STRICT_FLAG: Final[str] = "--strict"

# The sole canonical project-local plans location.
APOTHEM_PLANS_RELPATH: Final[tuple[str, str]] = (".apothem", "plans")
_ROOT_FILES: Final[tuple[str, ...]] = ("PROGRESS.md", "COMPLETION.md")
_ATTESTATION_FILES: Final[tuple[str, ...]] = ("attestation.yml", "attestation.yaml")
_MANIFEST_RELPATH: Final[tuple[str, str]] = ("_inputs", "handoff-manifest.yml")
_YAML_SUFFIXES: Final[frozenset[str]] = frozenset({".yml", ".yaml"})

# The three items the contract requires beside a gate claim.
ITEM_COMMAND: Final[str] = "command"
ITEM_OUTPUT: Final[str] = "output"
ITEM_SHA: Final[str] = "sha"
_ITEMS: Final[tuple[str, ...]] = (ITEM_COMMAND, ITEM_OUTPUT, ITEM_SHA)

KIND_CLAIM: Final[str] = "gate-claim"
KIND_ROLLUP: Final[str] = "rollup-claim"
KIND_ATTESTATION: Final[str] = "attestation-incomplete"

_EXCERPT_CHARS: Final[int] = 100
_SHA_MIN: Final[int] = 7
_SHA_MAX: Final[int] = 64
_BAR_COUNT: Final[int] = 15

# --- Claim vocabulary --------------------------------------------------------
# A name is not a gate when it is part of a path (``tests/``, ``lint.py``), so
# every pattern refuses a neighbouring slash, backslash or ``.ext`` suffix.
_EDGE_BEFORE: Final[str] = r"(?<![\w/\\.])"
_EDGE_AFTER: Final[str] = r"(?![\w/\\]|\.\w)"

_SPECIFIC_GATE_RE: Final[re.Pattern[str]] = re.compile(
    _EDGE_BEFORE
    + r"(?:lint(?:er|ers|ing|s)?|ruff|eslint|flake8|pylint|format(?:ter|ting)|"
    r"prettier|types|type[- ]?check(?:s|er|ing)?|mypy|pyright|tsc|"
    r"(?:unit|integration|e2e|end-to-end|regression|smoke|acceptance|contract)"
    r"[ -]tests?|tests|test[- ]suites?|pytest|jest|vitest|mocha|builds?|"
    r"security[ -](?:scan|audit|check)s?|sast|bandit|semgrep|gitleaks|"
    r"secret[ -]scan|pip-audit|(?:npm|cargo|dependency)[ -]audit|coverage|"
    r"dead[ -]code|link[ -]?check(?:er)?|conformity|pre-commit|pre-emission|"
    r"fifteen-bar|15-bar|ci|continuous integration)" + _EDGE_AFTER,
    re.IGNORECASE,
)
_AGGREGATE_GATE_RE: Final[re.Pattern[str]] = re.compile(
    _EDGE_BEFORE + r"(?:gates?|all checks|every check|quality checks?)" + _EDGE_AFTER,
    re.IGNORECASE,
)
_PASS_WORD_RE: Final[re.Pattern[str]] = re.compile(
    _EDGE_BEFORE
    + r"(?:pass(?:es|ed|ing)?|green|clean(?!\s+up\b)|success(?:ful(?:ly)?)?|"
    r"succeeded|(?-i:OK)|(?:0|zero|no)\s+(?:errors?|failures?|findings?|"
    r"issues?|violations?|warnings?))" + _EDGE_AFTER,
    re.IGNORECASE,
)
_PASS_MARK_RE: Final[re.Pattern[str]] = re.compile(
    r"[\N{WHITE HEAVY CHECK MARK}\N{HEAVY CHECK MARK}\N{CHECK MARK}"
    r"\N{BALLOT BOX WITH CHECK}]"
)
# A check mark beside one of these is a phase or deliverable status.
_STATUS_WORD_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:complete[d]?|done|finished|delivered|shipped|merged|created|added|"
    r"written|verified|exists?|present)\b",
    re.IGNORECASE,
)
_ZERO_COUNT_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:0|zero|no)\s+(?:\w+\s+)?(?:fail\w*|errors?|findings?|issues?|"
    r"violations?|warnings?)\b",
    re.IGNORECASE,
)
_FAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"\bfail(?:s|ed|ing|ure|ures)?\b|\bblocked\b|"
    r"[\N{CROSS MARK}\N{BALLOT X}\N{HEAVY BALLOT X}\N{NO ENTRY SIGN}]|"
    r"\b(?:not|never|no longer)\s+(?:pass|passing|green|clean)\b|n't\s+pass",
    re.IGNORECASE,
)
_MODAL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:must|should|shall|will|needs? to|ensure|make sure|until|unless|"
    r"expected to|required to)\b",
    re.IGNORECASE,
)
_TICKED_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[xX]\]")
_UNTICKED_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[ \]")
_PATH_SPAN_RE: Final[re.Pattern[str]] = re.compile(r"`[^`\s]*[/\\.][^`\s]*`")
_LINK_TARGET_RE: Final[re.Pattern[str]] = re.compile(r"\]\([^)]*\)")

# --- Evidence vocabulary -----------------------------------------------------
_RUNNER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:python3?|py|pytest|ruff|mypy|pyright|pylint|flake8|black|isort|bandit|"
    r"semgrep|gitleaks|pip3?|pip-audit|pipx|uvx?|poetry|hatch|tox|nox|pre-commit|"
    r"npm|npx|pnpm|yarn|node|bun|deno|tsc|eslint|prettier|jest|vitest|mocha|"
    r"cargo|go|make|cmake|ctest|gradlew?|mvn|dotnet|git|gh|docker|bash|sh|pwsh|"
    r"powershell|ruby|bundle|rake|rspec|php|composer|phpunit|swift|xcodebuild|"
    r"flutter|dart|mix|task|just|apothem)",
    re.IGNORECASE,
)
_BACKTICK_RE: Final[re.Pattern[str]] = re.compile(r"`([^`]+)`")
_PROMPT_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(?:\$|>|%|PS\S*>)?\s*")
_RAN_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:ran|runs?|running|executed|invoked)\s+`?([\w./\\-]+)", re.IGNORECASE
)
_LABEL_TAIL: Final[str] = r"[^\w\n]{0,3}[:=][ \t*_]{0,4}(?P<v>\S.*)"
_COMMAND_LABEL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:command|cmd|invocation)\b" + _LABEL_TAIL, re.IGNORECASE
)
_POINTER_LABEL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:output|logs?|transcript|evidence|summary)\b" + _LABEL_TAIL,
    re.IGNORECASE,
)
_POINTER_TARGET_RE: Final[re.Pattern[str]] = re.compile(
    r"https?://\S*/(?:actions/runs|runs|jobs|builds?|pipelines)/\d+|"
    r"`[^`\s]+\.(?:log|txt|out|xml|sarif|json|html)`",
    re.IGNORECASE,
)
_EXIT_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:exit(?:ed)?|rc|return[ _-]?code|status[ _-]?code)(?:[ _-](?:status|code))?"
    r"\s*(?:[:=]\s*|\s+(?:with\s+)?(?:status\s+|code\s+)?)-?\d+\b",
    re.IGNORECASE,
)
_SUMMARY_RE: Final[re.Pattern[str]] = re.compile(
    r"\b\d[\d,]*\s+(?:source\s+)?(?:passed|failed|errors?|warnings?|tests?|"
    r"checks?|files?|issues?|findings?|skipped|specs?|assertions?)\b",
    re.IGNORECASE,
)
_SHA_RE: Final[re.Pattern[str]] = re.compile(
    rf"(?<![0-9A-Za-z])(?=[0-9a-f]*[0-9])(?=[0-9a-f]*[a-f])"
    rf"[0-9a-f]{{{_SHA_MIN},{_SHA_MAX}}}(?![0-9A-Za-z])"
)
_LABELLED_SHA_RE: Final[re.Pattern[str]] = re.compile(
    rf"\b(?:head|sha|commit|rev(?:ision)?)\b[^\w\n]{{0,4}}"
    rf"[0-9a-f]{{{_SHA_MIN},{_SHA_MAX}}}\b",
    re.IGNORECASE,
)
_SHA_CELL_RE: Final[re.Pattern[str]] = re.compile(
    rf"^\W*[0-9a-f]{{{_SHA_MIN},{_SHA_MAX}}}\W*$", re.IGNORECASE
)
_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:tbd|todo|n/?a|none|unknown|pending|null|~|"
    r"[-.?\N{EM DASH}\N{EN DASH}\N{HORIZONTAL ELLIPSIS}]*|<[^>]*>|\[[^\]]*\])$",
    re.IGNORECASE,
)
_EVIDENCE_EXCLUDED: Final[str] = "ecosystem-version"

# --- Markdown / YAML structure ----------------------------------------------
_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(```|~~~)\s*([A-Za-z0-9_-]*)")
_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_ITEM_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^\s*[\w.\"'-]+\s*:(?:\s|$)")
_SEPARATOR_RE: Final[re.Pattern[str]] = re.compile(
    r"^\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?$"
)
_YAML_LANGS: Final[frozenset[str]] = frozenset({"yaml", "yml"})

# --- Attestation vocabulary --------------------------------------------------
_ATTESTATION_ROOT: Final[str] = "conformity-attestation"
_ATTESTATION_ARRAYS: Final[tuple[str, ...]] = (
    "surfaced-gaps",
    "unresolved-inquiries",
    "amendments-disclosed",
)
_BAR_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^\s*M(\d{1,2})-", re.MULTILINE)
_NA_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^[^:\n]*:[ \t]*(?P<value>.*?)[ \t]*$", re.MULTILINE
)
_ISO_DATE_RE: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\S*)?$")


@dataclass
class _Block:
    """One claim-sized unit of a plan-suite file."""

    line: int
    kind: str  # row | item | para | heading | record
    prose: list[str]
    section: int = 0
    scope: str = ""
    indent: int = 0
    cells: dict[str, str] | None = None
    fenced: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Return the claim-capable lines joined."""
        return "\n".join(self.prose)


@dataclass(frozen=True)
class Finding:
    """One gate claim or attestation block that lacks required evidence."""

    surface: str
    suite: str
    line: int
    kind: str
    form: str
    claim: str
    missing: list[str]
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result across every plan suite under the root."""

    grep: str
    root: str
    suites_inspected: int
    files_inspected: int
    claims_inspected: int
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, suites_inspected,
        files_inspected, claims_inspected, passed, advisory, findings, notes}``;
        each finding is flattened through ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "suites_inspected": self.suites_inspected,
            "files_inspected": self.files_inspected,
            "claims_inspected": self.claims_inspected,
            "passed": self.passed,
            # Always advisory: the gate classifies a validator as advisory by this
            # literal in its report, and ``--strict`` is a CLI exit choice only.
            "advisory": True,
            "findings": [asdict(f) for f in self.findings],
            "notes": list(self.notes),
        }
        return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# Claim detection
# ---------------------------------------------------------------------------


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _plain(text: str) -> str:
    """Return *text* with path-like spans and link targets removed, for naming."""
    text = _LINK_TARGET_RE.sub("]", _PATH_SPAN_RE.sub(" ", text))
    return text.replace("_", " ")


def _claim_kind(text: str) -> str | None:
    """Return ``KIND_CLAIM``, ``KIND_ROLLUP`` or None for a block's prose.

    A claim names a gate and asserts a pass. Failure reports, unticked boxes
    and directive wording are not claims. A ticked box, or a claim naming only
    "the gates" in general, is a roll-up.
    """
    if _UNTICKED_RE.match(text) or _MODAL_RE.search(text):
        return None
    plain = _plain(text)
    if _FAIL_RE.search(_ZERO_COUNT_RE.sub("", plain)):
        return None
    asserts_pass = _PASS_WORD_RE.search(plain) or (
        _PASS_MARK_RE.search(plain) and not _STATUS_WORD_RE.search(plain)
    )
    if not asserts_pass:
        return None
    if _SPECIFIC_GATE_RE.search(plain):
        return KIND_ROLLUP if _TICKED_RE.match(text) else KIND_CLAIM
    if _AGGREGATE_GATE_RE.search(plain):
        return KIND_ROLLUP
    return None


# ---------------------------------------------------------------------------
# Evidence detection
# ---------------------------------------------------------------------------


def _is_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER_RE.match(value.strip().strip("`'\"*_ ")))


def _is_command(span: str) -> bool:
    """Return True when *span* starts with a known runner or a ``./`` script."""
    tokens = _PROMPT_RE.sub("", span, count=1).split()
    if not tokens:
        return False
    first = tokens[0].lower()
    return bool(_RUNNER_RE.fullmatch(first)) or first.startswith(("./", ".\\"))


def _has_command(prose: str, fenced: list[str]) -> bool:
    for match in _COMMAND_LABEL_RE.finditer(prose):
        if not _is_placeholder(match.group("v")):
            return True
    if any(_is_command(span) for span in _BACKTICK_RE.findall(prose)):
        return True
    if any(_RUNNER_RE.fullmatch(name) for name in _RAN_RE.findall(prose)):
        return True
    return any(_is_command(line) for line in fenced)


def _has_output(text: str, fenced: list[str]) -> bool:
    if _EXIT_RE.search(text) or _SUMMARY_RE.search(text):
        return True
    if _POINTER_TARGET_RE.search(text):
        return True
    if any(ln.strip() and not _is_command(ln) for ln in fenced):
        return True
    return any(
        not _is_placeholder(m.group("v")) for m in _POINTER_LABEL_RE.finditer(text)
    )


def _has_sha(text: str) -> bool:
    return bool(_SHA_RE.search(text) or _LABELLED_SHA_RE.search(text))


def _column_evidence(cells: dict[str, str]) -> set[str]:
    """Return the items a table row records under its own column headers."""
    found: set[str] = set()
    for header, value in cells.items():
        if _is_placeholder(value):
            continue
        if re.search(r"command|cmd", header):
            found.add(ITEM_COMMAND)
        elif (
            re.search(r"\bexit\b|\brc\b|return", header) and re.search(r"\d", value)
        ) or re.search(r"output|log|evidence|summary", header):
            found.add(ITEM_OUTPUT)
        elif re.search(r"sha|head|commit|rev", header) and _SHA_CELL_RE.match(value):
            found.add(ITEM_SHA)
    return found


def _found_items(block: _Block, context: list[str]) -> set[str]:
    """Return the evidence items recorded in or beside *block*."""
    pool = "\n".join([block.scope, *context, *block.prose]).splitlines()
    prose = "\n".join(ln for ln in pool if _EVIDENCE_EXCLUDED not in ln)
    everything = "\n".join([prose, *block.fenced])
    found = _column_evidence(block.cells) if block.cells else set()
    if _has_command(prose, block.fenced):
        found.add(ITEM_COMMAND)
    if _has_output(everything, block.fenced):
        found.add(ITEM_OUTPUT)
    if _has_sha(everything):
        found.add(ITEM_SHA)
    return found


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------


def _segment_yaml(
    lines: list[str], first_line: int, section: int, scope: str
) -> list[_Block]:
    """Split YAML text into top-level record blocks (key or list item + body)."""
    live = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    base = min((_indent(ln) for ln in live), default=0)
    blocks: list[_Block] = []
    cur: _Block | None = None
    for offset, raw in enumerate(lines):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if cur is None or _indent(raw) <= base:
            cur = _Block(first_line + offset, "record", [], section, scope)
            blocks.append(cur)
        cur.prose.append(raw[base:])
    return blocks


def _segment_markdown(lines: list[str]) -> list[_Block]:
    """Split Markdown into claim-sized blocks, keeping pasted output as evidence.

    A pasted (non-YAML) fenced block attaches to the paragraph, list item or
    claim heading above it, even across one blank line; a YAML fence becomes
    its own record blocks.
    """
    blocks: list[_Block] = []
    cur: _Block | None = None  # open block that continues across lines
    anchor: _Block | None = None  # block that a fenced block attaches to
    heads: list[tuple[int, str]] = []
    section = 0
    fence: str | None = None
    fence_yaml = False
    yaml_lines: list[str] = []
    yaml_start = 0
    header: list[str] | None = None
    seen_separator = False
    blank = False

    def scope() -> str:
        return " / ".join(text for _, text in heads)

    for number, raw in enumerate(lines, start=1):
        if fence is not None:
            if raw.strip().startswith(fence):
                if fence_yaml:
                    blocks.extend(
                        _segment_yaml(yaml_lines, yaml_start, section, scope())
                    )
                fence = None
            elif fence_yaml:
                yaml_lines.append(raw)
            elif anchor is not None:
                anchor.fenced.append(raw)
            continue
        opened = _FENCE_RE.match(raw)
        if opened:
            fence, fence_yaml = opened.group(1), opened.group(2).lower() in _YAML_LANGS
            yaml_lines, yaml_start = [], number + 1
            continue
        stripped = raw.strip()
        if not stripped:
            blank, header = True, None
            if cur is not None and cur.kind == "para":
                cur = None
            continue
        heading = _HEADING_RE.match(raw)
        if heading:
            level = len(heading.group(1))
            heads = [(lv, tx) for lv, tx in heads if lv < level]
            heads.append((level, heading.group(2)))
            section, header, blank, cur, anchor = section + 1, None, False, None, None
            if _claim_kind(heading.group(2)) == KIND_CLAIM:
                cur = anchor = _Block(number, "heading", [raw], section, scope())
                blocks.append(cur)
            continue
        was_blank, blank = blank, False
        if cur is not None and cur.kind == "heading":
            cur.prose.append(raw)
            continue
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if header is None:
                header, seen_separator = [c.lower() for c in cells], False
            elif not seen_separator and _SEPARATOR_RE.match(stripped):
                seen_separator = True
            else:
                row = _Block(number, "row", [raw], section, scope())
                row.cells = dict(zip(header, cells, strict=False))
                blocks.append(row)
            cur = anchor = None
            continue
        header = None
        indent = _indent(raw)
        if _ITEM_RE.match(raw) and (
            cur is None or cur.kind != "item" or indent <= cur.indent
        ):
            cur = anchor = _Block(number, "item", [raw], section, scope(), indent)
            blocks.append(cur)
        elif (
            cur is not None
            and cur.kind == "item"
            and (indent > cur.indent or not was_blank)
        ) or (cur is not None and cur.kind == "para"):
            cur.prose.append(raw)
        else:
            cur = anchor = _Block(number, "para", [raw], section, scope())
            blocks.append(cur)
    if fence is not None and fence_yaml:  # an unclosed fence runs to the end
        blocks.extend(_segment_yaml(yaml_lines, yaml_start, section, scope()))
    return blocks


def _split(block: _Block) -> list[_Block]:
    """Judge a nested block child by child when two or more children are claims."""
    if block.kind not in ("item", "record") or len(block.prose) < 3:
        return [block]
    own_indent = _indent(block.prose[0])
    deeper = [_indent(ln) for ln in block.prose[1:] if ln.strip()]
    child_indent = min(deeper, default=own_indent)
    if child_indent <= own_indent:
        return [block]
    starts = [
        i
        for i, ln in enumerate(block.prose)
        if i > 0
        and _indent(ln) == child_indent
        and (_ITEM_RE.match(ln) or _KEY_RE.match(ln))
    ]
    if len(starts) < 2:
        return [block]
    parent = "\n".join(block.prose[: starts[0]])
    bounds = [*starts, len(block.prose)]
    children = [
        replace(
            block,
            line=block.line + lo,
            prose=block.prose[lo:hi],
            scope=f"{block.scope}\n{parent}",
            indent=child_indent,
            fenced=[],
        )
        for lo, hi in pairwise(bounds)
    ]
    is_claim = [_claim_kind(c.text) is not None for c in children]
    if sum(is_claim) < 2:
        return [block]
    # A key or bullet that is no claim (``command:``, ``exit:``, ``head:``, a
    # "Run: ..." line) is evidence the claims beside it may lean on.
    siblings = "\n".join(
        c.text for c, claim in zip(children, is_claim, strict=True) if not claim
    )
    return [
        piece
        for child, claim in zip(children, is_claim, strict=True)
        for piece in _split(
            replace(child, scope=f"{child.scope}\n{siblings}") if claim else child
        )
    ]


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _excerpt(block: _Block) -> str:
    first = next((ln.strip() for ln in block.prose if ln.strip()), "")
    return first[:_EXCERPT_CHARS]


def _has_bare_na(text: str) -> bool:
    """Return True when a ``key: n/a`` line gives no reason after the ``n/a``.

    Quotes around the ``n/a`` are ignored; a trailing ``# comment`` is a reason.
    """
    for match in _NA_LINE_RE.finditer(text):
        value, _, comment = match.group("value").partition(" #")
        if comment.strip():
            continue
        if value.strip().strip("'\"").strip().lower() == "n/a":
            return True
    return False


def _attestation_gaps(lines: list[str]) -> list[str]:
    """Return what a ``conformity-attestation`` block omits (rule section 2)."""
    text = "\n".join(lines)
    gaps: list[str] = []
    for key in ("artifact", "ecosystem-version", "date"):
        found = re.search(rf"^\s*{key}\s*:[ \t]*(.*)$", text, re.MULTILINE)
        value = found.group(1) if found else ""
        if not found or _is_placeholder(value):
            gaps.append(f"{key} (absent or unfilled)")
        elif key == "date" and not _ISO_DATE_RE.match(value.strip().strip("'\"")):
            gaps.append("date (not ISO-8601)")
    gaps.extend(
        f"{key} (array not written out)"
        for key in _ATTESTATION_ARRAYS
        if not re.search(rf"^\s*{key}\s*:", text, re.MULTILINE)
    )
    bars = {int(n) for n in _BAR_KEY_RE.findall(text)}
    absent = [n for n in range(1, _BAR_COUNT + 1) if n not in bars]
    if absent:
        gaps.append("bar lines " + ", ".join(f"M{n}" for n in absent))
    if _has_bare_na(text):
        gaps.append("n/a without a reason")
    return gaps


def _gap_detail(missing: list[str], what: str) -> str:
    return (
        f"{what} is missing {', '.join(missing)}; record the command, its exit "
        f"status or output, and the HEAD sha beside the claim "
        f"(commands/plan-execute.md, Gate evidence)"
    )


def _inspect_file(
    path: Path, root: Path, suite: str
) -> tuple[list[Finding], int] | None:
    """Return ``(findings, claims)`` for one file, or None when unreadable."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    if path.suffix in _YAML_SUFFIXES:
        raw_blocks = _segment_yaml(lines, 1, 0, path.name)
    else:
        raw_blocks = _segment_markdown(lines)
    surface = _rel(path, root)
    findings: list[Finding] = []
    pending: list[Finding] = []
    claims = complete = 0
    paragraphs: dict[int, list[str]] = {}

    def finding(block: _Block, kind: str, missing: list[str], what: str) -> Finding:
        return Finding(
            surface,
            suite,
            block.line,
            kind,
            block.kind,
            _excerpt(block),
            missing,
            _gap_detail(missing, what),
        )

    for raw_block in raw_blocks:
        if raw_block.kind == "record" and raw_block.prose[0].lstrip().startswith(
            _ATTESTATION_ROOT
        ):
            gaps = _attestation_gaps(raw_block.prose)
            if gaps:
                findings.append(
                    Finding(
                        surface,
                        suite,
                        raw_block.line,
                        KIND_ATTESTATION,
                        raw_block.kind,
                        _excerpt(raw_block),
                        gaps,
                        "attestation block omits "
                        + "; ".join(gaps)
                        + " (rules/pre-emission-gate-bars.md, section 2)",
                    )
                )
            continue  # judged by the schema alone, not as a prose gate claim
        for block in _split(raw_block):
            kind = _claim_kind(block.text)
            context = paragraphs.get(block.section, [])
            if kind is not None:
                claims += 1
                found = _found_items(block, context)
                missing = [item for item in _ITEMS if item not in found]
                if not missing:
                    complete += 1
                elif kind == KIND_ROLLUP:
                    pending.append(finding(block, kind, missing, "roll-up gate claim"))
                else:
                    findings.append(finding(block, kind, missing, "gate claim"))
            if block.kind in ("para", "item") and kind is None:
                paragraphs.setdefault(block.section, []).append(
                    "\n".join([*block.prose, *block.fenced])
                )
    if not complete:
        findings.extend(pending)
    return findings, claims


def _suite_dirs(root: Path) -> list[Path]:
    """Return the suite directories to inspect for *root*."""
    plans = root.joinpath(*APOTHEM_PLANS_RELPATH)
    if plans.is_dir():
        return sorted(p for p in plans.iterdir() if p.is_dir())
    if root.name == APOTHEM_PLANS_RELPATH[1] and root.parent.name == ".apothem":
        return sorted(p for p in root.iterdir() if p.is_dir())
    if (root / "PROGRESS.md").is_file() or (root / "phases").is_dir():
        return [root]
    return []


def _suite_files(suite: Path) -> list[Path]:
    """Return the report, progress and attestation files of one suite."""
    files = [suite / name for name in _ROOT_FILES if (suite / name).is_file()]
    files.extend(sorted(suite.rglob("REPORT.md")))
    for name in _ATTESTATION_FILES:
        files.extend(sorted(suite.rglob(name)))
    manifest = suite.joinpath(*_MANIFEST_RELPATH)
    if manifest.is_file():
        files.append(manifest)
    return files


def check(root: Path) -> GrepResult:
    """Walk every plan suite under *root* for gate claims lacking evidence.

    Pre-conditions: *root* is a project root (holding ``.apothem/plans/``), the
    plans directory, or a single suite directory. Post-conditions:
    ``passed`` is True when no claim or attestation block lacks evidence; a
    root with no suite inspects nothing and passes.
    """
    findings: list[Finding] = []
    notes: list[str] = []
    suites = _suite_dirs(root)
    files_inspected = claims_inspected = 0
    for suite in suites:
        for path in _suite_files(suite):
            outcome = _inspect_file(path, root, suite.name)
            if outcome is None:
                notes.append(f"{_rel(path, root)}: not readable as UTF-8 text")
                continue
            files_inspected += 1
            claims_inspected += outcome[1]
            findings.extend(outcome[0])
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        suites_inspected=len(suites),
        files_inspected=files_inspected,
        claims_inspected=claims_inspected,
        passed=not findings,
        findings=findings,
        notes=notes,
    )


def _read_input(argv: list[str]) -> tuple[Path, bool]:
    """Return ``(root, strict)`` parsed from argv; root defaults to cwd.

    Usage errors (unknown flag, a root that is not an existing directory) exit
    ``EXIT_USAGE`` (3); ``--help`` exits 0.
    """

    def _configure(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            STRICT_FLAG,
            dest="strict",
            action="store_true",
            help="exit non-zero when a gate claim lacks its evidence",
        )

    args = parse_root_args(argv, prog=GREP_NAME, doc=__doc__, configure=_configure)
    return args.root, bool(args.strict)


def _main(argv: list[str]) -> int:
    root, strict = _read_input(argv)
    result = check(root)
    # Plan suites live under the gitignored ``.apothem/plans/`` tree, so a
    # clean checkout legitimately carries none: an empty scope is expected.
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=result.files_inspected,
        empty_scope_expected=True,
        advisory=not strict,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
