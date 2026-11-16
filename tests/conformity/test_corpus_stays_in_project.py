# SPDX-License-Identifier: MIT

"""The ``--all-perwrite`` corpus reads only regular files inside the project.

Why these tests exist. A project can arrive with its ``.git`` folder from
someone else, in an archive or a shared folder. The corpus runner lists the
tracked files with ``git ls-files`` and reads each one, so the project's own
index, working tree and git configuration decide what it would read:

- git lists an index entry exactly as the index stores it, so a hand-written
  index can list ``../outside.yml`` or an absolute path;
- a tracked file can be a symbolic link, and a folder on the way to it a
  symbolic link or a Windows junction, pointing outside the project;
- a tracked path can be a FIFO in the working tree, or a link to a device such
  as ``/dev/zero``, where a read waits or never ends;
- the repository's configuration can make ``git ls-files`` itself wait for
  ever, for example through an ``include.path`` that names a FIFO.

Every file outside the project holds an unpinned ``uses:`` ref, a blocking
finding, so reading it fails the run. Each repository is a throwaway one in
``tmp_path``, built with fixture git under :func:`hermetic_git_env`. A test
that can wait on a FIFO runs the gate on a thread and then lets the waiting
read go, and the ``/dev/zero`` test runs the gate in a child process with a
memory limit, so a regression fails the test instead of hanging the run or
using up the machine's memory.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import pytest

from apothem.conformity import gate, no_global_plans_grep
from tests._shared.git_env import hermetic_git_env

_T = TypeVar("_T")

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Split so the license scanner does not read the fixture text as this file's
# own license tag.
_SPDX_HASH = "# SPDX-License-" + "Identifier: MIT"

# The one file inside each project; it raises no blocking finding.
_CLEAN_PY = f"{_SPDX_HASH}\n\ndef h(x: int) -> int:\n    return x\n"

# A workflow with an unpinned ``uses:`` ref, a blocking finding. Every file
# outside a project holds it, so a read of one shows as a blocking result.
_UNPINNED_WORKFLOW = (
    f"{_SPDX_HASH}\n\n"
    "name: ci\non: [push]\n"
    "jobs:\n  build:\n    runs-on: ubuntu-latest\n"
    "    steps:\n      - uses: actions/checkout@v4\n"
)

# How long a run may take before a test calls it stalled.
_DEADLINE_SECONDS = 30.0
# The ls-files timeout the FIFO tests set, so a waiting git ends quickly.
_SHORT_TIMEOUT_SECONDS = 2
# Address-space limit for the child process that meets /dev/zero: a read of
# the device then fails fast with MemoryError instead of using up memory.
_CHILD_ADDRESS_SPACE_BYTES = 1 << 30

_POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt", reason="FIFOs and /dev/zero exist only on POSIX systems"
)


def _git(repo: Path, *args: str) -> str:
    """Run fixture git in *repo* without the host's git configuration."""
    done = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        env=hermetic_git_env(),
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return done.stdout


def _write(repo: Path, files: dict[str, str]) -> Path:
    """Write *files* (relative path to text) under *repo*."""
    for rel, body in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return repo


def _commit_tree(repo: Path) -> Path:
    """Make *repo* a git repository with everything in it committed."""
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@apothem.invalid")
    _git(repo, "config", "user.name", "apothem-test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed")
    return repo


