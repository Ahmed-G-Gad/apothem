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

from apothem.conformity import (
    _bounded_run,
    _grep_base,
    agents_md_coverage_grep,
    conventional_commit_grep,
    gate,
    no_global_plans_grep,
    production_ready_pr_grep,
    semver_stability_grep,
)
from apothem.conformity import _git as git_helper
from apothem.conformity._grep_base import GitCheckError, GitNameError, in_checkout
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
        agents_md_coverage_grep._read_history(repo)
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


# The guard below is a tripwire, not a proof. It reads source text and flags the
# ways of starting a program that it knows, so the usual slips (a plain
# ``subprocess.run(["git", ...])``, an ``import subprocess as sp``) fail a test.
# Code that hides the call behind a computed name can still pass it; the
# scenario tests above, which run git for real, are what holds then.

# The only names a module may take from ``subprocess``: the exception types a
# caller of ``run_git`` handles and the result type it annotates.
_SUBPROCESS_ALLOWED = frozenset(
    {"CalledProcessError", "CompletedProcess", "SubprocessError", "TimeoutExpired"}
)
# ``os`` functions that start a program or a process.
_OS_FUNCTIONS = frozenset({"fork", "forkpty", "popen", "startfile", "system"})
_OS_PREFIXES = ("exec", "spawn", "posix_spawn")
# Modules a conformity module has no use for other than starting a program or
# a process: importing one is flagged.
_PROGRAM_MODULES = frozenset(
    {
        "_ctypes",
        "_posixsubprocess",
        "_winapi",
        "antigravity",
        "ctypes",
        "ensurepip",
        "multiprocessing",
        "pty",
        "pydoc",
        "tkinter",
        "venv",
        "webbrowser",
    }
)
# Modules a dynamic import, a ``sys.modules`` lookup, ``vars`` or a computed
# ``getattr`` may not name.
_PROCESS_MODULES = _PROGRAM_MODULES | {"asyncio", "os", "posix", "nt", "subprocess"}
# Names that start or find a program on whatever object carries them.
# ``run_bounded`` starts any program it is given, so only its two callers may
# name it: ``run_git`` (in ``_git.py``) and the gate's validator launcher.
_PROGRAM_NAMES = frozenset(
    {
        "CreateProcess",
        "ProcessPoolExecutor",
        "create_subprocess_exec",
        "create_subprocess_shell",
        "find_git",
        "git_argv",
        "import_module",
        "run_bounded",
        "subprocess_exec",
        "subprocess_shell",
        "which",
    }
)
# Standard-library functions that start a program as a side effect.
_PROGRAM_FUNCTIONS = frozenset(
    {
        "pkgutil.resolve_name",
        "platform.architecture",
        "platform.processor",
        "platform.uname",
    }
)
# Built-in calls that run source text or import by name, and the modules that
# carry the same calls as attributes.
_DYNAMIC_CALLS = frozenset({"__import__", "compile", "eval", "exec"})
_DYNAMIC_HOSTS = frozenset({"__builtins__", "builtins", "importlib"})
# A dotted name that starts at an imported name is judged from its last
# segment that names one of these, so ``other_module.subprocess.run`` reads
# as ``subprocess.run``. A chain that starts at a local name is left as it
# is: a field called ``subprocess`` on some object starts nothing.
_JUDGED_FROM = frozenset({"os", "subprocess"})
# The package's own modules: reaching into one by a computed name, ``vars`` or
# ``__dict__`` can fetch ``run_bounded`` or the ``subprocess`` it imports.
_OWN_PACKAGE = "apothem.conformity"
# A string that names the git program: "git", "git.exe", or a path ending so.
_GIT_PROGRAM = re.compile(r"(?:^|[\\/])git(?:\.exe)?$", re.IGNORECASE)


def _root(module: str) -> str:
    """Return the top-level package of a dotted module name."""
    return module.partition(".")[0]


def _is_os_program_function(name: str) -> bool:
    return name in _OS_FUNCTIONS or name.startswith(_OS_PREFIXES)


def _canonical(dotted: str) -> str:
    """Return *dotted* cut to start at its last ``os`` or ``subprocess`` segment."""
    parts = dotted.split(".")
    for index in range(len(parts) - 1, 0, -1):
        if parts[index] in _JUDGED_FROM:
            return ".".join(parts[index:])
    return dotted


def _flagged_name(dotted: str, names: frozenset[str] = _PROGRAM_NAMES) -> bool:
    """Return True when a dotted name, as resolved, starts or finds a program.

    *names* is :data:`_PROGRAM_NAMES`, or that set without ``run_bounded``
    for the one call that may name it.
    """
    if dotted in _PROGRAM_FUNCTIONS:
        return True
    module, _, rest = dotted.partition(".")
    first = rest.partition(".")[0]
    last = dotted.rpartition(".")[2]
    if module == "subprocess":
        return first not in _SUBPROCESS_ALLOWED
    if module in {"os", "posix", "nt"} and (
        _is_os_program_function(first) or first == "__dict__"
    ):
        return True
    if module in _DYNAMIC_HOSTS and last in _DYNAMIC_CALLS:
        return True
    return last in names


