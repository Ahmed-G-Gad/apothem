# SPDX-License-Identifier: MIT

"""A path swapped for a link or a named pipe after its check is never read through.

Why these tests exist. Every conformity read checks a path first (the tree
walk's listing, ``project_file_target``, ``is_project_file``,
``list_real_entries``, the corpus run's ``lstat_inside``, ``path_kind``) and
reads it afterwards. A program that writes to the project while the gate runs
can swap the file, or the folder that holds it, for a link out of the project
or for a named pipe in between: a read by name would then take the outside
file's content, or wait on the pipe until the gate's time limit.

How the tests make the race. Each test wraps the check its validator uses so
that, right after the check answers for the target path, the path is swapped:

- ``file-link``: the file becomes a symbolic link to the outside copy (a
  junction to the outside copy's folder on Windows, which needs no
  privilege);
- ``fifo``: the file becomes a named pipe (POSIX hosts);
- ``parent-link``: the folder that holds the file is moved aside and a
  folder link (a junction on Windows) to the outside copy's folder takes its
  place.

The outside copy holds content the validator would report, so a read of it
shows in the result. Each run must not report that content, must finish well
within the deadline, and must name the swapped entry under the skip log that
becomes ``skipped_links``. One validator stands for each way the validators
check a path before they read it.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, TypeVar

import pytest

from apothem.conformity import (
    _corpus,
    _grep_base,
    _project_paths,
    dynamism_grep,
    gate,
    oidc_trusted_publishing_grep,
    recommend_next_step_grep,
    smoke_install_grep,
)
from tests._shared.git_env import hermetic_git_env

_T = TypeVar("_T")

# How long one check may take before the test calls it stalled on a pipe.
_DEADLINE_SECONDS = 20.0
# A literal version only the outside copies hold: a read of one is a finding.
_OUTSIDE_VERSION = "9.8.7"

_POSIX = os.name != "nt"
_KINDS = [
    pytest.param("file-link", id="file-link"),
    pytest.param(
        "fifo",
        id="fifo",
        marks=pytest.mark.skipif(not _POSIX, reason="named pipes are POSIX-only"),
    ),
    pytest.param("parent-link", id="parent-link"),
]


@pytest.fixture(autouse=True)
def _fresh_skip_log() -> Iterator[None]:
    """Leave no skip log or open folder behind for the next test."""
    yield
    _project_paths.take_skipped_paths()


def _write(base: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    return base


def _link_folder(link: Path, target: Path) -> None:
    """Make *link* a folder link to *target*: a junction on Windows."""
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
        return
    link.symlink_to(target, target_is_directory=True)


class _Race:
    """Swaps one path once, right after a wrapped check answers for it."""

    def __init__(self, root: Path, target: Path, outside: Path, kind: str) -> None:
        self.root = root
        self.target = target
        self.outside = outside
        self.kind = kind
        self.swapped: Path | None = None
        self.fifos: list[Path] = []

    def swap(self) -> None:
        """Swap :attr:`target` for its kind of entry, once."""
        if self.swapped is not None:
            return
        twin = self.outside / self.target.relative_to(self.root)
        if self.kind == "parent-link":
            folder = self.target.parent
            folder.rename(folder.with_name(folder.name + ".moved"))
            _link_folder(folder, twin.parent)
            self.swapped = folder
            return
        self.target.unlink()
        if self.kind == "fifo":
            os.mkfifo(self.target)
            self.fifos.append(self.target)
        elif os.name == "nt":
            _link_folder(self.target, twin.parent)
        else:
            self.target.symlink_to(twin)
        self.swapped = self.target

    def after(
        self, check: Callable[..., _T], matches: Callable[..., bool]
    ) -> Callable[..., _T]:
        """Return *check*, swapping the target once *matches* says it answered for it."""

        def wrapped(*args: Any, **kwargs: Any) -> _T:  # noqa: ANN401
            answer = check(*args, **kwargs)
            if matches(answer, *args):
                self.swap()
            return answer

        return wrapped

    def noted(self) -> str:
        assert self.swapped is not None, "the check never answered for the target"
        return self.swapped.relative_to(self.root).as_posix()

    def release(self) -> None:
        """Let a read that waits on one of the pipes end, so the thread stops."""
        for fifo in self.fifos:
            try:
                fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
            except OSError:
                continue
            os.close(fd)


def _within_deadline(race: _Race, call: Callable[[], _T]) -> _T:
    """Run *call* on a thread; fail when it is still running at the deadline."""
    box: dict[str, Any] = {}

    def run() -> None:
        try:
            box["result"] = call()
        except BaseException as exc:  # handed back to the test below
            box["error"] = exc

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(_DEADLINE_SECONDS)
    if thread.is_alive():
        race.release()
        thread.join(5)
        pytest.fail("the read waited on a named pipe that took the file's place")
    if "error" in box:
        raise box["error"]
    return box["result"]  # type: ignore[no-any-return]


def _skipped() -> list[str]:
    return _project_paths.take_skipped_paths()


def _started(root: Path) -> None:
    _project_paths.start_skip_log(root)


# ---------------------------------------------------------------------------
# The tree walk: dynamism-grep reads each page the walk lists
# ---------------------------------------------------------------------------


# The page at the root and one in a folder; the root itself is never swapped,
# as it is the folder the run was pointed at.
_WALKED = [
    pytest.param(rel, kind.values[0], id=f"{where}-{kind.id}", marks=kind.marks)
    for rel, where in (("README.md", "root"), ("site/content/docs/guide.md", "docs"))
    for kind in _KINDS
    if not (where == "root" and kind.values[0] == "parent-link")
]


@pytest.mark.parametrize(("rel", "kind"), _WALKED)
def test_a_walked_file_swapped_after_the_listing_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, rel: str
) -> None:
    files = {"README.md": "# Sample\n", "site/content/docs/guide.md": "# Guide\n"}
    root = _write(tmp_path / "project", files)
    outside = _write(
        tmp_path / "outside",
        dict.fromkeys(files, f"Version {_OUTSIDE_VERSION}\n"),
    )
    race = _Race(root, root / rel, outside, kind)
    real_walk = dynamism_grep.iter_tree_files

    def racing_walk(*args: Any, **kwargs: Any) -> Iterator[Path]:  # noqa: ANN401
        for path in real_walk(*args, **kwargs):
            if path == race.target:
                race.swap()
            yield path

    monkeypatch.setattr(dynamism_grep, "iter_tree_files", racing_walk)
    _started(root)

    result = _within_deadline(race, lambda: dynamism_grep.check(root))

    assert _OUTSIDE_VERSION not in result.to_json()
    assert race.noted() in _skipped()


# ---------------------------------------------------------------------------
# A fixed file found by project_file_target: smoke-install-grep
# ---------------------------------------------------------------------------

_STRICT_SCRIPT = "set -euo pipefail\n# --help\ncommand -v git\n"


@pytest.mark.parametrize("kind", _KINDS)
def test_a_fixed_file_swapped_after_its_lookup_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """The outside script is complete, the project's is not: a read of the
    outside one would clear the project's findings. The swapped script
    counts as absent instead."""
    rel = "scripts/installer/install.sh"
    files = {rel: "echo hi\n", "scripts/installer/install.ps1": "Write-Output hi\n"}
    root = _write(tmp_path / "project", files)
    outside = _write(tmp_path / "outside", dict.fromkeys(files, _STRICT_SCRIPT))
    race = _Race(root, root / rel, outside, kind)
    monkeypatch.setattr(
        smoke_install_grep,
        "project_file_target",
        race.after(
            smoke_install_grep.project_file_target,
            lambda answer, _root, path: path == race.target and answer is not None,
        ),
    )
    _started(root)

    result = _within_deadline(race, lambda: smoke_install_grep.check(root))

    details = [f.detail for f in result.findings if f.script == "install.sh"]
    assert len(details) == 1
    assert "absent" in details[0]
    assert race.noted() in _skipped()


# ---------------------------------------------------------------------------
# A listed file checked with is_project_file: recommend-next-step-grep
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", _KINDS)
def test_a_listed_file_swapped_after_its_check_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    rel = "src/apothem/commands/sample.md"
    files = {rel: "# Sample\n", "src/apothem/skills/s/SKILL.md": "# Skill\n"}
    root = _write(tmp_path / "project", files)
    outside = _write(tmp_path / "outside", {rel: f"# Sample {_OUTSIDE_VERSION}\n"})
    race = _Race(root, root / rel, outside, kind)
    monkeypatch.setattr(
        recommend_next_step_grep,
        "is_project_file",
        race.after(
            recommend_next_step_grep.is_project_file,
            lambda answer, _root, path: answer and path == race.target,
        ),
    )
    _started(root)

    result = _within_deadline(race, lambda: recommend_next_step_grep.check(root))

    unread = [
        f
        for f in result.findings
        if f.surface == str(race.target) and f.detail.startswith("could not read")
    ]
    assert len(unread) == 1
    assert race.noted() in _skipped()


# ---------------------------------------------------------------------------
# A file listed by list_real_entries: oidc-trusted-publishing-grep
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param(
            "file-link",
            marks=pytest.mark.skipif(
                not _POSIX, reason="the check skips a junction in a file's place"
            ),
        ),
        "parent-link",
    ],
)
def test_a_publish_workflow_swapped_after_the_listing_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    rel = ".github/workflows/publish-pypi.yml"
    root = _write(tmp_path / "project", {rel: "name: publish\n"})
    outside = _write(tmp_path / "outside", {rel: "name: publish\n"})
    race = _Race(root, root / rel, outside, kind)
    real_list = oidc_trusted_publishing_grep.list_real_entries

    def racing_list(*args: Any, **kwargs: Any) -> list[Path]:  # noqa: ANN401
        listed = real_list(*args, **kwargs)
        if race.target in listed:
            race.swap()
        return listed

    monkeypatch.setattr(oidc_trusted_publishing_grep, "list_real_entries", racing_list)
    _started(root)

    result = _within_deadline(race, lambda: oidc_trusted_publishing_grep.check(root))

    assert result.workflows_inspected == []
    assert race.noted() in _skipped()


# ---------------------------------------------------------------------------
# The --all-perwrite corpus run: lstat_inside, then the read
# ---------------------------------------------------------------------------

# Split so the license scanner does not read the fixture text as this file's
# own license tag.
_SPDX_HASH = "# SPDX-License-" + "Identifier: MIT"
_CLEAN_PY = f"{_SPDX_HASH}\n\ndef h(x: int) -> int:\n    return x\n"
# An unpinned ``uses:`` ref, a blocking finding: a read of it fails the run.
_UNPINNED_WORKFLOW = (
    f"{_SPDX_HASH}\n\n"
    "name: ci\non: [push]\n"
    "jobs:\n  build:\n    runs-on: ubuntu-latest\n"
    "    steps:\n      - uses: actions/checkout@v4\n"
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        env=hermetic_git_env(),
        check=True,
        capture_output=True,
    )


def test_a_tracked_file_whose_folder_is_swapped_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The corpus run already refused a link in the file's own place; a
    folder above it swapped for a link after the look is refused too, so the
    outside workflow's unpinned ref is never read and the entry counts as a
    link."""
    rel = "sub/ci.yml"
    root = _write(tmp_path / "project", {rel: "name: ok\n", "clean.py": _CLEAN_PY})
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(
        root,
        "-c",
        "user.email=test@apothem.invalid",
        "-c",
        "user.name=apothem-test",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "seed",
    )
    outside = _write(tmp_path / "outside", {rel: _UNPINNED_WORKFLOW})
    race = _Race(root, root / rel, outside, "parent-link")
    monkeypatch.setattr(
        _corpus,
        "lstat_inside",
        race.after(
            _corpus.lstat_inside,
            lambda answer, _root, path: (
                path == race.target and not isinstance(answer, str)
            ),
        ),
    )

    passed, payload_json = _within_deadline(race, lambda: gate._run_all_perwrite(root))
    payload = json.loads(payload_json)

    assert race.swapped is not None
    assert passed is True, payload["blocking"]
    assert payload["files_scanned"] == 1
    assert payload["files_skipped"]["link"] == 1


# ---------------------------------------------------------------------------
# A .git file looked at with path_kind: git_entry_state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("file-link", id="file-link"),
        pytest.param(
            "fifo",
            id="fifo",
            marks=pytest.mark.skipif(not _POSIX, reason="named pipes are POSIX-only"),
        ),
    ],
)
def test_a_git_file_swapped_after_the_look_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """The outside ``.git`` file names a real repository; read through the
    swap it would make the folder a checkout. The swapped entry is not read:
    the entry is broken, at once."""
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "-q")
    folder = _write(tmp_path / "folder", {".git": "gitdir: nowhere\n"})
    outside = _write(
        tmp_path / "outside", {".git": f"gitdir: {(repository / '.git').as_posix()}\n"}
    )
    race = _Race(folder, folder / ".git", outside, kind)
    monkeypatch.setattr(
        _grep_base,
        "path_kind",
        race.after(
            _grep_base.path_kind,
            lambda answer, path: path == race.target and answer == "file",
        ),
    )
    _started(folder)

    state = _within_deadline(race, lambda: _grep_base.git_entry_state(folder))

    assert race.swapped is not None, "the check never answered for the target"
    assert state == _grep_base.GIT_ENTRY_BROKEN
    assert race.noted() in _skipped()
