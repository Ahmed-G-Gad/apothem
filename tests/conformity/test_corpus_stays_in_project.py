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
import importlib
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

from apothem.conformity import gate, link_check, no_global_plans_grep
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
# The largest file the corpus run reads (``_corpus.MAX_FILE_BYTES``).
_MAX_FILE_BYTES = 8 * 1024 * 1024
# The fixed start of the reason a failed ``git ls-files`` reports.
_GIT_FAILED = "git ls-files failed with exit code"

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


def _write_index(
    repo: Path,
    names: list[str | bytes | tuple[str, int, int]],
    *,
    modes: dict[str, int] | None = None,
) -> None:
    """Replace *repo*'s index with one that lists *names* exactly as given.

    git refuses to add a path with a ``..`` part or a leading ``/``, but it
    lists whatever a hand-written index holds. This writes a version-2 index:
    a twelve-byte header, one entry per name in byte order (each pointing at
    the empty blob), and a SHA-1 checksum. ``git ls-files`` reads only the
    names, modes and stages. A ``bytes`` name is written as is, so it can hold
    bytes that are not UTF-8. *modes* maps a ``str`` name to its index mode,
    such as ``0o120000`` for a link; every other entry is a regular file. A
    ``(name, mode, stage)`` tuple writes one stage of a file with a merge
    conflict (1 the common base, 2 ours, 3 theirs).
    """
    empty_blob = hashlib.sha1(b"blob 0\0", usedforsecurity=False).digest()
    chosen = modes or {}
    entries: list[tuple[bytes, int, int]] = []
    for item in names:
        if isinstance(item, tuple):
            entries.append((item[0].encode("utf-8"), item[2], item[1]))
        elif isinstance(item, bytes):
            entries.append((item, 0, 0o100644))
        else:
            entries.append((item.encode("utf-8"), 0, chosen.get(item, 0o100644)))
    body = b""
    for name, stage, mode in sorted(entries):
        entry = struct.pack(">10I", 0, 0, 0, 0, 0, 0, mode, 0, 0, 0) + empty_blob
        entry += struct.pack(">H", (stage << 12) | min(len(name), 0xFFF)) + name
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


def _assert_only_clean_file_read(
    payload: dict[str, object], *, passed: bool = True
) -> None:
    """The run read ``clean.py`` alone: nothing outside was read."""
    assert payload["blocking"] == [], payload["blocking"]
    assert payload["files_scanned"] == 1
    assert payload["passed"] is passed


def _skipped(payload: dict[str, object]) -> dict[str, int]:
    """Return the payload's non-zero ``files_skipped`` counts by reason."""
    skipped = payload["files_skipped"]
    assert isinstance(skipped, dict)
    return {reason: count for reason, count in skipped.items() if count}


# --- Paths that leave the project -------------------------------------------


def test_index_entries_outside_the_project_are_not_read(tmp_path: Path) -> None:
    """An index entry with a ``..`` part or an absolute path is skipped.

    git lists these names as written. Joined to the project folder they name
    files above it (``..``) or anywhere on the disk (an absolute path replaces
    the folder it is joined to). git never writes such an entry itself, so the
    run counts them and does not pass.
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

    payload = _run(repo)
    _assert_only_clean_file_read(payload, passed=False)
    # Read as git reads a name, split on "/", the backslash entry is one file
    # name, and on Windows the absolute one is a folder named "C:". git on
    # another system can write both, so on Windows, where neither name can be
    # held as written, they are counted as unsupported names, not as entries
    # that leave the project. Elsewhere the backslash entry is just missing.
    expected = (
        {"outside_project": 2, "unsupported_name": 2}
        if os.name == "nt"
        else {"outside_project": 3, "missing": 1}
    )
    assert _skipped(payload) == expected


def test_name_with_a_colon_is_not_counted_as_leaving_the_project(
    tmp_path: Path,
) -> None:
    """A name such as ``a:b.py``, which git on Linux or macOS tracks, passes.

    On Windows the part before the colon reads as a drive, so the file is
    skipped as an unsupported name; elsewhere it is an ordinary file.
    """
    repo = _project(tmp_path)
    if os.name != "nt":
        (repo / "a:b.py").write_text(_CLEAN_PY, encoding="utf-8")
    _write_index(repo, ["clean.py", "a:b.py"])

    payload = _run(repo)
    assert payload["passed"] is True
    if os.name == "nt":
        assert payload["files_scanned"] == 1
        assert _skipped(payload) == {"unsupported_name": 1}
    else:
        assert payload["files_scanned"] == 2
        assert _skipped(payload) == {}


def test_link_in_any_stage_of_a_merge_conflict_counts_as_a_link(
    tmp_path: Path,
) -> None:
    """During a merge conflict the index holds several modes for one name; a
    link in any of them is enough to skip the file."""
    repo = _project(tmp_path, {"alias.yml": "real.yml"})
    _write_index(
        repo,
        [
            "clean.py",
            ("alias.yml", 0o100644, 1),
            ("alias.yml", 0o120000, 2),
            ("alias.yml", 0o100644, 3),
        ],
    )

    payload = _run(repo)
    _assert_only_clean_file_read(payload)
    assert _skipped(payload) == {"link": 1}


def test_missing_root_reports_a_git_failure(tmp_path: Path) -> None:
    """A root that is gone is git's own error, reported with its exit code."""
    payload = _run(tmp_path / "missing")
    assert payload["passed"] is False
    assert str(payload["check_error"]).startswith(_GIT_FAILED)


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
    assert payload["check_error"] == "git ls-files did not finish within 60 seconds"
    _assert_exit_codes_for_a_run_that_did_not_pass(tmp_path)


