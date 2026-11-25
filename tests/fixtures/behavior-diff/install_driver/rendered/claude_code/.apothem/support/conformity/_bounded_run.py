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
  group of its own, and a stop ends the whole group. From the start (held back
  until the program exists) to the end of the wait, a ``SIGTERM`` or
  ``SIGHUP`` to this process stops that group first and then exits, because a
  signal sent to this process's own group no longer reaches a program in
  another session. A ``SIGKILL``, which no handler sees, or another
  signal ends this process alone: the program runs on until it finishes, and
  the time limits of its own work (a validator's git limits) still end any
  wait;
- after a stop it waits up to half a second for the program to end, then at
  most :data:`STOP_GRACE_SECONDS` for the output to close, then leaves it
  open: a program that escaped the stop can hold it, and
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
import functools
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from types import FrameType
from typing import Any, Final, NoReturn

# Seconds to wait, after a stop, for the stopped program's output to close.
STOP_GRACE_SECONDS: Final[float] = 5.0

# The Windows process creation flag that starts a program with its main thread
# suspended.
_CREATE_SUSPENDED: Final[int] = 0x00000004

# The Popen class, kept at import: a test may put a function in its place.
_POPEN: Final[type[subprocess.Popen[Any]]] = subprocess.Popen

# Seconds to wait, after a failed resume, for a program that is already ending
# to finish. Windows ends a process a moment after it is told to.
_ENDING_WAIT_SECONDS: Final[float] = 0.5

# Seconds from just before the resume to just after the exit-code read that
# follows it, within which an exit code means a kill before the resume. The
# resume and the read take about 25 microseconds (55 at most, measured on
# Windows Server 2025). The smallest program Windows can run, with no imports
# and an entry point that returns at once, lives 3.2 ms at least past its
# resume there; ``cmd /c exit`` lives 9 ms, ``git --version`` 27 ms and
# ``python -c pass`` 40 ms. A read later than this is ambiguous, for example
# when other Python threads hold the GIL: the program may have run and ended.
_NEVER_RAN_WINDOW_SECONDS: Final[float] = 0.001

# How many times the stop after an error is tried. A try fails only when a
# signal raises in the few microseconds before its hold is in place, so a
# second try almost never fails; the bound keeps an error that recurs at every
# try from looping for ever. After the last failed try, one more stop runs
# without the hold.
_STOP_ATTEMPTS: Final[int] = 10


class ProgramResumeError(OSError):
    """A program that started suspended could not be let run, and was stopped.

    It is an :class:`OSError`, as a failed start is, but a caller that reads
    an OSError as "the program is missing" can tell this case apart: the
    program was there and started.
    """


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
    _GetExitCodeProcess = _KERNEL32.GetExitCodeProcess
    _GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    _GetExitCodeProcess.restype = wintypes.BOOL
    # The exit code GetExitCodeProcess gives for a process not told to end.
    _STILL_ACTIVE: Final[int] = 259
    _WaitForSingleObject = _KERNEL32.WaitForSingleObject
    _WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    _WaitForSingleObject.restype = wintypes.DWORD
    # What WaitForSingleObject returns for a process that has ended.
    _WAIT_OBJECT_0: Final[int] = 0

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
    # The NTSTATUS NtResumeProcess returns for a process that is ending.
    _STATUS_PROCESS_IS_TERMINATING: Final[int] = 0xC000010A

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

    def _told_to_end(handle: int) -> bool:
        """Return True when the process behind *handle* was told to end.

        Windows sets the exit code as soon as a process is told to end, while
        its threads still wind down. A suspended process cannot end by
        itself, so before the resume this means something else ended it.
        When the exit code cannot be read, the answer is False.

        An exit code of 259 is also what a running process reads as. Such a
        process counts as told to end once it has ended, when its handle is
        signalled; while it still winds down it reads as running.
        """
        code = wintypes.DWORD()
        if not _GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        if int(code.value) != _STILL_ACTIVE:
            return True
        return int(_WaitForSingleObject(handle, 0)) == _WAIT_OBJECT_0

    def _ended_at_once(handle: int, begun: float) -> bool:
        """Return True when the process just resumed was told to end before.

        *begun* is the :func:`time.perf_counter` value taken just before the
        resume. A kill between the first read and the resume leaves an exit
        code that the read after the resume sees. A program that ran can have
        one too, when this thread was slow to read (it waits for the GIL
        while other Python threads run). So the exit code counts only when the
        read came within :data:`_NEVER_RAN_WINDOW_SECONDS` of the resume, too
        soon for any program to run and end; later, the program's own result
        stands.
        """
        ended = _told_to_end(handle)
        return ended and time.perf_counter() - begun < _NEVER_RAN_WINDOW_SECONDS

    def _resume_process(handle: int | None, pid: int) -> bool:
        """Let process *pid*, started suspended, run; return False on a failure.

        *handle* is the process handle that started it, or None when it is not
        known. A process already told to end is not resumed: NtResumeProcess
        would report success while the process ends, and it never runs.
        NtResumeProcess on that handle comes first; the thread snapshot is the
        fallback. A process that NtResumeProcess reports as ending gets no
        snapshot: it has no thread left to resume, and the snapshot would hold
        every thread on the machine for nothing.
        """
        if handle is not None:
            if _told_to_end(handle):
                return False
            if _NT_RESUME_PROCESS is not None:
                begun = time.perf_counter()
                status = int(_NT_RESUME_PROCESS(handle))
                if status >= 0:
                    return not _ended_at_once(handle, begun)
                if status & 0xFFFFFFFF == _STATUS_PROCESS_IS_TERMINATING:
                    return False
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

    @property
    def holds_program(self) -> bool:
        """True once the program is in the job."""
        return self._holds_program

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
        changed: list[tuple[int, Any]] = []
        late: list[BaseException] = []
        try:
            if enabled and threading.current_thread() is threading.main_thread():
                _set_handlers(
                    [
                        (signum, _exit_on_signal)
                        for signum in (signal.SIGTERM, signal.SIGHUP)
                        if signal.getsignal(signum) is signal.SIG_DFL
                    ],
                    saved=changed,
                )
            yield
        finally:
            # Again until a call returns: a signal can raise as the call
            # begins, before it changed anything. A refusal would come back.
            while True:
                try:
                    _set_handlers(changed[::-1])
                    break
                except BaseException as error:
                    late.append(error)
                    if _refused(late):
                        break
            if late:
                try:
                    raise _gravest(late)
                finally:
                    # The errors' tracebacks hold this frame: a cycle.
                    late.clear()


def _gravest(errors: Sequence[BaseException]) -> BaseException:
    """Return the error to raise of several.

    A termination wins, then Ctrl+C, then the first of the rest: an error a
    caller may suppress, such as a refused handler's ``ValueError``, never
    hides a signal.
    """
    for kind in (SystemExit, KeyboardInterrupt):
        for error in errors:
            if isinstance(error, kind):
                return error
    return errors[0]


def _refused(errors: Sequence[BaseException]) -> bool:
    """Return True when the last two errors say a change can never be made.

    ``signal.signal`` refuses a handler with one of :data:`_REFUSALS`, and
    again at every try. A signal's handler that Python runs first can raise
    the same kinds of error (a caller's ``SIGALRM`` handler raising
    ``TimeoutError``, say), but it runs once: the try after it succeeds.
    """
    return (
        len(errors) > 1
        and isinstance(errors[-1], _REFUSALS)
        and type(errors[-1]) is type(errors[-2])
    )


# Outside Windows, the signal-mask calls of _set_handlers. They are the C
# function under signal.pthread_sigmask, with the action bound in by
# functools.partial (C too). A Python function would give a signal handler a
# chance to run, and raise, as it begins, before the mask is put back, and
# signal.pthread_sigmask turns each signal number it returns into an enum,
# which made each change of handlers several times slower. _BLOCKED is the
# signals whose handlers the gate changes, and no other: a handler that runs
# mid-change (a caller's SIGALRM handler, say) and a program it starts find at
# most these three blocked.
_BLOCK_MASK: Callable[[Iterable[int]], Iterable[int]] | None = None
_SET_MASK: Callable[[Iterable[int]], Iterable[int]] | None = None
_BLOCKED: frozenset[int] = frozenset()
if sys.platform != "win32":
    _SIGMASK_C: Callable[[int, Iterable[int]], Iterable[int]] | None
    try:
        import _signal  # type: ignore[import-not-found]  # no stub: CPython's C module

        _SIGMASK_C = _signal.pthread_sigmask
    except (ImportError, AttributeError):  # pragma: no cover - not CPython
        # No signal mask here: the per-pair retry alone covers the change.
        _SIGMASK_C = getattr(signal, "pthread_sigmask", None)
    if _SIGMASK_C is not None:
        _BLOCK_MASK = functools.partial(_SIGMASK_C, signal.SIG_BLOCK)
        _SET_MASK = functools.partial(_SIGMASK_C, signal.SIG_SETMASK)
        _BLOCKED = frozenset({signal.SIGINT, signal.SIGTERM, signal.SIGHUP})


# What signal.signal takes as a handler.
_Handler = Callable[[int, FrameType | None], object] | int | signal.Handlers | None

# The errors signal.signal raises itself when it refuses a handler: setting it
# again cannot succeed.
_REFUSALS: Final = (ValueError, TypeError, OSError)


def _set_handler(
    signum: int,
    handler: _Handler,
    saved: list[tuple[int, Any]] | None,
    errors: list[BaseException],
) -> None:
    """Set *handler* for *signum*, again when a signal's handler raised first.

    Python runs the handler of a signal that has arrived before
    ``signal.signal`` changes anything, so an error from it (``SystemExit``
    from :func:`_exit_on_signal`, say) can mean the change was not made. The
    change is then tried again; an error raised after the change leaves it
    made. The pair counts as refused only when the same refusal comes back
    on the next try (see :func:`_refused`). Each error is added to *errors*.
    With *saved*, the handler before the change is added to it first, so it
    can be put back.
    """
    last: type[BaseException] | None = None
    while True:
        try:
            if signal.getsignal(signum) == handler:
                return
            if saved is not None and not (saved and saved[-1][0] == signum):
                saved.append((signum, signal.getsignal(signum)))
            signal.signal(signum, handler)
            return
        except BaseException as error:
            errors.append(error)
            refused = type(error) is last and isinstance(error, _REFUSALS)
            last = type(error)
            if refused and signal.getsignal(signum) != handler:
                # The old handler is still in place: nothing to put back.
                if saved and saved[-1][0] == signum:
                    saved.pop()
                return


def _set_handlers(
    handlers: Sequence[tuple[int, Any]],
    saved: list[tuple[int, Any]] | None = None,
) -> None:
    """Set each ``(signal, handler)`` pair, all of them even if a signal lands.

    Outside Windows, ``SIGINT``, ``SIGTERM`` and ``SIGHUP``, the signals
    whose handlers the gate changes, are blocked on this thread while the
    handlers change, for a few microseconds: one that arrives waits, and is
    handled once every pair is set, by the handler then in place. No other
    signal is blocked, so a handler that runs meanwhile (a caller's
    ``SIGALRM`` handler, say), and a program it starts, find at most those
    three blocked. A signal that is still handled meanwhile (any other
    signal; on Windows, where there is no signal mask, any signal; outside
    it one that arrived just before the block, or one another thread of the
    process received, as the mask is per thread) cannot leave a pair unset:
    a pair whose change it stopped is set again, and the next pair follows.
    Only two handlers that raise the same refusal-like error back to back
    (two ``SIGALRM`` handlers raising ``TimeoutError``, say) leave a pair
    unset: they read as a refusal (see :func:`_set_handler`). With *saved*,
    the handler each change replaces is added to it first. One error then
    goes on, chosen by :func:`_gravest`. A signal can still raise as this
    call begins, before it changed anything, so a caller that must put
    handlers back calls it again until it returns.
    """
    if not handlers:
        return
    errors: list[BaseException] = []
    block, set_mask = _BLOCK_MASK, _SET_MASK
    # Read first: a handler Python runs here raises before anything changed.
    before = None if block is None else block(())
    try:
        if block is not None:
            try:
                block(_BLOCKED)
            except BaseException as error:
                # A handler run as the block took hold: the mask is set.
                errors.append(error)
        index = 0
        while index < len(handlers):
            try:
                while index < len(handlers):
                    signum, handler = handlers[index]
                    _set_handler(signum, handler, saved, errors)
                    index += 1
            except BaseException as error:
                errors.append(error)
    finally:
        if set_mask is not None and before is not None:
            try:
                set_mask(before)
            except BaseException as error:
                errors.append(error)
    if errors:
        try:
            raise _gravest(errors)
        finally:
            # The errors' tracebacks hold this frame: a cycle.
            errors.clear()


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
    """Stop *process* and every program it started that the platform can reach.

    The process group is signalled only while the program is not yet reaped:
    once it is, its process ID can name an unrelated process group later.
    """
    job.terminate()
    if sys.platform != "win32":
        if group and process.returncode is None:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(process.pid, signal.SIGKILL)
    with contextlib.suppress(OSError):
        process.kill()


def _fail_unresumed(
    process: subprocess.Popen[bytes], job: _Job, program: str
) -> NoReturn:
    """Stop *process*, which started suspended and was not resumed, and raise.

    A program that cannot be resumed would wait out the whole time limit, so
    it is stopped at once, its output is awaited for at most
    :data:`STOP_GRACE_SECONDS`, and :class:`ProgramResumeError` is raised.
    A program that something else told to end before the resume never ran:
    its exit code is whatever ended it chose (``taskkill /F`` gives 1), so it
    raises :class:`ProgramResumeError` too, and no caller reads that code as
    git's.
    """
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=_ENDING_WAIT_SECONDS)
    if process.returncode is not None:
        raise ProgramResumeError(
            f"{program!r} ended before it could run (exit code {process.returncode})"
        )
    in_job = job.holds_program
    job.terminate()
    with contextlib.suppress(OSError):
        process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.communicate(timeout=STOP_GRACE_SECONDS)
    if in_job:
        where = "it is in the job object"
    else:
        where = "it is not in the job object: Windows refused to add it"
    raise ProgramResumeError(f"could not resume {program!r} ({where})")


