# SPDX-License-Identifier: MIT

"""Installs and updates of a release whose paths pass Windows' 260-character limit.

The installers check a release out in a staging folder: beside APOTHEM_HOME
(``.apothem-clone.<id>/apothem``) for an install, and in the temporary folder
for a dry run. The folder adds about 55 characters to every path in the tree
(install.sh's shorter name adds about 30), and Apothem v1.5.0's deepest path
is 170 characters long, so on Windows a home folder of ordinary length puts
paths past the limit. Git for Windows writes and reads such paths only with
``core.longpaths`` set, and Windows PowerShell 5.1 removes them only through
the extended-length path form (``\\\\?\\C:\\...``) when long paths are off for
the machine.

Each test builds a fixture repository whose release tag holds one file at a
path chosen from the test's own folder, runs the real script against it, and
keeps HOME, USERPROFILE, APOTHEM_HOME, the XDG folders and the temporary
folder under the test's folder: install.ps1 and update.ps1 under PowerShell 7
and Windows PowerShell 5.1, install.sh under Git Bash. For an install the
file's path passes the limit only in the staging folder, and stays below it
at APOTHEM_HOME, so the test can read and remove it without long paths; an
update writes the file at APOTHEM_HOME itself, past the limit. The fixture
repository holds the long file in its index only, so building it needs no
long paths either.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests._shared.git_env import hermetic_git_env
from tests._shared.python_shim import write_python_shim
from tests._shared.release_fixture import (
    MAINTAINER_FINGERPRINT,
    git,
    good_signature_status,
    make_tagged_repo,
    repoint_tag,
    write_stub_gpg,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts" / "installer"
TAG = "v9.9.9"
OLD_TAG = "v9.9.8"
#: Windows' path limit, which Git for Windows keeps to without core.longpaths.
MAX_PATH = 260
#: The long file's path at APOTHEM_HOME after an install: below MAX_PATH, so
#: the test reads and removes it with long paths off for the machine.
INSTALLED_LENGTH = 250
#: The long file's path at APOTHEM_HOME after an update: past MAX_PATH.
UPDATED_LENGTH = 290
#: Folder names in the long path (NTFS allows 255 characters).
SEGMENT = 50
#: APOTHEM_HOME's name. One letter leaves the most room between its path
#: and the staging folder's.
HOME_NAME = "h"
LONG_TEXT = "a file past the path limit once staged\n"
TAG_OK_MARKER = "carries a valid signature from the maintainer key"
READY_MARKER = "Source ready at"
UPDATED_MARKER = "Source updated at"
DRY_RUN_MARKER = "dry run, so"
NOT_SOURCE_MARKER = "Fetched tree is not an apothem source"
SWITCH_MARKER = "Switching the release-archive install at"
NOT_REMOVED_MARKER = "Could not remove the earlier source at"
TOO_LONG_MARKER = "Filename too long"
TIMEOUT_SECONDS = 300

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _git_bash() -> Path | None:
    """Git for Windows' bash.exe, found from git on PATH (never WSL's bash)."""
    found = shutil.which("git")
    if found is None:
        return None
    # git.exe lives in <Git>\cmd or <Git>\mingw64\bin; bash.exe in <Git>\bin.
    for root in Path(found).resolve().parents[:3]:
        bash = root / "bin" / "bash.exe"
        if bash.is_file():
            return bash
    return None


GIT_BASH = _git_bash() if sys.platform == "win32" else None

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="the 260-character path limit is Windows'"
)
requires_git_bash = pytest.mark.skipif(
    GIT_BASH is None, reason="needs Git for Windows' bash.exe"
)


def _powershells() -> list[object]:
    """PowerShell 7 and Windows PowerShell 5.1, each skipped when absent."""
    shells: list[object] = []
    for name, label in (("pwsh", "pwsh"), ("powershell", "windows-powershell")):
        found = shutil.which(name) if sys.platform == "win32" else None
        shells.append(
            pytest.param(
                found,
                id=label,
                marks=pytest.mark.skipif(found is None, reason=f"no {name} here"),
            )
        )
    return shells


POWERSHELLS = _powershells()


@pytest.fixture
def base(tmp_path: Path) -> Path:
    """The test's folder in its long form. Git works in the long form of a
    folder (an 8.3 name such as RUNNER~1 expands), so lengths count on it."""
    return Path(os.path.realpath(tmp_path))


def _long_path(length: int) -> str:
    """A relative POSIX path exactly LENGTH characters long: folders of
    SEGMENT characters, then a file whose name makes up the rest."""
    folders = (length - 10) // (SEGMENT + 1)
    if folders < 1:
        pytest.skip("the test folder's own path leaves no room for a long path")
    leaf = length - folders * (SEGMENT + 1)
    names = [f"{index:02d}".ljust(SEGMENT, "d") for index in range(folders)]
    path = "/".join([*names, "f" * (leaf - len(".txt")) + ".txt"])
    assert len(path) == length
    return path


def _path_at_home(base: Path, length: int) -> str:
    """The long path that puts the file LENGTH characters deep at APOTHEM_HOME."""
    return _long_path(length - len(str(base / HOME_NAME)) - 1)


def _tag_long_file(repo: Path, long_path: str, *, source: bool = True) -> str:
    """Commit a file at LONG_PATH from REPO's index alone, so the fixture's
    own work tree never holds it, tag the commit TAG and return it. SOURCE
    false also drops pyproject.toml, so the tagged tree is not an Apothem
    source."""
    text_file = repo.parent / "long-file.txt"
    text_file.write_text(LONG_TEXT, encoding="utf-8", newline="\n")
    blob = git(["hash-object", "-w", str(text_file)], repo).strip()
    git(["update-index", "--add", "--cacheinfo", f"100644,{blob},{long_path}"], repo)
    if not source:
        git(["rm", "--quiet", "--cached", "pyproject.toml"], repo)
    git(["commit", "--quiet", "-m", "a path past the limit once staged"], repo)
    repoint_tag(repo, TAG, TAG)
    # The fixture is served bare: git's upload-pack, which runs without the
    # scripts' -c options, would otherwise look for .gitattributes along the
    # long path in the fixture's own work tree and warn that it is too long.
    git(["config", "core.bare", "true"], repo)
    return git(["rev-parse", "HEAD"], repo).strip()


def _release(base: Path, long_path: str, *, source: bool = True) -> str:
    """The fixture repository at BASE/fixture-repo, TAG on a commit that
    holds LONG_PATH; return that commit."""
    repo, _ = make_tagged_repo(base, TAG)
    return _tag_long_file(repo, long_path, source=source)


def _clone_at_old_tag(base: Path, long_path: str) -> str:
    """A clone of the fixture at APOTHEM_HOME, checked out at OLD_TAG, and a
    newer commit in the fixture, tagged TAG, that adds LONG_PATH; return
    that commit."""
    repo, _ = make_tagged_repo(base, OLD_TAG)
    home = base / HOME_NAME
    git(["clone", "--quiet", str(repo), str(home)], base)
    git(["checkout", "--quiet", f"refs/tags/{OLD_TAG}"], home)
    return _tag_long_file(repo, long_path)


def _extended(path: Path) -> Path:
    """PATH in the extended-length form, which reaches past MAX_PATH with
    long paths off for the machine."""
    return Path("\\\\?\\" + str(path))


def _staged_length(base: Path, long_path: str, folder: str) -> int:
    """How long the file's path is in a staging FOLDER of BASE."""
    return len(str(base / folder / "apothem" / long_path))


