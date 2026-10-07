# SPDX-License-Identifier: MIT

"""Tests for scripts/dev/hash_reference_tokens.py.

The script turns tokens into reference-token denylist entries without the
tokens reaching an argument list or shell history. These tests use invented
tokens only and pin its output order, its ``--check`` verdicts, its exit codes,
and its hidden prompt on a terminal.
"""

from __future__ import annotations

import getpass
import io
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import hash_reference_tokens  # noqa: E402

from apothem.conformity.reference_token_grep import digest_entry  # noqa: E402

_TOKENS = ("quill-mark", "skivorn", "skivorn.example", "quimble")


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def _feed(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))


def test_prints_sorted_unique_entries(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _feed(monkeypatch, "\n".join([*_TOKENS, "SKIVORN", ""]) + "\n")
    assert hash_reference_tokens.main([]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert sorted(lines) == sorted({digest_entry(t) for t in _TOKENS})
    kinds = [line.split()[0] for line in lines]
    assert kinds == ["word", "word", "literal", "literal"]
    assert [int(line.split()[1]) for line in lines[2:]] == [10, 15]
    for token in _TOKENS:
        assert token not in out


def test_check_passes_when_every_token_has_an_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    denylist = tmp_path / "denylist.txt"
    entries = "\n".join(digest_entry(t) for t in _TOKENS)
    denylist.write_text(f"# header\n{entries}\n", encoding="utf-8")
    _feed(monkeypatch, "Skivorn\nquill-mark\n")
    assert hash_reference_tokens.main(["--check", "--denylist", str(denylist)]) == 0
    assert capsys.readouterr() == ("", "")


def test_check_names_the_missing_token_by_position_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    denylist = tmp_path / "denylist.txt"
    denylist.write_text(digest_entry("skivorn") + "\n", encoding="utf-8")
    _feed(monkeypatch, "skivorn\nquimble\n")
    assert hash_reference_tokens.main(["--check", "--denylist", str(denylist)]) == 1
    err = capsys.readouterr().err
    assert "token 2" in err
    assert "quimble" not in err


def test_committed_denylist_is_the_default_for_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _feed(monkeypatch, "skivorn\n")
    # An invented token has no entry in the committed denylist.
    assert hash_reference_tokens.main(["--check"]) == 1


@pytest.mark.parametrize("text", ["", "\n  \n", "two words\n", "trail.\n"])
def test_bad_input_exits_2_without_echoing_it(
    text: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _feed(monkeypatch, text)
    assert hash_reference_tokens.main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    for word in text.split():
        assert word not in captured.err


def test_unreadable_denylist_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _feed(monkeypatch, "skivorn\n")
    missing = tmp_path / "absent.txt"
    assert hash_reference_tokens.main(["--check", "--denylist", str(missing)]) == 2


def test_terminal_input_uses_a_hidden_prompt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    answers = iter(["skivorn", " quill-mark ", ""])
    prompts: list[str] = []

    def fake_getpass(prompt: str = "") -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr(sys, "stdin", _Terminal(""))
    monkeypatch.setattr(getpass, "getpass", fake_getpass)
    assert hash_reference_tokens.main([]) == 0
    assert len(prompts) == 3
    out = capsys.readouterr().out
    assert out.splitlines() == [digest_entry("skivorn"), digest_entry("quill-mark")]
