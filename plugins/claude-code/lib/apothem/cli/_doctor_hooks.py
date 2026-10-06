# SPDX-License-Identifier: MIT

"""Find and start the hook commands an install registered, for ``doctor``.

The check is harness-neutral: it holds no vendor config format. It reads the
files the latest install wrote (from the install ledger), parses the JSON ones,
and collects every handler mapping the shared install driver recognizes as
Apothem-owned (``is_apothem_hook``: a ``command`` plus optional ``args`` that
point at the materialized ``hooks/dispatch.py`` or ``conformity/gate.py``).
Both registration shapes in use resolve to an argv: exec form (``command`` is
the interpreter, ``args`` the script and its arguments) and shell form (one
``command`` string, split with :mod:`shlex`).

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

import json
import os
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from apothem.harnesses._shared.install_driver import is_apothem_hook
from apothem.lib import install_ledger

#: Script names that identify an Apothem hook entry point inside an argv.
_HOOK_SCRIPTS = ("dispatch.py", "gate.py")

#: Seconds one probe may take; hook timeouts in harness configs use
#: vendor-specific units, so the probe applies its own ceiling.
_PROBE_TIMEOUT_SECONDS = 30

#: Characters of a failing probe's stderr kept for the report.
_DETAIL_LIMIT = 300


@dataclass(frozen=True)
class HookProbe:
    """The outcome of starting one registered hook command."""

    command: str
    ok: bool
    detail: str


def registered_hook_argvs(
    package_key: str, *, within: Path | None = None
) -> list[list[str]] | None:
    """Return the argv of every Apothem hook the latest install registered.

    Returns ``None`` when the harness has no install record (installed before
    the ledger existed, or by other means), so the caller can report the hook
    check as not run rather than as passed. *within* limits the scan to files
    under a project root (project-scope harnesses).

    Raises:
        install_ledger.LedgerError: The ledger exists but cannot be read.
    """
    record = install_ledger.latest_record(package_key)
    if record is None:
        return None
    argvs: list[list[str]] = []
    for target in record.targets:
        path = Path(target.path)
        if path.suffix != ".json" or not path.is_file():
            continue
        if within is not None and not path.resolve().is_relative_to(within.resolve()):
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for handler in _handlers(document):
            argv = _handler_argv(handler)
            if argv is not None and argv not in argvs:
                argvs.append(argv)
    return argvs


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


def _handlers(node: object) -> Iterator[dict[str, object]]:
    """Yield every Apothem-owned hook handler mapping nested in *node*."""
    if isinstance(node, dict):
        if isinstance(node.get("command"), str) and is_apothem_hook(node):
            yield node
        for value in node.values():
            yield from _handlers(value)
    elif isinstance(node, list):
        for item in node:
            yield from _handlers(item)


def _handler_argv(handler: dict[str, object]) -> list[str] | None:
    """Resolve a handler mapping to the argv the harness would run."""
    command = handler.get("command")
    windows_command = handler.get("commandWindows")
    if sys.platform == "win32" and isinstance(windows_command, str):
        command = windows_command
    if not isinstance(command, str) or not command.strip():
        return None
    args = handler.get("args")
    if isinstance(args, list):
        return [command, *(str(arg) for arg in args)]
    try:
        tokens = shlex.split(command, posix=sys.platform != "win32")
    except ValueError:
        return None
    return [token.strip('"') for token in tokens] or None


def _start(argv: list[str], *, display: str) -> HookProbe:
    """Run one hook command with the no-op payload in a scratch directory."""
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    with tempfile.TemporaryDirectory(prefix="apothem-doctor-") as scratch:
        try:
            completed = subprocess.run(  # noqa: S603 - argv list from the operator's own installed harness config; no shell
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
