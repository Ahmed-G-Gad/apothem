# SPDX-License-Identifier: MIT

"""Tests for scripts/dev/refresh_ci_locks.py.

The script compiles the hash-locked CI requirement files with ``uv pip compile``.
These tests need neither uv nor network access: they pin the lock table, the
header format, the date handling and the diff decision, and they run the
refresh and ``--check`` paths with the compile step replaced by a stub.
"""

from __future__ import annotations

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


def _body(version: str = "1.0.0", digest: str = HASH_A) -> str:
    return (
        f"click=={version} \\\n"
        f"    --hash=sha256:{digest} \\\n"
        f"    --hash=sha256:{HASH_B}\n"
        "colorama==0.4.6 ; sys_platform == 'win32' \\\n"
        f"    --hash=sha256:{HASH_C}\n"
    )


def _lock() -> refresh_ci_locks.Lock:
    return refresh_ci_locks.LOCKS[0]


# --- the lock table ----------------------------------------------------------


def test_table_has_the_four_locks_in_scripts_ci() -> None:
    names = [lock.filename for lock in refresh_ci_locks.LOCKS]
    assert names == [
        "requirements-ci-dev.txt",
        "requirements-ci-runtime.txt",
        "requirements-ci-test.txt",
        "requirements-ci-prereqs.txt",
    ]
    for lock in refresh_ci_locks.LOCKS:
        assert lock.relpath == f"scripts/ci/{lock.filename}"


def test_table_filenames_are_unique() -> None:
    names = [lock.filename for lock in refresh_ci_locks.LOCKS]
    assert len(names) == len(set(names))


def test_every_stdin_source_has_requirements_and_the_reverse() -> None:
    for lock in refresh_ci_locks.LOCKS:
        assert ("-" in lock.sources) == bool(lock.stdin_requirements), lock.filename


def test_dev_lock_reads_the_dev_extra_and_the_others_read_no_extra() -> None:
    by_name = {lock.filename: lock for lock in refresh_ci_locks.LOCKS}
    assert by_name["requirements-ci-dev.txt"].extras == ("dev",)
    assert by_name["requirements-ci-runtime.txt"].extras == ()
    assert by_name["requirements-ci-test.txt"].stdin_requirements == (
        "pytest",
        "pytest-xdist",
        "build",
    )
    assert by_name["requirements-ci-prereqs.txt"].stdin_requirements == (
        "click==8.4.2",
        "rich>=15.0.0",
    )


def test_lock_by_filename() -> None:
    assert refresh_ci_locks.lock_by_filename("requirements-ci-test.txt").extras == ()
    with pytest.raises(KeyError):
        refresh_ci_locks.lock_by_filename("requirements-ci-pip.txt")


def test_no_lock_has_a_sibling_in_file() -> None:
    ci_dir = REPO_ROOT / "scripts" / "ci"
    assert list(ci_dir.glob("*.in")) == []


# --- dates --------------------------------------------------------------------


def test_timestamp_is_midnight_utc() -> None:
    assert refresh_ci_locks.timestamp_for_date("2026-10-29") == STAMP


@pytest.mark.parametrize(
    "text", ["2026-10-2", "20261029", "2026-13-01", "2026-02-30", "", "today"]
)
def test_bad_dates_are_rejected(text: str) -> None:
    with pytest.raises(ValueError, match="lock date"):
        refresh_ci_locks.timestamp_for_date(text)


def test_today_utc_is_a_valid_date() -> None:
    today = refresh_ci_locks.today_utc()
    assert refresh_ci_locks.timestamp_for_date(today).startswith(today)


def test_uv_version_parsing() -> None:
    assert (
        refresh_ci_locks.uv_version_from_output("uv 0.11.14 (3fdfdc7d4 2026-05-12)\n")
        == "0.11.14"
    )
    with pytest.raises(ValueError, match="uv version"):
        refresh_ci_locks.uv_version_from_output("not uv")


# --- header -------------------------------------------------------------------


def test_header_starts_with_spdx_and_round_trips_the_date() -> None:
    header = refresh_ci_locks.render_header(_lock(), STAMP, "0.11.14")
    assert header.startswith(SPDX_LINE + "\n")
    assert refresh_ci_locks.parse_header(header) == (STAMP, "0.11.14")
    assert f"-r {_lock().relpath}" in header
    assert "scripts/dev/refresh_ci_locks.py" in header


def test_header_lines_are_comments_and_short() -> None:
    for lock in refresh_ci_locks.LOCKS:
        header = refresh_ci_locks.render_header(lock, STAMP, "0.11.14")
        for line in header.splitlines():
            assert line == "" or line.startswith("#"), line
            assert len(line) <= 90, line


def test_parse_header_ignores_a_malformed_timestamp() -> None:
    assert refresh_ci_locks.parse_header("# Locked as of: 2026-10-29\n") == (None, None)
    assert refresh_ci_locks.parse_header("click==8.4.2\n") == (None, None)


def test_compose_lock_normalises_line_endings() -> None:
    text = refresh_ci_locks.compose_lock(
        _lock(), _body().replace("\n", "\r\n"), STAMP, "1"
    )
    assert "\r" not in text
    assert text.endswith("\n")
    assert text.count("click==1.0.0") == 1


# --- requirement parsing and the diff decision --------------------------------


def test_requirement_entries_ignore_header_and_blank_lines() -> None:
    header = refresh_ci_locks.render_header(_lock(), STAMP, "0.11.14")
    entries = refresh_ci_locks.requirement_entries(header + "\n" + _body())
    assert set(entries) == {
        "click==1.0.0",
        "colorama==0.4.6 ; sys_platform == 'win32'",
    }
    assert entries["click==1.0.0"] == (f"sha256:{HASH_A}", f"sha256:{HASH_B}")
    assert entries["colorama==0.4.6 ; sys_platform == 'win32'"] == (f"sha256:{HASH_C}",)


