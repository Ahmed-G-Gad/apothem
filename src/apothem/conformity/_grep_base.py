# SPDX-License-Identifier: MIT

"""Shared scaffolding for path-based conformity matchers.

Why this module exists. The path-based conformity matchers
(``check(content, path) -> GrepResult``) each defined a byte-identical
``GrepResult`` dataclass, an identical ``to_json`` serialiser, and a
near-identical ``_read_input`` / ``_main`` / ``__main__`` skeleton. Hoisting
that boilerplate here removes the duplication while preserving every matcher's
observable behaviour: the JSON report shape, the exit codes, and the
stdin-or-path input contract are unchanged.

Scope. This base serves two matcher shapes. The path-based matchers
(``check(content, path) -> GrepResult``) whose canonical report payload is
exactly ``{grep, path, passed, findings}`` — optionally carrying a ``note``
emitted only when present — use :class:`GrepResult` / :func:`run_grep`. The
root-based standalone matchers (``check(root) -> RootGrepResult``) whose
canonical payload is ``{grep, root, passed, advisory, findings}`` use
:class:`RootGrepResult` / :func:`run_root_grep`. Matchers with extra report
keys or a bespoke ``_main`` (custom flags such as ``--staged`` / ``--strict``)
keep their own result dataclass because their serialised shape or CLI diverges
from these two.

Command-line contract. Every conformity entry point parses its arguments with
the one minimal parser built here (:func:`make_parser`), so they share one
behaviour: ``--help`` prints usage and exits 0; an unknown flag, a missing
file, or a root directory that does not exist is a usage error that prints a
one-line message and exits :data:`EXIT_USAGE` (3), never a traceback. A
root-based validator resolves its root to an absolute path before scanning, so
``.`` and the absolute form inspect the same tree, and its report carries an
``inspected`` count (:func:`finish_root_report`). A validator that inspected
nothing cannot pass unless it declares that an empty scope is expected.

Tree walks. A validator that walks the repository from its root uses
:func:`iter_tree_files`, which prunes every nested checkout (a worktree, a
submodule, or a nested clone, each marked by a ``.git`` entry) and the
vendored, virtual-environment, cache and build-output trees in
:data:`PRUNED_SEGMENTS`. Files below a nested checkout belong to another
repository, so a root-level finding on one is a false positive, and a walk that
descends into ``node_modules`` or a built site costs minutes.

Project files only. A project can arrive with its files from someone else, in
an archive or a shared folder, so every validator reads and lists only what
the project itself holds: regular files and real folders below its root. The
walk lists each folder with ``os.scandir`` and never follows a link, and the
helpers in ``_project_paths`` (re-exported here: :func:`is_project_file`,
:func:`is_project_dir`, :func:`project_file_target`,
:func:`list_real_entries`, :func:`child_folder_files`) treat a symbolic link,
a Windows junction, a named pipe, a device or a socket as if it were not
there. A root report lists what they left out under ``skipped_links``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final, NoReturn, Protocol

from apothem.conformity._project_paths import (
    DIR_ENTRY,
    FILE_ENTRY,
    LINK_ENTRY,
    SKIPPED_FOLDER_ENTRY,
    EntryKind,
    as_opened,
    linked_git_entry,
    note_checkout,
    note_root_spelling,
    note_skipped,
    path_kind,
    scan_entries,
    start_skip_log,
    take_skipped_checkouts,
    take_skipped_paths,
)
from apothem.conformity._project_paths import (
    NAME_SURROGATE_TAG_BIT as NAME_SURROGATE_TAG_BIT,
)
from apothem.conformity._project_paths import (
    child_folder_files as child_folder_files,
)
from apothem.conformity._project_paths import is_link as is_link
from apothem.conformity._project_paths import is_project_dir as is_project_dir
from apothem.conformity._project_paths import is_project_file as is_project_file
from apothem.conformity._project_paths import (
    list_real_entries as list_real_entries,
)
from apothem.conformity._project_paths import no_files as no_files
from apothem.conformity._project_paths import (
    project_file_target as project_file_target,
)
from apothem.conformity._safe_open import read_project_bytes

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2
# A command-line usage error (unknown flag, missing file or root): distinct
# from EXIT_FAIL so a caller can tell "invoked wrong" from "found a problem".
EXIT_USAGE: Final[int] = 3
STDIN_FLAG: Final[str] = "--stdin"

# Report key emitted only when the run left out links or special files: their
# paths relative to the root (see ``_project_paths``).
SKIPPED_KEY: Final[str] = "skipped_links"
# Report key emitted only when a walk left out folders as nested checkouts:
# their paths relative to the root. It is for information only and never
# changes a verdict (see ``nested_checkout``).
CHECKOUTS_KEY: Final[str] = "skipped_checkouts"
# Report key every root-based validator emits: how many targets it inspected.
INSPECTED_KEY: Final[str] = "inspected"
# Report key emitted only when nothing was inspected: whether the validator
# declared that an empty scope is expected (True) or not (False, a failure).
EMPTY_SCOPE_KEY: Final[str] = "empty_scope_expected"
# Report key emitted only when a check could not finish, for example because a
# git command ran past its time limit or the gate stopped the validator. The
# value says why; a report that carries it does not pass.
CHECK_ERROR_KEY: Final[str] = "check_error"

# Seconds a ``git ls-files`` run may take. Listing reads only the index, so
# even a large repository lists in about a second; the rest is room for a slow
# or busy machine. The checked repository's own configuration can still make
# git wait for ever, for example through an ``include.path`` that names a
# FIFO, and the limit ends such a run.
GIT_LS_FILES_TIMEOUT_SECONDS: Final[int] = 60


class GitCheckError(Exception):
    """A git command a check needs gave no answer, so the check could not finish.

    The message names the command and what happened, in fixed words: it never
    repeats git's own error output, which a checked repository can shape. A
    validator reports the message as its ``check_error``; a check whose git
    never answered has not earned a pass.
    """


class GitTimeoutError(GitCheckError):
    """A git command ran past its time limit.

    A repository's own configuration can make git wait for ever, for example
    through an ``include.path`` that names a FIFO. The message reads, for
    example, ``git log did not finish within 60 seconds``.
    """

    def __init__(self, command: str, seconds: float) -> None:
        """Name the git *command* that did not finish within *seconds*."""
        super().__init__(f"{command} did not finish within {seconds} seconds")


class GitEntryUnreadableError(GitCheckError):
    """A ``.git`` entry on git's search path could not be looked at.

    The check did not run git (see ``nearest_linked_git_entry``), and it has
    not earned a pass: the message is the sentence ``linked_git_message``
    gives, naming the entry.
    """


class GitEntryLinkedError(GitCheckError):
    """A ``.git`` entry on git's search path is a link, so git was not run.

    Raised by :func:`refuse_linked_git` for a check that reports a refusal as
    its ``check_error``, such as a ``--staged`` check: git would follow the
    link to another repository. The message is the sentence
    ``linked_git_message`` gives, naming the entry.
    """


class GitFailedError(GitCheckError):
    """A git command failed in a repository that is there.

    git refuses a repository it may not read (one another user owns, a bad
    line in its configuration, an included file it cannot open). That is not
    the exempt state of a folder with no repository or no commit: the history
    is there but was not read. The message reads, for example,
    ``git log failed with exit code 128``.
    """

    def __init__(self, command: str, returncode: int) -> None:
        """Name the git *command* that exited with *returncode*."""
        super().__init__(f"{command} failed with exit code {returncode}")


class GitNameError(GitCheckError):
    """A file name git listed cannot be given back to git as an argument.

    Windows passes arguments as UTF-16, so a name that is not valid UTF-8 (one
    from an index made on another system) reaches git as other bytes and git
    finds no such file. The file's content was not read, which is not the same
    as a file with nothing to report. The message reads, for example,
    ``git cat-file cannot read a file whose name is not UTF-8 on Windows``; it
    never repeats the name, which a checked repository shapes.
    """

    def __init__(self, command: str) -> None:
        """Name the git *command* that could not be given the file name."""
        super().__init__(
            f"{command} cannot read a file whose name is not UTF-8 on Windows"
        )


# ---------------------------------------------------------------------------
# Shared command-line parser
# ---------------------------------------------------------------------------


class UsageParser(argparse.ArgumentParser):
    """An ``ArgumentParser`` whose usage errors exit :data:`EXIT_USAGE`.

    ``argparse`` exits 2 on a usage error by default, which collides with the
    conformity findings-block code :data:`EXIT_FAIL`. This subclass prints the
    usage line plus a one-line message to stderr and exits 3 instead.
    """

    def error(self, message: str) -> NoReturn:
        """Report a usage error on stderr and exit :data:`EXIT_USAGE`."""
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _summary(doc: str | None) -> str | None:
    """Return the first paragraph of a module docstring for ``--help``."""
    if not doc:
        return None
    return doc.strip().split("\n\n", 1)[0]


def make_parser(prog: str, doc: str | None = None) -> UsageParser:
    """Return the shared conformity parser for one entry point.

    Pre-conditions: ``prog`` is the name shown in usage text; ``doc`` is the
    module docstring (its first paragraph becomes the description).
    Post-conditions: abbreviated flags are rejected (``allow_abbrev=False``)
    so ``--al`` never silently means ``--all``.
    """
    return UsageParser(prog=prog, description=_summary(doc), allow_abbrev=False)


def _entry_identity(
    check: Callable[..., Any], argv: list[str]
) -> tuple[str, str | None]:
    """Return ``(prog, docstring)`` for the module that defines ``check``."""
    module = sys.modules.get(getattr(check, "__module__", "") or "")
    doc = getattr(module, "__doc__", None)
    prog = getattr(module, "GREP_NAME", None)
    if not isinstance(prog, str):
        prog = Path(argv[0]).stem if argv and argv[0] else "conformity-grep"
    return prog, doc if isinstance(doc, str) else None


def add_path_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the path-or-stdin input arguments of a per-file matcher."""
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="file to scan (omit, or pass --stdin, to read the content from stdin)",
    )
    parser.add_argument(
        STDIN_FLAG,
        dest="stdin",
        action="store_true",
        help="read the content from stdin instead of a file",
    )


