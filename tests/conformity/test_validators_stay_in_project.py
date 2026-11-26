# SPDX-License-Identifier: MIT

"""Every ``--all`` validator reads and lists only real files inside the project.

Why these tests exist. A project can arrive with its files from someone else,
in an archive or a shared folder. The gate's ``--all`` mode runs every
standalone validator over that project, and each one reaches project files in
its own way: the shared tree walk, a ``glob`` or ``rglob`` of a fixed folder,
an ``iterdir`` of the plans tree, or a fixed file such as ``.gitattributes``.
So a link in the project, a symbolic link or a Windows junction, could lead a
validator to a file or a whole tree outside the project, and a named pipe or a
link to ``/dev/zero`` could make a read wait or never end.

How the tests see it. Each run starts all the validators one after another in
one child process, under a Python audit hook that records every file opened
(``open``) and every folder listed (``os.scandir`` and ``os.listdir``). The
pathlib reads, globs and walks the validators use all go through those calls.
The project holds the same files as an outside copy, reached through links:

- every top-level folder is a link into the outside copy;
- every second-level folder is a link, so ``src/apothem`` is one under a
  real ``src``;
- every deepest folder is a link, with real folders above it;
- every file is a symbolic link into the outside copy, or to a real copy
  elsewhere inside the project (hosts that can create one);
- every file is a named pipe (POSIX hosts);
- every file is a symbolic link to ``/dev/zero`` (Linux, where the child can
  cap its memory, so a regression fails fast instead of using up memory).

No validator may open or list a link, a named pipe, or anything that resolves
into the outside copy or to ``/dev/zero``, and each tree walker, and the plans
sweep, must name what it skipped under ``skipped_links``. The audit hook does
not see a ``stat`` call, so each test also deletes the links and pipes and runs
the validators again: every report and exit code must match, apart from
``skipped_links``, because a link counts as missing. Two exceptions are by
design: ``no-global-plans-grep`` reports a plans location that is a link, by
name, and a run that checked nothing because a link was in the way must not
pass. A first run over the outside copy itself shows that every validator does
reach these files when they are real, so a pass is not a validator that looked
at nothing, and every run must end in a pass or a findings exit, not a crash.
Windows junctions need no privilege, so the folder-link tests run everywhere.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import site
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from apothem.conformity import agent_capability_grep
from apothem.conformity._project_paths import is_link
from apothem.conformity.gate import STANDALONE_MODULES
from apothem.lib.harness_registry import HARNESS_REGISTRY
from tests._shared.git_env import hermetic_git_env

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Split so the license scanner does not read the fixture text as this file's
# own license tag.
_SPDX_HASH = "# SPDX-License-" + "Identifier: MIT"

_WORKFLOW = f"{_SPDX_HASH}\nname: ci\non: [push]\njobs: {{}}\n"
_PAGE = "---\nname: sample\ndescription: A sample page.\n---\n\n# Sample\n\nText.\n"
# A job that calls a reusable workflow in the same folder and passes it a
# time limit, so ``workflow-concurrency-grep`` reads the called file too.
_CALLER_WORKFLOW = (
    f"{_SPDX_HASH}\nname: caller\non: [push]\njobs:\n  call:\n"
    "    uses: ./.github/workflows/reusable.yml\n"
    "    with:\n      timeout-minutes: 30\n"
)

# Validators that open or list no project file in Python: one asks git for the
# last commit subject, the other only looks at the root entry named ``docs``,
# without following it.
_READS_NO_PROJECT_FILE = frozenset(
    {"conventional-commit-grep", "no-toplevel-docs-grep"}
)

# How long one child run of every validator may take.
_DEADLINE_SECONDS = 240
# Address-space cap for the child that meets /dev/zero links (Linux only).
_CHILD_ADDRESS_SPACE_BYTES = 1 << 30

_POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt", reason="named pipes exist only on POSIX systems"
)
_LINUX_ONLY = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="the child caps its memory with RLIMIT_AS, which Linux enforces",
)


def _project_files() -> dict[str, str]:
    """Return the files (relative path to text) that every validator reaches."""
    harness = agent_capability_grep.HARNESS_COHORT[0]
    return {
        "README.md": "# Sample\n\nVersion 1.2.3 of the sample.\n",
        "AGENTS.md": "# Agents\n",
        "CLAUDE.md": "# Claude\n",
        "pyproject.toml": '[project]\nname = "sample"\n',
        ".gitattributes": "* text=auto eol=lf\n",
        ".editorconfig": "root = true\n",
        ".github/copilot-instructions.md": "# Copilot\n",
        ".github/workflows/ci.yml": _WORKFLOW,
        ".github/workflows/ci-matrix.yml": _WORKFLOW,
        ".github/workflows/publish-pypi.yml": _WORKFLOW,
        ".github/workflows/caller.yml": _CALLER_WORKFLOW,
        ".apothem/plans/sample-suite/PROGRESS.md": "# Progress\n",
        ".apothem/plans/sample-suite/phases/01-start/PHASE.md": "# Phase\n",
        ".apothem/plans/sample-suite/phases/01-start/REPORT.md": "# Report\n",
        "scripts/installer/install.sh": "#!/bin/sh\nset -e\n",
        "scripts/installer/install.ps1": "Set-StrictMode -Version Latest\n",
        "site/package.json": '{"name": "sample"}\n',
        "site/content/docs/guide.md": _PAGE,
        "src/apothem/__init__.py": '__version__ = "1.2.3"\n',
        "src/apothem/agents/sample.md": _PAGE,
        "src/apothem/commands/sample.md": _PAGE,
        "src/apothem/hooks/messages/sample.md": _PAGE,
        "src/apothem/lib/propagation-manifest.yaml": "harnesses: {}\n",
        f"src/apothem/harnesses/{harness}/capabilities.yaml": "mcp_servers: []\n",
        "src/apothem/output-styles/default.md": _PAGE,
        "src/apothem/rules/sample-rule.md": _PAGE,
        "src/apothem/skills/sample/SKILL.md": _PAGE,
        "tests/fixtures/plans-discipline.txt": "Plans live in the project.\n",
    }


def _second_reads() -> list[str]:
    """Return files a validator reads only after another file passed its checks.

    - ``plan-next-step-consistency-grep``: a suite's other plan files, once its
      ``PROGRESS.md`` is real;
    - ``gate-evidence-grep``: a suite's completion, attestation and hand-off
      files;
    - ``registry-capability-consistency-grep``: each harness's
      ``materializer.py``, after the propagation manifest;
    - ``workflow-concurrency-grep``: the reusable workflow a caller job names.
    """
    suite = ".apothem/plans/sample-suite"
    return [
        f"{suite}/MASTER-PLAN.md",
        f"{suite}/MASTER-INDEX.md",
        f"{suite}/TRACE-MATRIX.md",
        f"{suite}/COMPLETION.md",
        f"{suite}/attestation.yml",
        f"{suite}/_inputs/handoff-manifest.yml",
        f"src/apothem/harnesses/{HARNESS_REGISTRY[0].package_key}/materializer.py",
        ".github/workflows/reusable.yml",
    ]


def _git_init(folder: Path) -> None:
    """Make *folder* an empty git repository with fixture git."""
    subprocess.run(
        ["git", "init", "-q"],
        cwd=str(folder),
        env=hermetic_git_env(),
        check=True,
        capture_output=True,
    )


def _write_tree(folder: Path, files: dict[str, str]) -> None:
    """Write *files* under *folder*."""
    for rel, text in files.items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))


def _link_folder(link: Path, target: Path) -> None:
    """Make *link* a folder link to *target*: a junction on Windows."""
    if os.name == "nt":
        winapi = pytest.importorskip("_winapi")
        winapi.CreateJunction(str(target), str(link))
        return
    link.symlink_to(target, target_is_directory=True)


def _symlink_or_skip(link: Path, target: Path) -> None:
    """Make *link* a symbolic link to *target*, or skip where that is not allowed."""
    try:
        link.symlink_to(target)
    except OSError as exc:  # Windows without the symbolic-link privilege
        pytest.skip(f"cannot create a symbolic link here: {exc}")


def _remove_special(path: Path) -> None:
    """Delete a link or a named pipe; the folder or file it points to stays."""
    if os.name == "nt" and path.is_dir():
        path.rmdir()  # a junction is a folder entry; rmdir removes the link alone
    else:
        path.unlink()


@pytest.fixture(scope="module")
def outside(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The outside copy: a git repository holding every file, all real."""
    folder = tmp_path_factory.mktemp("outside-copy")
    _write_tree(folder, _project_files())
    _git_init(folder)
    return folder