def _env(base: Path) -> dict[str, str]:
    """The scripts' environment: every home, data and temporary folder under
    BASE, the fixture repository as the remote, the signature check on the
    clone path, and a stub gpg that replays a good maintainer signature."""
    home = base / "home"
    temp = base / "temp"
    for folder in (home, temp):
        folder.mkdir(exist_ok=True)
    env = {
        key: value
        for key, value in hermetic_git_env().items()
        if not key.upper().startswith("APOTHEM_")
        and key.upper() not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "PYTHONPATH"}
    }
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "TMPDIR": str(temp),
            "TEMP": str(temp),
            "TMP": str(temp),
            "APOTHEM_REF": TAG,
            "APOTHEM_REPO": str(base / "fixture-repo"),
            "APOTHEM_HOME": str(base / HOME_NAME),
            "APOTHEM_VERIFY": "signature",
            "APOTHEM_BIN_DIR": str(base / "bin"),
            # -Yes lets the installer pip-install a missing click or rich;
            # with no package index that fails instead of changing the host.
            "PIP_NO_INDEX": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "NO_COLOR": "1",
        }
    )
    status = good_signature_status(MAINTAINER_FINGERPRINT)
    env["GIT_CONFIG_GLOBAL"] = str(write_stub_gpg(base / "stub-gpg", status))
    return env


