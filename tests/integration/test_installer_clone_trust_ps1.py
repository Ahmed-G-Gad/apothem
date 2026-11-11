# SPDX-License-Identifier: MIT

"""The PowerShell installer and updater: what an existing clone may hold
before git reads its objects or runs a filter, and before the engine runs
from it.

Each case plants something a clone at APOTHEM_HOME must not carry, then
runs install.ps1 or update.ps1 on it: settings that make git fetch a
missing object by running a command (a promisor remote, or a branch whose
remote is the clone itself), a setting name that holds a carriage return,
a GIT_ALLOW_PROTOCOL in the calling shell, a .gitattributes in the work
tree that git does not track or that differs from the index, a file that
makes git borrow objects from another repository, and files under src
that git does not track. The sh scripts print the same messages
(tests/scripts/test_installer_parity.py compares them).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests._shared.release_fixture import git, repoint_tag
from tests.integration.test_installer_hardening_ps1 import (
    INSTALLER_DIR,
    TRUSTED,
    _in,
    _invoke,
    _out,
    _script_env,
)
from tests.integration.test_installer_release_mode_ps1 import (
    _PWSH,
    TAG,
    _clone_at_old_tag,
    _head,
    _make_junction,
)

pytestmark = [
    pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host"),
    pytest.mark.skipif(
        sys.platform != "win32",
        reason="Git for Windows runs the sh stubs; the sh scripts' own tests cover POSIX",
    ),
]

#: Every PowerShell on this host: PowerShell 7 and Windows PowerShell 5.1.
_POWERSHELLS = [
    shell
    for shell in (shutil.which("pwsh"), shutil.which("powershell"))
    if shell is not None
]

LINE_BREAK = (
    "'s own git config has a setting whose name holds a line break, which an "
    "update in place does not accept. Remove it from "
)

#: A filter the user's own (trusted) git config defines: its clean and
#: smudge commands write a marker, then pass the content through.
_USER_FILTER = (
    '[filter "userfilter"]\n'
    "\tclean = \"touch '{marker}'; cat\"\n"
    "\tsmudge = \"touch '{marker}'; cat\"\n"
)


def _env_for(tmp_path: Path, path: str, gitconfig_extra: str = "") -> dict[str, str]:
    """The run's environment: an update in place, or (path "replace")
    install.ps1 -Yes replacing the clone with the archive in checksum mode,
    which looks for local work in the clone before it downloads."""
    if path == "replace":
        return _script_env(
            tmp_path,
            mode="checksum",
            gitconfig_extra=gitconfig_extra,
            extra_env={"APOTHEM_ALLOW_UNVERIFIED": "1"},
        )
    return _script_env(tmp_path, gitconfig_extra=gitconfig_extra)


def _stat_dirty(home: Path, name: str) -> None:
    """Give HOME/NAME a later time but the same bytes, so git must compare
    its content with the copy in HEAD (reading that blob, and running any
    clean filter its attributes assign) to tell it did not change."""
    target = home / name
    stat = target.stat()
    os.utime(target, (stat.st_atime + 100, stat.st_mtime + 100))


def _drop_blob(home: Path, name: str) -> None:
    """Delete the loose object HEAD:NAME from the clone at HOME, then make
    NAME stat-dirty, so git's next diff wants the missing blob."""
    oid = git(["rev-parse", f"HEAD:{name}"], home).strip()
    obj = home / ".git" / "objects" / oid[:2] / oid[2:]
    assert obj.is_file(), f"{obj} is not a loose object"
    obj.chmod(0o644)
    obj.unlink()
    _stat_dirty(home, name)


