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
from typing import IO, Any, TypeVar, cast

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
_MAX_FILE_BYTES = 64 * 1024 * 1024
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
    assert _skipped(payload) == {"exempt": 1}
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
        },
    )
    (repo / "gone.md").unlink()
    shutil.rmtree(repo / "linked")
    _link_folder(repo / "linked", outside)
    (repo / "blob.txt").write_bytes(b"\xff\xfe\x00 not text")

    payload = _run(repo)
    _assert_only_clean_file_read(payload)
    assert _skipped(payload) == {"link": 1, "missing": 1, "not_utf8_text": 1}


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


# --- Review of 2026-11-24 ----------------------------------------------------


def test_link_through_a_folder_link_is_not_looked_up_in_a_corpus_run(
    tmp_path: Path,
) -> None:
    """A link whose path crosses a folder link (a junction on Windows) is not
    followed: whether the file behind it exists stays out of the report."""
    outside = _write(tmp_path / "elsewhere", {"present.md": "here\n"})
    repo = _project(
        tmp_path,
        {"doc.md": "[a](linked/present.md) [b](linked/absent.md) [c](nothere.md)\n"},
    )
    _link_folder(repo / "linked", outside)

    # Only the plain dead link is reported, whether or not the file behind
    # the folder link exists.
    for _ in range(2):
        payload = _run(repo)
        assert _link_check_files(payload) == ["doc.md"]
        advisory = payload["advisory"]
        assert isinstance(advisory, list)
        entry = next(item for item in advisory if item["matcher"] == "link_check")
        assert entry["finding_count"] == 1
        (outside / "present.md").unlink(missing_ok=True)


def test_exempt_suffix_cannot_hide_an_entry_that_leaves_the_project(
    tmp_path: Path,
) -> None:
    """``../x.png`` is counted as leaving the project, not as an exempt image."""
    repo = _project(tmp_path)
    _write_index(repo, ["clean.py", "../x.png"])

    payload = _run(repo)
    _assert_only_clean_file_read(payload, passed=False)
    assert _skipped(payload) == {"outside_project": 1}


def test_tracked_path_that_is_a_folder_on_disk_is_not_regular(tmp_path: Path) -> None:
    """A tracked file replaced by a folder is counted as not a regular file."""
    repo = _project(tmp_path, {"notes.md": "notes\n"})
    (repo / "notes.md").unlink()
    (repo / "notes.md").mkdir()

    payload = _run(repo)
    _assert_only_clean_file_read(payload)
    assert _skipped(payload) == {"not_regular_file": 1}