def _script_copy(base: Path, script: str) -> Path:
    """A copy of SCRIPT outside this checkout: install.ps1 and install.sh,
    run from their own place in a checkout, install that checkout instead
    of cloning."""
    folder = base / "script-under-test"
    folder.mkdir(exist_ok=True)
    copy = folder / script
    shutil.copy2(SCRIPTS / script, copy)
    return copy


def _run_powershell(
    shell: str, base: Path, script: str, *flags: str
) -> subprocess.CompletedProcess[str]:
    """Run a copy of SCRIPT (install.ps1 or update.ps1) under SHELL with FLAGS."""
    copy = _script_copy(base, script)
    return subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(copy), *flags],
        cwd=str(copy.parent),
        env=_env(base),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_SECONDS,
        check=False,
    )


def _posix(path: Path) -> str:
    """PATH as Git Bash spells it (/c/...)."""
    drive, rest = path.drive, path.as_posix()[len(path.drive) :]
    return f"/{drive[0].lower()}{rest}"


def _run_git_bash(
    base: Path, script: str, *flags: str
) -> subprocess.CompletedProcess[str]:
    """Run a copy of SCRIPT (install.sh) with sh under Git Bash, with FLAGS
    and the test's Python first on PATH."""
    copy = _script_copy(base, script)
    python_dir = base / "python-shim"
    python_dir.mkdir(exist_ok=True)
    write_python_shim(python_dir / "python3")
    home = base / "home"
    exports = {
        "HOME": _posix(home),
        "TMPDIR": _posix(base / "temp"),
        "XDG_CONFIG_HOME": _posix(home / ".config"),
        "XDG_DATA_HOME": _posix(home / ".local" / "share"),
        "XDG_STATE_HOME": _posix(home / ".local" / "state"),
        "APOTHEM_HOME": _posix(base / HOME_NAME),
        "APOTHEM_REPO": _posix(base / "fixture-repo"),
        "APOTHEM_BIN_DIR": _posix(base / "bin"),
    }
    lines = [f"export {name}={shlex.quote(value)}" for name, value in exports.items()]
    lines.append(f'export PATH={shlex.quote(_posix(python_dir))}:"$PATH"')
    lines.append(shlex.join(["sh", _posix(copy), *flags]))
    # A file, not `bash -c`: Windows' command-line quoting would apply to
    # the program's backslashes on the way to bash.exe.
    program = base / "program.sh"
    program.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    env = _env(base)
    assert GIT_BASH is not None
    return subprocess.run(
        [str(GIT_BASH), _posix(program)],
        cwd=str(copy.parent),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_SECONDS,
        check=False,
    )


