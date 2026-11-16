# SPDX-License-Identifier: MIT

"""Find and start the hook commands an install registered, for ``doctor``.

The check is harness-neutral: it holds no vendor config format. It reads the
files an install wrote (from the install ledger), parses the JSON ones, and
collects every handler mapping whose command line for this platform the shared
install driver recognizes as Apothem-owned (``is_apothem_hook``: a command plus
optional ``args`` that point at the materialized ``hooks/dispatch.py`` or
``conformity/gate.py``). A handler holds that command line under ``command``,
or under a key for one platform that takes precedence there:
``commandWindows`` (Codex) and ``powershell`` (GitHub Copilot) on Windows,
``bash`` (GitHub Copilot) on macOS and Linux. Both registration shapes in use
resolve to an argv: exec form (the command is the interpreter, ``args`` the
script and its arguments) and shell form (one command string, split with
:mod:`shlex`). On Windows, a shell-form line written for PowerShell (Cursor's,
and Copilot's ``powershell``) starts with the call operator ``&``, which is
PowerShell syntax rather than part of the argv, so it is dropped first.

A project's files are shared: anyone who can commit to the project can change
them, so a project hook line that looks like Apothem's is no proof that
Apothem wrote it. For a project-scope harness doctor reads the install record
of the named project and starts a line only when it runs nothing but known
code: its interpreter is spelled as the Python Apothem runs under, or as the
interpreter the install wrote into its own entries of a hook file still as the
install left it; the options before the script take no value and run no code;
the script is spelled as the dispatcher the install recorded, in a hook folder
reached through no link, whose files still match the recorded SHA-256
checksums and which holds no other Python file; and the arguments after it are
the ``--contract`` ones Apothem writes. Doctor then starts those trusted
strings, not the tokens read from the file, and it opens or looks up no path a
hook line names unless that path is already trusted, so a line cannot make it
touch a path of its choosing, such as a network share. A trusted interpreter
or dispatcher that is gone is reported as unable to start, without starting
anything; any other line is reported as unchecked, with the reason. Files under
the operator's own home (user-scope harnesses) are read as they are.

Each distinct interpreter and script pair is started once with a no-op
payload: the registered arguments plus ``--help``, and ``{}`` on stdin. The
dispatcher prints its usage and exits 0 once its imports load; the gate's
``--hook`` mode treats a payload with no target path as a silent pass. Either
way nothing is written. The probe runs in a scratch directory with
``PYTHONPATH`` removed, so it tests the hook's own bootstrap rather than the
CLI's import path. A missing interpreter, a missing script, or a crash at
import time fails the probe.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePath

from apothem.harnesses._shared.install_driver import is_apothem_hook
from apothem.harnesses._shared.install_driver_hookfile import apothem_hook_entries
from apothem.lib import install_ledger

#: Script names that identify an Apothem hook entry point inside an argv.
_HOOK_SCRIPTS = ("dispatch.py", "gate.py")

#: Seconds one probe may take; hook timeouts in harness configs use
#: vendor-specific units, so the probe applies its own ceiling.
_PROBE_TIMEOUT_SECONDS = 30

#: Characters of a failing probe's stderr kept for the report.
_DETAIL_LIMIT = 300

#: Keys a handler may hold its command line under, in the order the harness
#: reads them on Windows and on macOS and Linux. GitHub Copilot uses ``command``
#: only when the key for the platform is absent
#: (https://docs.github.com/en/copilot/reference/hooks-reference).
_WINDOWS_COMMAND_KEYS = ("commandWindows", "powershell", "command")
_POSIX_COMMAND_KEYS = ("bash", "command")

#: The install mode of a file that holds nothing but hook registrations.
_HOOK_FILE_MODE = "native_hooks"

#: Python options a project hook line may pass before its script: the
#: isolation flags Apothem's own lines use (``-E -s``) and others that take no
#: value and run no code. Any other option leaves the line unstarted.
_SAFE_PYTHON_OPTIONS = re.compile(r"-[BEIOSsu]+")

#: A name after ``--contract`` in a project hook line: a contract id, an event
#: or a route. Never an option, so the ``--help`` doctor appends stays one.
_PLAIN_NAME = re.compile(r"[A-Za-z0-9][\w.-]*")

#: Suffixes Python imports a module from. A hook folder file with one of them
#: that the install did not write could replace a module the dispatcher loads.
_IMPORTABLE_SUFFIXES = frozenset({".py", ".pyc", ".pyo", ".pyw", ".pyd", ".so"})

#: Ends the sentence for a project hook line doctor did not start.
_NOT_STARTED = "so it was not started"


@dataclass(frozen=True)
class HookProbe:
    """The outcome of starting one registered hook command."""

    command: str
    ok: bool
    detail: str


@dataclass
class RegisteredHooks:
    """The hook commands an install registered, as doctor reads them.

    *argvs* are the commands doctor may start, without repeats. *unstartable*
    holds the commands that cannot start because their interpreter or script
    does not exist; doctor reports them without starting anything.
    *unchecked* holds one sentence for each command or hook file doctor does
    not start, naming it and the reason.
    """

    argvs: list[list[str]] = field(default_factory=list)
    unstartable: list[HookProbe] = field(default_factory=list)
    unchecked: list[str] = field(default_factory=list)

    def add(self, argv: list[str]) -> None:
        """Keep *argv* to start, unless an earlier handler registered it."""
        if argv not in self.argvs:
            self.argvs.append(argv)

    def cannot_start(self, probe: HookProbe) -> None:
        """Keep *probe* as a command that cannot start, once."""
        if probe not in self.unstartable:
            self.unstartable.append(probe)

    def note(self, reason: str) -> None:
        """Keep *reason* for a command or file doctor does not start, once."""
        if reason not in self.unchecked:
            self.unchecked.append(reason)


def registered_hooks(
    package_key: str, *, project_root: Path | None = None
) -> RegisteredHooks | None:
    """Return the Apothem hook commands an install registered.

    With *project_root* (a project-scope harness), the current install record
    of that project is read, and a line is kept to start only when it runs
    nothing but known code (see the module docstring). Without it, the latest
    install record of the harness is read. Returns ``None`` when there is no
    such record (installed before the ledger existed, into another project, or
    by other means), so the caller can report the hook check as not run rather
    than as passed.

    Raises:
        install_ledger.LedgerError: The ledger exists but cannot be read.
    """
    if project_root is None:
        record = install_ledger.latest_record(package_key)
    else:
        record = install_ledger.current_install_record(package_key, root=project_root)
    if record is None:
        return None
    hooks = RegisteredHooks()
    if project_root is None:
        for target in record.targets:
            if target.path.endswith(".json"):
                _read_user_file(Path(target.path), hooks)
        return hooks
    project = _ProjectInstall(project_root, record)
    for target in record.targets:
        project.learn_interpreter(target)
    for target in record.targets:
        project.read_file(target, hooks)
    return hooks


def probe_hooks(argvs: list[list[str]]) -> list[HookProbe]:
    """Start each distinct interpreter and hook-script pair once; return the outcomes."""
    seen: set[tuple[str, str]] = set()
    probes: list[HookProbe] = []
    for argv in argvs:
        script = next(
            (arg for arg in argv[1:] if arg.endswith(_HOOK_SCRIPTS)), argv[-1]
        )
        key = (argv[0], script)
        if key in seen:
            continue
        seen.add(key)
        probes.append(_start(argv, display=f"{argv[0]} {script}"))
    return probes


def _read_user_file(path: Path, hooks: RegisteredHooks) -> None:
    """Collect the hook commands in a file under the operator's own home."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    for handler in _handlers(document, project_scope=False):
        argv = _handler_argv(handler)
        if argv is not None:
            hooks.add(argv)