def _signals_to_hold(terminations: bool) -> list[int]:
    """Return the signals :func:`_held_signals` may hold on this thread.

    ``SIGINT`` while it has Python's own handler, which raises
    :class:`KeyboardInterrupt`; with *terminations*, outside Windows, also
    ``SIGTERM`` and ``SIGHUP`` while they keep their default action or the
    handler :func:`_exit_on_termination` set. A handler the caller installed
    is never replaced. Only the main thread may set a handler.
    """
    if threading.current_thread() is not threading.main_thread():
        return []
    held: list[int] = []
    if signal.getsignal(signal.SIGINT) is signal.default_int_handler:
        held.append(signal.SIGINT)
    if terminations and sys.platform != "win32":
        for signum in (signal.SIGTERM, signal.SIGHUP):
            if signal.getsignal(signum) in (signal.SIG_DFL, _exit_on_signal):
                held.append(signum)
    return held


def _held_error(received: Sequence[int]) -> BaseException:
    """Return the error a signal held back by :func:`_held_signals` becomes.

    A termination wins over Ctrl+C: it ends this process as the handler
    :func:`_exit_on_signal` would.
    """
    for signum in received:
        if signum != signal.SIGINT:
            return SystemExit(128 + signum)
    return KeyboardInterrupt()


@contextlib.contextmanager
def _held_signals(*, terminations: bool = False) -> Iterator[None]:
    """While the block runs, hold back Ctrl+C, then raise it once it ends.

    With *terminations*, outside Windows, ``SIGTERM`` and ``SIGHUP`` are held
    back too, and raised as :class:`SystemExit` (128 plus the signal
    number). :func:`_signals_to_hold` says which signals are held. The
    previous handlers come back when the block ends, each one while the
    hold's own handler is still in place. A signal that arrived meanwhile is
    then raised, in place of any error the block raised.

    The hold is a Python handler, not a blocked signal: a program started
    meanwhile inherits a blocked signal mask, but not a Python handler. Only
    the change of handlers, at each end, runs with the signals blocked (see
    :func:`_set_handlers`). A signal that lands as the handlers come back
    does not hide one held before: a termination still wins over Ctrl+C.
    """
    received: list[int] = []

    def record(signum: int, _frame: FrameType | None) -> None:
        received.append(signum)

    previous: list[tuple[int, Any]] = []
    late: list[BaseException] = []
    try:
        # Only the main interpreter may set a handler. A subinterpreter's
        # main thread normally fails the default-handler test first, as each
        # interpreter has its own default_int_handler, so nothing is held
        # there; the refusal covers an interpreter that passes it. Any other
        # error (a SIGTERM that lands once Ctrl+C is held, say) goes on, and
        # the handlers set so far come back first. A termination or Ctrl+C
        # that lands beside a refusal wins over it (see _gravest).
        with contextlib.suppress(ValueError):
            _set_handlers(
                [(signum, record) for signum in _signals_to_hold(terminations)],
                saved=previous,
            )
        yield
    finally:
        # Again until a call returns: a signal can raise as the call begins,
        # before it changed anything. A refusal would come back. Only a
        # handler the hold still has in place comes back: a hold closed late
        # (a signal raised in contextlib's __enter__ or __exit__, which left
        # this generator suspended) must not undo an outer restore made since.
        while True:
            try:
                _set_handlers(
                    [
                        pair
                        for pair in previous[::-1]
                        if signal.getsignal(pair[0]) is record
                    ]
                )
                break
            except BaseException as error:
                late.append(error)
                if _refused(late):
                    break
        if received:
            late.insert(0, _held_error(received))
        if late:
            try:
                raise _gravest(late)
            finally:
                # The errors' tracebacks hold this frame: a cycle.
                late.clear()


