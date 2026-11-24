# SPDX-License-Identifier: MIT

"""The gate's git commands never start a program the checked project names.

Why these tests exist. The conformity gate runs git inside the project it
checks: ``git ls-files`` for ``--all-perwrite`` and ``no-global-plans-grep``,
``git log`` for ``conventional-commit-grep`` and ``agents-md-coverage-grep``,
and ``git diff --cached`` / ``git cat-file`` for the two ``--staged``
change-set checks. git reads that repository's own ``.git/config`` on every
run, and a project that arrives with its ``.git`` folder (an archive, a shared
folder) can plant settings there that make git start a program while it only
reads.

Each scenario below plants one such setting in a throwaway repository, proves
the plant is live by running the matching plain git command (the planted
program then runs and leaves a marker file), and then drives every git call
the gate makes. No marker may appear. The scenarios that a plain git command
triggers today are the file-system monitor (``core.fsmonitor``, also through
``include.path`` and ``.git/config.worktree``), commit-signature checks
(``log.showSignature`` with the OpenPGP, SSH and X.509 programs), the lazy
fetch of a partial clone (``remote.<name>.uploadpack``, ``core.sshCommand``,
``ext::``), and a staged submodule entry shown as a commit: a ``%G?`` in
``format.pretty`` starts the signature program, and ``diff.submodule=diff``
starts a second git inside a submodule with its own ``diff.external``. Hooks,
filters, diff programs and pagers do not run for the gate's commands today;
they are planted too, so a later command change cannot bring them back
unnoticed.

The tests after the scenarios cover how the gate reads git's output: the
record marker of ``agents-md-coverage-grep``'s log format, non-ASCII path
names, a missing root, and the forward-slash path of the version check.

HERMETIC: every repository lives under ``tmp_path``. The fixture git commands
and the plain controls run with :func:`hermetic_git_env`, and the gate's own
git calls see the same hidden global and system configuration, so the
developer's git configuration changes nothing here.
"""

from __future__ import annotations

import ast
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from apothem.conformity import _git as git_helper
from apothem.conformity import (
    agents_md_coverage_grep,
    conventional_commit_grep,
    gate,
    no_global_plans_grep,
    production_ready_pr_grep,
    semver_stability_grep,
)
from apothem.conformity._grep_base import GitCheckError
from tests._shared.git_env import hermetic_git_env

_IDENT = (
    "-c",
    "user.name=Apothem Test",
    "-c",
    "user.email=test@apothem.invalid",
    "-c",
    "commit.gpgSign=false",
)
_TRACKED = "src/apothem/x.py"

# Signature blocks git recognizes by their first line; the payload is never
# checked because the planted program stands in for the real one.
_SIGNATURES = {
    "openpgp": [
        "-----BEGIN PGP SIGNATURE-----",
        "",
        "wsBcBAABCAAQBQJlAAAACRAAAAAAAAAAAAAAAA==",
        "=AAAA",
        "-----END PGP SIGNATURE-----",
    ],
    "ssh": [
        "-----BEGIN SSH SIGNATURE-----",
        "U1NIU0lHAAAAAQ==",
        "-----END SSH SIGNATURE-----",
    ],
    "x509": [
        "-----BEGIN SIGNED MESSAGE-----",
        "MIAGCSqGSIb3DQEHAqCAMIACAQEx",
        "-----END SIGNED MESSAGE-----",
    ],
}

_HOOK_NAMES = (
    "applypatch-msg",
    "pre-applypatch",
    "post-applypatch",
    "pre-commit",
    "pre-merge-commit",
    "prepare-commit-msg",
    "commit-msg",
    "post-commit",
    "pre-rebase",
    "post-checkout",
    "post-merge",
    "pre-push",
    "pre-receive",
    "update",
    "proc-receive",
    "post-receive",
    "post-update",
    "reference-transaction",
    "push-to-checkout",
    "pre-auto-gc",
    "post-rewrite",
    "sendemail-validate",
    "fsmonitor-watchman",
    "post-index-change",
)


def _git(
    repo: Path,
    *args: str,
    data: bytes | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """Run a fixture git command in *repo* with no host configuration."""
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        env={**hermetic_git_env(), **(env or {})},
        input=data,
        stdin=None if data is not None else subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=60,
    )
    stderr = completed.stderr.decode("utf-8", "replace")
    assert completed.returncode == 0, f"git {' '.join(args)}: {stderr}"
    return completed.stdout.decode("utf-8", "replace").strip()


def _plain(repo: Path, *args: str) -> str:
    """Run plain git, as the gate did before, so a planted program can run.

    Returns git's error output, for the message of a control that ran nothing.
    A host that already blocks fetching for every git would hide the
    partial-clone plants, so the two variables that do it are dropped here.
    """
    env = hermetic_git_env()
    env.pop("GIT_ALLOW_PROTOCOL", None)
    env.pop("GIT_NO_LAZY_FETCH", None)
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=60,
    )
    return completed.stderr.decode("utf-8", "replace")


