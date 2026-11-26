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
- on Windows a program runs only once it is in its job object, so a child it
  starts at once is stopped with it, and a program that cannot be let run
  fails at once and is not left behind;
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
import gc
import json
import os
import signal
import subprocess
import sys
import threading
import time
import tracemalloc
import uuid
import weakref
from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path
from types import FrameType
from typing import Any, TypeVar

import pytest

from apothem.conformity import (
    _bounded_run,
    agents_md_coverage_grep,
    conventional_commit_grep,
    gate,
    no_global_plans_grep,
    production_ready_pr_grep,
    semver_stability_grep,
)
from apothem.conformity._git import NOT_RESUMED_EXIT_CODE, run_git
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


def test_commit_subject_without_history_still_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ``.git`` is still the documented exemption, not a check error.

    The search does not go above ``tmp_path``, so a repository above the
    temp folder cannot count.
    """
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
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
        # rev-parse prints the root's path below the top of the work tree
        # (empty at the top), then the commit; log prints "<status>\t<name>".
        output = (
            "\n" + "0" * 40 + "\n"
            if _subcommand(argv) == "rev-parse"
            else "\x1e100\nA\tpkg/README.md\n"
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
            return subprocess.CompletedProcess(argv, 0, "\n" + "0" * 40 + "\n", "")
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
            # --show-prefix prints an empty line at the top, then the commit.
            return subprocess.CompletedProcess(argv, 0, "\n" + "0" * 40 + "\n", "")
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


def test_companion_promisor_turned_off_is_no_partial_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``promisor = false`` names no promisor, so a failed read still fails."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "README.md").write_text("# pkg\n", encoding="utf-8")
    turned_off = subprocess.CompletedProcess(
        ["git", "config"], 0, "remote.origin.promisor false\n", ""
    )
    monkeypatch.setattr(_bounded_run, "run_bounded", _history_read_failing(turned_off))

    result = agents_md_coverage_grep.check(tmp_path)
    assert result.passed is False
    assert result.check_error == "git log failed with exit code 128"


@pytest.mark.parametrize(
    ("advisory_report", "expected"),
    [
        (
            {
                "advisory": True,
                "passed": False,
                "findings": [],
                CHECK_ERROR_KEY: "git log did not finish within 300 seconds",
            },
            False,
        ),
        (
            {
                "advisory": True,
                "passed": False,
                "findings": [{"surface": "pkg/AGENTS.md", "kind": "stale-companion"}],
            },
            True,
        ),
    ],
)
def test_all_counts_advisory_findings_not_unfinished_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    advisory_report: dict[str, object],
    expected: bool,
) -> None:
    """An advisory validator that could not finish reports no advisory findings."""

    def run(name: str, root: Path) -> tuple[bool, str]:
        if name == "agents-md-coverage-grep":
            report = advisory_report
            return CHECK_ERROR_KEY not in report, json.dumps(report)
        return True, json.dumps({"passed": True})

    monkeypatch.setattr(gate, "_run_standalone", run)

    _passed, output = gate._run_all(tmp_path)
    payload = json.loads(output)
    assert payload["advisory_findings_present"] is expected
    (entry,) = [
        entry
        for entry in payload["results"]
        if entry["validator"] == "agents-md-coverage-grep"
    ]
    assert (CHECK_ERROR_KEY in entry) is not expected


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


def _history_with_a_lost_tree(tmp_path: Path) -> Path:
    """Return a full repository whose older commit's tree object is deleted.

    Fresh commits are loose objects, so deleting the file loses the tree, and
    reading the history then fails with exit code 128.
    """
    repo = _project(tmp_path)
    (repo / "pkg" / "notes.md").write_text("later\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "docs(pkg): add notes")
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD~1^{tree}"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()
    lost = repo / ".git" / "objects" / tree[:2] / tree[2:]
    # git writes objects read-only, and Windows deletes no read-only file.
    lost.chmod(0o644)
    lost.unlink()
    return repo


@pytest.mark.parametrize(
    "setting",
    [("remote.origin.promisor", "true"), ("extensions.partialClone", "origin")],
)
def test_any_failed_history_read_in_a_partial_clone_is_unavailable_history(
    tmp_path: Path, setting: tuple[str, str]
) -> None:
    """In a partial clone, a failed history read passes, whatever the cause.

    git gives no answer that tells a tree the clone left out from one that was
    lost (``rev-list --missing=allow-promisor`` fails on both), so the check
    treats every failed read there as history that is not available, as it
    did before it had limits. A repository's own settings make it a partial
    clone, recent git writing the promisor setting and older git the
    extension.
    """
    repo = _history_with_a_lost_tree(tmp_path)
    assert agents_md_coverage_grep.check(repo).check_error == (
        "git log failed with exit code 128"
    )
    _git(repo, "config", *setting)

    result = agents_md_coverage_grep.check(repo)
    assert result.check_error is None
    assert result.passed is True
    assert result.freshness_checked is False


def test_a_promisor_outside_the_repository_does_not_make_a_partial_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the repository's own settings count, not the user's global ones."""
    repo = _history_with_a_lost_tree(tmp_path)
    global_config = tmp_path / "global.gitconfig"
    global_config.write_text('[remote "origin"]\n\tpromisor = true\n', encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))

    result = agents_md_coverage_grep.check(repo)
    assert result.passed is False
    assert result.check_error == "git log failed with exit code 128"


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
        while _group_has_live_member(group):
            if time.monotonic() > give_up:
                pytest.fail("a process the stopped validator started is still running")
            time.sleep(0.1)
    finally:
        # Only now let any reader left waiting go on; git opens an included
        # file more than once.
        for _ in range(4):
            _release_fifo(fifo)
            time.sleep(0.05)