def _clone_on_main_missing_a_blob(tmp_path: Path) -> tuple[Path, Path, str]:
    """A clone at OLD_TAG, on branch main, whose pyproject.toml blob is gone
    and whose pyproject.toml is stat-dirty; TAG names the next commit."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    git(["checkout", "--quiet", "-B", "main", old_commit], home)
    _drop_blob(home, "pyproject.toml")
    return repo, home, old_commit


def _first_named(home: Path, names: set[str]) -> str:
    """The first of NAMES in the clone's own config file, in file order."""
    listed = git(
        ["config", "--file", str(home / ".git" / "config"), "--name-only", "--list"],
        home,
    ).splitlines()
    return next(name for name in listed if name in names)


# Item 1: git fetches a missing object by running a command --------------------


@pytest.mark.parametrize(
    ("script", "path"),
    [
        ("install.ps1", "in-place"),
        ("update.ps1", "in-place"),
        ("install.ps1", "replace"),
    ],
)
def test_a_clone_that_would_fetch_a_missing_object_through_a_command_is_refused(
    tmp_path: Path, script: str, path: str
) -> None:
    """A clone of repository format 1 whose extensions.partialclone holds an
    --upload-pack option, with branch main's remote set to the clone itself,
    makes git fetch a missing object by running that command (through sh)
    as soon as a diff needs it. Every one of those keys was on the
    allow-list. Now neither key may be there, git may not fetch a missing
    object at all, and the run stops before git reads any object."""
    _, home, old_commit = _clone_on_main_missing_a_blob(tmp_path)
    marker = tmp_path / "lazy-fetch-ran"
    git(["config", "core.repositoryformatversion", "1"], home)
    git(
        [
            "config",
            "extensions.partialclone",
            f"--upload-pack=touch '{marker.as_posix()}';",
        ],
        home,
    )
    git(["config", "branch.main.remote", "."], home)
    named = _first_named(home, {"branch.main.remote", "extensions.partialclone"})

    result = _invoke(tmp_path, script, _env_for(tmp_path, path))

    plain = _out(result)
    assert not marker.exists(), plain
    assert result.returncode != 0, plain
    assert _in(
        f"{home}'s own git config sets {named}{TRUSTED} {home}/.git/config, then "
        "re-run.",
        plain,
    ), plain
    assert _head(home) == old_commit, plain


# Item 2: a setting name that holds a carriage return --------------------------


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_a_setting_name_holding_a_carriage_return_is_refused(
    tmp_path: Path, script: str
) -> None:
    """git keeps a carriage return inside a quoted subsection, so
    [remote "origin.url<CR>branch.x"] lists as remote.origin.url<CR>
    branch.x.uploadpack: one name, but two allowed ones for a reader that
    ends a line at CR. As a promisor remote with an uploadpack command, it
    ran that command when a diff needed a missing object. The run now stops,
    naming the file, before anything is fetched."""
    repo, home, old_commit = _clone_on_main_missing_a_blob(tmp_path)
    marker = tmp_path / "cr-remote-ran"
    with (home / ".git" / "config").open("ab") as config:
        config.write(
            b'[remote "origin.url\rbranch.x"]\n'
            + f"\tuploadpack = touch '{marker.as_posix()}'; git-upload-pack\n".encode()
            + f"\turl = {repo.as_posix()}\n".encode()
            + b"\tpromisor = true\n"
        )

    result = _invoke(tmp_path, script, _script_env(tmp_path))

    plain = _out(result)
    assert not marker.exists(), plain
    assert result.returncode != 0, plain
    assert _in(f"{home}{LINE_BREAK}{home}/.git/config, then re-run.", plain), plain
    assert _head(home) == old_commit, plain
    assert git(["tag", "--list", TAG], home).strip() == "", plain


