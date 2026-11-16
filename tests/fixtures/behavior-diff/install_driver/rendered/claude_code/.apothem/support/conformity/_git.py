# SPDX-License-Identifier: MIT

"""Run git in a project the conformity gate checks, with that project's
program-running git settings turned off.

Why this module exists. The gate and several validators read the checked
project's git data: the tracked-file list (``ls-files``), the commit history
(``log``) and the staged change set (``diff --cached``, ``cat-file``). That
project can come from someone else together with its ``.git`` folder, in an
archive or a shared folder, and git reads the repository's own configuration
on every run: ``.git/config``, the files it includes and
``.git/config.worktree``. Settings there can name a program for git to start
while it only reads:

- ``core.fsmonitor`` names a program git runs whenever it loads the index
  (``ls-files``, ``diff --cached``, ``cat-file :<path>``);
- ``log.showSignature``, or a ``%G`` placeholder in ``format.pretty``, makes
  git check a commit signature with ``gpg.program``, ``gpg.ssh.program`` or
  ``gpg.x509.program``;
- ``diff.submodule=diff`` starts a second git in a submodule, which reads that
  submodule's own configuration;
- in a partial clone (``extensions.partialClone``), git fetches a missing
  object through the transport the configuration names, which can run
  ``remote.<name>.uploadpack``, ``core.sshCommand`` or an ``ext::`` command.

:func:`run_git` runs every git command the gate makes, the same way:

- options on git's own command line (:data:`PROTECTIVE_OPTIONS`), which win
  over every configuration file and reach any git that git starts: no pager,
  no file-system monitor, signature programs that cannot exist, submodule
  changes shown as commit ids only, no mailmap, no automatic maintenance, and
  a hooks path no hook can exist under;
- ``--no-ext-diff`` and ``--no-textconv`` on ``diff``, ``log`` and ``show``
  (:data:`NO_DIFF_PROGRAMS`), so no diff driver or text-conversion program
  runs;
- ``GIT_NO_LAZY_FETCH=1`` (git 2.44 and later) and an empty
  ``GIT_ALLOW_PROTOCOL`` (git 2.6.1 and later), which allows no transport and
  overrides the repository's ``protocol.*`` settings, so a missing object is
  never fetched;
- git found only in the full-path entries of ``PATH``, and git started with a
  ``PATH`` that holds only those entries. Windows otherwise looks for a bare
  ``git`` in the current folder first, and an empty or relative ``PATH`` entry
  names the current folder on every platform, so a ``git`` or helper program
  placed in the checked project would run instead.

What stays: the user's own global and system configuration and ``GIT_*``
variables apply, except the settings above, which win in every scope. The
repository can still make git read a file from another place: an
``include.path`` file, or objects borrowed through ``objects/info/alternates``.
On Windows a network path there (``\\\\server\\share``) makes Windows sign in
to that server. Reading content is done with ``cat-file blob``, never with
``show``, so a gitlink (a submodule entry) is refused instead of shown as a
commit.
"""

from __future__ import annotations

import errno
import ntpath
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

# A path below a regular file, where nothing can exist (a file cannot hold
# entries). This module's own file is a regular file wherever the gate runs
# from, and its path is absolute. ``core.hooksPath`` set to it runs no hook,
# and a signature program set to it cannot start.
_NOWHERE: Final[str] = str(Path(__file__).resolve() / "nothing-here")

# Options on git's own command line, ahead of the subcommand. A setting given
# with ``-c`` wins over every configuration file, so the checked repository
# cannot turn these back on, and git passes them on to any git it starts (a
# submodule's included). ``core.fsmonitor`` is set empty: on every git version
# that turns off both a monitor program and the built-in daemon (``false``
# would name a program called ``false`` on git before 2.36);
# ``core.useBuiltinFSMonitor`` is Git for Windows 2.33 to 2.35's own switch for
# that daemon. The three signature programs point nowhere, so neither
# ``log.showSignature`` nor a ``%G`` placeholder in ``format.pretty`` can start
# one. ``diff.submodule=short`` keeps git from starting a second git inside a
# submodule, where the submodule's own configuration would apply.
# ``log.mailmap=false`` keeps ``log`` from reading a mailmap file the
# repository names. ``core.quotePath=false`` prints path names as they are
# rather than C-quoting every byte above 0x7f, so a non-ASCII path reads as
# itself.
PROTECTIVE_OPTIONS: Final[tuple[str, ...]] = (
    "--no-pager",
    "-c",
    "core.fsmonitor=",
    "-c",
    "core.useBuiltinFSMonitor=false",
    "-c",
    f"core.hooksPath={_NOWHERE}",
    "-c",
    "log.showSignature=false",
    "-c",
    f"gpg.program={_NOWHERE}",
    "-c",
    f"gpg.ssh.program={_NOWHERE}",
    "-c",
    f"gpg.x509.program={_NOWHERE}",
    "-c",
    "diff.submodule=short",
    "-c",
    "log.mailmap=false",
    "-c",
    "gc.auto=0",
    "-c",
    "maintenance.auto=false",
    "-c",
    "core.quotePath=false",
)

# Subcommands that can show a diff or a blob, and the options that keep a
# configured external diff program or text-conversion filter from running.
DIFF_SUBCOMMANDS: Final[frozenset[str]] = frozenset({"diff", "log", "show"})
NO_DIFF_PROGRAMS: Final[tuple[str, ...]] = ("--no-ext-diff", "--no-textconv")

