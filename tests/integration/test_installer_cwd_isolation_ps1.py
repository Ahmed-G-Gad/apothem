# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""The PowerShell installer and updater never take code from the current folder.

The Windows counterpart of ``test_installer_cwd_isolation.py``. Two faults are
covered:

- A piped run (``irm ... | iex``) has no script file, so the installer must not
  look for a local source tree, or an interpreter locator, in the current
  folder or its parents. A tree planted there is ignored and the run takes the
  fetched, signature-checked path. A run by path from the script's own
  checkout, and ``APOTHEM_SOURCE``, still use their local tree.
- Python puts the current folder first on ``sys.path`` for ``-c`` and ``-m``,
  so a ``click.py`` or ``apothem\\`` package there would run instead of the
  real one; an empty or relative PYTHONPATH entry does the same before any
  program runs. The dependency probe, pip, the engine runs, the
  ``apothem.cmd`` shim, the updater and the uninstaller must not import from
  the current folder, while the engine still sees the caller's arguments and
  working directory.

Two more: git commands that work on no repository of their own never read a
repository in the current folder, and a run by path through a junction is not
taken as a local checkout.

Each planted module or locator writes a marker file when it runs; the tests
assert that no marker is written.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests._shared.git_env import hermetic_git_env
from tests._shared.release_fixture import (
    MAINTAINER_FINGERPRINT,
    good_signature_status,
    make_tagged_repo,
    write_stub_gpg,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "installer" / "install.ps1"
UPDATER = REPO_ROOT / "scripts" / "installer" / "update.ps1"
TAG = "v9.9.9"
HARNESS = "claude-code"

LOCAL_CHECKOUT_MARKER = "Using local checkout"
EXPLICIT_SOURCE_MARKER = "Using explicit source"
TAG_OK_MARKER = "carries a valid signature from the maintainer key"
CLONING_MARKER = "Cloning"

_PWSH = shutil.which("pwsh") or shutil.which("powershell")
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

pytestmark = pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host")
requires_windows = pytest.mark.skipif(
    sys.platform != "win32", reason="the installer writes a .cmd shim on Windows"
)

UNINSTALLER = REPO_ROOT / "scripts" / "installer" / "uninstall.ps1"

#: The user PYTHONPATH values each launcher is run with: none, ones whose
#: empty entry Python would read as the current folder, and relative ones
#: (``.``, and the drive-relative ``C:rel``, which names a poisoned
#: subfolder of the current folder) that Python would read against it.
USER_PYTHONPATHS = [
    pytest.param(None, id="pythonpath-unset"),
    pytest.param(";C:\\nonexistent", id="pythonpath-leading-empty-entry"),
    pytest.param("C:\\nonexistent;", id="pythonpath-trailing-empty-entry"),
    pytest.param(".", id="pythonpath-dot"),
    pytest.param("C:rel", id="pythonpath-drive-relative"),
    pytest.param("\\rooted", id="pythonpath-rooted-no-drive"),
]

#: The subfolder of the poisoned folder that ``C:rel`` names.
RELATIVE_ENTRY = "rel"

# The engine stand-in imports click and json (both shadowed in the poisoned
# folder) and records sys.argv, the working directory, sys.path, the
# PYTHONPATH its child processes would get and whether
# APOTHEM_USER_PYTHONPATH (the shim's hand-over variable) is still set, one
# JSON object per line, in the file APOTHEM_TEST_RECORD names.
ENGINE_MAIN = (
    "import json, os, sys\n"
    "import click\n"
    "with open(os.environ['APOTHEM_TEST_RECORD'], 'a', encoding='utf-8') as f:\n"
    "    f.write(json.dumps({'argv': sys.argv, 'cwd': os.getcwd(),"
    " 'path': sys.path, 'pythonpath': os.environ.get('PYTHONPATH'),"
    " 'handover': 'APOTHEM_USER_PYTHONPATH' in os.environ}) + '\\n')\n"
)


def _marker_code(marker: Path) -> str:
    """Python source that writes MARKER when it runs."""
    return f"open({str(marker)!r}, 'w').write('ran')\n"


def _locator(marker: Path) -> str:
    """A find-python.ps1 that writes MARKER when dot-sourced and finds nothing,
    so the installer falls back to its inline probe."""
    return (
        f"Set-Content -LiteralPath '{marker}' -Value 'ran'\n"
        "function Find-RealPython { param([int]$MinMajor, [int]$MinMinor) return $null }\n"
    )


def _apothem_tree(root: Path, locator_marker: Path, *, engine: bool) -> Path:
    """Lay out an Apothem-shaped source tree at ROOT whose locator writes
    LOCATOR_MARKER; with ENGINE, its apothem package records each run."""
    package = root / "src" / "apothem"
    (package / "hooks" / "lib").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.0.0"\n', encoding="utf-8"
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    if engine:
        (package / "__main__.py").write_text(ENGINE_MAIN, encoding="utf-8")
    (package / "hooks" / "lib" / "find-python.ps1").write_text(
        _locator(locator_marker), encoding="ascii"
    )
    return root


def _poison(folder: Path, marks: Path) -> Path:
    """Fill FOLDER with modules that shadow click, rich, json, platform, pip
    and apothem, plus a sitecustomize.py and usercustomize.py (which run only
    when the folder is on sys.path at startup); each writes a marker into
    MARKS when imported. Its RELATIVE_ENTRY subfolder gets the same
    single-file modules, for a ``C:rel`` PYTHONPATH entry."""
    folder.mkdir(parents=True, exist_ok=True)
    marks.mkdir(parents=True, exist_ok=True)
    nested = folder / RELATIVE_ENTRY
    nested.mkdir()
    for name in ("click", "json", "sitecustomize", "usercustomize"):
        (nested / f"{name}.py").write_text(
            _marker_code(marks / f"{RELATIVE_ENTRY}-{name}"), encoding="utf-8"
        )
    for name in (
        "click",
        "json",
        "platform",
        "sitecustomize",
        "usercustomize",
    ):
        (folder / f"{name}.py").write_text(_marker_code(marks / name), encoding="utf-8")
    for name in ("apothem", "pip", "rich"):
        package = folder / name
        package.mkdir()
        (package / "__init__.py").write_text(
            _marker_code(marks / name), encoding="utf-8"
        )
        (package / "__main__.py").write_text(
            _marker_code(marks / f"{name}-main"), encoding="utf-8"
        )
    return folder


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    """An isolated environment: own HOME and temp folder, the fixture
    repository as the remote, a stub gpg that reports a good maintainer
    signature, and an existing profile. The scripts clear GIT_CONFIG_GLOBAL,
    so the stub gpg is named in HOME/.gitconfig, where git then looks; the
    variable names the same text, for a script that does not clear it."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    temp = tmp_path / "temp"
    temp.mkdir(exist_ok=True)
    profile = tmp_path / "profile.yaml"
    profile.write_text("identity: {}\n", encoding="utf-8")
    env = {
        key: value
        for key, value in hermetic_git_env().items()
        if not key.upper().startswith("APOTHEM_")
        and key.upper() not in {"PYTHONPATH", "PYTHONSAFEPATH"}
    }
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "TMPDIR": str(temp),
            "TEMP": str(temp),
            "TMP": str(temp),
            "APOTHEM_REF": TAG,
            "APOTHEM_REPO": str(tmp_path / "fixture-repo"),
            "APOTHEM_HOME": str(tmp_path / "apothem-home"),
            "APOTHEM_VERIFY": "signature",
            "APOTHEM_PROFILE": str(profile),
            "APOTHEM_BIN_DIR": str(tmp_path / "bin"),
            "APOTHEM_TEST_RECORD": str(tmp_path / "engine-runs.jsonl"),
            "PIP_NO_INDEX": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "XDG_CONFIG_HOME": str(home / ".config"),
        }
    )
    stub_config = write_stub_gpg(
        tmp_path / "stub-gpg", good_signature_status(MAINTAINER_FINGERPRINT)
    )
    (home / ".gitconfig").write_bytes(stub_config.read_bytes())
    env["GIT_CONFIG_GLOBAL"] = str(stub_config)
    env.update(extra)
    return env


def _pwsh(
    args: list[str], cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    assert _PWSH is not None
    return subprocess.run(
        [_PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", *args],
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _run_by_path(
    script: Path, cwd: Path, env: dict[str, str], *flags: str
) -> subprocess.CompletedProcess[str]:
    return _pwsh(["-File", str(script), *flags], cwd, env)


def _run_piped(
    script: Path, cwd: Path, env: dict[str, str], *, how: str
) -> subprocess.CompletedProcess[str]:
    """Run SCRIPT's text the way the one-liner does: piped into
    Invoke-Expression, or (to pass -DryRun -Yes) as a script block made from
    the text. Neither has a script file, so $PSCommandPath is empty. Prints
    PYTHONSAFEPATH afterwards to show the run left the session unchanged."""
    env = {**env, "APOTHEM_TEST_SCRIPT": str(script)}
    text = "Get-Content -Raw -LiteralPath $env:APOTHEM_TEST_SCRIPT"
    if how == "iex":
        command = f"{text} | Invoke-Expression"
    else:
        command = f"& ([scriptblock]::Create(({text}))) -DryRun -Yes"
    command += '; "SAFEPATH=[$env:PYTHONSAFEPATH]"'
    return _pwsh(["-Command", command], cwd, env)


def _plain(result: subprocess.CompletedProcess[str]) -> str:
    """The run's output as single-spaced words, as a reader sees them."""
    words = _ANSI_ESCAPE.sub("", result.stdout + result.stderr).split()
    return " ".join(word for word in words if word != "|")


def _squashed(text: str) -> str:
    """TEXT without whitespace (Windows PowerShell 5.1 wraps long paths)."""
    return re.sub(r"\s+", "", text)


def _engine_runs(env: dict[str, str]) -> list[tuple[list[str], str]]:
    """Each engine run as (sys.argv, working directory)."""
    record = Path(env["APOTHEM_TEST_RECORD"])
    if not record.is_file():
        return []
    runs = []
    for line in record.read_text(encoding="utf-8").splitlines():
        run = json.loads(line)
        runs.append(([str(arg) for arg in run["argv"]], str(run["cwd"])))
    return runs


def _engine_paths(env: dict[str, str]) -> list[list[str]]:
    """The sys.path each engine run saw."""
    record = Path(env["APOTHEM_TEST_RECORD"])
    if not record.is_file():
        return []
    return [
        [str(entry) for entry in json.loads(line)["path"]]
        for line in record.read_text(encoding="utf-8").splitlines()
    ]


def _assert_cwd_off_path(env: dict[str, str], cwd: Path) -> None:
    """No engine run had '', the current folder or its RELATIVE_ENTRY
    subfolder on sys.path."""
    folders = {os.path.normcase(str(cwd)), os.path.normcase(str(cwd / RELATIVE_ENTRY))}
    for path in _engine_paths(env):
        assert "" not in path, path
        assert not folders & {os.path.normcase(entry) for entry in path}, path


#: The one full-path rule every launcher applies on Windows: a drive letter
#: and a separator, or two separators (a share).
FULL_PATH = re.compile(r"([A-Za-z]:[\\/]|[\\/]{2})")


def _full_path_entries(value: str | None, engine: list[str] | None = None) -> list[str]:
    """The entries of a user PYTHONPATH that are full paths, once each and
    without the ENGINE paths: the ones every launcher passes on to the
    engine."""
    entries = (value or "").split(os.pathsep)
    if sys.platform == "win32":
        kept = [entry for entry in entries if FULL_PATH.match(entry)]
    else:
        # PowerShell off Windows keeps only POSIX full paths.
        kept = [entry for entry in entries if entry.startswith("/")]
    return [entry for entry in dict.fromkeys(kept) if entry not in (engine or [])]


def _assert_full_path_entries_reach_the_engine(
    env: dict[str, str], value: str | None
) -> None:
    """Each engine run has the full-path entries of VALUE right after the two
    engine paths, on sys.path and in the PYTHONPATH its child processes get,
    and nothing else of VALUE."""
    for line in _records(env):
        run = json.loads(line)
        path = [str(entry) for entry in run["path"]]
        wanted = _full_path_entries(value, path[:2])
        assert path[2 : 2 + len(wanted)] == wanted, (wanted, path)
        assert run["pythonpath"] == os.pathsep.join(path[:2] + wanted), run


def _with_pythonpath(env: dict[str, str], value: str | None) -> dict[str, str]:
    """ENV with the caller's PYTHONPATH set to VALUE (None: unset)."""
    return env if value is None else {**env, "PYTHONPATH": value}


def _ran(marks: Path) -> list[str]:
    return sorted(p.name for p in marks.iterdir()) if marks.is_dir() else []


def _run_cmd(
    command: list[str], cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


# HIGH: a piped run never uses a tree in the current folder or its parents.


@pytest.mark.parametrize("how", ["iex", "scriptblock"])
@pytest.mark.parametrize(
    "where",
    [
        # The old locator lookup read <cwd>\..\..\src\apothem\hooks\lib.
        pytest.param(("scripts", "installer"), id="cwd-inside-planted-tree"),
        # The old walk climbed every parent folder.
        pytest.param(("a", "b", "c"), id="cwd-below-planted-tree"),
    ],
)
def test_a_piped_run_ignores_a_tree_planted_around_the_current_folder(
    tmp_path: Path, how: str, where: tuple[str, ...]
) -> None:
    make_tagged_repo(tmp_path, TAG)
    marks = tmp_path / "marks"
    marks.mkdir()
    planted = _apothem_tree(
        tmp_path / "planted", marks / "planted-locator", engine=False
    )
    (planted / "src" / "apothem" / "__main__.py").write_text(
        _marker_code(marks / "planted-engine"), encoding="utf-8"
    )
    cwd = planted.joinpath(*where)
    cwd.mkdir(parents=True)
    env = _env(tmp_path)

    result = _run_piped(INSTALLER, cwd, env, how=how)

    out = _plain(result)
    assert _ran(marks) == [], out
    assert LOCAL_CHECKOUT_MARKER not in out
    assert CLONING_MARKER in out, out
    assert TAG_OK_MARKER in out, out


def test_a_run_by_path_from_its_own_checkout_uses_that_checkout(
    tmp_path: Path,
) -> None:
    marks = tmp_path / "marks"
    marks.mkdir()
    checkout = _apothem_tree(tmp_path / "checkout", marks / "own-locator", engine=True)
    script = checkout / "scripts" / "installer" / "install.ps1"
    script.parent.mkdir(parents=True)
    shutil.copy2(INSTALLER, script)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    env = _env(tmp_path)

    result = _run_by_path(script, elsewhere, env, "-DryRun", "-Yes")

    out = _plain(result)
    assert result.returncode == 0, out
    assert _squashed(f"{LOCAL_CHECKOUT_MARKER}: {checkout}") in _squashed(out)
    assert _ran(marks) == ["own-locator"]
    assert CLONING_MARKER not in out
    runs = _engine_runs(env)
    assert [argv[1:] for argv, _ in runs] == [
        [
            "install",
            "--harness",
            HARNESS,
            "--profile",
            env["APOTHEM_PROFILE"],
            "--dry-run",
            "--yes",
        ]
    ]


def test_a_copy_outside_a_checkout_does_not_adopt_the_tree_around_it(
    tmp_path: Path,
) -> None:
    make_tagged_repo(tmp_path, TAG)
    marks = tmp_path / "marks"
    marks.mkdir()
    planted = _apothem_tree(
        tmp_path / "planted", marks / "planted-locator", engine=False
    )
    script = planted / "downloads" / "install.ps1"
    script.parent.mkdir()
    shutil.copy2(INSTALLER, script)
    env = _env(tmp_path)

    result = _run_by_path(script, script.parent, env, "-DryRun", "-Yes")

    out = _plain(result)
    assert _ran(marks) == [], out
    assert LOCAL_CHECKOUT_MARKER not in out
    assert TAG_OK_MARKER in out, out


# MEDIUM: no Python start imports click, rich or apothem from the current
# folder; APOTHEM_SOURCE still works from a piped run.


def test_a_piped_run_with_apothem_source_uses_it_and_not_the_current_folder(
    tmp_path: Path,
) -> None:
    marks = tmp_path / "marks"
    source = _apothem_tree(tmp_path / "source", marks / "source-locator", engine=True)
    cwd = _poison(tmp_path / "work", marks)
    env = _env(tmp_path, APOTHEM_SOURCE=str(source))

    result = _run_piped(INSTALLER, cwd, env, how="scriptblock")

    out = _plain(result)
    assert result.returncode == 0, out
    assert _squashed(f"{EXPLICIT_SOURCE_MARKER}: {source}") in _squashed(out)
    assert _ran(marks) == ["source-locator"]
    assert "SAFEPATH=[]" in out
    runs = _engine_runs(env)
    assert len(runs) == 1, out
    assert runs[0][1] == str(cwd)
    assert runs[0][0][1:] == [
        "install",
        "--harness",
        HARNESS,
        "--profile",
        env["APOTHEM_PROFILE"],
        "--dry-run",
        "--yes",
    ]


@requires_windows
@pytest.mark.parametrize("user_pythonpath", USER_PYTHONPATHS)
def test_the_install_its_shim_and_the_uninstall_do_not_import_from_the_current_folder(
    tmp_path: Path, user_pythonpath: str | None
) -> None:
    marks = tmp_path / "marks"
    source = _apothem_tree(tmp_path / "source", tmp_path / "locator-ran", engine=True)
    cwd = _poison(tmp_path / "work", marks)
    env = _with_pythonpath(_env(tmp_path, APOTHEM_SOURCE=str(source)), user_pythonpath)
    shim = Path(env["APOTHEM_BIN_DIR"]) / "apothem.cmd"

    install = _run_by_path(INSTALLER, cwd, env, "-Yes")
    shim_run = _run_cmd([str(shim), "doctor", "two words", "--flag=1"], cwd, env)
    uninstall = _run_by_path(UNINSTALLER, cwd, env, "-Yes")

    assert install.returncode == 0, _plain(install)
    assert shim_run.returncode == 0, shim_run.stdout + shim_run.stderr
    assert uninstall.returncode == 0, _plain(uninstall)
    assert _ran(marks) == []
    _assert_cwd_off_path(env, cwd)
    runs = _engine_runs(env)
    assert [argv[1:] for argv, _ in runs] == [
        ["install", "--harness", HARNESS, "--profile", env["APOTHEM_PROFILE"], "--yes"],
        ["verify", "--harness", HARNESS],
        ["doctor", "two words", "--flag=1"],
        ["uninstall", "--harness", HARNESS, "--yes"],
    ]
    assert all(run_cwd == str(cwd) for _, run_cwd in runs)
    assert all(
        Path(argv[0]) == source / "src" / "apothem" / "__main__.py" for argv, _ in runs
    )
    # The caller's full-path entries still reach the engine, and the shim's
    # hand-over variable does not.
    _assert_full_path_entries_reach_the_engine(env, user_pythonpath)
    assert not any(json.loads(line)["handover"] for line in _records(env))
    assert not shim.exists(), "uninstall.ps1 left the shim install.ps1 wrote"


def _records(env: dict[str, str]) -> list[str]:
    record = Path(env["APOTHEM_TEST_RECORD"])
    return record.read_text(encoding="utf-8").splitlines() if record.is_file() else []


#: User PYTHONPATH values a batch file handles badly: runs of empty entries
#: longer than a fixed number of ``;;`` -> ``;`` passes can collapse, and
#: entries holding characters cmd.exe treats specially.
AWKWARD_PYTHONPATHS = [
    pytest.param(";" * 40, id="forty-semicolons"),
    pytest.param(";" * 40 + "C:\\abs-one" + ";" * 40, id="full-path-in-semicolons"),
    pytest.param(
        "C:\\a&b;C:\\pct%OS%x;C:\\bang!x!;C:\\caret^y;C:\\par(en)s;"
        "C:\\with space;.;;C:rel",
        id="special-characters",
    ),
    pytest.param("C:\\bang!x!;C:\\b!OS!c;C:\\a!b", id="exclamation-marks"),
    pytest.param(
        "\\rooted;/rooted;C:/forward;\\\\?\\C:\\share-form;C:\\twice;C:\\twice",
        id="rooted-forward-share-and-repeated",
    ),
    pytest.param("C:\\x & echo INJECTED", id="ampersand-command"),
]


@requires_windows
def test_the_shim_passes_on_only_the_full_path_entries_of_pythonpath(
    tmp_path: Path,
) -> None:
    """The apothem.cmd shim sets PYTHONPATH to the engine paths only; its
    program puts the caller's full-path entries right after them, as
    written, on sys.path and in the PYTHONPATH child processes get, and
    leaves out empty and relative entries, however many there are and
    whatever characters they hold. A `!` passes through even when cmd.exe
    runs with delayed expansion on (cmd /v:on)."""
    marks = tmp_path / "marks"
    source = _apothem_tree(tmp_path / "source", tmp_path / "locator-ran", engine=True)
    cwd = _poison(tmp_path / "work", marks)
    env = _env(tmp_path, APOTHEM_SOURCE=str(source), APOTHEM_SKIP_VERIFY="1")
    install = _run_by_path(INSTALLER, cwd, env, "-Yes")
    assert install.returncode == 0, _plain(install)
    shim = Path(env["APOTHEM_BIN_DIR"]) / "apothem.cmd"
    engine_paths = [str(source / "src" / "apothem" / "_vendor"), str(source / "src")]

    for param in AWKWARD_PYTHONPATHS:
        (value,) = param.values
        for prefix in ([], ["cmd", "/v:on", "/c"]):
            case = (param.id, prefix)
            Path(env["APOTHEM_TEST_RECORD"]).unlink(missing_ok=True)

            run = _run_cmd(
                [*prefix, str(shim), "doctor", "a!b!c"],
                cwd,
                {**env, "PYTHONPATH": str(value)},
            )

            assert run.returncode == 0, (case, run.stdout + run.stderr)
            assert "INJECTED" not in run.stdout, case
            assert _ran(marks) == [], case
            _assert_cwd_off_path(env, cwd)
            (record,) = [json.loads(line) for line in _records(env)]
            assert record["argv"][1:] == ["doctor", "a!b!c"], case
            path = record["path"]
            wanted = _full_path_entries(str(value), engine_paths)
            assert path[:2] == engine_paths, (case, path)
            assert path[2 : 2 + len(wanted)] == wanted, (case, path)
            assert record["pythonpath"] == ";".join(engine_paths + wanted), case
            assert not record["handover"], case


@requires_windows
def test_a_relative_apothem_home_gives_the_shim_full_engine_paths(
    tmp_path: Path,
) -> None:
    """A relative APOTHEM_HOME is resolved once, so the shim install.ps1
    writes names the engine by full paths and still works from another
    folder, and uninstall.ps1 runs the engine from the same full paths."""
    repo, _ = make_tagged_repo(tmp_path, TAG)
    _retag_with_engine(repo, tmp_path)
    marks = tmp_path / "marks"
    elsewhere = _poison(tmp_path / "elsewhere", marks)
    env = _env(tmp_path, APOTHEM_HOME="rel-home")
    home = tmp_path / "rel-home"

    # Piped, so the run fetches the fixture release into APOTHEM_HOME.
    install = _run_piped(INSTALLER, tmp_path, env, how="iex")
    shim = Path(env["APOTHEM_BIN_DIR"]) / "apothem.cmd"
    assert install.returncode == 0, _plain(install)
    shim_text = shim.read_text(encoding="ascii")
    shim_run = _run_cmd([str(shim), "doctor"], elsewhere, env)
    uninstall = _run_by_path(UNINSTALLER, tmp_path, env, "-Yes")

    assert f'set "PYTHONPATH={home}' in shim_text, shim_text
    assert shim_run.returncode == 0, shim_run.stdout + shim_run.stderr
    assert uninstall.returncode == 0, _plain(uninstall)
    assert _ran(marks) == []
    engine_paths = [str(home / "src" / "apothem" / "_vendor"), str(home / "src")]
    runs = _engine_paths(env)
    assert len(runs) == 4, runs
    assert all(path[:2] == engine_paths for path in runs), runs


def _retag_with_engine(repo: Path, root: Path) -> None:
    """Add the recording engine stand-in to REPO and move its TAG (a tag
    object with a signature block the stub gpg accepts) to that commit."""
    git_env = hermetic_git_env()

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            env=git_env,
            capture_output=True,
            text=True,
        ).stdout.strip()

    (repo / "src" / "apothem" / "__main__.py").write_text(ENGINE_MAIN, encoding="utf-8")
    git("add", "-A")
    git("commit", "--quiet", "-m", "engine stand-in")
    commit = git("rev-parse", "HEAD")
    tag_file = root / f"{TAG}-engine.tag"
    old = git("cat-file", "tag", f"refs/tags/{TAG}")
    tag_file.write_text(
        re.sub(r"\Aobject [0-9a-f]+", f"object {commit}", old) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tag_sha = git("hash-object", "-t", "tag", "-w", str(tag_file))
    git("update-ref", f"refs/tags/{TAG}", tag_sha)


@requires_windows
@pytest.mark.parametrize(
    ("body", "removed"),
    [
        pytest.param(
            '@echo off\r\nsetlocal\r\nset "PYTHONPATH=C:\\a;%PYTHONPATH%"\r\n'
            '"C:\\Python\\python.exe" -m apothem %*\r\n',
            True,
            id="shim-from-1.5.0",
        ),
        pytest.param(
            "@echo off\r\nrem my own apothem command\r\nC:\\tools\\apothem.exe %*\r\n",
            False,
            id="operator-owned-command",
        ),
    ],
)
def test_the_uninstaller_removes_an_older_shim_but_not_an_operator_command(
    tmp_path: Path, body: str, removed: bool
) -> None:
    source = _apothem_tree(tmp_path / "source", tmp_path / "locator-ran", engine=True)
    env = _env(tmp_path, APOTHEM_SOURCE=str(source))
    shim = Path(env["APOTHEM_BIN_DIR"]) / "apothem.cmd"
    shim.parent.mkdir()
    shim.write_bytes(body.encode("ascii"))

    result = _run_by_path(UNINSTALLER, tmp_path, env, "-Yes")

    assert result.returncode == 0, _plain(result)
    assert shim.exists() is not removed


@pytest.mark.parametrize("user_pythonpath", USER_PYTHONPATHS)
def test_the_updater_does_not_import_from_the_current_folder(
    tmp_path: Path, user_pythonpath: str | None
) -> None:
    marks = tmp_path / "marks"
    source = _apothem_tree(tmp_path / "source", tmp_path / "locator-ran", engine=True)
    cwd = _poison(tmp_path / "work", marks)
    env = _with_pythonpath(_env(tmp_path, APOTHEM_SOURCE=str(source)), user_pythonpath)

    result = _run_by_path(UPDATER, cwd, env)

    out = _plain(result)
    assert result.returncode == 0, out
    assert _ran(marks) == []
    _assert_cwd_off_path(env, cwd)
    _assert_full_path_entries_reach_the_engine(env, user_pythonpath)
    runs = _engine_runs(env)
    assert len(runs) == 1, out
    assert runs[0][1] == str(cwd)
    assert runs[0][0][1:] == [
        "update",
        "--harness",
        HARNESS,
        "--profile",
        env["APOTHEM_PROFILE"],
    ]


def _pipless_python(tmp_path: Path) -> Path:
    """A virtual environment without pip, click or rich; its interpreter."""
    venv = tmp_path / "pipless"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(venv)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    if sys.platform != "win32":
        return venv / "bin" / "python"
    python = venv / "Scripts" / "python.exe"
    # The updaters probe python3 before python.
    shutil.copy2(python, python.with_name("python3.exe"))
    return python


@pytest.mark.parametrize("user_pythonpath", USER_PYTHONPATHS)
@pytest.mark.parametrize("script", [INSTALLER, UPDATER], ids=lambda p: p.name)
def test_the_dependency_install_does_not_run_pip_from_the_current_folder(
    tmp_path: Path, script: Path, user_pythonpath: str | None
) -> None:
    marks = tmp_path / "marks"
    python = _pipless_python(tmp_path)
    source = _apothem_tree(tmp_path / "source", tmp_path / "locator-ran", engine=True)
    # The source's locator picks the interpreter that lacks click and rich,
    # so the run offers to install them with pip.
    locator = source / "src" / "apothem" / "hooks" / "lib" / "find-python.ps1"
    locator.write_text(
        "function Find-RealPython { param([int]$MinMajor, [int]$MinMinor) "
        f"return '{python}' }}\n",
        encoding="ascii",
    )
    cwd = _poison(tmp_path / "work", marks)
    env = _with_pythonpath(
        _env(tmp_path, APOTHEM_SOURCE=str(source), APOTHEM_AUTO_INSTALL_DEPS="1"),
        user_pythonpath,
    )
    if script == UPDATER:
        # update.ps1 has no locator: its interpreter probe takes the first
        # python on PATH, so the pip-less one goes first.
        env["PATH"] = f"{python.parent}{os.pathsep}{env['PATH']}"
    flags = ["-DryRun"] if script == INSTALLER else []

    result = _run_by_path(script, cwd, env, *flags)

    out = _plain(result)
    assert "pip is unavailable" in out, out
    assert _ran(marks) == [], out


# R7: git commands that work on no repository of their own never read a
# repository in the current folder, whose config could run a command.


def _plant_git_repository(folder: Path, marker: Path, repo: str) -> None:
    """Make FOLDER a repository whose config rewrites REPO to an ext:: command
    that writes MARKER."""
    folder.mkdir(parents=True, exist_ok=True)
    env = hermetic_git_env()
    for args in (
        ["init", "--quiet", str(folder)],
        ["-C", str(folder), "config", "protocol.ext.allow", "always"],
        [
            "-C",
            str(folder),
            "config",
            f"url.ext::cmd /c type nul > {marker} & rem .insteadOf",
            repo,
        ],
    ):
        subprocess.run(["git", *args], check=True, env=env, capture_output=True)


@requires_windows
def test_the_installer_never_reads_a_git_repository_in_the_current_folder(
    tmp_path: Path,
) -> None:
    """Resolving the latest tag (ls-remote) ignores an ext:: rewrite in the
    current folder's repository."""
    make_tagged_repo(tmp_path, TAG)
    marker = tmp_path / "ext-ran"
    env = _env(tmp_path)
    del env["APOTHEM_REF"]
    cwd = tmp_path / "work"
    _plant_git_repository(cwd, marker, env["APOTHEM_REPO"])

    result = _run_piped(INSTALLER, cwd, env, how="scriptblock")

    out = _plain(result)
    assert not marker.exists(), out
    assert TAG_OK_MARKER in out, out


@requires_windows
def test_the_signature_check_ignores_a_gpg_program_set_in_the_current_folder(
    tmp_path: Path,
) -> None:
    """The gpg check reads gpg.program and gpg.openpgp.program from git's
    configuration. A repository in the current folder that sets them, here to
    a program that does not exist, is not read: the check uses the caller's
    own configuration (the stub gpg) and the signed tag passes."""
    make_tagged_repo(tmp_path, TAG)
    env = _env(tmp_path)
    cwd = tmp_path / "work"
    cwd.mkdir()
    missing = tmp_path / "no-such-gpg.exe"
    git_env = hermetic_git_env()
    subprocess.run(["git", "init", "--quiet", str(cwd)], check=True, env=git_env)
    for key in ("gpg.program", "gpg.openpgp.program"):
        subprocess.run(
            ["git", "-C", str(cwd), "config", key, str(missing)],
            check=True,
            env=git_env,
        )

    result = _run_piped(INSTALLER, cwd, env, how="scriptblock")

    out = _plain(result)
    assert "gpg not found" not in out, out
    assert TAG_OK_MARKER in out, out


@requires_windows
def test_the_updater_never_reads_a_git_repository_in_the_current_folder(
    tmp_path: Path,
) -> None:
    repo, _ = make_tagged_repo(tmp_path, TAG)
    marker = tmp_path / "ext-ran"
    env = _env(tmp_path)
    del env["APOTHEM_REF"]
    subprocess.run(
        ["git", "clone", "--quiet", str(repo), env["APOTHEM_HOME"]],
        check=True,
        env=hermetic_git_env(),
        capture_output=True,
    )
    cwd = tmp_path / "work"
    _plant_git_repository(cwd, marker, env["APOTHEM_REPO"])

    result = _run_by_path(UPDATER, cwd, env)

    out = _plain(result)
    assert not marker.exists(), out
    assert f"Latest release tag: {TAG}" in out, out


# R9: a run by path through a junction is not taken as a local checkout.


@requires_windows
def test_a_run_through_a_junction_is_not_taken_as_a_local_checkout(
    tmp_path: Path,
) -> None:
    make_tagged_repo(tmp_path, TAG)
    marks = tmp_path / "marks"
    marks.mkdir()
    checkout = _apothem_tree(tmp_path / "checkout", marks / "own-locator", engine=True)
    script = checkout / "scripts" / "installer" / "install.ps1"
    script.parent.mkdir(parents=True)
    shutil.copy2(INSTALLER, script)
    link = tmp_path / "link"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(checkout)],
        check=True,
        capture_output=True,
    )
    env = _env(tmp_path)

    result = _run_by_path(
        link / "scripts" / "installer" / "install.ps1", tmp_path, env, "-DryRun", "-Yes"
    )

    out = _plain(result)
    assert LOCAL_CHECKOUT_MARKER not in out, out
    assert "is a symbolic link or junction" in out, out
    assert _ran(marks) == [], out
    assert TAG_OK_MARKER in out, out


