# SPDX-License-Identifier: MIT

"""Tests for scripts/dev/refresh_ci_locks.py and scripts/dev/ci_lock_table.py.

The script compiles the hash-locked CI requirement files with ``uv pip compile``.
These tests need neither uv nor network access: they pin the lock table, the
header format, the date and cooldown arithmetic, the cooldown exceptions and the
diff decision, and they run the refresh and ``--check`` paths with the compile
step replaced by a stub.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import ci_lock_table  # noqa: E402
import refresh_ci_locks  # noqa: E402

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
# Built in two pieces so the REUSE parser does not read this literal as a licence tag.
SPDX_LINE = "# SPDX-License-" + "Identifier: MIT"
STAMP = "2026-10-29T00:00:00Z"
CUTOFF = "2026-10-22T00:00:00Z"
UV = "0.11.14"
TOOL_FILENAMES = [
    "requirements-ci-ruff.txt",
    "requirements-ci-bandit.txt",
    "requirements-ci-pip-audit.txt",
    "requirements-ci-pip-licenses.txt",
    "requirements-ci-pre-commit.txt",
]


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


def _stamp(
    locked_as_of: str = STAMP,
    cooldown_days: int = 7,
    cutoff: str = CUTOFF,
    uv_version: str = UV,
) -> refresh_ci_locks.Stamp:
    return refresh_ci_locks.Stamp(locked_as_of, cooldown_days, cutoff, uv_version)


# --- the lock table ----------------------------------------------------------


def test_table_has_the_nine_locks_in_scripts_ci() -> None:
    names = [lock.filename for lock in refresh_ci_locks.LOCKS]
    assert names == [
        "requirements-ci-dev.txt",
        "requirements-ci-runtime.txt",
        "requirements-ci-test.txt",
        "requirements-ci-prereqs.txt",
        *TOOL_FILENAMES,
    ]
    for lock in refresh_ci_locks.LOCKS:
        assert lock.relpath == f"scripts/ci/{lock.filename}"


def test_the_script_re_exports_the_table() -> None:
    assert refresh_ci_locks.LOCKS is ci_lock_table.LOCKS
    assert refresh_ci_locks.Lock is ci_lock_table.Lock
    assert refresh_ci_locks.lock_by_filename is ci_lock_table.lock_by_filename
    assert refresh_ci_locks.PYTHON_FLOOR == ci_lock_table.PYTHON_FLOOR == "3.10"
    assert refresh_ci_locks.CI_DIR == ci_lock_table.CI_DIR == "scripts/ci"


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
    for lock in refresh_ci_locks.LOCKS:
        if lock.filename != "requirements-ci-dev.txt":
            assert lock.extras == (), lock.filename


def test_each_tool_lock_holds_one_exact_spec_read_from_stdin() -> None:
    tools = [lock for lock in refresh_ci_locks.LOCKS if lock.tool]
    assert [lock.filename for lock in tools] == TOOL_FILENAMES
    expected_names = {
        "requirements-ci-ruff.txt": "ruff",
        "requirements-ci-bandit.txt": "bandit[toml]",
        "requirements-ci-pip-audit.txt": "pip-audit",
        "requirements-ci-pip-licenses.txt": "pip-licenses",
        "requirements-ci-pre-commit.txt": "pre-commit",
    }
    for lock in tools:
        assert lock.sources == ("-",), lock.filename
        (spec,) = lock.stdin_requirements
        name, _, version = spec.partition("==")
        assert name == expected_names[lock.filename], lock.filename
        assert version, spec
        assert not any(char in version for char in "<>=!~,"), spec


def test_project_locks_are_not_tool_locks() -> None:
    projects = [lock for lock in refresh_ci_locks.LOCKS if not lock.tool]
    assert [lock.filename for lock in projects] == [
        "requirements-ci-dev.txt",
        "requirements-ci-runtime.txt",
        "requirements-ci-test.txt",
        "requirements-ci-prereqs.txt",
    ]


def test_only_pip_audit_and_pre_commit_raise_the_python_floor() -> None:
    # pre-commit 4.7.0 needs Python 3.11. The pip-audit lock is compiled for 3.11
    # because the newest filelock that supports 3.10 has published advisories that
    # only a release for 3.11 or later fixes, and a line in a manifest is read by
    # Dependency review and Scorecard whatever its environment marker says.
    floors = {lock.filename: lock.python_floor for lock in refresh_ci_locks.LOCKS}
    assert floors.pop("requirements-ci-pip-audit.txt") == "3.11"
    assert floors.pop("requirements-ci-pre-commit.txt") == "3.11"
    assert set(floors.values()) == {"3.10"}


def test_lock_by_filename() -> None:
    assert refresh_ci_locks.lock_by_filename("requirements-ci-test.txt").extras == ()
    assert refresh_ci_locks.lock_by_filename("requirements-ci-ruff.txt").tool
    with pytest.raises(KeyError):
        refresh_ci_locks.lock_by_filename("requirements-ci-pip.txt")


def test_no_lock_has_a_sibling_in_file() -> None:
    ci_dir = REPO_ROOT / "scripts" / "ci"
    assert list(ci_dir.glob("*.in")) == []


# --- dates and the cooldown ----------------------------------------------------


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
        == UV
    )
    with pytest.raises(ValueError, match="uv version"):
        refresh_ci_locks.uv_version_from_output("not uv")


def test_the_default_cooldown_is_the_dependabot_cooldown() -> None:
    document = yaml.safe_load(
        (REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    )
    days = {
        entry["cooldown"]["default-days"]
        for entry in document["updates"]
        if entry["package-ecosystem"] == "pip" and entry["directory"] == "/scripts/ci"
    }
    assert days == {refresh_ci_locks.DEFAULT_COOLDOWN_DAYS} == {7}


@pytest.mark.parametrize(
    ("locked", "days", "cutoff"),
    [
        (STAMP, 7, CUTOFF),
        (STAMP, 0, STAMP),
        (STAMP, 1, "2026-10-28T00:00:00Z"),
        (STAMP, 29, "2026-09-30T00:00:00Z"),
        ("2026-03-03T00:00:00Z", 7, "2026-02-24T00:00:00Z"),
        ("2026-01-03T00:00:00Z", 7, "2025-12-27T00:00:00Z"),
        ("2028-03-01T00:00:00Z", 1, "2028-02-29T00:00:00Z"),
        ("2026-10-29T00:00:00Z", 365, "2025-10-29T00:00:00Z"),
    ],
)
def test_cutoff_is_the_lock_date_less_the_cooldown(
    locked: str, days: int, cutoff: str
) -> None:
    assert refresh_ci_locks.cutoff_timestamp(locked, days) == cutoff


def test_a_zero_cooldown_keeps_the_lock_date() -> None:
    assert refresh_ci_locks.cutoff_timestamp(STAMP, 0) == STAMP


def test_a_negative_cooldown_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        refresh_ci_locks.cutoff_timestamp(STAMP, -1)


def test_a_cooldown_past_the_calendar_is_rejected() -> None:
    with pytest.raises(ValueError, match="out of range"):
        refresh_ci_locks.cutoff_timestamp(STAMP, 10**9)


@pytest.mark.parametrize("text", ["2026-10-29", "2026-10-29T12:00:00Z", "", "x"])
def test_the_cutoff_needs_a_lock_timestamp(text: str) -> None:
    with pytest.raises(ValueError, match="lock timestamp"):
        refresh_ci_locks.cutoff_timestamp(text, 7)


# --- cooldown exceptions ---------------------------------------------------------

EXCEPTION_UNTIL = "2026-10-23T00:00:00Z"


def _exception_lock(*exceptions: tuple[str, str]) -> refresh_ci_locks.Lock:
    """Return the dev lock's row with ``exceptions`` as its cooldown exceptions."""
    return dataclasses.replace(_lock(), cooldown_exceptions=exceptions)