def _group_has_live_member(group: int) -> bool:
    """Return True while process group *group* holds a process that is not a zombie.

    A killed process stays a zombie until its parent waits for it, and a
    killed git's parent, process 1 once the validator is gone, may wait late or
    never (pytest as process 1 of a container). On Linux the zombies are told
    apart through /proc; macOS answers ``EPERM`` for a group that holds only
    zombies, and ``ESRCH`` for one that is gone.
    """
    proc = Path("/proc")
    if (proc / "self" / "stat").is_file():
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                stat = (entry / "stat").read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Fields after the command name, which ends at the last ")":
            # state, parent id, process group.
            fields = stat.rpartition(")")[2].split()
            if len(fields) > 2 and fields[2] == str(group) and fields[0] != "Z":
                return True
        return False
    try:
        os.killpg(group, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


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


# How long the slowed job add waits before it puts the program in the job: long
# enough for a program that runs at once to start its own child first.
_SLOW_ADD_SECONDS = 2.0
# The time limit of the early-child test below: longer than the slowed add, and
# long enough for the program to start its child on a busy machine.
_RUN_TIMEOUT_SECONDS = 10

# A program that at once starts a child with no pipe of the parent's, writes
# that child's process ID to the file named by its first argument, and sleeps.
# It writes a side file and renames it, so the file is never seen half written.
_EARLY_CHILD_PROGRAM = (
    "import subprocess, sys, time\n"
    "from pathlib import Path\n"
    "child = subprocess.Popen(\n"
    f"    [sys.executable, '-c', 'import time; time.sleep({_SLEEP_SECONDS})'],\n"
    "    stdin=subprocess.DEVNULL,\n"
    "    stdout=subprocess.DEVNULL,\n"
    "    stderr=subprocess.DEVNULL,\n"
    ")\n"
    "side = Path(sys.argv[1] + '.tmp')\n"
    "side.write_text(str(child.pid), encoding='utf-8')\n"
    "side.replace(sys.argv[1])\n"
    f"time.sleep({_SLEEP_SECONDS})\n"
)


def _read_pid(pid_file: Path) -> int | None:
    """Return the process ID in *pid_file*, or None when it holds none."""
    try:
        text = pid_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return int(text) if text.isdigit() else None


def _skip_without_a_job() -> None:
    """Skip the test when Windows refuses this process a job object."""
    job = _bounded_run._Job()
    try:
        if not job.suspends:
            pytest.skip("Windows refuses a job object here")
    finally:
        job.close()


def _wait_gone(pid: int) -> bool:
    """Return True once *pid* has ended, waiting at most the exit wait."""
    give_up = time.monotonic() + _EXIT_WAIT_SECONDS
    while not _process_gone(pid) and time.monotonic() < give_up:
        time.sleep(0.1)
    return _process_gone(pid)


@_WINDOWS_ONLY
def test_child_started_before_the_job_add_is_stopped_with_the_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A child the program starts at once is in the job, so a stop ends it.

    The job add is slowed down here. A program that ran before the add would
    start its child outside the job, and that child would outlive the stop.
    The program starts suspended and runs only once it is in the job.
    """
    _skip_without_a_job()
    real_add = _bounded_run._Job.add

    def slow_add(job: _bounded_run._Job, pid: int) -> None:
        time.sleep(_SLOW_ADD_SECONDS)
        real_add(job, pid)

    monkeypatch.setattr(_bounded_run._Job, "add", slow_add)
    pid_file = tmp_path / "child.pid"
    child_gone = False
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            _bounded_run.run_bounded(
                [sys.executable, "-c", _EARLY_CHILD_PROGRAM, str(pid_file)],
                timeout=_RUN_TIMEOUT_SECONDS,
            )
        child = _read_pid(pid_file)
        assert child is not None, (
            f"the program never wrote its child's process ID within "
            f"{_RUN_TIMEOUT_SECONDS}s (the file exists: {pid_file.is_file()})"
        )
        child_gone = _wait_gone(child)
        assert child_gone, "the program's child still runs after the stop"
    finally:
        # Stop a child still running, but never signal an ID already seen
        # gone: the system may reuse it.
        leftover = _read_pid(pid_file)
        if leftover is not None and not child_gone:
            _end_process(leftover)


@_WINDOWS_ONLY
def test_program_that_cannot_be_resumed_is_stopped_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A suspended program that cannot run raises and is not left behind.

    The error is a ProgramResumeError, which a caller can tell from a
    program that is missing, and its message says the program is in the job.
    """
    _skip_without_a_job()
    started: list[int] = []
    real_add = _bounded_run._Job.add

    def recording_add(job: _bounded_run._Job, pid: int) -> None:
        started.append(pid)
        real_add(job, pid)

    monkeypatch.setattr(_bounded_run._Job, "add", recording_add)
    monkeypatch.setattr(_bounded_run._Job, "resume", lambda _job, _process: False)
    program_gone = False
    begun = time.monotonic()
    try:
        with pytest.raises(
            _bounded_run.ProgramResumeError,
            match=r"could not resume .* \(it is in the job object\)",
        ):
            _bounded_run.run_bounded(
                [sys.executable, "-c", f"import time; time.sleep({_SLEEP_SECONDS})"],
                timeout=_SLEEP_SECONDS,
            )
        took = time.monotonic() - begun
        assert took < _bounded_run.STOP_GRACE_SECONDS, f"the failure took {took:.1f}s"
        assert len(started) == 1, started
        program_gone = _wait_gone(started[0])
        assert program_gone, "the program that could not run still exists"
    finally:
        if started and not program_gone:
            _end_process(started[0])


@_WINDOWS_ONLY
def test_resume_failure_says_when_the_program_is_not_in_the_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the job add failed, the message does not claim the program joined."""
    _skip_without_a_job()
    started: list[int] = []

    def refused_add(_job: _bounded_run._Job, pid: int) -> None:
        started.append(pid)

    monkeypatch.setattr(_bounded_run._Job, "add", refused_add)
    monkeypatch.setattr(_bounded_run._Job, "resume", lambda _job, _process: False)
    program_gone = False
    try:
        with pytest.raises(
            _bounded_run.ProgramResumeError, match="it is not in the job object"
        ):
            _bounded_run.run_bounded(
                [sys.executable, "-c", f"import time; time.sleep({_SLEEP_SECONDS})"],
                timeout=_SLEEP_SECONDS,
            )
        assert len(started) == 1, started
        program_gone = _wait_gone(started[0])
        assert program_gone, "the program that could not run still exists"
    finally:
        if started and not program_gone:
            _end_process(started[0])


# The access rights the test below opens a program with: PROCESS_TERMINATE
# and SYNCHRONIZE.
_END_AND_WAIT_ACCESS = 0x0001 | 0x00100000


def _winapi_pid(handle: int) -> int:
    """Return the process ID of the process *handle* names (Windows only)."""
    import ctypes

    get_process_id = ctypes.WinDLL("kernel32").GetProcessId
    get_process_id.argtypes = (ctypes.c_void_p,)
    get_process_id.restype = ctypes.c_ulong
    return int(get_process_id(handle))


@_WINDOWS_ONLY
@pytest.mark.parametrize("exit_code", [0, 1, 7])
@pytest.mark.parametrize("when", ["ending", "ended", "ended-unread", "between"])
def test_program_ended_before_the_resume_is_no_result(
    monkeypatch: pytest.MonkeyPatch, exit_code: int, when: str
) -> None:
    """A program ended before the resume never ran: its exit code is no answer.

    Whatever ended it chose that code (``taskkill /F`` gives 1), and a 0 or a
    1 would read as git's own answer, which some checks exempt. So it raises
    :class:`ProgramResumeError`, which ``run_git`` turns into a failed git.
    No thread snapshot is taken for such a program either.

    The program is really ended, inside the job add, before the real resume.
    While it still winds down ("ending"), NtResumeProcess reports success, so
    before the exit code was read first such a program passed. Once it is
    gone ("ended"), NtResumeProcess reports it as ending. "ended-unread"
    hides the exit code, as a kill between that read and the resume would,
    so NtResumeProcess's answer is the one that counts. "between" ends the
    program right after the first read, still running, so NtResumeProcess
    reports success and only the read after the resume catches it.
    """
    import _winapi

    _skip_without_a_job()
    real_add = _bounded_run._Job.add
    real_told = _bounded_run._told_to_end

    def end(pid: int, *, wait: bool) -> None:
        handle = _winapi.OpenProcess(_END_AND_WAIT_ACCESS, False, pid)
        try:
            _winapi.TerminateProcess(handle, exit_code)
            if wait:
                _winapi.WaitForSingleObject(handle, int(_EXIT_WAIT_SECONDS * 1000))
        finally:
            _winapi.CloseHandle(handle)

    def add_then_end(job: _bounded_run._Job, pid: int) -> None:
        real_add(job, pid)
        if when != "between":
            end(pid, wait=when != "ending")

    reads: list[int] = []

    def told_then_end(handle: int) -> bool:
        reads.append(handle)
        answer = real_told(handle)
        if len(reads) == 1:
            end(_winapi_pid(handle), wait=False)
        return answer

    monkeypatch.setattr(_bounded_run._Job, "add", add_then_end)
    if when == "ended-unread":
        monkeypatch.setattr(_bounded_run, "_told_to_end", lambda _handle: False)
    if when == "between":
        monkeypatch.setattr(_bounded_run, "_told_to_end", told_then_end)
    taken = _record_snapshots(monkeypatch)
    with pytest.raises(
        _bounded_run.ProgramResumeError,
        match=rf"ended before it could run \(exit code {exit_code}\)",
    ):
        _bounded_run.run_bounded(
            [sys.executable, "-c", _PRINT_PROGRAM], timeout=_DEADLINE_SECONDS
        )
    assert taken == [], "a thread snapshot was taken for an ending program"


@_WINDOWS_ONLY
@pytest.mark.parametrize("exit_code", [0, 3])
def test_program_read_late_after_the_resume_still_gives_its_result(
    monkeypatch: pytest.MonkeyPatch, exit_code: int
) -> None:
    """A program that ran and ended before the read after the resume counts.

    The calling thread can be slow to read the exit code after the resume,
    for example while other Python threads hold the GIL. The program may then
    have run and ended. Its exit code used to read as a kill before the
    resume, and a git that had printed its answer failed with "ended before
    it could run". Here the resume waits until the program has ended.
    """
    import _winapi

    _skip_without_a_job()
    real_resume = _bounded_run._NT_RESUME_PROCESS
    if real_resume is None:
        pytest.skip("this Windows has no NtResumeProcess")

    def resume_then_wait(handle: int) -> int:
        status = int(real_resume(handle))
        _winapi.WaitForSingleObject(handle, int(_EXIT_WAIT_SECONDS * 1000))
        return status

    monkeypatch.setattr(_bounded_run, "_NT_RESUME_PROCESS", resume_then_wait)
    completed = _bounded_run.run_bounded(
        [sys.executable, "-c", f"import sys; print('ran'); sys.exit({exit_code})"],
        timeout=_DEADLINE_SECONDS,
    )
    assert completed.stdout == "ran\n"
    assert completed.returncode == exit_code


@_WINDOWS_ONLY
def test_program_ended_with_exit_code_259_reads_as_told_to_end() -> None:
    """A suspended program ended with exit code 259 is not read as running.

    259 is also the exit code Windows gives a running process (STILL_ACTIVE).
    Once the program has ended, its signalled handle tells the two apart.
    """
    import _winapi

    process = subprocess.Popen(
        [sys.executable, "-c", f"import time; time.sleep({_SLEEP_SECONDS})"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_bounded_run._CREATE_SUSPENDED,
    )
    try:
        handle = int(process._handle)  # type: ignore[attr-defined]  # Popen's own
        assert _bounded_run._told_to_end(handle) is False
        _winapi.TerminateProcess(handle, 259)
        _winapi.WaitForSingleObject(handle, int(_EXIT_WAIT_SECONDS * 1000))
        assert _bounded_run._told_to_end(handle) is True
    finally:
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            process.kill()
            process.wait(timeout=_EXIT_WAIT_SECONDS)


@_WINDOWS_ONLY
def test_interrupt_before_a_failed_resume_acts_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Ctrl+C held during the start is raised before the failed-resume waits.

    The resume fails and the program does not end by itself, so the failure
    path waits for it to end and then for its output. The held Ctrl+C used to
    wait behind those waits, for half a second or more.
    """
    _skip_without_a_job()
    started: list[int] = []
    interrupted_at: list[float] = []

    def interrupted_resume(_job: _bounded_run._Job, process: object) -> bool:
        started.append(int(getattr(process, "pid", 0)))
        interrupted_at.append(time.monotonic())
        signal.raise_signal(signal.SIGINT)
        return False

    monkeypatch.setattr(_bounded_run._Job, "resume", interrupted_resume)
    program_gone = False
    try:
        with _python_interrupt_handler():
            with pytest.raises(KeyboardInterrupt):
                _bounded_run.run_bounded(
                    [
                        sys.executable,
                        "-c",
                        f"import time; time.sleep({_SLEEP_SECONDS})",
                    ],
                    timeout=_SLEEP_SECONDS,
                )
            took = time.monotonic() - interrupted_at[0]
        assert took < _bounded_run._ENDING_WAIT_SECONDS, (
            f"the interrupt waited {took:.2f}s"
        )
        assert len(started) == 1, started
        program_gone = _wait_gone(started[0])
        assert program_gone, "the interrupted program still exists"
    finally:
        if started and not program_gone:
            _end_process(started[0])


@_WINDOWS_ONLY
def test_git_that_cannot_be_resumed_fails_the_checks_in_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A git that started but could not run is a failed git, not a missing one.

    Before, the resume failure was a plain OSError: conventional-commit then
    reported ``git-unavailable`` and passed, and agents-md skipped its
    freshness check and passed, inside a real checkout.
    """
    _skip_without_a_job()
    repo = _project(tmp_path)
    monkeypatch.setattr(_bounded_run._Job, "resume", lambda _job, _process: False)

    completed = run_git(["log", "-1"], cwd=repo, timeout=_DEADLINE_SECONDS)
    assert completed.returncode == NOT_RESUMED_EXIT_CODE
    assert "could not resume" in completed.stderr
    with pytest.raises(subprocess.CalledProcessError) as raised:
        run_git(["log", "-1"], cwd=repo, timeout=_DEADLINE_SECONDS, check=True)
    assert raised.value.returncode == NOT_RESUMED_EXIT_CODE

    subject = conventional_commit_grep.check_repo(repo)
    assert subject.passed is False
    assert subject.status == "git-failed"
    assert subject.check_error == "git log failed with exit code 128"

    companions = agents_md_coverage_grep.check(repo)
    assert companions.passed is False
    assert companions.check_error == "git rev-parse failed with exit code 128"


@contextlib.contextmanager
def _python_interrupt_handler() -> Iterator[None]:
    """Give ``SIGINT`` Python's own handler for the block, then restore it."""
    if threading.current_thread() is not threading.main_thread():
        pytest.skip("only the main thread can set a signal handler")
    previous = signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


def _ends(process: subprocess.Popen[bytes]) -> bool:
    """Return True once *process* has ended, waiting at most the exit wait.

    It reaps the process too, so outside Windows no zombie is left that a
    process ID check would still see.
    """
    try:
        process.wait(timeout=_EXIT_WAIT_SECONDS)
    except subprocess.TimeoutExpired:
        return False
    return True


@pytest.mark.parametrize(
    "new_session",
    [
        False,
        True,
        pytest.param(None, marks=_WINDOWS_ONLY, id="windows-without-a-job"),
    ],
)
def test_interrupt_inside_the_start_does_not_leave_the_program_behind(
    monkeypatch: pytest.MonkeyPatch, new_session: bool | None
) -> None:
    """A Ctrl+C that lands inside Popen, after the program exists, stops it.

    The stand-in Popen raises SIGINT right after the real one created the
    program, before it returns. Without the held-back interrupt the
    KeyboardInterrupt left Popen with no object. On Windows the program,
    never in the job and never resumed, stayed suspended for good. Outside
    Windows, where Python handles a signal as the fork and exec call
    returns, the program ran on outside the time limit, in a session of its
    own with *new_session*. On Windows without a job (None here: Windows
    refuses one, as in a sandbox) the program does not start suspended, and
    it ran on outside the time limit too.
    """
    if new_session is None:
        monkeypatch.setattr(_bounded_run, "_new_job", lambda: None)
    started: list[subprocess.Popen[bytes]] = []
    real_popen = subprocess.Popen

    def interrupted_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        process: subprocess.Popen[bytes] = real_popen(*args, **kwargs)  # type: ignore[call-overload]
        started.append(process)
        signal.raise_signal(signal.SIGINT)
        return process

    monkeypatch.setattr(_bounded_run.subprocess, "Popen", interrupted_popen)
    program_gone = False
    try:
        with _python_interrupt_handler():
            with pytest.raises(KeyboardInterrupt):
                _bounded_run.run_bounded(
                    [
                        sys.executable,
                        "-c",
                        f"import time; time.sleep({_SLEEP_SECONDS})",
                    ],
                    timeout=_SLEEP_SECONDS,
                    new_session=bool(new_session),
                )
            assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
        assert len(started) == 1, started
        program_gone = _ends(started[0])
        assert program_gone, "the interrupted program still exists"
    finally:
        for process in started:
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                process.kill()
                process.communicate(timeout=_EXIT_WAIT_SECONDS)


def _popen_interrupted_in_its_wait(
    started: list[subprocess.Popen[bytes]],
) -> type[subprocess.Popen[bytes]]:
    """Return a Popen that records each program and raises SIGINT in its wait.

    Only the first wait is interrupted, so a test's own clean-up can wait.
    """
    real_popen = subprocess.Popen

    class InterruptedPopen(real_popen):  # type: ignore[misc,valid-type]
        def communicate(self, *args: object, **kwargs: object) -> object:
            if self not in started:
                started.append(self)
                signal.raise_signal(signal.SIGINT)
            return super().communicate(*args, **kwargs)

    return InterruptedPopen


@pytest.mark.parametrize(
    "new_session",
    [
        False,
        True,
        pytest.param(None, marks=_WINDOWS_ONLY, id="windows-without-a-job"),
    ],
)
def test_second_interrupt_during_the_stop_does_not_skip_it(
    monkeypatch: pytest.MonkeyPatch, new_session: bool | None
) -> None:
    """A Ctrl+C that lands as the stop for the first one begins still stops.

    The first Ctrl+C lands while run_bounded waits, the second as the stop
    begins. The second used to skip the kill. Outside Windows the program
    then ran on, in a session of its own with *new_session*, out of the
    terminal's reach. On Windows without a job (None here) it ran on too.
    """
    if new_session is None:
        monkeypatch.setattr(_bounded_run, "_new_job", lambda: None)
    started: list[subprocess.Popen[bytes]] = []
    monkeypatch.setattr(
        _bounded_run.subprocess, "Popen", _popen_interrupted_in_its_wait(started)
    )
    real_stop = _bounded_run._stop
    stops: list[int] = []

    def interrupted_stop(
        process: subprocess.Popen[bytes], job: _bounded_run._Job, *, group: bool
    ) -> None:
        stops.append(process.pid)
        if len(stops) == 1:
            signal.raise_signal(signal.SIGINT)
        real_stop(process, job, group=group)

    monkeypatch.setattr(_bounded_run, "_stop", interrupted_stop)
    program_gone = False
    try:
        with _python_interrupt_handler():
            with pytest.raises(KeyboardInterrupt):
                _bounded_run.run_bounded(
                    [
                        sys.executable,
                        "-c",
                        f"import time; time.sleep({_SLEEP_SECONDS})",
                    ],
                    timeout=_SLEEP_SECONDS,
                    new_session=bool(new_session),
                )
            assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
        assert len(started) == 1, started
        program_gone = _ends(started[0])
        assert program_gone, "the program still runs after the second interrupt"
    finally:
        for process in started:
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                process.kill()
                process.communicate(timeout=_EXIT_WAIT_SECONDS)


@pytest.mark.parametrize(
    "new_session",
    [
        False,
        True,
        pytest.param(None, marks=_WINDOWS_ONLY, id="windows-without-a-job"),
    ],
)
def test_interrupted_program_is_waited_for(
    monkeypatch: pytest.MonkeyPatch, new_session: bool | None
) -> None:
    """A program stopped by a Ctrl+C has ended by the time the interrupt leaves.

    Before, only a time-out waited for the stopped program. Outside Windows a
    program stopped by an interrupt stayed a zombie, holding its process ID,
    until a later Popen happened to reap it. On Windows with a job, the kill
    after the job's stop already records the exit code; without a job (None
    here) nothing did.
    """
    if new_session is None:
        monkeypatch.setattr(_bounded_run, "_new_job", lambda: None)
    started: list[subprocess.Popen[bytes]] = []
    monkeypatch.setattr(
        _bounded_run.subprocess, "Popen", _popen_interrupted_in_its_wait(started)
    )
    try:
        with _python_interrupt_handler(), pytest.raises(KeyboardInterrupt):
            _bounded_run.run_bounded(
                [sys.executable, "-c", f"import time; time.sleep({_SLEEP_SECONDS})"],
                timeout=_SLEEP_SECONDS,
                new_session=bool(new_session),
            )
        assert len(started) == 1, started
        assert started[0].returncode is not None, "the stopped program was not reaped"
    finally:
        for process in started:
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                process.kill()
                process.communicate(timeout=_EXIT_WAIT_SECONDS)


# A program that runs run_bounded with a new session, with a Popen that sends
# this process the signal named by the first argument right after the real
# Popen started the program. It writes that program's process ID to the file
# named by the second argument first.
_SIGNALLED_START_PROGRAM = (
    "import os, subprocess, sys\n"
    "from pathlib import Path\n"
    "from apothem.conformity import _bounded_run\n"
    "signum, pid_file = int(sys.argv[1]), Path(sys.argv[2])\n"
    "real_popen = subprocess.Popen\n"
    "def signalled_popen(*args, **kwargs):\n"
    "    process = real_popen(*args, **kwargs)\n"
    "    pid_file.write_text(str(process.pid), encoding='utf-8')\n"
    "    os.kill(os.getpid(), signum)\n"
    "    return process\n"
    "_bounded_run.subprocess.Popen = signalled_popen\n"
    "_bounded_run.run_bounded(\n"
    f"    [sys.executable, '-c', 'import time; time.sleep({_SLEEP_SECONDS})'],\n"
    f"    timeout={_SLEEP_SECONDS},\n"
    "    new_session=True,\n"
    ")\n"
)


@_POSIX_ONLY
@pytest.mark.parametrize("signal_name", ["SIGTERM", "SIGHUP"])
def test_termination_during_the_start_stops_the_program(
    tmp_path: Path, signal_name: str
) -> None:
    """A SIGTERM or SIGHUP as a new-session program starts does not leave it.

    The signal turned into an exit only once run_bounded waited. During the
    start it kept its default action: this process died at once, and the
    program, in a session of its own, ran on. It is now held back until the
    program exists, which is then stopped before the exit (128 plus the
    signal's number). The run is a process of its own, so a regression ends
    that process and not the test run.
    """
    # Looked up here: Windows, where the test is skipped, has no SIGHUP.
    signum = int(getattr(signal, signal_name))
    pid_file = tmp_path / "program.pid"
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}
    program_gone = False
    try:
        run = subprocess.run(
            [
                sys.executable,
                "-c",
                _SIGNALLED_START_PROGRAM,
                str(signum),
                str(pid_file),
            ],
            env=env,
            capture_output=True,
            check=False,
            timeout=_DEADLINE_SECONDS,
        )
        assert run.returncode == 128 + signum, (
            f"exit {run.returncode}: {run.stderr.decode('utf-8', 'replace')}"
        )
        program = _read_pid(pid_file)
        assert program is not None, "the run never started its program"
        program_gone = _wait_gone(program)
        assert program_gone, "the program still runs after the signal"
    finally:
        leftover = _read_pid(pid_file)
        if leftover is not None and not program_gone:
            with contextlib.suppress(OSError):
                os.kill(leftover, signal.SIGKILL)