def test_plans_check_reports_a_listing_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The plans check turns a listing timeout into its error, not a crash."""
    monkeypatch.setattr(subprocess, "run", _timing_out_run)

    with pytest.raises(RuntimeError, match="did not finish"):
        no_global_plans_grep._git_ls_files(tmp_path)


def test_plans_check_reports_a_listing_timeout_as_a_check_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The plans check's report carries the timeout as ``check_error``, the key
    the corpus run uses for a check that did not finish, and fails."""
    monkeypatch.setattr(subprocess, "run", _timing_out_run)

    code = no_global_plans_grep._main(["no-global-plans-grep", str(tmp_path)])
    report = json.loads(capsys.readouterr().out)
    assert code == no_global_plans_grep.EXIT_FAIL
    assert report["passed"] is False
    assert report["check_error"] == "git ls-files did not finish within 60 seconds"
    assert report["inspected"] == 0
    assert report["empty_scope_expected"] is False


def test_plans_check_leaves_git_error_text_out(tmp_path: Path) -> None:
    """The plans check's git failure names git's exit code, not git's own text,
    which can name files outside the project."""
    repo = _project(tmp_path)
    secret = _write(tmp_path / "outside", {"secret.cfg": "this is not git config\n"})
    with (repo / ".git" / "config").open("a", encoding="utf-8") as config:
        config.write(f"[include]\n\tpath = {(secret / 'secret.cfg').as_posix()}\n")

    with pytest.raises(RuntimeError, match="git ls-files failed under") as caught:
        no_global_plans_grep._git_ls_files(repo)
    assert "exit code" in str(caught.value)
    assert "secret" not in str(caught.value)