@pytest.mark.parametrize(
    "until", ["2026-10-23", "2026-10-23T00:00:00", "2026-10-23 00:00:00Z", "", "soon"]
)
def test_a_cooldown_exception_needs_a_full_utc_timestamp(until: str) -> None:
    with pytest.raises(ValueError, match="UTC timestamp"):
        _exception_lock(("virtualenv", until))


@pytest.mark.parametrize("until", [EXCEPTION_UNTIL, "2026-10-29T14:30:05Z"])
def test_a_cooldown_exception_takes_midnight_or_a_time_of_day(until: str) -> None:
    # A fix uploaded on the lock date itself is after the cutoff of a zero-day
    # cooldown, so an exception has to reach into that day.
    assert _exception_lock(("virtualenv", until)).cooldown_exceptions == (
        ("virtualenv", until),
    )


def test_an_exception_is_stale_once_the_cutoff_reaches_its_timestamp() -> None:
    lock = _exception_lock(
        ("virtualenv", EXCEPTION_UNTIL), ("filelock", "2026-10-30T00:00:00Z")
    )
    assert lock.stale_exceptions(CUTOFF) == []
    assert lock.stale_exceptions(EXCEPTION_UNTIL) == ["virtualenv"]
    assert lock.stale_exceptions("2026-10-31T00:00:00Z") == ["virtualenv", "filelock"]
    assert _lock().stale_exceptions("2099-01-01T00:00:00Z") == []