def _program_starts(
    source: str, *, run_bounded_in: frozenset[str] = frozenset()
) -> list[int]:
    """Return the lines where *source* starts or finds a program, or names git.

    Flagged, as a reference and not only as a call: any use of ``subprocess``
    beyond its exception and result types (through ``import ... as`` and
    ``from ... import ... as`` names too, through another module that carries
    it, and the module passed around as a value); the ``os`` functions that
    start a program; any ``which``, ``find_git``, ``git_argv`` or
    ``run_bounded``; the asyncio and event-loop program starters; an import of
    a module that exists to start programs (``ctypes``, ``multiprocessing``,
    ``pty``, ...); a star import from a process module; a dynamic import,
    ``exec`` or ``eval``, also as ``builtins.`` or ``importlib.`` attributes; a
    ``getattr`` with a computed name, ``vars`` or ``__dict__`` on a process
    module or on one of the package's own modules; a ``getattr`` that names a
    starter on any object; a ``sys.modules`` lookup of a process module; and
    any string naming the git program. ``run_bounded`` is not flagged where a
    module-level function named in *run_bounded_in* calls it directly; any
    other use of the name there (a value, a nested function) is.
    """
    tree = ast.parse(source)
    # A module with a function that may call run_bounded may import the name;
    # every use of it outside that function is still flagged.
    importable = _PROGRAM_NAMES - {"run_bounded"} if run_bounded_in else _PROGRAM_NAMES
    bound, lines = _import_bindings(tree, importable)

    def chain(node: ast.expr) -> tuple[str, bool]:
        """Return a dotted name and whether it starts at an imported name."""
        if isinstance(node, ast.Name):
            return bound.get(node.id, node.id), node.id in bound
        if isinstance(node, ast.Attribute):
            inner, imported = chain(node.value)
            return (f"{inner}.{node.attr}" if inner else ""), imported
        return "", False

    def resolve(node: ast.expr) -> str:
        dotted, imported = chain(node)
        return _canonical(dotted) if imported else dotted

    # A module name that is only the left side of ``module.attribute`` is
    # judged with that attribute; anywhere else the module itself is a value.
    attribute_bases = {
        id(node.value) for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    may_run_bounded = _direct_call_targets(tree, run_bounded_in)
    for node in ast.walk(tree):
        names = (
            _PROGRAM_NAMES - {"run_bounded"}
            if id(node) in may_run_bounded
            else _PROGRAM_NAMES
        )
        if isinstance(node, ast.Attribute):
            flagged = (
                _flagged_name(resolve(node), names)
                or node.attr in names
                or (
                    node.attr == "__dict__"
                    and chain(node.value)[0].startswith(_OWN_PACKAGE)
                )
            )
        elif isinstance(node, ast.Name):
            dotted = resolve(node)
            flagged = (
                (dotted == "subprocess" and id(node) not in attribute_bases)
                or ("." in dotted and _flagged_name(dotted, names))
                or node.id in names
                or node.id in _DYNAMIC_CALLS
            )
        elif isinstance(node, ast.Call):
            flagged = _flagged_call(node, resolve, chain)
        elif isinstance(node, ast.Subscript) and resolve(node.value) == "sys.modules":
            flagged = _names_process_module(node.slice)
        else:
            text = _fixed_string(node)
            flagged = text is not None and bool(_GIT_PROGRAM.search(text.strip()))
        if flagged:
            lines.append(node.lineno)  # type: ignore[attr-defined]
    return sorted(set(lines))


def _names_process_module(node: ast.AST) -> bool:
    """Return True for a string literal that names a process module."""
    key = _fixed_string(node)
    return key is not None and _root(key) in _PROCESS_MODULES


def _direct_call_targets(tree: ast.Module, functions: frozenset[str]) -> set[int]:
    """Return the ids of what the named module-level functions call directly.

    Only the called expression of a call in the function's own body counts:
    not a use of the name as a value, and nothing inside a nested function or
    a lambda, which could carry the name out of the function.
    """
    found: set[int] = set()
    for function in tree.body:
        if not isinstance(function, ast.FunctionDef) or function.name not in functions:
            continue
        pending: list[ast.AST] = list(function.body)
        while pending:
            node = pending.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(node, ast.Call):
                found.add(id(node.func))
            pending.extend(ast.iter_child_nodes(node))
    return found


def _run_bounded_uses(source: str, *, inside: frozenset[str]) -> list[int]:
    """Return the lines that name ``run_bounded`` other than as a direct call
    in a module-level function named in *inside*.

    The one rule checked in ``_git.py``, which names git and so cannot go
    through :func:`_program_starts`.
    """
    tree = ast.parse(source)
    allowed = _direct_call_targets(tree, inside)
    return sorted(
        {
            node.lineno
            for node in ast.walk(tree)
            if id(node) not in allowed
            and (
                (isinstance(node, ast.Name) and node.id == "run_bounded")
                or (isinstance(node, ast.Attribute) and node.attr == "run_bounded")
                or (
                    isinstance(node, ast.ImportFrom)
                    and any(alias.name == "run_bounded" for alias in node.names)
                )
            )
        }
    )


def _flagged_call(
    node: ast.Call,
    resolve: Callable[[ast.expr], str],
    chain: Callable[[ast.expr], tuple[str, bool]],
) -> bool:
    """Return True for a call that reaches a starter or a process module by name.

    ``getattr(x, "<starter or process module>")`` on any object;
    ``getattr(module, <computed name>)`` and ``vars(module)`` on a process
    module or one of the package's own modules; and a ``sys.modules`` method
    given a process module's name. The called name itself is judged where the
    walk meets it as a name or an attribute.
    """
    called = resolve(node.func)
    if called.startswith("sys.modules."):
        return bool(node.args) and _names_process_module(node.args[0])
    if called not in {"getattr", "vars"}:
        return False
    name = _fixed_string(node.args[1]) if len(node.args) > 1 else None
    if name is not None and (name in _PROGRAM_NAMES or name in _JUDGED_FROM):
        return True
    target = resolve(node.args[0]) if node.args else ""
    own = bool(node.args) and chain(node.args[0])[0].startswith(_OWN_PACKAGE)
    if _root(target) not in _PROCESS_MODULES and not own:
        return False
    return name is None or _flagged_name(f"{target}.{name}")


def _fixed_string(node: ast.AST) -> str | None:
    """Return the text of a string literal, or None for any other node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _import_bindings(
    tree: ast.AST, names: frozenset[str] = _PROGRAM_NAMES
) -> tuple[dict[str, str], list[int]]:
    """Return what each imported name stands for, and the flagged import lines.

    The map goes from a local name to its dotted name: ``sp`` to
    ``subprocess`` after ``import subprocess as sp``, ``co`` to
    ``subprocess.check_output`` after ``from subprocess import check_output
    as co``. An import line is flagged when it brings in a module that exists
    to start programs, a name that starts one (judged against *names*), or
    everything from a process module.
    """
    bound: dict[str, str] = {}
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _root(alias.name) in _PROGRAM_MODULES:
                    lines.append(node.lineno)
                if alias.asname is not None:
                    bound[alias.asname] = alias.name
                else:
                    bound[_root(alias.name)] = _root(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            if _root(node.module) in _PROGRAM_MODULES:
                lines.append(node.lineno)
            for alias in node.names:
                if alias.name == "*":
                    if _root(node.module) in _PROCESS_MODULES:
                        lines.append(node.lineno)
                    continue
                dotted = f"{node.module}.{alias.name}"
                bound[alias.asname or alias.name] = dotted
                if _flagged_name(_canonical(dotted), names):
                    lines.append(node.lineno)
    return bound, lines


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
    # The forms below start a program without one string that names git.
    "module alias with find_git": (
        "import subprocess as sp\n"
        "from apothem.conformity._git import find_git\n"
        'sp.run([find_git(), "log", "--show-signature"])\n'
    ),
    "module alias, joined name": (
        'import subprocess as sp\nsp.run(["g" + "it", "log"])\n'
    ),
    "find_git alone": (
        "from apothem.conformity import _git\nprogram = _git.find_git()\n"
    ),
    "function alias": (
        'import subprocess\nRUN = subprocess.run\nRUN(["g" + "it", "log"])\n'
    ),
    "function as a value": (
        "import functools\nimport subprocess\n"
        'start = functools.partial(subprocess.run, ["g" + "it"])\n'
    ),
    "module as a value": (
        'import subprocess\nrunner = subprocess\nrunner.run(["g" + "it"])\n'
    ),
    "exec through a variable": (
        'import os\nstart = os.execvp\nstart("g" + "it", ["g" + "it"])\n'
    ),
    "os.fork": "import os\nos.fork()\n",
    "from os import a starter": (
        'from os import spawnlp as go\ngo(0, "g" + "it", "g" + "it")\n'
    ),
    "star import": 'from os import *\nsystem("g" + "it" + " log")\n',
    "import_module": (
        'import importlib\nimportlib.import_module("sub" + "process").run(["x"])\n'
    ),
    "__import__": '__import__("sub" + "process").run(["x"])\n',
    "exec of a string": 'exec("import sub" + "process")\n',
    "eval of a string": 'eval("__imp" + "ort__")("os")\n',
    "sys.modules": 'import sys\nsys.modules["subprocess"].run(["x"])\n',
    "getattr, computed name": (
        'import os\ngetattr(os, "sys" + "tem")("g" + "it" + " log")\n'
    ),
    "getattr, aliased module": (
        'import subprocess as sp\ngetattr(sp, "r" + "un")(["x"])\n'
    ),
    "ctypes": "import ctypes\nctypes.windll.kernel32.CreateProcessW\n",
    "_winapi": "import _winapi\n_winapi.CreateProcess\n",
    "multiprocessing": (
        "import multiprocessing\nmultiprocessing.Process(target=print).start()\n"
    ),
    "process pool": (
        "from concurrent.futures import ProcessPoolExecutor\n"
        "ProcessPoolExecutor().submit(print)\n"
    ),
    "process pool, attribute": (
        "import concurrent.futures as cf\ncf.ProcessPoolExecutor().submit(print)\n"
    ),
    "event loop": (
        'import asyncio\nasyncio.new_event_loop().subprocess_exec(object, "g" + "it")\n'
    ),
    "asyncio alias": (
        "import asyncio.subprocess as aio\n"
        'aio.create_subprocess_shell("g" + "it" + " log")\n'
    ),
    "pty": 'import pty\npty.spawn(["g" + "it"])\n',
    "webbrowser": 'import webbrowser\nwebbrowser.open("file:///x")\n',
    # run_bounded starts whatever it is given, with none of run_git's options.
    "run_bounded, imported": (
        "import sys\n"
        "from apothem.conformity._bounded_run import run_bounded\n"
        'run_bounded([sys.executable, "-c", "x"], timeout=5)\n'
    ),
    "run_bounded, attribute": (
        "from apothem.conformity import _bounded_run\n"
        '_bounded_run.run_bounded(["sh", "-c", "x"], timeout=5)\n'
    ),
    "run_bounded as a value": (
        "from apothem.conformity import _bounded_run\n"
        "start = _bounded_run.run_bounded\n"
    ),
    # subprocess reached through a module that carries it.
    "subprocess, re-exported": (
        'from apothem.conformity._bounded_run import subprocess as s\ns.Popen(["x"])\n'
    ),
    "subprocess, through a module": (
        'from apothem.conformity import _bounded_run\n_bounded_run.subprocess.run(["x"])\n'
    ),
    "vars of a module": 'import os\nvars(os)["sys" + "tem"]("x")\n',
    "module __dict__": 'import os\nos.__dict__["sys" + "tem"]("x")\n',
    "sys.modules.get": 'import sys\nsys.modules.get("subprocess").run(["x"])\n',
    "importlib.__import__": (
        'import importlib\nimportlib.__import__("sub" + "process")\n'
    ),
    "builtins.__import__": 'import builtins\nbuiltins.__import__("sub" + "process")\n',
    "builtins.exec": 'import builtins\nbuiltins.exec("import sub" + "process")\n',
    "platform.architecture": "import platform\nplatform.architecture()\n",
    "venv": 'import venv\nvenv.create("x", with_pip=True)\n',
    "pydoc": 'import pydoc\npydoc.pipepager("text", "x")\n',
    "ensurepip": "import ensurepip\nensurepip.bootstrap()\n",
    "tkinter": 'import tkinter\ntkinter.Tcl().eval("exec x")\n',
    "platform.processor": "import platform\nplatform.processor()\n",
    "pkgutil.resolve_name": (
        'import pkgutil\npkgutil.resolve_name("sub" + "process:run")\n'
    ),
    "__builtins__": '__builtins__.__import__("sub" + "process")\n',
    "sys.modules.pop": 'import sys\nsys.modules.pop("subprocess").run(["x"])\n',
    # Reaching into one of the package's own modules by name.
    "getattr, a starter by name": (
        "from apothem.conformity import _bounded_run\n"
        'getattr(_bounded_run, "run_bounded")(["npm", "test"], timeout=60)\n'
    ),
    "getattr, computed, own module": (
        "from apothem.conformity import _bounded_run\n"
        'getattr(_bounded_run, "run_" + "bounded")(["x"], timeout=5)\n'
    ),
    "getattr, subprocess by name": (
        "from apothem.conformity import _bounded_run\n"
        'getattr(_bounded_run, "subprocess").Popen(["x"])\n'
    ),
    "getattr on a carried subprocess": (
        "from apothem.conformity import _bounded_run\n"
        'getattr(_bounded_run.subprocess, "r" + "un")(["x"])\n'
    ),
    "vars of an own module": (
        "from apothem.conformity import _bounded_run\n"
        'vars(_bounded_run)["sub" + "process"].Popen(["x"])\n'
    ),
    "__dict__ of an own module": (
        "from apothem.conformity import _bounded_run\n"
        '_bounded_run.__dict__["run_" + "bounded"](["x"], timeout=5)\n'
    ),
}


@pytest.mark.parametrize("source", _BYPASSES.values(), ids=list(_BYPASSES))
def test_the_program_guard_catches_each_direct_form(source: str) -> None:
    assert _program_starts(source) != []


def test_the_program_guard_passes_run_git_and_exception_types() -> None:
    source = (
        "import os\n"
        "import shutil\n"
        "import subprocess\n"
        "import subprocess as sp\n"
        "import sys\n"
        "from subprocess import CalledProcessError\n"
        "from apothem.conformity._git import run_git, split_names\n"
        'GIT_ENTRY = ".git"\n'
        "def read() -> subprocess.CompletedProcess[str] | None:\n"
        "    try:\n"
        '        return run_git(["log", "-1"], timeout=5)\n'
        "    except (subprocess.TimeoutExpired, sp.SubprocessError):\n"
        "        return None\n"
        "    except CalledProcessError:\n"
        "        return None\n"
        'here = os.path.join(os.getcwd(), os.environ.get("HOME", ""))\n'
        'shutil.copyfile("a", "b")\n'
        'module = sys.modules.get(getattr(read, "__module__", ""))\n'
        'name = getattr(os, "name")\n'
        # A field or a setting that only shares a module's name starts nothing.
        "def which_step(result, context):\n"
        "    return result.subprocess, context.os.system\n"
        "from apothem.conformity import _grep_base\n"
        'check = getattr(_grep_base, "has_git_entry")\n'
    )
    assert _program_starts(source) == []


# ``_bounded_run.py`` starts programs and ``_git.py`` names git; both are left
# out of the guard by their path below the package. The one caller of
# ``run_bounded`` besides ``run_git``, by path and function, is the gate's
# launcher, which starts a validator with this Python.
_RUN_BOUNDED_CALLERS = {"gate.py": frozenset({"_run_standalone"})}


def _modules_that_start_programs(package: Path) -> list[str]:
    """Return ``path:line`` for each program start below *package*.

    Only the package's own ``_git.py`` and ``_bounded_run.py`` are left out,
    by their path: a file of the same name in a subfolder is checked. A call
    to ``run_bounded`` counts everywhere but in ``_run_standalone`` of the
    package's own ``gate.py`` and in ``run_git`` of its ``_git.py``, which is
    checked for that one rule.
    """
    offenders: list[str] = []
    for module in sorted(package.rglob("*.py")):
        relative = module.relative_to(package).as_posix()
        if relative == "_bounded_run.py":
            continue
        source = module.read_text(encoding="utf-8")
        if relative == "_git.py":
            lines = _run_bounded_uses(source, inside=frozenset({"run_git"}))
        else:
            allowed = _RUN_BOUNDED_CALLERS.get(relative, frozenset())
            lines = _program_starts(source, run_bounded_in=allowed)
        offenders.extend(f"{relative}:{line}" for line in lines)
    return offenders


def test_no_conformity_module_starts_a_program_itself() -> None:
    """No module but ``_git.py`` and ``_bounded_run.py`` trips the guard.

    ``_bounded_run.py`` is the one module that starts a program:
    ``run_git`` starts git through ``run_bounded``, and gate.py's validator
    launcher (``_run_standalone``) starts Python through it. The guard flags
    the forms :func:`_program_starts` lists, a ``run_bounded`` call anywhere
    else among them; it is a tripwire, not a proof that nothing else starts.
    """
    package = Path(gate.__file__).resolve().parent
    assert _modules_that_start_programs(package) == []


def test_run_bounded_is_allowed_only_in_the_gate_launcher(tmp_path: Path) -> None:
    """``run_bounded`` passes in ``gate.py``'s ``_run_standalone`` and nowhere else."""
    # The form gate.py uses: the name imported, the call inside the launcher.
    launcher = (
        "import sys\n"
        "from apothem.conformity._bounded_run import run_bounded\n"
        "def _run_standalone():\n"
        "    return run_bounded([sys.executable], timeout=5)\n"
    )
    elsewhere = (
        "def _helper():\n"
        "    return run_bounded([sys.executable], timeout=5)\n"
        "START = run_bounded\n"
    )
    package = tmp_path / "conformity"
    (package / "sub").mkdir(parents=True)
    (package / "gate.py").write_text(launcher + elsewhere, encoding="utf-8")
    (package / "sub" / "gate.py").write_text(launcher, encoding="utf-8")
    (package / "some_grep.py").write_text(launcher, encoding="utf-8")

    assert _program_starts(launcher) == [2, 4]
    assert (
        _program_starts(launcher, run_bounded_in=frozenset({"_run_standalone"})) == []
    )
    assert _modules_that_start_programs(package) == [
        "gate.py:6",
        "gate.py:7",
        "some_grep.py:2",
        "some_grep.py:4",
        "sub/gate.py:2",
        "sub/gate.py:4",
    ]

    # Inside the launcher only the direct call passes: the name kept as a
    # value, or used in a nested function or a lambda, could leave it.
    allowed = frozenset({"_run_standalone"})
    leaks = (
        "import sys\n"
        "from apothem.conformity._bounded_run import run_bounded\n"
        "LATER = []\n"
        "def _run_standalone():\n"
        "    global START\n"
        "    START = run_bounded\n"
        "    LATER.append(lambda: run_bounded([sys.executable], timeout=5))\n"
        "    def inner():\n"
        "        return run_bounded([sys.executable], timeout=5)\n"
        "    return run_bounded([sys.executable], timeout=5)\n"
        "class Holder:\n"
        "    def _run_standalone(self):\n"
        "        return run_bounded([sys.executable], timeout=5)\n"
    )
    assert _program_starts(leaks, run_bounded_in=allowed) == [6, 7, 9, 13]


def test_run_bounded_in_the_git_helper_is_called_by_run_git_only() -> None:
    """In ``_git.py`` only ``run_git`` may call ``run_bounded``."""
    helper = (
        "from apothem.conformity import _bounded_run\n"
        "def run_git(args):\n"
        '    return _bounded_run.run_bounded(["git", *args], timeout=5)\n'
    )
    extra = (
        "def run_anything(argv):\n"
        "    return _bounded_run.run_bounded(argv, timeout=5)\n"
    )
    inside = frozenset({"run_git"})
    assert _run_bounded_uses(helper, inside=inside) == []
    assert _run_bounded_uses(helper + extra, inside=inside) == [5]

    package = Path(gate.__file__).resolve().parent
    real = (package / "_git.py").read_text(encoding="utf-8")
    assert _run_bounded_uses(real, inside=inside) == []
    assert _run_bounded_uses(real, inside=frozenset()) != []


def test_the_module_walk_leaves_out_the_two_starters_by_path_only(
    tmp_path: Path,
) -> None:
    """A ``_git.py`` in a subfolder, or an aliased import, is not passed over."""
    package = tmp_path / "conformity"
    (package / "sub").mkdir(parents=True)
    direct = 'import subprocess\nsubprocess.run(["git", "log"])\n'
    (package / "_git.py").write_text(direct, encoding="utf-8")
    (package / "_bounded_run.py").write_text(direct, encoding="utf-8")
    (package / "sub" / "_git.py").write_text(direct, encoding="utf-8")
    (package / "sub" / "_bounded_run.py").write_text(direct, encoding="utf-8")
    (package / "zz_alias.py").write_text(
        'import subprocess as sp\nsp.run(["g" + "it", "log"])\n', encoding="utf-8"
    )
    (package / "clean.py").write_text(
        "from apothem.conformity._git import run_git\n", encoding="utf-8"
    )

    assert _modules_that_start_programs(package) == [
        "sub/_bounded_run.py:2",
        "sub/_git.py:2",
        "zz_alias.py:2",
    ]


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

    history = agents_md_coverage_grep._read_history(repo)
    assert history is not None
    assert history.times == {
        "pkg/AGENTS.md": 1_700_000_000,
        "pkg/README.md": 1_700_000_000,
        "pkg/x.py": 1_700_001_000,
    }
    assert history.deleted == frozenset()
    assert history.root_is_top
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
    history = agents_md_coverage_grep._read_history(repo)
    assert history is not None
    assert history.times == {"docs/café.md": 1_700_000_000}


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


def _as_name(raw: bytes) -> str:
    """Return *raw*, a name as git stores it, the way the gate reads it."""
    if os.name == "nt":
        return raw.decode("utf-8", "surrogateescape")
    return os.fsdecode(raw)


def _index_entry(repo: Path, oid: str, raw: bytes) -> None:
    """Write a file entry named *raw* straight into the index of *repo*.

    The work tree never sees the name: NTFS cannot hold a carriage return, and
    Git for Windows refuses to add one unless ``core.protectNTFS`` is off.
    That is how such a name reaches a Windows machine: in an index made
    elsewhere.
    """
    record = b"100644 " + oid.encode() + b"\t" + raw + b"\0"
    _git(
        repo,
        "-c",
        "core.protectNTFS=false",
        "update-index",
        "-z",
        "--index-info",
        data=record,
    )


def _odd_name_repo(tmp_path: Path, raw: bytes) -> Path:
    """A repository whose staged change drops ``g`` from a module named *raw*."""
    repo = _empty_repo(tmp_path / "project")
    (repo / "src" / "apothem").mkdir(parents=True)
    (repo / _VERSIONED).write_bytes(b'__version__ = "1.2.3"\n')
    _git(repo, "add", "-A")
    before = b"def f():\n    return 1\n\n\ndef g():\n    return 1\n"
    _index_entry(repo, _git(repo, "hash-object", "-w", "--stdin", data=before), raw)
    _git(repo, *_IDENT, "commit", "-q", "-m", "feat: add a module")
    after = b"def f():\n    return 2\n"
    _index_entry(repo, _git(repo, "hash-object", "-w", "--stdin", data=after), raw)
    return repo


_ODD_NAMES = {
    "carriage-return": b"src/apothem/a\rb.py",
    "carriage-return-line-feed": b"src/apothem/a\r\nb.py",
    "not-utf-8": b"src/apothem/a\xffb.py",
}


@pytest.mark.usefixtures("hermetic_git")
@pytest.mark.parametrize("raw", _ODD_NAMES.values(), ids=list(_ODD_NAMES))
def test_a_name_git_lists_reaches_every_reader_whole(
    raw: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A carriage return or a byte that is not UTF-8 in a name changes nothing.

    Reading git's ``-z`` list as text turned ``\\r`` and ``\\r\\n`` into ``\\n``
    and a byte that is not UTF-8 into U+FFFD. The changed name matched no file,
    so the version check skipped the module and passed a dropped public
    function.
    """
    repo = _odd_name_repo(tmp_path, raw)
    plain = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "-z"],
        cwd=str(repo),
        env=hermetic_git_env(),
        capture_output=True,
        check=True,
        timeout=60,
    )
    assert plain.stdout == raw + b"\0"  # git itself lists the name whole
    as_text = plain.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    assert as_text.replace("\r", "\n") != raw.decode("utf-8", "surrogateescape") + "\0"
    name = _as_name(raw)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(semver_stability_grep, "current_version", lambda: "1.2.3")

    assert production_ready_pr_grep._staged_paths() == [name]
    assert name in no_global_plans_grep._git_ls_files(repo)
    assert name.rpartition("/")[2] in {
        path.name for path in gate._corpus_tracked_files(repo)
    }
    # The index entry has no file in the work tree; the corpus run takes that
    # as it takes any tracked file that is gone from disk.
    gate._run_all_perwrite(repo)
    if git_helper.reaches_git_unchanged(name):
        findings = semver_stability_grep.check_staged()
        assert [finding.path for finding in findings] == [name]  # g was dropped
    else:
        # Windows cannot hand git a name that is not UTF-8: the module's
        # content is unread, which the check reports instead of skipping it.
        with pytest.raises(GitNameError):
            semver_stability_grep.check_staged()
        exit_code = semver_stability_grep._main(["semver-stability-grep", "--staged"])
        payload = json.loads(capsys.readouterr().out)
        assert exit_code == semver_stability_grep.EXIT_FAIL
        assert payload["passed"] is False
        assert payload["check_error"] == str(GitNameError("git cat-file"))


@pytest.mark.skipif(os.name == "nt", reason="NTFS cannot hold a carriage return")
@pytest.mark.usefixtures("hermetic_git")
def test_the_corpus_run_reads_files_with_odd_names(tmp_path: Path) -> None:
    """``--all-perwrite`` reads a tracked file whose name holds ``\\r`` or a bad byte.

    The name came back with ``\\n`` or U+FFFD in its place, named no file, and
    the file was left out of the run without a word.
    """
    repo = _empty_repo(tmp_path / "project")
    (repo / "docs").mkdir()
    names = ["a\rb.md", os.fsdecode(b"c\xe9d.md")]
    for name in names:
        (repo / "docs" / name).write_bytes(b"# page\n")
    _git(repo, "add", "-A")
    _git(repo, *_IDENT, "commit", "-q", "-m", "docs: add two pages")

    tracked = gate._corpus_tracked_files(repo)

    assert [path.name for path in tracked] == names
    assert all(path.is_file() for path in tracked)


def test_file_name_output_keeps_every_byte() -> None:
    """``run_bounded(file_names=True)`` hands back the bytes the program wrote."""
    raw = b"a\rb\0c\r\nd\0e\xfff\0"
    argv = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.buffer.write(bytes.fromhex(sys.argv[1]))",
        raw.hex(),
    ]

    as_text = _bounded_run.run_bounded(argv, timeout=60)
    as_names = _bounded_run.run_bounded(argv, timeout=60, file_names=True)

    # Text, as before: every line ending is "\n", a bad byte is U+FFFD.
    assert as_text.stdout == "a\nb\0c\nd\0e�f\0"
    names = git_helper.split_names(as_names.stdout)
    assert len(names) == 3
    encoding = "utf-8" if os.name == "nt" else sys.getfilesystemencoding()
    assert [name.encode(encoding, "surrogateescape") for name in names] == [
        b"a\rb",
        b"c\r\nd",
        b"e\xfff",
    ]


def test_only_windows_cannot_hand_git_a_name_that_is_not_utf_8() -> None:
    odd = b"a\xffb.py".decode("utf-8", "surrogateescape")
    assert git_helper.reaches_git_unchanged(odd, windows=False)
    assert not git_helper.reaches_git_unchanged(odd, windows=True)
    for name in ("a\rb.py", "a\nb.py", "café.py", 'a"b c.py'):
        assert git_helper.reaches_git_unchanged(name, windows=True), name


_MALFORMED_DIFF_SETTINGS = (
    ("diff.renameLimit", "abc"),
    ("diff.algorithm", "bogus"),
    ("diff.renames", "bogus"),
    ("diff.wsErrorHighlight", "bogus"),
    ("diff.colorMovedWS", "bogus"),
)


@pytest.mark.usefixtures("hermetic_git")
@pytest.mark.parametrize(
    ("key", "value"), _MALFORMED_DIFF_SETTINGS, ids=lambda item: str(item)
)
@pytest.mark.parametrize("folder", [".", "src/apothem"], ids=["top", "subfolder"])
def test_a_malformed_diff_setting_is_not_an_empty_change_set(
    key: str,
    value: str,
    folder: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A ``git diff`` that fails on its own configuration does not pass.

    A value git cannot read for one of these settings makes ``git diff
    --cached`` exit with an error. Both ``--staged`` checks read that as no
    staged change and passed, also from a subfolder of the checkout. The
    version is the repository's own, read from disk: from the subfolder the
    version check finds the package through the top of the work tree.
    """
    repo = _build_repo(tmp_path / "project")
    _config(repo, key, value)
    plain = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(repo),
        env=hermetic_git_env(),
        capture_output=True,
        check=False,
        timeout=60,
    )
    if plain.returncode == 0:
        pytest.skip(f"this git accepts {key}={value}")
    monkeypatch.chdir(repo / folder)

    for module in (production_ready_pr_grep, semver_stability_grep):
        exit_code = module._main([module.GREP_NAME, "--staged"])
        payload = json.loads(capsys.readouterr().out)
        assert exit_code == module.EXIT_FAIL, module.GREP_NAME
        assert payload["passed"] is False
        assert payload["check_error"] == (
            f"git diff --cached failed with exit code {plain.returncode}"
        )


@pytest.mark.usefixtures("hermetic_git")
@pytest.mark.parametrize("folder", ["src/apothem", "src", "docs"])
def test_the_version_check_reads_the_change_set_from_a_subfolder(
    folder: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``semver_stability_grep --staged`` finds a dropped function from a subfolder.

    It looked for ``src/apothem/__init__.py`` below the current folder only.
    From a subfolder it found no version, ran no git, and passed.
    """
    repo = _build_repo(tmp_path / "project")
    (repo / "docs").mkdir()
    listed = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", "src/apothem"],
        cwd=str(repo / folder),
        env=hermetic_git_env(),
        capture_output=True,
        check=True,
        timeout=60,
    )
    assert listed.stdout == b""  # git reads that path from the subfolder
    monkeypatch.chdir(repo / folder)

    findings = semver_stability_grep.check_staged()
    assert [finding.path for finding in findings] == [_TRACKED]  # g was dropped
    exit_code = semver_stability_grep._main(["semver-stability-grep", "--staged"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == semver_stability_grep.EXIT_FAIL
    assert "check_error" not in payload
    assert [finding["path"] for finding in payload["findings"]] == [_TRACKED]


@pytest.mark.usefixtures("hermetic_git")
@pytest.mark.parametrize("folder", [".", "src/apothem"], ids=["top", "subfolder"])
def test_a_refused_checkout_does_not_pass_a_staged_check(
    folder: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A git that cannot read ``.git/config`` fails both ``--staged`` checks.

    The repository holds the package, so from a subfolder the version check
    still has a change set to read, and reports the git that refused it.
    """
    repo = _build_repo(tmp_path / "project")
    with (repo / ".git" / "config").open("ab") as config:
        config.write(b"[broken\n")
    plain = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(repo),
        env=hermetic_git_env(),
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert plain.returncode != 0  # git refuses the repository
    monkeypatch.chdir(repo / folder)

    for module in (production_ready_pr_grep, semver_stability_grep):
        exit_code = module._main([module.GREP_NAME, "--staged"])
        payload = json.loads(capsys.readouterr().out)
        assert exit_code == module.EXIT_FAIL, module.GREP_NAME
        assert payload["passed"] is False
        assert payload["check_error"] == (
            f"git diff --cached failed with exit code {plain.returncode}"
        )


def _git_must_not_run(argv: list[str], **_kwargs: object) -> None:
    """Stand in for ``run_bounded`` where a check has to finish without git."""
    raise AssertionError(f"git ran: {argv}")


def _refuse_nothing(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A healthy checkout."""


def _refuse_by_config(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A line in ``.git/config`` git cannot read."""
    with (repo / ".git" / "config").open("ab") as config:
        config.write(b"[broken\n")


def _refuse_by_owner(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """git takes the checkout as another user's (as in many CI containers)."""
    monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")


@pytest.mark.usefixtures("hermetic_git")
@pytest.mark.parametrize(
    "refuse",
    [_refuse_nothing, _refuse_by_config, _refuse_by_owner],
    ids=["healthy", "broken-config", "another-owner"],
)
@pytest.mark.parametrize("folder", [".", "lib"], ids=["top", "subfolder"])
def test_the_version_check_passes_a_project_without_the_package_without_git(
    refuse: Callable[[Path, pytest.MonkeyPatch], None],
    folder: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A project with no ``src/apothem`` passes the version check, git or no git.

    The check covers Apothem's own package. Where no folder up to the top of
    the checkout holds it, the answer is known without git, so a repository
    git refuses must not fail a check that has nothing to compare. The
    change-set check still reports that repository.
    """
    repo = _empty_repo(tmp_path / "project")
    (repo / "lib").mkdir()
    (repo / "lib" / "x.py").write_bytes(b"def f():\n    return 1\n")
    _dated_commit(repo, "feat: add lib", 1_700_000_000)
    (repo / "lib" / "x.py").write_bytes(b"X = 1\n")
    _git(repo, "add", "-A")
    refuse(repo, monkeypatch)
    plain = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(repo),
        env=hermetic_git_env(),
        capture_output=True,
        check=False,
        timeout=60,
    )
    refused = refuse is not _refuse_nothing
    if refused and plain.returncode == 0:
        pytest.skip("this git does not refuse the checkout this way")
    monkeypatch.chdir(repo / folder)

    production_ready_pr_grep._main(["production-ready-pr-grep", "--staged"])
    assert ("check_error" in json.loads(capsys.readouterr().out)) is refused

    monkeypatch.setattr(_bounded_run, "run_bounded", _git_must_not_run)
    exit_code = semver_stability_grep._main(["semver-stability-grep", "--staged"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == semver_stability_grep.EXIT_PASS
    assert payload["passed"] is True
    assert "check_error" not in payload


@pytest.mark.usefixtures("hermetic_git")
def test_the_version_check_needs_no_pathspec_magic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``GIT_LITERAL_PATHSPECS`` in the environment hides no change from a subfolder.

    git then reads a ``:(top)`` path as a plain file name, which matches
    nothing. The check runs git in the package's folder with a plain path.
    """
    repo = _build_repo(tmp_path / "project")
    (repo / "docs").mkdir()
    monkeypatch.setenv("GIT_LITERAL_PATHSPECS", "1")
    monkeypatch.chdir(repo / "docs")

    findings = semver_stability_grep.check_staged()

    assert [finding.path for finding in findings] == [_TRACKED]  # g was dropped


@pytest.mark.usefixtures("hermetic_git")
@pytest.mark.parametrize("folder", [".", "docs"], ids=["top", "subfolder"])
def test_the_version_check_reads_the_change_set_with_git_dir_exported(
    folder: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hook that exports ``GIT_DIR`` and runs in a subfolder hides no change.

    With ``GIT_DIR`` set and no ``GIT_WORK_TREE``, git takes the folder it
    runs in as the top of the work tree. The check runs git in the folder
    that holds the package, so the staged list is the same from a subfolder.
    """
    repo = _build_repo(tmp_path / "project")
    (repo / "docs").mkdir()
    monkeypatch.setenv("GIT_DIR", str(repo / ".git"))
    monkeypatch.chdir(repo / folder)

    findings = semver_stability_grep.check_staged()

    assert [finding.path for finding in findings] == [_TRACKED]  # g was dropped


@pytest.mark.usefixtures("hermetic_git")
def test_the_version_check_follows_a_link_into_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A current folder reached through a link is read as the folder it names.

    On Windows the current folder keeps the text of a junction's path, so
    ``..`` from there leads out of the checkout. The search for the package
    starts from the real folder, as git's own search does.
    """
    repo = _build_repo(tmp_path / "project")
    (repo / "docs").mkdir()
    link = tmp_path / "elsewhere" / "docs-link"
    link.parent.mkdir()
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(repo / "docs"), str(link))
    else:
        link.symlink_to(repo / "docs", target_is_directory=True)
    monkeypatch.chdir(link)

    findings = semver_stability_grep.check_staged()

    assert [finding.path for finding in findings] == [_TRACKED]  # g was dropped


@pytest.mark.usefixtures("hermetic_git")
def test_the_version_check_passes_a_checkout_without_the_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--`` marks ``src/apothem`` as a path, so a missing folder is no error.

    Without it git stops with "ambiguous argument" where the folder is gone,
    which is not a change set git refused to list.
    """
    repo = _empty_repo(tmp_path / "project")
    (repo / "README.md").write_bytes(b"# readme\n")
    _dated_commit(repo, "docs: add the readme", 1_700_000_000)
    (repo / "README.md").write_bytes(b"# readme, second\n")
    _git(repo, "add", "-A")
    plain = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "src/apothem"],
        cwd=str(repo),
        env=hermetic_git_env(),
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert plain.returncode != 0  # without "--" git cannot tell path from revision
    monkeypatch.chdir(repo)
    monkeypatch.setattr(semver_stability_grep, "current_version", lambda: "1.2.3")

    exit_code = semver_stability_grep._main(["semver-stability-grep", "--staged"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == semver_stability_grep.EXIT_PASS
    assert payload["passed"] is True
    assert "check_error" not in payload


def test_in_checkout_looks_above_the_folder_and_stops_at_a_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    project = tmp_path / "project"
    inner = project / "src" / "apothem"
    inner.mkdir(parents=True)
    assert not in_checkout(inner)  # no .git below the ceiling

    (project / ".git").mkdir()
    assert in_checkout(project)
    assert in_checkout(inner)

    # git does not look in or above a ceiling folder, and neither does this.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(project))
    assert not in_checkout(inner)
    assert in_checkout(project)  # the folder itself is still searched

    # git ignores a ceiling entry that is not a full path.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", "project")
    assert in_checkout(inner)


def test_in_checkout_stops_at_another_file_system(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A folder mounted below a repository is not inside that repository.

    git stops its search at a folder on another file system and reports no
    repository there. A walk that went on found the ``.git`` above the mount,
    so git's "no repository" was reported as a git that refused a checkout.
    """
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.delenv("GIT_DISCOVERY_ACROSS_FILESYSTEM", raising=False)
    outer = tmp_path / "outer"
    mounted = outer / "mounted"
    inner = mounted / "work"
    inner.mkdir(parents=True)
    (outer / ".git").mkdir()
    below_mount = {mounted.resolve(), inner.resolve()}

    def device(folder: Path) -> int:
        # Stand in for a mount: "mounted" and below are a file system apart.
        return 2 if folder in below_mount else 1

    monkeypatch.setattr(_grep_base, "_device", device)
    monkeypatch.setattr(_grep_base, "_STOPS_AT_FILE_SYSTEM", True)

    assert not in_checkout(inner)
    assert not in_checkout(mounted)
    assert in_checkout(outer)
    # A repository on the mounted file system itself is found.
    (mounted / ".git").mkdir()
    assert in_checkout(inner)
    (mounted / ".git").rmdir()

    # git searches across file systems when this variable is set ...
    monkeypatch.setenv("GIT_DISCOVERY_ACROSS_FILESYSTEM", "1")
    assert in_checkout(inner)
    monkeypatch.setenv("GIT_DISCOVERY_ACROSS_FILESYSTEM", "false")
    assert not in_checkout(inner)
    # ... and Git for Windows always does.
    monkeypatch.setattr(_grep_base, "_STOPS_AT_FILE_SYSTEM", False)
    assert in_checkout(inner)


def test_in_checkout_reads_ceiling_links_as_git_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ceiling entry given through a link is resolved, unless an empty entry precedes it."""
    project = tmp_path / "real" / "project"
    inner = project / "src"
    inner.mkdir(parents=True)
    (tmp_path / "real" / ".git").mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(tmp_path / "real" / "project", target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"this host cannot create a directory symlink: {exc}")

    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(link))
    assert not in_checkout(inner)  # the link names "project", which stops the walk
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", os.pathsep + str(link))
    assert in_checkout(inner)  # after an empty entry the link is taken as written


def _without_drive(folder: Path) -> str:
    """Return *folder* as Windows writes it with no drive letter."""
    return os.path.splitdrive(str(folder))[1]


# Each case names a value for GIT_CEILING_DIRECTORIES, given the folder that
# holds the repository; ``a`` is the folder between it and the current one.
_CEILING_CASES: dict[str, Callable[[Path], str]] = {
    "no ceiling": lambda top: "",
    "the folder between": lambda top: str(top / "a"),
    "the repository's own folder": lambda top: str(top),
    "a folder beside": lambda top: str(top / "other"),
    "not a full path": lambda top: "a",
    "a missing folder on the way": lambda top: str(top / "missing" / ".." / "a"),
    "a trailing separator": lambda top: str(top / "a") + os.sep,
    "after an empty entry, as git writes it": (
        lambda top: os.pathsep + (top / "a").as_posix()
    ),
    "after an empty entry, with a dot": (
        lambda top: os.pathsep + top.as_posix() + "/./a"
    ),
    "after an empty entry, a trailing slash": (
        lambda top: os.pathsep + (top / "a").as_posix() + "/"
    ),
    "after an empty entry, the platform's separators": (
        lambda top: os.pathsep + str(top / "a")
    ),
    "after an empty entry, another case": (
        lambda top: os.pathsep + (top / "a").as_posix().upper()
    ),
    "second of two entries": lambda top: (
        str(top / "other") + os.pathsep + str(top / "a")
    ),
}
if os.name == "nt":
    _CEILING_CASES["no drive letter"] = lambda top: _without_drive(top / "a")
    _CEILING_CASES["no drive letter, forward slashes"] = lambda top: _without_drive(
        top / "a"
    ).replace("\\", "/")


@pytest.mark.usefixtures("hermetic_git")
@pytest.mark.parametrize("case", list(_CEILING_CASES))
def test_in_checkout_agrees_with_git_about_ceilings(
    case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """For each ceiling value, ``in_checkout`` says what git itself finds.

    The answer is git's own: ``git rev-parse --git-dir`` in the same folder
    with the same environment either finds the repository or does not.
    """
    top = _empty_repo((tmp_path / "top").resolve())
    (top / "other").mkdir()
    inner = top / "a" / "b"
    inner.mkdir(parents=True)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", _CEILING_CASES[case](top))

    found = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=str(inner),
        env=hermetic_git_env(),
        capture_output=True,
        check=False,
        timeout=60,
    )

    assert in_checkout(inner) is (found.returncode == 0), found.stderr


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        ("true", True),
        ("Yes", True),
        ("on", True),
        ("2", True),
        ("1k", True),
        ("-1", True),
        ("0", False),
        ("0k", False),
        ("", False),
        ("false", False),
        ("no", False),
        ("off", False),
        ("maybe", False),
    ],
)
def test_a_git_flag_is_read_as_git_reads_it(
    value: str, expected: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_DISCOVERY_ACROSS_FILESYSTEM", value)
    assert _grep_base._git_flag_is_set("GIT_DISCOVERY_ACROSS_FILESYSTEM") is expected


@pytest.mark.usefixtures("hermetic_git")
def test_a_recreated_folder_companion_is_fresh_until_committed(
    tmp_path: Path,
) -> None:
    """A per-folder ``AGENTS.md`` written again after its deletion is not stale.

    Its newest commit is the one that deleted it. That commit's time was used
    for the new file, so content committed after the deletion made a
    brand-new, uncommitted companion read as stale.
    """
    repo = _empty_repo(tmp_path / "project")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "README.md").write_bytes(b"# pkg\n")
    (repo / "pkg" / "AGENTS.md").write_bytes(b"# pkg notes\n")
    _dated_commit(repo, "docs: add pkg", 1_700_000_000)
    (repo / "pkg" / "AGENTS.md").unlink()
    _dated_commit(repo, "docs: drop the pkg notes", 1_700_000_500)
    (repo / "pkg" / "x.py").write_bytes(b"X = 1\n")
    _dated_commit(repo, "feat: add pkg code", 1_700_001_000)
    (repo / "pkg" / "AGENTS.md").write_bytes(b"# pkg notes, again\n")

    result = agents_md_coverage_grep.check(repo)
    assert result.freshness_checked
    assert result.findings == []

    # Committed again, it is judged by that commit: fresh now, and stale once
    # the folder's content changes after it.
    _dated_commit(repo, "docs: write the pkg notes again", 1_700_002_000)
    assert agents_md_coverage_grep.check(repo).findings == []
    (repo / "pkg" / "y.py").write_bytes(b"Y = 1\n")
    _dated_commit(repo, "feat: add more pkg code", 1_700_003_000)
    result = agents_md_coverage_grep.check(repo)
    assert [(finding.surface, finding.kind) for finding in result.findings] == [
        ("pkg/AGENTS.md", "stale-companion")
    ]


@pytest.mark.usefixtures("hermetic_git")
def test_a_deleted_content_file_still_counts_as_a_folder_change(
    tmp_path: Path,
) -> None:
    """Only a companion's own deletion is set aside; content deletions count."""
    repo = _empty_repo(tmp_path / "project")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "README.md").write_bytes(b"# pkg\n")
    (repo / "pkg" / "x.py").write_bytes(b"X = 1\n")
    (repo / "pkg" / "AGENTS.md").write_bytes(b"# pkg notes\n")
    _dated_commit(repo, "feat: add pkg", 1_700_000_000)
    (repo / "pkg" / "x.py").unlink()
    _dated_commit(repo, "feat: drop pkg code", 1_700_001_000)

    result = agents_md_coverage_grep.check(repo)

    assert [(finding.surface, finding.kind) for finding in result.findings] == [
        ("pkg/AGENTS.md", "stale-companion")
    ]


@pytest.mark.usefixtures("hermetic_git")
def test_a_subfolder_root_reports_its_own_companion_like_the_whole_repository(
    tmp_path: Path,
) -> None:
    """Only the ``AGENTS.md`` at the top of the repository is the canon.

    A run on a subfolder treated that subfolder's own ``AGENTS.md`` as the
    canon and passed it, while a run on the whole repository reported it.
    """
    repo = _empty_repo(tmp_path / "project")
    pkg = repo / "proj" / "pkg"
    pkg.mkdir(parents=True)
    (repo / "README.md").write_bytes(b"# project\n")
    (repo / "AGENTS.md").write_bytes(b"# agents\n")
    (pkg / "README.md").write_bytes(b"# pkg\n")
    (pkg / "AGENTS.md").write_bytes(b"# pkg notes\n")
    _dated_commit(repo, "docs: add pkg", 1_700_000_000)
    (pkg / "x.py").write_bytes(b"X = 1\n")
    _dated_commit(repo, "feat: add pkg code", 1_700_001_000)

    whole = agents_md_coverage_grep.check(repo)
    part = agents_md_coverage_grep.check(pkg)

    assert [(finding.surface, finding.kind) for finding in whole.findings] == [
        ("proj/pkg/AGENTS.md", "stale-companion")
    ]
    assert [(finding.surface, finding.kind) for finding in part.findings] == [
        ("AGENTS.md", "stale-companion")
    ]