def _config(repo: Path, key: str, value: str) -> None:
    _git(repo, "config", "--local", key, value)


_VERSIONED = "src/apothem/__init__.py"
_LINKED = "src/apothem/linked.py"


def _build_repo(repo: Path) -> Path:
    """Two commits, a staged change to a public module, an unstaged one on top.

    The staged change drops the public ``g``, so the change-set check finds a
    breaking change and goes on to read ``src/apothem/__init__.py`` as well.
    """
    repo.mkdir()
    _git(repo, "-c", "init.defaultBranch=main", "init", "-q")
    (repo / "src" / "apothem").mkdir(parents=True)
    (repo / _VERSIONED).write_bytes(b'__version__ = "1.2.3"\n')
    (repo / _TRACKED).write_bytes(
        b"def f():\n    return 1\n\n\ndef g():\n    return 1\n"
    )
    (repo / "README.md").write_bytes(b"# readme\n")
    (repo / ".gitattributes").write_bytes(b"* diff=planted filter=planted\n")
    _git(repo, "add", "-A")
    _git(repo, *_IDENT, "commit", "-q", "-m", "feat: add x")
    (repo / "README.md").write_bytes(b"# readme, second\n")
    _git(repo, "add", "-A")
    _git(repo, *_IDENT, "commit", "-q", "-m", "docs: reword the readme")
    (repo / _TRACKED).write_bytes(b"def f():\n    return 2\n")
    _git(repo, "add", "-A")
    (repo / _TRACKED).write_bytes(b"def f():\n    return 3\n")
    return repo


def _signed_copy_of_head(repo: Path, fmt: str) -> str:
    """Write a copy of HEAD that carries a *fmt* signature header; return its id."""
    header, _, message = _git(repo, "cat-file", "commit", "HEAD").partition("\n\n")
    signature = "\n ".join(_SIGNATURES[fmt])
    signed = f"{header}\ngpgsig {signature}\n\n{message}\n"
    return _git(
        repo, "hash-object", "-t", "commit", "-w", "--stdin", data=signed.encode()
    )


def _sign_head(repo: Path, fmt: str) -> None:
    """Replace HEAD with a copy that carries a *fmt* signature header."""
    _git(repo, "update-ref", "refs/heads/main", _signed_copy_of_head(repo, fmt))


def _stage_gitlink(repo: Path, path: str, oid: str) -> None:
    """Stage a gitlink (a submodule entry, mode 160000) at *path* naming *oid*."""
    _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{oid},{path}")


def _drop_head_objects(repo: Path) -> None:
    """Delete HEAD's trees and the tracked blob, so reading them needs a fetch."""
    # Resolve every object first: once the root tree is gone, git can no
    # longer walk to the others.
    oids = [
        _git(repo, "rev-parse", spec)
        for spec in ("HEAD^{tree}", "HEAD:src", "HEAD:src/apothem", f"HEAD:{_TRACKED}")
    ]
    for oid in oids:
        loose = repo / ".git" / "objects" / oid[:2] / oid[2:]
        loose.chmod(0o644)
        loose.unlink()


class _Programs:
    """Write planted programs that record each run in a marker folder."""

    def __init__(self, base: Path) -> None:
        self.bin = base / "bin"
        self.markers = base / "markers"
        self.bin.mkdir()
        self.markers.mkdir()

    def __call__(self, name: str) -> str:
        program = self.bin / name
        marker = (self.markers / f"{name}.ran").as_posix()
        program.write_bytes(f"#!/bin/sh\necho ran >> '{marker}'\nexit 0\n".encode())
        program.chmod(0o755)
        return program.as_posix()

    def ran(self) -> list[str]:
        return sorted(path.stem for path in self.markers.iterdir())

    def clear(self) -> None:
        for path in self.markers.iterdir():
            path.unlink()


Plant = Callable[[Path, _Programs, Path], None]


@dataclass(frozen=True)
class _Scenario:
    name: str
    plant: Plant
    # Plain git arguments that run the planted program today; None when no
    # plain command can show it without a terminal.
    control: tuple[str, ...] | None


def _fsmonitor(repo: Path, programs: _Programs, outside: Path) -> None:
    _config(repo, "core.fsmonitor", programs("fsmonitor"))


def _fsmonitor_included(repo: Path, programs: _Programs, outside: Path) -> None:
    included = outside / "included.config"
    included.write_bytes(f"[core]\n\tfsmonitor = {programs('fsmonitor')}\n".encode())
    _config(repo, "include.path", included.as_posix())


def _fsmonitor_worktree(repo: Path, programs: _Programs, outside: Path) -> None:
    _config(repo, "core.repositoryformatversion", "1")
    _config(repo, "extensions.worktreeConfig", "true")
    (repo / ".git" / "config.worktree").write_bytes(
        f"[core]\n\tfsmonitor = {programs('fsmonitor')}\n".encode()
    )