def _ps1_define(script: str, names: tuple[str, ...], body: str) -> str:
    """PowerShell that parses SCRIPT (not running it), defines its functions
    and script variables NAMES (a name starting with $ is a variable, whose
    assignment runs), then runs BODY."""
    statements = [
        "Set-StrictMode -Version Latest",
        "$ErrorActionPreference = 'Stop'",
        "$tokens = $null",
        "$parseErrors = $null",
        "$ast = [Management.Automation.Language.Parser]::ParseFile("
        f"'{INSTALLER_DIR / script}', [ref]$tokens, [ref]$parseErrors)",
        "if ($parseErrors) { throw ($parseErrors -join ' | ') }",
    ]
    for name in names:
        if name.startswith("$"):
            find = (
                "$n -is [Management.Automation.Language.AssignmentStatementAst] "
                f"-and $n.Left.Extent.Text -eq '{name}'"
            )
        else:
            find = (
                "$n -is [Management.Automation.Language.FunctionDefinitionAst] "
                f"-and $n.Name -eq '{name}'"
            )
        statements += [
            f"$found = $ast.Find({{ param($n) {find} }}, $true)",
            f"if (-not $found) {{ throw 'no {name} in the script' }}",
            ". ([scriptblock]::Create($found.Extent.Text))",
        ]
    return "; ".join([*statements, body])


def _run_shell(
    shell: str, program: str, **env: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            shell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            program,
        ],
        env={
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "NO_COLOR": "1",
            **env,
        },
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


#: A clone's own config text (after what git init writes) and the setting
#: Assert-CloneConfig names for it: None when the file passes, "<line break>"
#: for the line-break message.
_CONFIG_CASES: tuple[tuple[str, bytes, str | None], ...] = (
    (
        "branch-origin",
        b'[branch "main"]\n\tremote = origin\n\tpushremote = origin\n\tmerge = refs/heads/main\n',
        None,
    ),
    ("branch-self", b'[branch "main"]\n\tremote = .\n', "branch.main.remote"),
    ("branch-case", b'[branch "main"]\n\tremote = Origin\n', "branch.main.remote"),
    ("branch-no-value", b'[branch "main"]\n\tremote\n', "branch.main.remote"),
    ("branch-empty", b'[branch "main"]\n\tremote =\n', "branch.main.remote"),
    (
        "branch-second-value",
        b'[branch "main"]\n\tremote = origin\n\tremote = up\n',
        "branch.main.remote",
    ),
    (
        "branch-line-break",
        b'[branch "main"]\n\tremote = "origin\\n"\n',
        "branch.main.remote",
    ),
    (
        "branch-carriage-return",
        b'[branch "main"]\n\tremote = "origin\r"\n',
        "branch.main.remote",
    ),
    ("branch-crlf-line", b'[branch "main"]\r\n\tremote = origin\r\n', None),
    ("push-remote", b'[branch "main"]\n\tpushremote = up\n', "branch.main.pushremote"),
    (
        "dotted-branch",
        b'[branch "feat.x"]\n\tmerge = refs/heads/feat.x\n\tREMOTE = .\n',
        "branch.feat.x.remote",
    ),
    (
        "first-in-file",
        b'[branch "a"]\n\tremote = up\n[core]\n\tpager = less\n',
        "branch.a.remote",
    ),
    (
        "pager-first",
        b'[core]\n\tpager = less\n[branch "a"]\n\tremote = up\n',
        "core.pager",
    ),
    (
        "partial-clone",
        b"[extensions]\n\tpartialclone = origin\n",
        "extensions.partialclone",
    ),
    ("promisor", b'[remote "origin"]\n\tpromisor = true\n', "remote.origin.promisor"),
    (
        "remote-filter",
        b'[remote "origin"]\n\tpartialclonefilter = blob:none\n',
        "remote.origin.partialclonefilter",
    ),
    (
        "core-filter",
        b"[core]\n\tpartialclonefilter = blob:none\n",
        "core.partialclonefilter",
    ),
    (
        "carriage-return-name",
        b'[remote "origin.url\rbranch.x"]\n\turl = x\n\tpromisor = true\n',
        "<line break>",
    ),
)


