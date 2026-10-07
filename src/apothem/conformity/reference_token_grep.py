# SPDX-License-Identifier: MIT

"""Flag leaked reference-platform branding tokens on authored surfaces.

Why this enforcement exists. Apothem reimplements a peer platform's
feature-set in its own voice; the own-voice discipline requires that no
authored surface — rules, commands, skills, agents, documentation, brand
assets — leak the reference platform's slug or brand vocabulary. A
mechanical sweep proves zero in-scope hits so the product narrative reads
as its own work rather than as a paraphrase of the reference platform.

Scope. Corpus-level standalone validator. Walks the working tree under the
supplied root and inspects ONLY authored in-scope surfaces (the rules,
commands, skills, agents directories, the documentation tree, and the
brand-asset tree). The denylist data file, the conformity machinery, the
schemas directory, the test tree, and the plan-suite scratch are all
exempt — they are not the authored product narrative the discipline holds
to the zero-leak bar.

Detection. The denylist data file holds a SHA-256 digest of each forbidden
token rather than the token, so neither this module nor the data file
carries a token in readable, searchable form. A digest does not hide a
token: a short name can be recovered by exhaustive search, or confirmed by
hashing a guess. Matching is case-insensitive with the same folding as
``re.IGNORECASE``. A ``word`` entry is a pure-alpha token: every maximal run
of word characters is folded and hashed, which is the same match as
``\\btoken\\b``. A ``literal <n>`` entry is an ``n``-character token that
carries a ``.`` or ``-``: every ``n``-character window of a word-dot-hyphen
run is folded and hashed, which is the same match as an escaped literal. A
word hit that lies inside a literal hit is reported once, as the literal.
Generate entries with ``scripts/dev/hash_reference_tokens.py``.

Posture. The result is advisory: the sweep surfaces findings and never
silent-blocks by default, honoring apothem's agnostic gate posture. CI
opts into strict enforcement separately. Per the gate's advisory contract
(``gate.py`` ``Advisory validators exit 0 even when they report
findings``), ``_main`` always exits 0 — the verdict travels in the JSON
``passed`` field, which the orchestrator reads via
``gate._advisory_verdict`` and surfaces as ``advisory_findings_present``
without failing the ``gate --all`` run.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "reference-token-grep"
RULE_ANCHOR: Final[str] = "rules/own-voice-reimplementation.md"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# The denylist data file is package-relative: the conformity package ships
# beside its ``schemas/`` sibling in both supported layouts — the repo
# checkout (``src/apothem/{conformity,schemas}``) and the installed tree
# (``<install-root>/apothem/{conformity,schemas}``) — so one parent hop
# from this module reaches it in either shape. The data file holds digests
# of the forbidden tokens, so neither file carries a token as text.
_DENYLIST_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1] / "schemas" / "reference-token-denylist.txt"
)

# Denylist entry grammar. ``word`` digests match a whole run of word
# characters; ``literal <n>`` digests match an ``n``-character window that
# contains a ``.`` or ``-``.
_WORD_ENTRY: Final[re.Pattern[str]] = re.compile(r"^word sha256:([0-9a-f]{64})$")
_LITERAL_ENTRY: Final[re.Pattern[str]] = re.compile(
    r"^literal ([1-9][0-9]{0,2}) sha256:([0-9a-f]{64})$"
)

# Candidate spans. A ``\btoken\b`` match of a pure-alpha token is exactly a
# maximal run of word characters equal to the token. An escaped-literal match
# of a dot- or hyphen-bearing token lies inside a maximal run of word, dot,
# and hyphen characters; runs without a dot or hyphen are skipped. Both
# patterns are a single character class, so a scan is linear in line length.
_WORD_RUN: Final[re.Pattern[str]] = re.compile(r"\w+")
_LITERAL_RUN: Final[re.Pattern[str]] = re.compile(r"[\w.\-]+")
# A literal token starts and ends with a letter or digit, so a window whose
# first or last character is not alphanumeric is skipped without hashing.
_LITERAL_TOKEN: Final[re.Pattern[str]] = re.compile(
    r"[^\W_][\w.\-]*[.\-][\w.\-]*[^\W_]"
)

# Case folding. ``re.IGNORECASE`` also matches U+017F (long s) to ``s``,
# U+0131 (dotless i) and U+0130 (capital I with dot) to ``i``, and U+212A
# (Kelvin sign) to ``k``; ``str.lower`` alone leaves the first two as they
# are and turns U+0130 into two characters. Translating those four first
# gives the same verdict as ``re.IGNORECASE`` for every ASCII token, and keeps
# every folded string the same length as its source.
_FOLD: Final[dict[int, str]] = {0x17F: "s", 0x131: "i", 0x130: "i", 0x212A: "k"}

# Authored in-scope surface roots (relative to the supplied root). Only text
# files under these directories are scanned.
_IN_SCOPE_DIRS: Final[tuple[str, ...]] = (
    "src/apothem/rules",
    "src/apothem/commands",
    "src/apothem/skills",
    "src/apothem/agents",
    "site/content/docs",
    "assets",
)

# Text-file suffixes scanned under the in-scope roots.
_TEXT_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".md", ".mdx", ".txt", ".svg", ".json", ".yaml", ".yml"}
)

# Exempt path fragments. A candidate whose POSIX-relative path contains any
# of these fragments is never scanned — the conformity machinery, the
# schemas data files (the denylist itself), the test tree, and the
# plan-suite scratch are not authored product narrative.
_EXEMPT_FRAGMENTS: Final[tuple[str, ...]] = (
    ".plans/",
    "tests/",
    "src/apothem/conformity/",
    "src/apothem/schemas/",
)


@dataclass(frozen=True)
class Finding:
    """One leaked reference-platform token on an authored surface."""

    surface: str
    kind: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class Denylist:
    """Parsed denylist: word digests, literal digests by length, bad lines."""

    words: frozenset[str] = frozenset()
    literals: dict[int, frozenset[str]] = field(default_factory=dict)
    malformed_lines: tuple[int, ...] = ()

    @property
    def empty(self) -> bool:
        """Return True when the denylist carries no usable entry."""
        return not self.words and not self.literals


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result for a single corpus sweep."""

    grep: str
    root: str
    files_inspected: int
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, files_inspected,
        passed, findings, advisory}``; each finding is flattened through
        ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "files_inspected": self.files_inspected,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
            "advisory": True,
        }
        return json.dumps(payload, indent=2)