def _signature(fmt: str, key: str) -> Plant:
    def plant(repo: Path, programs: _Programs, outside: Path) -> None:
        _sign_head(repo, fmt)
        _config(repo, "log.showSignature", "true")
        _config(repo, key, programs("signature"))
        if fmt == "ssh":
            # git checks an SSH signature only when this file exists.
            allowed = outside / "allowed-signers"
            allowed.write_bytes(
                b"test@apothem.invalid ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIA==\n"
            )
            _config(repo, "gpg.ssh.allowedSignersFile", allowed.as_posix())

    return plant


def _lazy_fetch(kind: str) -> Plant:
    def plant(repo: Path, programs: _Programs, outside: Path) -> None:
        _config(repo, "core.repositoryformatversion", "1")
        _config(repo, "extensions.partialClone", "origin")
        _config(repo, "remote.origin.promisor", "true")
        if kind == "upload-pack":
            upstream = outside / "upstream.git"
            _git(outside, "init", "-q", "--bare", upstream.name)
            _config(repo, "remote.origin.url", upstream.as_posix())
            _config(repo, "remote.origin.uploadpack", programs("transport"))
            _config(repo, "protocol.file.allow", "always")
        elif kind == "ssh-command":
            _config(repo, "remote.origin.url", "ssh://example.invalid/planted.git")
            _config(repo, "core.sshCommand", programs("transport"))
            _config(repo, "protocol.ssh.allow", "always")
        else:
            _config(repo, "remote.origin.url", f"ext::{programs('transport')}")
            _config(repo, "protocol.ext.allow", "always")
        _drop_head_objects(repo)

    return plant


def _hooks_folder(repo: Path, programs: _Programs, outside: Path) -> None:
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    source = Path(programs("hook"))
    for name in _HOOK_NAMES:
        shutil.copyfile(source, hooks / name)
        (hooks / name).chmod(0o755)


def _hooks_path(repo: Path, programs: _Programs, outside: Path) -> None:
    hooks = outside / "hooks"
    hooks.mkdir()
    source = Path(programs("hook"))
    for name in _HOOK_NAMES:
        shutil.copyfile(source, hooks / name)
        (hooks / name).chmod(0o755)
    _config(repo, "core.hooksPath", hooks.as_posix())


def _setting(key: str, program: str) -> Plant:
    def plant(repo: Path, programs: _Programs, outside: Path) -> None:
        _config(repo, key, programs(program))

    return plant


def _pagers(repo: Path, programs: _Programs, outside: Path) -> None:
    _config(repo, "core.pager", programs("pager"))
    for command in ("log", "show", "diff", "ls-files"):
        _config(repo, f"pager.{command}", programs("pager"))


def _gitlink_signature(repo: Path, programs: _Programs, outside: Path) -> None:
    """A staged gitlink naming a signed commit, which a ``%G?`` format checks."""
    _stage_gitlink(repo, _LINKED, _signed_copy_of_head(repo, "openpgp"))
    _config(repo, "format.pretty", "format:%H %G?")
    _config(repo, "gpg.program", programs("signature"))


def _gitlink_submodule_diff(repo: Path, programs: _Programs, outside: Path) -> None:
    """A staged gitlink naming a commit whose diff moves a populated submodule.

    With ``diff.submodule=diff``, showing that commit starts a second git
    inside the submodule, where the submodule's own ``diff.external`` applies.
    """
    sub = repo / "sub"
    sub.mkdir()
    _git(sub, "-c", "init.defaultBranch=main", "init", "-q")
    (sub / "a.txt").write_bytes(b"one\n")
    _git(sub, "add", "-A")
    _git(sub, *_IDENT, "commit", "-q", "-m", "one")
    first = _git(sub, "rev-parse", "HEAD")
    (sub / "a.txt").write_bytes(b"two\n")
    _git(sub, *_IDENT, "commit", "-q", "-am", "two")
    second = _git(sub, "rev-parse", "HEAD")
    _config(sub, "diff.external", programs("diff"))
    entries = _git(repo, "ls-tree", "HEAD")

    def commit_with_sub_at(oid: str, parent: str) -> str:
        listing = f"{entries}\n160000 commit {oid}\tsub\n".encode()
        tree = _git(repo, "mktree", data=listing)
        return _git(repo, *_IDENT, "commit-tree", tree, "-p", parent, "-m", "sub")

    before = commit_with_sub_at(first, _git(repo, "rev-parse", "HEAD"))
    _stage_gitlink(repo, _LINKED, commit_with_sub_at(second, before))
    _config(repo, "diff.submodule", "diff")


_SHOW_HEAD = ("show", f"HEAD:{_TRACKED}")
_SHOW_LINKED = ("show", f":{_LINKED}")
_COMMIT = (*_IDENT, "commit", "-q", "--allow-empty", "-m", "test: run the hooks")