def _project(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    """Return a committed project holding ``clean.py`` plus *files*."""
    repo = _write(tmp_path / "project", {"clean.py": _CLEAN_PY, **(files or {})})
    return _commit_tree(repo)


def _write_index(repo: Path, names: list[str]) -> None:
    """Replace *repo*'s index with one that lists *names* exactly as given.

    git refuses to add a path with a ``..`` part or a leading ``/``, but it
    lists whatever a hand-written index holds. This writes a version-2 index:
    a twelve-byte header, one entry per name in byte order (each pointing at
    the empty blob), and a SHA-1 checksum. ``git ls-files`` reads only the
    names.
    """
    empty_blob = hashlib.sha1(b"blob 0\0", usedforsecurity=False).digest()
    body = b""
    for name in sorted(item.encode("utf-8") for item in names):
        entry = struct.pack(">10I", 0, 0, 0, 0, 0, 0, 0o100644, 0, 0, 0) + empty_blob
        entry += struct.pack(">H", min(len(name), 0xFFF)) + name
        entry += b"\0" * (8 - len(entry) % 8)
        body += entry
    data = b"DIRC" + struct.pack(">II", 2, len(names)) + body
    checksum = hashlib.sha1(data, usedforsecurity=False).digest()
    (repo / ".git" / "index").write_bytes(data + checksum)


def _symlink_or_skip(link: Path, target: Path) -> None:
    """Make *link* a symbolic link to *target*, or skip where that is not allowed."""
    try:
        link.symlink_to(target)
    except OSError as exc:  # Windows without the symbolic-link privilege
        pytest.skip(f"cannot create a symbolic link here: {exc}")


def _link_folder(link: Path, target: Path) -> None:
    """Make *link* a folder link to *target*.

    Windows gets a junction, which needs no special privilege; other systems
    get a symbolic link.
    """
    if os.name == "nt":
        winapi = pytest.importorskip("_winapi")
        winapi.CreateJunction(str(target), str(link))
        return
    link.symlink_to(target, target_is_directory=True)


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


def _run(repo: Path) -> dict[str, object]:
    """Run ``--all-perwrite`` over *repo* in this process; return its payload."""
    passed, payload_json = gate._run_all_perwrite(repo)
    payload: dict[str, object] = json.loads(payload_json)
    assert payload["passed"] is passed
    return payload


# The child process for the /dev/zero test. It limits its address space, so a
# read of the device fails with MemoryError, then prints the gate's payload.
_CHILD_SCRIPT = """
import resource
import sys
from pathlib import Path

limit = int(sys.argv[2])
try:
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
except (OSError, ValueError):
    pass

from apothem.conformity import gate

print(gate._run_all_perwrite(Path(sys.argv[1]))[1])
"""


def _run_in_child(repo: Path) -> dict[str, object]:
    """Run ``--all-perwrite`` over *repo* in a memory-limited child process."""
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            _CHILD_SCRIPT,
            str(repo),
            str(_CHILD_ADDRESS_SPACE_BYTES),
        ],
        capture_output=True,
        encoding="utf-8",
        env=env,
        timeout=_DEADLINE_SECONDS * 4,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    payload: dict[str, object] = json.loads(done.stdout)
    return payload


def _assert_only_clean_file_read(payload: dict[str, object]) -> None:
    """The run read ``clean.py`` alone and passed: nothing outside was read."""
    assert payload["blocking"] == [], payload["blocking"]
    assert payload["files_scanned"] == 1
    assert payload["passed"] is True


# --- Paths that leave the project -------------------------------------------


def test_index_entries_outside_the_project_are_not_read(tmp_path: Path) -> None:
    """An index entry with a ``..`` part or an absolute path is skipped.

    git lists these names as written. Joined to the project folder they name
    files above it (``..``) or anywhere on the disk (an absolute path replaces
    the folder it is joined to).
    """
    repo = _project(tmp_path)
    above = tmp_path / "above.yml"
    absolute = tmp_path / "absolute.yml"
    for outside in (above, absolute):
        outside.write_text(_UNPINNED_WORKFLOW, encoding="utf-8")
    (repo / "sub").mkdir()
    names = [
        "clean.py",
        "../above.yml",
        "sub/../../above.yml",
        "sub\\..\\..\\above.yml",
        absolute.as_posix(),
    ]
    _write_index(repo, names)
    listed = _git(repo, "ls-files", "-z").split("\0")
    assert "../above.yml" in listed  # git lists the entry as written

    _assert_only_clean_file_read(_run(repo))


