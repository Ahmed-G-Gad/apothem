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

- on Windows, whenever Windows grants a job object, the program starts
  suspended, is added to the job, and only then is resumed. The job ends every
  program in it when it is closed, so a stop, or the end of this process, also
  ends every program it started, even one it starts at once (the launcher's
  real git). When the add fails the program is still resumed, but it runs
  outside the job. Without a job, or outside it, a stop reaches only the
  program itself;
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

The output is captured as bytes and decoded here, in one of two ways. By
default it reads as text: UTF-8, a byte that is not UTF-8 as U+FFFD, and every
line ending as ``\\n``. With ``file_names=True`` it reads as a list of file
names (git's ``-z`` lists): nothing is translated, and a byte that does not
decode comes back as a surrogate escape, so each name encodes back to the
bytes the program wrote. Text decoding would turn a carriage return in a name
into a line feed and an undecodable byte into U+FFFD, and the name would then
match no file.

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

# The Windows process creation flag that starts a program with its main thread
# suspended.
_CREATE_SUSPENDED: Final[int] = 0x00000004

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

    _TH32CS_SNAPTHREAD: Final[int] = 0x00000004
    _THREAD_SUSPEND_RESUME: Final[int] = 0x0002
    # What ResumeThread returns when it fails: (DWORD)-1.
    _RESUME_FAILED: Final[int] = 0xFFFFFFFF
    # What CreateToolhelp32Snapshot returns when it fails.
    _INVALID_HANDLE_VALUE: Final[int | None] = ctypes.c_void_p(-1).value

    class _ThreadEntry(ctypes.Structure):
        """THREADENTRY32."""

        _fields_ = (
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        )

    # The entry size Windows must fill for the owner's process ID to be valid.
    _OWNER_FIELD_END: Final[int] = _ThreadEntry.th32OwnerProcessID.offset + (
        ctypes.sizeof(wintypes.DWORD)
    )

    _CreateToolhelp32Snapshot = _KERNEL32.CreateToolhelp32Snapshot
    _CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    _CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _Thread32First = _KERNEL32.Thread32First
    _Thread32First.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ThreadEntry))
    _Thread32First.restype = wintypes.BOOL
    _Thread32Next = _KERNEL32.Thread32Next
    _Thread32Next.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ThreadEntry))
    _Thread32Next.restype = wintypes.BOOL
    _OpenThread = _KERNEL32.OpenThread
    _OpenThread.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _OpenThread.restype = wintypes.HANDLE
    _ResumeThread = _KERNEL32.ResumeThread
    _ResumeThread.argtypes = (wintypes.HANDLE,)
    _ResumeThread.restype = wintypes.DWORD

    # ntdll's NtResumeProcess lets every thread of a process run in one call.
    # It is not documented, but it has been stable for many Windows versions
    # and psutil relies on it. When it is missing or fails, the program is
    # resumed through a thread snapshot instead, which is much slower: the
    # snapshot holds every thread on the machine. A private handle again, and
    # None when this Windows has no such function.
    _NTDLL = ctypes.WinDLL("ntdll")
    _NT_RESUME_PROCESS: Any = getattr(_NTDLL, "NtResumeProcess", None)
    if _NT_RESUME_PROCESS is not None:
        _NT_RESUME_PROCESS.argtypes = (wintypes.HANDLE,)
        # An NTSTATUS: zero or more is a success.
        _NT_RESUME_PROCESS.restype = wintypes.LONG

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

    def _thread_ids(pid: int) -> list[int]:
        """Return the IDs of the threads of process *pid*, or [] on a failure."""
        snapshot = _CreateToolhelp32Snapshot(_TH32CS_SNAPTHREAD, 0)
        if not snapshot or snapshot == _INVALID_HANDLE_VALUE:
            return []
        found: list[int] = []
        try:
            entry = _ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            more = _Thread32First(snapshot, ctypes.byref(entry))
            while more:
                if entry.dwSize >= _OWNER_FIELD_END and entry.th32OwnerProcessID == pid:
                    found.append(int(entry.th32ThreadID))
                entry.dwSize = ctypes.sizeof(entry)
                more = _Thread32Next(snapshot, ctypes.byref(entry))
        finally:
            _CloseHandle(snapshot)
        return found

    def _resume_process(handle: int | None, pid: int) -> bool:
        """Let process *pid*, started suspended, run; return False on a failure.

        *handle* is the process handle that started it, or None when it is not
        known. NtResumeProcess on that handle comes first; the thread snapshot
        is the fallback.
        """
        if (
            handle is not None
            and _NT_RESUME_PROCESS is not None
            and int(_NT_RESUME_PROCESS(handle)) >= 0
        ):
            return True
        return _resume_threads(pid)

    def _resume_threads(pid: int) -> bool:
        """Let process *pid*, started suspended, run; return False on a failure."""
        threads = _thread_ids(pid)
        if not threads:
            return False
        for thread_id in threads:
            thread = _OpenThread(_THREAD_SUSPEND_RESUME, False, thread_id)
            if not thread:
                return False
            try:
                if _ResumeThread(thread) == _RESUME_FAILED:
                    return False
            finally:
                _CloseHandle(thread)
        return True