SCENARIOS = (
    _Scenario("fsmonitor", _fsmonitor, ("ls-files",)),
    _Scenario("fsmonitor-include", _fsmonitor_included, ("ls-files",)),
    _Scenario("fsmonitor-config-worktree", _fsmonitor_worktree, ("ls-files",)),
    _Scenario("signature-openpgp", _signature("openpgp", "gpg.program"), ("log", "-1")),
    _Scenario("signature-ssh", _signature("ssh", "gpg.ssh.program"), ("log", "-1")),
    _Scenario("signature-x509", _signature("x509", "gpg.x509.program"), ("log", "-1")),
    _Scenario("lazy-fetch-upload-pack", _lazy_fetch("upload-pack"), _SHOW_HEAD),
    _Scenario("lazy-fetch-ssh-command", _lazy_fetch("ssh-command"), _SHOW_HEAD),
    _Scenario("lazy-fetch-ext", _lazy_fetch("ext"), _SHOW_HEAD),
    _Scenario("hooks-folder", _hooks_folder, _COMMIT),
    _Scenario("hooks-path", _hooks_path, _COMMIT),
    _Scenario(
        "filter-clean", _setting("filter.planted.clean", "filter"), ("add", "-A")
    ),
    _Scenario(
        "filter-process", _setting("filter.planted.process", "filter"), ("add", "-A")
    ),
    _Scenario("diff-external", _setting("diff.external", "diff"), ("diff",)),
    _Scenario("diff-driver", _setting("diff.planted.command", "diff"), ("diff",)),
    _Scenario("diff-textconv", _setting("diff.planted.textconv", "diff"), ("diff",)),
    _Scenario("pagers", _pagers, None),
    _Scenario("gitlink-signature", _gitlink_signature, _SHOW_LINKED),
    _Scenario("gitlink-submodule-diff", _gitlink_submodule_diff, _SHOW_LINKED),
)