@pytest.mark.parametrize("new_session", [False, True])
def test_a_refused_signal_handler_leaves_no_trace_on_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, new_session: bool
) -> None:
    """When no handler can be set, the start runs without the hold.

    Only the main interpreter may set a signal handler; elsewhere
    ``signal.signal`` raises ValueError. The program then runs as usual, and
    an error from the start does not carry that ValueError as its context
    (the hold used to yield inside the ``except ValueError`` block). With
    *new_session*, outside Windows, the termination handlers are refused
    too: that refusal used to fail the run before the program started.
    """

    refusals: list[int] = []

    def refused(_signum: int, _handler: object) -> object:
        # Give up after a thousand calls, so a lost bound fails the test
        # instead of hanging it.
        refusals.append(_signum)
        if len(refusals) < 1000:
            raise ValueError("signal only works in main thread of the main interpreter")
        return None

    with (
        _python_interrupt_handler(),
        _default_terminations(),
        monkeypatch.context() as patch,
    ):
        patch.setattr(_bounded_run, "_SET_HANDLER", refused)
        completed = _bounded_run.run_bounded(
            [sys.executable, "-c", _PRINT_PROGRAM],
            timeout=_DEADLINE_SECONDS,
            new_session=new_session,
        )
        with pytest.raises(FileNotFoundError) as raised:
            _bounded_run.run_bounded(
                [str(tmp_path / "missing-program")],
                timeout=_DEADLINE_SECONDS,
                new_session=new_session,
            )
    assert completed.stdout == "ran\n"
    assert not isinstance(raised.value.__context__, ValueError), raised.value
    assert len(refusals) < 1000, "the refused change was tried without a bound"


@_WINDOWS_ONLY
def test_a_handler_the_caller_installed_stays_during_the_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only Python's own interrupt handler is replaced while a program starts."""
    _skip_without_a_job()
    seen: list[object] = []
    real_popen = subprocess.Popen

    def watching_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        seen.append(signal.getsignal(signal.SIGINT))
        process: subprocess.Popen[bytes] = real_popen(*args, **kwargs)  # type: ignore[call-overload]
        return process

    def own_handler(_signum: int, _frame: FrameType | None) -> None:
        """Stand in for a handler the caller installed."""

    monkeypatch.setattr(_bounded_run.subprocess, "Popen", watching_popen)
    with _python_interrupt_handler():
        _bounded_run.run_bounded(
            [sys.executable, "-c", _PRINT_PROGRAM], timeout=_DEADLINE_SECONDS
        )
        assert seen[-1] is not signal.default_int_handler
        signal.signal(signal.SIGINT, own_handler)
        _bounded_run.run_bounded(
            [sys.executable, "-c", _PRINT_PROGRAM], timeout=_DEADLINE_SECONDS
        )
        assert seen[-1] is own_handler
        assert signal.getsignal(signal.SIGINT) is own_handler


@pytest.mark.parametrize("new_session", [False, True])
def test_error_that_escapes_popen_after_the_start_stops_the_program(
    monkeypatch: pytest.MonkeyPatch, new_session: bool
) -> None:
    """An error inside Popen, once the program exists, does not leave it behind.

    Popen returns no object when it raises, so run_bounded finds the program
    through Popen's own frames. Outside Windows, with *new_session*, the stop
    ends the program's whole process group.
    """
    started: list[int] = []
    real_popen = subprocess.Popen

    class FailingPopen(real_popen):  # type: ignore[misc,valid-type]
        def _execute_child(self, *args: object, **kwargs: object) -> None:
            super()._execute_child(*args, **kwargs)
            started.append(self.pid)
            raise RuntimeError("a failure after the program was created")

    monkeypatch.setattr(_bounded_run.subprocess, "Popen", FailingPopen)
    program_gone = False
    try:
        with pytest.raises(RuntimeError, match="after the program was created"):
            _bounded_run.run_bounded(
                [sys.executable, "-c", f"import time; time.sleep({_SLEEP_SECONDS})"],
                timeout=_SLEEP_SECONDS,
                new_session=new_session,
            )
        assert len(started) == 1, started
        program_gone = _wait_gone(started[0])
        assert program_gone, "the program Popen started still exists"
    finally:
        if started and not program_gone:
            _end_process(started[0])


# A program that prints one line and ends.
_PRINT_PROGRAM = "print('ran')"


