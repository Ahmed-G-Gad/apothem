# SPDX-License-Identifier: MIT

"""Tests for the reference-token leak matcher.

The matcher proves zero reference-platform branding leaks across authored
in-scope surfaces (rules, commands, skills, agents, docs, assets). The shipped
denylist holds SHA-256 digests rather than tokens, so these tests never use a
real token: they hash invented tokens into a scratch denylist and point the
matcher at it. They cover the digest grammar of the shipped file, a scan of
every repository file with the shipped digests, the in-scope pass and fail
paths, exemptions, the advisory JSON flag, word-boundary and literal
semantics, Unicode case folding, one finding per literal occurrence, scan time
on long lines, and line-level parity with the plaintext regex the digests
replaced.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import string
import subprocess
import sys
import time
from pathlib import Path

import pytest

from apothem.conformity import reference_token_grep as rtg

_FIXTURE_DIR = Path(__file__).resolve().parent / "reference-token-grep"
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Invented tokens. Two pure-alpha words, then dot- or hyphen-bearing literals:
# one that starts with a word token, one that joins both word tokens, and one
# with no word token inside. Between them they carry an s, an i and a k, the
# ASCII letters that re.IGNORECASE also matches to a non-ASCII character.
_WORDS = ("skivorn", "quimble")
_LITERALS = ("skivorn.example", "skivorn-quimble", "quill-mark")
_TOKENS = (*_WORDS, *_LITERALS)

# The non-ASCII characters re.IGNORECASE treats as an ASCII letter: long s,
# dotless i, capital I with dot, and the Kelvin sign.
_LONG_S, _DOTLESS_I, _DOTTED_I, _KELVIN = "\u017f", "\u0131", "\u0130", "\u212a"
_CASE_PARTNERS = {"s": _LONG_S, "i": _DOTLESS_I + _DOTTED_I, "k": _KELVIN}

# Characters in the long-line scan-time cases.
_LONG_LINE = 50_000


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def synthetic_denylist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the matcher at a scratch denylist built from the invented tokens."""
    path = tmp_path / "_denylist" / "reference-token-denylist.txt"
    entries = "\n".join(rtg.digest_entry(token) for token in _TOKENS)
    _write(path, f"# SPDX-License-Identifier: MIT\n{entries}\n")
    monkeypatch.setattr(rtg, "_DENYLIST_PATH", path)
    return path


def _plaintext_pattern(tokens: tuple[str, ...]) -> re.Pattern[str]:
    """Return the plaintext regex the digest matcher replaced (the oracle)."""
    alternatives = [
        (r"\b" + re.escape(t) + r"\b") if t.isalpha() else re.escape(t) for t in tokens
    ]
    return re.compile(r"(?i)(?:" + "|".join(alternatives) + r")")


def _flagged(text: str) -> bool:
    return bool(rtg._line_matches(text, rtg._load_denylist(), {}, {}))


def test_shipped_denylist_is_digest_only() -> None:
    denylist = rtg._load_denylist()
    assert not denylist.empty, "denylist parsed to no entry"
    assert denylist.malformed_lines == (), (
        "every non-comment line must be a 'word' or 'literal <n>' digest entry; "
        f"offending lines: {denylist.malformed_lines}"
    )


