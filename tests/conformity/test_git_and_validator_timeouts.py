# SPDX-License-Identifier: MIT

"""A git command or validator that stalls ends in bounded time and never passes.

Why these tests exist. A project can arrive with its ``.git`` folder from
someone else, in an archive or a shared folder, and git reads that
repository's own configuration on every run. An ``include.path`` that names a
FIFO, or on Windows a named pipe, makes git wait for ever while it reads the
file. Several validators run git, and the gate runs each standalone validator
in a child process, so one waiting git held ``gate --all`` up for good, and a
validator whose git ran past its time limit reported a pass without having
checked anything.

The tests cover:

- each validator's own git call has a time limit, and a call that runs past
  it, or a git that refuses a checkout, reports ``passed: false`` with a
  ``check_error`` that names the command; no repository, no commit and no git
  stay exempt;
- the limit holds on Windows behind Git for Windows' ``cmd\\git.exe``
  launcher, which starts the real git that holds the output;
- the gate gives each standalone validator a time limit, stops a validator
  that runs past it together with every program it started, and reports it
  as not passed. The advisory default still exits ``0``; only ``--strict``
  turns that into exit ``2``;
- a ``SIGTERM`` or ``SIGHUP`` to the gate stops the validator and its git,
  although the validator runs in a session of its own.

A test that can wait runs the code on a thread with a deadline and lets the
waiting read go, so a regression fails the test instead of hanging the run.
The FIFO and signal tests are POSIX-only and the named-pipe tests Windows-only;
the tests that run everywhere fake :class:`subprocess.TimeoutExpired`, break a
repository's configuration, or give the gate a validator launcher that sleeps.
Each repository is a throwaway one in ``tmp_path``, built with fixture git
under :func:`hermetic_git_env`.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import pytest

from apothem.conformity import (
    _bounded_run,
    _grep_base,
    agents_md_coverage_grep,
    conventional_commit_grep,
    gate,
    no_global_plans_grep,
    production_ready_pr_grep,
    semver_stability_grep,
)
from apothem.conformity._grep_base import CHECK_ERROR_KEY
from tests._shared.git_env import hermetic_git_env

_T = TypeVar("_T")

_REPO_ROOT = Path(__file__).resolve().parents[2]

# How long a run may take before a test calls it stalled.
_DEADLINE_SECONDS = 30.0
# The git time limit the stall tests give a validator, so a waiting git ends
# quickly.
_SHORT_GIT_TIMEOUT_SECONDS = 2
# The validator time limit the gate tests set.
_SHORT_VALIDATOR_TIMEOUT_SECONDS = 2
# The validator time limit of the gate tests whose validator's git waits: long
# enough for the child to start git, shorter than the commit-subject
# validator's own git limit, so the gate's limit is the one that ends the run.
_STALL_VALIDATOR_TIMEOUT_SECONDS = 4
# How long the stand-in validators sleep: longer than the deadline above, so a
# gate that waits for them fails the test.
_SLEEP_SECONDS = 45
# How long a stopped process may take to disappear.
_EXIT_WAIT_SECONDS = 10.0

_POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt", reason="FIFOs, sessions and signals here are POSIX features"
)
_WINDOWS_ONLY = pytest.mark.skipif(
    os.name != "nt", reason="named pipes and job objects are Windows features"
)
_NEEDS_PROC = pytest.mark.skipif(
    not Path("/proc/self/cmdline").is_file(),
    reason="finding the validator's processes reads /proc",
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


def _include(repo: Path, path: str) -> None:
    """Make *repo*'s own configuration include *path*."""
    with (repo / ".git" / "config").open("a", encoding="utf-8") as config:
        config.write(f"[include]\n\tpath = {path}\n")


def _break_config(repo: Path) -> None:
    """Add a line git cannot parse to *repo*'s own configuration."""
    with (repo / ".git" / "config").open("a", encoding="utf-8") as config:
        config.write("[broken\n")


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


def _include_fifo(repo: Path, fifo: Path) -> None:
    """Make *repo*'s own configuration include *fifo*, so git waits opening it."""
    os.mkfifo(fifo)
    _include(repo, fifo.as_posix())