def test_tracked_link_to_a_file_outside_the_project_is_not_read(
    tmp_path: Path,
) -> None:
    """A tracked symbolic link is skipped, not followed.

    git tracks a link as the path it holds. Following it reads a file the
    project does not contain; reading the link's own text would report
    findings for a file that has no content of its own.
    """
    outside = _write(tmp_path / "elsewhere", {"ci.yml": _UNPINNED_WORKFLOW})
    repo = _write(tmp_path / "project", {"clean.py": _CLEAN_PY})
    _symlink_or_skip(repo / "ci.yml", outside / "ci.yml")
    _commit_tree(repo)
    assert "ci.yml" in _git(repo, "ls-files").splitlines()

    _assert_only_clean_file_read(_run(repo))


def test_tracked_link_inside_the_project_leaves_its_target_to_its_own_path(
    tmp_path: Path,
) -> None:
    """A link that points inside the project is skipped too.

    The tracked file it points to is read under its own path, so a finding
    there is reported once, for that file, and not again for the link.
    """
    repo = _write(
        tmp_path / "project",
        {"clean.py": _CLEAN_PY, "real.yml": _UNPINNED_WORKFLOW},
    )
    _symlink_or_skip(repo / "alias.yml", Path("real.yml"))
    _commit_tree(repo)

    payload = _run(repo)
    assert payload["files_scanned"] == 2
    blocking = payload["blocking"]
    assert isinstance(blocking, list)
    assert [entry["files"] for entry in blocking] == [["real.yml"]]


def test_folder_link_on_the_way_to_a_tracked_file_is_not_followed(
    tmp_path: Path,
) -> None:
    """A tracked file under a folder that is now a link is skipped.

    The index still lists ``linked/ci.yml`` after the ``linked`` folder is
    replaced with a link to a folder outside the project, so checking only
    the last part of the path would still read the outside file.
    """
    outside = _write(tmp_path / "elsewhere", {"ci.yml": _UNPINNED_WORKFLOW})
    repo = _project(tmp_path, {"linked/ci.yml": "placeholder: true\n"})
    shutil.rmtree(repo / "linked")
    _link_folder(repo / "linked", outside)
    assert "linked/ci.yml" in _git(repo, "ls-files").splitlines()

    _assert_only_clean_file_read(_run(repo))


# --- Paths that are not regular files ----------------------------------------


@_POSIX_ONLY
def test_fifo_in_the_working_tree_is_not_opened(tmp_path: Path) -> None:
    """A tracked path that is a FIFO on disk is skipped; opening it would wait."""
    repo = _project(tmp_path, {"notes.md": "notes\n"})
    fifo = repo / "notes.md"
    fifo.unlink()
    os.mkfifo(fifo)

    payload = _run_guarded(lambda: _run(repo), release=lambda: _release_fifo(fifo))
    _assert_only_clean_file_read(payload)


@_POSIX_ONLY
def test_tracked_link_to_a_device_is_not_read(tmp_path: Path) -> None:
    """A tracked link to ``/dev/zero`` is skipped; reading it would never end."""
    device = Path("/dev/zero")
    if not device.exists():
        pytest.skip("this system has no /dev/zero")
    repo = _write(tmp_path / "project", {"clean.py": _CLEAN_PY})
    (repo / "zero.md").symlink_to(device)
    _commit_tree(repo)

    _assert_only_clean_file_read(_run_in_child(repo))


# --- The git ls-files timeout ------------------------------------------------


def _timing_out_run(
    *args: object, **kwargs: object
) -> subprocess.CompletedProcess[str]:
    """Stand in for ``subprocess.run``: every git call runs past its timeout."""
    timeout = kwargs.get("timeout")
    raise subprocess.TimeoutExpired(
        cmd="git", timeout=timeout if isinstance(timeout, (int, float)) else 0
    )


