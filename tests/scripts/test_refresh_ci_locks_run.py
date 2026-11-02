# SPDX-License-Identifier: MIT

"""The refresh and ``--check`` runs of scripts/dev/refresh_ci_locks.py, with uv stubbed.

``test_refresh_ci_locks.py`` pins the lock table, the header, the date and cooldown
arithmetic and the uv command line. This module runs ``refresh``, ``check`` and
``main`` end to end with the compile step replaced by a stub, so it needs neither
uv nor network access: what each lock records (the cooldown exceptions included),
what ``--check`` reproduces and reports, and the exit codes of the command line.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import refresh_ci_locks  # noqa: E402

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
# Built in two pieces so the REUSE parser does not read this literal as a licence tag.
SPDX_LINE = "# SPDX-License-" + "Identifier: MIT"
STAMP = "2026-10-29T00:00:00Z"
CUTOFF = "2026-10-22T00:00:00Z"
UV = "0.11.14"


def _body(version: str = "1.0.0", digest: str = HASH_A) -> str:
    return (
        f"click=={version} \\\n"
        f"    --hash=sha256:{digest} \\\n"
        f"    --hash=sha256:{HASH_B}\n"
        "colorama==0.4.6 ; sys_platform == 'win32' \\\n"
        f"    --hash=sha256:{HASH_C}\n"
    )


# --- refresh and --check with a stubbed compile -------------------------------


@pytest.fixture
def stubbed(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Replace uv: every lock compiles to ``bodies[filename]`` (default ``_body()``).

    The table is patched to carry no cooldown exceptions, so these tests do not
    depend on which exception the real table lists on the day they run.
    """
    bodies: dict[str, str] = {}

    def fake_compile(
        lock: refresh_ci_locks.Lock,
        cutoff: str,
        uv: str,
        work_dir: Path,
        repo_root: Path,
    ) -> str:
        return bodies.get(lock.filename, _body())

    monkeypatch.setattr(refresh_ci_locks, "compile_lock", fake_compile)
    monkeypatch.setattr(refresh_ci_locks, "read_uv_version", lambda uv: UV)
    monkeypatch.setattr(refresh_ci_locks, "_find_uv", lambda: "uv")
    monkeypatch.setattr(refresh_ci_locks, "_REPO_ROOT", Path())
    monkeypatch.setattr(
        refresh_ci_locks,
        "LOCKS",
        tuple(
            dataclasses.replace(lock, cooldown_exceptions=())
            for lock in refresh_ci_locks.LOCKS
        ),
    )
    return bodies