def test_compile_command_passes_each_cooldown_exception_to_uv(tmp_path: Path) -> None:
    lock = _exception_lock(
        ("virtualenv", EXCEPTION_UNTIL), ("filelock", "2026-10-24T12:30:00Z")
    )
    command = refresh_ci_locks.compile_command(lock, CUTOFF, tmp_path / "o.txt")
    passed = [
        command[index + 1]
        for index, item in enumerate(command)
        if item == "--exclude-newer-package"
    ]
    assert passed == [f"virtualenv={EXCEPTION_UNTIL}", "filelock=2026-10-24T12:30:00Z"]
    assert command[command.index("--exclude-newer") + 1] == CUTOFF


def test_a_lock_without_exceptions_passes_no_exclude_newer_package(
    tmp_path: Path,
) -> None:
    plain = [lock for lock in refresh_ci_locks.LOCKS if not lock.cooldown_exceptions]
    assert plain
    for lock in plain:
        command = refresh_ci_locks.compile_command(lock, CUTOFF, tmp_path / "o.txt")
        assert "--exclude-newer-package" not in command, lock.filename


def test_the_header_records_each_cooldown_exception_beside_the_cutoff() -> None:
    lock = _exception_lock(("virtualenv", EXCEPTION_UNTIL))
    header = refresh_ci_locks.render_header(lock, _stamp())
    assert header.splitlines()[-5:] == [
        f"# Locked as of: {STAMP}",
        "# Cooldown: 7 days",
        f"# Cutoff: {CUTOFF}",
        f"# Cooldown exception: virtualenv, files uploaded before {EXCEPTION_UNTIL}",
        f"# Compiled with: uv {UV}",
    ]
    # The exception line is neither the `Cooldown:` line nor a requirement.
    assert refresh_ci_locks.parse_header(header) == refresh_ci_locks.ParsedHeader(
        STAMP, 7, CUTOFF, UV
    )
    assert refresh_ci_locks.requirement_entries(header + _body()) == (
        refresh_ci_locks.requirement_entries(_body())
    )


def test_a_lock_without_exceptions_records_no_exception_line() -> None:
    header = refresh_ci_locks.render_header(_lock(), _stamp())
    assert refresh_ci_locks.EXCEPTION_PREFIX not in header
    assert _lock().exception_lines == []


def test_the_header_names_both_ways_to_lock_a_fix_younger_than_the_cooldown() -> None:
    header = " ".join(
        line.removeprefix("#").strip()
        for line in refresh_ci_locks.render_header(_lock(), _stamp()).splitlines()
    )
    assert "--cooldown-days 0" in header
    assert "00:00 UTC of the lock date" in header
    assert "cooldown exception" in header


# --- header -------------------------------------------------------------------


def test_header_starts_with_spdx_and_round_trips_the_stamp() -> None:
    header = refresh_ci_locks.render_header(_lock(), _stamp())
    assert header.startswith(SPDX_LINE + "\n")
    assert refresh_ci_locks.parse_header(header) == refresh_ci_locks.ParsedHeader(
        STAMP, 7, CUTOFF, UV
    )
    assert f"-r {_lock().relpath}" in header
    assert "scripts/dev/refresh_ci_locks.py" in header
    assert "scripts/dev/ci_lock_table.py" in header