def _squashed(text: str) -> str:
    """TEXT without colour codes, PowerShell's error gutter or whitespace:
    Windows PowerShell 5.1 wraps an error record at the console width, which
    can split a long path."""
    words = _ANSI_ESCAPE.sub("", text).split()
    return "".join(word for word in words if word != "|")


def _said(result: subprocess.CompletedProcess[str], marker: str) -> bool:
    """Whether the run printed MARKER, on either stream."""
    return _squashed(marker) in _squashed(result.stdout + result.stderr)


def _leftovers(base: Path) -> list[str]:
    """Any staging or scratch folder the script left behind."""
    temp = [
        p.name
        for p in (base / "temp").iterdir()
        if p.name.startswith(("apothem-", "tmp."))
    ]
    staged = [p.name for p in base.iterdir() if p.name.startswith(".apothem-")]
    return temp + staged


def _assert_installed(base: Path, commit: str, long_path: str) -> None:
    """APOTHEM_HOME is a clone at COMMIT whose tracked files, the long one
    among them, are all checked out."""
    home = base / HOME_NAME
    assert git(["rev-parse", "HEAD"], home).strip() == commit
    assert (home / long_path).read_text(encoding="utf-8") == LONG_TEXT
    assert git(["status", "--porcelain", "--untracked-files=no"], home) == ""


def _move_long_tree_out(base: Path, long_path: str) -> None:
    """Rename the long path's first folder at APOTHEM_HOME to a short name
    beside it, so pytest removes the tree with long paths off."""
    first = base / HOME_NAME / long_path.split("/", 1)[0]
    if first.exists():
        first.rename(base / "z")


# install.ps1 ----------------------------------------------------------------


@pytest.mark.parametrize("shell", POWERSHELLS)
def test_install_ps1_checks_out_a_release_past_the_path_limit(
    base: Path, shell: str
) -> None:
    """The clone in the staging folder beside APOTHEM_HOME is checked out
    with paths past the limit, moved into place, and its folder removed."""
    long_path = _path_at_home(base, INSTALLED_LENGTH)
    assert _staged_length(base, long_path, ".apothem-clone." + "0" * 32) > MAX_PATH
    commit = _release(base, long_path)

    result = _run_powershell(shell, base, "install.ps1", "-Yes")

    output = result.stdout + result.stderr
    assert _said(result, TAG_OK_MARKER), output
    assert not _said(result, TOO_LONG_MARKER), output
    assert _said(result, READY_MARKER), output
    _assert_installed(base, commit, long_path)
    assert _leftovers(base) == [], output


@pytest.mark.parametrize("shell", POWERSHELLS)
def test_install_ps1_dry_run_removes_its_scratch_clone_past_the_path_limit(
    base: Path, shell: str
) -> None:
    """A dry run checks the release out in the temporary folder, past the
    limit, previews from it, and removes it, leaving APOTHEM_HOME alone."""
    long_path = _path_at_home(base, INSTALLED_LENGTH)
    scratch = str(Path("temp") / ("apothem-" + "0" * 32))
    assert _staged_length(base, long_path, scratch) > MAX_PATH
    _release(base, long_path)

    result = _run_powershell(shell, base, "install.ps1", "-DryRun", "-Yes")

    output = result.stdout + result.stderr
    assert _said(result, TAG_OK_MARKER), output
    assert not _said(result, TOO_LONG_MARKER), output
    assert _said(result, DRY_RUN_MARKER), output
    assert not (base / HOME_NAME).exists(), output
    assert _leftovers(base) == [], output


@pytest.mark.parametrize("shell", POWERSHELLS)
def test_install_ps1_failed_run_removes_its_staging_clone_past_the_path_limit(
    base: Path, shell: str
) -> None:
    """A run that stops after the checkout (the tagged tree is not an
    Apothem source) removes the staging folder, long paths and all, and
    reports why it stopped."""
    long_path = _path_at_home(base, INSTALLED_LENGTH)
    _release(base, long_path, source=False)

    result = _run_powershell(shell, base, "install.ps1", "-Yes")

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert not _said(result, TOO_LONG_MARKER), output
    assert _said(result, NOT_SOURCE_MARKER), output
    assert not (base / HOME_NAME).exists(), output
    assert _leftovers(base) == [], output