def _top_level_folder_links(project: Path, outside: Path) -> list[Path]:
    """Link every top-level folder into *outside*; copy the top-level files."""
    files = _project_files()
    links = [
        project / top
        for top in sorted({rel.split("/", 1)[0] for rel in files if "/" in rel})
    ]
    for link in links:
        _link_folder(link, outside / link.name)
    _write_tree(project, {rel: text for rel, text in files.items() if "/" not in rel})
    return links


def _deepest_folder_links(project: Path, outside: Path) -> list[Path]:
    """Link every folder that holds files but no further folder of the tree."""
    files = _project_files()
    parents = {Path(rel).parent.as_posix() for rel in files}
    leaves = sorted(
        parent
        for parent in parents
        if parent != "."
        and not any(other.startswith(parent + "/") for other in parents)
    )
    for leaf in leaves:
        (project / leaf).parent.mkdir(parents=True, exist_ok=True)
        _link_folder(project / leaf, outside / leaf)
    _write_tree(
        project,
        {
            rel: text
            for rel, text in files.items()
            if Path(rel).parent.as_posix() not in leaves
        },
    )
    return [project / leaf for leaf in leaves]


def _middle_folder_links(project: Path, outside: Path) -> list[Path]:
    """Link every second-level folder, with a real folder above it.

    A link in the middle of a path, such as ``src/apothem`` under a real
    ``src``, must stop a validator as a link at either end does.
    """
    files = _project_files()
    middles = sorted(
        {"/".join(rel.split("/")[:2]) for rel in files if rel.count("/") >= 2}
    )
    for middle in middles:
        (project / middle).parent.mkdir(parents=True, exist_ok=True)
        _link_folder(project / middle, outside / middle)
    _write_tree(
        project, {rel: text for rel, text in files.items() if rel.count("/") < 2}
    )
    return [project / middle for middle in middles]