def test_header_records_the_lock_date_the_cooldown_and_the_cutoff() -> None:
    header = refresh_ci_locks.render_header(_lock(), _stamp())
    assert header.splitlines()[-4:] == [
        f"# Locked as of: {STAMP}",
        "# Cooldown: 7 days",
        f"# Cutoff: {CUTOFF}",
        f"# Compiled with: uv {UV}",
    ]


@pytest.mark.parametrize(
    ("days", "text"), [(0, "0 days"), (1, "1 day"), (14, "14 days")]
)
def test_the_cooldown_line_round_trips(days: int, text: str) -> None:
    stamp = _stamp(
        cooldown_days=days,
        cutoff=refresh_ci_locks.cutoff_timestamp(STAMP, days),
    )
    header = refresh_ci_locks.render_header(_lock(), stamp)
    assert f"# Cooldown: {text}\n" in header
    assert refresh_ci_locks.parse_header(header).cooldown_days == days


def test_header_lines_are_comments_and_short() -> None:
    for lock in refresh_ci_locks.LOCKS:
        header = refresh_ci_locks.render_header(lock, _stamp())
        for line in header.splitlines():
            assert line == "" or line.startswith("#"), line
            assert len(line) <= 90, line


def test_header_names_the_python_floor_and_the_install_command_of_each_lock() -> None:
    for lock in refresh_ci_locks.LOCKS:
        header = refresh_ci_locks.render_header(lock, _stamp())
        assert f"Python {lock.python_floor} and later" in header, lock.filename
        assert (
            f"python -m pip install --require-hashes -r {lock.relpath}\n" in header
        ), lock.filename


def test_header_says_pip_belongs_to_the_pip_lock_and_names_the_escape_hatch() -> None:
    header = " ".join(
        line.removeprefix("#").strip()
        for line in refresh_ci_locks.render_header(_lock(), _stamp()).splitlines()
    )
    assert "requirements-ci-pip.txt pins pip" in header
    assert "--cooldown-days 0" in header


def test_parse_header_ignores_malformed_lines() -> None:
    assert (
        refresh_ci_locks.parse_header(
            "# Locked as of: 2026-10-29\n"
            "# Cooldown: seven days\n"
            "# Cutoff: 2026-10-22\n"
            "# Compiled with: uv \n"
        )
        == refresh_ci_locks.ParsedHeader()
    )
    assert refresh_ci_locks.parse_header("click==8.4.2\n") == (
        refresh_ci_locks.ParsedHeader()
    )


def test_parse_header_reports_the_lines_a_lock_does_not_carry() -> None:
    old_format = f"# Locked as of: {STAMP}\n# Compiled with: uv {UV}\n"
    header = refresh_ci_locks.parse_header(old_format)
    assert header.missing() == ["Cooldown", "Cutoff"]
    assert refresh_ci_locks.ParsedHeader().missing() == [
        "Locked as of",
        "Cooldown",
        "Cutoff",
        "Compiled with",
    ]
    complete = refresh_ci_locks.parse_header(
        refresh_ci_locks.render_header(_lock(), _stamp())
    )
    assert complete.missing() == []


def test_compose_lock_normalises_line_endings() -> None:
    text = refresh_ci_locks.compose_lock(
        _lock(), _body().replace("\n", "\r\n"), _stamp(uv_version="1")
    )
    assert "\r" not in text
    assert text.endswith("\n")
    assert text.count("click==1.0.0") == 1


# --- requirement parsing and the diff decision --------------------------------


def test_requirement_entries_ignore_header_and_blank_lines() -> None:
    header = refresh_ci_locks.render_header(_lock(), _stamp())
    entries = refresh_ci_locks.requirement_entries(header + "\n" + _body())
    assert set(entries) == {
        "click==1.0.0",
        "colorama==0.4.6 ; sys_platform == 'win32'",
    }
    assert entries["click==1.0.0"] == (f"sha256:{HASH_A}", f"sha256:{HASH_B}")
    assert entries["colorama==0.4.6 ; sys_platform == 'win32'"] == (f"sha256:{HASH_C}",)


def test_a_trailing_uv_comment_is_not_a_requirement() -> None:
    body = (
        _body() + "\n# The following packages were excluded from the output:\n# pip\n"
    )
    assert set(refresh_ci_locks.requirement_entries(body)) == set(
        refresh_ci_locks.requirement_entries(_body())
    )