def _record_snapshots(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Record the process ID of each thread snapshot run_bounded takes."""
    taken: list[int] = []
    real_thread_ids = _bounded_run._thread_ids

    def recording_thread_ids(pid: int) -> list[int]:
        taken.append(pid)
        return real_thread_ids(pid)

    monkeypatch.setattr(_bounded_run, "_thread_ids", recording_thread_ids)
    return taken


@_WINDOWS_ONLY
def test_suspended_program_resumes_without_a_thread_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The program is resumed through its process handle, not a snapshot.

    A thread snapshot holds every thread on the machine, which made each start
    several times slower.
    """
    _skip_without_a_job()
    if _bounded_run._NT_RESUME_PROCESS is None:
        pytest.skip("this Windows has no NtResumeProcess")
    taken = _record_snapshots(monkeypatch)
    completed = _bounded_run.run_bounded(
        [sys.executable, "-c", _PRINT_PROGRAM], timeout=_DEADLINE_SECONDS
    )
    assert completed.stdout == "ran\n"
    assert taken == [], "the program was resumed through a thread snapshot"


def _failing_nt_resume(_handle: int) -> int:
    """Stand in for an NtResumeProcess that fails (STATUS_UNSUCCESSFUL)."""
    return -0x3FFFFFFF


@_WINDOWS_ONLY
@pytest.mark.parametrize(
    "nt_resume", [None, _failing_nt_resume], ids=["missing", "failing"]
)
def test_suspended_program_resumes_through_the_snapshot_fallback(
    monkeypatch: pytest.MonkeyPatch, nt_resume: Callable[[int], int] | None
) -> None:
    """Without a working NtResumeProcess the thread snapshot resumes it."""
    _skip_without_a_job()
    monkeypatch.setattr(_bounded_run, "_NT_RESUME_PROCESS", nt_resume)
    taken = _record_snapshots(monkeypatch)
    completed = _bounded_run.run_bounded(
        [sys.executable, "-c", _PRINT_PROGRAM], timeout=_DEADLINE_SECONDS
    )
    assert completed.stdout == "ran\n"
    assert len(taken) == 1, taken


@_WINDOWS_ONLY
def test_interrupt_right_after_the_start_stops_the_program(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An interrupt just after the program starts never leaves it suspended.

    A trace function raises KeyboardInterrupt at the first line run_bounded
    runs after Popen returns, before the program is in the job or resumed.
    """
    _skip_without_a_job()
    started: list[subprocess.Popen[bytes]] = []
    real_popen = subprocess.Popen

    def recording_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        process: subprocess.Popen[bytes] = real_popen(*args, **kwargs)  # type: ignore[call-overload]
        started.append(process)
        return process

    monkeypatch.setattr(_bounded_run.subprocess, "Popen", recording_popen)
    code = _bounded_run.run_bounded.__code__
    interrupted_at: list[int] = []

    def trace_line(frame: FrameType, event: str, _arg: object) -> object:
        if event == "line" and started and not interrupted_at:
            interrupted_at.append(frame.f_lineno)
            raise KeyboardInterrupt
        return trace_line

    def trace_call(frame: FrameType, _event: str, _arg: object) -> object:
        return trace_line if frame.f_code is code else None

    program_gone = False
    previous = sys.gettrace()
    try:
        sys.settrace(trace_call)
        try:
            with pytest.raises(KeyboardInterrupt):
                _bounded_run.run_bounded(
                    [
                        sys.executable,
                        "-c",
                        f"import time; time.sleep({_SLEEP_SECONDS})",
                    ],
                    timeout=_SLEEP_SECONDS,
                )
        finally:
            sys.settrace(previous)
        assert interrupted_at, "the interrupt never fired"
        assert len(started) == 1, started
        program_gone = _wait_gone(started[0].pid)
        assert program_gone, (
            f"the program interrupted at line {interrupted_at[0]} still exists"
        )
    finally:
        for process in started:
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                process.kill()
                process.communicate(timeout=_EXIT_WAIT_SECONDS)


# Errors a signal's handler can raise as a change of handlers begins: the
# gate's termination, Ctrl+C, and a caller's own handler raising an error of
# the kind signal.signal raises when it refuses a handler (an OSError).
_HANDLER_ERRORS = pytest.mark.parametrize(
    "first_error",
    [SystemExit(143), KeyboardInterrupt(), TimeoutError("a caller's alarm")],
    ids=["termination", "ctrl-c", "caller-timeout"],
)


@_HANDLER_ERRORS
def test_a_change_a_signal_stopped_is_made_again(
    monkeypatch: pytest.MonkeyPatch, first_error: BaseException
) -> None:
    """A signal that lands as a handler changes leaves no pair unset.

    CPython runs the handler of a signal that has arrived before
    ``signal.signal`` changes anything, so a pending ``SIGTERM`` whose
    handler raises ``SystemExit`` stops that change. The stand-in raises the
    way CPython does, before the real change. That pair used to stay unset
    (``SIGTERM`` kept the hold's handler); it is now set in the next pass,
    the pair after it is set in the first, and the error is kept to go on. A
    ``TimeoutError`` from a caller's handler comes once, so it does not end
    the tries.
    """
    real_signal = signal.signal
    old_int = signal.getsignal(signal.SIGINT)
    old_term = signal.getsignal(signal.SIGTERM)
    calls: list[int] = []

    def raising_first(signum: int, handler: object) -> object:
        calls.append(signum)
        if len(calls) == 1:
            raise first_error
        return real_signal(signum, handler)  # type: ignore[arg-type]

    def wanted(_signum: int, _frame: object) -> None:
        return None

    errors: list[BaseException] = []
    try:
        monkeypatch.setattr(_bounded_run, "_SET_HANDLER", raising_first)
        done = _bounded_run._swap(
            [(signal.SIGTERM, wanted), (signal.SIGINT, wanted)], errors
        )
        monkeypatch.undo()
        assert done
        assert errors == [first_error]
        assert calls == [signal.SIGTERM, signal.SIGINT, signal.SIGTERM]
        assert signal.getsignal(signal.SIGTERM) is wanted
        assert signal.getsignal(signal.SIGINT) is wanted
    finally:
        monkeypatch.undo()
        errors.clear()
        real_signal(signal.SIGINT, old_int)
        real_signal(signal.SIGTERM, old_term)


def test_a_refused_handler_is_left_and_the_next_one_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A handler ``signal.signal`` refuses at every try is left as it was.

    The same ``ValueError`` comes back on the second try, so the tries end
    and the pair keeps its old handler. The other pair is still set, the
    block runs, the refusal goes no further, and the restore leaves the
    refused pair alone.
    """
    real_signal = signal.signal
    old_int = signal.getsignal(signal.SIGINT)
    old_term = signal.getsignal(signal.SIGTERM)
    tries: list[int] = []

    def refusing_sigterm(signum: int, handler: object) -> object:
        if signum == signal.SIGTERM:
            tries.append(signum)
            # A thousand refusals at most: a lost bound fails, not hangs.
            if len(tries) < 1000:
                raise ValueError("signal only works in main thread")
        return real_signal(signum, handler)  # type: ignore[arg-type]

    def wanted(_signum: int, _frame: object) -> None:
        return None

    inside: list[object] = []
    try:
        monkeypatch.setattr(_bounded_run, "_SET_HANDLER", refusing_sigterm)
        with _bounded_run._swapped(
            [signal.SIGTERM, signal.SIGINT], wanted, lambda current: current is wanted
        ):
            inside.extend(
                signal.getsignal(signum) for signum in (signal.SIGTERM, signal.SIGINT)
            )
        monkeypatch.undo()
        assert len(tries) == 2, f"signal.signal was tried {len(tries)} times"
        assert inside == [old_term, wanted]
        assert signal.getsignal(signal.SIGTERM) is old_term
        assert signal.getsignal(signal.SIGINT) is old_int
    finally:
        monkeypatch.undo()
        real_signal(signal.SIGINT, old_int)
        real_signal(signal.SIGTERM, old_term)


def test_a_callers_one_off_value_error_is_not_taken_for_a_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``ValueError`` raised once as a hold is set goes on.

    Only a refusal, the same error at every try, leaves a pair unset, and
    only then is its ``ValueError`` dropped. A caller's handler raising
    ``ValueError`` once used to be dropped too, and the block ran.
    """
    real_signal = signal.signal
    calls: list[int] = []

    def value_error_once(signum: int, handler: object) -> object:
        calls.append(signum)
        if len(calls) == 1:
            raise ValueError("a caller's own error")
        return real_signal(signum, handler)  # type: ignore[arg-type]

    ran: list[bool] = []
    with _python_interrupt_handler():
        monkeypatch.setattr(_bounded_run, "_SET_HANDLER", value_error_once)
        with pytest.raises(ValueError, match="own error"), _bounded_run._held_signals():
            ran.append(True)
        monkeypatch.undo()
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    assert not ran, "the block ran: the caller's ValueError was dropped"


@pytest.mark.parametrize("kind", [RuntimeError, KeyboardInterrupt])
def test_an_error_at_every_change_ends_the_tries(
    monkeypatch: pytest.MonkeyPatch, kind: type[BaseException]
) -> None:
    """An error that comes back at every change ends within a few tries.

    A ``signal.signal`` that raises ``RuntimeError`` at every call stands in
    for any error that recurs, such as a ``RecursionError`` near the limit.
    The change used to be tried for ever, with the signals blocked and the
    list of errors growing. It now ends at the second ``RuntimeError``, the
    run raises it, nothing is left blocked, and one error is kept. A
    ``KeyboardInterrupt``, which a signal's handler raises once per signal,
    is tried again, but only up to the bound. The stand-in gives up after a
    thousand calls, so a regression fails the test instead of hanging it.
    """
    real_signal = signal.signal
    calls: list[int] = []

    def always_failing(signum: int, handler: object) -> object:
        calls.append(signum)
        if len(calls) < 1000:
            raise kind("signal.signal failed")
        return real_signal(signum, handler)  # type: ignore[arg-type]

    errors: list[BaseException] = []
    mask_before = _blocked_now()
    tries = 2 if kind is RuntimeError else _bounded_run._TRIES
    tracemalloc.start()
    try:
        with _python_interrupt_handler(), _default_terminations():
            # Start with the gate's three signals unblocked, whatever an
            # earlier test or the worker left, so the check below reads this
            # test's own effect. A signal that waited is handled here, by
            # this test's handlers.
            _unblock_the_gates_signals()
            monkeypatch.setattr(_bounded_run, "_SET_HANDLER", always_failing)
            assert not _bounded_run._swap([(signal.SIGINT, signal.SIG_IGN)], errors)
            assert len(calls) == tries, f"signal.signal was tried {len(calls)} times"
            assert [type(error) for error in errors] == [kind]
            calls.clear()
            with pytest.raises(kind, match="failed"):
                _bounded_run.run_bounded(
                    [sys.executable, "-c", _PRINT_PROGRAM],
                    timeout=_DEADLINE_SECONDS,
                    new_session=True,
                )
            monkeypatch.undo()
            peak = tracemalloc.get_traced_memory()[1]
            assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    finally:
        tracemalloc.stop()
        errors.clear()
        blocked = _blocked_now()
        _restore_mask(mask_before)
    assert 0 < len(calls) <= 2 * _bounded_run._TRIES, f"{len(calls)} calls"
    assert _GATES_SIGNALS.isdisjoint(blocked), f"left blocked: {blocked}"
    assert peak < 1_000_000, f"the tries took {peak} bytes"


def test_an_error_that_would_come_back_ends_the_tries_at_once() -> None:
    """Only an error a signal's handler raises once per signal earns a new try.

    A ``SystemExit`` or ``KeyboardInterrupt`` is tried again, even when it
    came before. A ``RecursionError`` or ``MemoryError`` would come back at
    once: no new try. Any other error is tried again once, until its type
    comes back. One error of each type is kept.
    """
    note = _bounded_run._note
    errors: list[BaseException] = []
    assert note(errors, KeyboardInterrupt())
    assert note(errors, KeyboardInterrupt())
    assert note(errors, SystemExit(143))
    assert note(errors, SystemExit(129))
    assert not note(errors, RecursionError())
    assert not note(errors, MemoryError())
    assert note(errors, TimeoutError("a caller's alarm"))
    assert not note(errors, TimeoutError("a caller's alarm"))
    assert [type(error) for error in errors] == [
        KeyboardInterrupt,
        SystemExit,
        RecursionError,
        MemoryError,
        TimeoutError,
    ]
    assert errors[1].code == 143


def test_the_change_takes_an_enum_handler() -> None:
    """``signal.SIG_IGN`` given as the enum reaches the C call as a plain int.

    The C ``signal`` that the gate calls refuses the ``Handlers`` enum with
    ``TypeError``; ``signal.signal`` converts it, and the gate does the same.
    """
    errors: list[BaseException] = []
    with _python_interrupt_handler():
        try:
            assert _bounded_run._swap([(signal.SIGINT, signal.SIG_IGN)], errors)
            assert errors == []
            assert signal.getsignal(signal.SIGINT) is signal.SIG_IGN
        finally:
            signal.signal(signal.SIGINT, signal.default_int_handler)


def test_a_restore_that_raises_every_time_ends_within_the_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The call that puts handlers back is made again at most a few times.

    Each restore call meets a Ctrl+C as it begins. Such a restore used to be
    tried until a call returned, for ever if the Ctrl+C came every time. It
    now ends after :data:`_bounded_run._TRIES` calls and the Ctrl+C goes on.
    The last try, made from the hold's own frame, still puts Python's
    handler back: a Ctrl+C left on the hold's recorder would be dropped for
    the rest of the process.
    """
    calls: list[int] = []
    after: object = None
    raising: dict[int, BaseException] = {
        number: KeyboardInterrupt() for number in range(2, 1000)
    }
    with _python_interrupt_handler():
        monkeypatch.setattr(
            _bounded_run, "_swap", _swap_raising_as_it_begins(raising, calls)
        )
        try:
            with pytest.raises(KeyboardInterrupt), _bounded_run._held_signals():
                pass
        finally:
            monkeypatch.undo()
            after = signal.getsignal(signal.SIGINT)
            # Should the test fail, put Python's handler back by hand.
            signal.signal(signal.SIGINT, signal.default_int_handler)
    assert len(calls) == 1 + _bounded_run._TRIES, f"{len(calls)} calls"
    assert after is signal.default_int_handler, f"SIGINT left on {after!r}"


def test_the_last_try_keeps_a_handler_the_caller_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The last try puts back only a handler that is still the hold's.

    Every restore call meets a Ctrl+C as it begins, so the last try runs. A
    handler the caller set during the block stays: without the last try's
    check, Python's handler would replace it.
    """
    calls: list[int] = []
    after: object = None
    raising: dict[int, BaseException] = {
        number: KeyboardInterrupt() for number in range(2, 1000)
    }

    def own_handler(_signum: int, _frame: FrameType | None) -> None:
        return None

    with _python_interrupt_handler():
        monkeypatch.setattr(
            _bounded_run, "_swap", _swap_raising_as_it_begins(raising, calls)
        )
        try:
            with pytest.raises(KeyboardInterrupt), _bounded_run._held_signals():
                signal.signal(signal.SIGINT, own_handler)
        finally:
            monkeypatch.undo()
            after = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, signal.default_int_handler)
    assert len(calls) == 1 + _bounded_run._TRIES, f"{len(calls)} calls"
    assert after is own_handler, f"SIGINT left on {after!r}"


def test_a_second_ctrl_c_in_the_restore_still_reaches_the_last_try(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Ctrl+C as the restore's error is noted still leaves the last try.

    The restore meets a Ctrl+C as it begins, and a second one lands as that
    error is noted, outside the restore's own ``try``. The second used to
    leave the hold, skipping every later try, and ``SIGINT`` stayed on the
    hold's recorder for the rest of the process.
    """
    calls: list[int] = []
    after: object = None
    real_note = _bounded_run._note
    notes: list[BaseException] = []

    def note_interrupted_once(
        errors: list[BaseException], error: BaseException
    ) -> bool:
        notes.append(error)
        if len(notes) == 1:
            raise KeyboardInterrupt("second, as the first was noted")
        return real_note(errors, error)

    with _python_interrupt_handler():
        monkeypatch.setattr(
            _bounded_run,
            "_swap",
            _swap_raising_as_it_begins({2: KeyboardInterrupt("first")}, calls),
        )
        monkeypatch.setattr(_bounded_run, "_note", note_interrupted_once)
        try:
            with pytest.raises(KeyboardInterrupt), _bounded_run._held_signals():
                pass
        finally:
            monkeypatch.undo()
            after = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, signal.default_int_handler)
    assert len(notes) >= 2, f"{len(notes)} errors noted"
    assert after is signal.default_int_handler, f"SIGINT left on {after!r}"


@pytest.mark.skipif(
    sys.implementation.name != "cpython", reason="_signal is CPython's C module"
)
def test_the_gate_changes_handlers_with_the_c_calls() -> None:
    """The gate calls the C ``signal`` and ``getsignal``, not the Python ones.

    ``signal.signal`` and ``signal.getsignal`` are Python functions that call
    these, one frame deeper: near the recursion limit a restore through them
    failed where the change had passed, and left Ctrl+C on a hold's recorder.
    """
    import _signal  # type: ignore[import-not-found]  # no stub: CPython's C module

    assert _bounded_run._SET_HANDLER is _signal.signal
    assert _bounded_run._GET_HANDLER is _signal.getsignal


def test_a_ctrl_c_in_the_last_stop_keeps_the_termination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An error in run_bounded's own last stop ranks after a termination.

    A ``SIGTERM`` lands as the stop after a time-out begins, so run_bounded
    stops the program itself; a Ctrl+C then lands in that stop. The Ctrl+C
    used to replace the termination, and the gate exited ``130``, not
    ``143``. The program is stopped either way.
    """
    real_stop = _bounded_run._stop
    started: list[subprocess.Popen[bytes]] = []

    def terminated(
        process: subprocess.Popen[bytes],
        _job: _bounded_run._Job,
        _error: BaseException,
        *,
        group: bool,
    ) -> None:
        started.append(process)
        raise SystemExit(143)

    def stop_then_interrupt(
        process: subprocess.Popen[bytes], job: _bounded_run._Job, *, group: bool
    ) -> None:
        real_stop(process, job, group=group)
        raise KeyboardInterrupt

    monkeypatch.setattr(_bounded_run, "_stop_after_error", terminated)
    monkeypatch.setattr(_bounded_run, "_stop", stop_then_interrupt)
    try:
        with (
            _python_interrupt_handler(),
            _default_terminations(),
            # KeyboardInterrupt too, so a regression fails this test instead
            # of stopping the whole run.
            pytest.raises((SystemExit, KeyboardInterrupt)) as raised,
        ):
            _bounded_run.run_bounded(
                [sys.executable, "-c", f"import time; time.sleep({_SLEEP_SECONDS})"],
                timeout=0.5,
                new_session=True,
            )
        assert isinstance(raised.value, SystemExit), f"{raised.value!r} went out"
        assert raised.value.code == 143
        assert started, "the run did not reach the stop"
        assert _ends(started[0]), "the program still runs"
    finally:
        for process in started:
            with contextlib.suppress(OSError):
                process.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=_EXIT_WAIT_SECONDS)


def _blocked_now() -> list[int]:
    """Return the signals this thread blocks; none where there is no mask."""
    if not hasattr(signal, "pthread_sigmask"):
        return []
    return sorted(signal.pthread_sigmask(signal.SIG_BLOCK, []))


# The signals the gate blocks while it changes handlers (none on Windows).
_GATES_SIGNALS: frozenset[int] = frozenset(
    getattr(signal, name) for name in ("SIGINT", "SIGTERM", "SIGHUP") if os.name != "nt"
)


def _unblock_the_gates_signals() -> None:
    """Unblock the gate's signals on this thread."""
    if hasattr(signal, "pthread_sigmask"):
        signal.pthread_sigmask(signal.SIG_UNBLOCK, _GATES_SIGNALS)


def _restore_mask(mask: list[int]) -> None:
    """Make *mask* this thread's signal mask again."""
    if hasattr(signal, "pthread_sigmask"):
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)


# A program that calls run_bounded a few frames below the recursion limit, at
# each gap from 1 to 15 frames, and prints, as JSON, what each call did, then
# which of the gate's signals it left blocked and whether SIGINT has its
# handler back.
_NEAR_THE_LIMIT_PROGRAM = """\
import json, signal, sys
from apothem.conformity import _bounded_run

new_session = sys.argv[1] == "1"
limit = sys.getrecursionlimit()
argv = [sys.executable, "-c", "pass"]
gates = {signal.SIGINT, signal.SIGTERM, signal.SIGHUP} if hasattr(signal, "SIGHUP") else set()
if hasattr(signal, "pthread_sigmask"):
    # Whatever mask this process inherited, start with the gate's unblocked.
    signal.pthread_sigmask(signal.SIG_UNBLOCK, gates)
# An ignored SIGINT is inherited too: start from Python's own handler.
signal.signal(signal.SIGINT, signal.default_int_handler)


def depth():
    frame, count = sys._getframe(), 0
    while frame is not None:
        count += 1
        frame = frame.f_back
    return count


def dive(gap):
    if depth() < limit - gap:
        return dive(gap)
    return _bounded_run.run_bounded(argv, timeout=60, new_session=new_session)


outcomes = []
for gap in range(1, 16):
    try:
        dive(gap)
        outcomes.append("returned")
    except Exception as error:
        outcomes.append(type(error).__name__)
mask = []
if hasattr(signal, "pthread_sigmask"):
    mask = sorted(gates & set(signal.pthread_sigmask(signal.SIG_BLOCK, [])))
interrupt = signal.getsignal(signal.SIGINT) is signal.default_int_handler
print(json.dumps({"outcomes": outcomes, "mask": mask, "interrupt": interrupt}))
"""


@pytest.mark.parametrize("new_session", [False, True])
def test_a_run_near_the_recursion_limit_raises_at_once(new_session: bool) -> None:
    """A run a few frames below the recursion limit ends with an error at once.

    Every signal call there raises ``RecursionError``, and the change of
    handlers used to try again for ever: the process hung with ``SIGINT``,
    ``SIGTERM`` and ``SIGHUP`` blocked, and its memory grew. The error now
    goes on (on Windows, Python 3.10's ctypes may wrap it in an
    ``ArgumentError``), nothing stays blocked, and ``SIGINT`` has its
    handler back. The run is a process of its own with a deadline, so a
    regression fails the test instead of hanging it.
    """
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}
    run = subprocess.run(
        [sys.executable, "-c", _NEAR_THE_LIMIT_PROGRAM, "1" if new_session else "0"],
        env=env,
        capture_output=True,
        check=False,
        timeout=_DEADLINE_SECONDS * 4,
    )
    assert run.returncode == 0, run.stderr.decode("utf-8", "replace")
    result = json.loads(run.stdout)
    errors = {outcome for outcome in result["outcomes"] if outcome != "returned"}
    assert errors, f"no run reached the limit: {result}"
    assert errors <= {"RecursionError", "ArgumentError"}, result
    assert result["mask"] == [], result
    assert result["interrupt"], result