def _fold(text: str) -> str:
    """Return ``text`` case-folded the way ``re.IGNORECASE`` compares letters."""
    return text.translate(_FOLD).lower()


def _sha256(text: str) -> str:
    """Return the lowercase hex SHA-256 digest of ``text`` encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_entry(token: str) -> str:
    """Return the denylist line that forbids ``token``.

    Pre-conditions: ``token`` is ASCII and either pure-alpha or a run of word,
    dot, and hyphen characters that starts and ends with a letter or digit and
    carries at least one dot or hyphen.
    Post-conditions: returns ``word sha256:<hex>`` or
    ``literal <n> sha256:<hex>``; the plaintext token is not in the result.

    Raises:
        ValueError: when ``token`` has neither accepted shape.
    """
    folded = _fold(token.strip())
    if folded.isascii() and folded.isalpha():
        return f"word sha256:{_sha256(folded)}"
    if folded.isascii() and _LITERAL_TOKEN.fullmatch(folded):
        return f"literal {len(folded)} sha256:{_sha256(folded)}"
    raise ValueError(
        "a denylist token must be ASCII: letters only, or letters and digits "
        "joined by '.' or '-'"
    )


def _load_denylist(path: Path | None = None) -> Denylist:
    """Parse the denylist data file into digest sets.

    Pre-conditions: ``path`` (default :data:`_DENYLIST_PATH`) is the data file.
    Post-conditions: every ``word`` / ``literal`` line is parsed; any other
    non-empty, non-comment line is recorded in ``malformed_lines``. A missing
    or unreadable file yields an empty denylist.
    """
    try:
        raw = (path or _DENYLIST_PATH).read_text(encoding="utf-8")
    except OSError:
        return Denylist()
    words: set[str] = set()
    literals: dict[int, set[str]] = {}
    malformed: list[int] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        word = _WORD_ENTRY.match(stripped)
        if word:
            words.add(word.group(1))
            continue
        literal = _LITERAL_ENTRY.match(stripped)
        if literal:
            literals.setdefault(int(literal.group(1)), set()).add(literal.group(2))
            continue
        malformed.append(line_number)
    return Denylist(
        words=frozenset(words),
        literals={length: frozenset(d) for length, d in sorted(literals.items())},
        malformed_lines=tuple(malformed),
    )


def _word_hit(run: str, denylist: Denylist, memo: dict[str, bool]) -> bool:
    """Return True when the word run ``run`` folds to a denylisted word.

    ``memo`` caches the verdict per raw run across the whole sweep: the corpus
    repeats a small vocabulary, so most runs are folded and hashed once.
    """
    verdict = memo.get(run)
    if verdict is None:
        verdict = _sha256(_fold(run)) in denylist.words
        memo[run] = verdict
    return verdict


def _literal_hits(
    run: str,
    denylist: Denylist,
    literal_memo: dict[str, tuple[tuple[int, int], ...]],
) -> tuple[tuple[int, int], ...]:
    """Return ``(start, length)`` for each denylisted window of a literal run.

    A window is hashed only when it starts and ends with a letter or digit and
    carries a dot or hyphen, the shape every literal entry has. The run is
    folded once; folding keeps its length, so window offsets index the raw run.
    ``literal_memo`` caches the result per raw run across the whole sweep.
    """
    cached = literal_memo.get(run)
    if cached is not None:
        return cached
    folded = _fold(run)
    hits: list[tuple[int, int]] = []
    for length, digests in denylist.literals.items():
        for start in range(len(folded) - length + 1):
            window = folded[start : start + length]
            if not (window[0].isalnum() and window[-1].isalnum()):
                continue
            if "." not in window and "-" not in window:
                continue
            if _sha256(window) in digests:
                hits.append((start, length))
    found = tuple(hits)
    literal_memo[run] = found
    return found


def _text_has_hit(
    text: str,
    denylist: Denylist,
    memo: dict[str, bool],
    literal_memo: dict[str, tuple[tuple[int, int], ...]],
) -> bool:
    """Return True when any line of ``text`` would yield a finding.

    No word run or literal run crosses a line break, so the whole text is
    scanned at once: each distinct word-dot-hyphen run is checked once, its
    dot- and hyphen-separated parts as word runs and the run itself for
    literal windows. A file without a hit, the common case, is never split
    into lines.
    """
    shortest = min(denylist.literals, default=0)
    for run in set(_LITERAL_RUN.findall(text)):
        if "." not in run and "-" not in run:
            if _word_hit(run, denylist, memo):
                return True
            continue
        parts = run.replace("-", ".").split(".")
        if any(part and _word_hit(part, denylist, memo) for part in parts):
            return True
        if (
            shortest
            and len(run) >= shortest
            and _literal_hits(run, denylist, literal_memo)
        ):
            return True
    return False


def _drop_nested(hits: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Return ``(start, end)`` hits in line order, minus any inside another.

    A literal token can contain a word token, so one occurrence can give a
    literal hit with a word hit inside it; reporting both would count that
    occurrence twice.
    """
    kept: list[tuple[int, int]] = []
    for start, end in sorted(set(hits), key=lambda hit: (hit[0], -hit[1])):
        if any(k_start <= start and end <= k_end for k_start, k_end in kept):
            continue
        kept.append((start, end))
    return kept