def read_path_arguments(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> tuple[str, Path | None]:
    """Return ``(content, path)`` from parsed path-or-stdin arguments.

    Post-conditions: a ``path`` that is not an existing regular file is a
    usage error (exit :data:`EXIT_USAGE`); a ``path`` combined with
    ``--stdin`` is a usage error; with neither, stdin is read.
    """
    if args.path is not None and args.stdin:
        parser.error("pass either a file path or --stdin, not both")
    if args.path is None:
        return sys.stdin.read(), None
    path = Path(args.path)
    if not path.is_file():
        parser.error(f"not an existing file: {path}")
    try:
        return path.read_text(encoding="utf-8"), path
    except (OSError, UnicodeDecodeError) as exc:
        parser.error(f"cannot read {path}: {exc}")


def parse_root_args(
    argv: list[str],
    *,
    prog: str,
    doc: str | None = None,
    configure: Callable[[argparse.ArgumentParser], None] | None = None,
) -> argparse.Namespace:
    """Parse a root-based validator's arguments; resolve and check the root.

    Pre-conditions: ``argv`` is ``sys.argv`` (``argv[0]`` is the script
    name). ``configure``, when given, adds validator-specific flags.
    Post-conditions: ``namespace.root`` is the absolute, resolved root (the
    current directory when omitted). A root that is not an existing directory,
    or an unknown flag, exits :data:`EXIT_USAGE`; ``--help`` exits 0.
    """
    parser = make_parser(prog, doc)
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="directory to inspect (default: the current directory)",
    )
    if configure is not None:
        configure(parser)
    args = parser.parse_args(argv[1:])
    root = Path(args.root) if args.root is not None else Path.cwd()
    if not root.is_dir():
        parser.error(f"root is not an existing directory: {root}")
    args.root = root.resolve()
    start_skip_log(args.root)
    # The root as typed, made absolute but not resolved: an absolute link may
    # be written through this spelling.
    # ``..`` is not collapsed by name: through a link it can name another
    # folder, so such a spelling is not recorded at all.
    typed = root if root.is_absolute() else Path.cwd() / root
    note_root_spelling(typed if ".." not in typed.parts else args.root, args.root)
    return args