@pytest.fixture
def hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide the host's global and system git configuration from the gate too."""
    for name in list(os.environ):
        if name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")) or name in {
            "GIT_CONFIG",
            "GIT_CONFIG_PARAMETERS",
            "GIT_CONFIG_COUNT",
        }:
            monkeypatch.delenv(name)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _planted_repo(tmp_path: Path, scenario: _Scenario) -> tuple[Path, _Programs]:
    """Build a repository with *scenario* planted, proven live by its control."""
    programs = _Programs(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = _build_repo(tmp_path / "project")
    scenario.plant(repo, programs, outside)
    if scenario.control is not None:
        stderr = _plain(repo, *scenario.control)
        assert programs.ran(), (
            f"`git {' '.join(scenario.control)}` ran nothing: {stderr}"
        )
        programs.clear()
    return repo, programs


def _drive_every_gate_git_call(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run each git-reading path of the gate and its validators against *repo*.

    A path whose git fails or runs past its limit raises ``GitCheckError``,
    its report of an unread history or change set; that is an outcome here,
    not an error: what counts is that no planted program ran.
    """
    gate._run_all_perwrite(repo)
    with contextlib.suppress(RuntimeError):
        no_global_plans_grep._git_ls_files(repo)
    conventional_commit_grep._read_head_subject(repo)
    with contextlib.suppress(GitCheckError):
        agents_md_coverage_grep._last_commit_times(repo)
    # The two change-set checks read the repository the process runs in.
    monkeypatch.chdir(repo)
    with contextlib.suppress(GitCheckError):
        production_ready_pr_grep._staged_paths()
    monkeypatch.setattr(semver_stability_grep, "current_version", lambda: "1.2.3")
    with contextlib.suppress(GitCheckError):
        semver_stability_grep.check_staged()


@pytest.mark.usefixtures("hermetic_git")
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.name)
def test_no_planted_program_runs(
    scenario: _Scenario, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, programs = _planted_repo(tmp_path, scenario)

    _drive_every_gate_git_call(repo, monkeypatch)

    assert programs.ran() == []


@pytest.mark.usefixtures("hermetic_git")
@pytest.mark.parametrize(
    "scenario",
    [scenario for scenario in SCENARIOS if scenario.name.startswith("lazy-fetch")],
    ids=lambda scenario: scenario.name,
)
def test_no_transport_without_the_lazy_fetch_switch(
    scenario: _Scenario, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """git before 2.44 ignores GIT_NO_LAZY_FETCH; the empty transport list holds."""
    repo, programs = _planted_repo(tmp_path, scenario)
    monkeypatch.delitem(git_helper.GIT_ENVIRONMENT, "GIT_NO_LAZY_FETCH")

    _drive_every_gate_git_call(repo, monkeypatch)

    assert programs.ran() == []


@pytest.mark.usefixtures("hermetic_git")
def test_gate_all_and_all_perwrite_run_no_planted_program(tmp_path: Path) -> None:
    """End to end: the gate started from inside a project that plants everything."""
    programs = _Programs(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = _build_repo(tmp_path / "project")
    for scenario in SCENARIOS:
        if scenario.name in {
            "fsmonitor",
            "signature-openpgp",
            "hooks-path",
            "filter-clean",
            "diff-external",
            "pagers",
        }:
            scenario.plant(repo, programs, outside)
    _lazy_fetch("upload-pack")(repo, programs, outside)
    for control in (("ls-files",), ("log", "-1"), _SHOW_HEAD):
        _plain(repo, *control)
    assert {"fsmonitor", "signature", "transport"} <= set(programs.ran())
    programs.clear()

    env = hermetic_git_env()
    gate_script = str(Path(gate.__file__).resolve())
    for mode in ("--all", "--all-perwrite"):
        completed = subprocess.run(
            [sys.executable, gate_script, mode, str(repo)],
            cwd=str(repo),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
        payload = json.loads(completed.stdout)
        if mode == "--all":
            assert payload["validator_count"] == len(gate.STANDALONE_MODULES)
        else:
            # The tracked-file list still comes back: git ran, safely.
            assert payload["files_scanned"] > 0, payload
        assert programs.ran() == [], (mode, completed.stderr[-2000:])


def test_git_never_comes_from_the_current_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A git placed in the checked project never runs in place of the real one."""
    real_git = git_helper.find_git()
    if real_git is None:
        pytest.skip("no git in a full-path PATH entry")
    project = tmp_path / "project"
    project.mkdir()
    marker = tmp_path / "planted-git.ran"
    if os.name == "nt":
        # Windows looks in the current folder for a bare program name unless
        # this variable is set; any program that is not git will do.
        system_root = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
        shutil.copyfile(system_root / "System32" / "whoami.exe", project / "git.exe")
        monkeypatch.delenv("NoDefaultCurrentDirectoryInExePath", raising=False)
    else:
        planted = project / "git"
        planted.write_bytes(f"#!/bin/sh\necho ran > '{marker}'\n".encode())
        planted.chmod(0o755)
    # An empty PATH entry names the current folder on every platform.
    monkeypatch.setenv("PATH", os.pathsep + str(Path(real_git).parent))
    monkeypatch.chdir(project)

    control = subprocess.run(
        ["git", "version"], capture_output=True, text=True, check=False, timeout=60
    )
    assert marker.exists() or not control.stdout.startswith("git version ")

    marker.unlink(missing_ok=True)
    completed = git_helper.run_git(["version"], cwd=project, timeout=60)

    assert completed.stdout.startswith("git version ")
    assert not marker.exists()


def test_full_path_entries_keep_only_full_paths() -> None:
    posix = ":.:bin:/usr/bin:~/bin:/opt/git/bin"
    assert git_helper.full_path_entries(posix, windows=False) == [
        "/usr/bin",
        "/opt/git/bin",
    ]
    windows = ";".join(
        [
            r"C:\Git\cmd",
            r'"C:\Program Files\Git\cmd"',
            r"\bin",
            "C:bin",
            r"\\server\share\bin",
            ".",
            "",
            "D:/tools",
        ]
    )
    assert git_helper.full_path_entries(windows, windows=True) == [
        r"C:\Git\cmd",
        r"C:\Program Files\Git\cmd",
        r"\\server\share\bin",
        "D:/tools",
    ]


def test_git_argv_puts_the_protective_options_first() -> None:
    argv = git_helper.git_argv("/usr/bin/git", ["log", "-1", "--pretty=%B"])
    options = len(git_helper.PROTECTIVE_OPTIONS)
    assert argv[0] == "/usr/bin/git"
    assert tuple(argv[1 : 1 + options]) == git_helper.PROTECTIVE_OPTIONS
    assert argv[1 + options :] == [
        "log",
        "--no-ext-diff",
        "--no-textconv",
        "-O/dev/null",
        "-1",
        "--pretty=%B",
    ]

    argv = git_helper.git_argv("/usr/bin/git", ["ls-files", "-z"])
    assert argv[1 + options :] == ["ls-files", "-z"]

    # A folder reaches git as -C, so git reports a missing one itself.
    argv = git_helper.git_argv("/usr/bin/git", ["ls-files"], cwd="/project")
    assert argv[1 + options :] == ["-C", "/project", "ls-files"]

    with pytest.raises(ValueError, match="subcommand"):
        git_helper.git_argv("/usr/bin/git", [])


def test_protective_options_name_every_program_switch() -> None:
    settings = dict(
        option.split("=", 1)
        for flag, option in zip(
            git_helper.PROTECTIVE_OPTIONS,
            git_helper.PROTECTIVE_OPTIONS[1:],
            strict=False,
        )
        if flag == "-c"
    )
    assert settings["core.fsmonitor"] == ""
    assert settings["core.useBuiltinFSMonitor"] == "false"
    assert settings["log.showSignature"] == "false"
    assert settings["diff.submodule"] == "short"
    assert settings["log.mailmap"] == "false"
    assert settings["gc.auto"] == "0"
    assert settings["maintenance.auto"] == "false"
    assert settings["core.quotePath"] == "false"
    # The hooks path, the signature programs and the excludes file sit below a
    # regular file, where nothing can exist, so none of them can start or be read.
    for key in (
        "core.hooksPath",
        "gpg.program",
        "gpg.ssh.program",
        "gpg.x509.program",
        "core.excludesFile",
    ):
        assert Path(settings[key]).parent.is_file(), key
    assert git_helper.PROTECTIVE_OPTIONS[0] == "--no-pager"


def test_git_environment_blocks_fetches_and_narrows_path() -> None:
    separator = os.pathsep
    full = r"C:\Git\cmd" if os.name == "nt" else "/usr/bin"
    env = git_helper.git_environment(
        {"PATH": f"{separator}.{separator}{full}", "HOME": "h"}
    )
    assert env["GIT_ALLOW_PROTOCOL"] == ""
    assert env["GIT_NO_LAZY_FETCH"] == "1"
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["PATH"] == full
    assert env["HOME"] == "h"

    assert "PATH" not in git_helper.git_environment({"PATH": f".{separator}bin"})


def test_run_git_reports_a_missing_git_as_file_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "")
    with pytest.raises(FileNotFoundError, match=re.escape("full-path PATH entry")):
        git_helper.run_git(["version"])


_PROCESS_FUNCTIONS = frozenset(
    {
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.getoutput",
        "subprocess.getstatusoutput",
        "os.system",
        "os.popen",
        "os.startfile",
        "asyncio.create_subprocess_exec",
        "asyncio.create_subprocess_shell",
        "asyncio.subprocess.create_subprocess_exec",
        "asyncio.subprocess.create_subprocess_shell",
        "pty.spawn",
    }
)
_PROCESS_PREFIXES = ("os.exec", "os.spawn", "os.posix_spawn")
_PROCESS_MODULES = ("subprocess", "os", "shutil", "asyncio", "pty")
# A string that names the git program: "git", "git.exe", or a path ending so.
_GIT_PROGRAM = re.compile(r"(?:^|[\\/])git(?:\.exe)?$", re.IGNORECASE)


def _dotted(node: ast.expr, imported: dict[str, str]) -> str:
    """Return a call target as a dotted name, through ``from ... import``."""
    if isinstance(node, ast.Name):
        return imported.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value, imported)}.{node.attr}"
    return ""