@_POSIX_ONLY
def test_corpus_listing_that_waits_on_its_configuration_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``include.path`` naming a FIFO makes git wait; the timeout ends the run."""
    repo = _project(tmp_path)
    fifo = tmp_path / "config-fifo"
    _include_fifo(repo, fifo)
    corpus = importlib.import_module("apothem.conformity._corpus")
    monkeypatch.setattr(corpus, "GIT_LS_FILES_TIMEOUT_SECONDS", _SHORT_TIMEOUT_SECONDS)

    payload = _run_guarded(lambda: _run(repo), release=lambda: _release_fifo(fifo))
    assert payload["passed"] is False
    assert payload["files_scanned"] == 0
    assert "did not finish" in str(payload["check_error"])


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
    assert str(payload["check_error"]).startswith(_GIT_FAILED)


def test_run_that_reads_no_file_does_not_pass(tmp_path: Path) -> None:
    """A listed corpus with nothing to read reports an empty scope, not a pass."""
    repo = _commit_tree(_write(tmp_path / "project", {"logo.png": "not an image\n"}))

    payload = _run(repo)
    assert payload["passed"] is False
    assert payload["files_scanned"] == 0
    assert payload["empty_scope_expected"] is False
    assert "check_error" not in payload
    _assert_exit_codes_for_a_run_that_did_not_pass(repo)


# --- What the report says about paths it did not read --------------------------


def test_paths_the_run_did_not_read_are_counted_by_reason(tmp_path: Path) -> None:
    """Each listed path that is not read leaves a count under its reason.

    A tracked file missing from the working tree, a folder link, a file whose
    bytes are not UTF-8 text and a file over the size limit are each counted,
    so a pass that left most entries unread shows it.
    """
    outside = _write(tmp_path / "elsewhere", {"ci.yml": _UNPINNED_WORKFLOW})
    repo = _project(
        tmp_path,
        {
            "gone.md": "gone\n",
            "linked/ci.yml": "placeholder: true\n",
            "blob.txt": "text for now\n",
            "big.yml": "small for now\n",
        },
    )
    (repo / "gone.md").unlink()
    shutil.rmtree(repo / "linked")
    _link_folder(repo / "linked", outside)
    (repo / "blob.txt").write_bytes(b"\xff\xfe\x00 not text")
    with (repo / "big.yml").open("wb") as big:  # one byte over the limit
        big.write(_UNPINNED_WORKFLOW.encode("utf-8"))
        big.seek(_MAX_FILE_BYTES)
        big.write(b"\n")

    payload = _run(repo)
    _assert_only_clean_file_read(payload)
    assert _skipped(payload) == {
        "link": 1,
        "missing": 1,
        "too_large": 1,
        "not_utf8_text": 1,
    }


def test_index_modes_for_links_and_submodules_are_skipped(tmp_path: Path) -> None:
    """An entry the index marks as a link or a submodule is not read.

    With ``core.symlinks=false``, git writes a tracked link as a regular file
    that holds the path it points to, so only the index mode shows it is a
    link. A submodule's entry names a folder.
    """
    repo = _project(tmp_path, {"alias.yml": "real.yml", "lib/README.md": "lib\n"})
    _write_index(
        repo,
        ["clean.py", "alias.yml", "lib"],
        modes={"alias.yml": 0o120000, "lib": 0o160000},
    )

    payload = _run(repo)
    _assert_only_clean_file_read(payload)
    assert _skipped(payload) == {"link": 1, "submodule": 1}


# --- When the file list cannot be read ------------------------------------------


def _assert_exit_codes_for_a_run_that_did_not_pass(root: Path) -> None:
    """The advisory default still exits 0; ``--strict`` exits 2."""
    assert gate.main(["gate", gate.ALL_PERWRITE_FLAG, str(root)]) == gate.EXIT_PASS
    strict = gate.main(["gate", gate.ALL_PERWRITE_FLAG, str(root), gate.STRICT_FLAG])
    assert strict == gate.EXIT_FAIL


def test_git_error_text_stays_out_of_the_report(tmp_path: Path) -> None:
    """git's own error text can name files outside the project, so the report
    gives a fixed reason with git's exit code instead."""
    repo = _project(tmp_path)
    secret = _write(tmp_path / "outside", {"secret.cfg": "this is not git config\n"})
    with (repo / ".git" / "config").open("a", encoding="utf-8") as config:
        config.write(f"[include]\n\tpath = {(secret / 'secret.cfg').as_posix()}\n")

    payload = _run(repo)
    assert payload["passed"] is False
    error = str(payload["check_error"])
    assert error.startswith(_GIT_FAILED)
    assert "secret" not in error
    assert "corpus_error" not in payload


def test_git_error_text_that_is_not_utf8_does_not_crash_the_run(
    tmp_path: Path,
) -> None:
    """A git error that is not UTF-8 text still ends in a report, not a crash."""
    repo = _project(tmp_path)
    with (repo / ".git" / "config").open("ab") as config:
        config.write(b"[core]\n\tabbrev = caf\xe9\n")

    payload = _run(repo)
    assert payload["passed"] is False
    assert str(payload["check_error"]).startswith(_GIT_FAILED)
    _assert_exit_codes_for_a_run_that_did_not_pass(repo)


def test_index_name_that_is_not_utf8_skips_that_entry_only(tmp_path: Path) -> None:
    """One file name that is not UTF-8 does not stop the other files."""
    repo = _project(tmp_path)
    _write_index(repo, ["clean.py", b"caf\xe9.md"])

    payload = _run(repo)
    _assert_only_clean_file_read(payload)
    assert _skipped(payload) == {"missing": 1}