def finish_root_report(
    report_json: str,
    *,
    passed: bool,
    inspected: int,
    empty_scope_expected: bool = False,
    advisory: bool = False,
    check_error: str | None = None,
) -> int:
    """Stamp the ``inspected`` count on a root report, print it, return the exit.

    Pre-conditions: ``report_json`` is the validator's JSON object report;
    ``passed`` is its verdict; ``inspected`` is how many targets it examined;
    ``empty_scope_expected`` is True only when the validator documents that
    an empty scope is legitimate (for example a gitignored plans tree that a
    clean checkout does not carry). ``advisory`` validators report findings
    without failing. ``check_error`` is why the check could not finish (a
    git command that ran past its time limit, say), or None when it finished.
    Post-conditions: the printed payload carries ``inspected``. When nothing
    was inspected it also carries ``empty_scope_expected``; an unexpected empty
    scope sets ``passed`` to false and returns :data:`EXIT_FAIL` even for an
    advisory validator, because a validator that inspected nothing has not
    earned a pass. A ``check_error`` is stamped on the payload and fails the
    run the same way, advisory or not: a check that could not finish has not
    earned a pass either. Otherwise the return is :data:`EXIT_PASS` for a pass
    or an advisory validator, and :data:`EXIT_FAIL` for a failing blocking one.
    When the run left out links or special files, the payload lists them under
    ``skipped_links`` (relative to the root, or by full path for an entry
    outside it, such as a linked ``.git`` above the root), so a link never hides a file
    without a trace. A run that inspected nothing while it left a link out
    does not pass, even when an empty scope is expected: a fixed folder that
    is a link must not pass as a folder that is not there yet. Every folder a
    walk left out as a nested checkout is listed under ``skipped_checkouts``
    (relative to the root); that list never changes the verdict.
    """
    payload = json.loads(report_json)
    payload[INSPECTED_KEY] = inspected
    checkouts = take_skipped_checkouts()
    if checkouts:
        payload[CHECKOUTS_KEY] = checkouts
    skipped = take_skipped_paths()
    if skipped:
        payload[SKIPPED_KEY] = skipped
    # A scope that is empty because a link was in the way is not the empty
    # scope a validator expects: the files may be there, behind the link.
    scope_expected = empty_scope_expected and not skipped
    vacuous = inspected == 0 and not scope_expected
    if inspected == 0:
        payload[EMPTY_SCOPE_KEY] = scope_expected
    if check_error is not None:
        payload[CHECK_ERROR_KEY] = check_error
    unearned = vacuous or check_error is not None
    if unearned:
        payload["passed"] = False
    print(json.dumps(payload, indent=2))
    if unearned:
        return EXIT_FAIL
    if advisory or passed:
        return EXIT_PASS
    return EXIT_FAIL


# ---------------------------------------------------------------------------
# Shared tree walk
# ---------------------------------------------------------------------------
#
# ``Path.rglob`` cannot prune: it lists every file below the root, including
# the files of a nested checkout (a Claude Code worktree under
# ``.claude/worktrees/``, a submodule, a nested clone) and the tens of
# thousands under ``node_modules``. The root-level validators walk with
# :func:`iter_tree_files` instead, which drops those subtrees before listing
# them.

# The marker of a checkout: a file in a linked worktree or a submodule, a
# directory in a clone.
GIT_ENTRY: Final[str] = ".git"

# Directory names no validator scans, wherever they sit below the root: VCS
# state, vendored dependencies, virtual environments, caches, and build output
# (``dist``, ``.next``, ``.audit``). The repository's ``.gitignore`` lists the
# build-output names, so none of them holds authored content. A validator with
# exclusions of its own keeps them and passes any further names as
# ``extra_prune``.
PRUNED_SEGMENTS: Final[frozenset[str]] = frozenset(
    {
        GIT_ENTRY,
        "node_modules",
        "_vendor",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        ".audit",
        ".next",
        "dist",
    }
)


def has_git_entry(directory: Path) -> bool:
    """Return True iff ``directory`` holds a ``.git`` file or directory.

    A broken symbolic link named ``.git`` counts: the entry exists, so the
    directory is a checkout root.
    """
    return os.path.lexists(directory / GIT_ENTRY)


# What the ``.git`` entry of a folder is to git's search for a repository.
GIT_ENTRY_NONE: Final[str] = "none"
GIT_ENTRY_REPOSITORY: Final[str] = "repository"
GIT_ENTRY_BROKEN: Final[str] = "broken"
_GITFILE_PREFIX: Final[bytes] = b"gitdir: "
# git refuses a ``.git`` file larger than this ("too large to be a .git file").
_GITFILE_MAX_BYTES: Final[int] = 1 << 20
# On Windows a path that starts with two separators is a network path
# (``\\host\share``) or a device path (``\\?\``, ``\\.\``). One that starts
# with ``\??\`` is an NT path, which can name a host as well
# (``\??\UNC\host\share``); Python's path joining turns ``/??/`` and the
# mixed forms into ``\??\``. On POSIX all of these are local paths.
_NON_LOCAL_START: Final[re.Pattern[str]] = re.compile(r"[\\/](?:[\\/]|\?\?[\\/])")


def _names_non_local_path(text: str) -> bool:
    """Return True when *text* is a network, device or NT path on Windows.

    Looking such a path up makes Windows connect to the named host and offer
    the user's sign-in. Git for Windows refuses a ``gitdir:`` line in the
    local device forms ``\\\\?\\C:\\...`` and ``\\\\.\\C:\\...`` and in the
    NT form ``\\??\\C:\\...`` ("may refer to a non-local directory"); the
    tests run git on those. They never run git on a line that names a real
    share, so whether git refuses one before it connects is not tested.

    Only the text is read, so these cases still reach a share:

    - a ``gitdir:`` line that names a mapped network drive (``Z:\\repo``);
    - a ``.git`` that is a symbolic link to a share, which is followed
      before the file is read;
    - a ``gitdir:`` line, with a drive or relative (``C:\\link\\repo``,
      ``../link/repo``), whose path passes through a symbolic link to a
      share;
    - a checked folder that is itself on a share or reached through such a
      link;
    - Python built for MSYS2 or Cygwin, where ``os.name`` is ``"posix"``
      and no path is refused.
    """
    return os.name == "nt" and _NON_LOCAL_START.match(text) is not None


# A drive prefix such as ``C:``, which Git for Windows skips before it checks
# a path.
_DRIVE_PREFIX: Final[re.Pattern[str]] = re.compile(r"[A-Za-z]:")
# Characters Git for Windows refuses anywhere in a path after the drive: a
# colon (an NTFS stream such as ``::$INDEX_ALLOCATION``), the wildcard and
# redirection characters, and the control characters.
_REFUSED_WIN32_CHARACTERS: Final[re.Pattern[str]] = re.compile(r'[:<>"|?*\x01-\x1f]')
# Device names Git for Windows refuses as a path name, in any case, alone or
# before spaces, a dot, a colon or a separator. Git for Windows refuses
# ``lpt`` before any digit, ``lpt0`` too, but ``com`` only before 1 to 9.
_RESERVED_WIN32_NAMES: Final[frozenset[str]] = frozenset(
    {"aux", "con", "conin$", "conout$", "nul", "prn"}
    | {f"com{digit}" for digit in range(1, 10)}
    | {f"lpt{digit}" for digit in range(0, 10)}
)