class _ProjectInstall:
    """One project install's record, to judge the hook lines found in its files.

    Paths are compared by spelling only (:func:`_spelling`). A path is opened
    or looked up only once it is trusted: the Python Apothem runs under, an
    interpreter the install wrote into its own hook entries, or a file the
    install recorded, reached from the project root through no link.
    """

    def __init__(self, root: Path, record: install_ledger.LedgerRecord) -> None:
        self._root = root
        self._root_key = _spelling(str(root)) or ""
        # The files the install wrote, by spelling: the path as recorded and
        # its checksum (``None`` in a record older than checksums). A folder
        # target lists its files' checksums.
        self._files: dict[str, tuple[str, str | None]] = {}
        for target in record.targets:
            if target.files is None:
                self._remember(target.path, target.digest)
            for relative, digest in (target.files or {}).items():
                self._remember(str(Path(target.path, relative)), digest)
        # The interpreters doctor may start, by spelling, each mapped to the
        # string doctor starts. The install writes the resolved form; the first
        # string trusted for a spelling keeps it, so the one Python reports wins.
        executable = Path(sys.executable)
        self._pythons: dict[str, str] = {}
        for trusted in (
            sys.executable,
            str(executable.resolve()),
            str(executable.absolute()),
        ):
            self._trust(trusted)
        self._folders: dict[str, str | None] = {}

    def _remember(self, path: str, digest: str | None) -> None:
        key = _spelling(path)
        if key is not None:
            self._files[key] = (path, digest)

    def _trust(self, interpreter: str) -> None:
        key = _spelling(interpreter)
        if key is not None:
            self._pythons.setdefault(key, interpreter)

    def _inside(self, path: str) -> bool:
        """Return True when *path* is spelled as a path inside the project."""
        key = _spelling(path)
        return key is not None and key.startswith(self._root_key + os.sep)

    def _link_free(self, path: Path) -> bool:
        """Return True when no folder or file from the project root to *path* is a link.

        Each step is looked at without following it, after the steps above it
        were found to be no link, so the check itself never leaves the project.
        """
        try:
            relative = PurePath(os.path.normcase(str(path))).relative_to(self._root_key)
        except ValueError:
            return False
        current = self._root
        for part in relative.parts:
            current = current / part
            if _is_link(current):
                return False
        return True

    def learn_interpreter(self, target: install_ledger.LedgerTarget) -> None:
        """Trust the interpreter the install wrote into its own hook entries.

        Read from a hook file still byte for byte as the install left it: the
        install replaced every entry :func:`apothem_hook_entries` selects, so
        each such entry there is the install's own rendering.
        """
        path = Path(target.path)
        if target.mode != _HOOK_FILE_MODE or target.digest is None:
            return
        if not self._inside(target.path) or not self._link_free(path):
            return
        try:
            data = path.read_bytes()
            document: object = json.loads(data.decode("utf-8"))
        except (OSError, ValueError):
            return
        if hashlib.sha256(data).hexdigest() != target.digest:
            return
        for entry in apothem_hook_entries(document):
            for handler in _handlers(entry, project_scope=True):
                argv = _handler_argv(handler)
                if argv is not None:
                    self._trust(argv[0])

    def read_file(
        self, target: install_ledger.LedgerTarget, hooks: RegisteredHooks
    ) -> None:
        """Judge each Apothem-looking hook line in one project file."""
        path = Path(target.path)
        if not target.path.endswith(".json") or not self._inside(target.path):
            return
        hook_file = target.mode == _HOOK_FILE_MODE
        if not self._link_free(path):
            if hook_file:
                hooks.note(
                    f"{path} is reached through a link, so no hook in it was read"
                )
            return
        try:
            document: object = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            if hook_file:
                hooks.note(
                    f"{path} cannot be read as JSON, so no hook in it was started"
                )
            return
        found = False
        for handler in _handlers(document, project_scope=True):
            argv = _handler_argv(handler)
            if argv is not None:
                found = True
                self._judge(argv, path, hooks)
        if hook_file and not found:
            hooks.note(f"{path} holds no hook command doctor can start")

    def _judge(self, argv: list[str], source: Path, hooks: RegisteredHooks) -> None:
        """Keep the trusted form of *argv* to start, or say why it is not started."""
        interpreter, rest = argv[0], argv[1:]
        options: list[str] = []
        while len(options) < len(rest) and rest[len(options)].startswith("-"):
            options.append(rest[len(options)])
        script = rest[len(options)] if len(options) < len(rest) else None
        tail = rest[len(options) + 1 :]
        display = interpreter if script is None else f"{interpreter} {script}"
        line = f"a hook command in {source}"
        python = self._pythons.get(_spelling(interpreter) or "")
        if python is None:
            hooks.note(
                f"{line} runs {interpreter}, not a Python Apothem runs under or "
                f"wrote into its own hook entries, {_NOT_STARTED}"
            )
            return
        if not Path(python).exists():
            hooks.cannot_start(
                HookProbe(display, False, "the interpreter does not exist")
            )
            return
        if not all(_SAFE_PYTHON_OPTIONS.fullmatch(option) for option in options):
            hooks.note(
                f"{line} starts Python with an option Apothem does not write, "
                f"{_NOT_STARTED}"
            )
            return
        recorded = None if script is None else self._files.get(_spelling(script) or "")
        if recorded is None or Path(recorded[0]).name != "dispatch.py":
            hooks.note(
                f"{line} runs {script}, which this install did not write, {_NOT_STARTED}"
            )
            return
        dispatcher = Path(recorded[0])
        if not self._link_free(dispatcher):
            hooks.note(
                f"{line} runs a hook script reached through a link, {_NOT_STARTED}"
            )
            return
        if not dispatcher.is_file():
            hooks.cannot_start(
                HookProbe(display, False, "the hook script does not exist")
            )
            return
        names = tail[1:]
        if tail[:1] != ["--contract"] or not names:
            hooks.note(
                f"{line} passes arguments Apothem does not write, {_NOT_STARTED}"
            )
            return
        if not all(_PLAIN_NAME.fullmatch(name) for name in names):
            hooks.note(
                f"{line} passes arguments Apothem does not write, {_NOT_STARTED}"
            )
            return
        problem = self._folder_problem(dispatcher.parent)
        if problem is not None:
            hooks.note(problem)
            return
        hooks.add([python, *options, str(dispatcher), *tail])

    def _folder_problem(self, folder: Path) -> str | None:
        """Return why *folder*'s scripts cannot be trusted, or ``None``; once per folder."""
        key = _spelling(str(folder)) or ""
        if key not in self._folders:
            self._folders[key] = self._check_folder(folder, key)
        return self._folders[key]

    def _check_folder(self, folder: Path, key: str) -> str | None:
        """Compare *folder* with the files and checksums the install recorded."""
        prefix = key + os.sep
        recorded = {
            spelled: entry
            for spelled, entry in self._files.items()
            if spelled.startswith(prefix)
        }
        reason = f"the hook scripts in {folder}"
        stop = "so no hook command that runs them was started"
        for directory, folders, files in os.walk(folder):
            for name in sorted([*folders, *files]):
                entry = Path(directory, name)
                shown = os.path.relpath(entry, folder)
                if _is_link(entry):
                    return f"{reason} hold a link, {shown}, {stop}"
                if (
                    name in files
                    and entry.suffix.lower() in _IMPORTABLE_SUFFIXES
                    and _spelling(str(entry)) not in recorded
                ):
                    return f"{reason} hold {shown}, which the install did not write, {stop}"
        for spelled, (path, digest) in sorted(recorded.items()):
            shown = os.path.relpath(spelled, key)
            if digest is None:
                if Path(path).is_dir():
                    continue  # a folder in an older record; its files were walked
                return f"{reason} include {shown}, of which the install kept no checksum, {stop}"
            if _sha256(Path(path)) != digest:
                return f"{reason} changed after the install ({shown}), {stop}"
        return None