# Environment for every git run. GIT_ALLOW_PROTOCOL holds an empty list, so no
# transport (file, ssh, ext, or a remote-helper program) is allowed whatever
# the repository's protocol.* settings say (git 2.6.1 and later read it).
# GIT_NO_LAZY_FETCH stops git 2.44 and later from even trying to fetch a
# missing object. GIT_TERMINAL_PROMPT=0 keeps git from waiting for a
# credential on the terminal.
GIT_ENVIRONMENT: Final[Mapping[str, str]] = {
    "GIT_ALLOW_PROTOCOL": "",
    "GIT_NO_LAZY_FETCH": "1",
    "GIT_TERMINAL_PROMPT": "0",
}


def is_full_path_entry(entry: str, *, windows: bool = os.name == "nt") -> bool:
    r"""Return True when a ``PATH`` entry is a full path on its own.

    On Windows an entry qualifies only when it starts with a drive letter and a
    separator (``C:\`` or ``C:/``) or with two separators (a network path); a
    rooted ``\bin`` or a drive-relative ``C:bin`` still depends on the current
    folder or drive. Elsewhere the entry must start with ``/``. An empty or
    relative entry names the current folder, so it never qualifies. This is the
    rule the gate applies to a validator's ``PYTHONPATH`` as well.
    """
    if not windows:
        return entry.startswith("/")
    if entry[:2] in ("\\\\", "//"):
        return True
    return bool(ntpath.splitdrive(entry)[0]) and entry[2:3] in ("\\", "/")


def full_path_entries(path_value: str, *, windows: bool = os.name == "nt") -> list[str]:
    """Return the full-path entries of a ``PATH`` value, in order.

    On Windows a pair of double quotes around an entry is dropped first, as
    the Windows shells accept quoted ``PATH`` entries.
    """
    separator = ";" if windows else ":"
    kept: list[str] = []
    for raw in path_value.split(separator):
        entry = raw.strip('"') if windows else raw
        if entry and is_full_path_entry(entry, windows=windows):
            kept.append(entry)
    return kept


def find_git(environ: Mapping[str, str] | None = None) -> str | None:
    """Return the full path of the git that ``PATH`` names, or None.

    Only full-path entries are searched (see :func:`full_path_entries`), never
    the current folder. On Windows only ``git.exe`` is accepted: a ``git.cmd``
    or ``git.bat`` runs through ``cmd.exe``, which reads its arguments with
    different quoting rules.
    """
    source = os.environ if environ is None else environ
    name = "git.exe" if os.name == "nt" else "git"
    for entry in full_path_entries(source.get("PATH", "")):
        candidate = Path(entry) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def git_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return the environment for one git run.

    A copy of *environ* (default ``os.environ``) with :data:`GIT_ENVIRONMENT`
    set and ``PATH`` narrowed to its full-path entries, so a program git
    starts by name is never taken from the current folder either.
    """
    env = dict(os.environ if environ is None else environ)
    env.update(GIT_ENVIRONMENT)
    kept = full_path_entries(env.get("PATH", ""))
    if kept:
        env["PATH"] = os.pathsep.join(kept)
    else:
        env.pop("PATH", None)
    return env


def git_argv(
    git: str, args: Sequence[str], *, cwd: Path | str | None = None
) -> list[str]:
    """Return the full argument vector for ``git <args>``.

    *args* starts with the subcommand. :data:`PROTECTIVE_OPTIONS` go before
    it, then ``-C <cwd>`` when *cwd* is given, and :data:`NO_DIFF_PROGRAMS`
    right after the subcommand for ``diff``, ``log`` and ``show``.
    """
    if not args:
        raise ValueError("git_argv needs a subcommand")
    subcommand, *rest = args
    where = ("-C", str(cwd)) if cwd is not None else ()
    extra = NO_DIFF_PROGRAMS if subcommand in DIFF_SUBCOMMANDS else ()
    return [git, *PROTECTIVE_OPTIONS, *where, subcommand, *extra, *rest]


def run_git(
    args: Sequence[str],
    *,
    cwd: Path | str | None = None,
    timeout: float | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` in *cwd* with the project's program-running settings off.

    *args* starts with the git subcommand (``ls-files``, ``log``, ...). *cwd*
    reaches git as ``-C <cwd>``, so a folder that does not exist is git's own
    error (a non-zero exit), as for any other git failure. Output is captured
    and decoded as UTF-8, the encoding git writes path names in; a byte that
    is not UTF-8 reads as U+FFFD. Standard input is empty.

    Raises :class:`FileNotFoundError` when no git is found in a full-path
    ``PATH`` entry, and otherwise what :func:`subprocess.run` raises
    (:class:`subprocess.TimeoutExpired`, and
    :class:`subprocess.CalledProcessError` when *check* is set), so a caller
    handles a missing git as it would any failed start.
    """
    git = find_git()
    if git is None:
        raise FileNotFoundError(
            errno.ENOENT, "git not found in a full-path PATH entry", "git"
        )
    return subprocess.run(  # noqa: S603 — argv list (never a shell): the git found above, fixed options, and the caller's git arguments
        git_argv(git, args, cwd=cwd),
        env=git_environment(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=check,
    )