def _refused_by_git_for_windows(text: str) -> bool:
    """Return True when Git for Windows refuses *text* as a path.

    Git for Windows checks each path it opens (``is_valid_win32_path``). It
    refuses a name that ends in a dot or a space, other than ``.`` and
    ``..``, and a colon or another refused character after the drive. Windows
    itself drops such a dot and reads such a colon as a stream, so a lookup
    of ``../repo/.git.`` or ``../repo/.git::$INDEX_ALLOCATION`` finds the
    repository git refuses. It also refuses a reserved device name (``aux``,
    ``con``, ``conin$``, ``conout$``, ``nul``, ``prn``, ``com1`` to ``com9``,
    ``lpt0`` to ``lpt9``) in any case, alone or before a dot, such as
    ``aux.d``, which newer Windows opens as an ordinary folder. On POSIX git
    takes every such name as written, so nothing is refused.
    """
    if os.name != "nt":
        return False
    rest = text[2:] if _DRIVE_PREFIX.match(text) else text
    if _REFUSED_WIN32_CHARACTERS.search(rest):
        return True
    for name in re.split(r"[\\/]", rest):
        if name in {".", ".."}:
            continue
        if name.endswith((".", " ")):
            return True
        if name.split(".", 1)[0].rstrip(" ").lower() in _RESERVED_WIN32_NAMES:
            return True
    return False


def _decode_gitdir(raw: bytes) -> str | None:
    """Return the path a ``gitdir:`` line names, as git reads its bytes.

    Git for Windows reads the line as UTF-8 (``xutftowcsn``). A byte that
    is not part of valid UTF-8 stands for itself: from 0xA0 up it becomes
    the character of that number (Latin-1), and below that its two
    lowercase hex digits, so ``caf\\x9f`` names the folder ``caf9f``. git
    also reads an encoded surrogate (``ED A0 80`` to ``ED BF BF``) as that
    surrogate. Two that form a pair name the one character they stand for.
    A surrogate left alone makes git stop with an error, so None is
    returned. On POSIX git hands the bytes to the system as they are, so
    they are kept (``os.fsdecode``) and a name in another encoding still
    finds its folder.
    """
    if os.name != "nt":
        return os.fsdecode(raw)
    text: list[str] = []
    rest = raw
    while rest:
        try:
            text.append(rest.decode("utf-8", "surrogatepass"))
            break
        except UnicodeDecodeError as error:
            text.append(rest[: error.start].decode("utf-8", "surrogatepass"))
            byte = rest[error.start]
            text.append(chr(byte) if byte >= 0xA0 else f"{byte:02x}")
            rest = rest[error.start + 1 :]
    # A round trip through UTF-16 joins each pair and fails on a lone one.
    try:
        return "".join(text).encode("utf-16-le", "surrogatepass").decode("utf-16-le")
    except UnicodeDecodeError:
        return None


def _holds_repository(git_dir: Path) -> bool:
    """Return True when *git_dir* looks like a repository to git.

    git asks for a ``HEAD`` and for the object and reference stores, which a
    linked work tree's folder borrows through its ``commondir`` file. The
    caller makes sure *git_dir* is no network, device or NT path on Windows.
    """
    if not (git_dir / "HEAD").is_file():
        return False
    if (git_dir / "commondir").is_file():
        return True
    return (git_dir / "objects").is_dir() and (git_dir / "refs").is_dir()


def git_entry_state(directory: Path) -> str:
    """Say what the ``.git`` entry of ``directory`` is to git's search.

    - :data:`GIT_ENTRY_REPOSITORY`: git stops here and uses it. A ``.git``
      folder that holds a repository, or a ``.git`` file whose ``gitdir:``
      line names one (a linked work tree, a submodule). A ``.git`` link
      counts too: git uses what it names, which is not looked at here.
    - :data:`GIT_ENTRY_BROKEN`: git stops here with an error. A ``.git`` file
      that names no repository, that does not start with ``gitdir:`` and
      one space, that is larger than git reads (1 MiB), or, on Windows,
      whose path, alone or joined to a folder with no drive, is a network,
      device or NT path. That last path is never looked up, so Windows does
      not connect to a host the file names. On Windows a path Git for
      Windows refuses (a name that ends in a dot or a space, a colon after
      the drive) is broken too, and is not looked up either.
    - :data:`GIT_ENTRY_NONE`: git looks further up. No entry, a ``.git``
      folder that holds no repository (an empty one, say), or a named
      pipe, a device or a socket by that name.

    The entry is looked at with ``os.lstat``, never through a link. A
    ``.git`` file is read only up to git's size limit plus one byte, and
    through the guarded open (``_safe_open``): an entry swapped for a
    link or a named pipe after that look is not read, and is broken.
    """
    entry = directory / GIT_ENTRY
    kind = path_kind(entry)
    if kind == LINK_ENTRY:
        return GIT_ENTRY_REPOSITORY
    if kind == DIR_ENTRY:
        return GIT_ENTRY_REPOSITORY if _holds_repository(entry) else GIT_ENTRY_NONE
    if kind != FILE_ENTRY:
        return GIT_ENTRY_NONE
    try:
        content = read_project_bytes(directory, entry, max_bytes=_GITFILE_MAX_BYTES + 1)
    except OSError:
        return GIT_ENTRY_BROKEN
    if len(content) > _GITFILE_MAX_BYTES:
        return GIT_ENTRY_BROKEN
    # git reads the whole file. It must start with "gitdir: ", one space.
    # git drops only the CR and LF bytes at the end; the rest is the path as
    # written, so a second line, a tab or a second space stays in it. git
    # reads the path as a C string, so it ends at the first NUL byte.
    if not content.startswith(_GITFILE_PREFIX):
        return GIT_ENTRY_BROKEN
    raw = content[len(_GITFILE_PREFIX) :].rstrip(b"\r\n")
    if not raw:
        return GIT_ENTRY_BROKEN  # git: "no path in gitfile"
    named = _decode_gitdir(raw.split(b"\0", 1)[0])
    if named is None:
        return GIT_ENTRY_BROKEN
    if _names_non_local_path(named) or _refused_by_git_for_windows(named):
        return GIT_ENTRY_BROKEN
    target = directory / named
    # A folder with a root but no drive (``\\``) turns a relative line such as
    # ``??/UNC/host/share`` into an NT path. A folder with a drive is left
    # out: a long-path folder (``\\\\?\\C:\\...``) is local.
    if not directory.drive and _names_non_local_path(str(target)):
        return GIT_ENTRY_BROKEN
    return GIT_ENTRY_REPOSITORY if _holds_repository(target) else GIT_ENTRY_BROKEN


# git stops its search for a repository at a folder on another file system.
# Git for Windows does not: its file status carries no device number.
_STOPS_AT_FILE_SYSTEM: Final[bool] = os.name != "nt"


def _device(folder: Path) -> int | None:
    """Return the number of the file system ``folder`` is on, or None."""
    try:
        return folder.stat().st_dev
    except OSError:
        return None


# A whole number as git reads one: an optional sign, decimal, hexadecimal
# (0x) or octal (leading 0) digits, and an optional k, m or g for a multiple
# of 1024.
_GIT_INTEGER: Final[re.Pattern[str]] = re.compile(r"([-+]?)(0x[0-9a-f]+|\d+)[kmg]?")