@pytest.mark.skipif(not _POWERSHELLS, reason="no PowerShell on this host")
@pytest.mark.parametrize("shell", _POWERSHELLS, ids=lambda s: Path(s).stem)
@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
@pytest.mark.parametrize(
    ("case", "text", "named"), _CONFIG_CASES, ids=[c[0] for c in _CONFIG_CASES]
)
def test_the_config_check_reads_names_and_branch_remotes_as_git_writes_them(
    tmp_path: Path, shell: str, script: str, case: str, text: bytes, named: str | None
) -> None:
    """Assert-CloneConfig, under PowerShell 7 and Windows PowerShell 5.1,
    names the first setting in file order that is off the allow-list or
    whose value breaks a rule (a branch's remote and pushremote must be
    exactly origin), refuses a name that holds a line break without
    printing it, and passes a clone whose branch remotes are origin."""
    home = tmp_path / "clone"
    (home / ".git").mkdir(parents=True)
    (home / ".git" / "config").write_bytes(
        b"[core]\n\trepositoryformatversion = 0\n\tfilemode = false\n"
        b"\tbare = false\n\tlogallrefupdates = true\n" + text
    )
    body = (
        "function Write-Fail { param([string]$Msg) throw $Msg }; "
        'function Get-ClonePath { param([string]$Dir, [string]$Name) "$Dir/.git/$Name" }; '
        "try { Assert-CloneConfig $env:CLONE_HOME; 'passed' } "
        "catch { $_.Exception.Message }"
    )
    program = _ps1_define(
        script,
        (
            "$GitNoProgram",
            "$CloneConfigAllow",
            "Test-AllowedConfigKey",
            "Assert-ClonePlainFile",
            "Test-AttributeFilter",
            "Assert-CloneConfig",
        ),
        body,
    )

    result = _run_shell(shell, program, CLONE_HOME=home.as_posix())

    shown = home.as_posix()
    if named is None:
        expected = "passed"
    elif named == "<line break>":
        expected = f"{shown}{LINE_BREAK}{shown}/.git/config, then re-run."
    else:
        expected = f"{shown}'s own git config sets {named}{TRUSTED} {shown}/.git/config, then re-run."
    assert result.stdout.strip() == expected, result.stdout + result.stderr


# Item 3: transports from the calling shell ------------------------------------


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_a_transport_list_in_the_calling_shell_does_not_reach_git(
    tmp_path: Path, script: str
) -> None:
    """GIT_ALLOW_PROTOCOL wins over every protocol.* setting, so one in the
    calling shell that lists ext would let the clone's own origin address
    (an allowed key) run a program on fetch. The scripts set it to the five
    transports they use, so the fetch fails and the program never runs."""
    _, home, old_commit = _clone_at_old_tag(tmp_path)
    marker = tmp_path / "ext-ran"
    git(["config", "remote.origin.url", f"ext::cmd /c type nul > {marker} & rem"], home)
    env = _script_env(
        tmp_path, extra_env={"GIT_ALLOW_PROTOCOL": "ext:file:git:http:https:ssh"}
    )

    result = _invoke(tmp_path, script, env)

    plain = _out(result)
    assert not marker.exists(), plain
    assert result.returncode != 0, plain
    assert "Could not fetch from the origin of" in plain, plain
    assert _head(home) == old_commit, plain


# Item 4: a .gitattributes in the work tree ------------------------------------

UNTRACKED_ATTRIBUTES = (
    "{home} has a .gitattributes file that git does not track, at {home}/{path}. "
    "git would apply it while it reads the clone. Remove it, then re-run."
)
CHANGED_ATTRIBUTES = (
    "{home} has a changed .gitattributes file at {home}/{path}. git would apply "
    "it while it reads the clone. Undo the change, then re-run."
)


def _commit_attributes(home: Path) -> None:
    """Commit a harmless .gitattributes in the clone (moving HEAD)."""
    (home / ".gitattributes").write_text("*.md text\n", encoding="utf-8", newline="\n")
    git(["add", ".gitattributes"], home)
    git(
        [
            "-c",
            "user.name=T",
            "-c",
            "user.email=t@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "attrs",
        ],
        home,
    )


