# SPDX-License-Identifier: MIT

"""Run a program with a time limit that holds for every program it starts.

Why this module exists. The conformity gate runs each standalone validator as a
program of its own, and several validators run git in the project they check.
That project can arrive with its ``.git`` folder from someone else, and its own
configuration can make git wait for ever, for example through an
``include.path`` that names a FIFO or a Windows named pipe.
:func:`subprocess.run` with a ``timeout`` stops only the program it started. On
Windows it then waits, with no limit, until every program that still holds the
output open has ended. Git for Windows puts a launcher on ``PATH``
(``Git\\cmd\\git.exe``) that starts the real git, and that real git holds the
output after the launcher is stopped, so a limit could last as long as the
stall.

:func:`run_bounded` keeps the limit for the whole tree of programs:

- on Windows the program starts in a job object that ends every program in it
  when the job is closed, so a stop, or the end of this process, also ends every
  program it started;
- elsewhere, ``new_session=True`` starts the program in a session and process
  group of its own, and a stop ends the whole group. While it waits, a
  ``SIGTERM`` or ``SIGHUP`` to this process stops that group first and then
  exits, because a signal sent to this process's own group no longer reaches a
  program in another session. A ``SIGKILL``, which no handler sees, or another
  signal ends this process alone: the program runs on until it finishes, and
  the time limits of its own work (a validator's git limits) still end any
  wait;
- after a stop it waits at most :data:`STOP_GRACE_SECONDS` for the output to
  close, then leaves it open: a program that escaped the stop can hold it, and
  closing a pipe that a reader thread is blocked on would wait as well.

Without ``new_session`` the program stays in this process's group outside
Windows, so a signal or a stop aimed at that group reaches it too; that is how a
validator runs git under the gate. Every git command goes through
:func:`~apothem.conformity._git.run_git`, which runs it here; the gate runs
each standalone validator here too. This module is the one place in the
package that starts a program.

The module uses the standard library only, so it runs from a harness install as
well as from the package.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from types import FrameType
from typing import Any, Final

# Seconds to wait, after a stop, for the stopped program's output to close.
STOP_GRACE_SECONDS: Final[float] = 5.0

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    # A private handle on kernel32, so these argument types never clash with
    # another library's use of ctypes.windll.
    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: Final[int] = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: Final[int] = 0x2000
    _PROCESS_TERMINATE: Final[int] = 0x0001
    _PROCESS_SET_QUOTA: Final[int] = 0x0100

    class _BasicLimits(ctypes.Structure):
        """JOBOBJECT_BASIC_LIMIT_INFORMATION."""

        _fields_ = (
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        )

    class _IoCounters(ctypes.Structure):
        """IO_COUNTERS."""

        _fields_ = (
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        )

    class _ExtendedLimits(ctypes.Structure):
        """JOBOBJECT_EXTENDED_LIMIT_INFORMATION."""

        _fields_ = (
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        )

    _CreateJobObjectW = _KERNEL32.CreateJobObjectW
    _CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    _CreateJobObjectW.restype = wintypes.HANDLE
    _SetInformationJobObject = _KERNEL32.SetInformationJobObject
    _SetInformationJobObject.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    )
    _SetInformationJobObject.restype = wintypes.BOOL
    _AssignProcessToJobObject = _KERNEL32.AssignProcessToJobObject
    _AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    _AssignProcessToJobObject.restype = wintypes.BOOL
    _TerminateJobObject = _KERNEL32.TerminateJobObject
    _TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    _TerminateJobObject.restype = wintypes.BOOL
    _OpenProcess = _KERNEL32.OpenProcess
    _OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _OpenProcess.restype = wintypes.HANDLE
    _CloseHandle = _KERNEL32.CloseHandle
    _CloseHandle.argtypes = (wintypes.HANDLE,)
    _CloseHandle.restype = wintypes.BOOL

    def _new_job() -> int | None:
        """Return a job object that ends its programs when closed, or None."""
        job = _CreateJobObjectW(None, None)
        if not job:
            return None
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _SetInformationJobObject(
            job,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            _CloseHandle(job)
            return None
        return int(job)

    def _add_to_job(job: int, pid: int) -> bool:
        """Put process *pid* in *job*; its later child processes join it too."""
        process = _OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid)
        if not process:
            return False
        try:
            return bool(_AssignProcessToJobObject(job, process))
        finally:
            _CloseHandle(process)


class _Job:
    """A Windows job object that ends every program in it once it is closed.

    Elsewhere, and when Windows refuses a job (a sandbox that forbids one), it
    does nothing, and a stop reaches only the program itself. The program is
    added right after it starts; a process it starts before that moment stays
    outside the job, which the bounded wait after a stop still covers.
    """

    def __init__(self) -> None:
        self._handle: int | None = None
        self._holds_program = False
        if sys.platform == "win32":
            self._handle = _new_job()

    def add(self, pid: int) -> None:
        """Put the program with process ID *pid* in the job."""
        if sys.platform == "win32" and self._handle is not None:
            self._holds_program = _add_to_job(self._handle, pid)

    def terminate(self) -> None:
        """End every program in the job."""
        if sys.platform == "win32" and self._handle is not None and self._holds_program:
            _TerminateJobObject(self._handle, 1)

    def close(self) -> None:
        """Close the job, which ends any program still in it."""
        handle, self._handle = self._handle, None
        if sys.platform == "win32" and handle is not None:
            _CloseHandle(handle)


def _exit_on_signal(signum: int, _frame: FrameType | None) -> None:
    """Turn a termination signal into an exit, so clean-up code runs first."""
    raise SystemExit(128 + signum)


@contextlib.contextmanager
def _exit_on_termination(enabled: bool) -> Iterator[None]:
    """While the block runs, turn ``SIGTERM`` and ``SIGHUP`` into ``SystemExit``.

    Only outside Windows, only on the main thread (the only one that may set a
    signal handler), and only for a signal that still has its default action:
    a handler the caller installed, or an ignored ``SIGHUP`` under ``nohup``,
    stays as it is. The previous handlers come back when the block ends.
    """
    if sys.platform == "win32":
        yield
    else:
        changed: list[tuple[signal.Signals, Any]] = []
        if enabled and threading.current_thread() is threading.main_thread():
            for signum in (signal.SIGTERM, signal.SIGHUP):
                if signal.getsignal(signum) is signal.SIG_DFL:
                    changed.append((signum, signal.signal(signum, _exit_on_signal)))
        try:
            yield
        finally:
            for signum, previous in changed:
                signal.signal(signum, previous)


def _stop(process: subprocess.Popen[str], job: _Job, *, group: bool) -> None:
    """Stop *process* and every program it started that the platform can reach."""
    job.terminate()
    if sys.platform != "win32":
        if group:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(process.pid, signal.SIGKILL)
    with contextlib.suppress(OSError):
        process.kill()


def run_bounded(
    argv: Sequence[str],
    *,
    timeout: float | None,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = False,
    new_session: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run *argv*, capture its output, and keep *timeout* for its whole tree.

    Pre-conditions: *argv* is a program and its arguments (never run through a
    shell); *timeout* is in seconds, or None for no limit.
    Post-conditions: standard input is the null device and the output is
    decoded as UTF-8, with a byte that is not UTF-8 read as U+FFFD. Returns the
    completed process, and with *check* raises
    :class:`subprocess.CalledProcessError` on a non-zero exit. Past *timeout*
    the program and every program it started that the platform can reach are
    stopped (see the module docstring), the output is awaited for at most
    :data:`STOP_GRACE_SECONDS`, and :class:`subprocess.TimeoutExpired` is
    raised. An interrupt, such as Ctrl+C, stops them the same way before it
    goes on. A program that cannot be started raises :class:`OSError`.
    """
    command = list(argv)
    job = _Job()
    try:
        process = subprocess.Popen(  # noqa: S603 — argv list from the caller, never a shell
            command,
            cwd=None if cwd is None else str(cwd),
            env=None if env is None else dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            start_new_session=new_session and sys.platform != "win32",
        )
    except BaseException:
        job.close()
        raise
    try:
        job.add(process.pid)
        with _exit_on_termination(new_session):
            stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _stop(process, job, group=new_session)
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.communicate(timeout=STOP_GRACE_SECONDS)
        raise
    except BaseException:
        _stop(process, job, group=new_session)
        raise
    finally:
        job.close()
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if check:
        completed.check_returncode()
    return completed