# Windows named-pipe flags that ``_winapi`` does not name.
_FILE_FLAG_OVERLAPPED = 0x40000000
_PIPE_UNLIMITED_INSTANCES = 255
# Instances listening from the start: git opens an included file more than
# once in quick succession, and an open with no listening instance fails.
_PIPE_INSTANCES = 4


class _StalledPipe:
    """A Windows named pipe that accepts readers and never writes to them.

    A git whose configuration includes it waits for ever in its read, as on a
    FIFO. :meth:`readers` tells whether git came and whether it is still there.
    """

    def __init__(self) -> None:
        import _winapi

        self.name = f"apothem-test-{uuid.uuid4().hex}"
        path = "\\\\.\\pipe\\" + self.name
        self._closed = False
        self._instances: list[tuple[int, _winapi.Overlapped]] = []
        for _ in range(_PIPE_INSTANCES):
            handle = _winapi.CreateNamedPipe(
                path,
                _winapi.PIPE_ACCESS_DUPLEX | _FILE_FLAG_OVERLAPPED,
                _winapi.PIPE_WAIT,
                _PIPE_UNLIMITED_INSTANCES,
                65536,
                65536,
                0,
                _winapi.NULL,
            )
            pending = _winapi.ConnectNamedPipe(handle, overlapped=True)
            self._instances.append((handle, pending))

    @property
    def include_path(self) -> str:
        """The pipe's path as a git configuration names it."""
        return f"//./pipe/{self.name}"

    def readers(self) -> tuple[int, int]:
        """Return how many readers came, and how many are still connected."""
        import _winapi

        came = still_there = 0
        for handle, pending in self._instances:
            if _winapi.WaitForSingleObject(pending.event, 0) != 0:
                continue
            came += 1
            try:
                _winapi.PeekNamedPipe(handle, 0)
            except OSError:
                continue
            still_there += 1
        return came, still_there

    def close(self) -> None:
        """Close every instance, which ends any read still waiting on one."""
        import _winapi

        if self._closed:
            return
        self._closed = True
        for handle, pending in self._instances:
            if _winapi.WaitForSingleObject(pending.event, 0) != 0:
                pending.cancel()
                with contextlib.suppress(OSError):
                    pending.GetOverlappedResult(True)
            _winapi.CloseHandle(handle)