def _plant_attributes(home: Path, case: str) -> tuple[str, str]:
    """Plant CASE's .gitattributes in the clone; return (message, path)."""
    assign = "* filter=userfilter\n"
    if case == "untracked":
        (home / ".gitattributes").write_text(assign, encoding="utf-8", newline="\n")
        return UNTRACKED_ATTRIBUTES, ".gitattributes"
    if case == "untracked-other-spelling":
        (home / "docs").mkdir()
        (home / "docs" / ".GitAttributes").write_text(
            assign, encoding="utf-8", newline="\n"
        )
        return UNTRACKED_ATTRIBUTES, "docs/.GitAttributes"
    if case == "ignored":
        (home / ".git" / "info").mkdir(exist_ok=True)
        (home / ".git" / "info" / "exclude").write_text("build/\n", encoding="utf-8")
        (home / "build").mkdir()
        (home / "build" / ".gitattributes").write_text(
            assign, encoding="utf-8", newline="\n"
        )
        return UNTRACKED_ATTRIBUTES, "build/.gitattributes"
    _commit_attributes(home)
    (home / ".gitattributes").write_text(assign, encoding="utf-8", newline="\n")
    if case == "staged":
        git(["add", ".gitattributes"], home)
    return CHANGED_ATTRIBUTES, ".gitattributes"


@pytest.mark.parametrize(
    ("script", "path", "case"),
    [
        ("install.ps1", "in-place", "untracked"),
        ("update.ps1", "in-place", "untracked"),
        ("update.ps1", "in-place", "untracked-other-spelling"),
        ("update.ps1", "in-place", "ignored"),
        ("install.ps1", "in-place", "changed"),
        ("update.ps1", "in-place", "changed"),
        ("update.ps1", "in-place", "staged"),
        ("install.ps1", "replace", "untracked"),
        ("install.ps1", "replace", "changed"),
    ],
)
def test_a_gitattributes_file_that_differs_from_the_index_is_refused(
    tmp_path: Path, script: str, path: str, case: str
) -> None:
    """git applies the work tree's .gitattributes files when a diff, status
    or checkout reads a file, so one it does not track (ignored, in a
    folder, or spelled another way included), or one that differs from the
    index or from HEAD, could run a filter the user's own config defines on
    any file. The run stops before git runs any of them; the filter never
    runs."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    marker = tmp_path / "filter-ran"
    message, planted = _plant_attributes(home, case)
    _stat_dirty(home, "pyproject.toml")
    before = _head(home)
    user_filter = _USER_FILTER.format(marker=marker.as_posix())

    result = _invoke(
        tmp_path, script, _env_for(tmp_path, path, gitconfig_extra=user_filter)
    )

    plain = _out(result)
    assert not marker.exists(), plain
    assert result.returncode != 0, plain
    assert _in(message.format(home=home, path=planted), plain), plain
    assert _head(home) == before, plain


def test_a_tracked_gitattributes_file_that_matches_lets_the_update_go_on(
    tmp_path: Path,
) -> None:
    """A .gitattributes file the clone tracks, unchanged, is not refused."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    _commit_attributes(home)

    result = _invoke(tmp_path, "update.ps1", _script_env(tmp_path))

    plain = _out(result)
    assert ".gitattributes" not in plain, plain
    assert _head(home) == _head(repo), plain


# Item 5: objects borrowed from another repository -----------------------------