# A program that runs run_bounded in a subinterpreter, which may not set a
# signal handler, with and without a new session.
_SUBINTERPRETER_PROGRAM = """\
from concurrent import interpreters

interpreter = interpreters.create()
interpreter.exec('''
import sys
from apothem.conformity import _bounded_run

for new_session in (False, True):
    done = _bounded_run.run_bounded(
        [sys.executable, "-c", "print(42)"], timeout=60, new_session=new_session
    )
    assert done.stdout == "42\\\\n", done
''')
print("ran")
"""


# Windows is left out: there Popen.communicate reads the output on daemon
# threads, which a subinterpreter does not allow.
@_POSIX_ONLY
@pytest.mark.skipif(
    sys.version_info < (3, 14), reason="concurrent.interpreters is Python 3.14+"
)
def test_a_run_in_a_subinterpreter_runs_its_program() -> None:
    """A subinterpreter, where ``signal.signal`` refuses, still runs programs.

    Outside Windows the subinterpreter's ``SIGTERM`` reads as the default
    action, so the termination handlers were set, and their refusal
    (``ValueError``) failed every run with a new session before it started.
    The refusal now leaves the handlers as they are, as the Ctrl+C hold
    does.
    """
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}
    run = subprocess.run(
        [sys.executable, "-c", _SUBINTERPRETER_PROGRAM],
        env=env,
        capture_output=True,
        check=False,
        timeout=_DEADLINE_SECONDS * 2,
    )
    assert run.returncode == 0, run.stderr.decode("utf-8", "replace")
    assert run.stdout.decode("utf-8").split() == ["ran"]


def test_the_gravest_error_ranks_a_termination_then_ctrl_c() -> None:
    """Of several errors, a termination goes on, then Ctrl+C, then the first."""
    refusal, timeout = ValueError("refused"), TimeoutError("a caller's alarm")
    interrupt, termination = KeyboardInterrupt(), SystemExit(143)
    gravest = _bounded_run._gravest
    assert gravest([refusal, interrupt, termination]) is termination
    assert gravest([refusal, timeout, interrupt]) is interrupt
    assert gravest([refusal, timeout]) is refusal