def _file_links(project: Path, outside: Path) -> list[Path]:
    """Make every file a symbolic link to its outside copy."""
    links = [project / rel for rel in _project_files()]
    for link in links:
        link.parent.mkdir(parents=True, exist_ok=True)
        _symlink_or_skip(link, outside / link.relative_to(project))
    return links


def _inside_file_links(project: Path, outside: Path) -> list[Path]:
    """Make every file a link to a real copy kept elsewhere in the project.

    The copies stay when the links are deleted, so both runs see them.
    """
    del outside
    files = _project_files()
    copies = project / "linked-copies"
    _write_tree(copies, files)
    links = [project / rel for rel in files]
    for link in links:
        link.parent.mkdir(parents=True, exist_ok=True)
        target = copies / link.relative_to(project)
        _symlink_or_skip(link, Path(os.path.relpath(target, link.parent)))
    return links


def _named_pipes(project: Path, outside: Path) -> list[Path]:
    """Make every file a named pipe."""
    del outside
    pipes = [project / rel for rel in _project_files()]
    for pipe in pipes:
        pipe.parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(pipe)
    return pipes


def _device_links(project: Path, outside: Path) -> list[Path]:
    """Make every file a symbolic link to ``/dev/zero``."""
    del outside
    links = [project / rel for rel in _project_files()]
    for link in links:
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to("/dev/zero")
    return links