def test_missing_git_reports_a_check_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no git to run, the run reports that and does not pass."""
    repo = _project(tmp_path)
    empty = tmp_path / "no-programs"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    payload = _run(repo)
    assert payload["passed"] is False
    assert payload["check_error"] == "git did not start"
    _assert_exit_codes_for_a_run_that_did_not_pass(repo)


def test_corrupt_index_reports_a_check_error(tmp_path: Path) -> None:
    """An index git cannot read ends the run with a reason, not a pass."""
    repo = _project(tmp_path)
    (repo / ".git" / "index").write_bytes(b"not an index")

    payload = _run(repo)
    assert payload["passed"] is False
    assert str(payload["check_error"]).startswith(_GIT_FAILED)


# --- Links inside file content --------------------------------------------------


@pytest.mark.parametrize(
    "destination",
    [
        "\\\\192.0.2.1\\share\\notes.md",
        "//192.0.2.1/share/notes.md",
        "C:/Windows/win.ini",
        "C:notes.md",
        "\\rooted\\notes.md",
        "file:///etc/hosts",
        "file://192.0.2.1/share/notes.md",
    ],
)
def test_link_check_never_looks_up_network_or_absolute_targets(
    tmp_path: Path, destination: str
) -> None:
    """A link to a network share, a drive or another absolute place is counted
    as external and never looked up, so no connection is made.

    On Windows, looking up ``\\\\host\\share`` opens a network connection that
    sends the user's sign-in to that host and can wait about 21 seconds.
    """
    started = time.monotonic()
    result = link_check.check(f"[x]({destination})\n", tmp_path / "doc.md")
    assert time.monotonic() - started < _DEADLINE_SECONDS / 6
    assert result.findings == []
    assert result.external_count == 1
    assert result.internal_count == 0


def _link_check_files(payload: dict[str, object]) -> list[str]:
    """Return the files the corpus run's ``link_check`` flagged."""
    advisory = payload["advisory"]
    assert isinstance(advisory, list)
    for entry in advisory:
        if entry["matcher"] == "link_check":
            return list(entry["files"])
    return []


def test_link_check_in_a_corpus_run_stays_inside_the_project(tmp_path: Path) -> None:
    """A relative link that leaves the project is not looked up, so whether a
    file outside exists stays out of the report; links inside are checked."""
    _write(tmp_path, {"present.md": "here\n"})
    repo = _project(
        tmp_path,
        {
            "doc.md": "[a](../present.md) [b](../absent.md)\n",
            "page.md": "[c](gone.md)\n",
        },
    )

    assert _link_check_files(_run(repo)) == ["page.md"]


def test_link_check_finds_the_docs_folder_only_inside_the_project(
    tmp_path: Path,
) -> None:
    """A site route such as ``/docs/page`` is checked against the project's own
    ``site/content/docs`` folder, never one found above the project."""
    _write(tmp_path, {"site/content/docs/index.mdx": "page\n"})
    repo = _project(tmp_path, {"doc.md": "[p](/docs/nowhere)\n"})

    assert _link_check_files(_run(repo)) == []


def test_link_with_a_nul_character_keeps_the_other_findings(tmp_path: Path) -> None:
    """A NUL in one link's destination is a dead link like any other; the
    file's other link findings are still reported."""
    repo = _project(
        tmp_path,
        {"one.md": "[c](gone-too.md)\n", "two.md": "[a](gone.md) [b](a\0b.md)\n"},
    )

    payload = _run(repo)
    assert _link_check_files(payload) == ["one.md", "two.md"]
    advisory = payload["advisory"]
    assert isinstance(advisory, list)
    entry = next(item for item in advisory if item["matcher"] == "link_check")
    assert entry["finding_count"] == 3


def test_link_check_skips_a_docs_route_with_a_drive_on_windows_only(
    tmp_path: Path,
) -> None:
    """On Windows a ``/docs/`` route whose segment names a drive, such as
    ``/docs/Z:/x``, is counted as external, not looked up on that drive.
    Elsewhere a colon is an ordinary character, so the route is checked and,
    with no such page, reported as dead."""
    _write(tmp_path, {"site/content/docs/index.mdx": "page\n"})
    result = link_check.check("[x](/docs/Z:/x)\n", tmp_path / "page.md")
    if os.name == "nt":
        assert result.findings == []
        assert result.external_count == 1
    else:
        assert len(result.findings) == 1
        assert result.internal_count == 1