@_POSIX_ONLY
def test_a_ctrl_c_beside_a_refused_hold_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Ctrl+C that lands as a hold is set goes on even when a pair is refused.

    The hold drops a refusal (``ValueError``) and runs its block without
    that pair. ``SIGINT`` is refused here, and a Ctrl+C then stops the change
    of ``SIGTERM`` once. Raised first, the refusal used to stand for both,
    so the Ctrl+C was dropped with it and the block ran.
    """
    real_signal = signal.signal
    interrupted: list[int] = []
    refusals: list[int] = []

    def refuse_sigint_then_interrupt(signum: int, handler: object) -> object:
        if signum == signal.SIGINT and handler is not signal.default_int_handler:
            refusals.append(signum)
            # A thousand refusals at most: a lost bound fails, not hangs.
            if len(refusals) < 1000:
                raise ValueError("signal only works in main thread")
        if signum == signal.SIGTERM and not interrupted:
            interrupted.append(signum)
            raise KeyboardInterrupt
        return real_signal(signum, handler)  # type: ignore[arg-type]

    ran: list[bool] = []
    with _python_interrupt_handler(), _default_terminations():
        before = {
            name: signal.getsignal(getattr(signal, name))
            for name in ("SIGINT", "SIGTERM", "SIGHUP")
        }
        monkeypatch.setattr(_bounded_run, "_SET_HANDLER", refuse_sigint_then_interrupt)
        with (
            pytest.raises(KeyboardInterrupt),
            _bounded_run._held_signals(terminations=True),
        ):
            ran.append(True)
        monkeypatch.undo()
        after = {name: signal.getsignal(getattr(signal, name)) for name in before}
    assert interrupted, "the Ctrl+C was never raised"
    assert not ran, "the block ran: the Ctrl+C was dropped with the refusal"
    assert after == before
    assert len(refusals) < 1000, "the refused change was tried without a bound"


@_POSIX_ONLY
def test_a_hold_closed_late_does_not_undo_the_outer_restore() -> None:
    """A hold whose end comes after the termination handlers are back keeps them.

    A signal whose handler raises as contextlib enters or leaves the hold
    leaves its generator suspended: the error reaches the outer
    ``_exit_on_termination`` first, which puts ``SIGTERM`` and ``SIGHUP``
    back, and the hold ends only when its generator is closed. Its restore
    used to put the exit handler it found back on them for good; it now puts
    back only the handlers it still has in place (here ``SIGINT``).
    """
    with _python_interrupt_handler(), _default_terminations():
        outer = _bounded_run._exit_on_termination(True)
        outer.__enter__()
        hold = _bounded_run._held_signals(terminations=True)
        try:
            hold.__enter__()
            # The error stops the hold's exit before it starts, so only the
            # outer manager leaves now; the hold's generator stays suspended.
            assert not outer.__exit__(SystemExit, SystemExit(143), None)
            assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL
        finally:
            hold.gen.close()
        assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL
        assert signal.getsignal(signal.SIGHUP) is signal.SIG_DFL
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler


def _swap_raising_as_it_begins(
    raising: dict[int, BaseException], calls: list[int]
) -> Callable[..., bool]:
    """Return a stand-in for ``_swap`` that raises as some of its calls begin.

    Call *n* (from 1) raises ``raising[n]`` before it changes anything, as a
    signal's handler that Python runs at the start of the call would. Each
    call adds the number of pairs it was given to *calls*.
    """
    real_swap = _bounded_run._swap

    def swap(
        pairs: Sequence[tuple[int, Any]],
        errors: list[BaseException],
        *,
        saved: list[tuple[int, Any]] | None = None,
        ours: Callable[[object], bool] | None = None,
    ) -> bool:
        calls.append(len(pairs))
        if len(calls) in raising:
            raise raising[len(calls)]
        return real_swap(pairs, errors, saved=saved, ours=ours)

    return swap


@contextlib.contextmanager
def _default_terminations() -> Iterator[None]:
    """Give ``SIGTERM`` and ``SIGHUP`` their default action for the block."""
    # Windows has no SIGHUP.
    names = [name for name in ("SIGTERM", "SIGHUP") if hasattr(signal, name)]
    previous = {
        name: signal.signal(getattr(signal, name), signal.SIG_DFL) for name in names
    }
    try:
        yield
    finally:
        for name, handler in previous.items():
            signal.signal(getattr(signal, name), handler)


@_HANDLER_ERRORS
@pytest.mark.parametrize(
    "hold",
    [
        "held_signals",
        pytest.param(
            "exit_on_termination",
            marks=pytest.mark.skipif(
                sys.platform == "win32", reason="no termination handlers on Windows"
            ),
        ),
    ],
)
def test_a_restore_stopped_as_it_begins_is_made_again(
    monkeypatch: pytest.MonkeyPatch, first_error: BaseException, hold: str
) -> None:
    """The handlers come back even when the call that restores them raises.

    A signal's handler can raise as that call begins, before it changed
    anything; the stand-in raises there. The restore is made again, and the
    error still goes on. A ``TimeoutError`` comes once here, so it does not
    end the tries.
    """
    calls: list[int] = []
    with _python_interrupt_handler(), _default_terminations():
        before = {
            name: signal.getsignal(getattr(signal, name))
            for name in ("SIGINT", "SIGTERM", "SIGHUP")
            if hasattr(signal, name)
        }
        monkeypatch.setattr(
            _bounded_run, "_swap", _swap_raising_as_it_begins({2: first_error}, calls)
        )
        manager = (
            _bounded_run._held_signals()
            if hold == "held_signals"
            else _bounded_run._exit_on_termination(True)
        )
        with pytest.raises(type(first_error)), manager:
            pass
        monkeypatch.undo()
        after = {name: signal.getsignal(getattr(signal, name)) for name in before}
        assert len(calls) == 3, f"the handlers were changed {len(calls)} times"
        assert after == before


# A program that runs the gate's signal hold many times while a real SIGTERM
# lands at a random moment of each run. SIGTERM and SIGHUP start with the
# gate's own exit handler, so the signal never ends the program. It prints, as
# JSON, how many runs left a handler changed and how many the SIGTERM ended.
_HANDLER_RACE_PROGRAM = """\
import json, os, random, signal, sys
from apothem.conformity import _bounded_run

rounds = int(sys.argv[1])
random.seed(1)
signal.signal(signal.SIGINT, signal.default_int_handler)
signal.signal(signal.SIGTERM, _bounded_run._exit_on_signal)
signal.signal(signal.SIGHUP, _bounded_run._exit_on_signal)
wanted = {
    signal.SIGINT: signal.default_int_handler,
    signal.SIGTERM: _bounded_run._exit_on_signal,
    signal.SIGHUP: _bounded_run._exit_on_signal,
}
armed = False

def on_alarm(_signum, _frame):
    if armed:
        os.kill(os.getpid(), signal.SIGTERM)

signal.signal(signal.SIGALRM, on_alarm)
left = ended = 0
for _ in range(rounds):
    armed = True
    try:
        try:
            signal.setitimer(signal.ITIMER_REAL, random.uniform(1e-6, 3e-5))
            with _bounded_run._held_signals(terminations=True):
                pass
            for _ in range(50):
                pass
        except SystemExit:
            ended += 1
        armed = False
        signal.setitimer(signal.ITIMER_REAL, 0)
    except SystemExit:
        ended += 1
    armed = False
    if any(signal.getsignal(s) is not h for s, h in wanted.items()):
        left += 1
        for s, h in wanted.items():
            signal.signal(s, h)
print(json.dumps({"left": left, "ended": ended}))
"""

# Runs of the hold in _HANDLER_RACE_PROGRAM. Before the changes of handlers
# were made atomic (signals blocked during each change, a stopped change made
# again, a stopped restore tried again), about one run in twenty left a
# handler changed in WSL; the runs take about a second in all.
_HANDLER_RACE_ROUNDS = 20000


@_POSIX_ONLY
def test_a_termination_as_the_hold_changes_leaves_no_handler_behind() -> None:
    """A real SIGTERM that lands as a hold is set or removed changes nothing.

    CPython runs a pending signal's handler just before ``signal.signal``
    changes a handler, and as a function begins. A SIGTERM there raised
    ``SystemExit`` halfway through the change: the hold's own handler stayed
    on ``SIGINT`` (every later Ctrl+C was recorded and dropped), or the old
    handler was never saved. Three parts now close that gap together: each
    change runs with the signals blocked, a change a signal stopped is made
    again, and a restore a signal stopped as it began is tried again. This
    end-to-end run does not single out one part (it still passes with the
    blocking alone taken out); each part has a test of its own. The run is a
    process of its own: no other thread can take the signal there.
    """
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}
    run = subprocess.run(
        [sys.executable, "-c", _HANDLER_RACE_PROGRAM, str(_HANDLER_RACE_ROUNDS)],
        env=env,
        capture_output=True,
        check=False,
        timeout=_DEADLINE_SECONDS * 4,
    )
    assert run.returncode == 0, run.stderr.decode("utf-8", "replace")
    counts = json.loads(run.stdout)
    assert counts["ended"] > 0, f"no SIGTERM landed during a run: {counts}"
    assert counts["left"] == 0, f"runs left a handler changed: {counts}"


@_POSIX_ONLY
def test_handlers_change_with_the_signals_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each change of handlers runs with Ctrl+C and the terminations blocked.

    A signal that arrives then waits until every pair is set. The mask is
    read from inside ``signal.signal`` at each change, as a hold is set and
    removed. No other signal is blocked: a caller's handler that runs
    mid-change, and a program it starts, used to find every signal but a
    fault's blocked. The mask is back as it was once the hold ends, and
    those three are not blocked then: a program started later inherits no
    block.
    """
    real_signal = signal.signal
    masks: list[set[int]] = []

    def watching(signum: int, handler: object) -> object:
        masks.append(set(signal.pthread_sigmask(signal.SIG_BLOCK, [])))
        return real_signal(signum, handler)  # type: ignore[arg-type]

    start = _blocked_now()
    try:
        with _python_interrupt_handler(), _default_terminations():
            # Start with the gate's signals unblocked, whatever the worker or
            # an earlier test left, so the checks below read this hold alone.
            _unblock_the_gates_signals()
            before = signal.pthread_sigmask(signal.SIG_BLOCK, [])
            monkeypatch.setattr(_bounded_run, "_SET_HANDLER", watching)
            with _bounded_run._held_signals(terminations=True):
                during = signal.pthread_sigmask(signal.SIG_BLOCK, [])
            monkeypatch.undo()
        after = signal.pthread_sigmask(signal.SIG_BLOCK, [])
    finally:
        _restore_mask(start)
    # Set and put back: SIGINT, SIGTERM and SIGHUP, each twice.
    assert len(masks) == 6, f"signal.signal was called {len(masks)} times"
    held = {signal.SIGINT, signal.SIGTERM, signal.SIGHUP}
    for mask in masks:
        assert held <= mask, f"a change ran with only {sorted(mask)} blocked"
        extra = mask - held - set(before)
        assert not extra, f"a change also blocked {sorted(extra)}"
    assert during == before
    assert after == before
    assert not held & set(during), f"the hold ran with {sorted(during)} blocked"
    assert not held & set(after), f"the hold left {sorted(after)} blocked"