# The child process: it records every file opened and folder listed, then runs
# each validator as ``__main__`` with the root as its argument, as the gate's
# own launcher does, keeping each validator's printed report and exit code.
# Events go to a file opened before the hook is set, one JSON line each, so a
# run that stalls still leaves its record.
_CHILD_SCRIPT = r"""
import contextlib
import io
import json
import os
import runpy
import sys

events_path, results_path, root, limit = sys.argv[1:5]
modules = sys.argv[5:]
if int(limit):
    import resource

    try:
        resource.setrlimit(resource.RLIMIT_AS, (int(limit), int(limit)))
    except (OSError, ValueError):
        pass
log = open(events_path, "a", encoding="utf-8", buffering=1)
current = ["-"]


def hook(event, args):
    if event not in ("open", "os.scandir", "os.listdir") or not args:
        return
    target = args[0]
    if target is None or isinstance(target, int):
        return
    try:
        text = os.fsdecode(os.fspath(target))
    except TypeError:
        return
    log.write(json.dumps([current[0], event, os.path.abspath(text)]) + "\n")


sys.addaudithook(hook)
results = {}
for module in modules:
    current[0] = module
    log.write(json.dumps([module, "start", ""]) + "\n")
    sys.argv = [module, root]
    report = io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(report):
            runpy.run_module(
                "apothem.conformity." + module.replace("-", "_"),
                run_name="__main__",
                alter_sys=True,
            )
    except SystemExit as exc:
        code = exc.code
    except BaseException as exc:  # a crash is a result too
        code = "crashed: " + type(exc).__name__
    current[0] = "-"
    results[module] = [code, report.getvalue()]
with open(results_path, "w", encoding="utf-8") as handle:
    json.dump(results, handle)
log.write(json.dumps(["-", "done", ""]) + "\n")
"""

_Events = list[list[str]]
_Results = dict[str, list[object]]