@pytest.mark.parametrize("shell", POWERSHELLS)
def test_install_ps1_removes_the_earlier_tree_it_replaced_past_the_path_limit(
    base: Path, shell: str
) -> None:
    """Switching an archive install to a clone moves the earlier tree to a
    folder beside APOTHEM_HOME, where its paths pass the limit, and removes
    it there; the engine's data stays."""
    long_path = _path_at_home(base, INSTALLED_LENGTH)
    commit = _release(base, long_path)
    home = base / HOME_NAME
    (home / "src" / "apothem").mkdir(parents=True)
    (home / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (home / long_path).parent.mkdir(parents=True)
    (home / long_path).write_text("from the earlier install\n", encoding="utf-8")
    (home / "state").mkdir()
    (home / "state" / "ledger.json").write_text("{}\n", encoding="utf-8")

    result = _run_powershell(shell, base, "install.ps1", "-Yes")

    output = result.stdout + result.stderr
    assert _said(result, SWITCH_MARKER), output
    assert not _said(result, TOO_LONG_MARKER), output
    assert not _said(result, NOT_REMOVED_MARKER), output
    _assert_installed(base, commit, long_path)
    assert (home / "state" / "ledger.json").is_file(), output
    assert _leftovers(base) == [], output


# update.ps1 -----------------------------------------------------------------


@pytest.mark.parametrize("shell", POWERSHELLS)
def test_update_ps1_updates_a_clone_to_a_release_past_the_path_limit(
    base: Path, shell: str
) -> None:
    """The in-place update checks out a release whose path at APOTHEM_HOME
    passes the limit, and finds the checkout clean afterwards."""
    long_path = _path_at_home(base, UPDATED_LENGTH)
    commit = _clone_at_old_tag(base, long_path)
    home = base / HOME_NAME

    try:
        result = _run_powershell(shell, base, "update.ps1")

        output = result.stdout + result.stderr
        assert _said(result, TAG_OK_MARKER), output
        assert not _said(result, TOO_LONG_MARKER), output
        assert _said(result, UPDATED_MARKER), output
        assert git(["rev-parse", "HEAD"], home).strip() == commit
        long_file = _extended(home / long_path)
        assert long_file.read_text(encoding="utf-8") == LONG_TEXT
    finally:
        _move_long_tree_out(base, long_path)


# install.sh under Git Bash ---------------------------------------------------


@requires_git_bash
@pytest.mark.parametrize("dry_run", [False, True], ids=["install", "dry-run"])
def test_install_sh_checks_out_a_release_past_the_path_limit_under_git_bash(
    base: Path, dry_run: bool
) -> None:
    """install.sh's clone in its staging folder (or, for a dry run, in the
    temporary folder) is checked out with paths past the limit; the install
    moves it into place, the dry run removes it."""
    long_path = _path_at_home(base, INSTALLED_LENGTH)
    staging = (
        str(Path("temp") / "tmp.0123456789") if dry_run else ".apothem-clone.012345"
    )
    assert _staged_length(base, long_path, staging) > MAX_PATH
    commit = _release(base, long_path)

    flags = ("--dry-run", "--yes") if dry_run else ("--yes",)
    result = _run_git_bash(base, "install.sh", *flags)

    output = result.stdout + result.stderr
    assert _said(result, TAG_OK_MARKER), output
    assert not _said(result, TOO_LONG_MARKER), output
    assert _said(result, READY_MARKER), output
    if dry_run:
        assert _said(result, DRY_RUN_MARKER), output
        assert not (base / HOME_NAME).exists(), output
    else:
        _assert_installed(base, commit, long_path)
    assert _leftovers(base) == [], output