def _line_matches(
    line: str,
    denylist: Denylist,
    memo: dict[str, bool],
    literal_memo: dict[str, tuple[tuple[int, int], ...]],
) -> list[str]:
    """Return the spans of ``line`` whose folded digest is denylisted.

    One span per occurrence, in line order; a word hit inside a literal hit is
    dropped. ``memo`` and ``literal_memo`` cache verdicts across the sweep.
    """
    hits = [
        run.span()
        for run in _WORD_RUN.finditer(line)
        if _word_hit(run.group(), denylist, memo)
    ]
    if denylist.literals and ("." in line or "-" in line):
        shortest = min(denylist.literals)
        for run in _LITERAL_RUN.finditer(line):
            text = run.group()
            if len(text) < shortest or ("." not in text and "-" not in text):
                continue
            base = run.start()
            hits.extend(
                (base + start, base + start + size)
                for start, size in _literal_hits(text, denylist, literal_memo)
            )
    if len(hits) > 1:
        hits = _drop_nested(hits)
    return [line[start:end] for start, end in hits]


def _is_in_scope(rel_posix: str) -> bool:
    """Return True iff a relative POSIX path is an authored in-scope surface."""
    for fragment in _EXEMPT_FRAGMENTS:
        if fragment in rel_posix or rel_posix.startswith(fragment.rstrip("/")):
            return False
    return any(rel_posix == d or rel_posix.startswith(d + "/") for d in _IN_SCOPE_DIRS)