def _git_flag_is_set(name: str) -> bool:
    """Return True unless git would read the environment variable as false.

    git takes ``true``, ``yes``, ``on`` and any number other than zero as
    true, and ``false``, ``no``, ``off``, zero and an empty value as false. On
    any other value git stops with an error. That reads as true here: the
    search for a checkout then stops nowhere git might have gone on, and the
    git command the caller runs reports the error itself.
    """
    value = os.environ.get(name, "").lower()
    if value in {"", "false", "no", "off"}:
        return False
    number = _GIT_INTEGER.fullmatch(value)
    if number is None:
        return True
    digits = number.group(2)
    base = 16 if digits.startswith("0x") else 8 if digits.startswith("0") else 10
    try:
        return int(digits, base) != 0
    except ValueError:
        return True


def _git_reads_as_full_path(entry: str) -> bool:
    """Return True when git takes *entry* as a full path.

    Elsewhere than Windows that is a path that starts with ``/``. Git for
    Windows also takes a path that starts with a separator and has no drive
    letter, and one that starts with a drive letter and a colon.
    """
    if os.name != "nt":
        return entry.startswith("/")
    return entry[:1] in ("\\", "/") or (entry[:1].isalpha() and entry[1:2] == ":")


def _ceiling_folders(start: Path) -> tuple[frozenset[str], frozenset[str]]:
    """Return the folders ``GIT_CEILING_DIRECTORIES`` names, as git reads them.

    *start* is the folder git would run in, as it is named: its full path
    with links and mapped drive letters left as they are. git ignores an entry
    that is not a full path. Up to the first empty entry it resolves each
    entry (links, ``..``, a missing drive letter) and drops one it cannot
    resolve; those come back first, in the platform's case form. A Windows
    entry with no drive letter is read on the drive of *start*, which is
    git's current folder: not on the drive this process happens to be on, and
    not on the drive a mapped letter resolves to. After an
    empty entry git compares each entry as it is written, with forward
    slashes, against its own current folder; those come back second, without
    the one slash git lets such an entry end with (an entry that ends with
    two never matches a folder, for git as here).
    """
    resolved: set[str] = set()
    as_written: set[str] = set()
    resolve = True
    for entry in os.environ.get("GIT_CEILING_DIRECTORIES", "").split(os.pathsep):
        if not entry:
            resolve = False
        elif not _git_reads_as_full_path(entry):
            continue
        elif not resolve:
            ends_with_slash = entry.endswith("/") and len(entry) > 1
            as_written.add(entry[:-1] if ends_with_slash else entry)
        else:
            try:
                real = str(Path(_on_drive_of(start, entry)).resolve(strict=True))
            except OSError:
                continue
            resolved.add(os.path.normcase(_without_long_path_prefix(real)))
    return frozenset(resolved), frozenset(as_written)


def _on_drive_of(start: Path, entry: str) -> str:
    r"""Return a Windows path that has no drive letter with the drive of *start*.

    ``\work\projects`` names a folder on the current drive, and for git that
    is the drive of the folder it runs in. A path that names its own drive or
    server (``C:\work``, ``\\server\share``), and any path elsewhere than
    Windows, comes back unchanged.
    """
    if os.name != "nt":
        return entry
    rooted = entry[:1] in ("\\", "/") and entry[1:2] not in ("\\", "/")
    return start.drive + entry if rooted else entry


def _without_long_path_prefix(path: str) -> str:
    r"""Return a Windows path without its ``\\?\`` long-path prefix.

    ``\\?\C:\work`` names ``C:\work`` and ``\\?\UNC\server\share`` names
    ``\\server\share``. Git for Windows drops the prefix from a ceiling entry
    before it compares. Elsewhere the path comes back unchanged.
    """
    if os.name != "nt":
        return path
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def checkout_search_folders(directory: Path) -> Iterator[Path]:
    """Yield ``directory`` and the folders above it that git would search.

    These are the folders git looks in for a repository when it runs in
    ``directory``, nearest first, with links resolved as in git's own current
    folder. The walk stops where git's search stops: below a folder that
    ``GIT_CEILING_DIRECTORIES`` names, and, outside Windows, at a folder on
    another file system unless ``GIT_DISCOVERY_ACROSS_FILESYSTEM`` is set.
    """
    start = directory.resolve()
    # The drive of a ceiling entry with no drive letter is the drive git runs
    # on: the folder as it is named, not as it resolves. A mapped drive letter
    # (``subst V:``) resolves to the folder behind it on another drive.
    resolved, as_written = _ceiling_folders(directory.absolute())
    one_file_system = _STOPS_AT_FILE_SYSTEM and not _git_flag_is_set(
        "GIT_DISCOVERY_ACROSS_FILESYSTEM"
    )
    device = _device(start) if one_file_system else None
    yield start
    for folder in start.parents:
        if os.path.normcase(str(folder)) in resolved or folder.as_posix() in as_written:
            return
        if device is not None and _device(folder) != device:
            return
        yield folder


def in_checkout(directory: Path) -> bool:
    """Return True iff ``directory`` or a folder above it holds a ``.git`` entry.

    The walk covers :func:`checkout_search_folders`, the folders git searches
    for a repository when it runs in ``directory``, so a git command that
    fails there failed inside a checkout and its data was not read, also when
    ``directory`` is a subfolder of the checkout. A folder with no repository
    of its own, mounted below one, is outside a checkout here as it is for
    git. Differences from git remain, among them: a ``.git`` folder that
    holds no repository counts here, while git looks past it; and ``GIT_DIR``
    or ``GIT_WORK_TREE`` in the environment, which tell git where the
    repository is, are not read.
    """
    return any(has_git_entry(folder) for folder in checkout_search_folders(directory))