@pytest.mark.parametrize(
    ("script", "path", "name"),
    [
        ("install.ps1", "in-place", "alternates"),
        ("update.ps1", "in-place", "alternates"),
        ("update.ps1", "in-place", "http-alternates"),
        ("install.ps1", "replace", "alternates"),
    ],
)
def test_a_clone_that_borrows_objects_from_another_repository_is_refused(
    tmp_path: Path, script: str, path: str, name: str
) -> None:
    """objects/info/alternates (or http-alternates) makes git read objects
    from, and run git in, another repository whose settings nothing checks.
    A release clone has neither file, so the run stops before git reads
    any object."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    borrowed = home / ".git" / "objects" / "info" / name
    borrowed.parent.mkdir(parents=True, exist_ok=True)
    borrowed.write_text(f"{(repo / '.git' / 'objects').as_posix()}\n", encoding="utf-8")
    shown = f"{home}/.git/objects/info/{name}"

    result = _invoke(tmp_path, script, _env_for(tmp_path, path))

    plain = _out(result)
    assert result.returncode != 0, plain
    assert _in(
        f"{home} borrows objects from another repository ({shown} names it). A "
        "release clone does not, and the update would run git in that repository "
        f"under settings nothing here checks. Run 'git -C {home} repack -a -d' to "
        f"copy the objects in, remove {shown}, then re-run.",
        plain,
    ), plain
    assert _head(home) == old_commit, plain


# Item 6: files under src that git does not track ------------------------------


def _assert_untracked_src_listed(
    result: subprocess.CompletedProcess[str], home: Path, listed: list[str]
) -> None:
    """The run named LISTED, one line each on the error stream under the
    header, then said what to do."""
    plain = _out(result)
    expected = [
        f"  x {home} has files under src that git does not track, and the engine "
        "could load them:",
        *(f"    {line}" for line in listed),
    ]
    lines = [line.rstrip() for line in result.stderr.splitlines()]
    assert expected[0] in lines, plain
    first = lines.index(expected[0])
    assert lines[first : first + len(expected)] == expected, plain
    assert _in(
        f"Nothing was changed. Move these files out of {home}/src, then re-run.", plain
    ), plain


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_an_untracked_module_under_src_is_refused(tmp_path: Path, script: str) -> None:
    """The engine runs with the clone's src first on its path, so a
    sitecustomize.py, or a module beside the vendored ones, would run with
    it after the tag check. Every untracked file under src stops the run
    before anything is fetched (a file an exclude file ignores, and a
    file named __pycache__, included); files inside a __pycache__ folder do
    not count. The clone is not changed."""
    repo, home, old_commit = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    (home / ".git" / "info").mkdir(exist_ok=True)
    (home / ".git" / "info" / "exclude").write_text("*.pyc\n", encoding="utf-8")
    planted = [
        "src/apothem/stale.pyc",
        "src/apothem/x/__pycache__",
        "src/sitecustomize.py",
    ]
    for name in planted:
        (home / name).parent.mkdir(parents=True, exist_ok=True)
        (home / name).write_text("raise SystemExit('planted')\n", encoding="utf-8")
    cache = home / "src" / "apothem" / "__pycache__" / "__init__.cpython-314.pyc"
    cache.parent.mkdir()
    cache.write_bytes(b"not loaded")

    result = _invoke(tmp_path, script, _script_env(tmp_path))

    plain = _out(result)
    assert result.returncode != 0, plain
    _assert_untracked_src_listed(result, home, [f"{home}/{name}" for name in planted])
    assert _head(home) == old_commit, plain
    assert all((home / name).is_file() for name in planted), plain
    assert git(["tag", "--list", TAG], home).strip() == "", plain


def test_a_long_list_of_untracked_files_under_src_is_cut_at_twenty(
    tmp_path: Path,
) -> None:
    """At most twenty files are listed, then how many more there are."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    names = [f"src/apothem/_vendor/m{index:02}.py" for index in range(23)]
    for name in names:
        (home / name).parent.mkdir(parents=True, exist_ok=True)
        (home / name).write_text("", encoding="utf-8")

    result = _invoke(tmp_path, "update.ps1", _script_env(tmp_path))

    assert result.returncode != 0, _out(result)
    _assert_untracked_src_listed(
        result, home, [*(f"{home}/{n}" for n in names[:20]), "and 3 more"]
    )