def test_identical_requirements_with_different_headers_do_not_differ() -> None:
    old = refresh_ci_locks.compose_lock(_lock(), _body(), _stamp())
    newer = _stamp(
        locked_as_of="2026-11-05T00:00:00Z",
        cutoff="2026-10-29T00:00:00Z",
        uv_version="0.12.0",
    )
    new = refresh_ci_locks.compose_lock(_lock(), _body(), newer)
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
    command = refresh_ci_locks.compile_command(_lock(), CUTOFF, tmp_path / "out.txt")
    assert command[:4] == ["uv", "pip", "compile", "pyproject.toml"]
    for flag in ("--universal", "--generate-hashes", "--no-annotate", "--no-header"):
        assert flag in command
    assert command[command.index("--python-version") + 1] == "3.10"
    assert command[command.index("--exclude-newer") + 1] == CUTOFF
    assert command[command.index("--extra") + 1] == "dev"
    assert "--only-binary" not in command
    assert "--upgrade" in command
    assert command[command.index("-o") + 1] == str(tmp_path / "out.txt")


def test_compile_command_reads_stdin_for_the_test_lock(tmp_path: Path) -> None:
    lock = refresh_ci_locks.lock_by_filename("requirements-ci-test.txt")
    command = refresh_ci_locks.compile_command(lock, CUTOFF, tmp_path / "o.txt")
    assert command[3:5] == ["pyproject.toml", "-"]
    assert "--extra" not in command


def test_compile_command_reads_only_stdin_for_a_tool_lock(tmp_path: Path) -> None:
    lock = refresh_ci_locks.lock_by_filename("requirements-ci-ruff.txt")
    command = refresh_ci_locks.compile_command(lock, CUTOFF, tmp_path / "o.txt")
    assert command[3] == "-"
    assert command[4] == "--universal"
    assert "--extra" not in command


def test_every_compile_command_leaves_pip_out_of_the_closure(tmp_path: Path) -> None:
    for lock in refresh_ci_locks.LOCKS:
        command = refresh_ci_locks.compile_command(lock, CUTOFF, tmp_path / "o.txt")
        index = command.index("--no-emit-package")
        assert command[index + 1] == "pip", lock.filename


def test_compile_command_uses_the_python_floor_of_each_lock(tmp_path: Path) -> None:
    for lock in refresh_ci_locks.LOCKS:
        command = refresh_ci_locks.compile_command(lock, CUTOFF, tmp_path / "o.txt")
        assert command[command.index("--python-version") + 1] == lock.python_floor
    pre_commit = refresh_ci_locks.lock_by_filename("requirements-ci-pre-commit.txt")
    command = refresh_ci_locks.compile_command(pre_commit, CUTOFF, tmp_path / "o.txt")
    assert command[command.index("--python-version") + 1] == "3.11"


class _Completed:
    def __init__(self, returncode: int, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr


def test_compile_lock_passes_the_cutoff_and_the_stdin_specs_to_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> _Completed:
        seen["command"] = command
        seen["input"] = kwargs.get("input")
        output = Path(command[command.index("-o") + 1])
        output.write_bytes(_body().encode("utf-8"))
        return _Completed(0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    lock = refresh_ci_locks.lock_by_filename("requirements-ci-test.txt")
    body = refresh_ci_locks.compile_lock(lock, CUTOFF, "uv", tmp_path, REPO_ROOT)
    assert body == _body()
    command = seen["command"]
    assert isinstance(command, list)
    assert command[command.index("--exclude-newer") + 1] == CUTOFF
    assert seen["input"] == "pytest\npytest-xdist\nbuild\n"


def test_a_compile_that_cannot_resolve_names_the_cutoff_and_the_way_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(command: list[str], **kwargs: object) -> _Completed:
        return _Completed(1, "No solution found when resolving dependencies")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError) as raised:
        refresh_ci_locks.compile_lock(_lock(), CUTOFF, "uv", tmp_path, REPO_ROOT)
    message = str(raised.value)
    assert "No solution found" in message
    assert CUTOFF in message
    assert "--cooldown-days 0" in message
    assert "cooldown exception" in message
    assert "scripts/dev/ci_lock_table.py" in message