def test_file_that_cannot_be_opened_is_unreadable_and_fails_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tracked file that exists but cannot be opened is counted as
    unreadable, not missing, and the run does not pass: its findings are
    unknown."""
    repo = _project(tmp_path, {"bad.yml": _UNPINNED_WORKFLOW})
    real_open = _corpus_module()._open_binary

    def refusing_open(self: Path, *args: object, **kwargs: object) -> object:
        if self.name == "bad.yml":
            raise PermissionError(13, "Permission denied", str(self))
        return real_open(self)

    monkeypatch.setattr(_corpus_module(), "_open_binary", refusing_open)
    payload = _run(repo)
    _assert_only_clean_file_read(payload, passed=False)
    assert _skipped(payload) == {"unreadable": 1}


def test_project_under_a_tests_fixtures_folder_is_still_read(tmp_path: Path) -> None:
    """The exemptions are judged on the path inside the project, so a project
    that itself sits under ``tests/fixtures`` is read as usual."""
    repo = _commit_tree(
        _write(tmp_path / "tests" / "fixtures" / "proj", {"clean.py": _CLEAN_PY})
    )

    payload = _run(repo)
    _assert_only_clean_file_read(payload)
    assert _skipped(payload) == {}


def test_names_git_never_writes_or_windows_cannot_hold(tmp_path: Path) -> None:
    """A ``.git`` part, in any case, or its short name ``GIT~1``, is never
    written by git, so it leaves the project. On Windows, device names and
    other short names such as ``GIT~2`` name something other than a project
    file, so they are unsupported there."""
    repo = _project(tmp_path)
    _write_index(
        repo,
        [
            "clean.py",
            ".git/config",
            ".GIT/config",
            "CON",
            "nul",
            "COM1",
            "GIT~1/config",
            "GIT~2/config",
            "git~notes.md",
        ],
    )

    payload = _run(repo)
    _assert_only_clean_file_read(payload, passed=False)
    if os.name == "nt":
        assert _skipped(payload) == {
            "outside_project": 3,
            "unsupported_name": 4,
            "missing": 1,
        }
    else:
        assert _skipped(payload) == {"outside_project": 3, "missing": 5}


def test_read_entry_reads_text_as_read_text_does(tmp_path: Path) -> None:
    """Line endings come out as ``read_text`` gives them, so matcher line
    numbers do not change."""
    from apothem.conformity import _corpus

    target = tmp_path / "mixed.md"
    target.write_bytes(b"one\r\ntwo\rthree\nfour\n")
    text, reason = _corpus.read_entry(tmp_path, _corpus.TrackedEntry(target, "100644"))
    assert reason is None
    assert text == target.read_text(encoding="utf-8")


def test_docs_route_with_a_query_is_checked_by_its_path(tmp_path: Path) -> None:
    """``/docs/guide?x=1.`` is the live ``/docs/guide`` page: the query is no
    part of the name."""
    _write(tmp_path, {"site/content/docs/guide.mdx": "page\n"})
    result = link_check.check("[x](/docs/guide?x=1.)\n", tmp_path / "doc.md")
    assert result.findings == []
    assert result.internal_count == 1


def test_docs_route_that_climbs_out_is_external(tmp_path: Path) -> None:
    """``/docs/../x`` is no page route, so it is never looked up."""
    _write(tmp_path, {"site/content/docs/index.mdx": "page\n"})
    result = link_check.check("[x](/docs/../x)\n", tmp_path / "doc.md")
    assert result.findings == []
    assert result.external_count == 1


def test_large_lockfile_is_read_and_the_run_passes(tmp_path: Path) -> None:
    """A text file of several MiB, such as a lockfile, is read like any other."""
    repo = _project(tmp_path, {"package-lock.json": "{}\n"})
    (repo / "package-lock.json").write_bytes(
        b'{"x": "' + b"a" * (12 * 1024 * 1024) + b'"}\n'
    )

    payload = _run(repo)
    assert payload["passed"] is True
    assert payload["files_scanned"] == 2
    assert _skipped(payload) == {}


def _corpus_module() -> Any:  # noqa: ANN401 - the module, for monkeypatching
    return importlib.import_module("apothem.conformity._corpus")


def _shrink_limit(monkeypatch: pytest.MonkeyPatch, size: int) -> None:
    """Lower the corpus read limit, so a test needs no huge file."""
    corpus = importlib.import_module("apothem.conformity._corpus")
    monkeypatch.setattr(corpus, "MAX_FILE_BYTES", size)


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (_UNPINNED_WORKFLOW.encode("utf-8") + b"# pad\n" * 2000, "too_large"),
        (
            b"\0" + _UNPINNED_WORKFLOW.encode("utf-8") + b"# pad\n" * 2000,
            "too_large",
        ),
        (b"\0" * 10000, "not_utf8_text"),
        (b"ok\n" + b"\xff" + b"x" * 10000, "not_utf8_text"),
        (b"a" * 4095 + "\u00e9".encode("utf-8") + b"a" * 6000, "too_large"),
    ],
    ids=["text", "text-with-nul", "zero-filled", "invalid-byte", "char-across-limit"],
)
def test_file_over_the_limit_is_judged_by_all_its_first_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes, reason: str
) -> None:
    """Over the limit, a file is text when its first bytes up to the limit
    decode as UTF-8, a stray NUL included. Text over the limit fails the run
    and is named; a binary, a zero-filled image included, does not fail it."""
    repo = _project(tmp_path, {"big.yml": "small\n"})
    (repo / "big.yml").write_bytes(body)
    _shrink_limit(monkeypatch, 4096)

    payload = _run(repo)
    assert _skipped(payload) == {reason: 1}
    assert payload["passed"] is (reason != "too_large")
    if reason == "too_large":
        assert payload["files_not_passed"] == {"too_large": ["big.yml"]}


def test_folder_that_cannot_be_looked_at_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refused look at a folder on the way to a tracked file counts as
    unreadable and fails the run; a name too long for the system is missing."""
    repo = _project(tmp_path, {"locked/bad.yml": _UNPINNED_WORKFLOW})
    real_lstat = os.lstat

    def refusing_lstat(path: object, *args: object, **kwargs: object) -> object:
        if Path(str(path)).name == "locked":
            raise PermissionError(13, "Permission denied", str(path))
        return real_lstat(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "lstat", refusing_lstat)
    payload = _run(repo)
    _assert_only_clean_file_read(payload, passed=False)
    assert _skipped(payload) == {"unreadable": 1}


def test_overlong_name_counts_as_missing(tmp_path: Path) -> None:
    """A name too long for this system names no file here: missing, which
    does not fail the run."""
    repo = _project(tmp_path)
    _write_index(repo, ["clean.py", "a" * 300 + ".md"])

    payload = _run(repo)
    _assert_only_clean_file_read(payload)
    assert _skipped(payload) == {"missing": 1}


@pytest.mark.parametrize(
    "parent",
    ["tests/fixtures", "tests/conformity", "node_modules", "_vendor", ".apothem/plans"],
)
def test_exemptions_are_judged_inside_the_root(tmp_path: Path, parent: str) -> None:
    """A project that sits under an exempt folder name is read as usual."""
    repo = _commit_tree(_write(tmp_path / parent / "proj", {"clean.py": _CLEAN_PY}))

    payload = _run(repo)
    _assert_only_clean_file_read(payload)