@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_python_cache_folders_under_src_are_removed_before_the_engine_runs(
    tmp_path: Path, script: str
) -> None:
    """Bytecode in a __pycache__ folder under src may be stale or planted,
    and Python loads it in place of the source. An update in place removes
    every such folder after the checkout, before the engine first runs, and
    a second update on the same clone (the engine has written its own
    bytecode since) goes on."""
    repo, home, _ = _clone_at_old_tag(tmp_path)
    repoint_tag(repo, TAG, TAG)
    stale = [
        home / "src" / "__pycache__" / "sitecustomize.cpython-314.pyc",
        home / "src" / "apothem" / "__pycache__" / "gone.cpython-314.pyc",
    ]
    for path in stale:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"stale")

    first = _invoke(tmp_path, script, _script_env(tmp_path))
    second = _invoke(tmp_path, script, _script_env(tmp_path))

    assert _head(home) == _head(repo), _out(first)
    assert not any(path.exists() for path in stale), _out(first)
    assert not (home / "src" / "__pycache__").exists(), _out(first)
    assert "has files under src" not in _out(second), _out(second)
    assert "Could not remove the Python cache folders" not in _out(second), _out(second)


@pytest.mark.skipif(not _POWERSHELLS, reason="no PowerShell on this host")
@pytest.mark.parametrize("shell", _POWERSHELLS, ids=lambda s: Path(s).stem)
@pytest.mark.parametrize("script", ["install.ps1", "update.ps1"])
def test_removing_the_cache_folders_never_follows_a_link(
    tmp_path: Path, shell: str, script: str
) -> None:
    """Remove-SourceCache removes each __pycache__ folder under src, a
    junction named __pycache__ as a link only, and a junction inside a
    cache folder without touching what it leads to; it does not enter any
    other junction. Windows PowerShell 5.1's Remove-Item -Recurse would
    delete the files a junction inside the folder leads to."""
    home = tmp_path / "clone"
    src = home / "src"
    outside = {
        name: tmp_path / name for name in ("linked-cache", "inner", "linked-dir")
    }
    for folder in outside.values():
        (folder / "__pycache__").mkdir(parents=True)
        (folder / "keep.txt").write_text("keep\n", encoding="utf-8")
        (folder / "__pycache__" / "keep.pyc").write_bytes(b"keep")
    plain_cache = src / "apothem" / "__pycache__"
    plain_cache.mkdir(parents=True)
    (plain_cache / "x.pyc").write_bytes(b"x")
    (src / "a").mkdir()
    _make_junction(src / "a" / "__pycache__", outside["linked-cache"])
    holding = src / "b" / "__pycache__"
    holding.mkdir(parents=True)
    _make_junction(holding / "inner", outside["inner"])
    _make_junction(src / "c", outside["linked-dir"])
    other_spelling = src / "d" / "__PYCACHE__"
    other_spelling.mkdir(parents=True)
    body = (
        "function Write-Fail { param([string]$Msg) throw $Msg }; "
        "try { Remove-SourceCache $env:CLONE_HOME; 'removed' } "
        "catch { 'FAILED: ' + $_.Exception.Message }"
    )

    result = _run_shell(
        shell,
        _ps1_define(script, ("Remove-SourceCache",), body),
        CLONE_HOME=str(home),
    )

    text = result.stdout + result.stderr
    assert result.stdout.strip() == "removed", text
    assert not plain_cache.exists(), text
    assert not os.path.lexists(src / "a" / "__pycache__"), text
    assert not holding.exists(), text
    assert (src / "c").exists(), text
    assert other_spelling.is_dir(), text
    for folder in outside.values():
        assert (folder / "keep.txt").is_file(), text
        assert (folder / "__pycache__" / "keep.pyc").is_file(), text