def nearest_linked_git_entry(root: Path) -> Path | None:
    """Return a ``.git`` entry on git's search path from *root* that git must not use.

    git looks for the repository in *root* and in the folders above it
    (:func:`checkout_search_folders`). This looks at the ``.git`` entry of
    each of those folders with ``os.lstat``, as the tree is at that moment,
    and returns the first one that is a link (to a folder or a file, a
    junction, or one that dangles), noted in the skip log, or that
    ``os.lstat`` cannot look at for any reason but its absence, so the check
    fails closed (:func:`linked_git_message` gives each its own sentence). It
    does not stop at a real ``.git`` entry and does not judge whether a
    folder holds a repository.

    The boundary this is part of, what it refuses that git would handle
    safely, and what it leaves to git, are stated once, in the conformity
    README's rule for checks that run git (``src/apothem/conformity/README.md``,
    "Project files only, never through a link"); the English usage page and
    the changelog state the same boundary. Every check in the ``--all`` and
    ``--all-perwrite`` set that runs git calls this first and runs git with
    ``discover=True``. The ``--staged`` checks call it too, through
    :func:`refuse_linked_git` on the folder git runs in; they keep the
    repository a hook's ``GIT_DIR`` names.
    """
    # What this look finds replaces what an earlier one found.
    _unreadable_entries.discard(os.fspath(root / GIT_ENTRY))
    if linked_git_entry(root):
        return root / GIT_ENTRY
    for folder in checkout_search_folders(root):
        entry = folder / GIT_ENTRY
        # What this look finds replaces what an earlier one found.
        _unreadable_entries.discard(os.fspath(entry))
        try:
            info = os.lstat(entry)
        except OSError as exc:
            if _absent(exc, entry):
                continue
            _unreadable_entries.add(os.fspath(entry))
            return entry
        except ValueError:
            _unreadable_entries.add(os.fspath(entry))
            return entry
        if is_link(info):
            note_skipped(entry)
            return entry
    return None


# The refusal of a ``--staged`` check whose own folder's ``.git`` is a link.
STAGED_LINKED_GIT_MESSAGE: Final[str] = (
    "the .git entry in the folder git runs in is a link, so the gate does not run git"
)


def refuse_linked_git(folder: Path) -> None:
    """Raise when git must not run in *folder* (see :func:`nearest_linked_git_entry`).

    For a check that runs git in *folder* and reports a refusal as its
    ``check_error``. Raises :class:`GitEntryUnreadableError` when a ``.git``
    entry on git's search path could not be looked at, and
    :class:`GitEntryLinkedError` when one is a link (noted in the skip log).
    The message is :func:`linked_git_message`'s sentence, except for a link
    in *folder* itself: a ``--staged`` check keeps a hook's ``GIT_DIR``, so
    git may not read the link's target, and the sentence
    (:data:`STAGED_LINKED_GIT_MESSAGE`) says only that the gate does not run
    git. Returns when git may run.
    """
    entry = nearest_linked_git_entry(folder)
    if entry is None:
        return
    if git_entry_unreadable(entry):
        raise GitEntryUnreadableError(linked_git_message(folder, entry))
    if entry == folder / GIT_ENTRY:
        # A hook's ``GIT_DIR`` may name the repository git reads, so the
        # sentence says only what the gate did, not where git would go.
        raise GitEntryLinkedError(STAGED_LINKED_GIT_MESSAGE)
    raise GitEntryLinkedError(linked_git_message(folder, entry))


def _absent(exc: OSError, entry: Path) -> bool:
    """Return True when *exc* from ``os.lstat(entry)`` means nothing is there.

    On Windows a path too long, a bad path or an unreachable share also
    raise :class:`FileNotFoundError`. Only ``ERROR_FILE_NOT_FOUND`` (2)
    means the entry is absent, and ``ERROR_PATH_NOT_FOUND`` (3) when what
    would hold it is missing or is not a folder, such as a root that does not
    exist or is a file; ``os.lstat`` looks at it.
    """
    if isinstance(exc, NotADirectoryError):
        return True
    if not isinstance(exc, FileNotFoundError):
        return False
    code = getattr(exc, "winerror", None)
    if code in (None, 2):
        return True
    if code != 3:
        return False
    try:
        holder = os.lstat(entry.parent)
    except FileNotFoundError as missing:
        # The holder's own winerror 3 is judged the same way, up the chain,
        # so only a chain that ends in nothing there or in no folder counts.
        # A drive root is its own parent: reached that way, the chain ends
        # in nothing known, so the entry counts as unreadable.
        if entry.parent == entry.parent.parent:
            return False
        return _absent(missing, entry.parent)
    except (OSError, ValueError):
        return False
    return not stat.S_ISDIR(holder.st_mode)


# The .git entries :func:`nearest_linked_git_entry` returned because
# ``os.lstat`` could not look at them, by exact spelling.
_unreadable_entries: set[str] = set()


def git_entry_unreadable(entry: Path) -> bool:
    """Return True when :func:`nearest_linked_git_entry` could not look at *entry*.

    Such an entry is not a link: it is not in the skip log, and it gets its
    own sentence (:func:`linked_git_message`). The answer is what the guard
    found, not a second look.
    """
    return os.fspath(entry) in _unreadable_entries


def linked_git_label(root: Path, entry: Path) -> str:
    """Return how a report names *entry*, as the skip log names it.

    ``.git`` for the root's own entry, and the full path of one above the
    root.
    """
    try:
        return entry.relative_to(root).as_posix()
    except ValueError:
        return entry.as_posix()


def linked_git_message(root: Path, entry: Path) -> str:
    """Return the sentence for a check that did not run git because of *entry*.

    It names *entry* (see :func:`linked_git_label`) and nothing git printed.
    The root's own ``.git`` keeps the sentence it always had; an entry above
    the root may lie above a repository git would use first, so its sentence
    says only what the gate did.
    """
    if git_entry_unreadable(entry):
        return (
            f"the .git entry {linked_git_label(root, entry)} on git's search "
            "path could not be looked at, so the gate does not run git below it"
        )
    if entry == root / GIT_ENTRY:
        return "the .git entry is a link, so git would read another repository"
    return (
        f"the .git entry {linked_git_label(root, entry)} on git's search path "
        "is a link, so the gate does not run git below it"
    )


def is_git_entry(path: Path, listed: frozenset[str]) -> bool:
    """Return True when the listed entry *path* is the ``.git`` of its folder.

    *listed* holds the names in the folder's own listing. ``.git`` as listed
    is; another spelling of it in case (``.GIT``) is only when the listing
    holds no exact ``.git`` and the file system opens ``.git`` there as that
    same entry, judged by ``os.lstat`` and ``os.path.samestat``. Where the
    file system gives no file number (0, as some network and FUSE file
    systems do), the listing settles it: no exact ``.git`` is listed, yet
    ``.git`` opens, so the file system matched it to this entry. A
    case-sensitive folder (NTFS, APFS) can hold both, and git uses only
    ``.git``. A folder listing gives long names
    only, so a short name such as ``GIT~2`` is a name of its own.
    """
    if path.name == GIT_ENTRY:
        return True
    if path.name.lower() != GIT_ENTRY or GIT_ENTRY in listed:
        return False
    try:
        variant = os.lstat(path)
        exact = os.lstat(path.parent / GIT_ENTRY)
    except (OSError, ValueError):
        return False
    if variant.st_ino == 0 or exact.st_ino == 0:
        return True
    return os.path.samestat(variant, exact)


