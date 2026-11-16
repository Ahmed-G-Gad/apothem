# SPDX-License-Identifier: MIT

"""A git command or validator that stalls ends in bounded time and never passes.

Why these tests exist. A project can arrive with its ``.git`` folder from
someone else, in an archive or a shared folder, and git reads that
repository's own configuration on every run. An ``include.path`` that names a
FIFO makes git wait for ever while it opens the file. Several validators run
git, and the gate runs each standalone validator in a child process, so one
waiting git held ``gate --all`` up for good, and a validator whose git ran past
its time limit reported a pass without having checked anything.

The tests cover both halves:

- each validator's own git call has a time limit, and a call that runs past
  it reports ``passed: false`` with a ``check_error`` that names the command;
- the gate gives each standalone validator a time limit, stops a validator
  that runs past it together with the processes it started, and reports it as
  not passed, with the reason. The advisory default still exits ``0``; only
  ``--strict`` turns that into exit ``2``.

A test that can wait runs the code on a thread with a deadline and, for a
FIFO, lets the waiting read go, so a regression fails the test instead of
hanging the run. The FIFO tests are POSIX-only; the tests that run everywhere
fake :class:`subprocess.TimeoutExpired` or give the gate a validator launcher
that sleeps. Each repository is a throwaway one in ``tmp_path``, built with
fixture git under :func:`hermetic_git_env`.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import pytest

from apothem.conformity import (
    agents_md_coverage_grep,
    conventional_commit_grep,
    gate,
    production_ready_pr_grep,
    semver_stability_grep,
)
from tests._shared.git_env import hermetic_git_env

_T = TypeVar("_T")

# How long a run may take before a test calls it stalled.
_DEADLINE_SECONDS = 30.0
# The git time limit the FIFO tests give a validator, so a waiting git ends
# quickly.
_SHORT_GIT_TIMEOUT_SECONDS = 2
# The validator time limit the gate tests set.
_SHORT_VALIDATOR_TIMEOUT_SECONDS = 2
# The validator time limit of the gate test whose validator waits on a FIFO:
# long enough for the child to start git, shorter than the commit-subject
# validator's own git limit, so the gate's limit is the one that ends the run.
_FIFO_VALIDATOR_TIMEOUT_SECONDS = 4
# How long the stand-in validators sleep: longer than the deadline above, so a
# gate that waits for them fails the test.
_SLEEP_SECONDS = 45
# How long a stopped process may take to disappear.
_EXIT_WAIT_SECONDS = 10.0

_POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt", reason="FIFOs and process groups exist only on POSIX systems"
)


# --- Fixture repositories ----------------------------------------------------


@pytest.fixture(autouse=True)
def _hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide the host's git configuration from every git this test starts.

    The validators and the gate's child processes inherit this environment, so
    a developer's global settings cannot change what git does in a test.
    """
    clean = hermetic_git_env()
    for name in list(os.environ):
        if name not in clean:
            monkeypatch.delenv(name)
    for name in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM"):
        monkeypatch.setenv(name, clean[name])


def _git(repo: Path, *args: str) -> None:
    """Run fixture git in *repo*."""
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        encoding="utf-8",
    )