def _git_launcher_folder() -> Path | None:
    """Return Git for Windows' ``cmd`` folder, whose ``git.exe`` is a launcher."""
    try:
        exec_path = subprocess.run(
            ["git", "--exec-path"],
            capture_output=True,
            encoding="utf-8",
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    folder = Path(exec_path).parents[2] / "cmd"
    return folder if (folder / "git.exe").is_file() else None


def _run_guarded(func: Callable[[], _T], *, release: Callable[[], None]) -> _T:
    """Return ``func()``, run on a thread; fail when it outlives the deadline.

    *release* is called until the thread ends, so a run waiting on a FIFO or a
    named pipe finishes and no blocked thread or git process outlives the
    test. git opens an included file more than once, hence the loop.
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
    """Nothing to let go: the run waits on a sleeping process, not a pipe."""


def _timing_out_run(
    argv: list[str], *, timeout: float | None, **_kwargs: object
) -> subprocess.CompletedProcess[str]:
    """Stand in for ``run_bounded``: every git call runs past its time limit."""
    assert isinstance(timeout, (int, float)), "git ran without a time limit"
    assert timeout > 0
    raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)


# The git subcommands the validators run; ``run_git`` puts its own options
# (and ``-C <folder>``) before the subcommand.
_SUBCOMMANDS = frozenset({"cat-file", "config", "diff", "log", "ls-files", "rev-parse"})


def _subcommand(argv: list[str]) -> str:
    """Return the git subcommand in *argv*, after ``run_git``'s own options."""
    return next(arg for arg in argv if arg in _SUBCOMMANDS)


def _printed_payload(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    """Return the JSON report a validator's command-line entry printed."""
    payload: dict[str, object] = json.loads(capsys.readouterr().out)
    return payload


def _assert_check_error(
    payload: dict[str, object], command: str, what: str = "did not finish"
) -> None:
    """The report does not pass, and its ``check_error`` names *command*."""
    assert payload["passed"] is False
    check_error = str(payload.get(CHECK_ERROR_KEY))
    assert command in check_error, check_error
    assert what in check_error, check_error


# --- Each validator's git call: a time limit that does not pass --------------


def test_commit_subject_timeout_does_not_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ``git log`` past its limit is not the no-history exemption."""
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(_bounded_run, "run_bounded", _timing_out_run)

    result = conventional_commit_grep.check_repo(tmp_path)
    assert result.passed is False
    assert result.status == "git-timeout"

    exit_code = conventional_commit_grep._main(
        ["conventional-commit-grep", str(tmp_path)]
    )
    payload = _printed_payload(capsys)
    assert exit_code == conventional_commit_grep.EXIT_FAIL
    _assert_check_error(payload, "git log")
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
    """The advisory companion check fails, not degrades, when git stalls."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "README.md").write_text("# pkg\n", encoding="utf-8")
    monkeypatch.setattr(_bounded_run, "run_bounded", _timing_out_run)

    result = agents_md_coverage_grep.check(tmp_path)
    assert result.passed is False
    assert result.freshness_checked is False

    exit_code = agents_md_coverage_grep._main(
        ["agents-md-coverage-grep", str(tmp_path)]
    )
    payload = _printed_payload(capsys)
    # Advisory findings exit 0; a check that could not finish does not.
    assert exit_code == gate.EXIT_FAIL
    _assert_check_error(payload, "git rev-parse")


def test_companion_check_without_history_still_passes(tmp_path: Path) -> None:
    """Outside a repository the companion check still degrades to presence-only."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "README.md").write_text("# pkg\n", encoding="utf-8")

    result = agents_md_coverage_grep.check(tmp_path)
    assert result.passed is True
    assert result.freshness_checked is False


def test_companion_history_read_gets_the_long_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The read of the whole history gets the long limit, not the short one.

    Its cost grows with the history, so a large repository is slow there, and
    the short limit covers only the quick ``rev-parse`` that comes first.
    """
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "README.md").write_text("# pkg\n", encoding="utf-8")
    limits: dict[str, float | None] = {}

    def run(
        argv: list[str], *, timeout: float | None, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        limits[_subcommand(argv)] = timeout
        output = (
            "0" * 40 + "\n"
            if _subcommand(argv) == "rev-parse"
            else "\x1e100\npkg/README.md\n"
        )
        return subprocess.CompletedProcess(argv, 0, output, "")

    monkeypatch.setattr(_bounded_run, "run_bounded", run)

    result = agents_md_coverage_grep.check(tmp_path)
    assert result.passed is True
    assert result.freshness_checked is True
    assert limits == {
        "rev-parse": agents_md_coverage_grep.GIT_TIMEOUT_SECONDS,
        "log": agents_md_coverage_grep.GIT_HISTORY_TIMEOUT_SECONDS,
    }
    assert agents_md_coverage_grep.GIT_HISTORY_TIMEOUT_SECONDS >= 120


def test_companion_history_read_past_its_limit_does_not_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A history read that never ends still stops at its own limit and fails."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "README.md").write_text("# pkg\n", encoding="utf-8")

    def run(
        argv: list[str], *, timeout: float | None, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if _subcommand(argv) == "rev-parse":
            return subprocess.CompletedProcess(argv, 0, "0" * 40 + "\n", "")
        return _timing_out_run(argv, timeout=timeout, **kwargs)

    monkeypatch.setattr(_bounded_run, "run_bounded", run)

    result = agents_md_coverage_grep.check(tmp_path)
    assert result.passed is False
    assert result.check_error == (
        "git log did not finish within "
        f"{agents_md_coverage_grep.GIT_HISTORY_TIMEOUT_SECONDS} seconds"
    )


def _history_read_failing(
    config: subprocess.CompletedProcess[str] | None,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Stand in for ``run_bounded``: a history exists, but its read fails.

    ``git rev-parse`` finds a commit and ``git log`` exits 128. ``git config``
    answers with *config*, or runs past its limit when *config* is None.
    """

    def run(
        argv: list[str], *, timeout: float | None, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        command = _subcommand(argv)
        if command == "rev-parse":
            return subprocess.CompletedProcess(argv, 0, "0" * 40 + "\n", "")
        if command == "log":
            return subprocess.CompletedProcess(argv, 128, "", "fatal: unreadable")
        if config is None:
            return _timing_out_run(argv, timeout=timeout, **kwargs)
        return config

    return run


def test_companion_history_read_that_fails_does_not_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After ``git rev-parse`` found a history, a failed read of it is no pass.

    The repository is no partial clone, so nothing it left out explains the
    failure: the history is there but was not read.
    """
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "README.md").write_text("# pkg\n", encoding="utf-8")
    no_promisor = subprocess.CompletedProcess(["git", "config"], 1, "", "")
    monkeypatch.setattr(_bounded_run, "run_bounded", _history_read_failing(no_promisor))

    result = agents_md_coverage_grep.check(tmp_path)
    assert result.passed is False
    assert result.freshness_checked is False
    assert result.check_error == "git log failed with exit code 128"


def test_companion_history_read_in_a_partial_clone_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partial clone's failed history read is missing history, not a failure.

    git may not fetch the trees the clone left out, so the check falls back to
    presence only, as it does where there is no history.
    """
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "README.md").write_text("# pkg\n", encoding="utf-8")
    promisor = subprocess.CompletedProcess(
        ["git", "config"], 0, "remote.origin.promisor true\n", ""
    )
    monkeypatch.setattr(_bounded_run, "run_bounded", _history_read_failing(promisor))

    result = agents_md_coverage_grep.check(tmp_path)
    assert result.passed is True
    assert result.freshness_checked is False
    assert result.check_error is None


def test_companion_partial_clone_question_past_its_limit_does_not_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``git config`` that asks about a partial clone has a limit too."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "README.md").write_text("# pkg\n", encoding="utf-8")
    monkeypatch.setattr(_bounded_run, "run_bounded", _history_read_failing(None))

    result = agents_md_coverage_grep.check(tmp_path)
    assert result.passed is False
    assert result.check_error == (
        "git config did not finish within "
        f"{agents_md_coverage_grep.GIT_TIMEOUT_SECONDS} seconds"
    )


def test_companion_check_falls_back_in_a_treeless_clone(tmp_path: Path) -> None:
    """A real ``--filter=tree:0`` clone passes, as it did before the limits.

    The clone has the trees of its newest commit only. Reading the history
    needs the older ones, and git may not fetch them in the checked project,
    so the read fails; the clone's promisor remote marks that history as left
    out rather than unreadable.
    """
    source = _project(tmp_path)
    (source / "pkg" / "notes.md").write_text("later\n", encoding="utf-8")
    _git(source, "add", "-A")
    _git(source, "commit", "-qm", "docs(pkg): add notes")
    _git(source, "config", "uploadpack.allowFilter", "true")
    clone = tmp_path / "clone"
    _git(
        tmp_path,
        "clone",
        "-q",
        "--no-local",
        "--filter=tree:0",
        source.as_uri(),
        str(clone),
    )

    result = agents_md_coverage_grep.check(clone)
    assert result.check_error is None
    assert result.passed is True
    assert result.freshness_checked is False


def test_plans_listing_timeout_does_not_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``no-global-plans-grep``'s ``git ls-files`` has a limit, and it fails there."""
    monkeypatch.setattr(_bounded_run, "run_bounded", _timing_out_run)

    exit_code = no_global_plans_grep._main(["no-global-plans-grep", str(tmp_path)])
    payload = _printed_payload(capsys)
    assert exit_code == no_global_plans_grep.EXIT_FAIL
    assert payload[CHECK_ERROR_KEY] == (
        "git ls-files did not finish within "
        f"{_grep_base.GIT_LS_FILES_TIMEOUT_SECONDS} seconds"
    )
    assert payload["passed"] is False
    assert payload["inspected"] == 0
    assert payload["empty_scope_expected"] is False


def test_staged_change_set_timeout_does_not_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``production-ready-pr-grep --staged`` fails when ``git diff`` stalls."""
    monkeypatch.setattr(_bounded_run, "run_bounded", _timing_out_run)

    exit_code = production_ready_pr_grep._main(["production-ready-pr-grep", "--staged"])
    payload = _printed_payload(capsys)
    assert exit_code == production_ready_pr_grep.EXIT_FAIL
    _assert_check_error(payload, "git diff --cached")
    assert payload["findings"] == []


def test_semver_staged_list_timeout_does_not_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``semver-stability-grep --staged`` fails when the staged list stalls."""
    monkeypatch.setattr(semver_stability_grep, "current_version", lambda: "1.2.3")
    monkeypatch.setattr(_bounded_run, "run_bounded", _timing_out_run)

    exit_code = semver_stability_grep._main(["semver-stability-grep", "--staged"])
    payload = _printed_payload(capsys)
    assert exit_code == semver_stability_grep.EXIT_FAIL
    _assert_check_error(payload, "git diff --cached")


def test_semver_staged_file_read_timeout_does_not_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A staged file whose ``git cat-file`` stalls is not skipped as if unchanged."""
    monkeypatch.setattr(semver_stability_grep, "current_version", lambda: "1.2.3")

    def run(
        argv: list[str], *, timeout: float | None, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if "diff" in argv:
            # ``-z`` ends each staged name with NUL.
            return subprocess.CompletedProcess(argv, 0, "src/apothem/api.py\0", "")
        return _timing_out_run(argv, timeout=timeout, **kwargs)

    monkeypatch.setattr(_bounded_run, "run_bounded", run)

    exit_code = semver_stability_grep._main(["semver-stability-grep", "--staged"])
    payload = _printed_payload(capsys)
    assert exit_code == semver_stability_grep.EXIT_FAIL
    _assert_check_error(payload, "git cat-file")


# --- A git that refuses the checkout does not pass ---------------------------


def test_commit_subject_check_fails_when_git_refuses_the_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bad configuration line is a git failure, not the no-commit exemption."""
    repo = _project(tmp_path)
    _break_config(repo)

    result = conventional_commit_grep.check_repo(repo)
    assert result.passed is False
    assert result.status == "git-failed"
    assert result.check_error == "git log failed with exit code 128"

    exit_code = conventional_commit_grep._main(["conventional-commit-grep", str(repo)])
    assert exit_code == conventional_commit_grep.EXIT_FAIL
    _assert_check_error(_printed_payload(capsys), "git log", "failed with exit code")


def test_commit_subject_check_still_exempts_a_branch_with_no_commit(
    tmp_path: Path,
) -> None:
    """A repository with no commit yet is still the documented exemption."""
    repo = tmp_path / "fresh"
    repo.mkdir()
    _git(repo, "init", "-q")

    result = conventional_commit_grep.check_repo(repo)
    assert result.passed is True
    assert result.status == "no-commits-yet"
    assert result.check_error is None


def test_companion_check_fails_when_git_refuses_the_checkout(tmp_path: Path) -> None:
    """In a checkout git cannot read, the companion check does not degrade."""
    repo = _project(tmp_path)
    _break_config(repo)

    result = agents_md_coverage_grep.check(repo)
    assert result.passed is False
    assert result.check_error == "git rev-parse failed with exit code 128"


def _dangling_git_file(folder: Path) -> None:
    """Leave a ``.git`` file that names a repository folder that is gone."""
    (folder / ".git").write_text("gitdir: ../gone/.git/worktrees/x\n", encoding="utf-8")


def _empty_git_folder(folder: Path) -> None:
    """Leave an empty ``.git`` folder, which holds no repository."""
    (folder / ".git").mkdir()


@pytest.mark.parametrize("leave", [_dangling_git_file, _empty_git_folder])
def test_checks_fail_on_a_git_entry_git_cannot_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, leave: Callable[[Path], None]
) -> None:
    """A ``.git`` entry git cannot open is a checkout that was not read.

    git calls such a folder "not a git repository", but the folder claims to be
    a checkout: the history the checks need may be there, unread, so they do
    not pass as if it had none. A folder with no ``.git`` entry still passes.
    """
    folder = tmp_path / "unpacked"
    (folder / "pkg").mkdir(parents=True)
    (folder / "pkg" / "README.md").write_text("# pkg\n", encoding="utf-8")
    leave(folder)
    # Keep git from finding a repository above the test's own folder.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    subject = conventional_commit_grep.check_repo(folder)
    assert subject.passed is False
    assert subject.status == "git-failed"
    assert subject.check_error == "git log failed with exit code 128"

    companions = agents_md_coverage_grep.check(folder)
    assert companions.passed is False
    assert companions.check_error == "git rev-parse failed with exit code 128"


def test_staged_checks_fail_when_git_refuses_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both ``--staged`` checks report a git failure in a checkout as unread."""
    repo = _project(tmp_path)
    _break_config(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(semver_stability_grep, "current_version", lambda: "1.2.3")

    assert (
        production_ready_pr_grep._main(["production-ready-pr-grep", "--staged"])
        == production_ready_pr_grep.EXIT_FAIL
    )
    _assert_check_error(
        _printed_payload(capsys), "git diff --cached", "failed with exit code"
    )
    assert (
        semver_stability_grep._main(["semver-stability-grep", "--staged"])
        == semver_stability_grep.EXIT_FAIL
    )
    _assert_check_error(
        _printed_payload(capsys), "git diff --cached", "failed with exit code"
    )


def test_staged_checks_still_pass_outside_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Outside a checkout there is no change set, as before."""
    folder = tmp_path / "plain"
    folder.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.chdir(folder)
    monkeypatch.setattr(semver_stability_grep, "current_version", lambda: "1.2.3")

    assert (
        production_ready_pr_grep._main(["production-ready-pr-grep", "--staged"])
        == production_ready_pr_grep.EXIT_PASS
    )
    assert CHECK_ERROR_KEY not in _printed_payload(capsys)
    assert (
        semver_stability_grep._main(["semver-stability-grep", "--staged"])
        == semver_stability_grep.EXIT_PASS
    )
    assert CHECK_ERROR_KEY not in _printed_payload(capsys)


# --- The gate's own limit on each standalone validator -----------------------


_SLEEPING_LAUNCHER = f"import time\ntime.sleep({_SLEEP_SECONDS})\n"


def _short_validator_limit(
    monkeypatch: pytest.MonkeyPatch, seconds: int = _SHORT_VALIDATOR_TIMEOUT_SECONDS
) -> None:
    """Give each standalone validator a short time limit in the gate."""
    monkeypatch.setattr(gate, "STANDALONE_TIMEOUT_SECONDS", seconds)


def _stopped_report(
    output: str, seconds: int = _SHORT_VALIDATOR_TIMEOUT_SECONDS
) -> dict[str, object]:
    """Return the report the gate wrote for a validator it stopped."""
    payload: dict[str, object] = json.loads(output)
    assert payload["passed"] is False
    check_error = str(payload.get(CHECK_ERROR_KEY))
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
# wait for that process to close the output it shares, and must end it.
_FORKING_LAUNCHER = (
    "import subprocess, sys, time\n"
    "from pathlib import Path\n"
    "child = subprocess.Popen("
    f"[sys.executable, '-c', 'import time; time.sleep({_SLEEP_SECONDS})'])\n"
    "Path(sys.argv[3]).joinpath('helper.pid').write_text(str(child.pid))\n"
    f"time.sleep({_SLEEP_SECONDS})\n"
)


def _process_gone(pid: int) -> bool:
    """Return True once no running process has *pid*."""
    if os.name == "nt":
        import _winapi

        try:
            # PROCESS_QUERY_LIMITED_INFORMATION; an ended process gives
            # another exit code than STILL_ACTIVE (259).
            handle = _winapi.OpenProcess(0x1000, False, pid)
        except OSError:
            return True
        try:
            return bool(_winapi.GetExitCodeProcess(handle) != 259)
        finally:
            _winapi.CloseHandle(handle)
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


def test_stopped_validator_ends_the_process_it_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A process the validator started cannot hold the stopped run open.

    On POSIX the gate stops the validator's whole process group, and on
    Windows the job object the validator runs in, so the helper process ends
    too and the run returns at the limit.
    """
    _short_validator_limit(monkeypatch)
    monkeypatch.setattr(_bounded_run, "STOP_GRACE_SECONDS", 1)
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
        helper = int(pid_file.read_text(encoding="utf-8"))
        give_up = time.monotonic() + _EXIT_WAIT_SECONDS
        while not _process_gone(helper) and time.monotonic() < give_up:
            time.sleep(0.1)
        helper_gone = _process_gone(helper)
        assert helper_gone, "the validator's helper process still runs"
    finally:
        # Stop a helper still running, but never signal an ID already seen
        # gone: the system may reuse it.
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
    assert "did not finish" in str(entry.get(CHECK_ERROR_KEY))

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


def test_interrupt_ends_the_gate_with_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ctrl+C prints one line and exits 130, not a traceback."""

    def interrupted(root: Path) -> tuple[bool, str]:
        raise KeyboardInterrupt

    monkeypatch.setattr(gate, "_run_all", interrupted)

    try:
        exit_code = gate.main(["gate", "--all", str(tmp_path)])
    except KeyboardInterrupt:
        # Escaping, the interrupt would end the whole test session, workers and
        # all, and hide every result after this one: fail this test alone.
        pytest.fail("the gate let the interrupt escape")
    assert exit_code == gate.EXIT_INTERRUPTED == 130
    assert capsys.readouterr().err.strip() == "conformity-gate: interrupted"


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
    """The companion check's git ends at its limit and does not pass."""
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
    _assert_check_error(_printed_payload(capsys), "git diff --cached")


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
    _assert_check_error(_printed_payload(capsys), "git diff --cached")


@_POSIX_ONLY
def test_plans_listing_that_waits_on_its_configuration_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``no-global-plans-grep``'s ``git ls-files`` ends at its limit and fails."""
    repo = _project(tmp_path)
    fifo = tmp_path / "config-fifo"
    _include_fifo(repo, fifo)
    monkeypatch.setattr(
        no_global_plans_grep, "GIT_LS_FILES_TIMEOUT_SECONDS", _SHORT_GIT_TIMEOUT_SECONDS
    )

    exit_code = _run_guarded(
        lambda: no_global_plans_grep._main(["no-global-plans-grep", str(repo)]),
        release=lambda: _release_fifo(fifo),
    )
    assert exit_code == no_global_plans_grep.EXIT_FAIL
    _assert_check_error(_printed_payload(capsys), "git ls-files")


@_POSIX_ONLY
def test_gate_stops_a_validator_whose_git_waits_and_ends_that_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate's limit ends the validator and the waiting git it started.

    The commit-subject validator's own git limit is longer than the gate's
    limit here, so the gate stops the run. Afterwards no process may be left in
    the validator's process group, where its git runs: the gate stopped the
    group. The check asks the group itself, because probing the FIFO for a
    reader would let a git that is still waiting go on.
    """
    repo = _project(tmp_path)
    fifo = tmp_path / "config-fifo"
    _include_fifo(repo, fifo)
    _short_validator_limit(monkeypatch, _STALL_VALIDATOR_TIMEOUT_SECONDS)
    started: list[int] = []
    real_popen = subprocess.Popen

    class RecordingPopen(real_popen):  # type: ignore[misc,valid-type]
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)
            started.append(self.pid)

    monkeypatch.setattr(subprocess, "Popen", RecordingPopen)

    try:
        # _run_guarded releases the FIFO only after its deadline, to end a run
        # that stalled; a run that ends in time is never released.
        passed, output = _run_guarded(
            lambda: gate._run_standalone("conventional-commit-grep", repo),
            release=lambda: _release_fifo(fifo),
        )
        assert passed is False
        _stopped_report(output, _STALL_VALIDATOR_TIMEOUT_SECONDS)
        # The validator leads a session, and so a process group, of its own.
        (group,) = started
        give_up = time.monotonic() + _EXIT_WAIT_SECONDS
        while time.monotonic() < give_up:
            try:
                os.killpg(group, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            pytest.fail("a process the stopped validator started is still running")
    finally:
        # Only now let any reader left waiting go on; git opens an included
        # file more than once.
        for _ in range(4):
            _release_fifo(fifo)
            time.sleep(0.05)


def _processes_naming(text: str, *words: str) -> list[int]:
    """Return the IDs of running processes whose arguments hold *text* and *words*."""
    found: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        args = [arg.decode("utf-8", "replace") for arg in raw.split(b"\0") if arg]
        if any(text in arg for arg in args) and all(word in args for word in words):
            found.append(int(entry.name))
    return found


@_POSIX_ONLY
@_NEEDS_PROC
@pytest.mark.parametrize("signal_name", ["SIGTERM", "SIGHUP"])
def test_signal_to_the_gate_ends_the_validator_and_its_git(
    tmp_path: Path, signal_name: str
) -> None:
    """A signal to the gate's own process group ends the validator's session too.

    The gate starts each validator in a session of its own, so a ``SIGTERM``
    from coreutils ``timeout`` or a CI job cancel, or the ``SIGHUP`` of a
    closed terminal, reaches only the gate's group. While a validator runs,
    the gate stops that validator's group, then exits with 128 plus the
    signal's number, so no validator or git is left waiting on the FIFO.
    """
    # Looked up here: Windows, where the test is skipped, has no SIGHUP.
    signum = int(getattr(signal, signal_name))
    repo = _project(tmp_path).resolve()
    fifo = tmp_path / "config-fifo"
    _include_fifo(repo, fifo)
    marker = str(repo)
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}
    command = [sys.executable, "-m", "apothem.conformity.gate"]
    gate_run = subprocess.Popen(
        [*command, "--check", "no-global-plans-grep", marker],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        give_up = time.monotonic() + _DEADLINE_SECONDS
        while not _processes_naming(marker, "ls-files"):
            assert gate_run.poll() is None, "the gate ended before git started"
            assert time.monotonic() < give_up, "git never started"
            time.sleep(0.1)
        os.killpg(gate_run.pid, signum)
        assert gate_run.wait(timeout=_DEADLINE_SECONDS) == 128 + signum
        give_up = time.monotonic() + _EXIT_WAIT_SECONDS
        while _processes_naming(marker) and time.monotonic() < give_up:
            time.sleep(0.1)
        assert not _processes_naming(marker), "a program the gate started still runs"
    finally:
        if gate_run.poll() is None:
            gate_run.kill()
            gate_run.wait()
        for pid in _processes_naming(marker):
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)
        # git opens an included file more than once; let every waiting
        # reader go.
        for _ in range(4):
            _release_fifo(fifo)


# --- A real repository whose configuration makes git wait (Windows) ----------


@_WINDOWS_ONLY
def test_validator_git_behind_the_git_launcher_ends_at_its_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The validator's own limit holds when ``git`` is Git's ``cmd`` launcher.

    The launcher starts the real git, which holds the output after the
    launcher is stopped; the job object the git call runs in ends both. The
    named pipe the configuration includes never answers, so git waits.
    """
    launcher = _git_launcher_folder()
    if launcher is None:
        pytest.skip("Git for Windows' cmd launcher is not installed")
    monkeypatch.setenv("PATH", f"{launcher}{os.pathsep}{os.environ['PATH']}")
    repo = _project(tmp_path)
    pipe = _StalledPipe()
    try:
        _include(repo, pipe.include_path)
        monkeypatch.setattr(
            conventional_commit_grep, "GIT_TIMEOUT_SECONDS", _SHORT_GIT_TIMEOUT_SECONDS
        )

        started = time.monotonic()
        result = _run_guarded(
            lambda: conventional_commit_grep.check_repo(repo), release=pipe.close
        )
        took = time.monotonic() - started

        assert result.status == "git-timeout", result
        bound = _SHORT_GIT_TIMEOUT_SECONDS + _bounded_run.STOP_GRACE_SECONDS
        assert took < bound, f"the 2-second limit took {took:.1f}s"
        came, _ = pipe.readers()
        assert came, "git never opened the named pipe"
        give_up = time.monotonic() + _EXIT_WAIT_SECONDS
        while pipe.readers()[1] and time.monotonic() < give_up:
            time.sleep(0.1)
        assert pipe.readers()[1] == 0, "the real git still waits on the pipe"
    finally:
        pipe.close()


@_WINDOWS_ONLY
def test_gate_stop_ends_the_git_a_validator_started_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stopping a validator ends every program in its job object, git included."""
    repo = _project(tmp_path)
    pipe = _StalledPipe()
    try:
        _include(repo, pipe.include_path)
        _short_validator_limit(monkeypatch, _STALL_VALIDATOR_TIMEOUT_SECONDS)

        passed, output = _run_guarded(
            lambda: gate._run_standalone("no-global-plans-grep", repo),
            release=pipe.close,
        )
        assert passed is False
        _stopped_report(output, _STALL_VALIDATOR_TIMEOUT_SECONDS)
        came, _ = pipe.readers()
        assert came, "git never opened the named pipe"
        give_up = time.monotonic() + _EXIT_WAIT_SECONDS
        while pipe.readers()[1] and time.monotonic() < give_up:
            time.sleep(0.1)
        assert pipe.readers()[1] == 0, "a git the validator started still waits"
    finally:
        pipe.close()
