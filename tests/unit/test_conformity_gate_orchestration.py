# SPDX-License-Identifier: MIT

"""Tests for the conformity-gate orchestration hardening (C2 / C6).

Covers:
- ``_load_check`` memoization: each matcher module is loaded once per process,
  so the corpus (file x matcher) sweep does not re-exec every module per file.
- The distinct ``EXIT_USAGE`` (3) code for CLI-usage errors, kept apart from the
  strict findings-block ``EXIT_FAIL`` (2).
- The ``files_truncated`` flag on the ``--all-perwrite`` payload.
- The Edit-payload reconstruction no-op note.
- A perf smoke assertion: a whole ``--all-perwrite`` corpus run loads each
  matcher module exactly once (memoization holds across the corpus sweep).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.conformity import gate


def test_load_check_is_memoized_by_module_name() -> None:
    """Two loads of the same matcher return the identical callable object."""
    gate._load_check.cache_clear()
    first = gate._load_check("file_header_grep")
    second = gate._load_check("file_header_grep")
    assert first is second
    info = gate._load_check.cache_info()
    assert info.hits >= 1


def test_load_check_loads_each_module_once_over_a_corpus_sweep(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Perf smoke: a full ``--all-perwrite`` run exec's each module once.

    The corpus sweep routes every tracked file through every matcher; without
    memoization each module would be re-exec'd once per (file x matcher) pair.
    We wrap the module-exec seam and assert no module name is loaded twice.
    """
    gate._load_check.cache_clear()

    # A small corpus of a few text files under a fake tracked tree.
    files = ["a.py", "b.md", "c.yaml", "d.txt"]

    def _fake_corpus(_root: Path) -> list[Path]:
        return [(tmp_path / name) for name in files]

    for name in files:
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(gate, "_corpus_tracked_files", _fake_corpus)

    loaded: list[str] = []
    real_load = gate._load_check.__wrapped__  # type: ignore[attr-defined]

    def _tracking_load(module_name: str) -> gate._CheckCallable:
        loaded.append(module_name)
        return real_load(module_name)

    # Re-wrap with the same cache so the tracker only fires on a genuine miss.
    import functools

    monkeypatch.setattr(gate, "_load_check", functools.cache(_tracking_load))

    gate._run_all_perwrite(tmp_path)

    # Each distinct module name is loaded (exec'd) at most once for the run.
    assert len(loaded) == len(set(loaded)), (
        f"a matcher module was re-loaded during the corpus sweep: {loaded}"
    )


def test_unknown_check_name_exits_usage_not_fail() -> None:
    """``--check <unknown>`` exits ``EXIT_USAGE`` (3), not ``EXIT_FAIL`` (2)."""
    code = gate.main(["gate", "--check", "no-such-grep", "."])
    assert code == gate.EXIT_USAGE
    assert gate.EXIT_USAGE != gate.EXIT_FAIL


def test_all_perwrite_payload_carries_files_truncated_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every ``--all-perwrite`` matcher entry carries a ``files_truncated`` bool."""
    # One trivially-non-conformant file so at least one advisory matcher fires.
    target = tmp_path / "sample.md"
    target.write_text("no header here\n", encoding="utf-8")

    monkeypatch.setattr(gate, "_corpus_tracked_files", lambda _root: [target])

    _passed, payload_json = gate._run_all_perwrite(tmp_path)
    payload = json.loads(payload_json)
    for entry in payload["blocking"] + payload["advisory"]:
        assert "files_truncated" in entry
        assert isinstance(entry["files_truncated"], bool)


def test_all_perwrite_files_truncated_true_when_over_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``files_truncated`` is True once a matcher flags more files than the cap."""
    over_cap = gate._PERWRITE_FILE_SAMPLE_CAP + 3
    corpus = []
    for i in range(over_cap):
        f = tmp_path / f"f{i}.md"
        f.write_text("no header here\n", encoding="utf-8")
        corpus.append(f)

    monkeypatch.setattr(gate, "_corpus_tracked_files", lambda _root: corpus)

    _passed, payload_json = gate._run_all_perwrite(tmp_path)
    payload = json.loads(payload_json)
    flagged = [
        e for e in payload["blocking"] + payload["advisory"] if e["file_count"] > 0
    ]
    assert flagged, "expected at least one matcher to flag the corpus"
    for entry in flagged:
        if entry["file_count"] > gate._PERWRITE_FILE_SAMPLE_CAP:
            assert entry["files_truncated"] is True
            assert len(entry["files"]) == gate._PERWRITE_FILE_SAMPLE_CAP


def test_edit_payload_noop_emits_stderr_note(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A stale Edit payload (old_string absent) notes the reconstruction no-op."""
    target = tmp_path / "existing.py"
    target.write_text("# SPDX-License-Identifier: MIT\n\nx = 1\n", encoding="utf-8")

    payload = json.dumps(
        {
            "tool_input": {
                "file_path": str(target),
                "old_string": "THIS TEXT IS NOT IN THE FILE",
                "new_string": "replacement",
            }
        }
    )
    monkeypatch.setattr("sys.stdin", _StubStdin(payload))

    post, path, pre = gate._read_tool_input_from_stdin()
    captured = capsys.readouterr()
    assert "no-op" in captured.err
    assert path == target
    # The reconstruction returns the file unchanged (the diff is vacuously clean).
    assert post == pre


class _StubStdin:
    """Minimal stdin stub returning a fixed payload from ``read()``."""

    def __init__(self, payload: str) -> None:
        self._payload = payload

    def read(self) -> str:
        return self._payload