def _run_validators(root: Path, scratch: Path) -> tuple[_Events, _Results]:
    """Run every standalone validator over *root*; return events and results."""
    scratch.mkdir(parents=True, exist_ok=True)
    events_path = scratch / "events.jsonl"
    results_path = scratch / "results.json"
    limit = _CHILD_ADDRESS_SPACE_BYTES if sys.platform.startswith("linux") else 0
    env = hermetic_git_env()
    env["PYTHONPATH"] = str(_REPO_ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # A run past the deadline is killed; the events show where it stopped.
    with contextlib.suppress(subprocess.TimeoutExpired):
        subprocess.run(
            [
                sys.executable,
                "-c",
                _CHILD_SCRIPT,
                str(events_path),
                str(results_path),
                str(root),
                str(limit),
                *STANDALONE_MODULES,
            ],
            cwd=str(scratch),
            env=env,
            capture_output=True,
            timeout=_DEADLINE_SECONDS,
            check=False,
        )
    lines = events_path.read_text(encoding="utf-8").splitlines()
    events: _Events = [json.loads(line) for line in lines if line]
    if not events or events[-1][1] != "done":
        started = [label for label, event, _ in events if event == "start"]
        stalled = started[-1] if started else "(none)"
        pytest.fail(f"the run stopped for good inside {stalled}")
    results: _Results = json.loads(results_path.read_text(encoding="utf-8"))
    return events, results


def _assert_exits_cleanly(results: _Results) -> None:
    """Every validator ended in a pass (0) or a findings exit (2), not a crash."""
    odd = {
        label: code for label, (code, _report) in results.items() if code not in (0, 2)
    }

    assert odd == {}


def _is_below(path: str, folder: Path) -> bool:
    """Return True when *path*, links resolved, lies strictly below *folder*."""
    real = os.path.normcase(os.path.realpath(path))
    base = os.path.normcase(os.path.realpath(folder))
    return real.startswith(base + os.sep)


def test_every_validator_reaches_the_files_when_they_are_real(
    outside: Path, tmp_path: Path
) -> None:
    """The control run: over the outside copy itself, each validator reads it."""
    events, results = _run_validators(outside, tmp_path / "scratch")
    _assert_exits_cleanly(results)
    reached = {
        label for label, _event, path in events if path and _is_below(path, outside)
    }
    expected = set(STANDALONE_MODULES) - _READS_NO_PROJECT_FILE

    assert sorted(expected - reached) == []


_Builder = Callable[[Path, Path], list[Path]]

# The validator that reports a plans location that is a link, by name.
_PLANS_SWEEP = "no-global-plans-grep"

# The validators that walk a tree with the shared walk and read what they
# find; each must name what it left out under ``skipped_links`` in every case
# here.
# naming-grep reads no content: it checks each link by its own name, so it
# lists no skipped link and its report counts names the links-deleted twin
# lacks. Its own test covers it.
_NAME_CHECKER = "naming-grep"

_TREE_WALKERS = frozenset(
    {
        "agents-md-coverage-grep",
        "agnosticism-grep",
        "dynamism-grep",
        "freshness-token-grep",
        "plain-language-grep",
        "reference-token-grep",
    }
)


def _comparable(result: list[object]) -> list[object]:
    """Return a result without its ``skipped_links`` list, the one part a link adds."""
    code, report = result
    try:
        payload = json.loads(str(report))
    except ValueError:
        return [code, report]
    if isinstance(payload, dict):
        payload.pop("skipped_links", None)
    return [code, payload]


def _differs(linked: list[object], missing: list[object]) -> bool:
    """Return True when a linked run does not match its links-deleted twin.

    A run that checked nothing because a link was in the way must not pass;
    apart from that it reports what the run without the link reports.
    """
    report = json.loads(str(linked[1]))
    if report.get("inspected") == 0 and report.get("skipped_links"):
        twin = json.loads(str(missing[1]))
        return report.get("passed") is not False or report.get("findings") != twin.get(
            "findings"
        )
    return _comparable(linked) != _comparable(missing)


def _finding_paths(result: list[object]) -> list[str]:
    """Return the ``path`` of each finding in a validator's printed report."""
    payload = json.loads(str(result[1]))
    return [str(finding.get("path")) for finding in payload.get("findings", [])]


@pytest.mark.parametrize(
    ("build", "plans_link", "same_once_deleted"),
    [
        pytest.param(
            _top_level_folder_links, ".apothem/", True, id="top-level-folder-links"
        ),
        pytest.param(
            _middle_folder_links, ".apothem/plans/", True, id="middle-folder-links"
        ),
        pytest.param(_deepest_folder_links, None, True, id="deepest-folder-links"),
        pytest.param(_file_links, None, True, id="file-links"),
        pytest.param(_inside_file_links, None, False, id="links-inside-the-project"),
        pytest.param(_named_pipes, None, True, id="named-pipes", marks=_POSIX_ONLY),
        pytest.param(_device_links, None, True, id="dev-zero-links", marks=_LINUX_ONLY),
    ],
)
def test_no_validator_reaches_through_a_link_or_a_pipe(
    outside: Path,
    tmp_path: Path,
    build: _Builder,
    plans_link: str | None,
    same_once_deleted: bool,
) -> None:
    """No validator opens or lists through a link or a pipe, and each one says so.

    A link or pipe counts as missing, so each report equals the report once
    they are deleted, apart from ``skipped_links``, which names them. Two
    exceptions are by design: a fixed file that links to a regular file in the
    project is read at that file (the links-inside-the-project case is checked
    by the audit hook alone), and ``no-global-plans-grep`` reports a plans
    location that is a link, by name.
    """
    project = tmp_path / "project"
    project.mkdir()
    _git_init(project)
    specials = build(project, outside)
    events, linked = _run_validators(project, tmp_path / "linked-run")
    _assert_exits_cleanly(linked)

    def offends(path: str) -> bool:
        if not path:
            return False
        if _is_below(path, outside) or os.path.realpath(path) == "/dev/zero":
            return True
        here = Path(path)
        return any(here == special or special in here.parents for special in specials)

    offenders = sorted(
        {f"{label}: {event} {path}" for label, event, path in events if offends(path)}
    )
    assert offenders == []
    # The plans sweep lists folders only, so a named pipe is not its concern.
    tracers = set(_TREE_WALKERS)
    if build is not _named_pipes:
        tracers.add(_PLANS_SWEEP)
    untraced = sorted(
        label
        for label in tracers
        if not json.loads(str(linked[label][1])).get("skipped_links")
    )
    assert untraced == [], untraced
    if plans_link is not None:
        assert plans_link in _finding_paths(linked[_PLANS_SWEEP])
    if not same_once_deleted:
        return

    for special in specials:
        _remove_special(special)
    _events, missing = _run_validators(project, tmp_path / "missing-run")
    _assert_exits_cleanly(missing)
    compared = [
        label
        for label in missing
        if label != _NAME_CHECKER and not (plans_link and label == _PLANS_SWEEP)
    ]
    changed = sorted(
        label for label in compared if _differs(linked[label], missing[label])
    )

    assert changed == [], {
        label: (linked.get(label), missing[label]) for label in changed
    }


@_POSIX_ONLY
def test_a_named_pipe_read_after_a_real_file_is_not_opened(tmp_path: Path) -> None:
    """A file a validator reads after a real one is checked too.

    Every file the other tests use is real here, so each validator gets past
    its first read and goes on to the files beside it; each of those is a
    named pipe, which a read would wait on for ever.
    """
    project = tmp_path / "project"
    project.mkdir()
    _git_init(project)
    _write_tree(project, _project_files())
    pipes = [project / rel for rel in _second_reads()]
    for pipe in pipes:
        pipe.parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(pipe)
    events, results = _run_validators(project, tmp_path / "run")
    _assert_exits_cleanly(results)
    opened = sorted(
        {
            f"{label}: {path}"
            for label, event, path in events
            if event == "open" and Path(path) in pipes
        }
    )

    assert opened == []


# ---------------------------------------------------------------------------
# A project whose .git names a foreign repository
# ---------------------------------------------------------------------------

# The child for the foreign-repository runs: every standalone validator as
# ``__main__`` (as ``--all`` starts each one), then the ``--all-perwrite``
# corpus run in the same process, under one audit hook that records each file
# opened, each folder listed and each program started.
_ORACLE_SCRIPT = r"""
import contextlib
import io
import json
import os
import runpy
import sys
from pathlib import Path

events_path, root = sys.argv[1:3]
modules = sys.argv[3:]
log = open(events_path, "a", encoding="utf-8", buffering=1)
current = ["-"]


def hook(event, args):
    if event == "subprocess.Popen":
        started = args[0] if args[0] is not None else args[1]
        if isinstance(started, (list, tuple)):
            started = started[0]
        log.write(json.dumps([current[0], event, os.fsdecode(started)]) + "\n")
        return
    # On Windows the corpus run opens each file with _winapi.CreateFile,
    # which raises only its own event: it counts as an open.
    if event == "_winapi.CreateFile":
        event = "open"
    if event not in ("open", "os.scandir", "os.listdir") or not args:
        return
    target = args[0]
    if target is None or isinstance(target, int):
        return
    try:
        text = os.fsdecode(os.fspath(target))
    except TypeError:
        return
    log.write(json.dumps([current[0], event, os.path.abspath(text)]) + "\n")


from apothem.conformity import gate

sys.addaudithook(hook)
for module in modules:
    current[0] = module
    sys.argv = [module, root]
    with contextlib.redirect_stdout(io.StringIO()):
        with contextlib.suppress(SystemExit):
            runpy.run_module(
                "apothem.conformity." + module.replace("-", "_"),
                run_name="__main__",
                alter_sys=True,
            )
current[0] = "all-perwrite"
passed, payload = gate._run_all_perwrite(Path(root))
current[0] = "-"
log.write(json.dumps(["-", "perwrite", payload]) + "\n")
log.write(json.dumps(["-", "done", ""]) + "\n")
"""


def _commit_all(repository: Path, *names: str) -> None:
    """Commit *names* in *repository*, each a small text file."""
    for name in names:
        _write_tree(repository, {name: "# Page\n\nText.\n"})
    env = hermetic_git_env()
    for args in (
        ["add", "--", *names],
        [
            "-c",
            "user.email=test@apothem.invalid",
            "-c",
            "user.name=apothem-test",
            "-c",
            "commit.gpgsign=false",
            # No maintenance in the background: it writes lock files into
            # .git while a test copies it.
            "-c",
            "maintenance.auto=false",
            "-c",
            "gc.auto=0",
            "commit",
            "-qm",
            "feat: foreign repository",
        ],
    ):
        subprocess.run(
            ["git", *args],
            cwd=str(repository),
            env=env,
            check=True,
            capture_output=True,
        )


# The names the foreign index tracks, below the root. In the project, the
# first is a folder link out (a junction on Windows), the second lies below a
# folder link out, the third is missing, and README.md is the one regular file.
_FOREIGN_NAMES = ("link-out.md", "via/page.md", "missing.md", "README.md")

# How the project points git at the foreign repository. None of them puts a
# link on git's search path, so the link rule lets git run in each.
# - gitdir: the project's .git is a file naming the foreign .git folder.
# - commondir: it names a work-tree folder whose commondir file gives the
#   foreign .git folder as an absolute path.
# - subfolder-root: as gitdir, with the root a subfolder of the project, so
#   the .git file lies above the root.
# - objects-junction: a real .git folder whose objects folder is a link to
#   the foreign object store.
# - alternates: a real .git folder whose objects/info/alternates names the
#   foreign object store.
# - include: a real .git folder whose config includes a file outside.
# - core-worktree: a real .git folder whose core.worktree names the foreign
#   work tree.
_ROUTES = (
    "gitdir",
    "commondir",
    "subfolder-root",
    "objects-junction",
    "alternates",
    "include",
    "core-worktree",
)


def _project_naming_a_foreign_repository(tmp_path: Path, route: str) -> Path:
    """Return the root of a project that sends git to a foreign repository.

    The foreign repository holds no link. See :data:`_ROUTES` for *route*.
    """
    below = "sub/" if route == "subfolder-root" else ""
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    _git_init(foreign)
    _commit_all(foreign, *(below + name for name in _FOREIGN_NAMES))
    elsewhere = tmp_path / "elsewhere"
    _write_tree(
        elsewhere,
        {
            "page.md": "# Outside\n",
            "link-out.md/page.md": "# Out\n",
            "extra.config": "[core]\n\tquotePath = false\n",
        },
    )
    project = tmp_path / "project"
    project.mkdir()
    gitdir = foreign / ".git"
    if route == "commondir":
        gitdir = foreign / ".git" / "worktrees" / "project"
        gitdir.mkdir(parents=True)
        (gitdir / "HEAD").write_text("ref: refs/heads/side\n", encoding="utf-8")
        (gitdir / "commondir").write_text(
            str(foreign / ".git") + "\n", encoding="utf-8"
        )
        (gitdir / "gitdir").write_text(str(project / ".git") + "\n", encoding="utf-8")
        shutil.copyfile(foreign / ".git" / "index", gitdir / "index")
    if route in ("gitdir", "commondir", "subfolder-root"):
        (project / ".git").write_text(
            f"gitdir: {gitdir.as_posix()}\n", encoding="utf-8"
        )
    else:
        own = project / ".git"
        shutil.copytree(foreign / ".git", own, ignore=shutil.ignore_patterns("*.lock"))
        if route in ("objects-junction", "alternates"):
            # git writes its objects read-only; Windows will not delete those.
            for stored in (own / "objects").rglob("*"):
                if stored.is_file():
                    stored.chmod(stat.S_IWRITE | stat.S_IREAD)
        if route == "objects-junction":
            shutil.rmtree(own / "objects")
            _link_folder(own / "objects", foreign / ".git" / "objects")
        elif route == "alternates":
            shutil.rmtree(own / "objects")
            (own / "objects" / "info").mkdir(parents=True)
            (own / "objects" / "info" / "alternates").write_text(
                str(foreign / ".git" / "objects") + "\n", encoding="utf-8"
            )
        elif route == "include":
            with (own / "config").open("a", encoding="utf-8") as config:
                config.write(
                    f"[include]\n\tpath = {(elsewhere / 'extra.config').as_posix()}\n"
                )
        else:
            with (own / "config").open("a", encoding="utf-8") as config:
                config.write(f"[core]\n\tworktree = {foreign.as_posix()}\n")
    root = project / below if below else project
    _write_tree(root, {"README.md": "# Sample\n\nText.\n"})
    _link_folder(root / "link-out.md", elsewhere / "link-out.md")
    _link_folder(root / "via", elsewhere)
    return root


@pytest.mark.parametrize("route", _ROUTES)
def test_a_foreign_repository_reaches_no_file_outside(
    tmp_path: Path, route: str
) -> None:
    """git may read another repository; the gate still reads only the project.

    No route puts a link on git's search path, so the link rule lets git run,
    and git lists names that, in the project, are a link out, a path through
    a junction and a missing file. Every file the validators and the
    ``--all-perwrite`` run open, and every folder they list, must be a regular
    file or a real folder inside the root, reached through real folders, and
    the only program they start is git.
    """
    root = _project_naming_a_foreign_repository(tmp_path, route)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    events_path = scratch / "events.jsonl"
    env = hermetic_git_env()
    env["PYTHONPATH"] = str(_REPO_ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [
            sys.executable,
            "-c",
            _ORACLE_SCRIPT,
            str(events_path),
            str(root),
            *STANDALONE_MODULES,
        ],
        cwd=str(scratch),
        env=env,
        capture_output=True,
        timeout=_DEADLINE_SECONDS,
        check=False,
    )
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert events
    assert events[-1][1] == "done"
    perwrite = json.loads(
        next(path for _, event, path in events if event == "perwrite")
    )
    if route != "core-worktree":
        # With core.worktree naming another folder, what git lists from the
        # project is git's own business; only the reads below are checked.
        # git listed the foreign names, and only the regular file was read.
        assert perwrite.get("check_error") is None
        assert perwrite["files_scanned"] == 1
        assert perwrite["files_skipped"]["link"] == 2
        assert perwrite["files_skipped"]["missing"] == 1
        # The control: the hook saw the one read, so it is not blind here.
        assert any(
            label == "all-perwrite"
            and event == "open"
            and Path(path) == root / "README.md"
            for label, event, path in events
        )

    # Python's own reads: the interpreter, its packages and this checkout's
    # source. A folder that holds the project does not count.
    project = tmp_path / "project"
    runtime = [
        Path(folder).resolve()
        for folder in {
            *sys.path,
            sys.prefix,
            sys.base_prefix,
            sys.exec_prefix,
            site.getusersitepackages(),
            str(_REPO_ROOT / "src"),
        }
        if folder
        and project not in Path(folder).resolve().parents
        and Path(folder).resolve() != project
        and Path(folder).resolve() not in project.parents
    ]

    # git's input is the null device. On Windows only os.path.abspath gives
    # its device path, the spelling the hook records; Path.absolute does not.
    nothing = {events_path, Path(os.path.abspath(os.devnull))}  # noqa: PTH100

    def runtime_read(path: Path) -> bool:
        return path in nothing or any(
            path == base or base in path.parents for base in runtime
        )

    def real(path: Path, want: Callable[[int], bool]) -> bool | None:
        """Return whether *path* is no link and *want* its mode; None if absent."""
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            return None
        return not is_link(info) and want(info.st_mode)

    def stays_inside(event: str, path: Path) -> bool:
        if path != root and root not in path.parents:
            return False
        # Each level below the root is a real folder, not a link of any kind
        # (a junction lstats as a folder on Windows), and the target is a
        # regular file (open) or a real folder (a listing). A path that does
        # not exist is fine when the levels that do are real folders: the
        # open fails without reaching anything.
        level = root
        for part in path.relative_to(root).parts[:-1]:
            level = level / part
            found = real(level, stat.S_ISDIR)
            if found is None:
                return True
            if not found:
                return False
        found = real(path, stat.S_ISREG if event == "open" else stat.S_ISDIR)
        return found is None or found

    offenders = sorted(
        f"{label}: {event} {path}"
        for label, event, path in events
        if label != "-"
        and event in ("open", "os.scandir", "os.listdir")
        and not runtime_read(Path(path))
        and not stays_inside(event, Path(path))
    )

    def program(started: str) -> str:
        # On Windows the program can arrive as one command line, its path
        # first and in quotes when it holds a space.
        if started.startswith('"'):
            started = started[1:].split('"', 1)[0]
        elif not Path(started).exists():
            started = started.split(" ", 1)[0]
        return Path(started).name.lower()

    programs = {
        program(path) for _, event, path in events if event == "subprocess.Popen"
    }

    assert offenders == []
    assert programs
    assert programs <= {"git", "git.exe"}