def test_identical_requirements_with_different_headers_do_not_differ() -> None:
    old = refresh_ci_locks.compose_lock(_lock(), _body(), STAMP, "0.11.14")
    new = refresh_ci_locks.compose_lock(
        _lock(), _body(), "2026-11-05T00:00:00Z", "0.12.0"
    )
    assert refresh_ci_locks.diff_summary(old, new) == []


def test_version_change_is_reported_by_name() -> None:
    messages = refresh_ci_locks.diff_summary(_body("1.0.0"), _body("1.1.0"))
    assert messages == ["click: committed 1.0.0, fresh 1.1.0"]


def test_hash_change_at_the_same_version_is_reported() -> None:
    messages = refresh_ci_locks.diff_summary(_body(), _body(digest=HASH_C))
    assert messages == ["click: the hashes differ at 1.0.0"]


def test_added_and_removed_packages_are_reported() -> None:
    longer = _body() + f"extra==2.0 \\\n    --hash=sha256:{HASH_A}\n"
    assert refresh_ci_locks.diff_summary(_body(), longer) == [
        "extra: only in the fresh compile"
    ]
    assert refresh_ci_locks.diff_summary(longer, _body()) == [
        "extra: only in the committed lock"
    ]


def test_a_marker_change_is_a_different_slot() -> None:
    old = f"x==1 ; python_full_version < '3.11' \\\n    --hash=sha256:{HASH_A}\n"
    new = f"x==1 ; python_full_version < '3.12' \\\n    --hash=sha256:{HASH_A}\n"
    messages = refresh_ci_locks.diff_summary(old, new)
    assert len(messages) == 2


# --- the uv command line -------------------------------------------------------


def test_compile_command_for_the_dev_lock(tmp_path: Path) -> None:
    command = refresh_ci_locks.compile_command(_lock(), STAMP, tmp_path / "out.txt")
    assert command[:4] == ["uv", "pip", "compile", "pyproject.toml"]
    for flag in ("--universal", "--generate-hashes", "--no-annotate", "--no-header"):
        assert flag in command
    assert command[command.index("--python-version") + 1] == "3.10"
    assert command[command.index("--exclude-newer") + 1] == STAMP
    assert command[command.index("--extra") + 1] == "dev"
    assert "--only-binary" not in command
    assert "--upgrade" in command
    assert command[command.index("-o") + 1] == str(tmp_path / "out.txt")


def test_compile_command_reads_stdin_for_the_test_lock(tmp_path: Path) -> None:
    lock = refresh_ci_locks.lock_by_filename("requirements-ci-test.txt")
    command = refresh_ci_locks.compile_command(lock, STAMP, tmp_path / "o.txt")
    assert command[3:5] == ["pyproject.toml", "-"]
    assert "--extra" not in command


# --- refresh and --check with a stubbed compile -------------------------------


@pytest.fixture
def stubbed(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Replace uv: every lock compiles to ``bodies[filename]`` (default ``_body()``)."""
    bodies: dict[str, str] = {}

    def fake_compile(
        lock: refresh_ci_locks.Lock,
        timestamp: str,
        uv: str,
        work_dir: Path,
        repo_root: Path,
    ) -> str:
        return bodies.get(lock.filename, _body())

    monkeypatch.setattr(refresh_ci_locks, "compile_lock", fake_compile)
    monkeypatch.setattr(refresh_ci_locks, "read_uv_version", lambda uv: "0.11.14")
    monkeypatch.setattr(refresh_ci_locks, "_find_uv", lambda: "uv")
    monkeypatch.setattr(refresh_ci_locks, "_REPO_ROOT", Path())
    return bodies


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
        assert refresh_ci_locks.parse_header(text) == (STAMP, "0.11.14")


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
    assert STAMP in problems[0]


def test_check_uses_the_date_recorded_in_each_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stubbed: dict[str, str]
) -> None:
    refresh_ci_locks.refresh(tmp_path, "2026-09-01", "uv")
    stamps: list[str] = []
    real = refresh_ci_locks.compile_lock

    def spy(
        lock: refresh_ci_locks.Lock,
        timestamp: str,
        uv: str,
        work_dir: Path,
        repo_root: Path,
    ) -> str:
        stamps.append(timestamp)
        return real(lock, timestamp, uv, work_dir, repo_root)

    monkeypatch.setattr(refresh_ci_locks, "compile_lock", spy)
    assert refresh_ci_locks.check(tmp_path, "uv") == []
    assert stamps == ["2026-09-01T00:00:00Z"] * len(refresh_ci_locks.LOCKS)


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
    assert "match a fresh compile" in capsys.readouterr().out


def test_main_refresh_writes_into_the_repo_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stubbed: dict[str, str],
) -> None:
    monkeypatch.setattr(refresh_ci_locks, "_REPO_ROOT", tmp_path)
    assert refresh_ci_locks.main(["--date", "2026-10-29"]) == 0
    assert (tmp_path / "scripts/ci/requirements-ci-dev.txt").is_file()
    assert "wrote scripts/ci/requirements-ci-dev.txt" in capsys.readouterr().out


def test_main_rejects_a_bad_date_with_exit_two(
    capsys: pytest.CaptureFixture[str], stubbed: dict[str, str]
) -> None:
    assert refresh_ci_locks.main(["--date", "yesterday"]) == 2
    assert "lock date" in capsys.readouterr().err


def test_main_rejects_date_with_check(stubbed: dict[str, str]) -> None:
    with pytest.raises(SystemExit) as raised:
        refresh_ci_locks.main(["--check", "--date", "2026-10-29"])
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
        timestamp: str,
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