def test_link_check_reports_a_docs_route_holding_nul_in_a_corpus_run(
    tmp_path: Path,
) -> None:
    """A NUL inside a ``/docs/`` route is a dead route, reported for its file."""
    repo = _project(
        tmp_path,
        {"site/content/docs/index.mdx": "page\n", "doc.md": "[x](/docs/a\0b)\n"},
    )

    assert _link_check_files(_run(repo)) == ["doc.md"]


def test_name_ending_in_a_dot_or_a_space_is_not_read_on_windows(
    tmp_path: Path,
) -> None:
    """Windows drops a trailing dot or space, so ``ci.yml.`` would open
    ``ci.yml``; such a name is counted as unsupported there. Elsewhere it is a
    name of its own, missing here."""
    repo = _project(tmp_path, {"ci.yml": _UNPINNED_WORKFLOW})
    _write_index(repo, ["clean.py", "ci.yml.", "ci.yml "])

    payload = _run(repo)
    _assert_only_clean_file_read(payload)
    expected = {"unsupported_name": 2} if os.name == "nt" else {"missing": 2}
    assert _skipped(payload) == expected


def test_name_with_a_character_windows_reserves_is_unsupported_there(
    tmp_path: Path,
) -> None:
    """A name with one of ``<>"|?*`` cannot exist on Windows, so it is counted
    as unsupported there; elsewhere it is a name of its own, missing here."""
    repo = _project(tmp_path)
    _write_index(repo, ["clean.py", "what?.md", "a|b.md"])

    payload = _run(repo)
    _assert_only_clean_file_read(payload)
    expected = {"unsupported_name": 2} if os.name == "nt" else {"missing": 2}
    assert _skipped(payload) == expected


@pytest.mark.parametrize(
    "destination",
    [
        "ci.yml.",
        "ci.yml ",
        "ci.yml..",
        "ci.yml.#top",
        "guide./notes.md",
        "/docs/guide./page",
    ],
)
def test_link_found_through_a_trailing_dot_or_space_is_unchecked_on_windows(
    tmp_path: Path, destination: str
) -> None:
    """On Windows, a lookup through a part ending in a dot or a space can find
    a file under another name (``ci.yml.`` finds ``ci.yml``). Such a find proves
    nothing about the link, so it is left unchecked, counted as external.
    Elsewhere the link names a file of its own, here a dead link."""
    _write(
        tmp_path,
        {
            "ci.yml": "x: 1\n",
            "guide/notes.md": "notes\n",
            "site/content/docs/guide/page.mdx": "page\n",
        },
    )
    result = link_check.check(f"[x](<{destination}>)\n", tmp_path / "doc.md")
    if os.name == "nt":
        assert result.findings == []
        assert result.external_count == 1
        assert result.internal_count == 0
    else:
        assert len(result.findings) == 1
        assert result.internal_count == 1


@pytest.mark.parametrize(
    "destination",
    [
        "/docs/missing?x=1.",
        "sub../a.md",
        "sub/.../a.md",
        "sub /a.md",
        "guide /notes.md",
    ],
)
def test_link_with_a_trailing_dot_or_space_that_finds_nothing_is_dead(
    tmp_path: Path, destination: str
) -> None:
    """A query string is no part of a file name, and a lookup through a part
    ending in a dot or a space that finds nothing is a dead link on every
    system: Windows keeps such a part in the middle of a path as written."""
    _write(
        tmp_path,
        {
            "sub/a.md": "a\n",
            "guide/notes.md": "notes\n",
            "site/content/docs/index.mdx": "page\n",
        },
    )
    result = link_check.check(f"[x](<{destination}>)\n", tmp_path / "doc.md")
    assert len(result.findings) == 1
    assert result.internal_count == 1


def test_tracked_file_next_to_its_trailing_dot_names_is_still_read(
    tmp_path: Path,
) -> None:
    """Skipping ``ci.yml.`` and ``ci.yml `` leaves the tracked ``ci.yml`` itself
    read, so its blocking finding is still reported."""
    repo = _project(tmp_path, {"ci.yml": _UNPINNED_WORKFLOW})
    _write_index(repo, ["clean.py", "ci.yml", "ci.yml.", "ci.yml "])

    payload = _run(repo)
    assert payload["passed"] is False
    assert payload["files_scanned"] == 2
    blocking = payload["blocking"]
    assert isinstance(blocking, list)
    assert [entry["files"] for entry in blocking] == [["ci.yml"]]
    expected = {"unsupported_name": 2} if os.name == "nt" else {"missing": 2}
    assert _skipped(payload) == expected