class _Job:
    """A Windows job object that ends every program in it once it is closed.

    Elsewhere, and when Windows refuses a job (a sandbox that forbids one), it
    does nothing, and a stop reaches only the program itself. When the job
    exists the program starts suspended (:attr:`suspends`), is added, and only
    then runs, so every process it starts is in the job as well. When Windows
    refuses to add it, it still runs, and a stop reaches only the program.
    """

    def __init__(self) -> None:
        self._handle: int | None = None
        self._holds_program = False
        if sys.platform == "win32":
            self._handle = _new_job()

    @property
    def suspends(self) -> bool:
        """True when the program should start suspended and wait for the job."""
        return sys.platform == "win32" and self._handle is not None

    def add(self, pid: int) -> None:
        """Put the program with process ID *pid* in the job."""
        if sys.platform == "win32" and self._handle is not None:
            self._holds_program = _add_to_job(self._handle, pid)

    def resume(self, process: subprocess.Popen[bytes]) -> bool:
        """Let the suspended *process* run; return False if it cannot."""
        if sys.platform == "win32" and self._handle is not None:
            # Popen keeps the process handle in a private attribute.
            handle = getattr(process, "_handle", None)
            return _resume_process(None if handle is None else int(handle), process.pid)
        return True

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


# The encoding of a file name in a program's output. Outside Windows a name is
# the bytes the file system holds, which Python reads with the file-system
# encoding; Git for Windows writes names as UTF-8 whatever the code page.
_NAME_ENCODING: Final[str] = (
    "utf-8" if sys.platform == "win32" else sys.getfilesystemencoding()
)


def decode_output(data: bytes, *, file_names: bool = False) -> str:
    """Return a program's captured output as a string.

    By default the output is text: UTF-8, with a byte that is not UTF-8 read
    as U+FFFD, and ``\\r\\n`` or a lone ``\\r`` read as ``\\n`` (what
    :mod:`subprocess` does in text mode). With *file_names* the output is a
    list of file names: no character is translated, and a byte that does not
    decode becomes a surrogate escape (``errors="surrogateescape"``), so every
    name encodes back to the bytes the program wrote. Outside Windows that is
    how Python itself reads a file name, so such a name opens the file and
    reaches a program unchanged as an argument.
    """
    if file_names:
        return data.decode(_NAME_ENCODING, "surrogateescape")
    return data.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")


def _stop(process: subprocess.Popen[bytes], job: _Job, *, group: bool) -> None:
    """Stop *process* and every program it started that the platform can reach."""
    job.terminate()
    if sys.platform != "win32":
        if group:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(process.pid, signal.SIGKILL)
    with contextlib.suppress(OSError):
        process.kill()


def _let_run(process: subprocess.Popen[bytes], job: _Job, program: str) -> None:
    """Let *process*, started suspended, run, or stop it and raise OSError.

    A program that cannot be resumed would wait out the whole time limit, so
    it is stopped at once, its output is awaited for at most
    :data:`STOP_GRACE_SECONDS`, and the start counts as failed.
    """
    if job.resume(process):
        return
    job.terminate()
    with contextlib.suppress(OSError):
        process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.communicate(timeout=STOP_GRACE_SECONDS)
    raise OSError(f"could not resume {program!r} after it joined the job object")


def run_bounded(
    argv: Sequence[str],
    *,
    timeout: float | None,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = False,
    new_session: bool = False,
    file_names: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run *argv*, capture its output, and keep *timeout* for its whole tree.

    Pre-conditions: *argv* is a program and its arguments (never run through a
    shell); *timeout* is in seconds, or None for no limit.
    Post-conditions: standard input is the null device and the output is
    decoded by :func:`decode_output`: as text by default (UTF-8, a byte that
    is not UTF-8 read as U+FFFD, line endings as ``\\n``), or, with
    *file_names*, standard output as file names that keep every byte. The
    error output is always text. Returns the completed process, and with
    *check* raises
    :class:`subprocess.CalledProcessError` on a non-zero exit. Past *timeout*
    the program and every program it started that the platform can reach are
    stopped (see the module docstring), the output is awaited for at most
    :data:`STOP_GRACE_SECONDS`, and :class:`subprocess.TimeoutExpired` is
    raised. An interrupt, such as Ctrl+C, that arrives once Popen has
    returned stops them the same way before it goes on. An interrupt inside
    Popen itself, after Windows created the program but before Popen returns,
    can leave the program suspended; that window is microseconds wide. A
    program that cannot be started raises :class:`OSError`. On
    Windows a program that started suspended and cannot be resumed is stopped
    and raises :class:`OSError` too, so a caller sees it as a program that
    could not be started.
    """
    command = list(argv)
    job = _Job()
    suspended = job.suspends
    process: subprocess.Popen[bytes] | None = None
    # One try covers everything from the moment Popen returns, so an interrupt
    # at any point after the start (even before the program is added or
    # resumed) stops the program instead of leaving it suspended.
    try:
        process = subprocess.Popen(  # noqa: S603 — argv list from the caller, never a shell
            command,
            cwd=None if cwd is None else str(cwd),
            env=None if env is None else dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=new_session and sys.platform != "win32",
            creationflags=_CREATE_SUSPENDED if suspended else 0,
        )
        job.add(process.pid)
        if suspended:
            _let_run(process, job, command[0])
        with _exit_on_termination(new_session):
            stdout, stderr = process.communicate(timeout=timeout)
    except BaseException as error:
        # process is None only when Popen itself failed: nothing started.
        if process is not None:
            _stop(process, job, group=new_session)
            if isinstance(error, subprocess.TimeoutExpired):
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.communicate(timeout=STOP_GRACE_SECONDS)
        raise
    finally:
        job.close()
    completed = subprocess.CompletedProcess(
        command,
        process.returncode,
        decode_output(stdout, file_names=file_names),
        decode_output(stderr),
    )
    if check:
        completed.check_returncode()
    return completed