def _spy_cutoffs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the cutoff each compile receives, then run the stubbed compile."""
    cutoffs: list[str] = []
    real = refresh_ci_locks.compile_lock

    def spy(
        lock: refresh_ci_locks.Lock,
        cutoff: str,
        uv: str,
        work_dir: Path,
        repo_root: Path,
    ) -> str:
        cutoffs.append(cutoff)
        return real(lock, cutoff, uv, work_dir, repo_root)

    monkeypatch.setattr(refresh_ci_locks, "compile_lock", spy)
    return cutoffs


def test_refresh_writes_every_lock_with_lf_endings(
    tmp_path: Path, stubbed: dict[str, str]
) -> None:
    written = refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    assert [path.name for path in written] == [
        lock.filename for lock in refresh_ci_locks.LOCKS
    ]
    for path in written:
        data = path.read_bytes()
        assert b"\r" not in data
        text = data.decode("utf-8")
        assert text.startswith(SPDX_LINE)
        assert refresh_ci_locks.parse_header(text) == refresh_ci_locks.ParsedHeader(
            STAMP, 7, CUTOFF, UV
        )


def test_refresh_compiles_every_lock_at_the_cutoff_not_the_lock_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    cutoffs = _spy_cutoffs(monkeypatch)
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    assert cutoffs == [CUTOFF] * len(refresh_ci_locks.LOCKS)


def test_refresh_with_a_zero_cooldown_compiles_at_the_lock_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    cutoffs = _spy_cutoffs(monkeypatch)
    written = refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv", 0)
    assert cutoffs == [STAMP] * len(refresh_ci_locks.LOCKS)
    header = refresh_ci_locks.parse_header(written[0].read_text(encoding="utf-8"))
    assert header == refresh_ci_locks.ParsedHeader(STAMP, 0, STAMP, UV)


def test_refresh_records_a_custom_cooldown(
    tmp_path: Path, stubbed: dict[str, str]
) -> None:
    written = refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv", 3)
    header = refresh_ci_locks.parse_header(written[0].read_text(encoding="utf-8"))
    assert header == refresh_ci_locks.ParsedHeader(STAMP, 3, "2026-10-26T00:00:00Z", UV)


def test_refresh_rejects_a_negative_cooldown_before_it_compiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    cutoffs = _spy_cutoffs(monkeypatch)
    with pytest.raises(ValueError, match="negative"):
        refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv", -1)
    assert cutoffs == []


def test_check_passes_after_a_refresh(tmp_path: Path, stubbed: dict[str, str]) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    assert refresh_ci_locks.check(tmp_path, "uv") == []


def test_check_reports_a_changed_package(
    tmp_path: Path, stubbed: dict[str, str]
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    stubbed["requirements-ci-dev.txt"] = _body("2.0.0")
    problems = refresh_ci_locks.check(tmp_path, "uv")
    assert len(problems) == 1
    assert "requirements-ci-dev.txt" in problems[0]
    assert "committed 1.0.0, fresh 2.0.0" in problems[0]
    assert CUTOFF in problems[0]


def test_check_uses_the_cutoff_recorded_in_each_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-09-01", "uv")
    cutoffs = _spy_cutoffs(monkeypatch)
    assert refresh_ci_locks.check(tmp_path, "uv") == []
    assert cutoffs == ["2026-08-25T00:00:00Z"] * len(refresh_ci_locks.LOCKS)


def test_check_reproduces_a_lock_written_with_a_zero_cooldown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-09-01", "uv", 0)
    cutoffs = _spy_cutoffs(monkeypatch)
    assert refresh_ci_locks.check(tmp_path, "uv") == []
    assert cutoffs == ["2026-09-01T00:00:00Z"] * len(refresh_ci_locks.LOCKS)


def test_check_does_not_recompute_a_cutoff_that_the_header_contradicts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    target = tmp_path / refresh_ci_locks.LOCKS[0].relpath
    text = target.read_text(encoding="utf-8")
    target.write_bytes(
        text.replace(f"# Cutoff: {CUTOFF}", "# Cutoff: 2026-10-27T00:00:00Z").encode()
    )
    cutoffs = _spy_cutoffs(monkeypatch)
    problems = refresh_ci_locks.check(tmp_path, "uv")
    assert len(problems) == 1
    assert refresh_ci_locks.LOCKS[0].relpath in problems[0]
    assert "2026-10-27T00:00:00Z" in problems[0]
    assert CUTOFF in problems[0]
    assert "edited by hand" in problems[0]
    # The other eight locks still compile, and the bad header never reaches uv.
    assert cutoffs == [CUTOFF] * (len(refresh_ci_locks.LOCKS) - 1)


def test_check_reports_a_cooldown_that_no_date_can_follow(
    tmp_path: Path, stubbed: dict[str, str]
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    target = tmp_path / refresh_ci_locks.LOCKS[2].relpath
    text = target.read_text(encoding="utf-8")
    target.write_bytes(
        text.replace("# Cooldown: 7 days", "# Cooldown: 99999999999 days").encode()
    )
    problems = refresh_ci_locks.check(tmp_path, "uv")
    assert len(problems) == 1
    assert "cooldown it cannot use" in problems[0]
    assert "refresh_ci_locks.py" in problems[0]


def test_check_names_the_missing_lines_of_a_lock_from_an_older_script(
    tmp_path: Path, stubbed: dict[str, str]
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    target = tmp_path / refresh_ci_locks.LOCKS[1].relpath
    kept = [
        line
        for line in target.read_text(encoding="utf-8").splitlines(keepends=True)
        if not line.startswith(("# Cooldown: ", "# Cutoff: "))
    ]
    target.write_bytes("".join(kept).encode("utf-8"))
    problems = refresh_ci_locks.check(tmp_path, "uv")
    assert len(problems) == 1
    assert "`Cooldown:`" in problems[0]
    assert "`Cutoff:`" in problems[0]
    assert "refresh_ci_locks.py" in problems[0]


def test_check_names_a_different_uv_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    monkeypatch.setattr(refresh_ci_locks, "read_uv_version", lambda uv: "0.12.0")
    stubbed["requirements-ci-runtime.txt"] = _body("3.0.0")
    problems = refresh_ci_locks.check(tmp_path, "uv")
    assert len(problems) == 1
    assert "uv 0.11.14" in problems[0]
    assert "uv 0.12.0" in problems[0]


def test_check_reports_a_crlf_working_copy(
    tmp_path: Path, stubbed: dict[str, str]
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    target = tmp_path / refresh_ci_locks.LOCKS[0].relpath
    target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    problems = refresh_ci_locks.check(tmp_path, "uv")
    assert any("CRLF" in problem for problem in problems)


def test_check_reports_a_missing_lock_and_a_missing_date(
    tmp_path: Path, stubbed: dict[str, str]
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    (tmp_path / refresh_ci_locks.LOCKS[0].relpath).unlink()
    undated = tmp_path / refresh_ci_locks.LOCKS[1].relpath
    undated.write_text(_body(), encoding="utf-8", newline="\n")
    problems = refresh_ci_locks.check(tmp_path, "uv")
    assert any("is missing" in problem for problem in problems)
    assert any("Locked as of" in problem for problem in problems)


# --- cooldown exceptions --------------------------------------------------------

EXCEPTION_LINE = (
    "# Cooldown exception: click, files uploaded before 2026-10-23T00:00:00Z"
)


def _with_exception(until: str) -> tuple[refresh_ci_locks.Lock, ...]:
    """Return the table with a cooldown exception for ``click`` on the first lock."""
    first, *rest = refresh_ci_locks.LOCKS
    return (dataclasses.replace(first, cooldown_exceptions=(("click", until),)), *rest)


def _exception_lines(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith(refresh_ci_locks.EXCEPTION_PREFIX)
    ]


def test_refresh_writes_the_exception_into_the_lock_that_lists_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    table = _with_exception("2026-10-23T00:00:00Z")
    monkeypatch.setattr(refresh_ci_locks, "LOCKS", table)
    first, *others = refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    text = first.read_text(encoding="utf-8")
    assert _exception_lines(first) == [EXCEPTION_LINE]
    assert (
        text.index("# Cutoff: ")
        < text.index(EXCEPTION_LINE)
        < text.index("# Compiled with: ")
    )
    for lock, path in zip(table[1:], others, strict=True):
        assert _exception_lines(path) == lock.exception_lines, lock.filename


def test_refresh_refuses_an_exception_the_cutoff_has_reached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    # The cutoff of a refresh on 2026-10-29 is 2026-10-22, so an exception that
    # ends there lifts nothing and uv would hold the package back to it.
    table = _with_exception(CUTOFF)
    monkeypatch.setattr(refresh_ci_locks, "LOCKS", table)
    cutoffs = _spy_cutoffs(monkeypatch)
    with pytest.raises(RuntimeError) as raised:
        refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    message = str(raised.value)
    assert table[0].relpath in message
    assert "cooldown exception for click" in message
    assert CUTOFF in message
    assert "Remove it from scripts/dev/ci_lock_table.py" in message
    assert cutoffs == []
    assert not (tmp_path / "scripts").exists()


def test_a_zero_cooldown_refuses_an_exception_older_than_the_lock_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    table = _with_exception("2026-10-23T00:00:00Z")
    monkeypatch.setattr(refresh_ci_locks, "LOCKS", table)
    with pytest.raises(RuntimeError, match="cooldown exception for click"):
        refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv", 0)


def test_a_zero_cooldown_accepts_an_exception_from_the_lock_date_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    # A fix uploaded on the lock date is later than the zero-day cutoff (midnight),
    # so only an exception with a time of day can take it.
    table = _with_exception("2026-10-29T14:30:00Z")
    monkeypatch.setattr(refresh_ci_locks, "LOCKS", table)
    first = refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv", 0)[0]
    assert _exception_lines(first) == [
        "# Cooldown exception: click, files uploaded before 2026-10-29T14:30:00Z"
    ]


def test_check_passes_for_a_lock_with_a_cooldown_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    table = _with_exception("2026-10-23T00:00:00Z")
    monkeypatch.setattr(refresh_ci_locks, "LOCKS", table)
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    assert refresh_ci_locks.check(tmp_path, "uv") == []


def test_check_reports_a_lock_that_lost_its_exception_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    table = _with_exception("2026-10-23T00:00:00Z")
    monkeypatch.setattr(refresh_ci_locks, "LOCKS", table)
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    target = tmp_path / table[0].relpath
    kept = [
        line
        for line in target.read_text(encoding="utf-8").splitlines(keepends=True)
        if not line.startswith(refresh_ci_locks.EXCEPTION_PREFIX)
    ]
    target.write_bytes("".join(kept).encode("utf-8"))
    problems = refresh_ci_locks.check(tmp_path, "uv")
    assert len(problems) == 1
    assert table[0].relpath in problems[0]
    assert "records the cooldown exceptions none" in problems[0]
    assert EXCEPTION_LINE in problems[0]


def test_check_reports_an_exception_added_to_the_table_after_the_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    table = _with_exception("2026-10-23T00:00:00Z")
    monkeypatch.setattr(refresh_ci_locks, "LOCKS", table)
    problems = refresh_ci_locks.check(tmp_path, "uv")
    assert len(problems) == 1
    assert "records the cooldown exceptions none" in problems[0]
    assert "run `python scripts/dev/refresh_ci_locks.py`" in problems[0]


def test_check_reports_an_exception_the_recorded_cutoff_has_reached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    monkeypatch.setattr(
        refresh_ci_locks, "LOCKS", _with_exception("2026-10-23T00:00:00Z")
    )
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    monkeypatch.setattr(refresh_ci_locks, "LOCKS", _with_exception(CUTOFF))
    cutoffs = _spy_cutoffs(monkeypatch)
    problems = refresh_ci_locks.check(tmp_path, "uv")
    assert len(problems) == 1
    assert "already reaches its timestamp" in problems[0]
    assert CUTOFF in problems[0]
    # The other eight locks still compile; the stale one never reaches uv.
    assert cutoffs == [CUTOFF] * (len(refresh_ci_locks.LOCKS) - 1)


def test_main_reports_a_stale_cooldown_exception_with_exit_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stubbed: dict[str, str],
) -> None:
    monkeypatch.setattr(refresh_ci_locks, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(refresh_ci_locks, "LOCKS", _with_exception(CUTOFF))
    assert refresh_ci_locks.main(["--date", "2026-10-29"]) == 1
    assert "cooldown exception for click" in capsys.readouterr().err
    assert not (tmp_path / "scripts").exists()


def test_main_check_exits_one_with_the_fix_on_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stubbed: dict[str, str],
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    monkeypatch.setattr(refresh_ci_locks, "_REPO_ROOT", tmp_path)
    stubbed["requirements-ci-test.txt"] = _body("9.9.9")
    assert refresh_ci_locks.main(["--check"]) == 1
    captured = capsys.readouterr()
    assert "CI lock drift detected" in captured.err
    assert "scripts/dev/refresh_ci_locks.py" in captured.err


def test_main_check_exits_zero_when_every_lock_matches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stubbed: dict[str, str],
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    monkeypatch.setattr(refresh_ci_locks, "_REPO_ROOT", tmp_path)
    assert refresh_ci_locks.main(["--check"]) == 0
    out = capsys.readouterr().out
    assert f"{len(refresh_ci_locks.LOCKS)} CI lock(s) match a fresh compile" in out


def test_main_refresh_writes_into_the_repo_root_and_prints_the_cutoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stubbed: dict[str, str],
) -> None:
    monkeypatch.setattr(refresh_ci_locks, "_REPO_ROOT", tmp_path)
    assert refresh_ci_locks.main(["--date", "2026-10-29"]) == 0
    assert (tmp_path / "scripts/ci/requirements-ci-dev.txt").is_file()
    assert (tmp_path / "scripts/ci/requirements-ci-pre-commit.txt").is_file()
    captured = capsys.readouterr()
    assert "wrote scripts/ci/requirements-ci-dev.txt" in captured.out
    assert (
        f"Locking as of 2026-10-29 with a 7-day cooldown: only files uploaded "
        f"before {CUTOFF} are used"
    ) in captured.out
    assert captured.err == ""


def test_main_cooldown_days_moves_the_cutoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stubbed: dict[str, str],
) -> None:
    monkeypatch.setattr(refresh_ci_locks, "_REPO_ROOT", tmp_path)
    cutoffs = _spy_cutoffs(monkeypatch)
    assert refresh_ci_locks.main(["--date", "2026-10-29", "--cooldown-days", "14"]) == 0
    assert set(cutoffs) == {"2026-10-15T00:00:00Z"}
    assert "14-day cooldown" in capsys.readouterr().out
    text = (tmp_path / "scripts/ci/requirements-ci-dev.txt").read_text(encoding="utf-8")
    assert "# Cooldown: 14 days\n" in text


def test_main_cooldown_days_zero_locks_the_lock_date_and_says_so(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stubbed: dict[str, str],
) -> None:
    monkeypatch.setattr(refresh_ci_locks, "_REPO_ROOT", tmp_path)
    cutoffs = _spy_cutoffs(monkeypatch)
    assert refresh_ci_locks.main(["--date", "2026-10-29", "--cooldown-days", "0"]) == 0
    assert set(cutoffs) == {STAMP}
    captured = capsys.readouterr()
    assert "note: a cooldown of 0 days" in captured.err
    text = (tmp_path / "scripts/ci/requirements-ci-ruff.txt").read_text(
        encoding="utf-8"
    )
    assert "# Cooldown: 0 days\n" in text
    assert f"# Cutoff: {STAMP}\n" in text


def test_main_defaults_to_today_with_the_seven_day_cooldown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stubbed: dict[str, str],
) -> None:
    monkeypatch.setattr(refresh_ci_locks, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(refresh_ci_locks, "today_utc", lambda: "2026-11-05")
    assert refresh_ci_locks.main([]) == 0
    text = (tmp_path / "scripts/ci/requirements-ci-dev.txt").read_text(encoding="utf-8")
    assert "# Locked as of: 2026-11-05T00:00:00Z\n" in text
    assert "# Cutoff: 2026-10-29T00:00:00Z\n" in text
    assert "7-day cooldown" in capsys.readouterr().out


def test_main_rejects_a_bad_date_with_exit_two(
    capsys: pytest.CaptureFixture[str], stubbed: dict[str, str]
) -> None:
    assert refresh_ci_locks.main(["--date", "yesterday"]) == 2
    assert "lock date" in capsys.readouterr().err


def test_main_rejects_a_negative_cooldown_with_exit_two(
    capsys: pytest.CaptureFixture[str], stubbed: dict[str, str]
) -> None:
    assert refresh_ci_locks.main(["--cooldown-days", "-1"]) == 2
    assert "negative" in capsys.readouterr().err


def test_main_rejects_a_cooldown_that_is_not_a_number(stubbed: dict[str, str]) -> None:
    with pytest.raises(SystemExit) as raised:
        refresh_ci_locks.main(["--cooldown-days", "a-week"])
    assert raised.value.code == 2


@pytest.mark.parametrize(
    "arguments",
    [
        ["--check", "--date", "2026-10-29"],
        ["--check", "--cooldown-days", "7"],
        ["--check", "--cooldown-days", "0"],
    ],
)
def test_main_rejects_the_refresh_options_with_check(
    arguments: list[str], stubbed: dict[str, str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        refresh_ci_locks.main(arguments)
    assert raised.value.code == 2


def test_missing_uv_exits_two_with_an_install_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(refresh_ci_locks.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit) as raised:
        refresh_ci_locks._find_uv()
    assert raised.value.code == 2
    assert "uv is not on PATH" in capsys.readouterr().err


def test_a_compile_failure_part_way_writes_no_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    last = refresh_ci_locks.LOCKS[-1].filename

    def fail_on_last(
        lock: refresh_ci_locks.Lock,
        cutoff: str,
        uv: str,
        work_dir: Path,
        repo_root: Path,
    ) -> str:
        if lock.filename == last:
            raise RuntimeError("uv failed")
        return _body()

    monkeypatch.setattr(refresh_ci_locks, "compile_lock", fail_on_last)
    with pytest.raises(RuntimeError):
        refresh_ci_locks.refresh(tmp_path, "2026-10-29", "uv")
    assert not (tmp_path / "scripts").exists()


def test_a_failed_compile_is_reported_not_raised(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stubbed: dict[str, str],
) -> None:
    def failing(*args: object, **kwargs: object) -> str:
        raise RuntimeError("uv failed for scripts/ci/requirements-ci-dev.txt (exit 1)")

    monkeypatch.setattr(refresh_ci_locks, "compile_lock", failing)
    monkeypatch.setattr(refresh_ci_locks, "_REPO_ROOT", tmp_path)
    assert refresh_ci_locks.main([]) == 1
    assert "uv failed" in capsys.readouterr().err
