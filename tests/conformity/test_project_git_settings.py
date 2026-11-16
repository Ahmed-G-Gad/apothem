# SPDX-License-Identifier: MIT

"""The gate's git commands never start a program the checked project names.

Why these tests exist. The conformity gate runs git inside the project it
checks: ``git ls-files`` for ``--all-perwrite`` and ``no-global-plans-grep``,
``git log`` for ``conventional-commit-grep`` and ``agents-md-coverage-grep``,
and ``git diff --cached`` / ``git show`` for the two ``--staged`` change-set
checks. git reads that repository's own ``.git/config`` on every run, and a
project that arrives with its ``.git`` folder (an archive, a shared folder) can
plant settings there that make git start a program while it only reads.

Each scenario below plants one such setting in a throwaway repository, proves
the plant is live by running the matching plain git command (the planted
program then runs and leaves a marker file), and then drives every git call
the gate makes. No marker may appear. The scenarios that a plain git command
triggers today are the file-system monitor (``core.fsmonitor``, also through
``include.path`` and ``.git/config.worktree``), commit-signature checks
(``log.showSignature`` with the OpenPGP, SSH and X.509 programs) and the lazy
fetch of a partial clone (``remote.<name>.uploadpack``, ``core.sshCommand``,
``ext::``). Hooks, filters, diff programs and pagers do not run for the gate's
commands today; they are planted too, so a later command change cannot bring
them back unnoticed.

HERMETIC: every repository lives under ``tmp_path``. The fixture git commands
and the plain controls run with :func:`hermetic_git_env`, and the gate's own
git calls see the same hidden global and system configuration, so the
developer's git configuration changes nothing here.
"""

from __future__ import annotations

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


def _git(repo: Path, *args: str, data: bytes | None = None) -> str:
    """Run a fixture git command in *repo* with no host configuration."""
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        env=hermetic_git_env(),
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


def _build_repo(repo: Path) -> Path:
    """Two commits, a staged change to a public module, an unstaged one on top."""
    repo.mkdir()
    _git(repo, "-c", "init.defaultBranch=main", "init", "-q")
    (repo / "src" / "apothem").mkdir(parents=True)
    (repo / _TRACKED).write_bytes(b"def f():\n    return 1\n")
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


def _sign_head(repo: Path, fmt: str) -> None:
    """Replace HEAD with a copy that carries a *fmt* signature header."""
    header, _, message = _git(repo, "cat-file", "commit", "HEAD").partition("\n\n")
    signature = "\n ".join(_SIGNATURES[fmt])
    signed = f"{header}\ngpgsig {signature}\n\n{message}\n"
    oid = _git(
        repo, "hash-object", "-t", "commit", "-w", "--stdin", data=signed.encode()
    )
    _git(repo, "update-ref", "refs/heads/main", oid)


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


_SHOW_HEAD = ("show", f"HEAD:{_TRACKED}")
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
    """Run each git-reading path of the gate and its validators against *repo*."""
    gate._run_all_perwrite(repo)
    with contextlib.suppress(RuntimeError):
        no_global_plans_grep._git_ls_files(repo)
    conventional_commit_grep._read_head_subject(repo)
    agents_md_coverage_grep._last_commit_times(repo)
    # The two change-set checks read the repository the process runs in.
    monkeypatch.chdir(repo)
    production_ready_pr_grep._staged_paths()
    monkeypatch.setattr(semver_stability_grep, "current_version", lambda: "1.2.3")
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
        "-1",
        "--pretty=%B",
    ]

    argv = git_helper.git_argv("/usr/bin/git", ["ls-files", "-z"])
    assert argv[1 + options :] == ["ls-files", "-z"]

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
    assert settings["log.showSignature"] == "false"
    assert settings["gc.auto"] == "0"
    assert settings["maintenance.auto"] == "false"
    # The hooks path sits below a regular file, where no hook can exist.
    assert Path(settings["core.hooksPath"]).parent.is_file()
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
