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
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from apothem.conformity import agent_capability_grep
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