def _stop_unreturned(error: BaseException, job: _Job, *, group: bool) -> None:
    """Stop the program a Popen call started before it raised *error*.

    Popen returns nothing when it raises, but its own frames in the
    traceback still hold the object as ``self``. Once Popen recorded the
    program's process ID, the program is stopped and awaited for at most
    :data:`STOP_GRACE_SECONDS`. Without an ID nothing is found: an error in
    the moment between the system making the program and Popen recording its
    ID still leaves it. Outside Windows that moment is the end of the fork
    and exec call, where Python handles a signal that arrived during it, so
    :func:`run_bounded` holds Ctrl+C back while Popen runs. A program Popen
    already waited for is left alone, as its process ID may be in use again.
    """
    traceback = error.__traceback__
    while traceback is not None:
        candidate = traceback.tb_frame.f_locals.get("self")
        traceback = traceback.tb_next
        # Popen sets neither attribute until its start is under way: an error
        # in its first lines must not turn into an AttributeError here.
        if (
            isinstance(candidate, _POPEN)
            and getattr(candidate, "pid", None) is not None
            and getattr(candidate, "returncode", None) is None
        ):
            started: subprocess.Popen[bytes] = candidate
            _stop(started, job, group=group)
            with contextlib.suppress(subprocess.TimeoutExpired):
                started.wait(timeout=STOP_GRACE_SECONDS)
            return