def test_exempt_folders_inside_the_project_are_counted(tmp_path: Path) -> None:
    """Files the checks leave out by design are counted as exempt."""
    repo = _project(
        tmp_path,
        {
            "node_modules/x.py": "x = 1\n",
            "src/tests/fixtures/y.py": "y = 1\n",
            "tests/unit/tests/fixtures/w.py": "w = 1\n",
            ".apothem/plans/z.md": "plan\n",
            "logo.png": "image\n",
        },
    )

    payload = _run(repo)
    _assert_only_clean_file_read(payload)
    assert _skipped(payload) == {"exempt": 5}


@pytest.mark.parametrize(
    "name",
    [
        "CON",
        "prn",
        "Aux",
        "NUL ",
        "COM5",
        "lpt9",
        "CONIN$",
        "conout$",
        "GIT~2",
        "git~12",
    ],
)
def test_windows_device_names_and_git_alias(name: str) -> None:
    """Bare device names and ``.git``'s short alias are unsupported on Windows;
    the same names with an extension, and ``git~notes``, are ordinary."""
    from apothem.conformity import _corpus

    expected = "unsupported_name" if os.name == "nt" else None
    assert _corpus.name_skip(name) == expected
    for ordinary in (f"{name.strip()}.md", "git~notes", "git~\u0661", "console.md"):
        assert _corpus.name_skip(ordinary) is None


def test_failing_run_names_the_files(tmp_path: Path) -> None:
    """A run that fails on an entry outside the project says which entry."""
    repo = _project(tmp_path)
    _write_index(repo, ["clean.py", "../above.md", "../../far.md"])

    payload = _run(repo)
    assert payload["passed"] is False
    assert payload["files_not_passed"] == {
        "outside_project": ["../../far.md", "../above.md"]
    }


def test_outside_entry_with_an_exempt_suffix_is_still_counted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check that an entry stays inside the root runs before the
    exemptions, so a path such as ``../x.png`` is never counted as exempt,
    even when the listing hands it over unjudged."""
    from apothem.conformity._corpus import TrackedEntry

    repo = _project(tmp_path)
    entries = [
        TrackedEntry(repo / "clean.py", "100644"),
        TrackedEntry(repo / ".." / "x.png", "100644"),
    ]
    monkeypatch.setattr(gate, "_corpus_tracked_files", lambda _root: entries)

    payload = _run(repo)
    _assert_only_clean_file_read(payload, passed=False)
    assert _skipped(payload) == {"outside_project": 1}


def _refusal(winerror: int | None) -> PermissionError:
    """A refused open, as Windows reports a file another program holds (32)
    or a plain lack of permission (no winerror)."""
    exc = PermissionError(13, "Permission denied")
    if winerror is not None:
        # ``winerror`` exists only on Windows; the corpus code reads it with
        # getattr, so the test sets it on every system.
        exc.winerror = winerror  # type: ignore[misc,attr-defined,unused-ignore]
    return exc


def _refuse_opens(
    monkeypatch: pytest.MonkeyPatch, name: str, times: int, winerror: int | None
) -> list[float]:
    """Refuse the first *times* opens of *name*; return the recorded sleeps."""
    corpus = importlib.import_module("apothem.conformity._corpus")
    real_open = _corpus_module()._open_binary
    left = [times]
    sleeps: list[float] = []

    def refusing_open(self: Path, *args: object, **kwargs: object) -> object:
        if self.name == name and left[0] > 0:
            left[0] -= 1
            raise _refusal(winerror)
        return real_open(self)

    monkeypatch.setattr(_corpus_module(), "_open_binary", refusing_open)
    monkeypatch.setattr(corpus.time, "sleep", sleeps.append)
    # Read the made-up winerror on every system (a real hold is tested on
    # Windows, and the errno rule for a lease below).
    monkeypatch.setattr(
        corpus,
        "_held_by_another_program",
        lambda exc: getattr(exc, "winerror", None) == 32,
    )
    return sleeps


@pytest.mark.parametrize("big", [False, True], ids=["small", "over-the-limit"])
def test_file_held_briefly_is_read_after_one_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, big: bool
) -> None:
    """An open refused because another program holds the file is tried once
    more after a short wait, starting afresh, so a hold that clears in time
    does not change the result."""
    repo = _project(tmp_path, {"busy.yml": _UNPINNED_WORKFLOW})
    if big:
        (repo / "busy.yml").write_bytes(
            _UNPINNED_WORKFLOW.encode("utf-8") + b"# pad\n" * 1000
        )
        _shrink_limit(monkeypatch, 4096)
    sleeps = _refuse_opens(monkeypatch, "busy.yml", 1, winerror=32)

    payload = _run(repo)
    assert sleeps == [0.2]
    assert payload["passed"] is False
    if big:
        assert _skipped(payload) == {"too_large": 1}
    else:
        assert payload["files_scanned"] == 2
        assert _skipped(payload) == {}


@pytest.mark.parametrize("winerror", [None, 32], ids=["no-permission", "still-held"])
def test_refused_open_is_waited_for_at_most_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, winerror: int | None
) -> None:
    """A lack of permission is not waited for at all, and a file still held
    after one wait is unreadable."""
    repo = _project(tmp_path, {"busy.yml": _UNPINNED_WORKFLOW})
    sleeps = _refuse_opens(monkeypatch, "busy.yml", 2, winerror=winerror)

    payload = _run(repo)
    assert sleeps == ([] if winerror is None else [0.2])
    _assert_only_clean_file_read(payload, passed=False)
    assert _skipped(payload) == {"unreadable": 1}


@pytest.mark.parametrize(
    "name",
    [
        ".git/config",
        ".GIT/x",
        ".git./x",
        ".git /x",
        "git~1/x",
        "GIT~1. /x",
        ".git:x/x",
        ".git::$INDEX_ALLOCATION/x",
    ],
)
def test_ntfs_spellings_of_git_leave_the_project(name: str) -> None:
    """git refuses the NTFS spellings of ``.git`` on every system by default,
    so each one means a hand-written index, like ``.git`` itself."""
    from apothem.conformity import _corpus

    assert _corpus.name_skip(name) == "outside_project"


class _RecordingHandle:
    """A binary file handle that records each read size, and can fail a read."""

    def __init__(self, handle: IO[bytes], fail_read: int | None = None) -> None:
        self._handle = handle
        self._fail_read = fail_read
        self.requests: list[int] = []

    def __enter__(self) -> _RecordingHandle:
        return self

    def __exit__(self, *exc: object) -> None:
        self._handle.close()

    def fileno(self) -> int:
        return int(self._handle.fileno())

    def read(self, size: int = -1) -> bytes:
        self.requests.append(size)
        if self._fail_read is not None and len(self.requests) == self._fail_read:
            raise _refusal(33)
        return bytes(self._handle.read(size))


def _record_opens(
    monkeypatch: pytest.MonkeyPatch, name: str, fail_read: int | None = None
) -> list[_RecordingHandle]:
    real_open = _corpus_module()._open_binary
    handles: list[_RecordingHandle] = []

    def recording_open(self: Path, *args: object, **kwargs: object) -> object:
        handle = real_open(self)
        if self.name != name:
            return handle
        handles.append(_RecordingHandle(handle, fail_read))
        return handles[-1]

    monkeypatch.setattr(_corpus_module(), "_open_binary", recording_open)
    return handles


def test_small_file_costs_a_small_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file is read with one request sized to it, not to the limit."""
    repo = _project(tmp_path, {"doc.md": "x" * 3000})
    handles = _record_opens(monkeypatch, "doc.md")

    payload = _run(repo)
    assert payload["files_scanned"] == 2
    assert [handle.requests for handle in handles] == [[3001]]