def _scan_file(
    path: Path,
    rel_posix: str,
    denylist: Denylist,
    memo: dict[str, bool],
    literal_memo: dict[str, tuple[tuple[int, int], ...]],
) -> list[Finding]:
    """Scan one text file; return one Finding per denylisted span."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if not _text_has_hit(content, denylist, memo, literal_memo):
        return []
    findings: list[Finding] = []
    for line_index, line in enumerate(content.splitlines(), start=1):
        for span in _line_matches(line, denylist, memo, literal_memo):
            findings.append(
                Finding(
                    surface=rel_posix,
                    kind="reference-token",
                    detail=f"line {line_index}: '{span}'",
                )
            )
    return findings


def check(root: Path) -> GrepResult:
    """Walk the corpus under ``root``; flag leaked reference-platform tokens.

    Pre-conditions: ``root`` is the repository root (or an arbitrary subtree).
    Post-conditions: ``result.passed`` is True iff the denylist parsed cleanly
    and every authored in-scope text file contained zero denylisted tokens.
    """
    denylist = _load_denylist()
    findings: list[Finding] = [
        Finding(
            surface="schemas/reference-token-denylist.txt",
            kind="denylist-entry-malformed",
            detail=f"line {line_number}: not a 'word' or 'literal <n>' digest entry",
        )
        for line_number in denylist.malformed_lines
    ]
    inspected = 0
    root_resolved = root.resolve()
    memo: dict[str, bool] = {}
    literal_memo: dict[str, tuple[tuple[int, int], ...]] = {}
    if not denylist.empty:
        for suffix in sorted(_TEXT_SUFFIXES):
            for path in root.rglob(f"*{suffix}"):
                if not path.is_file():
                    continue
                try:
                    rel_posix = path.resolve().relative_to(root_resolved).as_posix()
                except ValueError:
                    continue
                if not _is_in_scope(rel_posix):
                    continue
                inspected += 1
                findings.extend(
                    _scan_file(path, rel_posix, denylist, memo, literal_memo)
                )
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        files_inspected=inspected,
        passed=not findings,
        findings=findings,
    )


def _main(argv: list[str]) -> int:
    # Imported here, not at module top: ``check()`` stays stdlib-only; only
    # the command-line entry needs the shared parser and report stamp.
    from apothem.conformity._grep_base import finish_root_report, parse_root_args

    root = parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root
    result = check(root)
    # Advisory posture: ``to_json`` declares ``advisory: true``, so ``_main``
    # exits 0 even when findings are present (gate.py: "Advisory validators
    # exit 0 even when they report findings"). The verdict rides the JSON
    # ``passed`` field; the orchestrator surfaces it as
    # ``advisory_findings_present`` without failing ``gate --all``. A scan
    # that read no file is not advisory drift: it fails.
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=result.files_inspected,
        advisory=True,
    )


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