def _program_starts(
    source: str, *, allowed: frozenset[str] = frozenset(), starts: bool = True
) -> list[int]:
    """Return the lines where *source* starts or finds a program, or names git.

    Every process-starting call counts, whatever its arguments, and so does any
    ``which``, any use of ``git_argv``, and any string naming the git program.
    Calls inside a function named in *allowed* are skipped. With *starts*
    false, process-starting calls do not count; the rest still does.
    """
    tree = ast.parse(source)
    imported: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                imported[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    skipped: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in allowed:
            skipped.update(id(inner) for inner in ast.walk(node))
    lines: list[int] = []
    for node in ast.walk(tree):
        if id(node) in skipped:
            continue
        if isinstance(node, ast.Call):
            target = _dotted(node.func, imported)
            starts_one = target in _PROCESS_FUNCTIONS or target.startswith(
                _PROCESS_PREFIXES
            )
            if (
                (starts and starts_one)
                or target == "which"
                or target.endswith(".which")
            ):
                lines.append(node.lineno)
            continue
        uses_git_argv = (isinstance(node, ast.Name) and node.id == "git_argv") or (
            isinstance(node, ast.Attribute) and node.attr == "git_argv"
        )
        names_git = (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _GIT_PROGRAM.search(node.value.strip()) is not None
        )
        if uses_git_argv or names_git:
            lines.append(node.lineno)
    return sorted(set(lines))


# Source text for the guard's self-test: parsed with ast.parse, never run.
_BYPASSES = {
    "literal list": 'import subprocess\nsubprocess.run(["git", "log"])\n',
    "shell string": 'import subprocess\nsubprocess.run("git log", shell=True)\n',
    "name for git": 'import subprocess\nGIT = "git"\nsubprocess.run([GIT, "show"])\n',
    "full path": 'import subprocess\nsubprocess.run(["/usr/bin/git", "log"])\n',
    "split string": 'import subprocess\nsubprocess.run("git log".split())\n',
    "os.system": 'import os\nos.system("git status")\n',
    "os.popen": 'import os\nos.popen("git status")\n',
    "os.exec": 'import os\nos.execvp("git", ["git"])\n',
    "bare which": 'from shutil import which\nwhich("git")\n',
    "keyword which": 'import shutil\nshutil.which(cmd="git")\n',
    "renamed import": (
        'from subprocess import check_output as co\nco(["git", "log"])\n'
    ),
    "git_argv": (
        "import subprocess\n"
        "from apothem.conformity._git import git_argv\n"
        'subprocess.run(git_argv("g", ["log"]))\n'
    ),
    "getattr": 'import subprocess\ngetattr(subprocess, "run")(["git"])\n',
    "asyncio": 'import asyncio\nasyncio.create_subprocess_exec("git", "log")\n',
}


@pytest.mark.parametrize("source", _BYPASSES.values(), ids=list(_BYPASSES))
def test_the_program_guard_catches_each_direct_form(source: str) -> None:
    assert _program_starts(source) != []


def test_the_program_guard_passes_run_git_and_exception_types() -> None:
    source = (
        "import subprocess\n"
        "from apothem.conformity._git import run_git\n"
        'GIT_ENTRY = ".git"\n'
        "try:\n"
        '    run_git(["log", "-1"], timeout=5)\n'
        "except (subprocess.TimeoutExpired, subprocess.CalledProcessError):\n"
        "    pass\n"
    )
    assert _program_starts(source) == []


def test_no_conformity_module_starts_a_program_itself() -> None:
    """Only ``_git.py`` names git; every other module calls ``run_git``.

    ``_bounded_run.py`` is the one module that starts a program:
    ``run_git`` starts git through ``run_bounded``, and gate.py's validator
    launcher (``_run_standalone``) starts Python through it, so neither git
    nor any other program starts anywhere else. The rest of the guard still
    holds in ``_bounded_run.py``: it names no git and finds no program.
    """
    package = Path(gate.__file__).resolve().parent
    offenders: list[str] = []
    for module in sorted(package.rglob("*.py")):
        relative = module.relative_to(package).as_posix()
        if relative == "_git.py":
            continue
        source = module.read_text(encoding="utf-8")
        lines = _program_starts(source, starts=relative != "_bounded_run.py")
        offenders.extend(f"{relative}:{line}" for line in lines)
    assert offenders == []


def test_the_guard_still_finds_git_named_where_programs_may_start() -> None:
    """With program starts allowed, a string naming git is still caught."""
    source = 'import subprocess\nsubprocess.Popen(["git", "log"])\n'
    assert _program_starts(source, starts=False) == [2]
    assert (
        _program_starts("import subprocess\nsubprocess.Popen(argv)\n", starts=False)
        == []
    )
    assert _program_starts('import shutil\nshutil.which("x")\n', starts=False) == [2]


def test_only_the_shared_runner_and_git_helper_start_programs() -> None:
    """``_bounded_run.py`` starts programs and ``_git.py`` only names git."""
    package = Path(gate.__file__).resolve().parent
    runner = (package / "_bounded_run.py").read_text(encoding="utf-8")
    helper = (package / "_git.py").read_text(encoding="utf-8")
    assert _program_starts(runner) != []
    assert "subprocess.run(" not in helper
    assert "_bounded_run.run_bounded(" in helper


def _dated_commit(repo: Path, message: str, when: int) -> None:
    """Commit everything in *repo* with author and committer time *when*."""
    stamp = f"@{when} +0000"
    _git(repo, "add", "-A")
    _git(
        repo,
        *_IDENT,
        "commit",
        "-q",
        "-m",
        message,
        env={"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp},
    )


def _empty_repo(repo: Path) -> Path:
    repo.mkdir()
    _git(repo, "-c", "init.defaultBranch=main", "init", "-q")
    return repo


@pytest.mark.usefixtures("hermetic_git")
def test_a_stale_folder_companion_is_reported(tmp_path: Path) -> None:
    """The freshness check reads git log's ``\\x1e`` record markers.

    ``str.splitlines()`` treats ``\\x1e`` as a line break, which emptied every
    commit-time map, so no stale companion was ever reported.
    """
    repo = _empty_repo(tmp_path / "project")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "README.md").write_bytes(b"# pkg\n")
    (repo / "pkg" / "AGENTS.md").write_bytes(b"# pkg notes\n")
    _dated_commit(repo, "docs: add pkg", 1_700_000_000)
    (repo / "pkg" / "x.py").write_bytes(b"X = 1\n")
    _dated_commit(repo, "feat: add pkg code", 1_700_001_000)

    assert agents_md_coverage_grep._last_commit_times(repo) == {
        "pkg/AGENTS.md": 1_700_000_000,
        "pkg/README.md": 1_700_000_000,
        "pkg/x.py": 1_700_001_000,
    }
    result = agents_md_coverage_grep.check(repo)
    assert [(finding.surface, finding.kind) for finding in result.findings] == [
        ("pkg/AGENTS.md", "stale-companion")
    ]


@pytest.mark.usefixtures("hermetic_git")
def test_the_root_agents_md_is_never_a_stale_companion(tmp_path: Path) -> None:
    """The root ``AGENTS.md`` is the canon, checked against no folder's content."""
    repo = _empty_repo(tmp_path / "project")
    (repo / "README.md").write_bytes(b"# project\n")
    (repo / "AGENTS.md").write_bytes(b"# agents\n")
    _dated_commit(repo, "docs: add the canon", 1_700_000_000)
    (repo / "notes.md").write_bytes(b"later\n")
    _dated_commit(repo, "docs: add notes", 1_700_001_000)

    result = agents_md_coverage_grep.check(repo)

    assert result.freshness_checked
    assert result.findings == []


@pytest.mark.usefixtures("hermetic_git")
def test_a_deleted_folder_companion_is_not_reported(tmp_path: Path) -> None:
    """A per-folder ``AGENTS.md`` deleted since is absent, and absence passes."""
    repo = _empty_repo(tmp_path / "project")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "README.md").write_bytes(b"# pkg\n")
    (repo / "pkg" / "AGENTS.md").write_bytes(b"# pkg notes\n")
    _dated_commit(repo, "docs: add pkg", 1_700_000_000)
    (repo / "pkg" / "AGENTS.md").unlink()
    _dated_commit(repo, "docs: drop the pkg notes", 1_700_000_500)
    (repo / "pkg" / "x.py").write_bytes(b"X = 1\n")
    _dated_commit(repo, "feat: add pkg code", 1_700_001_000)

    result = agents_md_coverage_grep.check(repo)

    assert result.freshness_checked
    assert result.findings == []