def _project(tmp_path: Path) -> Path:
    """Return a committed repository with a conformant HEAD and a README folder.

    ``pkg/README.md`` makes ``pkg`` a folder the companion check inspects.
    """
    repo = tmp_path / "project"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "README.md").write_text("# pkg\n", encoding="utf-8")
    (repo / "pkg" / "AGENTS.md").write_text("# pkg agents\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@apothem.invalid")
    _git(repo, "config", "user.name", "apothem-test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "test(pkg): add the package readme")
    return repo


def _release_fifo(fifo: Path) -> None:
    """Let one reader waiting to open *fifo* go on: open it to write, then close.

    The reader then reads end-of-file. With no reader waiting, the open fails
    and nothing happens.
    """
    try:
        descriptor = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return
    os.close(descriptor)


def _fifo_has_reader(fifo: Path) -> bool:
    """Return True while a process has *fifo* open, or is opening it, to read.

    A write-only open that does not wait fails when no reader exists. When it
    succeeds, closing it lets that reader go on.
    """
    try:
        descriptor = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return False
    os.close(descriptor)
    return True


def _include_fifo(repo: Path, fifo: Path) -> None:
    """Make *repo*'s own configuration include *fifo*, so git waits opening it."""
    os.mkfifo(fifo)
    with (repo / ".git" / "config").open("a", encoding="utf-8") as config:
        config.write(f"[include]\n\tpath = {fifo.as_posix()}\n")


def _run_guarded(func: Callable[[], _T], *, release: Callable[[], None]) -> _T:
    """Return ``func()``, run on a thread; fail when it outlives the deadline.

    *release* is called until the thread ends, so a run waiting on a FIFO
    finishes and no blocked thread or git process outlives the test. git opens
    an included file more than once, hence the loop.
    """
    outcome: dict[str, object] = {}

    def target() -> None:
        try:
            outcome["value"] = func()
        except BaseException as exc:  # handed back to the test thread below
            outcome["error"] = exc

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(_DEADLINE_SECONDS)
    stalled = worker.is_alive()
    give_up = time.monotonic() + _DEADLINE_SECONDS
    while worker.is_alive() and time.monotonic() < give_up:
        release()
        worker.join(0.2)
    assert not stalled, f"the run was still going after {_DEADLINE_SECONDS} seconds"
    error = outcome.get("error")
    if isinstance(error, BaseException):
        raise error
    return outcome["value"]  # type: ignore[return-value]


def _no_release() -> None:
    """Nothing to let go: the run waits on a sleeping process, not a FIFO."""


def _timing_out_run(
    *args: object, **kwargs: object
) -> subprocess.CompletedProcess[str]:
    """Stand in for ``subprocess.run``: every git call runs past its time limit."""
    timeout = kwargs.get("timeout")
    assert isinstance(timeout, (int, float)), "git ran without a time limit"
    assert timeout > 0
    raise subprocess.TimeoutExpired(cmd="git", timeout=timeout)


def _printed_payload(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    """Return the JSON report a validator's command-line entry printed."""
    payload: dict[str, object] = json.loads(capsys.readouterr().out)
    return payload


def _assert_timeout_reported(payload: dict[str, object], command: str) -> None:
    """The report does not pass and names the git *command* that ran too long."""
    assert payload["passed"] is False
    check_error = str(payload.get("check_error"))
    assert command in check_error, check_error
    assert "did not finish" in check_error, check_error


# --- Each validator's git call: a time limit that does not pass --------------


def test_commit_subject_timeout_does_not_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ``git log`` past its limit is not the no-history exemption."""
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(subprocess, "run", _timing_out_run)

    result = conventional_commit_grep.check_repo(tmp_path)
    assert result.passed is False
    assert result.status == "git-timeout"

    exit_code = conventional_commit_grep._main(
        ["conventional-commit-grep", str(tmp_path)]
    )
    payload = _printed_payload(capsys)
    assert exit_code == conventional_commit_grep.EXIT_FAIL
    _assert_timeout_reported(payload, "git log")
    assert payload["inspected"] == 0
    assert payload["empty_scope_expected"] is False


def test_commit_subject_without_history_still_passes(tmp_path: Path) -> None:
    """No ``.git`` is still the documented exemption, not a check error."""
    result = conventional_commit_grep.check_repo(tmp_path)
    assert result.passed is True
    assert result.status == "not-a-git-repo"


def test_companion_freshness_timeout_does_not_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The advisory companion check fails, not degrades, when ``git log`` stalls."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "README.md").write_text("# pkg\n", encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", _timing_out_run)

    result = agents_md_coverage_grep.check(tmp_path)
    assert result.passed is False
    assert result.freshness_checked is False

    exit_code = agents_md_coverage_grep._main(
        ["agents-md-coverage-grep", str(tmp_path)]
    )
    payload = _printed_payload(capsys)
    # Advisory findings exit 0; a check that could not finish does not.
    assert exit_code == gate.EXIT_FAIL
    _assert_timeout_reported(payload, "git log")


def test_companion_check_without_history_still_passes(tmp_path: Path) -> None:
    """Outside a repository the companion check still degrades to presence-only."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "README.md").write_text("# pkg\n", encoding="utf-8")

    result = agents_md_coverage_grep.check(tmp_path)
    assert result.passed is True
    assert result.freshness_checked is False


def test_staged_change_set_timeout_does_not_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``production-ready-pr-grep --staged`` fails when ``git diff`` stalls."""
    monkeypatch.setattr(subprocess, "run", _timing_out_run)

    exit_code = production_ready_pr_grep._main(["production-ready-pr-grep", "--staged"])
    payload = _printed_payload(capsys)
    assert exit_code == production_ready_pr_grep.EXIT_FAIL
    _assert_timeout_reported(payload, "git diff")
    assert payload["findings"] == []


def test_semver_staged_list_timeout_does_not_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``semver-stability-grep --staged`` fails when the staged list stalls."""
    monkeypatch.setattr(semver_stability_grep, "current_version", lambda: "1.2.3")
    monkeypatch.setattr(subprocess, "run", _timing_out_run)

    exit_code = semver_stability_grep._main(["semver-stability-grep", "--staged"])
    payload = _printed_payload(capsys)
    assert exit_code == semver_stability_grep.EXIT_FAIL
    _assert_timeout_reported(payload, "git diff")


def test_semver_staged_file_read_timeout_does_not_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A staged file whose ``git show`` stalls is not skipped as if unchanged."""
    monkeypatch.setattr(semver_stability_grep, "current_version", lambda: "1.2.3")

    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = args[0]
        assert isinstance(argv, list)
        if "diff" in argv:
            return subprocess.CompletedProcess(argv, 0, "src/apothem/api.py\n", "")
        return _timing_out_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)

    exit_code = semver_stability_grep._main(["semver-stability-grep", "--staged"])
    payload = _printed_payload(capsys)
    assert exit_code == semver_stability_grep.EXIT_FAIL
    _assert_timeout_reported(payload, "git show")


# --- The gate's own limit on each standalone validator -----------------------


_SLEEPING_LAUNCHER = f"import time\ntime.sleep({_SLEEP_SECONDS})\n"


def _short_validator_limit(
    monkeypatch: pytest.MonkeyPatch, seconds: int = _SHORT_VALIDATOR_TIMEOUT_SECONDS
) -> None:
    """Give each standalone validator a short time limit in the gate."""
    monkeypatch.setattr(gate, "STANDALONE_TIMEOUT_SECONDS", seconds, raising=False)


def _stopped_report(
    output: str, seconds: int = _SHORT_VALIDATOR_TIMEOUT_SECONDS
) -> dict[str, object]:
    """Return the report the gate wrote for a validator it stopped."""
    payload: dict[str, object] = json.loads(output)
    assert payload["passed"] is False
    check_error = str(payload.get("check_error"))
    assert f"{seconds} seconds" in check_error, check_error
    assert "did not finish" in check_error, check_error
    return payload


def test_validator_past_its_time_limit_is_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A validator that never finishes is stopped at the limit and does not pass."""
    _short_validator_limit(monkeypatch)
    monkeypatch.setattr(gate, "_STANDALONE_LAUNCHER", _SLEEPING_LAUNCHER)

    started = time.monotonic()
    passed, output = _run_guarded(
        lambda: gate._run_standalone("naming-grep", tmp_path), release=_no_release
    )
    took = time.monotonic() - started

    assert passed is False
    _stopped_report(output)
    assert took < _SLEEP_SECONDS, f"the gate waited {took:.1f}s for the validator"


# A launcher that starts a process of its own, which inherits the launcher's
# output, writes that process's ID to a file, then sleeps. The gate must not
# wait for that process to close the output it shares.
_FORKING_LAUNCHER = (
    "import subprocess, sys, time\n"
    "from pathlib import Path\n"
    "child = subprocess.Popen("
    f"[sys.executable, '-c', 'import time; time.sleep({_SLEEP_SECONDS})'])\n"
    "Path(sys.argv[3]).joinpath('helper.pid').write_text(str(child.pid))\n"
    f"time.sleep({_SLEEP_SECONDS})\n"
)


def _process_gone(pid: int) -> bool:
    """Return True once no process with *pid* exists (POSIX)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def _end_process(pid: int) -> None:
    """Stop *pid* if it still runs, so no sleeper outlives the test."""
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return


def test_stopped_validator_does_not_wait_for_a_process_it_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A process the validator started cannot hold the stopped run open.

    On POSIX the gate stops the validator's whole process group, so the helper
    process ends too. On Windows the gate stops the validator and stops waiting
    for its output a few seconds later, so the run still ends.
    """
    _short_validator_limit(monkeypatch)
    monkeypatch.setattr(gate, "_STOP_GRACE_SECONDS", 1, raising=False)
    monkeypatch.setattr(gate, "_STANDALONE_LAUNCHER", _FORKING_LAUNCHER)
    pid_file = tmp_path / "helper.pid"

    started = time.monotonic()
    helper_gone = False
    try:
        passed, output = _run_guarded(
            lambda: gate._run_standalone("naming-grep", tmp_path), release=_no_release
        )
        took = time.monotonic() - started
        assert passed is False
        _stopped_report(output)
        assert took < _SLEEP_SECONDS, f"the gate waited {took:.1f}s for the helper"
        if os.name != "nt":
            helper = int(pid_file.read_text(encoding="utf-8"))
            give_up = time.monotonic() + _EXIT_WAIT_SECONDS
            while not _process_gone(helper) and time.monotonic() < give_up:
                time.sleep(0.1)
            helper_gone = _process_gone(helper)
            assert helper_gone, "the validator's helper process still runs"
    finally:
        # Stop a helper still running (on Windows the gate leaves it), but
        # never signal an ID already seen gone: the system may reuse it.
        if pid_file.is_file() and not helper_gone:
            _end_process(int(pid_file.read_text(encoding="utf-8")))


def test_all_reports_a_stopped_validator_as_not_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--all`` lists the stopped validator with its reason; only strict exits 2."""
    _short_validator_limit(monkeypatch)
    monkeypatch.setattr(gate, "_STANDALONE_LAUNCHER", _SLEEPING_LAUNCHER)
    monkeypatch.setattr(gate, "STANDALONE_MODULES", ("naming-grep",))

    advisory = _run_guarded(
        lambda: gate.main(["gate", "--all", str(tmp_path)]), release=_no_release
    )
    payload = json.loads(capsys.readouterr().out)
    assert advisory == gate.EXIT_PASS
    assert payload["passed"] is False
    (entry,) = payload["results"]
    assert entry["validator"] == "naming-grep"
    assert entry["passed"] is False
    assert "did not finish" in str(entry.get("check_error"))

    strict = _run_guarded(
        lambda: gate.main(["gate", "--all", str(tmp_path), "--strict"]),
        release=_no_release,
    )
    capsys.readouterr()
    assert strict == gate.EXIT_FAIL

    checked = _run_guarded(
        lambda: gate.main(
            ["gate", "--check", "naming-grep", str(tmp_path), "--strict"]
        ),
        release=_no_release,
    )
    _stopped_report(capsys.readouterr().out)
    assert checked == gate.EXIT_FAIL


# --- A real repository whose configuration makes git wait (POSIX) ------------


@_POSIX_ONLY
def test_commit_subject_read_that_waits_on_its_configuration_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``include.path`` naming a FIFO makes ``git log`` wait; the limit ends it."""
    repo = _project(tmp_path)
    fifo = tmp_path / "config-fifo"
    _include_fifo(repo, fifo)
    monkeypatch.setattr(
        conventional_commit_grep, "GIT_TIMEOUT_SECONDS", _SHORT_GIT_TIMEOUT_SECONDS
    )

    result = _run_guarded(
        lambda: conventional_commit_grep.check_repo(repo),
        release=lambda: _release_fifo(fifo),
    )
    assert result.passed is False
    assert result.status == "git-timeout"
    assert "did not finish" in str(result.check_error)


@_POSIX_ONLY
def test_companion_freshness_read_that_waits_on_its_configuration_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The companion check's ``git log`` ends at its limit and does not pass."""
    repo = _project(tmp_path)
    fifo = tmp_path / "config-fifo"
    _include_fifo(repo, fifo)
    monkeypatch.setattr(
        agents_md_coverage_grep, "GIT_TIMEOUT_SECONDS", _SHORT_GIT_TIMEOUT_SECONDS
    )

    result = _run_guarded(
        lambda: agents_md_coverage_grep.check(repo),
        release=lambda: _release_fifo(fifo),
    )
    assert result.passed is False
    assert "did not finish" in str(result.check_error)


@_POSIX_ONLY
def test_staged_change_set_read_that_waits_on_its_configuration_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``production-ready-pr-grep --staged`` ends at its limit and does not pass."""
    repo = _project(tmp_path)
    fifo = tmp_path / "config-fifo"
    _include_fifo(repo, fifo)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(
        production_ready_pr_grep, "GIT_TIMEOUT_SECONDS", _SHORT_GIT_TIMEOUT_SECONDS
    )

    exit_code = _run_guarded(
        lambda: production_ready_pr_grep._main(
            ["production-ready-pr-grep", "--staged"]
        ),
        release=lambda: _release_fifo(fifo),
    )
    assert exit_code == production_ready_pr_grep.EXIT_FAIL
    _assert_timeout_reported(_printed_payload(capsys), "git diff")


@_POSIX_ONLY
def test_semver_staged_read_that_waits_on_its_configuration_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``semver-stability-grep --staged`` ends at its limit and does not pass."""
    repo = _project(tmp_path)
    fifo = tmp_path / "config-fifo"
    _include_fifo(repo, fifo)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(semver_stability_grep, "current_version", lambda: "1.2.3")
    monkeypatch.setattr(
        semver_stability_grep, "GIT_TIMEOUT_SECONDS", _SHORT_GIT_TIMEOUT_SECONDS
    )

    exit_code = _run_guarded(
        lambda: semver_stability_grep._main(["semver-stability-grep", "--staged"]),
        release=lambda: _release_fifo(fifo),
    )
    assert exit_code == semver_stability_grep.EXIT_FAIL
    _assert_timeout_reported(_printed_payload(capsys), "git diff")


@_POSIX_ONLY
def test_gate_stops_a_validator_whose_git_waits_and_ends_that_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate's limit ends the validator and the waiting git it started.

    The commit-subject validator's own git limit is longer than the gate's
    limit here, so the gate stops the run. Afterwards no process may still be
    waiting to read the FIFO: the gate stopped the validator's process group.
    """
    repo = _project(tmp_path)
    fifo = tmp_path / "config-fifo"
    _include_fifo(repo, fifo)
    _short_validator_limit(monkeypatch, _FIFO_VALIDATOR_TIMEOUT_SECONDS)

    passed, output = _run_guarded(
        lambda: gate._run_standalone("conventional-commit-grep", repo),
        release=lambda: _release_fifo(fifo),
    )
    assert passed is False
    _stopped_report(output, _FIFO_VALIDATOR_TIMEOUT_SECONDS)
    give_up = time.monotonic() + _EXIT_WAIT_SECONDS
    while time.monotonic() < give_up:
        if not _fifo_has_reader(fifo):
            break
        time.sleep(0.1)
    else:
        pytest.fail("a git started by the stopped validator still waits on the FIFO")


def test_gate_gives_validators_empty_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A validator child reads from the null device, never from the gate's input.

    The child's standard input is recorded where the process starts, not read
    in the child: a child of a pytest-xdist worker that read the inherited
    input would take the worker's own messages.
    """
    recorded: list[object] = []
    real_popen = subprocess.Popen

    class RecordingPopen(real_popen):  # type: ignore[misc,valid-type]
        def __init__(self, *args: object, **kwargs: object) -> None:
            recorded.append(kwargs.get("stdin"))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", RecordingPopen)
    monkeypatch.setattr(gate, "_STANDALONE_LAUNCHER", "pass\n")

    passed, _output = _run_guarded(
        lambda: gate._run_standalone("naming-grep", tmp_path), release=_no_release
    )
    assert passed is True
    assert recorded == [subprocess.DEVNULL]