def test_both_ls_files_calls_carry_a_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The corpus listing and the plans check each give git a time limit."""
    repo = _project(tmp_path)
    timeouts: list[object] = []
    real_run = subprocess.run

    def recording_run(*args: object, **kwargs: object) -> object:
        timeouts.append(kwargs.get("timeout"))
        return real_run(*args, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(subprocess, "run", recording_run)
    gate._corpus_tracked_files(repo)
    no_global_plans_grep._git_ls_files(repo)

    assert len(timeouts) == 2
    for timeout in timeouts:
        assert isinstance(timeout, (int, float))
        assert timeout > 0


def test_corpus_listing_timeout_does_not_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A listing that runs past its timeout reports the reason and no pass."""
    monkeypatch.setattr(subprocess, "run", _timing_out_run)

    payload = _run(tmp_path)
    assert payload["passed"] is False
    assert payload["files_scanned"] == 0
    assert payload["empty_scope_expected"] is False
    assert "did not finish" in str(payload["corpus_error"])
    strict = gate.main(
        ["gate", gate.ALL_PERWRITE_FLAG, str(tmp_path), gate.STRICT_FLAG]
    )
    assert strict == gate.EXIT_FAIL


def test_plans_check_reports_a_listing_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The plans check turns a listing timeout into its error, not a crash."""
    monkeypatch.setattr(subprocess, "run", _timing_out_run)

    with pytest.raises(RuntimeError, match="did not finish"):
        no_global_plans_grep._git_ls_files(tmp_path)


@_POSIX_ONLY
def test_corpus_listing_that_waits_on_its_configuration_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``include.path`` naming a FIFO makes git wait; the timeout ends the run."""
    repo = _project(tmp_path)
    fifo = tmp_path / "config-fifo"
    _include_fifo(repo, fifo)
    monkeypatch.setattr(
        gate, "GIT_LS_FILES_TIMEOUT_SECONDS", _SHORT_TIMEOUT_SECONDS, raising=False
    )

    payload = _run_guarded(lambda: _run(repo), release=lambda: _release_fifo(fifo))
    assert payload["passed"] is False
    assert payload["files_scanned"] == 0
    assert "did not finish" in str(payload["corpus_error"])


@_POSIX_ONLY
def test_plans_check_listing_that_waits_on_its_configuration_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The plans check's own ``git ls-files`` ends at its timeout too."""
    repo = _project(tmp_path)
    fifo = tmp_path / "config-fifo"
    _include_fifo(repo, fifo)
    monkeypatch.setattr(
        no_global_plans_grep,
        "GIT_LS_FILES_TIMEOUT_SECONDS",
        _SHORT_TIMEOUT_SECONDS,
        raising=False,
    )

    def list_files() -> None:
        with pytest.raises(RuntimeError, match="did not finish"):
            no_global_plans_grep._git_ls_files(repo)

    _run_guarded(list_files, release=lambda: _release_fifo(fifo))


# --- A run that reads no file does not pass ----------------------------------


def test_folder_outside_a_git_work_tree_does_not_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no tracked-file list there is no corpus, so the run cannot pass."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    _write(tmp_path, {"clean.py": _CLEAN_PY})

    payload = _run(tmp_path)
    assert payload["passed"] is False
    assert payload["files_scanned"] == 0
    assert payload["corpus_error"]


def test_run_that_reads_no_file_does_not_pass(tmp_path: Path) -> None:
    """A listed corpus with nothing to read reports an empty scope, not a pass."""
    repo = _commit_tree(_write(tmp_path / "project", {"logo.png": "not an image\n"}))

    payload = _run(repo)
    assert payload["passed"] is False
    assert payload["files_scanned"] == 0
    assert payload["empty_scope_expected"] is False
    assert "corpus_error" not in payload
    strict = gate.main(["gate", gate.ALL_PERWRITE_FLAG, str(repo), gate.STRICT_FLAG])
    assert strict == gate.EXIT_FAIL