@pytest.mark.usefixtures("hermetic_git")
def test_a_subfolder_root_checks_its_own_folders(tmp_path: Path) -> None:
    """Paths come relative to the checked root, so a subfolder root matches."""
    repo = _empty_repo(tmp_path / "project")
    pkg = repo / "proj" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "README.md").write_bytes(b"# pkg\n")
    (pkg / "AGENTS.md").write_bytes(b"# pkg notes\n")
    _dated_commit(repo, "docs: add pkg", 1_700_000_000)
    (pkg / "x.py").write_bytes(b"X = 1\n")
    _dated_commit(repo, "feat: add pkg code", 1_700_001_000)

    result = agents_md_coverage_grep.check(repo / "proj")

    assert [(finding.surface, finding.kind) for finding in result.findings] == [
        ("pkg/AGENTS.md", "stale-companion")
    ]


@pytest.mark.usefixtures("hermetic_git")
def test_names_with_line_separators_stay_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A name holding U+2028, U+2029 or U+0085 reaches the validators whole.

    git prints such a name unquoted, and ``str.splitlines()`` would break it.
    """
    odd = f"a{chr(0x2028)}b{chr(0x2029)}c{chr(0x85)}d.md"
    repo = _empty_repo(tmp_path / "project")
    (repo / "docs").mkdir()
    (repo / "docs" / odd).write_bytes(b"x\n")
    _dated_commit(repo, "docs: add an oddly named page", 1_700_000_000)
    staged = f"src/apothem/m{chr(0x2028)}x.py"
    (repo / "src" / "apothem").mkdir(parents=True)
    (repo / staged).write_bytes(b"X = 1\n")
    _git(repo, "add", "-A")
    monkeypatch.chdir(repo)

    assert no_global_plans_grep._git_ls_files(repo) == [f"docs/{odd}", staged]
    assert production_ready_pr_grep._staged_paths() == [staged]


@pytest.mark.usefixtures("hermetic_git")
def test_a_missing_diff_order_file_hides_no_staged_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``diff.orderFile`` the repository names is never read.

    A missing one made ``git diff`` fail, and both ``--staged`` checks then saw
    an empty change set and passed; a network one makes Windows connect to it.
    """
    repo = _build_repo(tmp_path / "project")
    _config(repo, "diff.orderFile", (tmp_path / "no-such-order-file").as_posix())
    plain = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(repo),
        env=hermetic_git_env(),
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert plain.returncode != 0  # plain git cannot list the staged change
    monkeypatch.chdir(repo)

    assert production_ready_pr_grep._staged_paths() == [_TRACKED]
    assert semver_stability_grep.check_staged() != []  # g was dropped


