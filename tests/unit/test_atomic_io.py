# SPDX-License-Identifier: MIT

"""Tests for the shared atomic-write / durable-append / advisory-lock util."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from apothem.lib import atomic_io

# --- write_bytes_atomically --------------------------------------------------


def test_write_bytes_atomically_writes_and_creates_parents(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "file.txt"
    atomic_io.write_bytes_atomically(target, b"hello world")
    assert target.read_bytes() == b"hello world"


def test_write_failure_leaves_original_intact_and_no_residue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "file.txt"
    target.write_bytes(b"ORIGINAL")

    def _boom(src: object, dst: object) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(atomic_io.os, "replace", _boom)
    with pytest.raises(OSError, match="injected replace failure"):
        atomic_io.write_bytes_atomically(target, b"NEW CONTENT")

    # Original untouched (atomic: never truncated to partial content)...
    assert target.read_bytes() == b"ORIGINAL"
    # ...and no .tmp residue remains.
    residue = [p for p in tmp_path.iterdir() if p.name.startswith(".file.txt")]
    assert residue == []


def test_write_is_atomic_replace_not_truncation(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_bytes(b"x" * 1000)
    atomic_io.write_bytes_atomically(target, b"y" * 5)
    assert target.read_bytes() == b"y" * 5


@pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX permission bits; Windows chmod is limited"
)
def test_replace_preserves_existing_target_mode(tmp_path: Path) -> None:
    # An operator-chosen mode on an existing target survives the rewrite;
    # mkstemp's private 0o600 must not silently clobber it.
    target = tmp_path / "file.txt"
    target.write_bytes(b"OLD")
    target.chmod(0o644)

    atomic_io.write_bytes_atomically(target, b"NEW")

    assert target.read_bytes() == b"NEW"
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


@pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX permission bits; Windows chmod is limited"
)
def test_new_file_is_created_owner_only(tmp_path: Path) -> None:
    # A NEW file inherits mkstemp's owner-only 0o600 (documented contract).
    target = tmp_path / "new.txt"
    atomic_io.write_bytes_atomically(target, b"data")
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


# --- _replace_with_retry (win32 transient PermissionError) --------------------


def test_replace_retries_transient_permission_error_on_win32(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Antivirus / a concurrent reader holds the target briefly: two transient
    # denials, then success — the write completes without surfacing an error.
    target = tmp_path / "file.txt"
    target.write_bytes(b"OLD")
    real_replace = os.replace
    calls = {"count": 0}

    def flaky_replace(src: object, dst: object) -> None:
        calls["count"] += 1
        if calls["count"] <= 2:
            raise PermissionError("target briefly held open")
        real_replace(src, dst)  # type: ignore[arg-type]

    sleeps: list[float] = []
    monkeypatch.setattr(atomic_io.sys, "platform", "win32")
    monkeypatch.setattr(atomic_io.os, "replace", flaky_replace)
    monkeypatch.setattr(atomic_io.time, "sleep", lambda s: sleeps.append(s))

    atomic_io.write_bytes_atomically(target, b"NEW")

    assert target.read_bytes() == b"NEW"
    assert calls["count"] == 3  # two transient failures, then success
    assert len(sleeps) == 2


def test_replace_retry_exhaustion_reraises_on_win32(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "file.txt"
    target.write_bytes(b"ORIGINAL")
    calls = {"count": 0}

    def always_denied(src: object, dst: object) -> None:
        calls["count"] += 1
        raise PermissionError("persistently held open")

    monkeypatch.setattr(atomic_io.sys, "platform", "win32")
    monkeypatch.setattr(atomic_io.os, "replace", always_denied)
    monkeypatch.setattr(atomic_io.time, "sleep", lambda _s: None)

    with pytest.raises(PermissionError, match="persistently held open"):
        atomic_io.write_bytes_atomically(target, b"NEW")

    # Bounded: every attempt consumed, the final failure re-raised, and the
    # original target untouched (atomicity preserved through the retries).
    assert calls["count"] == atomic_io._REPLACE_ATTEMPTS
    assert target.read_bytes() == b"ORIGINAL"


def test_replace_does_not_retry_on_posix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # POSIX rename never contends with a reader; a PermissionError there is
    # real and surfaces immediately — exactly one attempt, no sleeping.
    target = tmp_path / "file.txt"
    target.write_bytes(b"ORIGINAL")
    calls = {"count": 0}

    def always_denied(src: object, dst: object) -> None:
        calls["count"] += 1
        raise PermissionError("no permission")

    sleeps: list[float] = []
    monkeypatch.setattr(atomic_io.sys, "platform", "linux")
    monkeypatch.setattr(atomic_io.os, "replace", always_denied)
    monkeypatch.setattr(atomic_io.time, "sleep", lambda s: sleeps.append(s))

    with pytest.raises(PermissionError, match="no permission"):
        atomic_io.write_bytes_atomically(target, b"NEW")

    assert calls["count"] == 1
    assert sleeps == []
    assert target.read_bytes() == b"ORIGINAL"


# --- append_line_durably -----------------------------------------------------


def test_append_line_durably_appends_records(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    atomic_io.append_line_durably(ledger, "first")
    atomic_io.append_line_durably(ledger, "second\n")  # already newline-terminated
    atomic_io.append_line_durably(ledger, "third")
    assert ledger.read_text(encoding="utf-8").splitlines() == [
        "first",
        "second",
        "third",
    ]


def test_concurrent_appends_under_lock_do_not_interleave(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    lock = tmp_path / "ledger.lock"

    def appender(tag: str) -> None:
        for i in range(20):
            with atomic_io.advisory_lock(lock, timeout=30):
                atomic_io.append_line_durably(ledger, f"{tag}-{i}")

    threads = [threading.Thread(target=appender, args=(t,)) for t in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = ledger.read_text(encoding="utf-8").splitlines()
    # Every record is intact (no torn/interleaved bytes) and all 40 are present.
    assert len(lines) == 40
    assert sorted(lines) == sorted(
        [f"{tag}-{i}" for tag in ("A", "B") for i in range(20)]
    )


# --- advisory_lock -----------------------------------------------------------


def test_advisory_lock_serializes_contending_threads(tmp_path: Path) -> None:
    lock = tmp_path / "x.lock"
    events: list[str] = []

    def worker(tag: str) -> None:
        with atomic_io.advisory_lock(lock, timeout=30):
            events.append(f"start-{tag}")
            time.sleep(0.1)
            events.append(f"end-{tag}")

    threads = [threading.Thread(target=worker, args=(t,)) for t in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Each holder's start/end are adjacent — no interleaving across the lock.
    assert events in (
        ["start-A", "end-A", "start-B", "end-B"],
        ["start-B", "end-B", "start-A", "end-A"],
    )


def test_advisory_lock_releases_after_exception(tmp_path: Path) -> None:
    lock = tmp_path / "x.lock"
    with (
        pytest.raises(RuntimeError, match="boom"),
        atomic_io.advisory_lock(lock, timeout=5),
    ):
        raise RuntimeError("boom")
    # A subsequent acquire succeeds — the lock was released on the exception.
    with atomic_io.advisory_lock(lock, timeout=5):
        pass


def test_advisory_lock_times_out_rather_than_hanging(tmp_path: Path) -> None:
    lock = tmp_path / "x.lock"
    with atomic_io.advisory_lock(lock, timeout=30):
        # A second acquirer in another thread must time out, not block forever.
        result: dict[str, object] = {}

        def contender() -> None:
            start = time.monotonic()
            try:
                with atomic_io.advisory_lock(lock, timeout=0.3, poll_interval=0.02):
                    result["acquired"] = True
            except TimeoutError:
                result["timed_out"] = True
            result["elapsed"] = time.monotonic() - start

        t = threading.Thread(target=contender)
        t.start()
        t.join(timeout=10)

    assert result.get("timed_out") is True
    assert "acquired" not in result
    assert float(result["elapsed"]) < 5  # honored the 0.3s timeout, did not hang


def test_advisory_lock_killed_holder_does_not_deadlock(tmp_path: Path) -> None:
    lock = tmp_path / "x.lock"
    script = (
        "import sys, time\n"
        "from apothem.lib.atomic_io import advisory_lock\n"
        "with advisory_lock(__import__('pathlib').Path(sys.argv[1]), timeout=60):\n"
        "    print('LOCKED', flush=True)\n"
        "    time.sleep(60)\n"
    )
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.Popen(
        [sys.executable, "-c", script, str(lock)],
        stdout=subprocess.PIPE,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    try:
        assert proc.stdout is not None
        # Wait for the child to confirm it holds the lock. A blocking readline
        # is offloaded to a reader thread so a silent, non-exiting child cannot
        # hang the suite: the bounded join is the hard deadline, not a loop that
        # only re-checks the clock between reads.
        first_line: list[str] = []

        def _read_first_line() -> None:
            assert proc.stdout is not None
            first_line.append(proc.stdout.readline())

        reader = threading.Thread(target=_read_first_line, daemon=True)
        reader.start()
        reader.join(timeout=30)
        line = first_line[0] if first_line else ""
        assert "LOCKED" in line, "child never acquired the lock"
        # While the child holds it, this process cannot acquire (timeout).
        with (
            pytest.raises(TimeoutError),
            atomic_io.advisory_lock(lock, timeout=0.5, poll_interval=0.05),
        ):
            pass
        # Kill the holder without clean exit — the OS must release its lock.
        proc.kill()
        proc.wait(timeout=10)
        # The next acquirer now succeeds: no orphan lock from the dead holder.
        with atomic_io.advisory_lock(lock, timeout=10):
            pass
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