def nested_checkout(folder: Path, entries: list[tuple[Path, EntryKind]]) -> bool:
    """Return True when a walk skips *folder*, listed as *entries*, as a checkout.

    *folder* is below the root. Its ``.git`` entry, as listed (see
    :func:`is_git_entry`), decides. A link (dangling or not) or a special
    file marks a checkout for git too, but the folder is then left out
    because of that entry, so the entry is noted in the skip log. A ``.git``
    folder or file is a checkout only when it holds or names a repository
    (:func:`git_entry_state`): a plain ``.git`` file or an empty ``.git``
    folder is not one to git, so it does not hide its folder, and the walk
    goes on into it (never into the ``.git`` entry itself). Every folder this
    returns True for is noted in the checkout log (:func:`note_checkout`),
    which the report lists under ``skipped_checkouts`` and which never changes
    a verdict: one ``gitdir:`` line can make git, and so the walk, skip any
    folder.
    """
    listed = frozenset(path.name for path, _ in entries)
    git_entries = [(path, kind) for path, kind in entries if is_git_entry(path, listed)]
    if not git_entries:
        return False
    linked = [path for path, kind in git_entries if kind not in (DIR_ENTRY, FILE_ENTRY)]
    for path in linked:
        note_skipped(path)
    if linked or git_entry_state(folder) == GIT_ENTRY_REPOSITORY:
        note_checkout(folder)
        return True
    return False


def iter_tree_files(
    root: Path,
    suffixes: Iterable[str] = (),
    *,
    names: Iterable[str] = (),
    extra_prune: Iterable[str] = (),
    prune: bool = True,
    include_links: bool = False,
) -> Iterator[Path]:
    """Yield the matching regular files below ``root``, skipping pruned subtrees.

    Pre-conditions: ``root`` is an existing directory. ``suffixes`` are file
    name endings (``".md"``) and ``names`` exact file names (``"README.md"``);
    a file matching either is yielded, and with both empty every file is.
    Matching follows the host's file-name case rules, as ``Path.rglob`` does.
    ``extra_prune`` adds directory names to :data:`PRUNED_SEGMENTS`.
    ``prune=False`` drops the default pruning, so nested checkouts and the
    names in :data:`PRUNED_SEGMENTS` are walked too (``extra_prune`` still
    applies): the files a former ``Path.rglob`` caller saw, minus links.
    ``include_links=True`` yields each link by its own name, never entering
    it, for a caller that checks names and reads nothing.
    Post-conditions: yields regular files as ``root``-prefixed paths,
    directory by directory in name order, so a run is deterministic. The walk
    never enters a nested checkout (a directory below ``root`` whose ``.git``
    file or directory holds or names a repository, see
    :func:`nested_checkout`; ``root`` itself is never nested, even when its
    ``.git`` is a file), a directory named in the pruned set, or a link to a
    folder (a symbolic link or a Windows junction), and never yields a link, a
    named pipe, a device or a socket; each one it leaves out is noted in the
    skip log (see ``_project_paths``). A link that points inside ``root`` is
    skipped too; what it points to is yielded under its own path when the
    walk reaches it. A nested checkout whose ``.git`` is a link or a special
    file is noted by that entry, and a directory it cannot list (no access,
    a path too long) by its own path (see ``scan_entries``).
    """
    # Names match as the host's path rules spell them (os.path.normcase);
    # ``.git`` is judged on its own (:func:`is_git_entry`).
    extra = frozenset(extra_prune)
    pruned = frozenset(
        os.path.normcase(name)
        for name in (PRUNED_SEGMENTS.union(extra) if prune else extra)
        if name != GIT_ENTRY
    )
    prune_git = prune or GIT_ENTRY in extra
    wanted_suffixes = tuple(os.path.normcase(suffix) for suffix in suffixes)
    wanted_names = frozenset(os.path.normcase(name) for name in names)
    match_all = not wanted_suffixes and not wanted_names

    def wanted(name: str) -> bool:
        folded = os.path.normcase(name)
        return match_all or folded in wanted_names or folded.endswith(wanted_suffixes)

    # Depth first, files before folders, each in name order: the order a
    # top-down os.walk with sorted folder names gives. Each folder is listed
    # with os.scandir and every entry is classified without following it.
    stack: list[tuple[Path, bool]] = [(root, True)]
    while stack:
        folder, is_root = stack.pop()
        entries = scan_entries(folder)
        # The root's own ``.git`` marks the checkout being inspected; one
        # below it that holds or names a repository marks a nested checkout,
        # which is skipped whole (:func:`nested_checkout`).
        listed = frozenset(path.name for path, _ in entries)
        if prune and not is_root and nested_checkout(folder, entries):
            continue
        files: list[Path] = []
        folders: list[Path] = []
        for path, kind in sorted(entries, key=lambda entry: entry[0].name):
            if (
                os.path.normcase(path.name) in pruned
                or (prune_git and is_git_entry(path, listed))
            ) and kind in (DIR_ENTRY, LINK_ENTRY):
                if kind == LINK_ENTRY:
                    note_skipped(path)
                continue
            if kind == DIR_ENTRY:
                folders.append(path)
            elif kind == FILE_ENTRY:
                if wanted(path.name):
                    files.append(path)
            elif kind == LINK_ENTRY and include_links and wanted(path.name):
                # A caller that checks names only gets the link by its own
                # name; the walk still never enters it.
                files.append(path)
            elif kind in (LINK_ENTRY, SKIPPED_FOLDER_ENTRY) or wanted(
                as_opened(path.name)
            ):
                # A link may hide a folder or a file; a pipe, device or socket
                # with a wanted name would make the read wait or never end.
                note_skipped(path)
        yield from files
        stack.extend((path, False) for path in reversed(folders))


# ---------------------------------------------------------------------------
# Shared prose-line stripper
# ---------------------------------------------------------------------------
#
# The Markdown-prose matchers (hedging, completion_claim, agnosticism,
# freshness_token, binding_reciprocity) each re-implemented the identical
# fenced-code toggle loop: walk the lines, flip an ``inside_fence`` flag on a
# fence delimiter, skip fenced lines, and — for the two matchers that also
# exclude inline-code spans — blank those spans column-preservingly before
# scanning. The families diverge only in two parameters (the fence-delimiter
# regex and whether inline-code spans are blanked), so the loop is hoisted here
# as a parametrized generator. Each matcher passes its own regexes, preserving
# its exact matching behaviour: the column-0 fence form (``^```) or the
# indent-tolerant form (``^[ \t]*```), with or without inline blanking.
def _blank_span(match: re.Match[str]) -> str:
    """Replace a matched span with equal-length spaces (column-preserving)."""
    return " " * len(match.group(0))