def test_file_that_grows_while_read_is_read_on_or_counted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file that grew after its size was looked up is read on in blocks,
    and one that grew past the limit counts as too_large."""
    corpus = importlib.import_module("apothem.conformity._corpus")
    target = tmp_path / "grows.md"
    target.write_bytes(b"a" * 10)
    real_fstat = os.fstat
    monkeypatch.setattr(
        corpus.os,
        "fstat",
        lambda fd: os.stat_result((*real_fstat(fd)[:6], 4, *real_fstat(fd)[7:])),
    )
    entry = corpus.TrackedEntry(target, "100644")
    assert corpus.read_entry(tmp_path, entry) == ("a" * 10, None)
    _shrink_limit(monkeypatch, 6)
    assert corpus.read_entry(tmp_path, entry) == (None, "too_large")


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (b"a" * 2100 + b"\xff" + b"a" * 5000, "not_utf8_text"),
        (b"a" * 2100 + b"\0" + b"a" * 5000, "too_large"),
        (b"a" * 1023 + "\u00e9".encode("utf-8") + b"a" * 5000, "too_large"),
        (b"a" * 3000 + "\u20ac".encode("utf-8") + b"a" * 5000, "too_large"),
    ],
    ids=["bad-byte-third-block", "nul-third-block", "char-across-block", "char-late"],
)
def test_file_over_the_limit_is_decoded_across_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes, reason: str
) -> None:
    """Every block up to the limit is judged, and a character split between
    two blocks is still text."""
    corpus = importlib.import_module("apothem.conformity._corpus")
    repo = _project(tmp_path, {"big.md": "small\n"})
    (repo / "big.md").write_bytes(body)
    _shrink_limit(monkeypatch, 4096)
    monkeypatch.setattr(corpus, "_SNIFF_BLOCK_BYTES", 1024)

    assert _skipped(_run(repo)) == {reason: 1}


def test_file_that_ends_before_the_limit_is_judged_whole() -> None:
    """A file shorter than the limit (one that shrank after its size was
    looked up) that ends in a cut character is not text."""
    import io

    corpus = importlib.import_module("apothem.conformity._corpus")
    assert corpus._oversized_reason(io.BytesIO(b"abc\xe2\x82")) == "not_utf8_text"
    assert corpus._oversized_reason(io.BytesIO(b"abc\xe2\x82\xac")) == "too_large"


def test_read_error_after_the_open_is_unreadable_and_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An error while reading, such as a range of the file another program
    has locked, counts as unreadable at once."""
    corpus = importlib.import_module("apothem.conformity._corpus")
    repo = _project(tmp_path, {"locked.md": "x" * 100})
    sleeps: list[float] = []
    monkeypatch.setattr(corpus.time, "sleep", sleeps.append)
    handles = _record_opens(monkeypatch, "locked.md", fail_read=1)

    payload = _run(repo)
    assert len(handles) == 1
    assert sleeps == []
    _assert_only_clean_file_read(payload, passed=False)
    assert _skipped(payload) == {"unreadable": 1}


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (OSError(22, "Invalid argument"), "unreadable"),
        (FileNotFoundError(2, "No such file"), "missing"),
        (NotADirectoryError(20, "Not a directory"), "missing"),
    ],
    ids=["cannot-open", "deleted", "folder-replaced"],
)
def test_open_error_after_the_file_was_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: OSError, reason: str
) -> None:
    """Once the file was found, only an error saying it is gone is missing;
    any other, such as an online-only file whose sync program is stopped, is
    unreadable and fails the run."""
    repo = _project(tmp_path, {"cloud.yml": _UNPINNED_WORKFLOW})
    real_open = _corpus_module()._open_binary

    def failing_open(self: Path, *args: object, **kwargs: object) -> object:
        if self.name == "cloud.yml":
            raise error
        return real_open(self)

    monkeypatch.setattr(_corpus_module(), "_open_binary", failing_open)
    payload = _run(repo)
    _assert_only_clean_file_read(payload, passed=reason == "missing")
    assert _skipped(payload) == {reason: 1}