# The next-step banner prints commands that work when a path holds a quote.


def _run_banner_lines(
    tmp_path: Path, env: dict[str, str], lines: list[str]
) -> subprocess.CompletedProcess[str]:
    """Run LINES, copied from the banner, as a script of their own."""
    script = tmp_path / "from-the-banner.ps1"
    script.write_text("\n".join([*lines, "exit $LASTEXITCODE", ""]), encoding="utf-8")
    Path(env["APOTHEM_TEST_RECORD"]).unlink(missing_ok=True)
    return _run_by_path(script, tmp_path, env)


@requires_windows
def test_the_banner_prints_a_shim_folder_holding_a_quote_as_working_commands(
    tmp_path: Path,
) -> None:
    """With the shim's folder off PATH, the banner's PATH line and its
    full-path command still run the shim when the folder name holds a single
    quote (each printed path is a single-quoted string, its quotes doubled)."""
    source = _apothem_tree(tmp_path / "source", tmp_path / "locator-ran", engine=True)
    bin_dir = tmp_path / "it's bin"
    env = _env(
        tmp_path,
        APOTHEM_SOURCE=str(source),
        APOTHEM_SKIP_VERIFY="1",
        APOTHEM_BIN_DIR=str(bin_dir),
    )
    install = _run_by_path(INSTALLER, tmp_path, env, "-Yes")
    assert install.returncode == 0, _plain(install)
    lines = [line.strip() for line in install.stdout.splitlines()]
    path_line = next(line for line in lines if line.startswith("$env:Path = "))
    header = lines.index("Until then, run the apothem command by its full path:")
    run_line = lines[header + 1]
    assert "it''s bin" in path_line, path_line
    assert run_line.startswith("& '"), run_line
    assert run_line.endswith(" <command>"), run_line

    result = _run_banner_lines(
        tmp_path,
        env,
        [path_line, "apothem doctor", run_line.replace("<command>", "verify")],
    )

    assert result.returncode == 0, _plain(result)
    assert [argv[1:] for argv, _ in _engine_runs(env)] == [["doctor"], ["verify"]]