def _spelling(path: str) -> str | None:
    """Return the comparable spelling of an absolute *path*, or ``None``.

    Purely lexical: case and separators are folded the way this system folds
    them, and nothing is looked up. A relative path, or one with a ``..``
    step, has no spelling: what it names depends on the links it passes.
    """
    pure = PurePath(path)
    if not pure.is_absolute() or ".." in pure.parts:
        return None
    return os.path.normcase(str(pure))


def _sha256(path: Path) -> str | None:
    """Return the SHA-256 of *path*'s bytes, or ``None`` when it cannot be read."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _is_link(path: Path) -> bool:
    """Return True for a symbolic link, or a junction or other reparse point."""
    try:
        status = os.lstat(path)
    except OSError:
        return False
    reparse = (
        getattr(status, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )
    return stat.S_ISLNK(status.st_mode) or bool(reparse)


def _on_windows() -> bool:
    """Return True on Windows; the platform seam the tests monkeypatch."""
    return sys.platform == "win32"


def _platform_command(handler: dict[str, object]) -> str | None:
    """Return the command line *handler* runs on this platform, or ``None``."""
    keys = _WINDOWS_COMMAND_KEYS if _on_windows() else _POSIX_COMMAND_KEYS
    for key in keys:
        command = handler.get(key)
        if isinstance(command, str):
            return command
    return None


def _handlers(node: object, *, project_scope: bool) -> Iterator[dict[str, object]]:
    """Yield every Apothem-owned hook handler mapping nested in *node*.

    Ownership is read from the command line the handler runs on this platform,
    the one the probe starts. *project_scope* applies the install's own test
    for a project file: the line runs the project's native dispatcher with
    ``--contract``.
    """
    if isinstance(node, dict):
        command = _platform_command(node)
        if command is not None and is_apothem_hook(
            {"command": command, "args": node.get("args")},
            project_scope=project_scope,
        ):
            yield node
        for value in node.values():
            yield from _handlers(value, project_scope=project_scope)
    elif isinstance(node, list):
        for item in node:
            yield from _handlers(item, project_scope=project_scope)


def _handler_argv(handler: dict[str, object]) -> list[str] | None:
    """Resolve a handler mapping to the argv the harness would run."""
    command = _platform_command(handler)
    if command is None or not command.strip():
        return None
    args = handler.get("args")
    if isinstance(args, list):
        return [command, *(str(arg) for arg in args)]
    windows = _on_windows()
    line = command.lstrip()
    if windows and line.startswith("&"):  # PowerShell's call operator, not a program
        line = line[1:]
    try:
        tokens = shlex.split(line, posix=not windows)
    except ValueError:
        return None
    return [_unquoted(token) for token in tokens] or None


def _unquoted(token: str) -> str:
    """Return *token* without the pair of quotes :mod:`shlex` keeps on Windows.

    PowerShell takes a path in double or in single quotes.
    """
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def _start(argv: list[str], *, display: str) -> HookProbe:
    """Run one hook command with the no-op payload in a scratch directory."""
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    with tempfile.TemporaryDirectory(prefix="apothem-doctor-") as scratch:
        try:
            completed = subprocess.run(  # noqa: S603 - a project argv is rebuilt from trusted strings; a home one is the operator's own config; no shell
                [*argv, "--help"],
                input="{}",
                capture_output=True,
                text=True,
                cwd=scratch,
                env=env,
                timeout=_PROBE_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return HookProbe(display, False, f"{type(exc).__name__}: {exc}")
    if completed.returncode == 0:
        return HookProbe(display, True, "")
    tail = (completed.stderr or completed.stdout).strip().splitlines()
    detail = tail[-1] if tail else f"exit {completed.returncode}"
    return HookProbe(
        display, False, f"exit {completed.returncode}: {detail[:_DETAIL_LIMIT]}"
    )