@pytest.mark.usefixtures("hermetic_git")
def test_non_ascii_paths_read_as_themselves(tmp_path: Path) -> None:
    """git's C-quoting of non-ASCII path names is off for every gate git call."""
    repo = _empty_repo(tmp_path / "project")
    (repo / "docs").mkdir()
    (repo / "docs" / "café.md").write_bytes(b"# cafe\n")
    _dated_commit(repo, "docs: add the cafe page", 1_700_000_000)

    assert no_global_plans_grep._git_ls_files(repo) == ["docs/café.md"]
    assert agents_md_coverage_grep._last_commit_times(repo) == {
        "docs/café.md": 1_700_000_000
    }


def test_ls_files_reports_a_missing_root_as_a_git_failure(tmp_path: Path) -> None:
    """A root that is gone, or is a file, is git's own error, not a lost git."""
    with pytest.raises(RuntimeError, match="git ls-files failed under"):
        no_global_plans_grep._git_ls_files(tmp_path / "missing")
    a_file = tmp_path / "a-file"
    a_file.write_bytes(b"x\n")
    with pytest.raises(RuntimeError, match="git ls-files failed under"):
        no_global_plans_grep._git_ls_files(a_file)


@pytest.mark.usefixtures("hermetic_git")
def test_a_staged_major_bump_admits_a_breaking_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The version check reads ``src/apothem/__init__.py`` on every platform.

    git names a path with forward slashes; a Windows path spelled with
    backslashes made the check fail, so a staged MAJOR bump never counted.
    """
    repo = _build_repo(tmp_path / "project")
    monkeypatch.chdir(repo)
    assert semver_stability_grep.check_staged() != []  # g was dropped

    (repo / _VERSIONED).write_bytes(b'__version__ = "2.0.0"\n')
    _git(repo, "add", _VERSIONED)

    assert semver_stability_grep.check_staged() == []