@requires_windows
def test_the_banner_without_a_shim_prints_a_working_command_for_a_quoted_path(
    tmp_path: Path,
) -> None:
    """With no shim placed, the self-contained command the banner prints
    still runs the engine when the engine's paths hold a single quote."""
    source = _apothem_tree(
        tmp_path / "it's source", tmp_path / "locator-ran", engine=True
    )
    blocker = tmp_path / "a-file"
    blocker.write_text("", encoding="utf-8")
    env = _env(
        tmp_path,
        APOTHEM_SOURCE=str(source),
        APOTHEM_SKIP_VERIFY="1",
        APOTHEM_BIN_DIR=str(blocker / "bin"),
    )
    install = _run_by_path(INSTALLER, tmp_path, env, "-Yes")
    assert install.returncode == 0, _plain(install)
    assert "Could not place an apothem shim" in _plain(install)
    lines = [line.strip() for line in install.stdout.splitlines()]
    header = next(
        index
        for index, line in enumerate(lines)
        if line.endswith("the current folder is kept off sys.path):")
    )
    run_line = lines[header + 1]
    assert "it''s source" in run_line, run_line

    result = _run_banner_lines(
        tmp_path,
        env,
        [run_line.replace("<command>", "doctor"), '"SAFEPATH=[$env:PYTHONSAFEPATH]"'],
    )

    assert result.returncode == 0, _plain(result)
    assert [argv[1:] for argv, _ in _engine_runs(env)] == [["doctor"]]
    assert all(
        Path(argv[0]) == source / "src" / "apothem" / "__main__.py"
        for argv, _ in _engine_runs(env)
    )
    assert "SAFEPATH=[]" in result.stdout, result.stdout