def _stop_after_error(
    process: subprocess.Popen[bytes],
    job: _Job,
    error: BaseException,
    *,
    group: bool,
) -> None:
    """Stop *process* after *error* ended its run, and wait for it to end.

    The stop and a short wait for the stopped program run with Ctrl+C held
    back, and with *group* also ``SIGTERM`` and ``SIGHUP``: a second Ctrl+C
    that lands as the stop begins would skip the kill, and a program in a
    session of its own would run on, out of the terminal's reach. A signal
    that lands before the hold is in place, and so raises, cannot skip the
    stop either: the stop starts over, held again, up to
    :data:`_STOP_ATTEMPTS` times in all. When every try fails, or a signal
    raises between tries, the program is stopped once more without the hold.
    The gravest error of all the tries then goes on (see :func:`_gravest`),
    unless the error the stop began with outranks it: the caller raises that
    one again. The wait reaps the program, so
    outside Windows no zombie is left behind. After a time-out, the output
    is then awaited for at most :data:`STOP_GRACE_SECONDS`.
    """
    late: list[BaseException] = []
    stopped = False
    try:
        try:
            for _attempt in range(_STOP_ATTEMPTS):
                try:
                    with _held_signals(terminations=group):
                        _stop(process, job, group=group)
                        stopped = True
                        with contextlib.suppress(subprocess.TimeoutExpired):
                            process.wait(timeout=_ENDING_WAIT_SECONDS)
                except BaseException as caught:
                    late.append(caught)
                if stopped:
                    break
        except BaseException as caught:
            # A signal outside the tries' own handling: the range() call, the
            # append above, or the jump back to the next try.
            late.append(caught)
    finally:
        if not stopped:
            # No held try stopped the program: one last stop, without the
            # hold, so it does not run on. Its error is ranked with the rest.
            try:
                _stop(process, job, group=group)
            except BaseException as caught:
                late.append(caught)
    # The errors' tracebacks hold this frame, so neither the list nor a name
    # keeps one past the raise: a cycle would keep the program's Popen.
    pending = _gravest(late) if late else None
    late.clear()
    try:
        # The error that began the stop is ranked too: a termination on its
        # way out keeps its exit code when a Ctrl+C, or a caller's own error,
        # lands during its stop.
        if pending is not None and _gravest((pending, error)) is pending:
            raise pending
    finally:
        pending = None
    if isinstance(error, subprocess.TimeoutExpired):
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.communicate(timeout=STOP_GRACE_SECONDS)


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
    stopped (see the module docstring), the program is awaited for up to half
    a second and the output for at most :data:`STOP_GRACE_SECONDS` more, and
    :class:`subprocess.TimeoutExpired` is
    raised. An interrupt, such as Ctrl+C, that arrives once Popen has
    returned stops them the same way before it goes on, and the stopped
    program is waited for briefly, so no zombie is left. On the main thread,
    Ctrl+C is held back from just before Popen until the program runs (on
    Windows, until the resume of a program that starts suspended is tried),
    and then raised, so an interrupt inside Popen cannot leave the program
    running outside the time limit, or suspended. It is held back again while
    the program is stopped, so a second Ctrl+C cannot skip the stop. With
    *new_session*, outside Windows, ``SIGTERM`` and ``SIGHUP`` are held back
    at the same points and raised as :class:`SystemExit`. A ``SIGINT``
    handler the caller installed is left in place, and with it a window of
    microseconds in which such an interrupt can still leave the program
    behind. Any other error that escapes Popen after the program started
    stops the program. A program that cannot be started raises
    :class:`OSError`. On Windows a program that started suspended and cannot
    be resumed is stopped and raises :class:`ProgramResumeError`, an
    :class:`OSError`. One that something else had told to end before the
    resume never ran, and raises :class:`ProgramResumeError` too: its exit
    code is not the program's own answer. One ended between the first
    exit-code read and the resume is caught by a second read only when that
    read follows the resume within :data:`_NEVER_RAN_WINDOW_SECONDS`. One
    ended later, or read later (this thread waited, for example for the
    GIL), cannot be told apart from one that ran, and its exit code comes
    back. So does one ended with exit code 259 while it still winds down.
    """
    command = list(argv)
    job = _Job()
    suspended = job.suspends
    process: subprocess.Popen[bytes] | None = None
    # One try covers everything from the moment Popen returns, so an interrupt
    # at any point after the start (even before the program is added or
    # resumed) stops the program instead of leaving it suspended. With
    # new_session, SIGTERM and SIGHUP stop it too, from before Popen: during
    # Popen they are held back like Ctrl+C, and the stop runs while they still
    # become an exit.
    try:
        with _exit_on_termination(new_session):
            try:
                with _held_signals(terminations=new_session):
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
                    except BaseException as error:
                        _stop_unreturned(error, job, group=new_session)
                        raise
                    job.add(process.pid)
                    resumed = not suspended or job.resume(process)
                # The hold ends before the waits on a failed resume, so a
                # Ctrl+C then acts at once; the program is stopped either way.
                if not resumed:
                    _fail_unresumed(process, job, command[0])
                stdout, stderr = process.communicate(timeout=timeout)
            except BaseException as error:
                # process is None only when Popen itself failed: nothing
                # started, or what it started was stopped above.
                if process is not None:
                    _stop_after_error(process, job, error, group=new_session)
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