def test_named_files_are_capped_and_sorted(tmp_path: Path) -> None:
    """files_not_passed holds at most ten names per reason, sorted;
    files_skipped holds the count."""
    repo = _project(tmp_path)
    names: list[str | bytes | tuple[str, int, int]] = ["clean.py"]
    names += [f"../f{n:02}.md" for n in range(12, -1, -1)]
    _write_index(repo, names)

    payload = _run(repo)
    assert payload["files_not_passed"] == {
        "outside_project": [f"../f{n:02}.md" for n in range(10)]
    }
    assert _skipped(payload) == {"outside_project": 13}


def test_strict_run_says_on_stderr_why_it_did_not_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The failing reasons and their counts reach stderr, for a CI log."""
    repo = _project(tmp_path)
    _write_index(repo, ["clean.py", "../above.md"])

    assert gate.main(["gate", "--all-perwrite", str(repo), "--strict"]) == 2
    assert (
        "the run did not pass: tracked files it could not check: "
        "outside_project (1)" in capsys.readouterr().err
    )


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (b"\0\n" + b"a" * 20000, "too_large"),
        (b"a" * 100 + b"\0" * 1000 + b"a" * 20000, "too_large"),
        (b"a" * 100 + b"\0" * 3000 + b"a" * 20000, "not_utf8_text"),
        (b"\0" * 20000, "not_utf8_text"),
        ("uses: actions/checkout@v4\n".encode("utf-16-le") * 1000, "not_utf8_text"),
    ],
    ids=["nul-led-text", "few-nuls", "many-nuls", "zero-filled", "utf-16"],
)
def test_nul_share_decides_whether_a_large_file_is_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes, reason: str
) -> None:
    """Over the limit, a file is binary when a quarter or more of its first
    8000 bytes are NUL (a zero-filled image, UTF-16 text). A text file with a
    few NULs stays text, so it still fails the run."""
    repo = _project(tmp_path, {"dump.sql": "small\n"})
    (repo / "dump.sql").write_bytes(body)
    _shrink_limit(monkeypatch, 16384)

    payload = _run(repo)
    assert _skipped(payload) == {reason: 1}
    assert payload["passed"] is (reason != "too_large")


def test_file_of_exactly_the_limit_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The limit is the largest size read, not the first size refused."""
    repo = _project(tmp_path, {"edge.yml": "x\n"})
    body = _UNPINNED_WORKFLOW.encode("utf-8")
    (repo / "edge.yml").write_bytes(body)
    _shrink_limit(monkeypatch, len(body))

    payload = _run(repo)
    assert payload["files_scanned"] == 2
    assert _skipped(payload) == {}


def test_named_files_are_sorted_whatever_the_listing_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """files_not_passed is sorted even when the entries arrive out of order."""
    from apothem.conformity._corpus import TrackedEntry

    repo = _project(tmp_path)
    entries = [
        TrackedEntry(repo / "clean.py", "100644", name="clean.py"),
        TrackedEntry(repo, "100644", "outside_project", "../b.md"),
        TrackedEntry(repo, "100644", "outside_project", "../a.md"),
    ]
    monkeypatch.setattr(gate, "_corpus_tracked_files", lambda _root: entries)

    assert _run(repo)["files_not_passed"] == {"outside_project": ["../a.md", "../b.md"]}