@_POSIX_ONLY
def test_a_ctrl_c_as_the_handlers_come_back_keeps_a_held_termination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A SIGTERM held back still wins over a Ctrl+C that lands in the restore.

    The Ctrl+C lands just after ``SIGINT`` has Python's own handler back.
    Its ``KeyboardInterrupt`` used to skip the raise of the held SIGTERM, so
    a run asked to end reported an interrupt (130) instead of 143.
    """
    real_signal = signal.signal
    injected: list[int] = []

    def ctrl_c_once_restored(signum: int, handler: object) -> object:
        previous = real_signal(signum, handler)  # type: ignore[arg-type]
        if handler is signal.default_int_handler and not injected:
            injected.append(signum)
            signal.raise_signal(signal.SIGINT)
        return previous

    def hold_a_termination() -> None:
        with _bounded_run._held_signals(terminations=True):
            signal.raise_signal(signal.SIGTERM)
            monkeypatch.setattr(_bounded_run, "_SET_HANDLER", ctrl_c_once_restored)

    with _python_interrupt_handler():
        if signal.SIGTERM not in _bounded_run._signals_to_hold(terminations=True):
            pytest.skip("SIGTERM has a handler of its own here, so it is not held")
        # Both caught: a KeyboardInterrupt that wins fails the test below
        # instead of ending the pytest run.
        with pytest.raises((SystemExit, KeyboardInterrupt)) as raised:
            hold_a_termination()
        monkeypatch.undo()
        assert injected, "the Ctrl+C was never sent"
        assert isinstance(raised.value, SystemExit), f"raised {raised.value!r}"
        assert raised.value.code == 128 + signal.SIGTERM
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler


def test_ctrl_c_during_the_stop_keeps_a_termination_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Ctrl+C held while a SIGTERM's stop runs does not turn 143 into 130."""
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    job = _bounded_run._Job()
    real_stop = _bounded_run._stop

    def stop_then_interrupt(*args: object, **kwargs: object) -> None:
        signal.raise_signal(signal.SIGINT)
        real_stop(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(_bounded_run, "_stop", stop_then_interrupt)
    try:
        # Python's own handler: a run that starts with SIGINT ignored would
        # hold nothing, and the second stop would raise nothing.
        with _python_interrupt_handler():
            # Returns quietly: the caller then raises the SystemExit it holds.
            _bounded_run._stop_after_error(process, job, SystemExit(143), group=False)
            assert process.poll() is not None, "the program was not stopped"
            with pytest.raises(KeyboardInterrupt):
                _bounded_run._stop_after_error(
                    process, job, RuntimeError("other"), group=False
                )
    finally:
        job.close()
        with contextlib.suppress(OSError):
            process.kill()
        process.communicate(timeout=_EXIT_WAIT_SECONDS)


def _sleeping_program() -> subprocess.Popen[bytes]:
    """Start a program that sleeps, for a stop to end."""
    return subprocess.Popen(
        [sys.executable, "-c", f"import time; time.sleep({_SLEEP_SECONDS})"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _end_and_reap(process: subprocess.Popen[bytes], job: _bounded_run._Job) -> None:
    """Close *job*, end *process* if it still runs, and reap it."""
    job.close()
    with contextlib.suppress(OSError):
        process.kill()
    process.communicate(timeout=_EXIT_WAIT_SECONDS)


def test_ctrl_c_inside_the_stop_hold_does_not_stop_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Ctrl+C that lands as the held stop begins is held: one stop runs.

    The hold half of the stop after an error. Without it the Ctrl+C would
    raise before the kill, and only a second stop would end the program.
    """
    process = _sleeping_program()
    job = _bounded_run._Job()
    real_stop = _bounded_run._stop
    stops: list[int] = []

    def interrupt_first_stop(
        stopped: subprocess.Popen[bytes], stop_job: _bounded_run._Job, *, group: bool
    ) -> None:
        stops.append(stopped.pid)
        if len(stops) == 1:
            signal.raise_signal(signal.SIGINT)
        real_stop(stopped, stop_job, group=group)

    monkeypatch.setattr(_bounded_run, "_stop", interrupt_first_stop)
    try:
        with _python_interrupt_handler(), pytest.raises(KeyboardInterrupt):
            _bounded_run._stop_after_error(
                process, job, KeyboardInterrupt(), group=False
            )
        assert len(stops) == 1, f"the stop ran {len(stops)} times"
        assert process.poll() is not None, "the program was not stopped"
    finally:
        _end_and_reap(process, job)


def test_ctrl_c_before_the_stop_hold_starts_the_held_stop_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Ctrl+C before the stop's hold is in place cannot skip the stop.

    The other half of the stop after an error. The second Ctrl+C lands before
    the hold is set, and a third as the stop that follows begins. That stop
    used to run without a hold: the third Ctrl+C skipped its kill, and the
    program ran on. The stop now starts over with the hold set again, which
    holds the third.
    """
    process = _sleeping_program()
    job = _bounded_run._Job()
    real_to_hold = _bounded_run._signals_to_hold
    real_stop = _bounded_run._stop
    before_hold: list[bool] = []
    unheld_stops: list[int] = []

    def interrupt_before_first_hold(terminations: bool) -> list[int]:
        if not before_hold:
            before_hold.append(True)
            signal.raise_signal(signal.SIGINT)
        return real_to_hold(terminations)

    def interrupt_unheld_stop(
        stopped: subprocess.Popen[bytes], stop_job: _bounded_run._Job, *, group: bool
    ) -> None:
        if signal.getsignal(signal.SIGINT) is signal.default_int_handler:
            unheld_stops.append(stopped.pid)
            if len(unheld_stops) == 1:
                signal.raise_signal(signal.SIGINT)
        real_stop(stopped, stop_job, group=group)

    monkeypatch.setattr(_bounded_run, "_signals_to_hold", interrupt_before_first_hold)
    monkeypatch.setattr(_bounded_run, "_stop", interrupt_unheld_stop)
    try:
        with _python_interrupt_handler(), pytest.raises(KeyboardInterrupt):
            _bounded_run._stop_after_error(
                process, job, KeyboardInterrupt(), group=False
            )
        assert before_hold, "the Ctrl+C before the hold was never sent"
        assert _ends(process), "the program still runs after three interrupts"
    finally:
        _end_and_reap(process, job)


@_POSIX_ONLY
def test_stop_leaves_the_group_of_a_reaped_program_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stop after the program was reaped sends no signal to its group.

    Once reaped, the program's process ID can name an unrelated process
    group later; the kill went to it all the same.
    """
    process = subprocess.Popen(
        [sys.executable, "-c", "pass"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    process.communicate(timeout=_DEADLINE_SECONDS)
    sent: list[int] = []
    monkeypatch.setattr(
        _bounded_run.os, "killpg", lambda pid, _signum: sent.append(pid)
    )
    _bounded_run._stop(process, _bounded_run._Job(), group=True)
    assert sent == [], "the stop signalled the group of a reaped program"


@pytest.mark.parametrize("unheld_error", ["ctrl-c", "own-error"])
def test_a_stop_whose_every_held_try_fails_still_stops_the_program(
    monkeypatch: pytest.MonkeyPatch, unheld_error: str
) -> None:
    """After every held try failed, the program is stopped without the hold.

    A Ctrl+C lands before the hold at each try. The program used to run on
    after the last one: no stop had run at all. The first stop without the
    hold meets one more Ctrl+C before its kill, or raises an error of its
    own after it; a stop without the hold used to be tried once, and that
    Ctrl+C left the program running. The Ctrl+C still goes on.
    """
    process = _sleeping_program()
    job = _bounded_run._Job()
    real_stop = _bounded_run._stop
    tries: list[bool] = []
    stops: list[int] = []

    def interrupt_every_hold(_terminations: bool) -> list[int]:
        tries.append(True)
        # A thousand at most: a lost bound fails the test, not hangs it.
        if len(tries) < 1000:
            raise KeyboardInterrupt
        return []

    def stop_failing_once(
        stopped: subprocess.Popen[bytes], stop_job: _bounded_run._Job, *, group: bool
    ) -> None:
        stops.append(stopped.pid)
        if len(stops) == 1 and unheld_error == "ctrl-c":
            raise KeyboardInterrupt
        real_stop(stopped, stop_job, group=group)
        if len(stops) == 1:
            raise OSError("the stop's own error")

    monkeypatch.setattr(_bounded_run, "_signals_to_hold", interrupt_every_hold)
    monkeypatch.setattr(_bounded_run, "_stop", stop_failing_once)
    try:
        with pytest.raises(KeyboardInterrupt):
            _bounded_run._stop_after_error(
                process, job, KeyboardInterrupt(), group=False
            )
        assert len(tries) == _bounded_run._TRIES
        assert len(stops) == 2, f"the stop ran {len(stops)} times"
        assert _ends(process), "the program still runs after every try failed"
    finally:
        _end_and_reap(process, job)


class _InterruptingCount:
    """A count of tries whose first comparison raises Ctrl+C.

    It stands in for a signal whose handler Python runs in the stop's loop,
    outside any of the tries' own ``try``. Later comparisons read it as
    :data:`_bounded_run._TRIES`.
    """

    def __init__(self) -> None:
        self.compared = False
        # Read before the stand-in replaces it.
        self.tries = _bounded_run._TRIES

    def __gt__(self, other: int) -> bool:
        if not self.compared:
            self.compared = True
            raise KeyboardInterrupt
        return other < self.tries


def test_a_ctrl_c_in_the_stop_loop_still_stops_the_program(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Ctrl+C outside every held try still leaves the program stopped.

    Python runs a waiting signal's handler after a call returns and on a
    jump back, so a Ctrl+C can raise in the ``except`` that records a try's
    error, or on the way to the next try. The program used to run on: no
    stop had run.
    """
    process = _sleeping_program()
    job = _bounded_run._Job()
    monkeypatch.setattr(_bounded_run, "_TRIES", _InterruptingCount())
    try:
        with pytest.raises(KeyboardInterrupt):
            _bounded_run._stop_after_error(
                process, job, KeyboardInterrupt(), group=False
            )
        assert _ends(process), "the program still runs after the Ctrl+C"
    finally:
        _end_and_reap(process, job)


def test_a_callers_error_during_the_stop_keeps_the_termination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller's own error during the stop does not replace a termination.

    A caller's ``SIGALRM`` handler raising ``TimeoutError`` as the stop
    begins used to go on in place of the ``SIGTERM`` the stop began with,
    so the exit code was 1, not 143. The stop returns and the caller raises
    its termination again.
    """
    process = _sleeping_program()
    job = _bounded_run._Job()
    real_stop = _bounded_run._stop
    calls: list[int] = []

    def stop_then_fail(
        stopped: subprocess.Popen[bytes], stop_job: _bounded_run._Job, *, group: bool
    ) -> None:
        calls.append(stopped.pid)
        real_stop(stopped, stop_job, group=group)
        raise TimeoutError("a caller's alarm")

    monkeypatch.setattr(_bounded_run, "_stop", stop_then_fail)
    try:
        _bounded_run._stop_after_error(process, job, SystemExit(143), group=False)
        assert _ends(process), "the program still runs"
    finally:
        _end_and_reap(process, job)


@pytest.mark.skipif(sys.platform == "win32", reason="no signal mask on Windows")
def test_an_error_as_the_block_takes_hold_still_sets_every_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A handler run as the block takes hold cannot skip the handler changes.

    The C mask call runs a waiting handler after it set the mask. Its error
    used to leave the change before any pair was set, and a termination the
    restore of the mask raised was dropped. The pass is now made again, the
    mask is put back, and the error is kept to go on.
    """
    real_block = _bounded_run._BLOCK_MASK
    assert real_block is not None
    interrupted: list[bool] = []

    def block_then_interrupt(signals: Iterable[int]) -> Iterable[int]:
        before = real_block(signals)
        if signals and not interrupted:
            interrupted.append(True)
            raise KeyboardInterrupt
        return before

    monkeypatch.setattr(_bounded_run, "_BLOCK_MASK", block_then_interrupt)
    old_int = signal.getsignal(signal.SIGINT)
    old_term = signal.getsignal(signal.SIGTERM)

    def mark(_signum: int, _frame: object) -> None:
        return None

    errors: list[BaseException] = []
    start = _blocked_now()
    try:
        with _python_interrupt_handler(), _default_terminations():
            # The gate blocks only what is not blocked yet: start with its
            # signals unblocked, whatever the worker or an earlier test left.
            _unblock_the_gates_signals()
            assert _bounded_run._swap(
                [(signal.SIGINT, mark), (signal.SIGTERM, mark)], errors
            )
            assert interrupted, "the block never raised"
            assert [type(error) for error in errors] == [KeyboardInterrupt]
            assert signal.getsignal(signal.SIGINT) is mark
            assert signal.getsignal(signal.SIGTERM) is mark
            blocked = signal.pthread_sigmask(signal.SIG_BLOCK, [])
            assert _GATES_SIGNALS.isdisjoint(blocked), f"left blocked: {blocked}"
    finally:
        _restore_mask(start)
        errors.clear()
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)


def test_a_termination_before_a_stop_try_wins_over_an_earlier_ctrl_c(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Of the errors the stop's tries met, a termination goes on, not the first.

    A Ctrl+C lands before the first try's hold and a SIGTERM's
    ``SystemExit`` before the second; the third try stops the program. The
    ``SystemExit`` goes on, so the run still ends with 143.
    """
    process = _sleeping_program()
    job = _bounded_run._Job()
    real_to_hold = _bounded_run._signals_to_hold
    early: list[BaseException] = [KeyboardInterrupt(), SystemExit(143)]

    def raise_before_the_hold(terminations: bool) -> list[int]:
        if early:
            raise early.pop(0)
        return real_to_hold(terminations)

    monkeypatch.setattr(_bounded_run, "_signals_to_hold", raise_before_the_hold)
    try:
        # Both caught: a KeyboardInterrupt that wins fails the test below
        # instead of ending the pytest run.
        with (
            _python_interrupt_handler(),
            pytest.raises((SystemExit, KeyboardInterrupt)) as raised,
        ):
            _bounded_run._stop_after_error(
                process, job, RuntimeError("timed out"), group=False
            )
        assert not early, "a try before the hold never ran"
        assert isinstance(raised.value, SystemExit), f"raised {raised.value!r}"
        assert raised.value.code == 143
        assert _ends(process), "the program was not stopped"
    finally:
        _end_and_reap(process, job)


@pytest.mark.parametrize(
    "first_error",
    [KeyboardInterrupt(), ValueError("a caller's own error")],
    ids=["ctrl-c", "value-error"],
)
def test_two_different_errors_in_a_row_still_set_the_pair(
    monkeypatch: pytest.MonkeyPatch, first_error: BaseException
) -> None:
    """The tries of a change end only when an error of a known kind comes back.

    The first try of the change meets *first_error*, the second a caller's
    ``TimeoutError``, a kind ``signal.signal`` also raises when it refuses a
    handler (an ``OSError``). The kinds differ, so the third try is made and
    sets the handler; both errors are kept to go on, the first one first.
    """
    real_signal = signal.signal
    old_term = signal.getsignal(signal.SIGTERM)
    raising = [first_error, TimeoutError("a caller's alarm")]

    def raising_twice(signum: int, handler: object) -> object:
        if raising:
            raise raising.pop(0)
        return real_signal(signum, handler)  # type: ignore[arg-type]

    def wanted(_signum: int, _frame: object) -> None:
        return None

    errors: list[BaseException] = []
    try:
        monkeypatch.setattr(_bounded_run, "_SET_HANDLER", raising_twice)
        assert _bounded_run._swap([(signal.SIGTERM, wanted)], errors)
        monkeypatch.undo()
        assert not raising, "the second error was never raised"
        assert signal.getsignal(signal.SIGTERM) is wanted
        assert [type(error) for error in errors] == [type(first_error), TimeoutError]
        assert errors[0] is first_error
    finally:
        monkeypatch.undo()
        errors.clear()
        real_signal(signal.SIGTERM, old_term)


@pytest.mark.parametrize(
    "hold",
    [
        "held_signals",
        pytest.param(
            "exit_on_termination",
            marks=pytest.mark.skipif(
                sys.platform == "win32", reason="no termination handlers on Windows"
            ),
        ),
    ],
)
def test_two_different_refusal_kinds_in_a_row_still_restore(
    monkeypatch: pytest.MonkeyPatch, hold: str
) -> None:
    """A restore stops trying only when an error of a known kind comes back.

    A ``ValueError`` stops the restore as it begins, then a caller's
    ``TimeoutError``. ``signal.signal`` raises both kinds when it refuses a
    handler, but they differ, so the restore is tried a third time and the
    handlers come back; the first error goes on.
    """
    calls: list[int] = []
    raising: dict[int, BaseException] = {
        2: ValueError("a caller's own error"),
        3: TimeoutError("a caller's alarm"),
    }
    with _python_interrupt_handler(), _default_terminations():
        before = {
            name: signal.getsignal(getattr(signal, name))
            for name in ("SIGINT", "SIGTERM", "SIGHUP")
            if hasattr(signal, name)
        }
        monkeypatch.setattr(
            _bounded_run, "_swap", _swap_raising_as_it_begins(raising, calls)
        )
        manager = (
            _bounded_run._held_signals()
            if hold == "held_signals"
            else _bounded_run._exit_on_termination(True)
        )
        with pytest.raises(ValueError, match="own error"), manager:
            pass
        monkeypatch.undo()
        after = {name: signal.getsignal(getattr(signal, name)) for name in before}
        # The change, then three restore calls: this needs _TRIES >= 3, or
        # the third restore would be the last try instead.
        assert _bounded_run._TRIES >= 3
        assert len(calls) == 1 + 3, f"the handlers were changed {len(calls)} times"
        assert after == before


@_POSIX_ONLY
def test_a_held_termination_wins_over_one_that_lands_in_the_restore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A SIGTERM held during the block goes on over a SIGHUP in the restore.

    The SIGHUP's ``SystemExit`` stops the restore as it begins. The held
    SIGTERM came first, so its exit code, 143, is the one that goes on,
    not 129.
    """
    calls: list[int] = []
    hangup = {2: SystemExit(128 + signal.SIGHUP)}
    with _python_interrupt_handler(), _default_terminations():
        monkeypatch.setattr(
            _bounded_run, "_swap", _swap_raising_as_it_begins(hangup, calls)
        )
        with (
            pytest.raises(SystemExit) as raised,
            _bounded_run._held_signals(terminations=True),
        ):
            signal.raise_signal(signal.SIGTERM)
        monkeypatch.undo()
        assert raised.value.code == 128 + signal.SIGTERM
        assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL
        assert signal.getsignal(signal.SIGHUP) is signal.SIG_DFL
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler


def test_an_error_before_popen_sets_its_process_id_goes_on_as_itself() -> None:
    """An error raised in Popen's first lines is not turned into another one.

    Popen sets ``pid`` and ``returncode`` only once its start is under way.
    An interrupt before then left a Popen without them in the traceback, and
    the stop that looks for the started program raised ``AttributeError``
    in place of the interrupt.
    """
    unstarted = _bounded_run._POPEN.__new__(_bounded_run._POPEN)
    # Read by Popen's __del__; Popen's own first lines set it.
    unstarted.__dict__["_child_created"] = False

    def popen_first_lines(self: object) -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt) as raised:
        popen_first_lines(unstarted)
    job = _bounded_run._Job()
    try:
        # Returns: nothing was started, and no error of its own goes on.
        _bounded_run._stop_unreturned(raised.value, job, group=False)
    finally:
        job.close()


@pytest.mark.parametrize("where", ["in-the-stop", "as-the-hold-is-set"])
def test_a_ctrl_c_held_during_the_stop_leaves_no_cycle_holding_the_program(
    monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    """The errors the stop met do not keep the program's Popen in a cycle.

    Each list of errors is emptied once its error goes on, as their
    tracebacks hold the frame that lists them. A list left as it was kept
    the stop's frame, and the Popen in it, alive until the next garbage
    collection; the collector is off here, so only a cycle keeps it. The
    Ctrl+C lands during the held stop, or as the stop's hold is set, where
    the change of handlers keeps it before the hold raises it.
    """
    process = _sleeping_program()
    job = _bounded_run._Job()
    real_stop = _bounded_run._stop
    real_signal = signal.signal
    interrupted_hold: list[bool] = []

    def interrupt_the_stop(
        stopped: subprocess.Popen[bytes], stop_job: _bounded_run._Job, *, group: bool
    ) -> None:
        signal.raise_signal(signal.SIGINT)
        real_stop(stopped, stop_job, group=group)

    def interrupt_the_hold(signum: int, handler: object) -> object:
        if isinstance(handler, _bounded_run._Recorder) and not interrupted_hold:
            interrupted_hold.append(True)
            signal.raise_signal(signal.SIGINT)
        return real_signal(signum, handler)  # type: ignore[arg-type]

    if where == "in-the-stop":
        monkeypatch.setattr(_bounded_run, "_stop", interrupt_the_stop)
    else:
        monkeypatch.setattr(_bounded_run, "_SET_HANDLER", interrupt_the_hold)
    collecting = gc.isenabled()
    gc.disable()
    try:
        interrupted = False
        with _python_interrupt_handler():
            try:
                _bounded_run._stop_after_error(
                    process, job, KeyboardInterrupt(), group=False
                )
            except KeyboardInterrupt:
                interrupted = True
        monkeypatch.undo()
        _end_and_reap(process, job)
        program = weakref.ref(process)
        del process
        assert interrupted, "the held Ctrl+C did not go on"
        assert interrupted_hold or where == "in-the-stop", "the hold was not set"
        assert program() is None, "a reference cycle still holds the program"
    finally:
        if collecting:
            gc.enable()


@pytest.mark.parametrize(
    "new_session",
    [
        False,
        True,
        pytest.param(None, marks=_WINDOWS_ONLY, id="windows-without-a-job"),
    ],
)
def test_a_ctrl_c_as_the_stop_begins_still_stops_the_program(
    monkeypatch: pytest.MonkeyPatch, new_session: bool | None
) -> None:
    """A second Ctrl+C that lands as the stop's call begins does not skip it.

    Python runs a waiting signal's handler as a function begins, before its
    first line, so a Ctrl+C there skipped every try of the stop, and the
    program ran on (outside Windows in a session of its own with
    *new_session*). A trace function raises the Ctrl+C at that point here;
    run_bounded now stops the program itself.
    """
    if new_session is None:
        monkeypatch.setattr(_bounded_run, "_new_job", lambda: None)
    started: list[subprocess.Popen[bytes]] = []
    monkeypatch.setattr(
        _bounded_run.subprocess, "Popen", _popen_interrupted_in_its_wait(started)
    )
    code = _bounded_run._stop_after_error.__code__
    fired: list[bool] = []

    def trace_call(frame: FrameType, event: str, _arg: object) -> None:
        if event == "call" and frame.f_code is code and not fired:
            fired.append(True)
            raise KeyboardInterrupt

    program_gone = False
    previous = sys.gettrace()
    try:
        with _python_interrupt_handler():
            sys.settrace(trace_call)
            try:
                with pytest.raises(KeyboardInterrupt):
                    _bounded_run.run_bounded(
                        [
                            sys.executable,
                            "-c",
                            f"import time; time.sleep({_SLEEP_SECONDS})",
                        ],
                        timeout=_SLEEP_SECONDS,
                        new_session=bool(new_session),
                    )
            finally:
                sys.settrace(previous)
        assert fired, "the Ctrl+C at the stop's start was never raised"
        assert len(started) == 1, started
        program_gone = _ends(started[0])
        assert program_gone, "the program still runs after the second interrupt"
    finally:
        for process in started:
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                process.kill()
                process.communicate(timeout=_EXIT_WAIT_SECONDS)


@pytest.mark.parametrize(
    "hold",
    [
        "held_signals",
        pytest.param(
            "exit_on_termination",
            marks=pytest.mark.skipif(
                sys.platform == "win32", reason="no termination handlers on Windows"
            ),
        ),
    ],
)
def test_a_ctrl_c_in_the_restore_keeps_the_termination_on_its_way_out(
    monkeypatch: pytest.MonkeyPatch, hold: str
) -> None:
    """A Ctrl+C that lands as the handlers come back does not replace a SIGTERM.

    The block ends with the ``SystemExit`` of a termination, and a Ctrl+C
    stops the restore of a handler once. Only the errors met on the way were
    ranked, so the Ctrl+C went on in place of the termination: exit 130,
    not 143. The error already on its way out is ranked with them now.
    """
    real_signal = signal.signal
    restored = signal.default_int_handler if hold == "held_signals" else signal.SIG_DFL
    interrupted: list[bool] = []

    def ctrl_c_as_the_restore_begins(signum: int, handler: object) -> object:
        # ==, not is: the gate hands the C call SIG_DFL as a plain 0.
        if handler == restored and not interrupted:
            interrupted.append(True)
            raise KeyboardInterrupt
        return real_signal(signum, handler)  # type: ignore[arg-type]

    with _python_interrupt_handler(), _default_terminations():
        before = {
            name: signal.getsignal(getattr(signal, name))
            for name in ("SIGINT", "SIGTERM", "SIGHUP")
            if hasattr(signal, name)
        }
        manager = (
            _bounded_run._held_signals()
            if hold == "held_signals"
            else _bounded_run._exit_on_termination(True)
        )

        def end_with_a_termination() -> None:
            with manager:
                monkeypatch.setattr(
                    _bounded_run, "_SET_HANDLER", ctrl_c_as_the_restore_begins
                )
                raise SystemExit(143)

        # Both caught: a KeyboardInterrupt that wins fails the test below
        # instead of ending the pytest run.
        with pytest.raises((SystemExit, KeyboardInterrupt)) as raised:
            end_with_a_termination()
        monkeypatch.undo()
        after = {name: signal.getsignal(getattr(signal, name)) for name in before}
    assert interrupted, "the Ctrl+C was never raised"
    assert isinstance(raised.value, SystemExit), f"raised {raised.value!r}"
    assert raised.value.code == 143
    assert after == before


@_POSIX_ONLY
def test_a_termination_handler_set_during_the_run_stays() -> None:
    """A ``SIGTERM`` handler the caller sets while the block runs is kept.

    The block's end used to put the default action back over it, so a later
    ``SIGTERM`` ended the process without the caller's clean-up.
    """

    def own_handler(_signum: int, _frame: FrameType | None) -> None:
        """Stand in for a handler the caller installs."""

    with _default_terminations():
        with _bounded_run._exit_on_termination(True):
            assert signal.getsignal(signal.SIGTERM) is _bounded_run._exit_on_signal
            signal.signal(signal.SIGTERM, own_handler)
        assert signal.getsignal(signal.SIGTERM) is own_handler
        assert signal.getsignal(signal.SIGHUP) is signal.SIG_DFL


@_POSIX_ONLY
def test_a_mask_change_made_during_a_change_of_handlers_stays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A signal block that a handler adds while the handlers change is kept.

    A handler that runs mid-change (a caller's ``SIGALRM`` handler, say) can
    block a signal itself. The change used to end by setting the whole mask
    back as it found it, which undid that block; it now unblocks only the
    signals it blocked. ``SIGHUP``, one of the three a change blocks, was
    blocked by the caller before: it stays blocked too.
    """
    real_signal = signal.signal
    added: list[bool] = []

    def block_usr1_first(signum: int, handler: object) -> object:
        if not added:
            added.append(True)
            signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
        return real_signal(signum, handler)  # type: ignore[arg-type]

    ours = {signal.SIGUSR1, signal.SIGHUP}
    before = signal.pthread_sigmask(signal.SIG_BLOCK, [])
    if ours & set(before):
        pytest.skip("SIGUSR1 or SIGHUP is blocked already")
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGHUP})
    try:
        with _python_interrupt_handler():
            monkeypatch.setattr(_bounded_run, "_SET_HANDLER", block_usr1_first)
            with _bounded_run._held_signals():
                pass
            monkeypatch.undo()
        after = signal.pthread_sigmask(signal.SIG_BLOCK, [])
        assert added, "the stand-in never ran"
        assert set(after) == set(before) | ours
    finally:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, ours)