# APOTHEM_HOME must name a file-system folder path.


@requires_windows
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("HKCU:\\Software\\apothem-test-home", id="registry-path"),
        pytest.param("nosuchdrive:\\apothem", id="unknown-drive"),
    ],
)
@pytest.mark.parametrize(
    ("script", "flags"),
    [
        pytest.param(INSTALLER, ("-DryRun", "-Yes"), id="install"),
        pytest.param(UPDATER, (), id="update"),
        pytest.param(UNINSTALLER, ("-Yes",), id="uninstall"),
    ],
)
def test_an_apothem_home_that_names_no_folder_path_stops_the_run(
    tmp_path: Path, script: Path, flags: tuple[str, ...], value: str
) -> None:
    env = _env(tmp_path, APOTHEM_HOME=value)

    result = _run_by_path(script, tmp_path, env, *flags)

    out = _plain(result)
    assert result.returncode != 0, out
    assert _squashed(f"APOTHEM_HOME is not a usable folder path: {value}") in _squashed(
        out
    ), out
    assert _engine_runs(env) == []


@requires_windows
def test_a_relative_apothem_home_is_read_against_the_file_system_folder(
    tmp_path: Path,
) -> None:
    """A session sitting in a registry location still reads a relative
    APOTHEM_HOME against its current file-system folder."""
    env = {
        **_env(tmp_path, APOTHEM_HOME="rel-home"),
        "APOTHEM_TEST_SCRIPT": str(UNINSTALLER),
    }

    result = _pwsh(
        ["-Command", "Set-Location HKCU:\\; & $env:APOTHEM_TEST_SCRIPT -Yes"],
        tmp_path,
        env,
    )

    out = _plain(result)
    assert _squashed(f"No apothem source found at {tmp_path / 'rel-home'}") in (
        _squashed(out)
    ), out
    assert "HKEY_CURRENT_USER" not in out, out


# REUSE-IgnoreEnd