def test_stderr_gives_the_full_count_not_the_sample_size(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With more failing entries than the report names, stderr says how many."""
    repo = _project(tmp_path)
    names: list[str | bytes | tuple[str, int, int]] = ["clean.py"]
    names += [f"../f{n:02}.md" for n in range(13)]
    _write_index(repo, names)

    assert gate.main(["gate", "--all-perwrite", str(repo), "--strict"]) == 2
    assert "outside_project (13)" in capsys.readouterr().err


def _hold_without_sharing(path: Path) -> int:
    """Open *path* the way a program that shares nothing does; return the handle."""
    import _winapi

    return int(
        _winapi.CreateFile(
            str(path), _winapi.GENERIC_READ, 0, 0, _winapi.OPEN_EXISTING, 0, 0
        )
    )


@pytest.mark.skipif(
    sys.platform != "win32", reason="only Windows holds a file this way"
)
@pytest.mark.parametrize("released", [True, False], ids=["let-go", "still-held"])
def test_file_a_program_holds_on_windows(tmp_path: Path, released: bool) -> None:
    """A real hold by another program: the gate waits once, then reads the
    file if the hold is over, and counts it unreadable if not."""
    import _winapi
    import threading

    from apothem.conformity import _corpus

    target = tmp_path / "held.md"
    target.write_bytes(b"held\n")
    handle = _hold_without_sharing(target)
    timer = threading.Timer(0.05, _winapi.CloseHandle, (handle,))
    if released:
        timer.start()
    try:
        result = _corpus.read_entry(tmp_path, _corpus.TrackedEntry(target, "100644"))
    finally:
        if released:
            timer.join()
        else:
            _winapi.CloseHandle(handle)
    assert result == (("held\n", None) if released else (None, "unreadable"))


def _swap_after_each_look(
    monkeypatch: pytest.MonkeyPatch,
    target: Path,
    swap_in: Any,  # noqa: ANN401
) -> list[int]:
    """After every lookup of *target*, call *swap_in* to put something else
    there; return the list that counts the lookups."""
    corpus = _corpus_module()
    real_lstat_inside = corpus.lstat_inside
    looks: list[int] = []

    def swapping(root: Path, path: Path) -> object:
        info = real_lstat_inside(root, path)
        if path == target:
            looks.append(1)
            swap_in(target, len(looks))
        return info

    monkeypatch.setattr(corpus, "lstat_inside", swapping)
    return looks


def test_file_swapped_after_its_lookup_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file replaced by another between the lookup and the open is looked
    up once more; replaced again, it is unreadable and nothing is read."""
    corpus = _corpus_module()
    target = tmp_path / "doc.md"
    target.write_text("first\n")

    def replace(path: Path, look: int) -> None:
        fresh = path.with_name(f"fresh{look}.md")
        fresh.write_text(f"swap {look}\n")
        fresh.replace(path)

    looks = _swap_after_each_look(monkeypatch, target, replace)
    entry = corpus.TrackedEntry(target, "100644")
    assert corpus.read_entry(tmp_path, entry) == (None, "unreadable")
    assert len(looks) == 2


def test_file_swapped_once_is_read_as_it_is_now(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A single swap, such as an editor saving through a new file, is looked
    up again and the new file is read."""
    corpus = _corpus_module()
    target = tmp_path / "doc.md"
    target.write_text("first\n")

    def replace_once(path: Path, look: int) -> None:
        if look == 1:
            fresh = path.with_name("fresh.md")
            fresh.write_text("saved\n")
            fresh.replace(path)

    _swap_after_each_look(monkeypatch, target, replace_once)
    entry = corpus.TrackedEntry(target, "100644")
    assert corpus.read_entry(tmp_path, entry) == ("saved\n", None)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="named pipes are POSIX-only")
@pytest.mark.parametrize("kind", ["fifo", "link-to-fifo", "link-outside"])
def test_swap_to_a_pipe_or_a_link_neither_waits_nor_reads_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """A file swapped for a named pipe, or a link to one or to a file outside
    the project, after its lookup: the open neither waits for a writer nor
    follows the link, and nothing outside is read."""
    corpus = _corpus_module()
    project = tmp_path / "proj"
    project.mkdir()
    outside = tmp_path / "secret.md"
    outside.write_text("outside\n")
    pipe = tmp_path / "pipe"
    os.mkfifo(pipe)  # type: ignore[attr-defined,unused-ignore]
    target = project / "doc.md"
    target.write_text("inside\n")

    def swap_in(path: Path, look: int) -> None:
        if look > 1:
            return
        path.unlink()
        if kind == "fifo":
            os.mkfifo(path)  # type: ignore[attr-defined,unused-ignore]
        else:
            path.symlink_to(pipe if kind == "link-to-fifo" else outside)

    _swap_after_each_look(monkeypatch, target, swap_in)
    entry = corpus.TrackedEntry(target, "100644")

    def release() -> None:
        _release_fifo(target)
        _release_fifo(pipe)

    result = _run_guarded(lambda: corpus.read_entry(project, entry), release=release)
    assert result == (None, "not_regular_file" if kind == "fifo" else "link")


def test_hold_is_told_from_a_denial() -> None:
    """Only a hold is retried: a sharing violation on Windows, a lease being
    broken (EAGAIN) elsewhere; never a lack of permission."""
    import errno

    corpus = _corpus_module()
    if sys.platform == "win32":
        assert corpus._held_by_another_program(_refusal(32)) is True
        assert corpus._held_by_another_program(_refusal(5)) is False
    else:
        assert corpus._held_by_another_program(OSError(errno.EAGAIN, "lease")) is True
        assert corpus._held_by_another_program(_refusal(None)) is False
    assert corpus._held_by_another_program(OSError(22, "Invalid")) is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows share modes")
def test_file_another_program_writes_while_sharing_is_read(tmp_path: Path) -> None:
    """A program that has the file open to write, delete or rename, sharing
    it, does not keep the gate from reading it."""
    import _winapi

    from apothem.conformity import _corpus

    target = tmp_path / "open.md"
    target.write_bytes(b"open\n")
    access = _winapi.GENERIC_READ | _winapi.GENERIC_WRITE | 0x00010000  # DELETE
    handle = _winapi.CreateFile(
        str(target), access, 0x7, 0, _winapi.OPEN_EXISTING, 0, 0
    )
    try:
        entry = _corpus.TrackedEntry(target, "100644")
        assert _corpus.read_entry(tmp_path, entry) == ("open\n", None)
    finally:
        _winapi.CloseHandle(handle)


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are Windows-only")
def test_junction_swapped_in_after_the_lookup_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On Windows the open never goes through a link at the file's own name,
    so a junction swapped in after the lookup is not followed."""
    import _winapi

    corpus = _corpus_module()
    project = tmp_path / "proj"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = project / "doc.md"
    target.write_text("inside\n")

    def swap_in(path: Path, look: int) -> None:
        if look == 1:
            path.unlink()
            _winapi.CreateJunction(str(outside), str(path))

    _swap_after_each_look(monkeypatch, target, swap_in)
    text, reason = corpus.read_entry(project, corpus.TrackedEntry(target, "100644"))
    assert text is None
    assert reason in {"link", "unreadable"}


def test_file_system_without_file_ids_is_still_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file system that gives every file an inode of 0 is judged by the
    file's type; the file is read."""
    corpus = _corpus_module()
    target = tmp_path / "doc.md"
    target.write_text("no ids\n")
    real_fstat = os.fstat
    monkeypatch.setattr(
        corpus.os,
        "fstat",
        lambda fd: os.stat_result((*real_fstat(fd)[:1], 0, *real_fstat(fd)[2:])),
    )
    entry = corpus.TrackedEntry(target, "100644")
    assert corpus.read_entry(tmp_path, entry) == ("no ids\n", None)


@pytest.mark.parametrize(
    ("nuls", "reason"), [(1999, "too_large"), (2000, "not_utf8_text")]
)
def test_quarter_of_nul_is_the_binary_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nuls: int, reason: str
) -> None:
    """Exactly a quarter of the first 8000 bytes being NUL makes a large
    file binary; one fewer keeps it text."""
    repo = _project(tmp_path, {"dump.sql": "small\n"})
    (repo / "dump.sql").write_bytes(b"\0" * nuls + b"a" * (20000 - nuls))
    _shrink_limit(monkeypatch, 16384)

    assert _skipped(_run(repo)) == {reason: 1}


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows open")
def test_windows_open_never_follows_a_link_at_the_last_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The open asks Windows for the reparse point itself, never its target."""
    import _winapi

    corpus = _corpus_module()
    target = tmp_path / "doc.md"
    target.write_text("doc\n")
    real_create = _winapi.CreateFile
    flags: list[int] = []

    def recording_create(*args: Any) -> int:  # noqa: ANN401
        flags.append(args[5])
        return int(real_create(*args))

    monkeypatch.setattr(_winapi, "CreateFile", recording_create)
    assert corpus.read_entry(tmp_path, corpus.TrackedEntry(target, "100644")) == (
        "doc\n",
        None,
    )
    assert flags
    assert all(flag & 0x00200000 for flag in flags)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows reparse tags")
@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        (0xA000000C, (None, "unreadable")),  # a symbolic link
        (0xA0000003, (None, "unreadable")),  # a junction
        (0x80000013, ("kept\n", None)),  # Data Deduplication
        (0x9000001A, ("kept\n", None)),  # a cloud sync placeholder, hydrated
        (0, ("kept\n", None)),
    ],
    ids=["symlink", "junction", "dedup", "cloud", "none"],
)
def test_only_a_reparse_point_naming_another_file_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tag: int,
    expected: tuple[str | None, str | None],
) -> None:
    """A link or junction in the file's place is never read through; a file
    deduplication or a sync program keeps behind a reparse point is read."""
    corpus = _corpus_module()
    target = tmp_path / "kept.md"
    target.write_text("kept\n")
    monkeypatch.setattr(corpus, "_reparse_tag", lambda _handle: tag)

    assert (
        corpus.read_entry(tmp_path, corpus.TrackedEntry(target, "100644")) == expected
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows reparse tags")
def test_reparse_tag_is_read_from_the_handle(tmp_path: Path) -> None:
    """A plain file has no tag; a junction opened as itself has its own."""
    import _winapi

    corpus = _corpus_module()
    plain = tmp_path / "plain.md"
    plain.write_text("x\n")
    folder = tmp_path / "folder"
    folder.mkdir()
    junction = tmp_path / "junction"
    _winapi.CreateJunction(str(folder), str(junction))
    backup_semantics = 0x02000000
    for path, flags, tag in (
        (plain, 0, 0),
        (junction, 0x00200000 | backup_semantics, 0xA0000003),
    ):
        handle = _winapi.CreateFile(
            str(path), _winapi.GENERIC_READ, 0x7, 0, _winapi.OPEN_EXISTING, flags, 0
        )
        try:
            assert corpus._reparse_tag(handle) == tag
        finally:
            _winapi.CloseHandle(handle)


def _set_reparse_tag(path: Path, tag: int, *, remove: bool = False) -> None:
    """Put a Microsoft reparse *tag* with no owner on *path*, or take it off.

    No elevation is needed. The tag must be removed again before the test
    folder is cleaned up, or the file cannot be deleted.
    """
    import _winapi
    import ctypes
    import struct
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined,unused-ignore]
    control = kernel32.DeviceIoControl
    control.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    )
    control.restype = wintypes.BOOL
    data = b"" if remove else b"\0" * 8
    request = struct.pack("<IHH", tag, len(data), 0) + data
    code = 0x000900AC if remove else 0x000900A4  # FSCTL_DELETE / SET_REPARSE_POINT
    access = _winapi.GENERIC_READ | 0x40000000  # GENERIC_WRITE
    handle = _winapi.CreateFile(
        str(path), access, 0x7, 0, _winapi.OPEN_EXISTING, 0x00200000 | 0x02000000, 0
    )
    try:
        buffer = ctypes.create_string_buffer(request)
        returned = wintypes.DWORD()
        if not control(
            handle, code, buffer, len(request), None, 0, ctypes.byref(returned), None
        ):
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined,unused-ignore]
    finally:
        _winapi.CloseHandle(handle)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows reparse tags")
def test_reparse_point_no_filter_claims_is_unreadable(tmp_path: Path) -> None:
    """A file behind a reparse point whose program is stopped (here an Azure
    File Sync tag with no filter) is unreadable, not read as its empty stub,
    and the run does not pass."""
    repo = _project(tmp_path, {"tiered.yml": _UNPINNED_WORKFLOW})
    tiered = repo / "tiered.yml"
    _set_reparse_tag(tiered, 0x8000001E)
    try:
        payload = _run(repo)
    finally:
        _set_reparse_tag(tiered, 0x8000001E, remove=True)
    _assert_only_clean_file_read(payload, passed=False)
    assert _skipped(payload) == {"unreadable": 1}


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows open")
@pytest.mark.parametrize(
    ("tag", "second_id", "expected"),
    [
        (0x80000013, None, ("kept\n", None)),
        (0x80000013, (1, 2), (None, "unreadable")),
        (None, None, ("kept\n", None)),
        (OSError(5, "query refused"), None, (None, "unreadable")),
        (0xA000000C, None, (None, "unreadable")),
    ],
    ids=[
        "dedup-same-file",
        "dedup-other-file",
        "no-tag-support",
        "query-fails",
        "symlink",
    ],
)
def test_windows_open_reads_through_the_filter_and_closes_every_handle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tag: object,
    second_id: tuple[int, int] | None,
    expected: tuple[str | None, str | None],
) -> None:
    """A reparse point that is not a link, or a file whose tag cannot be told,
    is read through a second, plain open that must name the same file; a
    failed query or a link is not read; no handle is left open."""
    corpus = _corpus_module()
    target = tmp_path / "kept.md"
    target.write_text("kept\n")
    opened: list[int] = []
    closed: list[int] = []
    real_create, real_close, real_id = (
        corpus._create_file,
        corpus._close_handle,
        corpus._file_id,
    )

    def creating(path: Path, flags: int) -> int:
        handle = int(real_create(path, flags))
        opened.append(handle)
        return handle

    def closing(handle: int) -> None:
        closed.append(handle)
        real_close(handle)

    def reading_tag(_handle: int) -> int | None:
        if isinstance(tag, OSError):
            raise tag
        return cast("int | None", tag)

    def file_id(handle: int) -> tuple[int, int]:
        if second_id is not None and handle == opened[-1] and len(opened) % 2 == 0:
            return second_id
        return cast("tuple[int, int]", real_id(handle))

    monkeypatch.setattr(corpus, "_create_file", creating)
    monkeypatch.setattr(corpus, "_close_handle", closing)
    monkeypatch.setattr(corpus, "_reparse_tag", reading_tag)
    monkeypatch.setattr(corpus, "_file_id", file_id)

    result = corpus.read_entry(tmp_path, corpus.TrackedEntry(target, "100644"))
    assert result == expected
    # Handles that reached the reader are closed with the file object; every
    # other one was closed here.
    read_through = 1 if expected[0] is not None else 0
    assert len(closed) == len(opened) - read_through