def test_no_repository_file_carries_a_denylisted_token() -> None:
    # The validator reads authored surfaces only, so it misses a token that
    # returns in a test, a fixture, a README or a template. No file in
    # the repository needs a plaintext token now, so this scan of every
    # tracked or new text file exempts nothing, the denylist included. A
    # failure names the file and line, never the matched text.
    if not (_REPO_ROOT / ".git").exists():
        pytest.skip("not a git checkout; a release archive ships tests without .git")
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not installed")
    listed = subprocess.run(
        [
            git,
            "-C",
            str(_REPO_ROOT),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    # Generated copies repeat many files byte for byte; each distinct content
    # is scanned once and a hit is reported at every path that holds it.
    paths_by_content: dict[bytes, list[str]] = {}
    for relative in filter(None, listed.split("\0")):
        try:
            data = (_REPO_ROOT / relative).read_bytes()
        except OSError:
            continue
        if b"\0" not in data:
            paths_by_content.setdefault(data, []).append(relative)
    assert len(paths_by_content) > 1000
    denylist = rtg._load_denylist()
    assert not denylist.empty
    memo: dict[str, bool] = {}
    literal_memo: dict[str, tuple[tuple[int, int], ...]] = {}
    hits: list[str] = []
    for data, paths in paths_by_content.items():
        text = data.decode("utf-8", errors="replace")
        if not rtg._text_has_hit(text, denylist, memo, literal_memo):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if rtg._line_matches(line, denylist, memo, literal_memo):
                hits.extend(f"{path}:{number}" for path in paths)
    assert hits == [], f"a denylisted token appears at: {hits}"


def test_digest_entry_never_contains_the_token() -> None:
    for token in _TOKENS:
        entry = rtg.digest_entry(token)
        assert token not in entry
        assert re.fullmatch(r"(word|literal \d+) sha256:[0-9a-f]{64}", entry)
    assert rtg.digest_entry("SkiVorn") == rtg.digest_entry("skivorn")
    assert rtg.digest_entry(f"{_LONG_S}K{_DOTTED_I}VORN") == rtg.digest_entry("skivorn")
    assert rtg.digest_entry(f"QUILL-MAR{_KELVIN}") == rtg.digest_entry("quill-mark")


@pytest.mark.parametrize(
    "token", ["", "two words", "abc123", "-lead", "trail.", "a/b", "caf\u00e9"]
)
def test_digest_entry_rejects_unsupported_shapes(token: str) -> None:
    with pytest.raises(ValueError, match="denylist token"):
        rtg.digest_entry(token)


@pytest.mark.usefixtures("synthetic_denylist")
def test_clean_in_scope_file_passes(tmp_path: Path) -> None:
    clean = (_FIXTURE_DIR / "pass.md").read_text(encoding="utf-8")
    _write(tmp_path / "src" / "apothem" / "rules" / "clean.md", clean)
    result = rtg.check(tmp_path)
    assert result.passed
    assert result.findings == []
    assert result.files_inspected == 1


@pytest.mark.usefixtures("synthetic_denylist")
def test_reference_token_in_scope_file_fails(tmp_path: Path) -> None:
    leaky = (_FIXTURE_DIR / "fail.md").read_text(encoding="utf-8")
    _write(tmp_path / "src" / "apothem" / "rules" / "leaky.md", leaky)
    result = rtg.check(tmp_path)
    assert not result.passed
    assert {f.surface for f in result.findings} == {"src/apothem/rules/leaky.md"}
    assert {f.kind for f in result.findings} == {"reference-token"}
    reported = [f.detail.split("'")[1].lower() for f in result.findings]
    # One finding per occurrence: each token appears once in the fixture.
    assert sorted(reported) == sorted(_TOKENS)


@pytest.mark.usefixtures("synthetic_denylist")
def test_token_only_in_exempt_location_passes(tmp_path: Path) -> None:
    # Reference tokens under exempt trees must not be flagged.
    leaky = (_FIXTURE_DIR / "fail.md").read_text(encoding="utf-8")
    _write(tmp_path / "tests" / "conformity" / "fixture.md", leaky)
    _write(tmp_path / ".plans" / "suite" / "notes.md", "skivorn here.\n")
    _write(tmp_path / "src" / "apothem" / "schemas" / "notes.txt", "skivorn\n")
    result = rtg.check(tmp_path)
    assert result.passed
    assert result.findings == []


def test_to_json_includes_advisory_flag(tmp_path: Path) -> None:
    result = rtg.check(tmp_path)
    payload = json.loads(result.to_json())
    assert payload["advisory"] is True


@pytest.mark.usefixtures("synthetic_denylist")
@pytest.mark.parametrize(
    ("text", "flagged"),
    [
        ("Skivorn ships", True),
        ("(skivorn)", True),
        ("skivorn-based", True),
        (f"{_LONG_S}kivorn", True),
        (f"SK{_DOTTED_I}VORN", True),
        (f"sk{_DOTLESS_I}vorn", True),
        (f"S{_KELVIN}IVORN", True),
        ("preskivorned", False),
        ("skivorns", False),
        ("skivorn_id", False),
        ("skivorn1", False),
        ("sk\u0131\u0307vorn", False),
    ],
)
def test_word_entries_match_whole_words(text: str, flagged: bool) -> None:
    assert (_plaintext_pattern(_TOKENS).search(text) is not None) is flagged
    assert _flagged(f"# R {text} end") is flagged


@pytest.mark.usefixtures("synthetic_denylist")
@pytest.mark.parametrize(
    ("text", "flagged"),
    [
        ("https://www.skivorn.example/path", True),
        ("SKIVORN.EXAMPLE", True),
        ("theskivorn.examples", True),
        ("quill-marks", True),
        (f"QUILL-MAR{_KELVIN}", True),
        (f"qu{_DOTLESS_I}ll-mark", True),
        (f"QU{_DOTTED_I}LL-MARK", True),
        ("quill mark", False),
        ("quill_mark", False),
        ("quill.mark", False),
        ("quil-mark", False),
    ],
)
def test_literal_entries_match_as_escaped_literals(text: str, flagged: bool) -> None:
    assert (_plaintext_pattern(_TOKENS).search(text) is not None) is flagged
    assert _flagged(f"# R {text} end") is flagged


@pytest.mark.usefixtures("synthetic_denylist")
@pytest.mark.parametrize(
    ("line", "spans"),
    [
        ("see skivorn.example now", ["skivorn.example"]),
        ("see SKIVORN-QUIMBLE now", ["SKIVORN-QUIMBLE"]),
        ("skivorn and skivorn.example", ["skivorn", "skivorn.example"]),
        ("quimble, skivorn-quimble.", ["quimble", "skivorn-quimble"]),
        ("skivorn-quimble.example", ["skivorn-quimble"]),
        ("skivorn.example skivorn.example", ["skivorn.example", "skivorn.example"]),
    ],
)
def test_word_inside_a_literal_is_reported_once(line: str, spans: list[str]) -> None:
    # A literal hit that carries a word hit is one occurrence, so it yields
    # one finding, named by the literal. A word hit outside every literal hit
    # is still its own finding.
    found = rtg._line_matches(line, rtg._load_denylist(), {}, {})
    assert sorted(found) == sorted(spans)


def test_fold_agrees_with_ignorecase_for_every_character() -> None:
    # Digest matching is exact only when folding a character gives the ASCII
    # token character that re.IGNORECASE would match it to, and keeps lengths.
    token_chars = string.ascii_lowercase + string.digits + ".-"
    ignorecase_class = re.compile(r"(?i)[a-z0-9.\-]")
    for code_point in range(sys.maxunicode + 1):
        char = chr(code_point)
        folded = rtg._fold(char)
        assert len(folded) == 1, f"U+{code_point:04X} folds to {len(folded)} characters"
        if folded in token_chars or ignorecase_class.fullmatch(char):
            assert folded in token_chars, f"U+{code_point:04X}"
            assert re.fullmatch("(?i)" + re.escape(folded), char), f"U+{code_point:04X}"


def _variant(token: str, rng: random.Random, alphabet: str) -> str:
    """Return ``token`` in a random case, at times with a case partner or an edit."""
    text = rng.choice([token, token.upper(), token.title(), token.swapcase()])
    partner_slots = [i for i, c in enumerate(text) if c.lower() in _CASE_PARTNERS]
    if partner_slots and rng.random() < 0.4:
        slot = rng.choice(partner_slots)
        text = (
            text[:slot]
            + rng.choice(_CASE_PARTNERS[text[slot].lower()])
            + text[slot + 1 :]
        )
    if rng.random() < 0.3:
        slot = rng.randrange(len(text))
        edit = rng.choice(["insert", "delete", "replace"])
        if edit == "insert":
            text = text[:slot] + rng.choice(alphabet) + text[slot:]
        elif edit == "delete":
            text = text[:slot] + text[slot + 1 :]
        else:
            text = text[:slot] + rng.choice(alphabet) + text[slot + 1 :]
    return text


@pytest.mark.usefixtures("synthetic_denylist")
def test_digest_matcher_has_line_parity_with_plaintext_regex() -> None:
    oracle = _plaintext_pattern(_TOKENS)
    denylist = rtg._load_denylist()
    rng = random.Random(20261007)  # noqa: S311 — seeded test input, not security
    partners = "".join(_CASE_PARTNERS.values())
    glue = [
        "",
        " ",
        "x",
        "_",
        "1",
        ".",
        "-",
        "/",
        "(",
        "www.",
        ".org",
        "\u00e9",
        "s",
        *partners,
    ]
    alphabet = string.ascii_lowercase + string.digits + "._- \u00e9" + partners
    flagged = 0
    for _ in range(10000):
        if rng.random() < 0.8:
            token = _variant(rng.choice(_TOKENS), rng, alphabet)
            line = f"lead {rng.choice(glue)}{token}{rng.choice(glue)} tail"
        else:
            line = "".join(rng.choice(alphabet) for _ in range(40))
        expected = oracle.search(line) is not None
        actual = bool(rtg._line_matches(line, denylist, {}, {}))
        assert actual is expected, ascii(line)
        assert rtg._text_has_hit(line, denylist, {}, {}) is expected, ascii(line)
        flagged += expected
    # Both verdicts are exercised in volume.
    assert 2000 < flagged < 9000


@pytest.mark.usefixtures("synthetic_denylist")
@pytest.mark.parametrize(
    "line",
    [
        "a" * _LONG_LINE + " x.y",
        "x-y " + "a" * _LONG_LINE,
        "0.1-" * (_LONG_LINE // 4),
    ],
    ids=["word-run-then-dot", "hyphen-then-word-run", "dot-hyphen-run"],
)
def test_long_lines_scan_in_linear_time(line: str) -> None:
    # A pattern that backtracks over a long word run took about 20 s on a
    # 50,000-character line; a linear scan takes milliseconds.
    denylist = rtg._load_denylist()
    started = time.perf_counter()
    rtg._line_matches(line, denylist, {}, {})
    assert time.perf_counter() - started < 2.0


def test_malformed_denylist_line_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "denylist.txt"
    _write(path, f"# comment\n{rtg.digest_entry('skivorn')}\nplaintext-token\n")
    monkeypatch.setattr(rtg, "_DENYLIST_PATH", path)
    result = rtg.check(tmp_path)
    assert not result.passed
    assert [f.kind for f in result.findings] == ["denylist-entry-malformed"]
    assert result.findings[0].detail.startswith("line 3:")
    assert "plaintext-token" not in result.findings[0].detail


def test_missing_denylist_is_a_vacuous_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(rtg, "_DENYLIST_PATH", tmp_path / "absent.txt")
    _write(tmp_path / "src" / "apothem" / "rules" / "r.md", "# R\n")
    assert rtg.check(tmp_path).files_inspected == 0
    # A scan that read no file has not earned a pass, even for an advisory
    # validator, so a deleted denylist cannot pass the repository's own gate.
    assert rtg._main(["reference-token-grep", str(tmp_path)]) == rtg.EXIT_FAIL
    assert json.loads(capsys.readouterr().out)["passed"] is False