def iter_prose_lines(
    lines: Iterable[str],
    *,
    fence_re: re.Pattern[str],
    inline_blank_re: re.Pattern[str] | None = None,
    start: int = 1,
) -> Iterator[tuple[int, str, str]]:
    """Yield ``(line_number, raw_line, scanned_line)`` for non-fenced lines.

    Pre-conditions: ``lines`` is an iterable of already-split lines (no trailing
    newlines); ``fence_re`` matches a fenced-code delimiter; ``inline_blank_re``,
    when given, matches an inline-code span to blank column-preservingly.
    Post-conditions: a line inside a fenced block (delimited by ``fence_re``,
    opening and closing fences both toggling the state) is skipped; every other
    line is yielded with a 1-based number offset by ``start``. ``scanned_line``
    is ``raw_line`` with each ``inline_blank_re`` span replaced by equal-length
    spaces when ``inline_blank_re`` is supplied, else ``raw_line`` unchanged.
    """
    inside_fence = False
    for line_number, raw_line in enumerate(lines, start=start):
        if fence_re.match(raw_line):
            inside_fence = not inside_fence
            continue
        if inside_fence:
            continue
        scanned = (
            inline_blank_re.sub(_blank_span, raw_line)
            if inline_blank_re is not None
            else raw_line
        )
        yield line_number, raw_line, scanned


class _Finding(Protocol):
    """Structural marker for a per-matcher finding dataclass.

    Documentation only — not enforced at runtime or by the type checker:
    ``GrepResult.findings`` is typed loosely and each frozen finding dataclass
    is serialized by duck-typing through ``dataclasses.asdict``. This Protocol
    records the shape matcher findings are expected to satisfy; it is not wired
    as a bound on ``findings``.
    """


@dataclass(frozen=True)
class GrepResult:
    """Canonical path-based matcher report.

    Pre-conditions: ``findings`` holds the matcher-specific finding dataclasses
    (each a frozen ``@dataclass``). ``check_error``, when set, says why the
    check could not finish, and the caller sets ``passed`` to false with it.
    Post-conditions: ``to_json`` emits the canonical ``{grep, path, passed,
    findings}`` payload, including ``note`` and ``check_error`` only when they
    are not ``None``.
    """

    grep: str
    path: str | None
    passed: bool
    findings: list[Any] = field(default_factory=list)
    note: str | None = None
    check_error: str | None = None

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, path, passed,
        findings}``; each finding is flattened through ``dataclasses.asdict``.

        ``note`` and ``check_error`` are emitted only when they are not
        ``None``.
        """
        payload: dict[str, object] = {
            "grep": self.grep,
            "path": self.path,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        if self.note is not None:
            payload["note"] = self.note
        if self.check_error is not None:
            payload[CHECK_ERROR_KEY] = self.check_error
        return json.dumps(payload, indent=2)


def parse_path_input(
    argv: list[str],
    *,
    prog: str,
    doc: str | None = None,
    configure: Callable[[argparse.ArgumentParser], None] | None = None,
) -> tuple[argparse.Namespace, str, Path | None]:
    """Parse a per-file matcher's arguments and read its input.

    Pre-conditions: ``argv`` is ``sys.argv``. ``configure`` adds
    matcher-specific flags.
    Post-conditions: returns ``(namespace, content, path)``; ``--help`` exits
    0 and a usage error (unknown flag, missing file) exits :data:`EXIT_USAGE`.
    """
    parser = make_parser(prog, doc)
    add_path_arguments(parser)
    if configure is not None:
        configure(parser)
    args = parser.parse_args(argv[1:])
    content, path = read_path_arguments(parser, args)
    return args, content, path


def run_grep(
    check: Callable[[str, Path | None], GrepResult],
    argv: list[str],
) -> int:
    """Run ``check`` over the resolved input, print the report, return the exit.

    Pre-conditions: ``check`` returns a :class:`GrepResult`. Post-conditions:
    the JSON report is printed to stdout; the return is ``EXIT_PASS`` when the
    result passed, ``EXIT_FAIL`` otherwise. ``--help`` and usage errors follow
    the shared command-line contract (exit 0 and :data:`EXIT_USAGE`).
    """
    prog, doc = _entry_identity(check, argv)
    _args, content, path = parse_path_input(argv, prog=prog, doc=doc)
    result = check(content, path)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


# ---------------------------------------------------------------------------
# Root-based standalone matchers
# ---------------------------------------------------------------------------
#
# The corpus-level standalone validators (``check(root) -> RootGrepResult``)
# each re-implement a byte-near-identical ``root``-based ``GrepResult`` +
# ``to_json`` + ``_read_input`` / ``_main`` skeleton. The types below hoist that
# boilerplate the same way ``GrepResult`` / ``run_grep`` hoist the path-based
# skeleton: the ``{grep, root, passed, advisory, findings}`` payload shape and
# the ``EXIT_PASS`` / ``EXIT_FAIL`` exit codes. The root comes from
# :func:`parse_root_args` (resolved, and required to exist) and the printed
# report carries the ``inspected`` count from :func:`finish_root_report`.


@dataclass(frozen=True)
class RootGrepResult:
    """Canonical root-based standalone-matcher report.

    Pre-conditions: ``findings`` holds the matcher-specific finding dataclasses
    (each a frozen ``@dataclass``). Post-conditions: ``to_json`` emits the
    canonical ``{grep, root, passed, advisory, findings}`` payload. ``advisory``
    is always serialised (unlike ``GrepResult.note``, which is conditional) so a
    consumer can read the advisory disposition without inferring it.
    """

    grep: str
    root: str
    passed: bool
    advisory: bool = False
    findings: list[Any] = field(default_factory=list)
    # How many targets the run examined. Not part of ``to_json``: the CLI
    # stamps it on the printed report through :func:`finish_root_report`.
    inspected: int = 0

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, passed, advisory,
        findings}``; each finding is flattened through ``dataclasses.asdict``.
        """
        payload: dict[str, object] = {
            "grep": self.grep,
            "root": self.root,
            "passed": self.passed,
            "advisory": self.advisory,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def run_root_grep(
    check: Callable[[Path], RootGrepResult],
    argv: list[str],
) -> int:
    """Run a root-based ``check``, print the report, return the exit code.

    Pre-conditions: ``check`` returns a :class:`RootGrepResult` whose
    ``inspected`` counts the targets the run examined. Post-conditions: the root is
    parsed and resolved per :func:`parse_root_args`; the JSON report, stamped
    with ``inspected``, is printed per :func:`finish_root_report`, whose exit
    contract this returns. A matcher whose ``--strict``-gated advisory posture
    differs keeps its own ``_main`` and calls only the dataclass.
    """
    prog, doc = _entry_identity(check, argv)
    root = parse_root_args(argv, prog=prog, doc=doc).root
    result = check(root)
    return finish_root_report(
        result.to_json(),
        passed=result.passed,
        inspected=result.inspected,
        advisory=result.advisory,
    )
